#!/usr/bin/env python3
"""Which USDT perpetuals exist on both venues, ranked by turnover.

The bot reads candles from Bitget and cross-checks every price against OKX, so a coin is
only usable when both venues list it. Run this from a GitHub runner: this machine's network
blocks both exchanges.

    python scripts/list_symbols.py --top 30
"""

from __future__ import annotations

import argparse
import json

import httpx

BITGET = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
OKX = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"


def turnover(row: dict) -> float:
    for key in ("usdtVolume", "quoteVolume", "volCcy24h", "baseVolume"):
        try:
            value = float(row.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if value:
            return value
    return 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    with httpx.Client(timeout=30) as client:
        bitget = client.get(BITGET).json().get("data") or []
        okx = client.get(OKX).json().get("data") or []

    on_okx = {
        row["instId"].replace("-USDT-SWAP", "") + "USDT"
        for row in okx
        if str(row.get("instId", "")).endswith("-USDT-SWAP")
    }
    both = sorted(
        ((turnover(r), r["symbol"]) for r in bitget
         if str(r.get("symbol", "")).endswith("USDT") and r["symbol"] in on_okx),
        reverse=True,
    )

    print(f"{len(bitget)} Bitget perps, {len(on_okx)} OKX perps, {len(both)} on both")
    print(f"top {args.top} by 24h turnover:")
    for value, symbol in both[: args.top]:
        print(f"  {symbol:14s} {value / 1e6:10,.0f}M")
    print("\nsettings list:")
    print(json.dumps([s for _, s in both[: args.top]]))


if __name__ == "__main__":
    main()
