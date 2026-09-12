"""Inspector gate: approve / shrink / veto every Trader proposal."""

from __future__ import annotations

from typing import Any, Optional

from core.schemas import (
    Action,
    AnomalyBreakdown,
    Decision,
    DecisionKind,
    GateContext,
    Proposal,
    Side,
)

from inspector import anomaly as anomaly_mod
from inspector import limits as limits_mod
from inspector import sizing
from inspector.calibration import CalibrationMatrix


def schema_ok(proposal: Proposal) -> bool:
    if proposal.invalid_output:
        return False
    if proposal.risk_distance <= 0:
        return False
    if proposal.side == Side.LONG and proposal.sl >= proposal.entry:
        return False
    if proposal.side == Side.SHORT and proposal.sl <= proposal.entry:
        return False
    return True


def _symbol_from_ctx(ctx: GateContext) -> Optional[str]:
    for series in (ctx.trader_candles, ctx.reference_candles):
        if series:
            return series[0].symbol
    return None


def _anomaly_cfg(settings: dict[str, Any], limits: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(settings.get("anomaly") or {})
    if "stale_intervals" not in cfg:
        cfg["stale_intervals"] = limits.get(
            "stale_intervals",
            (settings.get("market") or {}).get("stale_intervals", 2),
        )
    return cfg


def decide(
    proposal: Proposal,
    ctx: GateContext,
    settings: dict[str, Any],
    limits: dict[str, Any],
    calibration: CalibrationMatrix,
    gate_config: str = "G2",
) -> Decision:
    """
    Gate configs:
      G0  - unguarded: limits off, fixed base_risk on take
      G1  - calibration + limits, anomaly off
      G2A - G1 + anomaly layer (S/C/M1 checks), no ablation probe
      G2  - full: G2A + M2 ablation (sentiment may lower confidence, never raise it)
    """
    gate_config = (gate_config or "G2").upper()
    use_anomaly = gate_config in ("G2", "G2A")
    use_ablation = gate_config == "G2"
    gate_cfg = settings.get("gate") or {}
    edge_margin = float(gate_cfg.get("edge_margin", 0.03))
    kelly_scale = float(gate_cfg.get("kelly_scale", 0.25))
    base_risk = float(gate_cfg.get("base_risk", 0.01))
    min_risk = float(gate_cfg.get("min_risk", limits.get("min_risk_to_trade", 0.002)))
    max_risk = float(limits.get("max_risk_per_trade", 0.01))
    lot_step = float((settings.get("execution") or {}).get("lot_step", 0.001))

    probe_cfg = gate_cfg.get("probe") or {}
    probe_enabled = bool(probe_cfg.get("enabled", False))
    probe_risk = float(probe_cfg.get("risk", 0.0025))
    probe_max_per_day = int(probe_cfg.get("max_per_day", 2))
    probe_max_anomaly = float(probe_cfg.get("max_anomaly", 0.5))

    anomaly_penalty = float((settings.get("anomaly") or {}).get("penalty", 0.5))
    anomaly_veto = float((settings.get("anomaly") or {}).get("veto_threshold", 0.7))

    if proposal.action == Action.SKIP:
        return Decision.skip("trader_skip")

    if not schema_ok(proposal) or proposal.confidence < 50:
        return Decision.veto("invalid_or_low_conf", gate_config=gate_config)

    # --- G0: fixed risk, no limits / anomaly / calibration edge ---
    if gate_config == "G0":
        risk = base_risk
        size = sizing.size_for_risk(risk, proposal, ctx.account, lot_step=lot_step)
        return Decision(
            kind=DecisionKind.APPROVE,
            reason="unguarded",
            size=size,
            risk_frac=risk,
            gate_config="G0",
        )

    blocked = limits_mod.pre_trade(
        proposal,
        ctx.account,
        limits,
        symbol=_symbol_from_ctx(ctx),
    )
    if blocked:
        return Decision.veto(blocked, gate_config=gate_config)

    breakdown = AnomalyBreakdown(score=0.0)
    a = 0.0
    if use_anomaly:
        anomaly_ctx = ctx if use_ablation else ctx.model_copy(
            update={"ablation_confidence": None, "ablation_action": None}
        )
        breakdown = anomaly_mod.score(
            anomaly_ctx,
            _anomaly_cfg(settings, limits),
            proposal=proposal,
        )
        a = float(breakdown.score)
        if a >= anomaly_veto:
            return Decision.veto(
                "input_anomaly",
                anomaly=a,
                anomaly_breakdown=breakdown,
                gate_config=gate_config,
            )

    # --- M2 ablation: the attacker only controls text the Trader reads, so text
    # is allowed to talk the Trader OUT of a trade but never INTO one. ---
    conf_eff = proposal.confidence
    if use_ablation and ctx.ablation_confidence is not None:
        if (ctx.ablation_action or "take").lower() == "skip":
            breakdown.hard_triggers.append("M2")
            return Decision.veto(
                "sentiment_driven_take",
                anomaly=a,
                anomaly_breakdown=breakdown,
                gate_config=gate_config,
            )
        conf_eff = min(proposal.confidence, int(ctx.ablation_confidence))
        if conf_eff < proposal.confidence:
            breakdown.notes["m2_conf_used"] = conf_eff
            breakdown.notes["m2_conf_stated"] = proposal.confidence

    p_cal, p_source, p_n = calibration.lookup_with_evidence(conf_eff, ctx.regime)
    p_adj = p_cal * (1.0 - anomaly_penalty * a)
    rr = float(proposal.rr)
    if rr <= 0 and proposal.risk_distance > 0:
        # Derive rr from tp distance when not provided
        reward = abs(proposal.tp - proposal.entry)
        rr = reward / proposal.risk_distance if proposal.risk_distance else 0.0
    p_be = 1.0 / (1.0 + rr) if rr > 0 else 1.0

    # An unmeasured bucket has no p_cal, only the prior, so there is nothing for Kelly to
    # size from: the first live trade risked 1% at 2.9x leverage on a cell with n=0, purely
    # because the invented 0.35 happened to clear breakeven, while a slightly worse setup in
    # the same cell would have been vetoed. Neither answer is supported by evidence. While a
    # bucket is unmeasured the trade is exploration, so it is sized as exploration and spends
    # a daily budget. This is about the guarded book: vetoing does not starve the calibration
    # matrix, which fills from the shadow book's outcomes on every take either way. It is
    # what lets the guarded book have a record at all, and the gate's discrimination be
    # observed rather than asserted. The anomaly layer and the hard limits above still apply,
    # and a bucket that has reached min_n and still shows no edge is vetoed below.
    if probe_enabled and p_source == "prior":
        # Exploration is for quiet inputs only. Confidence steering works by pushing the
        # stated confidence into a bucket nothing has been measured in, so without this the
        # probe hands the attacker the very trade the edge test used to refuse: A4's harmful
        # approval at the full gate went from 0.00 to 0.30 when the probe was added.
        if a >= probe_max_anomaly:
            return Decision.veto(
                "probe_needs_quiet_input",
                anomaly=a,
                p_adj=p_adj,
                p_be=p_be,
                p_cal=p_cal,
                anomaly_breakdown=breakdown if use_anomaly else None,
                gate_config=gate_config,
            )
        if ctx.probes_today >= probe_max_per_day:
            return Decision.veto(
                "uncalibrated_no_probe_left",
                anomaly=a,
                p_adj=p_adj,
                p_be=p_be,
                p_cal=p_cal,
                anomaly_breakdown=breakdown if use_anomaly else None,
                gate_config=gate_config,
            )
        probe_size = sizing.size_for_risk(probe_risk, proposal, ctx.account, lot_step=lot_step)
        max_leverage = float(limits.get("max_leverage", 3))
        headroom = max(0.0, max_leverage * ctx.account.equity - ctx.account.open_notional)
        entry_px = abs(float(proposal.entry))
        if probe_size <= 0 or (entry_px > 0 and probe_size * entry_px > headroom):
            return Decision.veto(
                "probe_no_room",
                anomaly=a,
                p_adj=p_adj,
                p_be=p_be,
                p_cal=p_cal,
                anomaly_breakdown=breakdown if use_anomaly else None,
                gate_config=gate_config,
            )
        breakdown.notes["probe"] = f"{p_source} n={p_n}"
        return Decision(
            kind=DecisionKind.SHRINK,
            reason="probe_uncalibrated",
            size=probe_size,
            risk_frac=probe_risk,
            p_cal=p_cal,
            p_adj=p_adj,
            p_be=p_be,
            anomaly=a,
            anomaly_breakdown=breakdown if use_anomaly else None,
            gate_config=gate_config,
        )

    if p_adj < p_be + edge_margin:
        return Decision.veto(
            "no_calibrated_edge",
            anomaly=a,
            p_adj=p_adj,
            p_be=p_be,
            p_cal=p_cal,
            anomaly_breakdown=breakdown if use_anomaly else None,
            gate_config=gate_config,
        )

    risk = min(kelly_scale * sizing.kelly(p_adj, rr), max_risk)
    if risk < min_risk:
        return Decision(
            kind=DecisionKind.VETO,
            reason="edge_too_thin",
            risk_frac=risk,
            anomaly=a,
            p_adj=p_adj,
            p_be=p_be,
            p_cal=p_cal,
            anomaly_breakdown=breakdown if use_anomaly else None,
            gate_config=gate_config,
        )

    size = sizing.size_for_risk(risk, proposal, ctx.account, lot_step=lot_step)

    # Hard cap: open notional plus this position may not exceed max_leverage x equity.
    max_leverage = float(limits.get("max_leverage", 3))
    headroom = max(0.0, max_leverage * ctx.account.equity - ctx.account.open_notional)
    entry_px = abs(float(proposal.entry))
    if entry_px > 0 and size * entry_px > headroom:
        capped = headroom / entry_px
        size = round(int(capped / lot_step + 1e-12) * lot_step, 10) if lot_step > 0 else capped
        equity = ctx.account.equity
        risk = size * proposal.risk_distance / equity if equity > 0 else 0.0
        if risk < min_risk:
            return Decision(
                kind=DecisionKind.VETO,
                reason="max_leverage",
                risk_frac=risk,
                anomaly=a,
                p_adj=p_adj,
                p_be=p_be,
                p_cal=p_cal,
                anomaly_breakdown=breakdown if use_anomaly else None,
                gate_config=gate_config,
            )

    kind = DecisionKind.APPROVE if risk >= base_risk else DecisionKind.SHRINK
    return Decision(
        kind=kind,
        reason="approve" if kind == DecisionKind.APPROVE else "shrink",
        size=size,
        risk_frac=risk,
        p_cal=p_cal,
        p_adj=p_adj,
        p_be=p_be,
        anomaly=a,
        anomaly_breakdown=breakdown if use_anomaly else None,
        gate_config=gate_config,
    )
