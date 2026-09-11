"""Sentiment digest: headlines/posts normalizer with pluggable sources."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from core.schemas import SentimentItem


class SentimentFeed:
    """
    Collects recent sentiment items.

    Priority:
    1. Local JSONL / mock injector (for attacks & tests)
    2. Optional CryptoPanic public API if CRYPTOPANIC_TOKEN is set
    3. Empty list (Trader still runs on structure alone)
    """

    def __init__(self, lookback_hours: int = 6, injected: Optional[list[SentimentItem]] = None) -> None:
        self.lookback_hours = lookback_hours
        self._injected: list[SentimentItem] = list(injected or [])
        self.token = os.getenv("CRYPTOPANIC_TOKEN", "")

    def inject(self, items: list[SentimentItem]) -> None:
        """Used by attack suite to tamper with Trader-visible sentiment only."""
        self._injected.extend(items)

    def clear_injected(self) -> None:
        self._injected.clear()

    def fetch(self, symbols: Optional[list[str]] = None) -> list[SentimentItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        items: list[SentimentItem] = [i for i in self._injected if i.published_at >= cutoff]
        if self.token:
            try:
                items.extend(self._cryptopanic(symbols or ["BTC", "ETH", "SOL"], cutoff))
            except Exception:
                pass
        # newest first
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items

    def _cryptopanic(self, symbols: list[str], cutoff: datetime) -> list[SentimentItem]:
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": self.token,
            "currencies": ",".join(s.replace("USDT", "") for s in symbols),
            "public": "true",
        }
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        out: list[SentimentItem] = []
        for post in data.get("results", []):
            published = post.get("published_at") or post.get("created_at")
            if not published:
                continue
            ts = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if ts < cutoff:
                continue
            title = post.get("title") or ""
            source = (post.get("source") or {}).get("title") or "cryptopanic"
            votes = post.get("votes") or {}
            pos = float(votes.get("positive") or 0)
            neg = float(votes.get("negative") or 0)
            score = 0.0
            if pos + neg > 0:
                score = (pos - neg) / (pos + neg)
            out.append(
                SentimentItem(
                    source=source,
                    text=title,
                    published_at=ts,
                    score=score,
                    url=post.get("url"),
                )
            )
        return out

    @staticmethod
    def digest(items: list[SentimentItem], max_items: int = 12) -> str:
        lines = []
        for it in items[:max_items]:
            lines.append(f"[{it.source}] ({it.score:+.2f}) {it.text[:180]}")
        return "\n".join(lines) if lines else "(no sentiment items)"

    @staticmethod
    def aggregate_score(items: list[SentimentItem]) -> float:
        if not items:
            return 0.0
        return sum(i.score for i in items) / len(items)
