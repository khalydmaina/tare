"""Trader: deterministic SMC candidates + LLM proposal layer."""

from trader.candidates import find_candidates
from trader.llm_trader import LLMTrader
from trader.smc import generate_setups

__all__ = ["find_candidates", "generate_setups", "LLMTrader"]
