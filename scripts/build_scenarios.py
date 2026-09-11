#!/usr/bin/env python3
"""Build a REAL scenario bank for the attack harness.

Pulls historical Bitget USDT-futures candles (what the Trader sees) and
Binance USDT-M futures candles (the Inspector's independent reference),
walks the deterministic SMC engine forward bar by bar, and labels every
setup with what actually happened next (TP before SL = win, SL first or
timeout = loss). No LLM calls here, so it is free to run.

Output: data/scenarios.jsonl, one scenario per line, consumed by
    python scripts/run_attacks.py --scenarios data/scenarios.jsonl --llm real

Usage:
    python scripts/build_scenarios.py --days 45 --symbols BTCUSDT,ETHUSDT,SOLUSDT
"""

from __future__ import annotations

import argparse
import bisect
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import ConfigBundle  # noqa: E402
from core.schemas import Candle  # noqa: E402
from data.bitget_feed import TF_MAP as BG_TF, BitgetFeed  # noqa: E402
from data.reference_feed import TF_MAP as BN_TF, ReferenceFeed  # noqa: E402
from execution.labeler import resolve  # noqa: E402
from inspector.regime import ATR_PERIOD, LOOKBACK_BARS, atr_pct_series, regime_from_history  # noqa: E402
from trader.candidates import find_candidates  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scenarios")
TF_MIN = {"15m": 15, "1h": 60, "4h": 240}


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def bitget_history(symbol: str, tf: str, start: datetime, end: datetime) -> list[Candle]:
    """Page backwards through /api/v2/mix/market/history-candles (200 per call)."""
    feed = BitgetFeed(paper=True)
    out: dict[datetime, Candle] = {}
    cursor = end
    step = timedelta(minutes=TF_MIN[tf] * 200)
    while cursor > start:
        params = {
            "symbol": symbol, "productType": "USDT-FUTURES", "granularity": BG_TF[tf],
            "startTime": str(_ms(max(start, cursor - step))), "endTime": str(_ms(cursor)),
            "limit": "200",
        }
        raw = feed._get("/api/v2/mix/market/history-candles", params=params)
        batch = feed._parse_candles(raw, symbol, tf)
        if not batch:
            cursor -= step
            continue
        for c in batch:
            out[c.open_time] = c
        cursor = min(c.open_time for c in batch)
        time.sleep(0.12)  # stay well under public rate limits
    return sorted((c for c in out.values() if start <= c.open_time < end), key=lambda c: c.open_time)


def binance_history(symbol: str, tf: str, start: datetime, end: datetime) -> list[Candle]:
    ref = ReferenceFeed("binance")
    out: dict[datetime, Candle] = {}
    cursor = start
    with httpx.Client(timeout=20.0) as client:
        while cursor < end:
            r = client.get("https://fapi.binance.com/fapi/v1/klines", params={
                "symbol": symbol, "interval": BN_TF[tf], "startTime": _ms(cursor),
                "endTime": _ms(end), "limit": 1500,
            })
            r.raise_for_status()
            batch = ref._parse_binance(r.json(), symbol, tf)
            if not batch:
                break
            for c in batch:
                out[c.open_time] = c
            cursor = max(c.open_time for c in batch) + timedelta(minutes=TF_MIN[tf])
            time.sleep(0.1)
    return sorted(out.values(), key=lambda c: c.open_time)


def _dump(c: Candle) -> list:
    return [c.open_time.isoformat(), c.open, c.high, c.low, c.close, c.volume]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--step", type=int, default=4, help="Bars between SMC scans")
    ap.add_argument("--lookback", type=int, default=200)
    ap.add_argument("--dedupe-bars", type=int, default=8,
                    help="Skip a new setup on the same symbol/side within N bars")
    ap.add_argument("--out", default=str(ROOT / "data" / "scenarios.jsonl"))
    args = ap.parse_args()

    cfg = ConfigBundle()
    smc_cfg = cfg.settings.get("smc", {})
    timeout = int(cfg.settings["calibration"]["timeout_bars"])
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(hours=2)
    start = end - timedelta(days=args.days)

    n_out, results = 0, {"win": 0, "loss": 0}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for symbol in [s.strip() for s in args.symbols.split(",") if s.strip()]:
            log.info("%s: fetching %d days", symbol, args.days)
            c15 = bitget_history(symbol, "15m", start, end)
            # 31 extra days of 1h bars so the regime tercile has a full 30-day history
            c1h = bitget_history(symbol, "1h", start - timedelta(days=31), end)
            c4h = bitget_history(symbol, "4h", start - timedelta(days=40), end)
            r15 = binance_history(symbol, "15m", start, end)
            log.info("%s: bitget 15m=%d 1h=%d 4h=%d | binance 15m=%d",
                     symbol, len(c15), len(c1h), len(c4h), len(r15))
            ref_by_t = {c.open_time: c for c in r15}
            # Same regime definition as the live loop (inspector/regime.py):
            # atr_series[j] belongs to c1h[j + ATR_PERIOD]
            atr_series = atr_pct_series(c1h)
            closes_1h = [c.close_time for c in c1h]
            last_seen: dict[str, int] = {}

            for i in range(args.lookback, len(c15) - timeout, args.step):
                window = c15[i - args.lookback: i]
                t = window[-1].close_time
                k = bisect.bisect_right(closes_1h, t)  # 1h bars closed by t
                w1 = c1h[:k][-args.lookback:]
                w4 = [c for c in c4h if c.close_time <= t][-args.lookback:]
                if len(w1) < 50 or len(w4) < 30:
                    continue
                n_atr = k - ATR_PERIOD
                regime = (
                    regime_from_history(atr_series[max(0, n_atr - LOOKBACK_BARS):n_atr],
                                        atr_series[n_atr - 1])
                    if n_atr > 0 else "mid"
                )

                for setup in find_candidates(window, w1, w4, symbol, smc_cfg):
                    key = setup.side.value
                    if i - last_seen.get(key, -10_000) < args.dedupe_bars:
                        continue
                    last_seen[key] = i
                    outcome = resolve(entry=setup.entry, sl=setup.sl, tp=setup.tp,
                                      side=setup.side.value, candles=c15[i: i + timeout],
                                      timeout_bars=timeout)
                    res = outcome.result.value
                    if res not in ("win", "loss", "timeout"):
                        continue
                    label = "win" if res == "win" else "loss"
                    ref_window = [ref_by_t[c.open_time] for c in window[-50:] if c.open_time in ref_by_t]
                    if len(ref_window) < 40:
                        continue
                    fh.write(json.dumps({
                        "scenario_id": f"{symbol}-{t.strftime('%Y%m%d%H%M')}-{key}",
                        "symbol": symbol,
                        "as_of": t.isoformat(),
                        "regime": regime,
                        "true_result": label,
                        "outcome": res,
                        "r_multiple": outcome.r_multiple,
                        "setup": setup.model_dump(mode="json"),
                        "c15": [_dump(c) for c in window[-50:]],
                        "c1h": [_dump(c) for c in w1[-50:]],
                        "c4h": [_dump(c) for c in w4[-50:]],
                        "r15": [_dump(c) for c in ref_window],
                    }) + "\n")
                    n_out += 1
                    results[label] += 1
    log.info("wrote %d scenarios to %s (wins=%d losses=%d)", n_out, out_path,
             results["win"], results["loss"])


if __name__ == "__main__":
    main()
