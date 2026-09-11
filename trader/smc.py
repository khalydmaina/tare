"""Deterministic Smart Money Concepts setup generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Optional, Sequence

import numpy as np
import pandas as pd

from core.schemas import Candle, Setup, Side

Bias = Literal["bullish", "bearish", "neutral"]


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: Literal["high", "low"]


@dataclass
class SweepEvent:
    index: int
    side: Side  # LONG = swept lows (buy-side liquidity), SHORT = swept highs
    extreme: float
    level: float


@dataclass
class DisplacementEvent:
    index: int
    side: Side
    fvg_low: float
    fvg_high: float
    ob_low: float
    ob_high: float


def _default_smc_cfg() -> dict[str, Any]:
    return {
        "swing_lookback": 3,
        "displacement_atr_mult": 1.5,
        "sl_atr_buffer": 0.1,
        "min_rr": 1.5,
        "sl_atr_min": 0.5,
        "sl_atr_max": 3.0,
        "dead_market_atr_percentile": 10,
    }


def merge_smc_cfg(cfg: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    out = _default_smc_cfg()
    if cfg:
        smc = cfg.get("smc", cfg) if "smc" in cfg else cfg
        for k, v in smc.items():
            if k in out:
                out[k] = v
    return out


def candles_to_df(candles: Sequence[Candle]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame(
            columns=["open_time", "open", "high", "low", "close", "volume"]
        )
    rows = [
        {
            "open_time": c.open_time,
            "open": float(c.open),
            "high": float(c.high),
            "low": float(c.low),
            "close": float(c.close),
            "volume": float(c.volume),
        }
        for c in candles
    ]
    df = pd.DataFrame(rows).sort_values("open_time").reset_index(drop=True)
    return df


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    ranges = np.vstack(
        [
            high - low,
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        ]
    )
    return np.max(ranges, axis=0)


def atr_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder-style ATR via ewm(alpha=1/period)."""
    if df.empty:
        return pd.Series(dtype=float)
    tr = true_range(
        df["high"].to_numpy(dtype=float),
        df["low"].to_numpy(dtype=float),
        df["close"].to_numpy(dtype=float),
    )
    s = pd.Series(tr, index=df.index)
    return s.ewm(alpha=1.0 / period, adjust=False).mean()


def atr_at(df: pd.DataFrame, index: int, period: int = 14) -> float:
    series = atr_series(df, period)
    if series.empty or index < 0 or index >= len(series):
        return 0.0
    val = float(series.iloc[index])
    return val if np.isfinite(val) else 0.0


def atr_pct_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    atr = atr_series(df, period)
    close = df["close"].replace(0, np.nan)
    return (atr / close) * 100.0


def find_swings(df: pd.DataFrame, lookback: int = 3) -> list[Swing]:
    """Fractal swings: extreme must exceed `lookback` bars on each side."""
    swings: list[Swing] = []
    n = len(df)
    if n < 2 * lookback + 1:
        return swings
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    for i in range(lookback, n - lookback):
        left_h = highs[i - lookback : i]
        right_h = highs[i + 1 : i + lookback + 1]
        if highs[i] > left_h.max() and highs[i] >= right_h.max():
            swings.append(Swing(index=i, price=float(highs[i]), kind="high"))
        left_l = lows[i - lookback : i]
        right_l = lows[i + 1 : i + lookback + 1]
        if lows[i] < left_l.min() and lows[i] <= right_l.min():
            swings.append(Swing(index=i, price=float(lows[i]), kind="low"))
    swings.sort(key=lambda s: s.index)
    return swings


def _swings_before(swings: Iterable[Swing], index: int, kind: str) -> list[Swing]:
    return [s for s in swings if s.kind == kind and s.index < index]


def last_bos(
    df: pd.DataFrame,
    swings: Sequence[Swing],
    *,
    confirm_close: bool = True,
) -> tuple[Optional[Literal["up", "down"]], Optional[int]]:
    """
    Walk chronologically; BOS up when price breaks prior confirmed swing high,
    BOS down when price breaks prior confirmed swing low.
    """
    if df.empty or not swings:
        return None, None
    last_dir: Optional[Literal["up", "down"]] = None
    last_idx: Optional[int] = None
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    # Only use swings that are fully confirmed (lookback bars after)
    confirmed = list(swings)
    for i in range(len(df)):
        prior_highs = _swings_before(confirmed, i, "high")
        prior_lows = _swings_before(confirmed, i, "low")
        if prior_highs:
            lvl = prior_highs[-1].price
            broke = closes[i] > lvl if confirm_close else highs[i] > lvl
            if broke:
                last_dir, last_idx = "up", i
        if prior_lows:
            lvl = prior_lows[-1].price
            broke = closes[i] < lvl if confirm_close else lows[i] < lvl
            if broke:
                last_dir, last_idx = "down", i
    return last_dir, last_idx


