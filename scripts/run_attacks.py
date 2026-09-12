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
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from attacks.a5_adaptive import attacker_config, call_attacker, parse_variant  # noqa: E402
from attacks.harness import GATES, AttackHarness, Scenario, save_metrics  # noqa: E402
from backtest.blind import blind_bundle  # noqa: E402
from core.config import ConfigBundle, db_path  # noqa: E402
from core.schemas import Action, Candle, SentimentItem, Setup, Side  # noqa: E402
from data.sentiment_feed import SentimentFeed  # noqa: E402
from inspector.calibration import CalibrationMatrix  # noqa: E402
from inspector.gate import decide  # noqa: E402
from recorder.db import FlightRecorder  # noqa: E402
from trader.llm_trader import LLMTrader, _retry_after, build_user_payload  # noqa: E402
from trader.sim_trader import SimTrader  # noqa: E402

# Consecutive failed model calls that end the run instead of quietly thinning the calibration
MAX_FAILED_STREAK = 8
PUBLISHED = ROOT / "docs" / "attack_metrics.json"


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


def load_cache(cache_path: Path | None) -> dict[str, dict]:
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}


def spend(calls: dict) -> None:
    """Count one model call, stopping the run first if it would go past --max-calls."""
    if calls["max"] and calls["n"] >= calls["max"]:
        sys.exit(f"Stopped at the budget of {calls['max']} model calls. Every answer so far is "
                 "cached, so the next run resumes from here; nothing was measured.")
    calls["n"] += 1


def make_propose_fn(mode: str, settings: dict, cache_path: Path | None, cache_only: bool = False,
                    cache: dict | None = None, calls: dict | None = None):
    base = LLMTrader(settings)
    if mode == "sim":
        sim = SimTrader(base)
        return (lambda setup, tfs, digest: sim.propose(setup, tfs, digest)), "sim"

    if base._client is None and not cache_only:
        sys.exit("--llm real needs XAI_API_KEY (or the key named in llm.api_key_env)")

    cache = load_cache(cache_path) if cache is None else cache
    calls = {"n": 0, "max": 0} if calls is None else calls

    if cache_only:
        # Replaying a past run's answers to re-measure the gate after a policy change,
        # without spending quota. A miss is counted, never invented, and main() refuses to
        # write metrics if any occurred.
        misses = {"n": 0}

        def propose_cached(setup: Setup, tfs: dict, digest: str):
            b_setup, b_tfs, _ = blind_bundle(setup, {k: list(v) for k, v in tfs.items()})
            b_tfs = {k: v[-30:] for k, v in b_tfs.items()}
            indicators = {"setup_score": setup.setup_score, "bias": setup.bias}
            key = cache_key(base, build_user_payload(b_setup, b_tfs, digest, indicators))
            raw = cache.get(key)
            if raw is None:
                misses["n"] += 1
                p = base.propose_mock(setup, confidence=0, action="skip")
                p.invalid_output = True
                return p
            p = base.propose_mock(setup, confidence=raw["confidence"], action=raw["action"])
            p.rationale = raw.get("rationale", "")
            return p

        propose_cached.misses = misses  # type: ignore[attr-defined]
        return propose_cached, f"{base.model}@{base.base_url} (cached)"

    # A rate limit or a dead key makes every proposal an empty skip. Without this the run
    # finishes "fine" on a calibration built from nothing. The total matters too: a few
    # scattered failures would otherwise sit in the table as skips the model never chose.
    failures = {"streak": 0, "total": 0}

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
        spend(calls)
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
            failures["total"] += 1
            # The provider's own reason is on the proposal. Printing it is the difference
            # between "something failed" and knowing whether to pace the calls, wait for a
            # daily reset, or change the key.
            reason = (p.rationale or "").replace("invalid_output: ", "")
            print(f"  model call failed ({failures['streak']}/{MAX_FAILED_STREAK}): "
                  f"{reason[:300] or 'no reason given'}", flush=True)
            if failures["streak"] >= MAX_FAILED_STREAK:
                sys.exit(f"{MAX_FAILED_STREAK} model calls failed in a row. Last reason: "
                         f"{reason[:500] or 'none given'}\nStopping: a thinned calibration must "
                         "not pass as a finished run.")
        return p

    propose.failures = failures  # type: ignore[attr-defined]
    return propose, f"{base.model}@{base.base_url}"


def make_attacker_writer(cache: dict, cache_path: Path | None, cache_only: bool, calls: dict,
                         misses: dict, tries: int = 3):
    """A5's attacker, cached like the Trader: same prompt, same model, same headline.

    The attacker's prompt carries only what the gate said about earlier attempts, so once the
    Trader's answers and the attacker's are both cached the whole closed loop replays."""
    key, base_url, model = attacker_config()
    if not key and not cache_only:
        sys.exit("A5 with --llm real needs ATTACKER_API_KEY (and ATTACKER_BASE_URL / "
                 "ATTACKER_MODEL). Without one it walks a scripted ladder, which is plumbing, "
                 "not a measurement of an adaptive attacker.")

    def write(prompt: str, attempt: int) -> tuple[str, str]:
        k = hashlib.sha256("\n\x1f".join(["attacker", model, base_url, prompt]).encode()).hexdigest()
        if k in cache:
            return cache[k]["text"], cache[k]["source"]
        if cache_only:
            misses["n"] += 1
            return "(attacker answer missing from the cache)", f"missing-{attempt}"
        reason = ""
        for i in range(tries):
            spend(calls)
            try:
                text, source = parse_variant(call_attacker(prompt, key, base_url, model), attempt)
            except Exception as exc:  # noqa: BLE001 - retried, then the run stops
                reason = str(exc)
                print(f"  attacker call failed ({i + 1}/{tries}): {reason[:300]}", flush=True)
                if i + 1 < tries:
                    time.sleep(_retry_after(exc))
                continue
            cache[k] = {"text": text, "source": source}
            if cache_path:
                cache_path.write_text(json.dumps(cache))
            return text, source
        sys.exit(f"The attacker model failed {tries} times on one prompt. Last reason: "
                 f"{reason[:500]}\nStopping: rows from a scripted stand-in would not be the "
                 "adaptive attack.")

    return write, f"{model}@{base_url}"


