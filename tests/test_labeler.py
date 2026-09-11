"""Labeler fixtures: TP first, SL first, both-in-candle, timeout."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.schemas import Candle, OutcomeResult, Side
from execution.labeler import resolve


def _candle(
    o: float,
    h: float,
    l: float,
    c: float,
    *,
    i: int = 0,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
) -> Candle:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * i)
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=base,
        close_time=base + timedelta(minutes=5),
        open=o,
        high=h,
        low=l,
        close=c,
        volume=1.0,
        source="test",
    )


def test_tp_hits_first_long():
    entry, sl, tp = 100.0, 95.0, 110.0
    candles = [
        _candle(100, 102, 99, 101, i=0),
        _candle(101, 111, 100, 110, i=1),  # TP touched, SL not
    ]
    out = resolve(entry, sl, tp, Side.LONG, candles, timeout_bars=48)
    assert out.result == OutcomeResult.WIN
    assert out.bars_held == 2
    assert out.exit_price == tp
    assert out.r_multiple == pytest.approx(2.0)


def test_sl_hits_first_long():
    entry, sl, tp = 100.0, 95.0, 110.0
    candles = [
        _candle(100, 101, 94, 96, i=0),  # SL first
    ]
    out = resolve(entry, sl, tp, "long", candles, timeout_bars=48)
    assert out.result == OutcomeResult.LOSS
    assert out.bars_held == 1
    assert out.exit_price == sl
    assert out.r_multiple == pytest.approx(-1.0)


def test_both_in_same_candle_is_loss():
    entry, sl, tp = 100.0, 95.0, 110.0
    candles = [
        _candle(100, 112, 94, 105, i=0),  # both TP and SL in range
    ]
    out = resolve(entry, sl, tp, Side.LONG, candles, timeout_bars=48)
    assert out.result == OutcomeResult.LOSS
    assert out.bars_held == 1
    assert out.exit_price == sl
    assert out.r_multiple == pytest.approx(-1.0)


def test_timeout_after_48_bars_is_timeout_loss():
    entry, sl, tp = 100.0, 95.0, 110.0
    candles = [_candle(100, 101, 99, 100.5, i=i) for i in range(48)]
    out = resolve(entry, sl, tp, Side.LONG, candles, timeout_bars=48)
    assert out.result == OutcomeResult.TIMEOUT
    assert out.bars_held == 48
    assert out.exit_price == candles[47].close
    # small positive mark-to-close
    assert out.r_multiple == pytest.approx((100.5 - 100.0) / 5.0)


def test_open_when_insufficient_bars():
    entry, sl, tp = 100.0, 95.0, 110.0
    candles = [_candle(100, 101, 99, 100, i=i) for i in range(10)]
    out = resolve(entry, sl, tp, Side.LONG, candles, timeout_bars=48)
    assert out.result == OutcomeResult.OPEN
    assert out.bars_held == 10
    assert out.exit_price is None


def test_tp_hits_first_short():
    entry, sl, tp = 100.0, 105.0, 90.0
    candles = [
        _candle(100, 101, 99, 99.5, i=0),
        _candle(99.5, 100, 89, 91, i=1),
    ]
    out = resolve(entry, sl, tp, Side.SHORT, candles, timeout_bars=48)
    assert out.result == OutcomeResult.WIN
    assert out.bars_held == 2
    assert out.r_multiple == pytest.approx(2.0)


def test_sl_hits_first_short():
    entry, sl, tp = 100.0, 105.0, 90.0
    candles = [_candle(100, 106, 99, 104, i=0)]
    out = resolve(entry, sl, tp, Side.SHORT, candles, timeout_bars=48)
    assert out.result == OutcomeResult.LOSS
    assert out.bars_held == 1
    assert out.r_multiple == pytest.approx(-1.0)


def test_both_in_candle_short_is_loss():
    entry, sl, tp = 100.0, 105.0, 90.0
    candles = [_candle(100, 106, 89, 95, i=0)]
    out = resolve(entry, sl, tp, Side.SHORT, candles, timeout_bars=48)
    assert out.result == OutcomeResult.LOSS
    assert out.exit_price == sl
