#!/usr/bin/env python3
"""Measure real Bitget vs Binance 15m close deviation to set C1's threshold.

C1 hard-vetoes when |bitget_close - binance_close| / binance_close exceeds
anomaly.cross_venue_max_dev (0.003 by default) on any of the last 10 bars.
If normal basis ever gets near that, clean trades get vetoed in fast markets.
This prints the distribution of the worst deviation in each 10-bar window,
which is exactly what C1 sees.

    python scripts/measure_basis.py --days 30
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_scenarios import binance_history, bitget_history  # noqa: E402


def pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    end = datetime.now(timezone.utc) - timedelta(hours=1)
    start = end - timedelta(days=args.days)
    for sym in args.symbols.split(","):
        bg = {c.open_time: c.close for c in bitget_history(sym, "15m", start, end)}
        bn = {c.open_time: c.close for c in binance_history(sym, "15m", start, end)}
        ts = sorted(set(bg) & set(bn))
        dev = [abs(bg[t] - bn[t]) / bn[t] for t in ts]
        win = [max(dev[i - 10:i]) for i in range(10, len(dev))]
        if not win:
            print(f"{sym}: no overlap")
            continue
        print(f"{sym}: bars={len(ts)}  window-max deviation  "
              f"p50={pct(win, .5):.5f} p99={pct(win, .99):.5f} "
              f"p99.9={pct(win, .999):.5f} max={max(win):.5f}")
        print(f"   suggested cross_venue_max_dev >= {max(0.003, 1.5 * pct(win, .999)):.4f}")


if __name__ == "__main__":
    main()
