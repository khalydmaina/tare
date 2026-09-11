"""SQLite flight recorder."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    limits_hash TEXT,
    prompt_version TEXT,
    regime TEXT
);

CREATE TABLE IF NOT EXISTS setups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER REFERENCES cycles(id),
    side TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    rr REAL,
    setup_score REAL,
    structure_summary TEXT
);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setup_id INTEGER REFERENCES setups(id),
    action TEXT,
    confidence INTEGER,
    rationale TEXT,
    raw_json TEXT,
    latency_ms REAL,
    attack_id TEXT,
    side TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    prompt_version TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER REFERENCES proposals(id),
    kind TEXT,
    reason TEXT,
    p_cal REAL,
    p_adj REAL,
    p_be REAL,
    anomaly REAL,
    anomaly_breakdown_json TEXT,
    risk_frac REAL,
    size REAL,
    gate_config TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER REFERENCES decisions(id),
    exchange_order_id TEXT,
    fill_price REAL,
    fees REAL,
    symbol TEXT,
    side TEXT,
    size REAL
);

CREATE TABLE IF NOT EXISTS shadow_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER REFERENCES proposals(id),
    entry REAL,
    sl REAL,
    tp REAL,
    size REAL,
    symbol TEXT,
    side TEXT
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_type TEXT,
    ref_id INTEGER,
    result TEXT,
    r_multiple REAL,
    bars_held INTEGER,
    exit_price REAL
);

CREATE TABLE IF NOT EXISTS equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    book TEXT NOT NULL,
    equity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS calibration_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cell TEXT NOT NULL,
    n INTEGER,
    wins INTEGER,
    wilson_lower REAL
);

CREATE TABLE IF NOT EXISTS attack_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attack TEXT,
    gate_config TEXT,
    scenario_id TEXT,
    approved INTEGER,
    true_result TEXT,
    confidence INTEGER,
    reason TEXT,
    metrics_json TEXT
);

CREATE TABLE IF NOT EXISTS bot_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT,
    updated_at TEXT,
    note TEXT
);
"""


