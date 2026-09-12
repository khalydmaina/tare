"""The AgentRouter backend, checked without the network.

AgentRouter bills per call and does not publish its response envelope, so the request it
receives and the shapes it may answer with are both pinned here rather than discovered in
production. The request contract comes from the route's own context endpoint, read
12 Sep 2026:

    required model, messages; optional max_tokens temperature stream top_p stop provider
    allowFallback optimizationPreferences; routeKey pins one provider route.
"""

from __future__ import annotations

import httpx
import pytest

from trader.agentrouter import (
    AgentRouterClient,
    AgentRouterError,
    _content_from,
    looks_like_agentrouter,
)
from trader.llm_trader import LLMTrader


def _client(**kwargs) -> AgentRouterClient:
    return AgentRouterClient(api_key="k", **kwargs)


def _capture(monkeypatch, response: httpx.Response) -> dict:
    """Answer the next POST with `response`, recording what was sent."""
    seen: dict = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            seen["url"] = url
            seen["payload"] = json
            seen["headers"] = headers
            return response

    monkeypatch.setattr(httpx, "Client", FakeClient)
    return seen


def _ok(body: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json=body,
        request=httpx.Request("POST", "https://api.agentrouter.to/x"),
    )


def test_the_request_matches_the_published_execute_contract(monkeypatch):
    seen = _capture(monkeypatch, _ok({"choices": [{"message": {"content": "hi"}}]}))
    c = _client(route_key="models.chat.complete.groq.mpp", provider="groq")

    out = c.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "q"}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    assert out.choices[0].message.content == "hi"
    assert seen["url"].endswith("/api/agentic-api/domains/models/capabilities/chat-complete/execute")
    assert seen["headers"]["Authorization"] == "Bearer k"
    payload = seen["payload"]
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["messages"] == [{"role": "user", "content": "q"}]
    assert payload["routeKey"] == "models.chat.complete.groq.mpp"
    assert payload["provider"] == "groq"
    assert payload["temperature"] == 0.2
    # Not in the accepted field list, and an unknown field is a 400 on a route that bills.
    assert "response_format" not in payload


def test_the_route_key_is_omitted_when_unset(monkeypatch):
    seen = _capture(monkeypatch, _ok({"choices": [{"message": {"content": "x"}}]}))
    _client().chat.completions.create(model="m", messages=[{"role": "user", "content": "q"}])
    assert "routeKey" not in seen["payload"]
    assert "provider" not in seen["payload"]


@pytest.mark.parametrize(
    "base",
    [
        "https://api.agentrouter.to/api/agentic-api",
        "https://api.agentrouter.to",
        "https://api.agentrouter.to/v1",
        "https://api.agentrouter.to/api/agentic-api/",
    ],
)
def test_any_reasonable_base_url_lands_on_the_capability_api(base):
    assert _client(base_url=base).base_url == "https://api.agentrouter.to/api/agentic-api"


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [{"message": {"content": "the reply"}}]},
        {"data": {"choices": [{"message": {"content": "the reply"}}]}},
        {"result": {"content": "the reply"}},
        {"success": True, "data": {"output_text": "the reply"}},
        {"response": "the reply"},
        {"choices": [{"text": "the reply"}]},
    ],
)
def test_the_reply_is_found_in_any_plausible_envelope(body):
    assert _content_from(body) == "the reply"


def test_an_unrecognised_envelope_raises_with_the_body_attached(monkeypatch):
    _capture(monkeypatch, _ok({"weird": {"nested": [1, 2, 3]}}))
    with pytest.raises(AgentRouterError) as err:
        _client().chat.completions.create(model="m", messages=[{"role": "user", "content": "q"}])
    # The body has to travel with the error: it is the only way to learn the real shape.
    assert "weird" in str(err.value)


def test_a_credit_failure_reads_as_one(monkeypatch):
    _capture(
        monkeypatch,
        _ok({"success": False, "error": "insufficient credits", "code": "CREDITS_REQUIRED"}, status=402),
    )
    with pytest.raises(AgentRouterError) as err:
        _client().chat.completions.create(model="m", messages=[{"role": "user", "content": "q"}])
    assert err.value.status == 402
    assert err.value.code == "CREDITS_REQUIRED"
    assert "insufficient credits" in str(err.value)


def test_a_success_false_body_is_not_treated_as_a_reply(monkeypatch):
    _capture(monkeypatch, _ok({"success": False, "error": "AgentRouter key is required",
                              "code": "AGENTIC_API_KEY_REQUIRED"}))
    with pytest.raises(AgentRouterError) as err:
        _client().chat.completions.create(model="m", messages=[{"role": "user", "content": "q"}])
    assert err.value.code == "AGENTIC_API_KEY_REQUIRED"


def test_the_trader_picks_the_backend_off_the_base_url(monkeypatch):
    assert looks_like_agentrouter("https://api.agentrouter.to/api/agentic-api")
    assert not looks_like_agentrouter("https://api.groq.com/openai/v1")

    monkeypatch.setenv("LLM_BASE_URL", "https://api.agentrouter.to/api/agentic-api")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("AGENTIC_API_KEY", "aak_test")
    monkeypatch.setenv("LLM_ROUTE_KEY", "models.chat.complete.groq.mpp")

    trader = LLMTrader()
    assert isinstance(trader._client, AgentRouterClient)
    assert trader._client.route_key == "models.chat.complete.groq.mpp"
    assert trader._client.api_key == "aak_test"
    # No response_format on this route, so the prompt has to ask plainly.
    assert trader.json_mode is False


def test_a_non_agentrouter_base_url_still_uses_the_openai_client(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_API_KEY", "gsk_test")
    monkeypatch.delenv("AGENTIC_API_KEY", raising=False)

    trader = LLMTrader()
    assert not isinstance(trader._client, AgentRouterClient)
    assert trader.json_mode is True
