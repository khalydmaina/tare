"""Contamination control: rebase prices, strip symbol/dates/sentiment."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from core.schemas import Candle


def blind_candles(candles: list[Candle], index_base: float = 100.0) -> list[Candle]:
    """Rebase so first close = index_base; anonymize symbol and timestamps."""
    if not candles:
        return []
    first = candles[0].close
    if first == 0:
        raise ValueError("cannot blind candles with zero first close")
    scale = index_base / first
    out: list[Candle] = []
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    for i, c in enumerate(candles):
        bc = copy.deepcopy(c)
        bc.symbol = "INDEX"
        bc.source = "blind"
        # Keep spacing via synthetic sequential times using original deltas approx
        from datetime import timedelta

        minutes = 15
        if c.timeframe.endswith("h"):
            try:
                minutes = int(c.timeframe[:-1]) * 60
            except ValueError:
                minutes = 60
        elif c.timeframe.endswith("m"):
            try:
                minutes = int(c.timeframe[:-1])
            except ValueError:
                minutes = 15
        bc.open_time = epoch + timedelta(minutes=minutes * i)
        bc.close_time = bc.open_time + timedelta(minutes=minutes)
        bc.open *= scale
        bc.high *= scale
        bc.low *= scale
        bc.close *= scale
        # volume left as-is (relative)
        out.append(bc)
    return out


def is_post_cutoff(ts: datetime, cutoff: datetime) -> bool:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return ts >= cutoff


def blind_bundle(setup, candles_by_tf: dict[str, list[Candle]]):
    """Blind a setup and all its timeframes with ONE shared scale and clock.

    blind_candles() rebases each series on its own first close, which leaves the
    setup's entry/SL/TP in raw prices and misaligns timeframes. For the Trader
    prompt we need everything on the same axis: price scaled so entry = 100,
    times shifted so the decision bar closes at 2000-01-01T00:00Z.
    """
    from datetime import timedelta

    scale = 100.0 / setup.entry if setup.entry else 1.0
    c15 = candles_by_tf.get("15m") or next(iter(candles_by_tf.values()), [])
    t_ref = c15[-1].close_time if c15 else datetime(2000, 1, 1, tzinfo=timezone.utc)
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)

    def _c(c: Candle) -> Candle:
        bc = c.model_copy()
        bc.symbol, bc.source = "INDEX", "blind"
        bc.open_time = epoch + (c.open_time - t_ref)
        bc.close_time = epoch + (c.close_time - t_ref)
        bc.open, bc.high, bc.low, bc.close = (c.open * scale, c.high * scale,
                                              c.low * scale, c.close * scale)
        return bc

    s = setup.model_copy()
    s.symbol = "INDEX"
    for f in ("entry", "sl", "tp", "zone_low", "zone_high", "atr"):
        v = getattr(s, f, None)
        if isinstance(v, (int, float)):
            setattr(s, f, v * scale)
    return s, {tf: [_c(c) for c in cs] for tf, cs in candles_by_tf.items()}, scale