def structure_bias(df: pd.DataFrame, lookback: int = 3) -> Bias:
    """Bullish if last BOS is up and price above last swing low; bearish mirror."""
    if len(df) < 2 * lookback + 5:
        return "neutral"
    swings = find_swings(df, lookback)
    direction, _ = last_bos(df, swings)
    if direction is None:
        return "neutral"
    price = float(df["close"].iloc[-1])
    lows = _swings_before(swings, len(df), "low")
    highs = _swings_before(swings, len(df), "high")
    if direction == "up":
        if lows and price > lows[-1].price:
            return "bullish"
        return "neutral"
    if highs and price < highs[-1].price:
        return "bearish"
    return "neutral"


def combined_bias(bias_1h: Bias, bias_4h: Bias) -> Bias:
    if bias_1h == bias_4h and bias_1h != "neutral":
        return bias_1h
    if bias_4h != "neutral" and bias_1h == "neutral":
        return bias_4h
    if bias_1h != "neutral" and bias_4h == "neutral":
        return bias_1h
    if bias_1h != "neutral" and bias_4h != "neutral" and bias_1h != bias_4h:
        return "neutral"
    return "neutral"


def find_liquidity_sweeps(
    df: pd.DataFrame,
    swings: Sequence[Swing],
    lookback: int = 3,
) -> list[SweepEvent]:
    """
    Wick through a prior swing that closes back inside.
    LONG sweep = take-out of swing low (sell-side liquidity raid).
    SHORT sweep = take-out of swing high.
    """
    events: list[SweepEvent] = []
    n = len(df)
    start = 2 * lookback
    for i in range(start, n):
        row = df.iloc[i]
        h, l, c = float(row.high), float(row.low), float(row.close)
        prior_lows = _swings_before(swings, i, "low")
        prior_highs = _swings_before(swings, i, "high")
        if prior_lows:
            lvl = prior_lows[-1].price
            if l < lvl and c > lvl:
                events.append(
                    SweepEvent(index=i, side=Side.LONG, extreme=l, level=lvl)
                )
        if prior_highs:
            lvl = prior_highs[-1].price
            if h > lvl and c < lvl:
                events.append(
                    SweepEvent(index=i, side=Side.SHORT, extreme=h, level=lvl)
                )
    return events


def _body(row: pd.Series) -> float:
    return abs(float(row.close) - float(row.open))


def _is_bullish(row: pd.Series) -> bool:
    return float(row.close) > float(row.open)


def _is_bearish(row: pd.Series) -> bool:
    return float(row.close) < float(row.open)


def find_fvg(
    df: pd.DataFrame, index: int, side: Side
) -> Optional[tuple[float, float]]:
    """
    3-candle fair value gap ending at `index` (displacement / impulse candle).
    Bullish: low[i] > high[i-2]; Bearish: high[i] < low[i-2].
    """
    if index < 2 or index >= len(df):
        return None
    c0 = df.iloc[index - 2]
    c2 = df.iloc[index]
    if side == Side.LONG:
        if float(c2.low) > float(c0.high):
            return float(c0.high), float(c2.low)
    else:
        if float(c2.high) < float(c0.low):
            return float(c2.high), float(c0.low)
    return None


def find_order_block(
    df: pd.DataFrame, displacement_index: int, side: Side, search: int = 8
) -> Optional[tuple[float, float, int]]:
    """Last opposite-color candle before the displacement candle."""
    start = max(0, displacement_index - search)
    for j in range(displacement_index - 1, start - 1, -1):
        row = df.iloc[j]
        if side == Side.LONG and _is_bearish(row):
            return float(row.low), float(row.high), j
        if side == Side.SHORT and _is_bullish(row):
            return float(row.low), float(row.high), j
    return None


