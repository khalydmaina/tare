"""The exporter turns the live bot's database into the log judges read and the website's live.json."""

import json
import os
import subprocess
import sys
from pathlib import Path

from recorder.db import FlightRecorder

ROOT = Path(__file__).resolve().parents[1]


def test_live_json_after_quiet_cycles(tmp_path):
    db = tmp_path / "tare.db"
    rec = FlightRecorder(db)
    for symbol, regime in (("BTCUSDT", "high"), ("ETHUSDT", "low"), ("BTCUSDT", "mid")):
        rec.insert_cycle(symbol, "hash", "trader_v2", regime)
    for book in ("guarded", "shadow"):
        rec.insert_equity(book, 10_000.0)
    rec.set_status(
        "running",
        "gate=G2 llm=openai/gpt-oss-120b local-sim-fills | "
        "last cycle 2026-09-11 19:25Z: 2/2 feeds ok, 0 setups, 0 orders",
    )

    out = tmp_path / "log"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_paper_log.py"),
         "--out", str(out), "--state", str(tmp_path / "no_state.json")],
        check=True, cwd=ROOT, env={**os.environ, "TARE_DB": str(db)},
    )

    live = json.loads((out / "live.json").read_text(encoding="utf-8"))
    assert live["status"]["status"] == "running"
    assert live["bot"] == {
        "model": "openai/gpt-oss-120b",
        "gate": "G2",
        "fills": "local simulated fills",
        "health": "last cycle 2026-09-11 19:25Z: 2/2 feeds ok, 0 setups, 0 orders",
    }
    assert live["counts"]["cycles"] == 3 and live["counts"]["setups"] == 0
    # Only the newest check of each coin, oldest first
    assert [(s["symbol"], s["regime"], s["setups"]) for s in live["scan"]] == [
        ("ETHUSDT", "low", 0),
        ("BTCUSDT", "mid", 0),
    ]
    assert live["decisions"] == [] and live["metrics"]["openPositions"] == 0
    for name in ("README.md", "decisions.csv", "trades.csv", "shadow_trades.csv", "equity.csv"):
        assert (out / name).exists()
