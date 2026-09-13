#!/usr/bin/env python3
"""Make one real trading decision through a model endpoint, the way the live bot does.

Checks that a provider can actually stand in as the Trader before the bot depends on it:
the request goes through LLMTrader.propose (same system prompt, same payload, same JSON
handling and retries), on a real setup from the scenario bank with ordinary background news.
Prints whether a valid decision came back, how long it took and how many tokens it used, so
a prepaid credit can be turned into a number of calls.

Reads CHECK_API_KEY, CHECK_BASE_URL and CHECK_MODEL from the environment and never prints
the key.

    CHECK_BASE_URL=https://hackathon.bitgetops.com/v1 CHECK_MODEL=qwen3.8-max \\
    CHECK_API_KEY=... python scripts/check_trader_model.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openai import OpenAI  # noqa: E402

from backtest.blind import blind_bundle  # noqa: E402
from core.config import ConfigBundle  # noqa: E402
from data.sentiment_feed import SentimentFeed  # noqa: E402
from scripts.run_attacks import add_background, load_scenarios  # noqa: E402
from trader.llm_trader import LLMTrader  # noqa: E402


class Recording:
    """Wraps the OpenAI client so every response's usage is kept; the Trader never sees it."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client
        self.responses: list = []
        self.chat = self
        self.completions = self

    def create(self, **request):
        resp = self._client.chat.completions.create(**request)
        self.responses.append(resp)
        return resp


def main() -> int:
    key = os.getenv("CHECK_API_KEY", "")
    base_url = os.getenv("CHECK_BASE_URL", "")
    model = os.getenv("CHECK_MODEL", "")
    if not (key and base_url and model):
        print("CHECK_API_KEY, CHECK_BASE_URL and CHECK_MODEL must all be set")
        return 2

    scenario = load_scenarios(ROOT / "data" / "scenarios.jsonl")[-1]
    add_background([scenario])
    os.environ["LLM_BASE_URL"], os.environ["LLM_MODEL"] = base_url, model
    recording = Recording(OpenAI(api_key=key, base_url=base_url))
    trader = LLMTrader(ConfigBundle().settings, client=recording)

    tfs = {"15m": scenario.candles_15m, "1h": scenario.candles_1h, "4h": scenario.candles_4h}
    b_setup, b_tfs, _ = blind_bundle(scenario.setup, {k: list(v) for k, v in tfs.items()})
    b_tfs = {k: v[-30:] for k, v in b_tfs.items()}
    indicators = {"setup_score": scenario.setup.setup_score, "bias": scenario.setup.bias}

    print(f"endpoint {base_url}, model {model}, setup {scenario.scenario_id}")
    t0 = time.perf_counter()
    proposal = trader.propose(b_setup, b_tfs, SentimentFeed.digest(scenario.sentiment), indicators)
    seconds = time.perf_counter() - t0

    print(f"requests sent: {len(recording.responses) or 'none answered'}, {seconds:.1f}s")
    for i, resp in enumerate(recording.responses, 1):
        u = resp.usage
        detail = getattr(u, "completion_tokens_details", None)
        reasoning = getattr(detail, "reasoning_tokens", None) if detail else None
        print(f"  response {i}: model={resp.model} prompt_tokens={u.prompt_tokens} "
              f"completion_tokens={u.completion_tokens}"
              + (f" (reasoning {reasoning})" if reasoning else ""))
    print(f"json mode accepted: {trader.json_mode}")
    if proposal.invalid_output:
        print(f"FAILED: no valid decision. {proposal.rationale[:400]}")
        return 1
    print(f"OK: {proposal.action.value} at confidence {proposal.confidence}")
    print(f"rationale: {proposal.rationale[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