def find_displacements(
    df: pd.DataFrame,
    sweep: SweepEvent,
    atr_mult: float,
    max_lag: int = 6,
) -> list[DisplacementEvent]:
    """Displacement candle after a sweep with body > atr_mult * ATR and an FVG."""
    out: list[DisplacementEvent] = []
    n = len(df)
    for i in range(sweep.index + 1, min(n, sweep.index + 1 + max_lag)):
        row = df.iloc[i]
        atr = atr_at(df, i)
        if atr <= 0:
            continue
        body = _body(row)
        if body < atr_mult * atr:
            continue
        if sweep.side == Side.LONG and not _is_bullish(row):
            continue
        if sweep.side == Side.SHORT and not _is_bearish(row):
            continue
        fvg = find_fvg(df, i, sweep.side)
        if fvg is None:
            # Strong body without textbook FVG: use body as imbalance proxy.
            lo = min(float(row.open), float(row.close))
            hi = max(float(row.open), float(row.close))
            if hi - lo < 1e-12:
                mid = float(row.close)
                lo, hi = mid - 0.25 * atr, mid + 0.25 * atr
            fvg = (lo, hi)
        ob = find_order_block(df, i, sweep.side)
        if ob is None:
            ob_low, ob_high = float(row.low), float(row.high)
        else:
            ob_low, ob_high, _ = ob
        fvg_low, fvg_high = fvg
        out.append(
            DisplacementEvent(
                index=i,
                side=sweep.side,
                fvg_low=float(fvg_low),
                fvg_high=float(fvg_high),
                ob_low=float(ob_low),
                ob_high=float(ob_high),
            )
        )
        break
    return out


def _zone_for(disp: DisplacementEvent) -> tuple[float, float]:
    low = min(disp.ob_low, disp.fvg_low)
    high = max(disp.ob_high, disp.fvg_high)
    if low > high:
        low, high = high, low
    return low, high


def next_opposing_liquidity(
    swings: Sequence[Swing],
    after_index: int,
    side: Side,
    entry: float,
) -> Optional[float]:
    """Next swing pool beyond entry in the trade direction."""
    if side == Side.LONG:
        highs = [
            s.price
            for s in swings
            if s.kind == "high" and s.index <= after_index and s.price > entry
        ]
        # Also consider swings formed later if available
        highs += [
            s.price
            for s in swings
            if s.kind == "high" and s.index > after_index and s.price > entry
        ]
        return max(highs) if highs else None
    lows = [
        s.price
        for s in swings
        if s.kind == "low" and s.price < entry
    ]
    return min(lows) if lows else None


def is_dead_market(df_1h: pd.DataFrame, percentile: float = 10.0) -> bool:
    """True when latest 1h ATR% is in the bottom `percentile` of the series."""
    if len(df_1h) < 30:
        return False
    pct = atr_pct_series(df_1h).dropna()
    if len(pct) < 20:
        return False
    arr = pct.to_numpy(dtype=float)
    # Flat ATR% is not "dead" - need a real lower tail.
    if float(np.nanstd(arr)) < 1e-12:
        return False
    threshold = float(np.nanpercentile(arr, percentile))
    latest = float(pct.iloc[-1])
    return latest <= threshold


def _in_zone(price: float, zone_low: float, zone_high: float) -> bool:
    return zone_low <= price <= zone_high


def _setup_score(
    *,
    bias: Bias,
    side: Side,
    rr: float,
    min_rr: float,
    sl_atr: float,
    has_fvg: bool,
) -> float:
    score = 0.35
    if bias == "bullish" and side == Side.LONG:
        score += 0.25
    elif bias == "bearish" and side == Side.SHORT:
        score += 0.25
    elif bias == "neutral":
        score += 0.05
    else:
        score -= 0.15
    score += min(0.25, 0.1 * (rr - min_rr))
    if 0.8 <= sl_atr <= 2.0:
        score += 0.1
    if has_fvg:
        score += 0.1
    return float(max(0.0, min(1.0, score)))


