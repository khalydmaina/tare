"""Volatility regime: 1h ATR% tercile over the trailing 30 days, per symbol.

One definition for the scenario bank and the live loop, so the calibration cell a
live proposal looks up is the same kind of cell the replay filled.
"""

from __future__ import annotations

from typing import Sequence

from core.schemas import Candle

ATR_PERIOD = 14
LOOKBACK_BARS = 24 * 30
MIN_HISTORY = 30


def atr_pct_series(c1h: Sequence[Candle], period: int = ATR_PERIOD) -> list[float]:
    """ATR(period) / close for every candle from index `period` on (oldest first)."""
    out: list[float] = []
    for i in range(period, len(c1h)):
        trs = [
            max(
                c1h[j].high - c1h[j].low,
                abs(c1h[j].high - c1h[j - 1].close),
                abs(c1h[j].low - c1h[j - 1].close),
            )
            for j in range(i - period + 1, i + 1)
        ]
        close = c1h[i].close
        out.append((sum(trs) / period) / close if close else 0.0)
    return out


def regime_from_history(
    history: Sequence[float], current: float, min_history: int = MIN_HISTORY
) -> str:
    """Tercile of `current` within `history`; 'mid' until there is enough history."""
    if len(history) < min_history:
        return "mid"
    ordered = sorted(history)
    lo, hi = ordered[len(ordered) // 3], ordered[2 * len(ordered) // 3]
    if current <= lo:
        return "low"
    if current >= hi:
        return "high"
    return "mid"


def regime_for(c1h: Sequence[Candle], lookback_bars: int = LOOKBACK_BARS) -> str:
    """Regime of the newest 1h candle against the trailing `lookback_bars` of the same symbol."""
    series = atr_pct_series(c1h)
    if not series:
        return "mid"
    return regime_from_history(series[-lookback_bars:], series[-1])