def narrower_than(published: Path, meta: dict) -> list[str]:
    """What the published table covers that this run leaves out; empty if nothing is lost."""
    if not published.exists():
        return []
    try:
        old = json.loads(published.read_text()).get("meta", {})
    except ValueError:
        return []
    lost = [f"attack {a}" for a in old.get("attacks", []) if a not in meta["attacks"]]
    lost += [f"gate {g}" for g in old.get("gates", []) if g not in meta["gates"]]
    if (old.get("eval_scenarios") or 0) > meta["eval_scenarios"]:
        lost.append(f"{old['eval_scenarios'] - meta['eval_scenarios']} eval scenarios")
    return lost


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
    ap.add_argument("--max-calls", type=int, default=0,
                    help="stop before the model call that would exceed this many (0 = no cap). "
                         "Answers are cached, so the next run resumes where this one stopped")
    ap.add_argument("--allow-narrower", action="store_true",
                    help="publish even if this run covers fewer attacks, gates or scenarios "
                         "than the table already in docs/attack_metrics.json")
    ap.add_argument("--no-background", action="store_true")
    ap.add_argument("--cache-only", action="store_true",
                    help="answer only from data/llm_cache.json; never call the model. Reports "
                         "what is missing and refuses to write metrics from a partial cache")
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

    cache_path = ROOT / "data" / "llm_cache.json" if args.llm == "real" else None
    cache = load_cache(cache_path)
    calls = {"n": 0, "max": args.max_calls}
    propose, trader_label = make_propose_fn(
        args.llm, cfg.settings, cache_path, cache_only=args.cache_only, cache=cache, calls=calls,
    )
    attack_ids = [a.strip() for a in args.attacks.split(",") if a.strip()]
    attacker_writer, attacker_label = None, None
    if "A5" in attack_ids:
        attacker_label = "scripted ladder (not evidence)"
        if args.llm == "real":
            attacker_writer, attacker_label = make_attacker_writer(
                cache, cache_path, args.cache_only, calls, getattr(propose, "misses", {"n": 0}),
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
        trader_label=trader_label, attacker_writer=attacker_writer,
    )
    metrics = harness.run(
        eval_set,
        attack_ids=attack_ids,
        gate_configs=[g.strip() for g in args.gates.split(",") if g.strip()],
        a5_subset=args.a5_subset, a5_attempts=args.a5_attempts,
    )
    metrics.meta.update({"cal_scenarios": len(cal_set), "cal_takes": takes,
                         "eval_scenarios": len(eval_set),
                         "scenario_source": args.scenarios or "synthetic",
                         "generated_at": datetime.now(timezone.utc).isoformat()})
    if attacker_label:
        metrics.meta["attacker"] = attacker_label
    print(f"model calls this run: {calls['n']}")
    missed = getattr(propose, "misses", {}).get("n", 0) if args.cache_only else 0
    if missed:
        sys.exit(f"{missed} answers were not in the cache, so this replay is incomplete and "
                 "nothing was written. Run without --cache-only to fill them in.")
    failed = getattr(propose, "failures", {}).get("total", 0)
    if failed:
        sys.exit(f"{failed} model calls failed, so their scenarios hold skips the model never "
                 "chose and nothing was written. The answers that did arrive are cached; run "
                 "again to fill in the rest.")

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

    # A run over part of the table fills the cache for that part; it must not replace the
    # whole published table with the slice it happened to measure. The Attack Lab files
    # mirror the published table, so they are only written alongside it.
    out = Path(args.out)
    publishing = out.resolve() == PUBLISHED.resolve()
    lost = narrower_than(PUBLISHED, metrics.meta) if publishing and not args.allow_narrower else []
    if lost:
        print(f"\nnot publishing: the table in {PUBLISHED.relative_to(ROOT)} also covers "
              f"{', '.join(lost)}. Run the full table (answers already cached cost nothing) or "
              "pass --allow-narrower.")
        return
    save_metrics(metrics, out)
    print(f"\nwrote {out}")
    if not publishing:
        return

    # Attack Lab demo: first 3 eval scenarios, real rows and real checks
    ids = {sc.scenario_id for sc in eval_set[:3]}
    demo = [r for r in metrics.rows if r["scenario_id"] in ids]
    for p in (ROOT / "docs" / "attack_lab_demo.json", ROOT / "web" / "public" / "attack_lab_demo.json"):
        p.write_text(json.dumps({"meta": metrics.meta, "rows": demo}, indent=2, default=str))
    (ROOT / "web" / "public" / "attack_metrics.json").write_text(
        json.dumps({"meta": metrics.meta, "summary": metrics.summary_table()}, indent=2, default=str)
    )


if __name__ == "__main__":
    main()
