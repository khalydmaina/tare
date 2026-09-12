#!/usr/bin/env python3
"""Check the Bitget demo API keys with the bot's own broker code.

Read-only by default: futures balance and position mode. With --order it opens the smallest
demo position (attached stop-loss and take-profit, the same request the bot sends), confirms
the exchange holds it, then closes it. Never prints the keys.

    python scripts/check_bitget_demo.py
    python scripts/check_bitget_demo.py --order --symbol DOGEUSDT
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from execution.bitget_broker import PaperBroker, Side, exchange_size  # noqa: E402

PRODUCT = "USDT-FUTURES"
TEST_NOTIONAL_USDT = 10.0


def explain(exc: Exception) -> str:
    """Bitget puts the useful reason (bad sign, wrong environment) in the response body."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
    return str(exc)[:300]


def first(data: Any) -> dict:
    return (data[0] if isinstance(data, list) and data else data) or {}


def compare_prices(broker: PaperBroker) -> int:
    """Demo-environment last price against the public market, per watchlist symbol.

    The bot reads candles from the public market unauthenticated and sends orders to the
    demo environment with the paptrading header. If those two disagree, a stop computed
    from public candles can sit on the wrong side of the demo price, and a fill on the
    demo book cannot be scored against public candles.
    """
    from core.config import load_settings

    symbols = load_settings()["market"]["symbols"]
    print(f"\ndemo price vs public market, {len(symbols)} symbols:")
    rows = []
    for sym in symbols:
        try:
            public = float(first(httpx.get(
                f"{broker.BASE}/api/v2/mix/market/ticker",
                params={"symbol": sym, "productType": PRODUCT}, timeout=20,
            ).json().get("data"))["lastPr"])
            demo = float(first(broker._get(
                "/api/v2/mix/market/ticker", {"symbol": sym, "productType": PRODUCT}
            ))["lastPr"])
        except Exception as exc:
            print(f"  {sym}: could not compare ({explain(exc)})")
            continue
        gap = (demo - public) / public * 100 if public else float("nan")
        rows.append(abs(gap))
        print(f"  {sym:10} public {public:>14.6g}  demo {demo:>14.6g}  {gap:+7.2f}%")
    if rows:
        worst = max(rows)
        print(f"largest absolute gap {worst:.2f}% across {len(rows)} symbols")
        if worst > 0.25:
            print("the demo environment is NOT quoting the public market: orders priced from "
                  "public candles will be rejected or filled at unrelated prices")
            return 1
        print("demo and public prices agree")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Bitget demo API keys")
    parser.add_argument("--symbol", default="DOGEUSDT", help="contract for the test order")
    parser.add_argument("--order", action="store_true", help="open and close one minimum-size demo position")
    parser.add_argument("--notional", type=float, default=TEST_NOTIONAL_USDT,
                        help="test order size in USDT (default the contract minimum)")
    parser.add_argument("--side", choices=("long", "short"), default="long",
                        help="direction of the test order")
    parser.add_argument("--compare-prices", action="store_true",
                        help="compare demo-environment prices against the public market")
    args = parser.parse_args()
    symbol = args.symbol.upper()

    broker = PaperBroker()
    if not broker._use_api:
        print("BITGET_API_KEY, BITGET_API_SECRET and BITGET_PASSPHRASE must all be set")
        return 1

    # 1. Read-only: the key signs, the passphrase matches, and it answers in demo mode
    try:
        accounts = broker._get("/api/v2/mix/account/accounts", {"productType": PRODUCT})
        acct = first(broker._get(
            "/api/v2/mix/account/account", {"symbol": symbol, "productType": PRODUCT, "marginCoin": "USDT"}
        ))
    except Exception as exc:
        print(f"FAILED reading the demo futures account: {explain(exc)}")
        return 1
    for a in accounts or []:
        print(f"demo futures {a.get('marginCoin')}: equity {a.get('accountEquity')}, available {a.get('available')}")
    # Demo money can sit in another demo wallet (spot, funding) until it is moved to futures
    for path, label in (("/api/v2/account/all-account-balance", "demo wallets (USDT value)"),
                        ("/api/v2/spot/account/assets", "demo spot coins")):
        try:
            rows = broker._get(path) or []
            shown = [
                (r.get("accountType"), r.get("usdtBalance")) if "accountType" in r
                else (r.get("coin"), r.get("available"))
                for r in rows
                if float(r.get("usdtBalance") or r.get("available") or 0) > 0
            ]
            print(f"{label}: {shown or 'all empty'}")
        except Exception as exc:
            print(f"{label}: could not read ({explain(exc)})")
    # Older demo accounts keep their money under the S-prefixed demo product type
    try:
        for a in broker._get("/api/v2/mix/account/accounts", {"productType": "SUSDT-FUTURES"}) or []:
            print(f"old-style demo futures {a.get('marginCoin')}: equity {a.get('accountEquity')}, "
                  f"available {a.get('available')}")
    except Exception as exc:
        print(f"old-style demo futures: could not read ({explain(exc)})")
    print(f"{symbol}: position mode {acct.get('posMode')}, margin mode {acct.get('marginMode')}, "
          f"cross leverage {acct.get('crossedMarginLeverage')}")
    if args.compare_prices:
        if compare_prices(broker) != 0:
            return 1

    if not args.order:
        print("read-only check passed")
        return 0

    # 2. One test order through the bot's own open request, then close it
    side = Side.LONG if args.side == "long" else Side.SHORT
    try:
        price = float(first(broker._get("/api/v2/mix/market/ticker", {"symbol": symbol, "productType": PRODUCT}))["lastPr"])
        spec = broker._contract_spec(symbol)
        size = max(exchange_size(args.notional / price, spec), spec["min_trade_num"])
        # Stop above and target below for a short, the way the bot sends them
        sl = price * (1.03 if side == Side.SHORT else 0.97)
        tp = price * (0.97 if side == Side.SHORT else 1.03)
        print(f"sending {args.side} {size:g} {symbol} (~{size * price:,.0f} USDT notional), "
              f"volumePlace {spec['volume_place']:g}, minTradeNum {spec['min_trade_num']:g}")
        fill, oid, qty = broker._place_api_order(symbol, side, size, sl, tp)
    except Exception as exc:
        print(f"FAILED opening the test position: {explain(exc)}")
        return 1
    print(f"opened {args.side} {qty} {symbol} at {fill} (order {oid}); stop {sl:.6g}, target {tp:.6g}")

    ok = True
    time.sleep(3)
    try:
        held = [
            (p.get("holdSide"), p.get("total"), p.get("openPriceAvg"))
            for p in broker._get("/api/v2/mix/position/single-position",
                                 {"symbol": symbol, "productType": PRODUCT, "marginCoin": "USDT"}) or []
            if float(p.get("total") or 0) > 0
        ]
        plans = broker._get("/api/v2/mix/order/orders-plan-pending",
                            {"productType": PRODUCT, "planType": "profit_loss", "symbol": symbol}) or {}
        attached = [(p.get("planType"), p.get("triggerPrice")) for p in plans.get("entrustedList") or []]
        print(f"exchange holds: {held}")
        print(f"attached stop-loss/take-profit: {attached}")
        ok = bool(held)
    except Exception as exc:
        print(f"could not read the position back: {explain(exc)}")
        ok = False

    try:
        pos = SimpleNamespace(symbol=symbol, side=side, size=qty, fill_price=fill)
        exit_px = broker._close_api_position(pos)  # type: ignore[arg-type]
        print(f"closed at {exit_px}")
    except Exception as exc:
        print(f"FAILED closing the test position, it is still open on the demo account "
              f"with its stop and target attached: {explain(exc)}")
        return 1

    # An earlier failed check may have left a test long behind; close whatever long remains
    time.sleep(2)
    try:
        left = sum(
            float(p.get("total") or 0)
            for p in broker._get("/api/v2/mix/position/single-position",
                                 {"symbol": symbol, "productType": PRODUCT, "marginCoin": "USDT"}) or []
            if p.get("holdSide") == args.side
        )
        if left > 0:
            leftover = SimpleNamespace(symbol=symbol, side=side, size=left, fill_price=fill)
            print(f"closing {left:g} {symbol} left from an earlier check at "
                  f"{broker._close_api_position(leftover)}")  # type: ignore[arg-type]
        print("no test position left open")
    except Exception as exc:
        print(f"could not confirm the demo account is flat: {explain(exc)}")
        ok = False
    print("order check passed" if ok else "order check incomplete: see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
