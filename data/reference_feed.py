"""Independent klines for the Inspector (Binance public by default)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from core.clock import tf_to_minutes
from core.schemas import Candle

TF_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}


class ReferenceFeed:
    """Second-venue public candles. Never used by the Trader."""

    def __init__(self, venue: str = "binance", timeout: float = 20.0) -> None:
        self.venue = venue.lower()
        self.timeout = timeout
        self.source = venue.lower()

    def fetch_klines(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if self.venue == "binance":
            return self._binance(symbol, timeframe, limit)
        if self.venue == "bybit":
            return self._bybit(symbol, timeframe, limit)
        raise ValueError(f"unsupported reference venue: {self.venue}")

    def _binance(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": TF_MAP[timeframe], "limit": limit}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            raw = r.json()
        return self._parse_binance(raw, symbol, timeframe)

    def _bybit(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        url = "https://api.bybit.com/v5/market/kline"
        interval = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}[timeframe]
        params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        rows = data.get("result", {}).get("list", [])
        # Bybit returns newest first
        rows = list(reversed(rows))
        fetched = datetime.now(timezone.utc)
        minutes = tf_to_minutes(timeframe)
        out: list[Candle] = []
        for row in rows:
            ts_ms = int(row[0])
            open_time = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            out.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=open_time + timedelta(minutes=minutes),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    source=self.source,
                    fetched_at=fetched,
                )
            )
        return out

    def _parse_binance(self, raw: Any, symbol: str, timeframe: str) -> list[Candle]:
        fetched = datetime.now(timezone.utc)
        minutes = tf_to_minutes(timeframe)
        out: list[Candle] = []
        for row in raw:
            open_time = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
            close_time = datetime.fromtimestamp(int(row[6]) / 1000, tz=timezone.utc)
            if close_time <= open_time:
                close_time = open_time + timedelta(minutes=minutes)
            out.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    source=self.source,
                    fetched_at=fetched,
                )
            )
        return out

    def max_close_deviation(
        self, trader: list[Candle], reference: list[Candle], lookback: int = 10
    ) -> float:
        """Max |trader_close - ref_close| / ref_close over last N aligned candles."""
        if not trader or not reference:
            return 0.0
        t = {c.open_time: c for c in trader[-lookback * 2 :]}
        r = {c.open_time: c for c in reference[-lookback * 2 :]}
        common = sorted(set(t) & set(r))[-lookback:]
        if not common:
            # align by index if timestamps differ slightly
            n = min(lookback, len(trader), len(reference))
            devs = []
            for i in range(1, n + 1):
                rc = reference[-i].close
                if rc == 0:
                    continue
                devs.append(abs(trader[-i].close - rc) / rc)
            return max(devs) if devs else 0.0
        devs = []
        for ts in common:
            rc = r[ts].close
            if rc == 0:
                continue
            devs.append(abs(t[ts].close - rc) / rc)
        return max(devs) if devs else 0.0
