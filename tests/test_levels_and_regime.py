"""Trader levels are fixed to the setup; cache key, prompt, regime, closed-bar and DB-path helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from core.clock import closed_candles
from core.config import ROOT, db_path, load_settings
from core.schemas import Candle, Setup, Side
from inspector.regime import regime_for, regime_from_history
from trader.llm_trader import LLMTrader, enforce_proposal_bounds

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _hourly(n: int, price: float, spread: float, last_spread: float | None = None) -> list[Candle]:
    out = []
    for i in range(n):
        s = last_spread if last_spread is not None and i >= n - 14 else spread
        ot = T0 + timedelta(hours=i)
        out.append(Candle(symbol="X", timeframe="1h", open_time=ot, close_time=ot + timedelta(hours=1),
                          open=price, high=price * (1 + s / 2), low=price * (1 - s / 2), close=price,
                          volume=1.0, source="test"))
    return out


def test_model_cannot_move_the_levels():
    setup = Setup(symbol="BTCUSDT", side=Side.LONG, entry=100.0, sl=99.0, tp=102.0, rr=2.0,
                  structure_summary="x", setup_score=0.6)
    norm = enforce_proposal_bounds(
        setup, {"action": "take", "side": "short", "sl": 99.8, "tp": 101.0, "confidence": 71}
    )
    assert (norm["side"], norm["entry"], norm["sl"], norm["tp"]) == (Side.LONG, 100.0, 99.0, 102.0)
    assert norm["rr"] == pytest.approx(2.0) and norm["confidence"] == 71


def test_prompt_file_follows_prompt_version():
    settings = load_settings()
    trader = LLMTrader(settings)
    assert trader.prompt_version == "trader_v2"
    assert "The levels are fixed" in trader.system_prompt
    broken = deepcopy(settings)
    broken["llm"]["prompt_version"] = "trader_missing"
    with pytest.raises(FileNotFoundError):
        LLMTrader(broken)


def test_llm_cache_key_changes_with_prompt_and_model():
    from scripts.run_attacks import cache_key

    trader = LLMTrader(load_settings())
    key = cache_key(trader, "payload")
    assert key == cache_key(trader, "payload")
    assert key != cache_key(trader, "payload with one different candle")
    trader.prompt_version = "trader_v3"
    assert cache_key(trader, "payload") != key
    trader.prompt_version, trader.model = "trader_v2", "another-model"
    assert cache_key(trader, "payload") != key


def test_closed_candles_drops_the_forming_bar():
    bars = _hourly(3, 100.0, 0.01)
    assert closed_candles(bars, bars[-1].open_time + timedelta(minutes=1)) == bars[:-1]


def test_regime_is_judged_against_the_symbols_own_history():
    # A calm high-priced coin and a volatile cheap one each sit in their own normal regime
    assert regime_for(_hourly(760, 100_000.0, 0.002)) == "low"
    assert regime_for(_hourly(760, 150.0, 0.02)) == "low"
    # A volatility spike moves a symbol to "high"
    assert regime_for(_hourly(760, 150.0, 0.02, last_spread=0.06)) == "high"
    assert regime_from_history([0.01] * 10, 0.05) == "mid"  # not enough history yet


def test_db_path_prefers_env_and_anchors_relative_paths(monkeypatch, tmp_path):
    monkeypatch.delenv("TARE_DB", raising=False)
    assert db_path({"recorder": {"db_path": "data/x.db"}}) == ROOT / "data" / "x.db"
    monkeypatch.setenv("TARE_DB", str(tmp_path / "y.db"))
    assert db_path({"recorder": {"db_path": "data/x.db"}}) == tmp_path / "y.db"
