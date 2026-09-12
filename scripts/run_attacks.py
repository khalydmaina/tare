#!/usr/bin/env python3
"""Scenario bank x attacks x gates. Writes docs/attack_metrics.json.

Two modes:
  --llm real   Real Trader model (XAI_API_KEY). Candles are blinded before they
               reach the prompt. THE ONLY MODE WHOSE NUMBERS GO IN THE WRITE-UP.
  --llm sim    Deterministic simulated trader. Plumbing and dashboard only.

Calibration is walk-forward: the first --cal-split of scenarios (by time) is
run clean through the Trader to fill the matrix, which is then frozen; attacks
are evaluated only on the later scenarios. No hand-seeded buckets.

Examples:
  python scripts/build_scenarios.py --days 45
  python scripts/run_attacks.py --scenarios data/scenarios.jsonl --llm real --max-eval 120
  python scripts/run_attacks.py --llm sim          # synthetic, offline
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from attacks.harness import GATES, AttackHarness, Scenario, save_metrics  # noqa: E402
from backtest.blind import blind_bundle  # noqa: E402
from core.config import ConfigBundle, db_path  # noqa: E402
from core.schemas import Action, Candle, SentimentItem, Setup, Side  # noqa: E402
from data.sentiment_feed import SentimentFeed  # noqa: E402
from inspector.calibration import CalibrationMatrix  # noqa: E402
from inspector.gate import decide  # noqa: E402
from recorder.db import FlightRecorder  # noqa: E402
from trader.llm_trader import LLMTrader, build_user_payload  # noqa: E402
from trader.sim_trader import SimTrader  # noqa: E402

# Consecutive failed model calls that end the run instead of quietly thinning the calibration
MAX_FAILED_STREAK = 8


# --------------------------------------------------------------------------- #
# Scenario loading
# --------------------------------------------------------------------------- #
def _candles(rows: list, symbol: str, tf: str, source: str) -> list[Candle]:
    minutes = {"15m": 15, "1h": 60, "4h": 240}[tf]
    out = []
    for ts, o, h, l, c, v in rows:
        ot = datetime.fromisoformat(ts)
        out.append(Candle(symbol=symbol, timeframe=tf, open_time=ot,
                          close_time=ot + timedelta(minutes=minutes), open=o, high=h,
                          low=l, close=c, volume=v, source=source, fetched_at=ot))
    return out


def load_scenarios(path: Path) -> list[Scenario]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        sym = d["symbol"]
        out.append(Scenario(
            scenario_id=d["scenario_id"], setup=Setup(**d["setup"]),
            candles_15m=_candles(d["c15"], sym, "15m", "bitget"),
            candles_1h=_candles(d["c1h"], sym, "1h", "bitget"),
            candles_4h=_candles(d["c4h"], sym, "4h", "bitget"),
            reference_15m=_candles(d["r15"], sym, "15m", d.get("reference_venue", "binance")),
            sentiment=[], true_result=d["true_result"], regime=d.get("regime", "mid"),
            r_multiple=d.get("r_multiple"), as_of=datetime.fromisoformat(d["as_of"]),
        ))
    out.sort(key=lambda s: s.as_of or datetime.min.replace(tzinfo=timezone.utc))
    return out


def synthetic_scenarios(n: int, seed: int = 7) -> list[Scenario]:
    """Offline bank with a real signal: higher setup_score wins more often."""
    rng = random.Random(seed)
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        side = Side.LONG if rng.random() < 0.5 else Side.SHORT
        score = rng.uniform(0.3, 0.95)
        px, bars, ref = 100.0 + rng.uniform(-5, 5), [], []
        for k in range(80):
            o = px
            c = px * (1 + rng.gauss(0, 0.002))
            ot = t0 + timedelta(minutes=15 * (k + i * 100))
            j = 1 + rng.gauss(0, 0.0002)
            for series, oo, cc, src in ((bars, o, c, "synth"), (ref, o * j, c * j, "synth-ref")):
                series.append(Candle(
                    symbol="SYN", timeframe="15m", open_time=ot,
                    close_time=ot + timedelta(minutes=15), open=oo,
                    high=max(oo, cc) * 1.001, low=min(oo, cc) * 0.999, close=cc,
                    volume=1000 + rng.random() * 50, source=src,
                    fetched_at=ot + timedelta(minutes=15),
                ))
            px = c
        entry = bars[-1].close
        risk = entry * 0.006
        sl = entry - risk if side == Side.LONG else entry + risk
        tp = entry + 2 * risk if side == Side.LONG else entry - 2 * risk
        win = rng.random() < 0.22 + 0.40 * score  # breakeven at rr=2 is 0.333
        out.append(Scenario(
            scenario_id=f"syn-{i:04d}",
            setup=Setup(symbol="SYN", side=side, entry=entry, sl=sl, tp=tp, rr=2.0,
                        structure_summary="synthetic", setup_score=round(score, 3)),
            candles_15m=bars, candles_1h=bars[::4], candles_4h=bars[::16], reference_15m=ref,
            sentiment=[], true_result="win" if win else "loss",
            regime=["low", "mid", "high"][i % 3], r_multiple=2.0 if win else -1.0,
            as_of=bars[-1].close_time,
        ))
    return out


def add_background(scenarios: list[Scenario], k: int = 4, seed: int = 11) -> None:
    """Give clean scenarios ordinary news so the defences have to discriminate."""
    pool = json.loads((ROOT / "data" / "background_headlines.json").read_text())
    rng = random.Random(seed)
    for sc in scenarios:
        ts = sc.as_of or datetime.now(timezone.utc)
        sc.sentiment = [
            SentimentItem(source=h["source"], text=h["text"], score=h["score"],
                          published_at=ts - timedelta(minutes=rng.randint(5, 300)))
            for h in rng.sample(pool, k)
        ]


# --------------------------------------------------------------------------- #
# Trader adapters
# --------------------------------------------------------------------------- #
def cache_key(trader: LLMTrader, payload: str) -> str:
    """Exactly what the model sees, plus which model and prompt answer it."""
    parts = [trader.model, trader.base_url, trader.prompt_version, trader.system_prompt, payload]
    return hashlib.sha256("\n\x1f".join(parts).encode("utf-8")).hexdigest()


def make_propose_fn(mode: str, settings: dict, cache_path: Path | None):
    base = LLMTrader(settings)
    if mode == "sim":
        sim = SimTrader(base)
        return (lambda setup, tfs, digest: sim.propose(setup, tfs, digest)), "sim"

    if base._client is None:
        sys.exit("--llm real needs XAI_API_KEY (or the key named in llm.api_key_env)")

    cache: dict[str, dict] = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())
    # A rate limit or a dead key makes every proposal an empty skip. Without this the run
    # finishes "fine" on a calibration built from nothing.
    failures = {"streak": 0}

    def propose(setup: Setup, tfs: dict, digest: str):
        b_setup, b_tfs, _ = blind_bundle(setup, {k: list(v) for k, v in tfs.items()})
        b_tfs = {k: v[-30:] for k, v in b_tfs.items()}
        indicators = {"setup_score": setup.setup_score, "bias": setup.bias}
        key = cache_key(base, build_user_payload(b_setup, b_tfs, digest, indicators))
        if key in cache:
            raw = cache[key]
            p = base.propose_mock(setup, confidence=raw["confidence"], action=raw["action"])
            p.rationale = raw.get("rationale", "")
            return p
        p = base.propose(b_setup, b_tfs, digest, indicators)
        # Levels always come from the setup; put the real prices back
        p.entry, p.sl, p.tp = setup.entry, setup.sl, setup.tp
        if not p.invalid_output:  # a transient API error must not become a cached skip
            failures["streak"] = 0
            cache[key] = {"confidence": p.confidence, "action": p.action.value,
                          "rationale": p.rationale}
            if cache_path:
                cache_path.write_text(json.dumps(cache))
        else:
            failures["streak"] += 1
            if failures["streak"] >= MAX_FAILED_STREAK:
                sys.exit(f"{MAX_FAILED_STREAK} model calls failed in a row (rate limit, quota or "
                         "key). Stopping: a thinned calibration must not pass as a finished run.")
        return p

    return propose, f"{base.model}@{base.base_url}"


def fill_calibration(cal: CalibrationMatrix, scenarios: list[Scenario], propose) -> int:
    n = 0
    for sc in scenarios:
        tfs = {"15m": sc.candles_15m, "1h": sc.candles_1h, "4h": sc.candles_4h}
        p = propose(sc.setup, tfs, SentimentFeed.digest(sc.sentiment))
        if p.action == Action.TAKE:
            cal.update(p.confidence, sc.regime, sc.true_result == "win")
            n += 1
    return n


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", choices=["sim", "real"], default="sim")
    ap.add_argument("--scenarios", help="JSONL from build_scenarios.py (default: synthetic)")
    ap.add_argument("--n", type=int, default=300, help="Synthetic scenario count")
    ap.add_argument("--cal-split", type=float, default=0.6)
    ap.add_argument("--max-eval", type=int, default=0, help="Cap eval scenarios (cost control)")
    ap.add_argument("--attacks", default="A1,A2,A3,A4,A4F,A5")
    ap.add_argument("--gates", default=",".join(GATES))
    ap.add_argument("--a5-subset", type=int, default=20)
    ap.add_argument("--a5-attempts", type=int, default=10)
    ap.add_argument("--no-background", action="store_true")
    ap.add_argument("--save-calibration", action="store_true",
                    help="Also write the walk-forward matrix to data/calibration.json")
    ap.add_argument("--out", default=str(ROOT / "docs" / "attack_metrics.json"))
    args = ap.parse_args()

    cfg = ConfigBundle()
    scenarios = load_scenarios(Path(args.scenarios)) if args.scenarios else synthetic_scenarios(args.n)
    if not args.no_background:
        add_background(scenarios)

    split = int(len(scenarios) * args.cal_split)
    cal_set, eval_set = scenarios[:split], scenarios[split:]
    if args.max_eval:
        eval_set = eval_set[: args.max_eval]

    propose, trader_label = make_propose_fn(
        args.llm, cfg.settings, ROOT / "data" / "llm_cache.json" if args.llm == "real" else None
    )

    cal = CalibrationMatrix.from_settings(cfg.settings)
    takes = fill_calibration(cal, cal_set, propose)
    print(f"calibration: {len(cal_set)} scenarios, {takes} takes (trader={trader_label})")
    for lo, hi in cal.buckets:
        n = sum(cal.get_cell(f"{lo}-{hi}", r).n for r in cal.regimes)
        w = sum(cal.get_cell(f"{lo}-{hi}", r).wins for r in cal.regimes)
        if n:
            print(f"  bucket {lo}-{hi}: n={n} hit={w / n:.2f} p_cal={cal.lookup(lo, 'mid'):.3f}")
    if args.save_calibration:
        if trader_label == "sim":
            print("not saving: a simulated-trader matrix must never reach data/calibration.json, "
                  "which the live loop sizes real decisions with")
        else:
            cal.save(ROOT / "data" / "calibration.json")

    harness = AttackHarness(
        decide_fn=decide, propose_fn=propose, calibration=cal, settings=cfg.settings,
        limits=cfg.limits, recorder=FlightRecorder(db_path(cfg.settings)),
        trader_label=trader_label,
    )
    metrics = harness.run(
        eval_set,
        attack_ids=[a.strip() for a in args.attacks.split(",") if a.strip()],
        gate_configs=[g.strip() for g in args.gates.split(",") if g.strip()],
        a5_subset=args.a5_subset, a5_attempts=args.a5_attempts,
    )
    metrics.meta.update({"cal_scenarios": len(cal_set), "cal_takes": takes,
                         "eval_scenarios": len(eval_set),
                         "scenario_source": args.scenarios or "synthetic",
                         "generated_at": datetime.now(timezone.utc).isoformat()})
    save_metrics(metrics, args.out)

    # Attack Lab demo: first 3 eval scenarios, real rows and real checks
    ids = {sc.scenario_id for sc in eval_set[:3]}
    demo = [r for r in metrics.rows if r["scenario_id"] in ids]
    for p in (ROOT / "docs" / "attack_lab_demo.json", ROOT / "web" / "public" / "attack_lab_demo.json"):
        p.write_text(json.dumps({"meta": metrics.meta, "rows": demo}, indent=2, default=str))
    (ROOT / "web" / "public" / "attack_metrics.json").write_text(
        json.dumps({"meta": metrics.meta, "summary": metrics.summary_table()}, indent=2, default=str)
    )

    gates = metrics.meta["gates"]
    print(f"\ntrader={trader_label} eval={len(eval_set)}")
    print(f"{'attack':<8}" + "".join(f"{g:>14}" for g in gates) + "   (HAR / ASR)")
    for row in metrics.summary_table():
        cells = []
        for g in gates:
            har, asr = row.get(f"{g}_HAR"), row.get(f"{g}_ASR")
            h = "-" if har is None else f"{har:.2f}"
            a = "-" if asr is None else f"{asr:.2f}"
            cells.append(f"{h} / {a}")
        print(f"{row['attack']:<8}" + "".join(f"{c:>14}" for c in cells))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
