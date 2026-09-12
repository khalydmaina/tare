#!/usr/bin/env python3
"""Check an AgentRouter key end to end, and print the response shape it answers with.

AgentRouter does not publish its response envelope (the capability contract returns
``responseExample: null``), so trader/agentrouter.py accepts several plausible shapes.
This makes one real call and says which one came back, so the adapter can be narrowed
to the truth instead of guessing.

Reads AGENTIC_API_KEY from the environment and never prints it.

    python scripts/check_agentrouter.py                      # account only, no spend
    python scripts/check_agentrouter.py --call               # one cheap chat call
    python scripts/check_agentrouter.py --call --model llama-3.1-8b-instant
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from trader.agentrouter import AgentRouterClient, AgentRouterError, _content_from  # noqa: E402

BASE = "https://api.agentrouter.to/api/agentic-api"


def show(label: str, url: str, key: str) -> dict | None:
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=30)
    except Exception as exc:
        print(f"{label}: could not reach it ({type(exc).__name__}: {str(exc)[:150]})")
        return None
    body: dict | None
    try:
        body = r.json()
    except Exception:
        body = None
    if r.is_success:
        print(f"{label}: OK ({r.status_code}) {json.dumps(body)[:300] if body else r.text[:200]}")
        return body
    hint = ""
    if isinstance(body, dict):
        hint = f" {body.get('code') or ''} {body.get('error') or body.get('message') or ''}".rstrip()
        if body.get("hint"):
            hint += f" | hint: {body['hint']}"
    print(f"{label}: FAILED ({r.status_code}){hint}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Check an AgentRouter key")
    ap.add_argument("--call", action="store_true", help="make one real chat call (spends credits)")
    ap.add_argument("--model", default="llama-3.1-8b-instant", help="model for the test call")
    ap.add_argument("--route-key", default="models.chat.complete.groq.mpp")
    args = ap.parse_args()

    key = os.getenv("AGENTIC_API_KEY", "")
    if not key:
        print("AGENTIC_API_KEY is not set. Run it inline so the key stays out of your history:")
        print("  AGENTIC_API_KEY=your_key python scripts/check_agentrouter.py")
        return 1
    print(f"key present, {len(key)} characters, starts {key[:4]}...")

    # 1. Does the key authenticate at all? These need it; /domains does not.
    ok = show("usage ", f"{BASE}/usage", key) is not None
    show("wallet", f"{BASE}/wallet", key)
    if not ok:
        print("\nThe key did not authenticate. AgentRouter's own hint is to sign in and "
              "enable AgentRouter for the account before the key works.")
        return 1

    if not args.call:
        print("\nKey works. Re-run with --call to make one real chat call (it spends credits) "
              "and learn the response shape.")
        return 0

    # 2. One real call through the same client the Trader uses.
    client = AgentRouterClient(api_key=key, base_url=BASE, route_key=args.route_key)
    print(f"\ncalling {args.model} on {args.route_key} ...")
    try:
        out = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=16,
            temperature=0,
        )
    except AgentRouterError as exc:
        print(f"the call failed: {exc}")
        print("\nIf that names credits or a payment challenge, the account needs funding. "
              "If it says the reply could not be found, paste the body above: it is the "
              "envelope trader/agentrouter.py needs to match.")
        return 1

    print(f"reply: {out.choices[0].message.content!r}")
    envelope = out.raw if isinstance(out.raw, dict) else {}
    print(f"top-level response keys: {sorted(envelope)}")
    print(f"reply found at: {'choices[0].message.content' if 'choices' in envelope else 'a nested envelope'}")
    assert _content_from(envelope) == out.choices[0].message.content
    print("\nThe adapter reads this shape. Set these to point the Trader at it:")
    print(f"  LLM_BASE_URL={BASE}")
    print(f"  LLM_MODEL={args.model}")
    print(f"  LLM_ROUTE_KEY={args.route_key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
