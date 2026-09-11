#!/usr/bin/env python3
"""Seed a demo SQLite DB so the dashboard is demoable without live trading."""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.schemas import (  # noqa: E402
    Action,
    AnomalyBreakdown,
    Decision,
    DecisionKind,
    Proposal,
    Setup,
    Side,
)
from recorder.db import FlightRecorder  # noqa: E402


def main() -> None:
    db = ROOT / "data" / "demo.db"
    if db.exists():
        db.unlink()
    rec = FlightRecorder(db)
    rec.set_status("running", "demo seed")

    rng = random.Random(42)
    equity_g = 10_000.0
    equity_s = 10_000.0
    peak_g = equity_g
    now = datetime.now(timezone.utc)

    # Calibration snapshot
    for lo, hi in [(50, 59), (60, 69), (70, 79), (80, 89), (90, 100)]:
        for regime in ("low", "mid", "high"):
            n = rng.randint(5, 40)
            # overconfident at high buckets
            hit = max(0.25, 0.55 - (lo - 50) * 0.005 + rng.uniform(-0.05, 0.05))
            wins = int(n * hit)
            p = wins / n if n else 0
            # rough wilson
            z = 1.96
            denom = 1 + z**2 / n
            centre = p + z**2 / (2 * n)
            margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
            w = (centre - margin) / denom
            rec.insert_calibration_snapshot(f"{lo}-{hi}|{regime}", n, wins, w)

    reasons = [
        ("approve", "calibrated_edge"),
        ("shrink", "reduced_size"),
        ("veto", "no_calibrated_edge"),
        ("veto", "input_anomaly"),
        ("veto", "invalid_or_low_conf"),
        ("skip", "trader_skip"),
    ]

    for i in range(60):
        ts = now - timedelta(minutes=15 * (60 - i))
        symbol = rng.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        side = rng.choice([Side.LONG, Side.SHORT])
        entry = 100 + rng.random() * 10
        sl = entry - 1 if side == Side.LONG else entry + 1
        tp = entry + 2 if side == Side.LONG else entry - 2
        cycle_id = rec.insert_cycle(symbol, "deadbeef", "trader_v1", "mid", ts)
        setup = Setup(
            symbol=symbol,
            side=side,
            entry=entry,
            sl=sl,
            tp=tp,
            rr=2.0,
            structure_summary="demo sweep+FVG",
            setup_score=0.6 + rng.random() * 0.3,
        )
        setup_id = rec.insert_setup(cycle_id, setup)
        kind_s, reason = reasons[i % len(reasons)]
        conf = rng.randint(55, 95)
        prop = Proposal(
            action=Action.SKIP if kind_s == "skip" else Action.TAKE,
            side=side,
            entry=entry,
            sl=sl,
            tp=tp,
            confidence=conf,
            rationale="demo proposal",
            rr=2.0,
        )
        pid = rec.insert_proposal(setup_id, prop)
        p_cal = 0.35 + (100 - conf) * 0.002
        decision = Decision(
            kind=DecisionKind(kind_s),
            reason=reason,
            size=0.01 if kind_s in ("approve", "shrink") else 0.0,
            risk_frac=0.005 if kind_s == "shrink" else (0.01 if kind_s == "approve" else 0.0),
            p_cal=p_cal,
            p_adj=p_cal * 0.9,
            p_be=1 / 3,
            anomaly=0.8 if reason == "input_anomaly" else rng.random() * 0.4,
            anomaly_breakdown=AnomalyBreakdown(
                score=0.8 if reason == "input_anomaly" else 0.2,
                hard_triggers=["S1"] if reason == "input_anomaly" else [],
                soft={"S2": 0.3, "M1": 0.2},
            ),
            gate_config="G2",
        )
        did = rec.insert_decision(pid, decision)

        # shadow always on take
        if prop.action == Action.TAKE:
            sid = rec.insert_shadow(pid, entry, sl, tp, 0.01, symbol, side.value)
            # random shadow outcome
            win = rng.random() > 0.55
            r = 2.0 if win else -1.0
            equity_s *= 1 + 0.01 * r
            rec.insert_outcome("shadow", sid, "win" if win else "loss", r, rng.randint(3, 40))

        if kind_s in ("approve", "shrink"):
            oid = rec.insert_order(did, f"demo-{i}", entry, 0.1, symbol, side.value, decision.size)
            win = rng.random() > 0.45
            r = 1.5 if win else -1.0
            equity_g *= 1 + decision.risk_frac * r
            peak_g = max(peak_g, equity_g)
            rec.insert_outcome("real", oid, "win" if win else "loss", r, rng.randint(3, 40))

        rec.insert_equity("guarded", equity_g, ts)
        rec.insert_equity("shadow", equity_s, ts)

    # Attack lab demo JSON
    demo = []
    for sc in ("sc-001", "sc-002", "sc-003"):
        for attack in ("clean", "A1", "A4"):
            for gate, approved, reason, checks in [
                ("G0", True, "unguarded_fixed_risk", []),
                ("G1", attack != "A1", "no_calibrated_edge" if attack == "A1" else "calibrated_edge", []),
                (
                    "G2",
                    attack == "clean",
                    "input_anomaly" if attack != "clean" else "calibrated_edge",
                    ["S1", "M1"] if attack != "clean" else [],
                ),
            ]:
                demo.append(
                    {
                        "scenario_id": sc,
                        "attack": attack,
                        "gate_config": gate,
                        "approved": approved,
                        "reason": reason,
                        "confidence": 74 if attack == "A4" else (92 if attack == "A1" else 68),
                        "anomaly": 0.85 if attack != "clean" and gate == "G2" else 0.1,
                        "checks_fired": checks,
                        "true_result": "loss" if attack != "clean" else "win",
                    }
                )
    # Hand-written rows stay out of docs/ and web/public/: those belong to
    # run_attacks.py so the dashboard never shows seeded checks as measured.
    out = ROOT / "data" / "demo_attack_rows.json"
    out.write_text(json.dumps(demo, indent=2), encoding="utf-8")
    print(f"Seeded {db} (DEMO ONLY, dashboard: TARE_DB=data/demo.db)")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