def generate_setups(
    candles_15m: Sequence[Candle],
    candles_1h: Sequence[Candle],
    candles_4h: Sequence[Candle],
    symbol: str,
    cfg: Optional[dict[str, Any]] = None,
    *,
    latest_only: bool = True,
) -> list[Setup]:
    """
    Build SMC setups on 15m using 1h/4h bias.

    Pattern: liquidity sweep → displacement (+ FVG) → OB/FVG re-entry.

    latest_only (the default) keeps only setups whose zone re-entry happens on the newest
    closed bar, priced at that bar's close: the fill a market order at the next open can
    actually get. An earlier re-entry is stale, because the trade has already run or price
    has moved on, and labelling it from the next bar builds wins into the scenario bank.
    latest_only=False is the old historical scan, for inspecting structure only.
    """
    smc = merge_smc_cfg(cfg)
    lookback = int(smc["swing_lookback"])
    atr_mult = float(smc["displacement_atr_mult"])
    sl_buf = float(smc["sl_atr_buffer"])
    min_rr = float(smc["min_rr"])
    sl_min = float(smc["sl_atr_min"])
    sl_max = float(smc["sl_atr_max"])
    dead_pct = float(smc["dead_market_atr_percentile"])

    df = candles_to_df(candles_15m)
    df_1h = candles_to_df(candles_1h)
    df_4h = candles_to_df(candles_4h)

    if len(df) < 2 * lookback + 20:
        return []

    if is_dead_market(df_1h, dead_pct):
        return []

    bias = combined_bias(
        structure_bias(df_1h, lookback),
        structure_bias(df_4h, lookback),
    )

    swings = find_swings(df, lookback)
    sweeps = find_liquidity_sweeps(df, swings, lookback)
    setups: list[Setup] = []
    used_entries: set[tuple[int, str]] = set()

    for sweep in sweeps:
        # Bias filter: prefer aligned trades; allow neutral bias
        if bias == "bullish" and sweep.side != Side.LONG:
            continue
        if bias == "bearish" and sweep.side != Side.SHORT:
            continue

        displacements = find_displacements(df, sweep, atr_mult)
        for disp in displacements:
            zone_low, zone_high = _zone_for(disp)
            # Wait for a later candle whose open is back inside the zone
            for j in range(disp.index + 1, len(df)):
                entry = float(df.iloc[j].open)
                if not _in_zone(entry, zone_low, zone_high):
                    # Also accept if the bar trades into the zone and we use
                    # the zone mid as synthetic fill for historical scan
                    bar = df.iloc[j]
                    traded_in = float(bar.low) <= zone_high and float(bar.high) >= zone_low
                    if not traded_in:
                        continue
                    entry = float(np.clip(entry, zone_low, zone_high))
                    if not _in_zone(entry, zone_low, zone_high):
                        entry = 0.5 * (zone_low + zone_high)
                if latest_only:
                    if j != len(df) - 1:
                        break  # price came back to this zone on an earlier bar: stale
                    entry = float(df.iloc[j].close)

                atr = atr_at(df, j)
                if atr <= 0:
                    continue

                if sweep.side == Side.LONG:
                    sl = sweep.extreme - sl_buf * atr
                    if sl >= entry:
                        sl = entry - sl_buf * atr
                    risk = entry - sl
                else:
                    sl = sweep.extreme + sl_buf * atr
                    if sl <= entry:
                        sl = entry + sl_buf * atr
                    risk = sl - entry

                if risk <= 0:
                    continue
                sl_atr = risk / atr
                if sl_atr < sl_min or sl_atr > sl_max:
                    continue

                tp_liq = next_opposing_liquidity(swings, j, sweep.side, entry)
                min_tp_dist = min_rr * risk
                if sweep.side == Side.LONG:
                    tp_floor = entry + min_tp_dist
                    tp = max(tp_liq, tp_floor) if tp_liq is not None else tp_floor
                    # Prefer a prior swing high above entry if it meets RR
                    prior_highs = [
                        s.price
                        for s in swings
                        if s.kind == "high" and s.price >= tp_floor
                    ]
                    if prior_highs:
                        # nearest valid liquidity above
                        tp = min(prior_highs)
                    rr = (tp - entry) / risk
                else:
                    tp_ceil = entry - min_tp_dist
                    tp = min(tp_liq, tp_ceil) if tp_liq is not None else tp_ceil
                    prior_lows = [
                        s.price
                        for s in swings
                        if s.kind == "low" and s.price <= tp_ceil
                    ]
                    if prior_lows:
                        tp = max(prior_lows)
                    rr = (entry - tp) / risk

                if rr < min_rr - 1e-9:
                    continue

                key = (j, sweep.side.value)
                if key in used_entries:
                    break
                used_entries.add(key)

                has_fvg = find_fvg(df, disp.index, sweep.side) is not None
                score = _setup_score(
                    bias=bias,
                    side=sweep.side,
                    rr=rr,
                    min_rr=min_rr,
                    sl_atr=sl_atr,
                    has_fvg=has_fvg,
                )
                summary = (
                    f"{sweep.side.value} sweep@{sweep.index} lvl={sweep.level:.4f} "
                    f"disp@{disp.index} zone=[{zone_low:.4f},{zone_high:.4f}] "
                    f"bias={bias}"
                )
                try:
                    setups.append(
                        Setup(
                            symbol=symbol,
                            side=sweep.side,
                            entry=float(entry),
                            sl=float(sl),
                            tp=float(tp),
                            rr=float(rr),
                            structure_summary=summary,
                            setup_score=score,
                            atr=float(atr),
                            bias=bias,
                            zone_low=float(zone_low),
                            zone_high=float(zone_high),
                        )
                    )
                except ValueError:
                    break
                break  # one entry per displacement

    # Prefer higher-score / higher-RR setups; keep chronological uniqueness
    setups.sort(key=lambda s: (s.setup_score, s.rr), reverse=True)
    return setups
