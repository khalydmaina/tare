"""Regression tests for the review fixes: ablation, paired ASR, blinding, harness."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attacks.harness import HarnessMetrics  # noqa: E402
from backtest.blind import blind_bundle  # noqa: E402
from core.config import load_limits, load_settings  # noqa: E402
from core.schemas import Action, GateContext, Proposal, Setup, Side  # noqa: E402
from inspector.behavior import BehaviorState  # noqa: E402
from inspector.calibration import CalibrationMatrix  # noqa: E402
from inspector.gate import decide  # noqa: E402
from tests.test_inspector import _account  # noqa: E402


def _cal() -> CalibrationMatrix:
    cal = CalibrationMatrix.from_settings(load_settings())
    for conf, w, l in ((65, 12, 18), (74, 24, 6)):
        for _ in range(w):
            cal.update(conf, "mid", True)
        for _ in range(l):
            cal.update(conf, "mid", False)
    return cal


def _prop(conf: int) -> Proposal:
    return Proposal(action=Action.TAKE, side=Side.LONG, entry=100, sl=99, tp=102,
                    confidence=conf, rationale="t", rr=2.0)


def _ctx(**kw) -> GateContext:
    return GateContext(account=_account(), regime="mid", **kw)


def test_ablation_skip_vetoes_sentiment_driven_take():
    d = decide(_prop(74), _ctx(ablation_confidence=55, ablation_action="skip"),
               load_settings(), load_limits(), _cal(), gate_config="G2")
    assert d.kind.value == "veto" and d.reason == "sentiment_driven_take"


def test_ablation_uses_lower_confidence():
    s, l, cal = load_settings(), load_limits(), _cal()
    steered = decide(_prop(74), _ctx(), s, l, cal, gate_config="G2A")
    ablated = decide(_prop(74), _ctx(ablation_confidence=65, ablation_action="take"),
                     s, l, cal, gate_config="G2")
    assert steered.kind.value in ("approve", "shrink")
    assert ablated.kind.value == "veto"  # 60-69 bucket has no edge at rr=2


def test_ablation_never_raises_confidence():
    s, l, cal = load_settings(), load_limits(), _cal()
    d = decide(_prop(65), _ctx(ablation_confidence=80, ablation_action="take"),
               s, l, cal, gate_config="G2")
    assert d.p_cal == cal.lookup(65, "mid")


def test_g2a_ignores_ablation():
    s, l, cal = load_settings(), load_limits(), _cal()
    d = decide(_prop(74), _ctx(ablation_confidence=50, ablation_action="skip"),
               s, l, cal, gate_config="G2A")
    assert d.reason != "sentiment_driven_take"


def test_paired_asr_never_negative():
    m = HarnessMetrics()
    for sid, clean_ok, atk_ok in (("a", True, False), ("b", False, True), ("c", False, False)):
        base = {"gate_config": "G2", "scenario_id": sid, "true_result": "loss",
                "risk_frac": 0.01, "r_multiple": -1.0}
        m.add({**base, "attack": "clean", "approved": clean_ok})
        m.add({**base, "attack": "A4", "approved": atk_ok})
    row = next(r for r in m.summary_table() if r["attack"] == "A4")
    assert row["G2_ASR"] == 0.5  # of b, c (blocked clean), only b got through
    assert row["G2_HAR"] >= 0


def test_blind_bundle_shares_scale_and_restores():
    setup = Setup(symbol="BTCUSDT", side=Side.LONG, entry=50_000, sl=49_500, tp=51_000,
                  rr=2.0, structure_summary="x", setup_score=0.6)
    b_setup, _, scale = blind_bundle(setup, {})
    assert abs(b_setup.entry - 100) < 1e-9 and b_setup.symbol == "INDEX"
    assert abs(b_setup.sl / scale - 49_500) < 1e-6


def test_behavior_state_roundtrip(tmp_path):
    st = BehaviorState()
    st.record_proposal(0.6, 70)
    st.record_sentiment(0.2)
    st.save(tmp_path / "b.json")
    st2 = BehaviorState.load(tmp_path / "b.json")
    assert st2.trailing() == [(0.6, 70)] and st2.sentiment_history() == [0.2]
