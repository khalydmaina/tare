"""Hard risk limits. Loaded from limits.yaml; LLM cannot modify them."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from core.config import hash_limits, load_limits
from core.schemas import AccountState, Proposal


def load(path: Optional[str] = None) -> dict[str, Any]:
    return load_limits(path)


def limits_hash(limits: dict[str, Any]) -> str:
    return hash_limits(limits)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def pre_trade(
    proposal: Proposal,
    account: AccountState,
    limits: dict[str, Any],
    *,
    symbol: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """
    Return a blocked reason string, or None if the proposal clears hard limits.
    """
    now = _as_aware(now) or _utcnow()

    if account.kill_switch:
        return "kill_switch"

    halted = _as_aware(account.halted_until)
    if halted is not None and now < halted:
        return "halted"

    peak = account.peak_equity
    if peak > 0:
        dd = (peak - account.equity) / peak
        if dd >= float(limits.get("max_drawdown_kill", 0.10)):
            return "max_drawdown"

    day_start = account.day_start_equity
    if day_start > 0:
        daily_loss = (day_start - account.equity) / day_start
        if daily_loss >= float(limits.get("daily_loss_limit", 0.03)):
            return "daily_loss_limit"

    cooldown = _as_aware(account.cooldown_until)
    if cooldown is not None and now < cooldown:
        return "consecutive_loss_cooldown"

    cd_cfg = limits.get("consecutive_loss_cooldown") or {}
    loss_threshold = int(cd_cfg.get("losses", 3)) if isinstance(cd_cfg, dict) else 3
    if account.consecutive_losses >= loss_threshold and cooldown is not None and now < cooldown:
        return "consecutive_loss_cooldown"

    max_concurrent = int(limits.get("max_concurrent", 2))
    if account.open_positions >= max_concurrent:
        return "max_concurrent"

    sym = symbol
    if sym is None:
        sym = getattr(proposal, "symbol", None)
    if sym is None and isinstance(proposal.raw_json, dict):
        sym = proposal.raw_json.get("symbol")
    max_per_symbol = int(limits.get("max_per_symbol", 1))
    if sym and account.positions_by_symbol.get(str(sym), 0) >= max_per_symbol:
        return "max_per_symbol"

    max_leverage = float(limits.get("max_leverage", 3))
    if account.leverage > max_leverage:
        return "max_leverage"

    if limits.get("require_sl", True):
        if proposal.sl is None or proposal.risk_distance <= 0:
            return "no_sl"
        if proposal.side.value == "long" and proposal.sl >= proposal.entry:
            return "no_sl"
        if proposal.side.value == "short" and proposal.sl <= proposal.entry:
            return "no_sl"

    return None
