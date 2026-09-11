"""Attack base types. Attacks only modify Trader-visible inputs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from core.schemas import Candle, Proposal, SentimentItem, Setup


@dataclass
class AttackContext:
    setup: Setup
    candles_15m: list[Candle]
    candles_1h: list[Candle]
    candles_4h: list[Candle]
    sentiment: list[SentimentItem]
    true_result: str  # win | loss
    scenario_id: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackResult:
    attack_id: str
    scenario_id: str
    setup: Setup
    candles_15m: list[Candle]
    sentiment: list[SentimentItem]
    notes: str = ""


class Attack(ABC):
    attack_id: str = "base"

    @abstractmethod
    def apply(self, ctx: AttackContext) -> AttackResult:
        """Return modified Trader inputs. Never touch Inspector reference data."""
