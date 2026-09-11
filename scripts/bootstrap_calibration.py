#!/usr/bin/env python3
"""Seed calibration matrix from historical replay (blind mode by default)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from backtest.replay import ReplayEngine  # noqa: E402
from core.config import ConfigBundle  # noqa: E402
from data.reference_feed import ReferenceFeed  # noqa: E402
from inspector.calibration import CalibrationMatrix  # noqa: E402
from trader.llm_trader import LLMTrader  # noqa: E402
from trader.smc import generate_setups  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bootstrap")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--limit", type=int, default=1000, help="Candles to fetch (15m)")
    parser.add_argument("--count-only", action="store_true", help="SMC setup count, no LLM")
    parser.add_argument("--blind", action="store_true", default=True)
    parser.add_argument("--no-blind", action="store_true")
    parser.add_argument("--max-setups", type=int, default=50)
    parser.add_argument("--mock-llm", action="store_true")
    parser.add_argument("--out", default=str(ROOT / "data" / "calibration.json"))
    args = parser.parse_args()
    blind = not args.no_blind

    cfg = ConfigBundle()
    feed = ReferenceFeed(cfg.settings["market"].get("reference_venue", "okx"))
    log.info("fetching %s candles…", args.symbol)
    c15 = feed.fetch_klines(args.symbol, "15m", min(args.limit, 1500))
    c1h = feed.fetch_klines(args.symbol, "1h", min(args.limit // 4 + 50, 1000))
    c4h = feed.fetch_klines(args.symbol, "4h", min(args.limit // 16 + 50, 500))
    log.info("got 15m=%d 1h=%d 4h=%d", len(c15), len(c1h), len(c4h))

    trader = LLMTrader(cfg.settings)

    def propose(setup, candles_by_tf, digest, indicators=None):
        if args.mock_llm or trader._client is None:
            # Heuristic confidence from setup_score for bootstrap without quota
            conf = int(50 + setup.setup_score * 40)
            return trader.propose_mock(setup, confidence=conf, action="take")
        return trader.propose(setup, candles_by_tf, digest, indicators or {})

    engine = ReplayEngine(
        generate_setups=generate_setups,
        propose=propose,
        smc_cfg=cfg.settings.get("smc", {}),
        timeout_bars=cfg.settings["calibration"]["timeout_bars"],
    )

    # Every bar: setups are only actionable on the bar they trigger (see generate_setups)
    if args.count_only:
        n = engine.count_setups_only(args.symbol, c15, c1h, c4h, step=1)
        log.info("SMC-only setup count≈%d (every bar). Estimate LLM calls≈%d", n, n)
        return

    result = engine.run(
        args.symbol,
        c15,
        c1h,
        c4h,
        blind=blind,
        step=1,
        max_setups=args.max_setups,
    )
    cal = CalibrationMatrix.from_settings(cfg.settings)
    for pair in result.pairs:
        if pair["action"] != "take":
            continue
        # regime proxy from setup_score tercile - bootstrap only
        regime = "low" if pair["setup_score"] < 0.45 else ("high" if pair["setup_score"] > 0.7 else "mid")
        cal.update_from_outcome(pair["confidence"], regime, pair["result"])

    out = Path(args.out)
    cal.save(out)
    log.info(
        "saved %s - setups=%d takes=%d",
        out,
        len(result.setups),
        sum(1 for p in result.pairs if p["action"] == "take"),
    )
    for b in cal.buckets:
        label = f"{b[0]}-{b[1]}"
        for r in cal.regimes:
            cell = cal.get_cell(label, r)
            if cell.n:
                log.info("cell %s|%s n=%d wins=%d wilson=%.3f", label, r, cell.n, cell.wins, cell.wilson())


if __name__ == "__main__":
    main()
