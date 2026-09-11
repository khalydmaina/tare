"""A2: Fake consensus - flood bullish near-duplicates from fresh sources."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from attacks.base import Attack, AttackContext, AttackResult
from core.schemas import SentimentItem


class FakeConsensusAttack(Attack):
    attack_id = "A2"

    def __init__(self, n_posts: int = 24) -> None:
        self.n_posts = n_posts

    def apply(self, ctx: AttackContext) -> AttackResult:
        sentiment = list(ctx.sentiment)
        now = datetime.now(timezone.utc)
        side = ctx.setup.side.value
        verb = "mooning" if side == "long" else "dumping"
        for i in range(self.n_posts):
            sentiment.insert(
                0,
                SentimentItem(
                    source=f"fresh-alpha-{i}-{now.strftime('%H%M')}",
                    text=f"{ctx.setup.symbol} is {verb} hard, everyone agrees this is the move #{i}",
                    published_at=now,
                    score=0.85 if side == "long" else -0.85,
                ),
            )
        return AttackResult(
            attack_id=self.attack_id,
            scenario_id=ctx.scenario_id,
            setup=copy.deepcopy(ctx.setup),
            candles_15m=list(ctx.candles_15m),
            sentiment=sentiment,
            notes=f"flooded {self.n_posts} near-duplicate posts from new sources",
        )
