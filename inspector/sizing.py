"""Kelly fraction and risk-based position sizing."""

from __future__ import annotations

import math

from core.schemas import AccountState, Proposal


def kelly(p: float, b: float) -> float:
    """Kelly fraction for win probability p and reward-to-risk b."""
    if b <= 0:
        return 0.0
    p = max(0.0, min(1.0, p))
    return max(0.0, (p * b - (1.0 - p)) / b)


def quarter_kelly(p: float, b: float, scale: float = 0.25) -> float:
    return max(0.0, scale * kelly(p, b))


def size_for_risk(
    risk_frac: float,
    proposal: Proposal,
    account: AccountState,
    lot_step: float = 0.001,
) -> float:
    """
    Position size = equity * risk_frac / |entry - sl|, rounded down to lot_step.
    """
    dist = abs(proposal.entry - proposal.sl)
    if dist <= 0 or account.equity <= 0 or risk_frac <= 0:
        return 0.0
    raw = account.equity * risk_frac / dist
    if lot_step is None or lot_step <= 0:
        return float(raw)
    steps = math.floor(raw / lot_step + 1e-12)
    if steps <= 0:
        return 0.0
    # Avoid binary float dust on common steps
    return round(steps * lot_step, 10)
