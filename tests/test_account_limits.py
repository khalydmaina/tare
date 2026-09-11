"""Hard limits that depend on account state: daily reset, loss cooldown, leverage cap, restarts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.config import load_limits, load_settings
from core.schemas import DecisionKind, Side
from execution.bitget_broker import PaperModeAccount, Position, exchange_price, exchange_size
from execution.shadow_book import ShadowBook
from inspector import limits as limits_mod
from inspector.calibration import CalibrationMatrix
from inspector.gate import decide
from tests.test_inspector import _account, _ctx, _proposal

NOW = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)


def _position(order_id: str) -> Position:
    return Position(order_id=order_id, symbol="BTCUSDT", side=Side.LONG, size=1.0, entry=100.0,
                    sl=99.0, tp=102.0, fill_price=100.0, fees=0.04, opened_at=NOW,
                    meta={"db_id": 7})


def test_daily_loss_baseline_resets_at_utc_midnight():
    acct = PaperModeAccount(10_000.0)
    acct.day = "2026-09-11"
    acct.equity = 9_500.0
    acct.roll_day(datetime(2026, 9, 11, 23, 59, tzinfo=timezone.utc))
    assert acct.day_start_equity == 10_000.0
    acct.roll_day(datetime(2026, 9, 12, 0, 1, tzinfo=timezone.utc))
    assert acct.day_start_equity == 9_500.0


def test_three_losses_in_a_row_start_the_cooldown():
    acct = PaperModeAccount(10_000.0)
    acct.loss_cooldown = (3, 4.0)
    for i in range(3):
        pos = _position(f"o{i}")
        acct.register_open(pos)
        acct.register_close(pos, pnl=-1.0, exit_fees=0.04, now=NOW)
    assert acct.cooldown_until == NOW + timedelta(hours=4)

    state, limits = acct.to_account_state(), load_limits()
    blocked = limits_mod.pre_trade(_proposal(), state, limits, symbol="BTCUSDT",
                                   now=NOW + timedelta(hours=1))
    assert blocked == "consecutive_loss_cooldown"
    assert limits_mod.pre_trade(_proposal(), state, limits, symbol="BTCUSDT",
                                now=NOW + timedelta(hours=5)) is None


@pytest.fixture
def edge_calibration() -> CalibrationMatrix:
    cal = CalibrationMatrix(min_n=20, prior_p=0.35)
    for i in range(35):
        cal.update(70, "mid", won=i < 30)
    return cal


def test_leverage_cap_shrinks_then_vetoes(edge_calibration):
    settings, limits = load_settings(), load_limits()
    # Uncapped this is 1% risk: 100 units x $100 = $10k notional against a $30k (3x) cap
    roomy = decide(_proposal(confidence=70, rr=3.0), _ctx(account=_account(open_notional=25_000.0)),
                   settings, limits, edge_calibration, gate_config="G1")
    assert roomy.kind == DecisionKind.SHRINK and roomy.size == pytest.approx(50.0)

    full = decide(_proposal(confidence=70, rr=3.0), _ctx(account=_account(open_notional=29_900.0)),
                  settings, limits, edge_calibration, gate_config="G1")
    assert full.kind == DecisionKind.VETO and full.reason == "max_leverage"


def test_account_and_shadow_state_roundtrip():
    acct = PaperModeAccount(10_000.0)
    acct.register_open(_position("keep"))
    acct.cooldown_until = NOW
    acct.consecutive_losses = 2
    restored = PaperModeAccount.from_dict(acct.to_dict())
    assert list(restored.positions) == ["keep"]
    assert restored.positions["keep"].meta == {"db_id": 7}
    assert restored.cooldown_until == NOW and restored.consecutive_losses == 2
    assert restored.equity == pytest.approx(acct.equity)

    book = ShadowBook(starting_equity=10_000.0)
    spos = book.open_position("BTCUSDT", Side.SHORT, 100.0, 101.0, 98.0, last_price=100.0)
    spos.meta["confidence"] = 74
    again = ShadowBook.from_dict(book.to_dict())
    assert again.equity == pytest.approx(book.equity)
    assert again.open_positions[spos.id].side == Side.SHORT
    assert again.open_positions[spos.id].meta == spos.meta
    assert again.open_positions[spos.id].meta["confidence"] == 74


def test_exchange_precision_rounds_size_down():
    assert exchange_size(0.12389, {"volume_place": 3, "size_multiplier": 0.001}) == pytest.approx(0.123)
    assert exchange_size(12.39, {"volume_place": 1}) == pytest.approx(12.3)
    assert exchange_size(5.9, {"volume_place": 0, "size_multiplier": 1}) == pytest.approx(5.0)
    assert exchange_price(123.45678, {"price_place": 2}) == "123.46"
