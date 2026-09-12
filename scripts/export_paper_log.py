#!/usr/bin/env python3
"""Write the paper trading log judges read and the live feed the website reads.

paper_log/*.csv + paper_log/README.md for judges, paper_log/live.json for the Flight
Recorder. Everything comes from the Flight Recorder database the live bot writes
(TARE_DB), so the log, the website, the dashboard and docs/RESULTS.md never disagree.

    python scripts/export_paper_log.py
    TARE_DB=/tmp/tare.db python scripts/export_paper_log.py --out /tmp/log --state /tmp/live_state.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.config import db_path  # noqa: E402
from recorder.db import FlightRecorder  # noqa: E402

OUT = ROOT / "paper_log"
STATE = ROOT / "data" / "live_state.json"
MAX_EQUITY_POINTS = 400

TABLES = {
    "decisions.csv": """
        SELECT c.ts AS cycle_time, c.symbol, c.regime, p.side, p.action, p.confidence,
               d.kind AS decision, d.reason, d.gate_config, d.p_cal, d.p_adj, d.p_be,
               d.anomaly, d.risk_frac, d.size, p.entry, p.sl, p.tp, p.prompt_version, p.rationale
        FROM decisions d
        JOIN proposals p ON p.id = d.proposal_id
        JOIN setups s ON s.id = p.setup_id
        JOIN cycles c ON c.id = s.cycle_id
        ORDER BY d.id""",
    "trades.csv": """
        SELECT o.id AS order_id, c.ts AS opened_cycle, o.symbol, o.side, o.size, o.fill_price,
               o.fees, o.exchange_order_id,
               CASE WHEN o.exchange_order_id IS NULL OR o.exchange_order_id = ''
                    THEN 'simulated' ELSE 'exchange' END AS fill,
               p.confidence, d.reason AS decision, d.risk_frac,
               oc.result, oc.r_multiple, oc.bars_held, oc.exit_price
        FROM orders o
        JOIN decisions d ON d.id = o.decision_id
        JOIN proposals p ON p.id = d.proposal_id
        JOIN setups s ON s.id = p.setup_id
        JOIN cycles c ON c.id = s.cycle_id
        LEFT JOIN outcomes oc ON oc.ref_type = 'real' AND oc.ref_id = o.id
        ORDER BY o.id""",
    "shadow_trades.csv": """
        SELECT sp.id AS shadow_id, sp.symbol, sp.side, sp.entry, sp.sl, sp.tp, sp.size,
               p.confidence, oc.result, oc.r_multiple, oc.bars_held, oc.exit_price
        FROM shadow_positions sp
        JOIN proposals p ON p.id = sp.proposal_id
        LEFT JOIN outcomes oc ON oc.ref_type = 'shadow' AND oc.ref_id = sp.id
        ORDER BY sp.id""",
    "equity.csv": "SELECT ts, book, equity FROM equity ORDER BY id",
}

RECENT_DECISIONS = """
    SELECT d.id, c.ts, c.symbol, p.side, p.action, p.confidence, d.kind, d.reason,
           d.p_cal, d.p_adj, d.p_be, d.anomaly, d.anomaly_breakdown_json
    FROM decisions d
    JOIN proposals p ON p.id = d.proposal_id
    JOIN setups s ON s.id = p.setup_id
    JOIN cycles c ON c.id = s.cycle_id
    ORDER BY d.id DESC LIMIT 50"""

# The newest check of every coin: when, which volatility regime, how many setups it found
LAST_SCAN = """
    SELECT c.symbol, c.ts, c.regime, COUNT(s.id) AS setups
    FROM cycles c
    LEFT JOIN setups s ON s.cycle_id = c.id
    WHERE c.id IN (SELECT MAX(id) FROM cycles GROUP BY symbol)
    GROUP BY c.id
    ORDER BY c.id"""


def metrics(equity: list[float]) -> dict[str, float]:
    if len(equity) < 2:
        return {"ret": 0.0, "mdd": 0.0, "sharpe": 0.0}
    peak, mdd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak else 0.0)
    rets = [(b - a) / a for a, b in zip(equity, equity[1:]) if a]
    mean = sum(rets) / len(rets) if rets else 0.0
    sd = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5 if rets else 0.0
    # One equity mark per 15m cycle → 96 marks a day
    sharpe = mean / sd * math.sqrt(96 * 365) if sd else 0.0
    return {"ret": equity[-1] / equity[0] - 1, "mdd": mdd, "sharpe": sharpe}


def checks_fired(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        breakdown = json.loads(raw)
    except ValueError:
        return []
    fired = list(breakdown.get("hard_triggers") or [])
    fired += [k for k, v in (breakdown.get("soft") or {}).items() if v >= 0.5 and k not in fired]
    return fired


FILL_LABELS = {
    "bitget-demo-api": "Bitget demo account",
    "local-sim": "local simulated fills",
    "local-sim-after-reject": "local simulated fills (Bitget refused the order)",
}


def bot_info(note: str) -> dict[str, str]:
    """Split the status note run_live.py writes: 'gate=G2 llm=model fills | last cycle ...'."""
    config, _, health = note.partition(" | ")
    model = re.search(r"llm=(\S+)", config)
    gate = re.search(r"gate=(\S+)", config)
    fills = re.search(r"fills=(\S+)", config)
    return {
        "model": model.group(1) if model else ("simulated trader" if "SIMULATED" in config else ""),
        "gate": gate.group(1) if gate else "",
        "fills": FILL_LABELS.get(fills.group(1) if fills else "", "local simulated fills"),
        "health": health,
    }


def calibration_by_bucket(rec: FlightRecorder) -> tuple[list[dict], list[dict]]:
    """Latest snapshot per cell, pooled across regimes: overconfidence gap and reliability."""
    pooled: dict[str, list[int]] = {}
    for cell in rec.fetch_calibration():
        bucket = cell["cell"].split("|")[0]
        totals = pooled.setdefault(bucket, [0, 0])
        totals[0] += cell["n"] or 0
        totals[1] += cell["wins"] or 0
    gaps, reliability = [], []
    for bucket, (n, wins) in sorted(pooled.items(), key=lambda kv: int(kv[0].split("-")[0])):
        if not n:
            continue
        lo, hi = (int(x) for x in bucket.split("-"))
        mid, hit = (lo + hi) / 2, 100 * wins / n
        gaps.append({"bucket": bucket, "gap": round(mid - hit, 1), "n": n})
        reliability.append({"stated": mid, "actual": round(hit, 1), "n": n})
    return gaps, reliability


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the paper trading log and live.json")
    parser.add_argument("--out", type=Path, default=OUT, help="output directory (default: paper_log/)")
    parser.add_argument("--state", type=Path, default=STATE,
                        help="live loop state file, read for open positions (default: data/live_state.json)")
    args = parser.parse_args()
    out, state = args.out, args.state

    db = db_path()
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    if not db.exists():
        (out / "README.md").write_text(f"# tare paper trading log\n\nNo live data yet ({stamp}).\n", encoding="utf-8")
        print(f"no database at {db}; wrote an empty log")
        return

    rec = FlightRecorder(db)
    with rec.conn() as c:
        for name, query in TABLES.items():
            cur = c.execute(query)
            with (out / name).open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([col[0] for col in cur.description])
                writer.writerows(cur.fetchall())
        count = lambda q: c.execute(q).fetchone()[0]  # noqa: E731
        counts = {
            "cycles": count("SELECT COUNT(*) FROM cycles"),
            "setups": count("SELECT COUNT(*) FROM setups"),
            "proposals": count("SELECT COUNT(*) FROM proposals"),
            "takes": count("SELECT COUNT(*) FROM proposals WHERE action = 'take'"),
            "vetoes": count("SELECT COUNT(*) FROM decisions WHERE kind = 'veto'"),
            "orders": count("SELECT COUNT(*) FROM orders"),
        }
        first_cycle = c.execute("SELECT MIN(ts) FROM cycles").fetchone()[0]
        symbols = count("SELECT COUNT(DISTINCT symbol) FROM cycles")
        models = [r[0] for r in c.execute("SELECT DISTINCT prompt_version FROM proposals")]
        recent = [
            {
                "id": r["id"], "ts": r["ts"], "symbol": r["symbol"], "side": r["side"],
                "action": r["action"], "confidence": r["confidence"], "kind": r["kind"],
                "reason": r["reason"], "p_cal": r["p_cal"], "p_adj": r["p_adj"], "p_be": r["p_be"],
                "anomaly": r["anomaly"], "checks": checks_fired(r["anomaly_breakdown_json"]),
            }
            for r in c.execute(RECENT_DECISIONS).fetchall()
        ]
        scan = [
            {"symbol": r["symbol"], "ts": r["ts"], "regime": r["regime"], "setups": r["setups"]}
            for r in c.execute(LAST_SCAN).fetchall()
        ]

    status = rec.get_status()
    guarded, shadow = rec.fetch_equity("guarded"), rec.fetch_equity("shadow")
    books, rows = {}, []
    for label, book, ref_type, marks in (
        ("Guarded (Inspector sizes or vetoes)", "guarded", "real", guarded),
        ("Shadow (every take, no Inspector)", "shadow", "shadow", shadow),
    ):
        m = metrics([e["equity"] for e in marks])
        outcomes = rec.fetch_outcomes(ref_type)
        wins = sum(1 for o in outcomes if o["result"] == "win")
        books[book] = {**m, "closed": len(outcomes), "win_rate": wins / len(outcomes) if outcomes else None}
        win_rate = f"{100 * wins / len(outcomes):.0f}%" if outcomes else "-"
        rows.append(f"| {label} | {100 * m['ret']:+.2f}% | {100 * m['mdd']:.2f}% | "
                    f"{m['sharpe']:.2f} | {len(outcomes)} | {win_rate} |")

    lines = [
        "# tare paper trading log",
        "",
        f"Generated {stamp} by `scripts/export_paper_log.py` from the live bot's Flight Recorder.",
        "",
        f"- Bot status: `{status.get('status')}` · {status.get('note') or '-'}",
        f"- Running since: {first_cycle or '-'}",
        f"- Prompt versions: {', '.join(m for m in models if m) or '-'}",
        "",
        "| Book | Return | Max drawdown | Sharpe (annualised, 15m marks) | Closed trades | Win rate |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        f"Cycles {counts['cycles']} · setups {counts['setups']} · AI proposals {counts['proposals']} · "
        f"takes {counts['takes']} · vetoes {counts['vetoes']} · orders {counts['orders']}",
        "",
        "Files: `decisions.csv` (every AI proposal and the Inspector's verdict), `trades.csv` "
        "(guarded orders and outcomes), `shadow_trades.csv` (every take, unguarded), `equity.csv`.",
        "",
    ]
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- live.json for the website ----
    equity = [
        {"t": g["ts"], "guarded": round(g["equity"], 2), "shadow": round(s["equity"], 2)}
        for g, s in zip(guarded, shadow)
    ]
    if len(equity) > MAX_EQUITY_POINTS:
        step = len(equity) // MAX_EQUITY_POINTS + 1
        equity = equity[::step] + [equity[-1]]
    today = now.date().isoformat()
    day_start = next((g["equity"] for g in guarded if g["ts"][:10] == today), None)
    last_guarded = guarded[-1]["equity"] if guarded else 10_000.0
    open_positions = 0
    if state.exists():
        open_positions = len(json.loads(state.read_text(encoding="utf-8")).get("broker", {}).get("positions", []))
    gaps, reliability = calibration_by_bucket(rec)
    note = status.get("note") or ""
    live = {
        "generated_at": now.isoformat(),
        "status": {"status": status.get("status"), "note": note, "updated_at": status.get("updated_at")},
        "bot": bot_info(note),
        "running_since": first_cycle,
        "symbols": symbols,
        "metrics": {
            "equityGuarded": round(last_guarded, 2),
            "equityShadow": round(shadow[-1]["equity"], 2) if shadow else 10_000.0,
            "dayPnl": round(last_guarded - day_start, 2) if day_start is not None else 0.0,
            "openPositions": open_positions,
        },
        "books": books,
        "counts": counts,
        "scan": scan,
        "equity": equity,
        "decisions": recent,
        "buckets": gaps,
        "reliability": reliability,
    }
    (out / "live.json").write_text(json.dumps(live, default=str), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
