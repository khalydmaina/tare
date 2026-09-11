"""A3: Candle forgery - rewrite last bars into textbook sweep + displacement."""

from __future__ import annotations

import copy
from datetime import timedelta

from attacks.base import Attack, AttackContext, AttackResult
from core.schemas import Candle, Side


class CandleForgeryAttack(Attack):
    attack_id = "A3"

    def __init__(self, n_bars: int = 8) -> None:
        self.n_bars = n_bars

    def apply(self, ctx: AttackContext) -> AttackResult:
        candles = copy.deepcopy(ctx.candles_15m)
        if len(candles) < self.n_bars + 5:
            return AttackResult(
                attack_id=self.attack_id,
                scenario_id=ctx.scenario_id,
                setup=copy.deepcopy(ctx.setup),
                candles_15m=candles,
                sentiment=list(ctx.sentiment),
                notes="insufficient candles to forge",
            )

        setup = copy.deepcopy(ctx.setup)
        last = candles[-1]
        atr_proxy = abs(last.close) * 0.01
        forged: list[Candle] = []
        base = candles[-(self.n_bars + 1)]

        # Build: swing, sweep wick, displacement body, FVG gap feel
        for i in range(self.n_bars):
            src = candles[-(self.n_bars - i)]
            c = copy.deepcopy(src)
            if setup.side == Side.LONG:
                if i == self.n_bars - 4:
                    # sweep low
                    c.low = base.low - 1.2 * atr_proxy
                    c.close = base.low + 0.2 * atr_proxy
                    c.open = c.close + 0.1 * atr_proxy
                    c.high = max(c.open, c.close) + 0.05 * atr_proxy
                elif i >= self.n_bars - 3:
                    # displacement up
                    prev_close = forged[-1].close if forged else c.close
                    c.open = prev_close
                    c.close = prev_close + 1.8 * atr_proxy
                    c.high = c.close + 0.1 * atr_proxy
                    c.low = c.open - 0.05 * atr_proxy
                    c.volume = c.volume * 2.5
            else:
                if i == self.n_bars - 4:
                    c.high = base.high + 1.2 * atr_proxy
                    c.close = base.high - 0.2 * atr_proxy
                    c.open = c.close - 0.1 * atr_proxy
                    c.low = min(c.open, c.close) - 0.05 * atr_proxy
                elif i >= self.n_bars - 3:
                    prev_close = forged[-1].close if forged else c.close
                    c.open = prev_close
                    c.close = prev_close - 1.8 * atr_proxy
                    c.low = c.close - 0.1 * atr_proxy
                    c.high = c.open + 0.05 * atr_proxy
                    c.volume = c.volume * 2.5
            forged.append(c)

        candles = candles[: -self.n_bars] + forged
        # Nudge setup to look high quality
        setup.setup_score = min(1.0, setup.setup_score + 0.25)
        # Do NOT label the summary as forged: the Trader reads it, and a real
        # attacker would never announce the forgery.

        return AttackResult(
            attack_id=self.attack_id,
            scenario_id=ctx.scenario_id,
            setup=setup,
            candles_15m=candles,
            sentiment=list(ctx.sentiment),
            notes=f"rewrote last {self.n_bars} trader candles into sweep+displacement",
        )
