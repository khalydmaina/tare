"""Tests for deterministic SMC setup generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.schemas import Candle, Side
from trader.candidates import find_candidates
from trader.smc import (
    atr_series,
    candles_to_df,
    find_swings,
    generate_setups,
    merge_smc_cfg,
)


def _ts(i: int, minutes: int = 15) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes * i)


def make_candle(
    i: int,
    o: float,
    h: float,
    l: float,
    c: float,
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    minutes: int = 15,
    volume: float = 100.0,
) -> Candle:
    open_time = _ts(i, minutes)
    close_time = open_time + timedelta(minutes=minutes)
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=volume,
        source="test",
    )


def _ohlc(o: float, h: float, l: float, c: float) -> tuple[float, float, float, float]:
    assert l <= min(o, c) <= max(o, c) <= h
    return o, h, l, c


def build_long_sweep_displacement_15m() -> list[Candle]:
    """
    Hand-built long pattern:
    - quiet range to seed ATR
    - fractal swing low
    - liquidity sweep of that low
    - bearish OB then bullish displacement with FVG
    - pullback open inside OB/FVG zone
    """
    candles: list[Candle] = []
    # 0..24: mild oscillation around 100, range ~1
    for i in range(25):
        base = 100.0 + (0.2 if i % 2 == 0 else -0.2)
        o, c = base, base + 0.15
        candles.append(make_candle(i, *_ohlc(o, max(o, c) + 0.3, min(o, c) - 0.3, c)))

    # 25..: swing low, sweep, OB, displacement+FVG, pullback into zone
    seq = [
        (101.0, 101.5, 100.6, 101.2),  # 25
        (101.2, 101.6, 100.9, 101.4),  # 26
        (101.4, 101.7, 101.0, 101.3),  # 27
        (101.3, 101.4, 99.0, 99.4),  # 28 swing low
        (99.4, 100.2, 99.2, 100.0),  # 29
        (100.0, 100.8, 99.7, 100.5),  # 30
        (100.5, 101.0, 100.2, 100.8),  # 31
        (100.8, 101.1, 100.4, 100.6),  # 32
        (100.6, 100.9, 100.3, 100.5),  # 33
        (100.5, 100.6, 98.5, 99.5),  # 34 sweep
        (99.5, 99.6, 98.9, 99.0),  # 35 bearish OB
        (99.0, 99.2, 98.85, 99.1),  # 36
        # 37 displacement: gap FVG vs high[35]=99.6 (low 99.8 > 99.6), large body
        (99.9, 105.0, 99.8, 104.5),
        (104.5, 105.5, 104.0, 105.0),  # 38
        (105.0, 105.8, 104.6, 105.2),  # 39
        (99.4, 100.5, 99.2, 100.0),  # 40 re-enter zone open 99.4
    ]
    for j, (o, h, l, c) in enumerate(seq):
        candles.append(make_candle(25 + j, *_ohlc(o, h, l, c)))
    return candles


def build_htf_bullish(n: int, minutes: int, timeframe: str) -> list[Candle]:
    """Uptrend with rising late volatility so ATR% is not in the dead tail."""
    candles: list[Candle] = []
    price = 90.0
    for i in range(n):
        # Quiet early, livelier late → latest ATR% above 10th percentile
        vol = 0.25 + (0.08 if i < n // 2 else 0.55 + (i % 5) * 0.12)
        o = price
        c = price + 0.35 + (0.05 if i % 3 == 0 else 0.0)
        h = max(o, c) + vol
        l = min(o, c) - vol * 0.5
        if i == 10:
            l = o - 2.0
            c = o - 0.5
            h = o + 0.2
        if i == 20:
            c = o + 2.5
            h = c + 0.3
            l = o - 0.2
        candles.append(
            make_candle(
                i,
                *_ohlc(o, h, l, c),
                timeframe=timeframe,
                minutes=minutes,
            )
        )
        price = c
    return candles


@pytest.fixture
def smc_cfg() -> dict:
    return merge_smc_cfg(
        {
            "swing_lookback": 3,
            "displacement_atr_mult": 1.5,
            "sl_atr_buffer": 0.1,
            "min_rr": 1.5,
            "sl_atr_min": 0.5,
            "sl_atr_max": 3.0,
            "dead_market_atr_percentile": 10,
        }
    )


def test_fractal_swings_detect_hand_built_low():
    candles = build_long_sweep_displacement_15m()
    df = candles_to_df(candles)
    swings = find_swings(df, lookback=3)
    lows = [s for s in swings if s.kind == "low"]
    assert lows, "expected at least one swing low"
    # Index 28 should be a swing low at 99.0
    assert any(s.index == 28 and abs(s.price - 99.0) < 1e-9 for s in lows)


def test_long_sweep_displacement_generates_setup(smc_cfg):
    c15 = build_long_sweep_displacement_15m()
    c1h = build_htf_bullish(60, minutes=60, timeframe="1h")
    c4h = build_htf_bullish(60, minutes=240, timeframe="4h")

    setups = generate_setups(c15, c1h, c4h, "BTCUSDT", smc_cfg)
    assert setups, "expected at least one long SMC setup from fixture"
    long_setups = [s for s in setups if s.side == Side.LONG]
    assert long_setups, "expected a long setup"
    s = long_setups[0]
    assert s.sl < s.entry < s.tp
    assert s.rr >= smc_cfg["min_rr"] - 1e-9
    assert 0.0 <= s.setup_score <= 1.0
    assert "sweep" in s.structure_summary


def test_find_candidates_wrapper(smc_cfg):
    c15 = build_long_sweep_displacement_15m()
    c1h = build_htf_bullish(60, minutes=60, timeframe="1h")
    c4h = build_htf_bullish(60, minutes=240, timeframe="4h")
    a = generate_setups(c15, c1h, c4h, "ETHUSDT", smc_cfg)
    b = find_candidates(c15, c1h, c4h, "ETHUSDT", smc_cfg)
    assert len(a) == len(b)
    if a:
        assert a[0].entry == b[0].entry


def test_sl_always_correct_side_property(smc_cfg):
    """Property: every generated setup has SL on the protective side of entry."""
    c15 = build_long_sweep_displacement_15m()
    # Also mutate into a short-leaning mirror series
    short_rows = []
    for c in c15:
        # Reflect about 100
        o = 200 - c.close
        h = 200 - c.low
        l = 200 - c.high
        cl = 200 - c.open
        short_rows.append(
            make_candle(
                int((c.open_time - _ts(0)).total_seconds() // 900),
                *_ohlc(o, h, l, cl),
            )
        )

    c1h = build_htf_bullish(60, minutes=60, timeframe="1h")
    c4h = build_htf_bullish(60, minutes=240, timeframe="4h")

    all_setups = []
    for series, symbol in ((c15, "BTCUSDT"), (short_rows, "BTCUSDT")):
        setups = generate_setups(series, c1h, c4h, symbol, smc_cfg)
        all_setups.extend(setups)
        for s in setups:
            if s.side == Side.LONG:
                assert s.sl < s.entry, f"long SL must be below entry: {s}"
                assert s.tp > s.entry
            else:
                assert s.sl > s.entry, f"short SL must be above entry: {s}"
                assert s.tp < s.entry
            assert s.rr >= 0
    assert all_setups, "property test needs at least one generated setup"


def test_atr_positive_on_fixture():
    df = candles_to_df(build_long_sweep_displacement_15m())
    atr = atr_series(df, 14)
    assert atr.iloc[-1] > 0
