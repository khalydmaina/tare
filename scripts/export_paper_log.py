#!/usr/bin/env python3
"""Write the paper trading log judges read: paper_log/*.csv plus paper_log/README.md.

Everything comes from the Flight Recorder the live bot writes (TARE_DB), so this log,
the dashboard and docs/RESULTS.md never disagree.

    python scripts/export_paper_log.py
"""

from __future__ import annotations

import csv
import math
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
               o.fees, o.exchange_order_id, p.confidence, d.reason AS decision, d.risk_frac,
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


def main() -> None:
    db = db_path()
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if not db.exists():
        (OUT / "README.md").write_text(f"# tare paper trading log\n\nNo live data yet ({now}).\n", encoding="utf-8")
        print(f"no database at {db}; wrote an empty log")
        return

    rec = FlightRecorder(db)
    with rec.conn() as c:
        for name, query in TABLES.items():
            cur = c.execute(query)
            with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([col[0] for col in cur.description])
                writer.writerows(cur.fetchall())
        count = lambda q: c.execute(q).fetchone()[0]  # noqa: E731
        counts = {
            "cycles": count("SELECT COUNT(*) FROM cycles"),
            "proposals": count("SELECT COUNT(*) FROM proposals"),
            "takes": count("SELECT COUNT(*) FROM proposals WHERE action = 'take'"),
            "vetoes": count("SELECT COUNT(*) FROM decisions WHERE kind = 'veto'"),
            "orders": count("SELECT COUNT(*) FROM orders"),
        }
        first_cycle = c.execute("SELECT MIN(ts) FROM cycles").fetchone()[0] or "-"
        models = [r[0] for r in c.execute("SELECT DISTINCT prompt_version FROM proposals")]

    status = rec.get_status()
    rows = []
    for label, book, ref_type in (
        ("Guarded (Inspector sizes or vetoes)", "guarded", "real"),
        ("Shadow (every take, no Inspector)", "shadow", "shadow"),
    ):
        m = metrics([e["equity"] for e in rec.fetch_equity(book)])
        outcomes = rec.fetch_outcomes(ref_type)
        wins = sum(1 for o in outcomes if o["result"] == "win")
        win_rate = f"{100 * wins / len(outcomes):.0f}%" if outcomes else "-"
        rows.append(f"| {label} | {100 * m['ret']:+.2f}% | {100 * m['mdd']:.2f}% | "
                    f"{m['sharpe']:.2f} | {len(outcomes)} | {win_rate} |")

    lines = [
        "# tare paper trading log",
        "",
        f"Generated {now} by `scripts/export_paper_log.py` from the live bot's Flight Recorder.",
        "",
        f"- Bot status: `{status.get('status')}` · {status.get('note') or '-'}",
        f"- Running since: {first_cycle}",
        f"- Prompt versions: {', '.join(m for m in models if m) or '-'}",
        "",
        "| Book | Return | Max drawdown | Sharpe (annualised, 15m marks) | Closed trades | Win rate |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        f"Cycles {counts['cycles']} · AI proposals {counts['proposals']} · takes {counts['takes']} · "
        f"vetoes {counts['vetoes']} · orders {counts['orders']}",
        "",
        "Files: `decisions.csv` (every AI proposal and the Inspector's verdict), `trades.csv` "
        "(guarded orders and outcomes), `shadow_trades.csv` (every take, unguarded), `equity.csv`.",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
