"""OpenAI-compatible LLM Trader: take/skip + confidence proposals."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional, Sequence

from openai import OpenAI

from core.config import load_settings
from core.schemas import Action, Candle, Proposal, Setup, Side

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "trader_v1.txt"
_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _rr(side: Side, entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    if risk <= 0:
        return 0.0
    if side == Side.LONG:
        return (tp - entry) / risk
    return (entry - tp) / risk


def enforce_proposal_bounds(setup: Setup, raw: dict[str, Any]) -> dict[str, Any]:
    """
    May tighten SL / move TP closer; never widen SL; never flip side.
    Mutates a copy of raw fields and returns normalized dict.
    """
    side = setup.side
    action_raw = str(raw.get("action", "skip")).lower().strip()
    action = Action.TAKE if action_raw == "take" else Action.SKIP

    entry = float(setup.entry)
    sl = float(raw.get("sl", setup.sl))
    tp = float(raw.get("tp", setup.tp))

    # Never flip side - ignore model side if it disagrees
    model_side = str(raw.get("side", side.value)).lower().strip()
    if model_side not in (side.value,):
        # keep setup side
        pass

    if side == Side.LONG:
        # SL must stay below entry; may only rise toward entry (tighten)
        sl = min(sl, entry - 1e-12)
        sl = max(sl, float(setup.sl))  # cannot go below original SL (widen)
        # TP may only move closer (down toward entry) or stay
        tp = max(min(tp, float(setup.tp)), entry + 1e-12)
    else:
        sl = max(sl, entry + 1e-12)
        sl = min(sl, float(setup.sl))  # cannot go above original SL (widen)
        tp = min(max(tp, float(setup.tp)), entry - 1e-12)

    conf = int(raw.get("confidence", 0))
    conf = max(0, min(100, conf))
    rationale = str(raw.get("rationale", ""))[:400]

    return {
        "action": action,
        "side": side,
        "entry": entry,
        "sl": float(sl),
        "tp": float(tp),
        "confidence": conf,
        "rationale": rationale,
        "rr": _rr(side, entry, float(sl), float(tp)),
    }


def _candles_compact(candles: Sequence[Candle], limit: int = 30) -> list[list[float | str]]:
    rows: list[list[float | str]] = []
    for c in list(candles)[-limit:]:
        rows.append(
            [
                c.open_time.isoformat(),
                round(c.open, 6),
                round(c.high, 6),
                round(c.low, 6),
                round(c.close, 6),
                round(c.volume, 4),
            ]
        )
    return rows


def build_user_payload(
    setup: Setup,
    candles_by_tf: dict[str, Sequence[Candle]],
    sentiment_digest: str,
    indicators: dict[str, Any],
) -> str:
    payload = {
        "SETUP": {
            "symbol": setup.symbol,
            "side": setup.side.value,
            "entry": setup.entry,
            "sl": setup.sl,
            "tp": setup.tp,
            "rr": setup.rr,
            "structure_summary": setup.structure_summary,
            "setup_score": setup.setup_score,
            "bias": setup.bias,
            "zone_low": setup.zone_low,
            "zone_high": setup.zone_high,
            "atr": setup.atr,
        },
        "INDICATORS": indicators,
        "CANDLES": {
            tf: _candles_compact(cs) for tf, cs in sorted(candles_by_tf.items())
        },
        "SENTIMENT": sentiment_digest,
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


class LLMTrader:
    def __init__(
        self,
        settings: Optional[dict[str, Any]] = None,
        *,
        client: Optional[OpenAI] = None,
        prompt_path: Optional[Path] = None,
    ) -> None:
        self.settings = settings or load_settings()
        llm = self.settings.get("llm", {})
        self.base_url = llm.get("base_url", "https://api.x.ai/v1")
        self.model = llm.get("model", "grok-4.5")
        self.temperature = float(llm.get("temperature", 0.2))
        self.max_retries = int(llm.get("max_retries", 2))
        self.prompt_version = str(llm.get("prompt_version", "trader_v1"))
        key_env = str(llm.get("api_key_env", "XAI_API_KEY"))
        self.api_key = os.getenv(key_env, "") or os.getenv("XAI_API_KEY", "")
        path = prompt_path or PROMPT_PATH
        self.system_prompt = path.read_text(encoding="utf-8")
        self._client = client
        if self._client is None and self.api_key:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def propose_mock(
        self,
        setup: Setup,
        confidence: int = 70,
        action: str = "take",
    ) -> Proposal:
        """Offline deterministic proposal for tests - still applies SL rules."""
        raw = {
            "action": action,
            "side": setup.side.value,
            "entry": setup.entry,
            "sl": setup.sl,
            "tp": setup.tp,
            "confidence": int(confidence),
            "rationale": "mock proposal",
        }
        norm = enforce_proposal_bounds(setup, raw)
        return Proposal(
            action=norm["action"],
            side=norm["side"],
            entry=norm["entry"],
            sl=norm["sl"],
            tp=norm["tp"],
            confidence=norm["confidence"],
            rationale=norm["rationale"],
            rr=norm["rr"],
            prompt_version=self.prompt_version,
            raw_json=raw,
            latency_ms=0.0,
            invalid_output=False,
        )

    def propose(
        self,
        setup: Setup,
        candles_by_tf: dict[str, Sequence[Candle]],
        sentiment_digest: str,
        indicators: dict[str, Any],
    ) -> Proposal:
        """Call the LLM; retry on invalid JSON; enforce SL/TP bounds in code."""
        if self._client is None:
            # No API key - safe skip proposal for dry runs
            return Proposal(
                action=Action.SKIP,
                side=setup.side,
                entry=setup.entry,
                sl=setup.sl,
                tp=setup.tp,
                confidence=0,
                rationale="no_api_key",
                rr=setup.rr,
                prompt_version=self.prompt_version,
                raw_json=None,
                invalid_output=False,
            )

        user_msg = build_user_payload(
            setup, candles_by_tf, sentiment_digest, indicators
        )
        attempts = self.max_retries + 1
        last_err: Optional[str] = None
        t0 = time.perf_counter()
        raw: Optional[dict[str, Any]] = None

        for _ in range(attempts):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or ""
                raw = _extract_json(content)
                # Basic schema check before bounds
                if "action" not in raw or "confidence" not in raw:
                    raise ValueError("missing action/confidence")
                conf = int(raw["confidence"])
                if not 0 <= conf <= 100:
                    raise ValueError("confidence out of range")
                break
            except Exception as exc:  # noqa: BLE001 - retry then skip
                last_err = str(exc)
                raw = None

        latency_ms = (time.perf_counter() - t0) * 1000.0

        if raw is None:
            return Proposal(
                action=Action.SKIP,
                side=setup.side,
                entry=setup.entry,
                sl=setup.sl,
                tp=setup.tp,
                confidence=0,
                rationale=f"invalid_output: {last_err or 'unknown'}",
                rr=setup.rr,
                prompt_version=self.prompt_version,
                raw_json=None,
                latency_ms=latency_ms,
                invalid_output=True,
            )

        norm = enforce_proposal_bounds(setup, raw)
        # skip decisions are still logged as Proposal with action=skip
        return Proposal(
            action=norm["action"],
            side=norm["side"],
            entry=norm["entry"],
            sl=norm["sl"],
            tp=norm["tp"],
            confidence=norm["confidence"],
            rationale=norm["rationale"],
            rr=norm["rr"],
            prompt_version=self.prompt_version,
            raw_json=raw,
            latency_ms=latency_ms,
            invalid_output=False,
        )