def _iso(ts: Optional[datetime] = None) -> str:
    t = ts or datetime.now(timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.isoformat()


class FlightRecorder:
    def __init__(self, db_path: str | Path = "data/tare.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO bot_status (id, status, updated_at, note) VALUES (1, 'stopped', ?, '')",
                (_iso(),),
            )

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = self._connect()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def set_status(self, status: str, note: str = "") -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE bot_status SET status=?, updated_at=?, note=? WHERE id=1",
                (status, _iso(), note),
            )

    def get_status(self) -> dict[str, Any]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM bot_status WHERE id=1").fetchone()
            return dict(row) if row else {"status": "unknown"}

    def insert_cycle(
        self,
        symbol: str,
        limits_hash: str,
        prompt_version: str,
        regime: str,
        ts: Optional[datetime] = None,
    ) -> int:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO cycles (ts, symbol, limits_hash, prompt_version, regime) VALUES (?,?,?,?,?)",
                (_iso(ts), symbol, limits_hash, prompt_version, regime),
            )
            return int(cur.lastrowid)

    def insert_setup(self, cycle_id: int, setup: Any) -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO setups
                   (cycle_id, side, entry, sl, tp, rr, setup_score, structure_summary)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    cycle_id,
                    setup.side.value if hasattr(setup.side, "value") else setup.side,
                    setup.entry,
                    setup.sl,
                    setup.tp,
                    setup.rr,
                    setup.setup_score,
                    setup.structure_summary,
                ),
            )
            return int(cur.lastrowid)

    def insert_proposal(self, setup_id: int, proposal: Any) -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO proposals
                   (setup_id, action, confidence, rationale, raw_json, latency_ms, attack_id,
                    side, entry, sl, tp, prompt_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    setup_id,
                    proposal.action.value if hasattr(proposal.action, "value") else proposal.action,
                    proposal.confidence,
                    proposal.rationale,
                    json.dumps(proposal.raw_json) if proposal.raw_json else None,
                    proposal.latency_ms,
                    proposal.attack_id,
                    proposal.side.value if hasattr(proposal.side, "value") else proposal.side,
                    proposal.entry,
                    proposal.sl,
                    proposal.tp,
                    proposal.prompt_version,
                ),
            )
            return int(cur.lastrowid)

    def insert_decision(self, proposal_id: int, decision: Any) -> int:
        breakdown = None
        if getattr(decision, "anomaly_breakdown", None) is not None:
            breakdown = decision.anomaly_breakdown.model_dump_json()
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO decisions
                   (proposal_id, kind, reason, p_cal, p_adj, p_be, anomaly,
                    anomaly_breakdown_json, risk_frac, size, gate_config)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    proposal_id,
                    decision.kind.value if hasattr(decision.kind, "value") else decision.kind,
                    decision.reason,
                    decision.p_cal,
                    decision.p_adj,
                    decision.p_be,
                    decision.anomaly,
                    breakdown,
                    decision.risk_frac,
                    decision.size,
                    decision.gate_config,
                ),
            )
            return int(cur.lastrowid)

    def insert_order(
        self,
        decision_id: int,
        exchange_order_id: str,
        fill_price: float,
        fees: float,
        symbol: str,
        side: str,
        size: float,
    ) -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO orders
                   (decision_id, exchange_order_id, fill_price, fees, symbol, side, size)
                   VALUES (?,?,?,?,?,?,?)""",
                (decision_id, exchange_order_id, fill_price, fees, symbol, side, size),
            )
            return int(cur.lastrowid)

    def insert_shadow(
        self,
        proposal_id: int,
        entry: float,
        sl: float,
        tp: float,
        size: float,
        symbol: str,
        side: str,
    ) -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO shadow_positions
                   (proposal_id, entry, sl, tp, size, symbol, side)
                   VALUES (?,?,?,?,?,?,?)""",
                (proposal_id, entry, sl, tp, size, symbol, side),
            )
            return int(cur.lastrowid)

    def insert_outcome(
        self,
        ref_type: str,
        ref_id: int,
        result: str,
        r_multiple: float,
        bars_held: int,
        exit_price: Optional[float] = None,
    ) -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO outcomes
                   (ref_type, ref_id, result, r_multiple, bars_held, exit_price)
                   VALUES (?,?,?,?,?,?)""",
                (ref_type, ref_id, result, r_multiple, bars_held, exit_price),
            )
            return int(cur.lastrowid)

    def insert_equity(self, book: str, equity: float, ts: Optional[datetime] = None) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT INTO equity (ts, book, equity) VALUES (?,?,?)",
                (_iso(ts), book, equity),
            )

    def insert_calibration_snapshot(self, cell: str, n: int, wins: int, wilson_lower: float) -> None:
        with self.conn() as c:
            c.execute(
                """INSERT INTO calibration_snapshots (ts, cell, n, wins, wilson_lower)
                   VALUES (?,?,?,?,?)""",
                (_iso(), cell, n, wins, wilson_lower),
            )

    def insert_attack_run(
        self,
        attack: str,
        gate_config: str,
        scenario_id: str,
        approved: bool,
        true_result: str,
        confidence: int,
        reason: str = "",
        metrics: Optional[dict] = None,
    ) -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO attack_runs
                   (attack, gate_config, scenario_id, approved, true_result, confidence, reason, metrics_json)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    attack,
                    gate_config,
                    scenario_id,
                    int(approved),
                    true_result,
                    confidence,
                    reason,
                    json.dumps(metrics or {}),
                ),
            )
            return int(cur.lastrowid)

    def fetch_recent_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT d.*, p.confidence, p.action, p.rationale, p.side, p.entry, p.sl, p.tp,
               s.symbol, c.ts AS cycle_ts
        FROM decisions d
        JOIN proposals p ON p.id = d.proposal_id
        JOIN setups s ON s.id = p.setup_id
        JOIN cycles c ON c.id = s.cycle_id
        ORDER BY d.id DESC LIMIT ?
        """
        with self.conn() as c:
            return [dict(r) for r in c.execute(q, (limit,)).fetchall()]

    def fetch_equity(self, book: Optional[str] = None) -> list[dict[str, Any]]:
        with self.conn() as c:
            if book:
                rows = c.execute(
                    "SELECT * FROM equity WHERE book=? ORDER BY ts", (book,)
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM equity ORDER BY ts").fetchall()
            return [dict(r) for r in rows]

    def fetch_calibration(self) -> list[dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute(
                """SELECT * FROM calibration_snapshots
                   WHERE id IN (SELECT MAX(id) FROM calibration_snapshots GROUP BY cell)"""
            ).fetchall()
            return [dict(r) for r in rows]

    def fetch_attack_runs(self) -> list[dict[str, Any]]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM attack_runs ORDER BY id").fetchall()]

    def fetch_outcomes(self, ref_type: Optional[str] = None) -> list[dict[str, Any]]:
        with self.conn() as c:
            if ref_type:
                rows = c.execute(
                    "SELECT * FROM outcomes WHERE ref_type=? ORDER BY id", (ref_type,)
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM outcomes ORDER BY id").fetchall()
            return [dict(r) for r in rows]
