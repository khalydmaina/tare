"""Unguarded counterfactual book: every take at full 1% risk."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Union

from core.config import load_settings
from core.schemas import Action, Candle, Outcome, OutcomeResult, Proposal, Side
from execution.bitget_broker import apply_slippage, fee_notional
from execution.labeler import resolve

logger = logging.getLogger(__name__)

SideLike = Union[Side, str]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_side(side: SideLike) -> Side:
    if isinstance(side, Side):
        return side
    return Side(str(side).lower())


@dataclass
class ShadowPosition:
    id: str
    proposal_id: Optional[int]
    symbol: str
    side: Side
    entry: float
    sl: float
    tp: float
    size: float
    fill_price: float
    fees_open: float
    risk_frac: float
    opened_at: datetime
    status: str = "open"
    outcome: Optional[Outcome] = None
    exit_price: Optional[float] = None
    fees_close: float = 0.0
    pnl: float = 0.0
    closed_at: Optional[datetime] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class EquityPoint:
    ts: datetime
    equity: float


class ShadowBook:
    """Simulated book that ignores Inspector sizing - always full base risk."""

    def __init__(
        self,
        starting_equity: float = 10_000.0,
        *,
        risk_frac: Optional[float] = None,
        slippage_bps: Optional[float] = None,
        fee_bps: Optional[float] = None,
        timeout_bars: Optional[int] = None,
    ) -> None:
        settings = load_settings()
        gate = settings.get("gate", {})
        ex = settings.get("execution", {})
        cal = settings.get("calibration", {})
        self.risk_frac = float(
            risk_frac if risk_frac is not None else gate.get("base_risk", 0.01)
        )
        self.slippage_bps = float(
            slippage_bps if slippage_bps is not None else ex.get("slippage_bps", 5)
        )
        self.fee_bps = float(fee_bps if fee_bps is not None else ex.get("fee_bps", 4))
        self.timeout_bars = int(
            timeout_bars if timeout_bars is not None else cal.get("timeout_bars", 48)
        )
        self.starting_equity = float(starting_equity)
        self.equity = float(starting_equity)
        self.open_positions: dict[str, ShadowPosition] = {}
        self.closed_positions: list[ShadowPosition] = []
        self.equity_curve: list[EquityPoint] = [EquityPoint(ts=_utcnow(), equity=self.equity)]

    def size_for_risk(self, entry: float, sl: float, equity: Optional[float] = None) -> float:
        risk_dist = abs(entry - sl)
        if risk_dist <= 0:
            raise ValueError("entry and sl must differ")
        eq = self.equity if equity is None else float(equity)
        risk_cash = eq * self.risk_frac
        return risk_cash / risk_dist

    def open_from_proposal(
        self,
        proposal: Proposal,
        *,
        symbol: str,
        next_open: Optional[float] = None,
        last_price: Optional[float] = None,
        proposal_id: Optional[int] = None,
    ) -> Optional[ShadowPosition]:
        """Open a shadow position for a take proposal at full 1% risk."""
        if proposal.action != Action.TAKE:
            return None
        return self.open_position(
            symbol=symbol,
            side=proposal.side,
            entry=proposal.entry,
            sl=proposal.sl,
            tp=proposal.tp,
            next_open=next_open,
            last_price=last_price,
            proposal_id=proposal_id if proposal_id is not None else proposal.setup_id,
        )

    def open_position(
        self,
        symbol: str,
        side: SideLike,
        entry: float,
        sl: float,
        tp: float,
        *,
        next_open: Optional[float] = None,
        last_price: Optional[float] = None,
        proposal_id: Optional[int] = None,
    ) -> ShadowPosition:
        side_e = _as_side(side)
        base = next_open if next_open is not None else last_price
        if base is None:
            base = entry
        fill = apply_slippage(float(base), side_e, self.slippage_bps, is_entry=True)
        # Size off proposed entry/sl risk distance at current equity (full base risk)
        size = self.size_for_risk(entry, sl)
        fees = fee_notional(fill * size, self.fee_bps)
        self.equity -= fees
        pos = ShadowPosition(
            id=f"shadow-{uuid.uuid4().hex[:12]}",
            proposal_id=proposal_id,
            symbol=symbol,
            side=side_e,
            entry=float(entry),
            sl=float(sl),
            tp=float(tp),
            size=size,
            fill_price=fill,
            fees_open=fees,
            risk_frac=self.risk_frac,
            opened_at=_utcnow(),
            meta={"slippage_bps": self.slippage_bps, "fee_bps": self.fee_bps},
        )
        self.open_positions[pos.id] = pos
        self._record_equity()
        logger.info(
            "shadow open id=%s fill=%.6f size=%.6f fees=%.6f risk=%.4f",
            pos.id,
            fill,
            size,
            fees,
            self.risk_frac,
        )
        return pos

    def resolve_position(
        self,
        position_id: str,
        candles: Sequence[Candle],
        *,
        timeout_bars: Optional[int] = None,
    ) -> Outcome:
        """Label a shadow position and realize PnL into equity."""
        pos = self.open_positions.get(position_id)
        if pos is None:
            raise KeyError(f"no open shadow position {position_id}")
        bars = timeout_bars if timeout_bars is not None else self.timeout_bars
        outcome = resolve(
            entry=pos.fill_price,
            sl=pos.sl,
            tp=pos.tp,
            side=pos.side,
            candles=candles,
            timeout_bars=bars,
        )
        if outcome.result == OutcomeResult.OPEN:
            return outcome

        exit_price = outcome.exit_price
        if exit_price is None:
            exit_price = candles[min(len(candles), bars) - 1].close if candles else pos.fill_price

        if pos.side == Side.LONG:
            gross = (exit_price - pos.fill_price) * pos.size
        else:
            gross = (pos.fill_price - exit_price) * pos.size
        exit_fees = fee_notional(exit_price * pos.size, self.fee_bps)
        pnl = gross - exit_fees
        self.equity += pnl
        pos.status = "closed"
        pos.outcome = outcome
        pos.exit_price = exit_price
        pos.fees_close = exit_fees
        pos.pnl = pnl
        pos.closed_at = _utcnow()
        self.open_positions.pop(position_id, None)
        self.closed_positions.append(pos)
        self._record_equity()
        logger.info(
            "shadow close id=%s result=%s r=%.3f pnl=%.6f equity=%.2f",
            pos.id,
            outcome.result.value,
            outcome.r_multiple,
            pnl,
            self.equity,
        )
        return outcome

    def resolve_all(
        self,
        candles_by_symbol: dict[str, Sequence[Candle]],
        *,
        timeout_bars: Optional[int] = None,
    ) -> list[Outcome]:
        outcomes: list[Outcome] = []
        for pid in list(self.open_positions.keys()):
            pos = self.open_positions[pid]
            candles = candles_by_symbol.get(pos.symbol, [])
            if not candles:
                continue
            out = self.resolve_position(pid, candles, timeout_bars=timeout_bars)
            if out.result != OutcomeResult.OPEN:
                outcomes.append(out)
        return outcomes

    def _record_equity(self) -> None:
        self.equity_curve.append(EquityPoint(ts=_utcnow(), equity=self.equity))

    def snapshot(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "open": len(self.open_positions),
            "closed": len(self.closed_positions),
            "risk_frac": self.risk_frac,
            "equity_curve": [
                {"ts": p.ts.isoformat(), "equity": p.equity} for p in self.equity_curve
            ],
        }
