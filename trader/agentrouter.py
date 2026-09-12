"""AgentRouter backend for the Trader, shaped like the OpenAI client it replaces.

AgentRouter (agentrouter.to) is not an OpenAI-compatible endpoint: there is no
``/v1/chat/completions``, and inference is one capability among many behind a single
execute route that takes an OpenAI-shaped message list plus a ``routeKey`` naming the
provider. Pointing ``LLM_BASE_URL`` at it would 404 on every call.

So this exposes exactly the one call the Trader makes,
``client.chat.completions.create(...)`` returning ``.choices[0].message.content``, and
translates it. Everything else in the Trader, including the retry loop, the JSON
extraction and the proposal cache, stays as it is.

Request contract, read from the route's own context endpoint on 12 Sep 2026:

    POST {base}/domains/models/capabilities/chat-complete/execute
    {"model": ..., "messages": [...], "routeKey": ..., "provider": ..., "allowFallback": ...}

required: model, messages. optional: max_tokens, temperature, stream, top_p, stop,
provider, allowFallback, optimizationPreferences. ``routeKey`` pins one provider route;
omitting it lets AgentRouter choose from its own recommendations.

The response envelope is the one thing AgentRouter does not publish (the capability
contract says ``responseExample: null``), so ``_content_from`` accepts the shapes it
could reasonably be and, failing that, raises with the body attached rather than
guessing, so the first real call says what the shape is.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Sequence

import httpx

logger = logging.getLogger(__name__)

EXECUTE_PATH = "/domains/models/capabilities/chat-complete/execute"

# Fields the execute route accepts. Anything else (response_format, for one) is dropped
# rather than sent, because an unknown field is a 400 on a route that bills per call.
PASSTHROUGH = ("max_tokens", "temperature", "stream", "top_p", "stop")


class AgentRouterError(RuntimeError):
    """A failed AgentRouter call, carrying the reason AgentRouter gave."""

    def __init__(self, message: str, *, status: Optional[int] = None, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class _Message:
    __slots__ = ("content", "role")

    def __init__(self, content: str, role: str = "assistant") -> None:
        self.content = content
        self.role = role


class _Choice:
    __slots__ = ("message", "finish_reason", "index")

    def __init__(self, content: str, finish_reason: Optional[str] = None, index: int = 0) -> None:
        self.message = _Message(content)
        self.finish_reason = finish_reason
        self.index = index


class _Completion:
    """The subset of a chat completion the Trader reads."""

    __slots__ = ("choices", "model", "raw")

    def __init__(self, content: str, model: str, raw: Any) -> None:
        self.choices = [_Choice(content)]
        self.model = model
        self.raw = raw


def _first_str(node: Any, keys: Sequence[str]) -> Optional[str]:
    if not isinstance(node, dict):
        return None
    for k in keys:
        v = node.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _content_from(body: Any, depth: int = 0) -> Optional[str]:
    """Pull the assistant's text out of whatever AgentRouter wraps it in.

    Handles a raw OpenAI completion, one nested under a data/result/response/output
    envelope, and a bare content/text field. Bounded recursion so a surprising shape
    cannot spin.
    """
    if depth > 4 or not isinstance(body, dict):
        return None

    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            content = _first_str(msg, ("content",)) if isinstance(msg, dict) else None
            return content or _first_str(first, ("text", "content"))

    direct = _first_str(body, ("content", "text", "completion", "output_text"))
    if direct:
        return direct

    for key in ("data", "result", "response", "output", "completion", "payload"):
        nested = body.get(key)
        if isinstance(nested, dict):
            found = _content_from(nested, depth + 1)
            if found:
                return found
        elif isinstance(nested, str) and nested.strip():
            return nested
    return None


class _Completions:
    def __init__(self, client: "AgentRouterClient") -> None:
        self._client = client

    def create(self, **kwargs: Any) -> _Completion:
        return self._client._execute(**kwargs)


class _Chat:
    def __init__(self, client: "AgentRouterClient") -> None:
        self.completions = _Completions(client)


class AgentRouterClient:
    """Minimal stand-in for ``OpenAI`` covering ``chat.completions.create``."""

    DEFAULT_BASE = "https://api.agentrouter.to/api/agentic-api"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        route_key: str = "",
        provider: str = "",
        allow_fallback: bool = True,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE).rstrip("/")
        # The base URL is usually given as the site root or the /v1 path people expect,
        # so normalise it onto the capability API rather than 404 on the first call.
        if not self.base_url.endswith("/api/agentic-api"):
            root = self.base_url.split("/api/agentic-api")[0].rstrip("/")
            for suffix in ("/v1", "/api"):
                if root.endswith(suffix):
                    root = root[: -len(suffix)]
            self.base_url = f"{root}/api/agentic-api"
        self.route_key = route_key
        self.provider = provider
        self.allow_fallback = allow_fallback
        self.timeout = timeout
        self.chat = _Chat(self)

    def _execute(self, **kwargs: Any) -> _Completion:
        model = kwargs.get("model")
        messages = kwargs.get("messages")
        if not model or not messages:
            raise AgentRouterError("model and messages are required")

        payload: dict[str, Any] = {"model": model, "messages": list(messages)}
        for field in PASSTHROUGH:
            if kwargs.get(field) is not None:
                payload[field] = kwargs[field]
        if self.route_key:
            payload["routeKey"] = self.route_key
        if self.provider:
            payload["provider"] = self.provider
        payload["allowFallback"] = self.allow_fallback

        url = f"{self.base_url}{EXECUTE_PATH}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json=payload, headers=headers)
        body: Any
        try:
            body = r.json()
        except Exception:
            body = {"_text": r.text[:400]}

        if not r.is_success:
            code = str(body.get("code") or "") if isinstance(body, dict) else ""
            # Routes are quoted and charged per call, so a funding failure has to read as
            # one rather than as a dead key.
            raise AgentRouterError(
                f"HTTP {r.status_code} from {EXECUTE_PATH}: {json.dumps(body)[:400]}",
                status=r.status_code,
                code=code,
            )
        if isinstance(body, dict) and body.get("success") is False:
            raise AgentRouterError(
                f"AgentRouter refused the call: {json.dumps(body)[:400]}",
                status=r.status_code,
                code=str(body.get("code") or ""),
            )

        content = _content_from(body)
        if content is None:
            raise AgentRouterError(
                "could not find the reply in AgentRouter's response; its capability "
                f"contract does not publish one. Body was: {json.dumps(body)[:600]}",
                status=r.status_code,
            )
        return _Completion(content, str(model), body)


def looks_like_agentrouter(base_url: str) -> bool:
    return "agentrouter" in (base_url or "").lower()
