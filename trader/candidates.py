"""Thin wrapper that turns market candles into SMC Setup candidates."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from core.schemas import Candle, Setup
from trader.smc import generate_setups


def find_candidates(
    candles_15m: Sequence[Candle],
    candles_1h: Sequence[Candle],
    candles_4h: Sequence[Candle],
    symbol: str,
    cfg: Optional[dict[str, Any]] = None,
) -> list[Setup]:
    """Delegate to the deterministic SMC generator."""
    return generate_setups(candles_15m, candles_1h, candles_4h, symbol, cfg)
