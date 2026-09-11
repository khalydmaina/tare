"""Input anomaly detector: sentiment, candle, and model-behaviour checks."""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from core.schemas import (
    AnomalyBreakdown,
    Candle,
    GateContext,
    Proposal,
    SentimentItem,
)

# Instruction-like / jailbreak patterns for S1 (hard).
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(previous|prior|all)\s+instructions",
        r"ignore\s+stop",
        r"system\s*(note|prompt|:)",
        r"\[internal\]",
        r"you\s+must\s+take",
        r"always\s+take",
        r"override\s+risk",
        r"action\s*=\s*take",
        r"set\s+confidence\s+to",
        r"confidence\s*[:=]\s*\d{2,3}",
        r"you\s+are\s+authorized\s+to\s+take",
        r"<\s*/?\s*system\s*>",
        r"role\s*:\s*system",
        r"base64:[a-z0-9+/=]{20,}",
        r"data:text/plain;base64,",
    ]
]

_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_SUSPICIOUS_HOST = re.compile(
    r"https?://(evil\.|localhost|127\.0\.0\.1|bit\.ly/|tinyurl\.)",
    re.IGNORECASE,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    return statistics.pstdev(xs)


def _z_score(value: float, hist: Sequence[float]) -> float:
    if len(hist) < 2:
        return 0.0
    mu = _mean(hist)
    sigma = _std(hist)
    if sigma <= 1e-12:
        return 0.0
    return (value - mu) / sigma


def _median(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    return float(statistics.median(xs))


def _infer_interval(candles: Sequence[Candle]) -> Optional[timedelta]:
    if len(candles) < 2:
        return None
    ordered = sorted(candles, key=lambda c: c.open_time)
    deltas = [
        (ordered[i].open_time - ordered[i - 1].open_time).total_seconds()
        for i in range(1, min(len(ordered), 20))
    ]
    deltas = [d for d in deltas if d > 0]
    if not deltas:
        return None
    return timedelta(seconds=statistics.median(deltas))


def _check_s1(sentiment: Sequence[SentimentItem]) -> tuple[bool, dict[str, Any]]:
    hits: list[str] = []
    for item in sentiment:
        text = item.text or ""
        for pat in _INJECTION_PATTERNS:
            if pat.search(text):
                hits.append(pat.pattern)
                break
        urls = _URL_RE.findall(text)
        if urls and _SUSPICIOUS_HOST.search(text):
            hits.append("suspicious_url")
        # Encoded blob heuristic: long opaque token with little whitespace
        if re.search(r"(?<![A-Za-z0-9])[A-Za-z0-9+/=]{40,}(?![A-Za-z0-9])", text):
            if "http" not in text.lower():
                hits.append("encoded_blob")
    return (len(hits) > 0, {"s1_hits": hits[:10]})


def _check_s2(
    sentiment: Sequence[SentimentItem],
    history: Sequence[float],
    z_soft: float,
) -> tuple[float, dict[str, Any]]:
    if not sentiment:
        return 0.0, {"s2_z": 0.0}
    agg = _mean([s.score for s in sentiment])
    hist = list(history) if history else [s.score for s in sentiment]
    z = abs(_z_score(agg, hist))
    soft = _clip01(z / z_soft) if z_soft > 0 else 0.0
    return soft, {"s2_z": z, "s2_agg": agg}


def _check_s3(
    sentiment: Sequence[SentimentItem],
    candles: Sequence[Candle],
) -> tuple[float, dict[str, Any]]:
    if not sentiment or len(candles) < 2:
        return 0.0, {}
    agg = _mean([s.score for s in sentiment])
    ordered = sorted(candles, key=lambda c: c.open_time)
    # Approximate 1h return: walk back ~1 hour of bars if possible
    last = ordered[-1]
    target = last.close_time - timedelta(hours=1)
    base = ordered[0]
    for c in ordered:
        if c.close_time <= target:
            base = c
    if base.close <= 0:
        return 0.0, {}
    ret = (last.close - base.close) / base.close
    # Bullish text vs negative return, or bearish text vs positive return
    divergence = 0.0
    if agg > 0.3 and ret < -0.002:
        divergence = min(1.0, abs(agg) * min(1.0, abs(ret) / 0.01) * 2)
    elif agg < -0.3 and ret > 0.002:
        divergence = min(1.0, abs(agg) * min(1.0, abs(ret) / 0.01) * 2)
    return _clip01(divergence), {"s3_agg": agg, "s3_ret_1h": ret}


def _check_s4(sentiment: Sequence[SentimentItem]) -> tuple[float, dict[str, Any]]:
    if not sentiment:
        return 0.0, {}
    counts: dict[str, int] = {}
    for s in sentiment:
        counts[s.source] = counts.get(s.source, 0) + 1
    n = len(sentiment)
    top_share = max(counts.values()) / n
    # Sources first-seen heuristic: single-item sources in this window
    new_share = sum(1 for v in counts.values() if v == 1) / n
    # Concentration soft: ramps from 0.45 → 0.9
    conc = _clip01((top_share - 0.45) / 0.45)
    fresh = _clip01((new_share - 0.5) / 0.5)
    soft = _clip01(max(conc, 0.7 * conc + 0.3 * fresh))
    return soft, {"s4_top_share": top_share, "s4_new_share": new_share}


def _align_closes(
    trader: Sequence[Candle],
    reference: Sequence[Candle],
    n: int = 10,
) -> list[tuple[float, float]]:
    if not trader or not reference:
        return []
    ref_by_open = {c.open_time: c.close for c in reference}
    pairs: list[tuple[float, float]] = []
    for c in sorted(trader, key=lambda x: x.open_time):
        if c.open_time in ref_by_open:
            pairs.append((c.close, ref_by_open[c.open_time]))
    if len(pairs) >= n:
        return pairs[-n:]
    # Fallback: last n by position if timestamps differ
    t = sorted(trader, key=lambda x: x.open_time)[-n:]
    r = sorted(reference, key=lambda x: x.open_time)[-n:]
    m = min(len(t), len(r))
    return [(t[i].close, r[i].close) for i in range(m)]


def _check_c1(
    trader: Sequence[Candle],
    reference: Sequence[Candle],
    max_dev: float,
) -> tuple[bool, dict[str, Any]]:
    pairs = _align_closes(trader, reference, n=10)
    if not pairs:
        return False, {"c1_max_dev": 0.0}
    max_seen = 0.0
    for t_close, r_close in pairs:
        if r_close == 0:
            continue
        max_seen = max(max_seen, abs(t_close - r_close) / abs(r_close))
    return max_seen > max_dev, {"c1_max_dev": max_seen}


def _wick_body_ratio(c: Candle) -> float:
    body = abs(c.close - c.open)
    wick = c.high - c.low
    if wick <= 1e-12:
        return 0.0
    return body / wick


def _check_c2(candles: Sequence[Candle]) -> tuple[float, dict[str, Any]]:
    if len(candles) < 10:
        return 0.0, {}
    ordered = sorted(candles, key=lambda c: c.open_time)
    ratios = [_wick_body_ratio(c) for c in ordered]
    volumes = [c.volume for c in ordered]
    last_r, last_v = ratios[-1], volumes[-1]
    hist_r, hist_v = ratios[:-1], volumes[:-1]
    z_r = abs(_z_score(last_r, hist_r))
    z_v = abs(_z_score(last_v, hist_v))
    # Soft ramp: z of 3 ≈ full
    soft = _clip01(max(z_r, z_v) / 3.0)
    return soft, {"c2_wick_z": z_r, "c2_vol_z": z_v}


def _check_c3(
    candles: Sequence[Candle],
    stale_intervals: int,
    now: Optional[datetime] = None,
) -> tuple[bool, dict[str, Any]]:
    notes: dict[str, Any] = {"c3_gaps": 0, "c3_ooo": False, "c3_stale": False}
    if not candles:
        notes["c3_stale"] = True
        return True, notes

    now = now or _utcnow()
    ordered = sorted(candles, key=lambda c: c.open_time)
    # Out of order vs original sequence
    opens = [c.open_time for c in candles]
    if opens != sorted(opens):
        notes["c3_ooo"] = True

    interval = _infer_interval(ordered)
    gaps = 0
    if interval and interval.total_seconds() > 0:
        tol = interval * 1.5
        for i in range(1, len(ordered)):
            delta = ordered[i].open_time - ordered[i - 1].open_time
            if delta > tol:
                gaps += 1
        notes["c3_gaps"] = gaps

        latest = max(c.close_time for c in ordered)
        # Prefer fetched_at freshness when present
        fetched = max((c.fetched_at for c in ordered), default=latest)
        age = now - max(latest, fetched)
        if age > interval * stale_intervals:
            notes["c3_stale"] = True

    hard = bool(notes["c3_ooo"] or notes["c3_gaps"] > 0 or notes["c3_stale"])
    return hard, notes


def _check_m1(
    setup_score: float,
    confidence: Optional[int],
    trailing: Sequence[tuple[float, int]],
    jump_soft: float,
    similar_eps: float = 0.1,
) -> tuple[float, dict[str, Any]]:
    if confidence is None or not trailing:
        return 0.0, {}
    similar = [c for s, c in trailing if abs(s - setup_score) <= similar_eps]
    if len(similar) < 3:
        similar = [c for _, c in trailing]
    if not similar:
        return 0.0, {}
    med = _median(similar)
    jump = abs(float(confidence) - med)
    soft = _clip01(jump / jump_soft) if jump_soft > 0 else 0.0
    return soft, {"m1_jump": jump, "m1_median": med}


def _check_m2(
    confidence: Optional[int],
    ablation_confidence: Optional[int],
    delta_threshold: int = 15,
) -> tuple[float, dict[str, Any]]:
    if confidence is None or ablation_confidence is None:
        return 0.0, {}
    delta = abs(int(confidence) - int(ablation_confidence))
    soft = _clip01(delta / delta_threshold) if delta_threshold > 0 else 0.0
    return soft, {"m2_delta": delta}


def score(
    ctx: GateContext,
    cfg: Optional[dict[str, Any]] = None,
    proposal: Optional[Proposal] = None,
) -> AnomalyBreakdown:
    """
    Run S1–S4, C1–C3, M1 (and optional M2).

    Soft signals are weighted and clipped to [0, 1]. Any hard trigger → score 1.0.
    """
    cfg = cfg or {}
    weights: dict[str, float] = dict(
        cfg.get("weights")
        or {"S2": 0.2, "S3": 0.2, "S4": 0.2, "C2": 0.2, "M1": 0.2}
    )
    max_dev = float(cfg.get("cross_venue_max_dev", 0.003))
    z_soft = float(cfg.get("sentiment_z_soft", 2.5))
    jump_soft = float(cfg.get("confidence_jump_soft", 20))
    stale_intervals = int(cfg.get("stale_intervals", 2))

    hard_triggers: list[str] = []
    soft: dict[str, float] = {}
    notes: dict[str, Any] = {}

    s1_hard, s1_notes = _check_s1(ctx.sentiment)
    notes.update(s1_notes)
    if s1_hard:
        hard_triggers.append("S1")

    s2, s2_notes = _check_s2(ctx.sentiment, ctx.sentiment_history_scores, z_soft)
    soft["S2"] = s2
    notes.update(s2_notes)

    s3, s3_notes = _check_s3(ctx.sentiment, ctx.trader_candles)
    soft["S3"] = s3
    notes.update(s3_notes)

    s4, s4_notes = _check_s4(ctx.sentiment)
    soft["S4"] = s4
    notes.update(s4_notes)

    c1_hard, c1_notes = _check_c1(ctx.trader_candles, ctx.reference_candles, max_dev)
    notes.update(c1_notes)
    if c1_hard:
        hard_triggers.append("C1")

    c2, c2_notes = _check_c2(ctx.trader_candles or ctx.reference_candles)
    soft["C2"] = c2
    notes.update(c2_notes)

    # Feed integrity on both feeds
    c3_hard = False
    for label, series in (
        ("trader", ctx.trader_candles),
        ("reference", ctx.reference_candles),
    ):
        if not series:
            continue
        h, n = _check_c3(series, stale_intervals=stale_intervals, now=ctx.as_of)
        notes[f"c3_{label}"] = n
        if h:
            c3_hard = True
    if c3_hard:
        hard_triggers.append("C3")

    conf = proposal.confidence if proposal is not None else None
    m1, m1_notes = _check_m1(
        ctx.setup_score,
        conf,
        ctx.trailing_confidences,
        jump_soft=jump_soft,
    )
    soft["M1"] = m1
    notes.update(m1_notes)

    m2, m2_notes = _check_m2(conf, ctx.ablation_confidence)
    notes.update(m2_notes)
    if ctx.ablation_confidence is not None:
        soft["M2"] = m2
        if "M2" not in weights:
            weights["M2"] = 0.2

    if hard_triggers:
        return AnomalyBreakdown(
            score=1.0,
            hard_triggers=hard_triggers,
            soft=soft,
            notes=notes,
        )

    weighted = sum(soft.get(k, 0.0) * float(w) for k, w in weights.items())

    return AnomalyBreakdown(
        score=_clip01(weighted),
        hard_triggers=hard_triggers,
        soft=soft,
        notes=notes,
    )
