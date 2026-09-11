"""LLM client: provider from the environment, JSON-mode fallback, rate-limit retry."""

from __future__ import annotations

from types import SimpleNamespace

from core.config import load_settings
from core.schemas import Action, Setup, Side
from trader import llm_trader
from trader.llm_trader import LLMTrader

SETUP = Setup(symbol="BTCUSDT", side=Side.LONG, entry=100.0, sl=99.0, tp=102.0, rr=2.0,
              structure_summary="x", setup_score=0.6)
REPLY = '{"action": "take", "confidence": 72, "rationale": "clean sweep"}'


class ApiError(Exception):
    def __init__(self, status: int, message: str, headers: dict | None = None) -> None:
        super().__init__(message)
        self.status_code = status
        self.response = SimpleNamespace(headers=headers or {})


class FakeClient:
    """Raises the queued errors in order, then answers with REPLY."""

    def __init__(self, failures: list[Exception]) -> None:
        self.failures = list(failures)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.requests.append(request)
        if self.failures:
            raise self.failures.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=REPLY))])


def test_provider_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("LLM_API_KEY", "gsk_test")
    trader = LLMTrader(load_settings())
    assert (trader.base_url, trader.model, trader.api_key) == (
        "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", "gsk_test",
    )
    assert trader._client is not None


def test_falls_back_when_json_mode_is_rejected():
    client = FakeClient([ApiError(400, "response_format json_object is not supported")])
    proposal = LLMTrader(load_settings(), client=client).propose(SETUP, {}, "(no sentiment items)", {})
    assert proposal.action == Action.TAKE and proposal.confidence == 72
    assert "response_format" in client.requests[0] and "response_format" not in client.requests[1]


def test_waits_out_a_rate_limit(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(llm_trader.time, "sleep", waits.append)
    client = FakeClient([ApiError(429, "rate limited", {"retry-after": "7"})])
    proposal = LLMTrader(load_settings(), client=client).propose(SETUP, {}, "(no sentiment items)", {})
    assert waits == [7.0] and proposal.confidence == 72
