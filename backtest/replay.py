"""Historical replay through SMC → Trader → labeler (optional gate)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backtest.blind import blind_candles
from core.schemas import Candle, Outcome, Proposal, Setup
from execution.labeler import resolve as resolve_outcome


@dataclass
class ReplayResult:
    setups: list[Setup] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)
    pairs: list[dict[str, Any]] = field(default_factory=list)


class ReplayEngine:
    def __init__(
        self,
        generate_setups: Callable[..., list[Setup]],
        propose: Callable[..., Proposal],
        smc_cfg: Optional[dict] = None,
        timeout_bars: int = 48,
    ) -> None:
        self.generate_setups = generate_setups
        self.propose = propose
        self.smc_cfg = smc_cfg or {}
        self.timeout_bars = timeout_bars

    def count_setups_only(
        self,
        symbol: str,
        c15: list[Candle],
        c1h: list[Candle],
        c4h: list[Candle],
        step: int = 1,
        lookback: int = 200,
    ) -> int:
        """Cheap pass: SMC only, no LLM - for cost estimation."""
        n = 0
        for i in range(lookback, len(c15), step):
            window = c15[i - lookback : i]
            # align higher TF roughly by time
            t = window[-1].close_time
            w1 = [c for c in c1h if c.close_time <= t][-lookback:]
            w4 = [c for c in c4h if c.close_time <= t][-lookback:]
            setups = self.generate_setups(window, w1, w4, symbol, self.smc_cfg)
            n += len(setups)
        return n

    def run(
        self,
        symbol: str,
        c15: list[Candle],
        c1h: list[Candle],
        c4h: list[Candle],
        *,
        blind: bool = False,
        step: int = 4,
        lookback: int = 200,
        max_setups: Optional[int] = None,
        sentiment_digest: str = "(no sentiment)",
    ) -> ReplayResult:
        if blind:
            c15 = blind_candles(c15)
            c1h = blind_candles(c1h)
            c4h = blind_candles(c4h)
            symbol = "INDEX"

        result = ReplayResult()
        for i in range(lookback, len(c15), step):
            if max_setups is not None and len(result.setups) >= max_setups:
                break
            window = c15[i - lookback : i]
            t = window[-1].close_time
            w1 = [c for c in c1h if c.close_time <= t][-lookback:]
            w4 = [c for c in c4h if c.close_time <= t][-lookback:]
            if len(w1) < 50 or len(w4) < 30:
                continue
            setups = self.generate_setups(window, w1, w4, symbol, self.smc_cfg)
            future = c15[i : i + self.timeout_bars + 5]
            for setup in setups:
                proposal = self.propose(
                    setup,
                    {"15m": window, "1h": w1, "4h": w4},
                    sentiment_digest,
                )
                # Label using subsequent bars (use future path as 15m proxy for resolution)
                outcome = resolve_outcome(
                    entry=proposal.entry if proposal.action.value == "take" else setup.entry,
                    sl=proposal.sl if proposal.action.value == "take" else setup.sl,
                    tp=proposal.tp if proposal.action.value == "take" else setup.tp,
                    side=setup.side.value,
                    candles=future,
                    timeout_bars=self.timeout_bars,
                )
                result.setups.append(setup)
                result.proposals.append(proposal)
                result.outcomes.append(outcome)
                result.pairs.append(
                    {
                        "symbol": symbol,
                        "side": setup.side.value,
                        "confidence": proposal.confidence,
                        "action": proposal.action.value,
                        "result": outcome.result.value,
                        "r_multiple": outcome.r_multiple,
                        "setup_score": setup.setup_score,
                        "blind": blind,
                    }
                )
                if max_setups is not None and len(result.setups) >= max_setups:
                    break
        return result
