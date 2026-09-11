"""Bitget public/private market + account feed for the Trader."""

from __future__ import annotations

import hashlib
import hmac
import base64
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from core.clock import is_stale, tf_to_minutes
from core.schemas import AccountState, Candle

TF_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}


class BitgetFeed:
    """Fetches klines and account state. Paper/demo keys via env."""

    BASE = "https://api.bitget.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        paper: bool = True,
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key or os.getenv("BITGET_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BITGET_API_SECRET", "")
        self.passphrase = passphrase or os.getenv("BITGET_PASSPHRASE", "")
        self.paper = paper
        self.timeout = timeout
        self.source = "bitget"

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        prehash = f"{ts}{method.upper()}{path}{body}"
        sign = base64.b64encode(
            hmac.new(self.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
        ).decode()
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": "en-US",
        }

    def _get(self, path: str, params: Optional[dict] = None, auth: bool = False) -> Any:
        url = f"{self.BASE}{path}"
        q = ""
        if params:
            q = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        headers = self._headers("GET", path + q) if auth else {}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        if isinstance(data, dict) and data.get("code") not in (None, "00000"):
            raise RuntimeError(f"Bitget error: {data}")
        return data.get("data", data) if isinstance(data, dict) else data

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        product_type: str = "USDT-FUTURES",
    ) -> list[Candle]:
        """Public candles. Symbol like BTCUSDT → BTCUSDT on mix market."""
        bg_symbol = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
        # Bitget V2 mix market candles
        path = "/api/v2/mix/market/candles"
        params = {
            "symbol": bg_symbol,
            "productType": product_type,
            "granularity": TF_MAP.get(timeframe, timeframe),
            "limit": str(limit),
        }
        try:
            raw = self._get(path, params=params, auth=False)
        except Exception:
            # Fallback: spot-style endpoint for public demo without product type quirks
            path = "/api/v2/spot/market/candles"
            params = {
                "symbol": bg_symbol,
                "granularity": TF_MAP.get(timeframe, timeframe),
                "limit": str(limit),
            }
            raw = self._get(path, params=params, auth=False)

        candles = self._parse_candles(raw, bg_symbol, timeframe)
        return candles

    def _parse_candles(self, raw: Any, symbol: str, timeframe: str) -> list[Candle]:
        rows = raw if isinstance(raw, list) else []
        out: list[Candle] = []
        fetched = datetime.now(timezone.utc)
        minutes = tf_to_minutes(timeframe)
        for row in rows:
            # Bitget: [ts, open, high, low, close, volume, quoteVolume] or dict
            if isinstance(row, dict):
                ts_ms = int(row.get("ts") or row.get("timestamp"))
                o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
                vol = float(row.get("baseVol") or row.get("volume") or 0)
            else:
                ts_ms = int(row[0])
                o, h, l, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
                vol = float(row[5]) if len(row) > 5 else 0.0
            open_time = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            close_time = open_time.replace(microsecond=0)
            # close_time is end of bar
            from datetime import timedelta

            close_time = open_time + timedelta(minutes=minutes)
            out.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=vol,
                    source=self.source,
                    fetched_at=fetched,
                )
            )
        out.sort(key=lambda x: x.open_time)
        return out

    def reject_stale(self, candles: list[Candle], tf: str, max_intervals: int = 2) -> list[Candle]:
        now = datetime.now(timezone.utc)
        return [c for c in candles if not is_stale(c.close_time, now, tf, max_intervals)]

    def fetch_account(self, fallback_equity: float = 10_000.0) -> AccountState:
        """Authenticated account. Falls back to synthetic paper equity if no keys."""
        if not self.api_key or not self.api_secret:
            return AccountState(
                equity=fallback_equity,
                available=fallback_equity,
                peak_equity=fallback_equity,
                day_start_equity=fallback_equity,
            )
        try:
            path = "/api/v2/mix/account/accounts"
            data = self._get(path, params={"productType": "USDT-FUTURES"}, auth=True)
            equity = fallback_equity
            if isinstance(data, list) and data:
                equity = float(data[0].get("accountEquity") or data[0].get("usdtEquity") or fallback_equity)
            elif isinstance(data, dict):
                equity = float(data.get("accountEquity") or data.get("usdtEquity") or fallback_equity)
            return AccountState(
                equity=equity,
                available=equity,
                peak_equity=equity,
                day_start_equity=equity,
            )
        except Exception:
            return AccountState(
                equity=fallback_equity,
                available=fallback_equity,
                peak_equity=fallback_equity,
                day_start_equity=fallback_equity,
            )
