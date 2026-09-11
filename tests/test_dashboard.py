"""The Streamlit dashboard renders a recorder database without raising."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from core.schemas import Action, Decision, Proposal, Setup, Side  # noqa: E402
from recorder.db import FlightRecorder  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


def test_dashboard_renders_recorded_data(tmp_path, monkeypatch):
    db = tmp_path / "dash.db"
    rec = FlightRecorder(db)
    setup = Setup(symbol="BTCUSDT", side=Side.LONG, entry=100.0, sl=99.0, tp=102.0, rr=2.0,
                  structure_summary="sweep", setup_score=0.7)
    cycle_id = rec.insert_cycle("BTCUSDT", "hash", "trader_v2", "mid")
    setup_id = rec.insert_setup(cycle_id, setup)
    proposal_id = rec.insert_proposal(setup_id, Proposal(
        action=Action.TAKE, side=Side.LONG, entry=100.0, sl=99.0, tp=102.0, confidence=88, rr=2.0,
    ))
    rec.insert_decision(proposal_id, Decision.veto("no_calibrated_edge", p_adj=0.30, p_be=0.33, p_cal=0.30))
    rec.insert_equity("guarded", 10_000.0)
    rec.insert_equity("shadow", 9_950.0)
    rec.insert_calibration_snapshot("80-89|mid", 24, 11, 0.28)
    rec.set_status("running", "gate=G2 test")
    monkeypatch.setenv("TARE_DB", str(db))

    at = AppTest.from_file(str(APP), default_timeout=60).run()

    assert not at.exception, [e.value for e in at.exception]
    assert any("Decision log" in s.value for s in at.subheader)
