"""Resolve trade outcomes by walking forward on candles."""

from __future__ import annotations

from typing import Sequence, Union

from core.schemas import Candle, Outcome, OutcomeResult, Side

SideLike = Union[Side, str]


def _as_side(side: SideLike) -> Side:
    if isinstance(side, Side):
        return side
    return Side(str(side).lower())


def resolve(
    entry: float,
    sl: float,
    tp: float,
    side: SideLike,
    candles: Sequence[Candle],
    timeout_bars: int = 48,
) -> Outcome:
    """Walk candles forward from entry until TP, SL, or timeout.

    Rules (calibration):
    - TP hit before SL → win
    - SL hit before TP → loss
    - Both in the same candle → loss
    - No resolution after ``timeout_bars`` → timeout (treated as loss for calibration)
    - Fewer than ``timeout_bars`` with neither hit → still open
    """
    if timeout_bars < 1:
        raise ValueError("timeout_bars must be >= 1")
    risk = abs(entry - sl)
    if risk <= 0:
        raise ValueError("entry and sl must differ")

    side_e = _as_side(side)
    is_long = side_e == Side.LONG

    n = min(len(candles), timeout_bars)
    for i in range(n):
        c = candles[i]
        bars = i + 1
        if is_long:
            hit_sl = c.low <= sl
            hit_tp = c.high >= tp
        else:
            hit_sl = c.high >= sl
            hit_tp = c.low <= tp

        if hit_sl and hit_tp:
            return Outcome(
                result=OutcomeResult.LOSS,
                r_multiple=-1.0,
                bars_held=bars,
                exit_price=sl,
            )
        if hit_sl:
            return Outcome(
                result=OutcomeResult.LOSS,
                r_multiple=-1.0,
                bars_held=bars,
                exit_price=sl,
            )
        if hit_tp:
            r_mult = abs(tp - entry) / risk
            return Outcome(
                result=OutcomeResult.WIN,
                r_multiple=r_mult,
                bars_held=bars,
                exit_price=tp,
            )

    if len(candles) < timeout_bars:
        return Outcome(
            result=OutcomeResult.OPEN,
            r_multiple=0.0,
            bars_held=len(candles),
            exit_price=None,
        )

    last = candles[timeout_bars - 1]
    exit_price = last.close
    if is_long:
        r_mult = (exit_price - entry) / risk
    else:
        r_mult = (entry - exit_price) / risk
    return Outcome(
        result=OutcomeResult.TIMEOUT,
        r_multiple=r_mult,
        bars_held=timeout_bars,
        exit_price=exit_price,
    )
