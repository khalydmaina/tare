"""Pydantic models shared across the Prosecutor pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class Action(str, Enum):
    TAKE = "take"
    SKIP = "skip"


class DecisionKind(str, Enum):
    APPROVE = "approve"
    SHRINK = "shrink"
    VETO = "veto"
    SKIP = "skip"


class OutcomeResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    TIMEOUT = "timeout"
    OPEN = "open"


class Candle(BaseModel):
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    fetched_at: datetime = Field(default_factory=utcnow)

    @field_validator("open_time", "close_time", "fetched_at", mode="before")
    @classmethod
    def _ensure_aware(cls, v: Any) -> Any:
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class SentimentItem(BaseModel):
    source: str
    text: str
    published_at: datetime
    score: float = 0.0  # -1..1 if available
    url: Optional[str] = None
    fetched_at: datetime = Field(default_factory=utcnow)

    @field_validator("published_at", "fetched_at", mode="before")
    @classmethod
    def _ensure_aware(cls, v: Any) -> Any:
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class Setup(BaseModel):
    symbol: str
    side: Side
    entry: float
    sl: float
    tp: float
    rr: float
    structure_summary: str
    setup_score: float = Field(ge=0.0, le=1.0)
    atr: float = 0.0
    bias: str = ""
    zone_low: float = 0.0
    zone_high: float = 0.0

    @model_validator(mode="after")
    def _sl_side(self) -> "Setup":
        if self.side == Side.LONG and self.sl >= self.entry:
            raise ValueError("long SL must be below entry")
        if self.side == Side.SHORT and self.sl <= self.entry:
            raise ValueError("short SL must be above entry")
        if self.rr < 0:
            raise ValueError("rr must be non-negative")
        return self


class Proposal(BaseModel):
    setup_id: Optional[int] = None
    action: Action
    side: Side
    entry: float
    sl: float
    tp: float
    confidence: int = Field(ge=0, le=100)
    rationale: str = ""
    rr: float = 0.0
    prompt_version: str = "trader_v1"
    raw_json: Optional[dict[str, Any]] = None
    latency_ms: Optional[float] = None
    attack_id: Optional[str] = None
    invalid_output: bool = False

    @property
    def risk_distance(self) -> float:
        return abs(self.entry - self.sl)


class AnomalyBreakdown(BaseModel):
    score: float = 0.0
    hard_triggers: list[str] = Field(default_factory=list)
    soft: dict[str, float] = Field(default_factory=dict)
    notes: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    kind: DecisionKind
    reason: str = ""
    size: float = 0.0
    risk_frac: float = 0.0
    p_cal: Optional[float] = None
    p_adj: Optional[float] = None
    p_be: Optional[float] = None
    anomaly: float = 0.0
    anomaly_breakdown: Optional[AnomalyBreakdown] = None
    gate_config: str = "G2"

    @classmethod
    def skip(cls, reason: str = "trader_skip") -> "Decision":
        return cls(kind=DecisionKind.SKIP, reason=reason)

    @classmethod
    def veto(
        cls,
        reason: str,
        *,
        anomaly: float = 0.0,
        p_adj: Optional[float] = None,
        p_be: Optional[float] = None,
        p_cal: Optional[float] = None,
        anomaly_breakdown: Optional[AnomalyBreakdown] = None,
        gate_config: str = "G2",
    ) -> "Decision":
        return cls(
            kind=DecisionKind.VETO,
            reason=reason,
            anomaly=anomaly,
            p_adj=p_adj,
            p_be=p_be,
            p_cal=p_cal,
            anomaly_breakdown=anomaly_breakdown,
            gate_config=gate_config,
        )


class AccountState(BaseModel):
    equity: float
    available: float
    peak_equity: float
    day_start_equity: float
    open_positions: int = 0
    positions_by_symbol: dict[str, int] = Field(default_factory=dict)
    consecutive_losses: int = 0
    cooldown_until: Optional[datetime] = None
    kill_switch: bool = False
    halted_until: Optional[datetime] = None
    leverage: float = 1.0
    open_notional: float = 0.0  # sum of |fill x size| over open positions, for the leverage cap


class Outcome(BaseModel):
    result: OutcomeResult
    r_multiple: float = 0.0
    bars_held: int = 0
    exit_price: Optional[float] = None


class GateContext(BaseModel):
    """Inputs the Inspector needs that do not come from the Trader proposal."""

    account: AccountState
    regime: Literal["low", "mid", "high"] = "mid"
    trader_candles: list[Candle] = Field(default_factory=list)
    reference_candles: list[Candle] = Field(default_factory=list)
    sentiment: list[SentimentItem] = Field(default_factory=list)
    setup_score: float = 0.0
    trailing_confidences: list[tuple[float, int]] = Field(default_factory=list)
    # (setup_score, confidence) recent takes for M1
    sentiment_history_scores: list[float] = Field(default_factory=list)
    ablation_confidence: Optional[int] = None
    # Trader re-run on the same setup with ALL sentiment stripped (M2 probe).
    ablation_action: Optional[str] = None
    # Evaluation clock. None = wall clock (live). Replays pass the scenario time
    # so feed-staleness checks (C3) are judged against the bar, not today.
    as_of: Optional[datetime] = None
