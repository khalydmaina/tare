"""Independent klines for the Inspector: a second venue's USDT perpetual (OKX by default)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from core.clock import tf_to_minutes
from core.schemas import Candle

TF_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
# OKX hour bars are UTC+8 aligned; 1H and 4H boundaries still fall on the UTC ones
OKX_BAR = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1Dutc"}
OKX_BASE = "https://www.okx.com"
OKX_RECENT_MAX = 300  # bars per /market/candles request
OKX_HISTORY_MAX = 100  # bars per /market/history-candles request


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def okx_inst_id(symbol: str) -> str:
    """BTCUSDT → BTC-USDT-SWAP, the USDT-margined perpetual that matches Bitget's contract."""
    s = symbol.upper()
    if "-" in s:
        return s
    if s.endswith("USDT"):
        return f"{s[:-4]}-USDT-SWAP"
    raise ValueError(f"cannot map {symbol} to an OKX instrument")


class ReferenceFeed:
    """Second-venue public candles. Never used by the Trader."""

    def __init__(self, venue: str = "okx", timeout: float = 20.0, page_pause: float = 0.12) -> None:
        self.venue = venue.lower()
        self.timeout = timeout
        self.page_pause = page_pause
        self.source = venue.lower()

    def fetch_klines(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if self.venue == "okx":
            return self._okx(symbol, timeframe, limit)
        if self.venue == "binance":
            return self._binance(symbol, timeframe, limit)
        if self.venue == "bybit":
            return self._bybit(symbol, timeframe, limit)
        raise ValueError(f"unsupported reference venue: {self.venue}")

    def history(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]:
        """Every bar with start <= open_time < end, oldest first (scenario bank, basis check)."""
        if self.venue == "okx":
            return self._okx_history(symbol, timeframe, start, end)
        if self.venue == "binance":
            return self._binance_history(symbol, timeframe, start, end)
        raise ValueError(f"history download is not implemented for {self.venue}")

    # ------------------------------------------------------------------ OKX
    def _okx_get(self, path: str, params: dict[str, str]) -> list[list[str]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{OKX_BASE}{path}", params=params)
            r.raise_for_status()
            data = r.json()
        if str(data.get("code")) != "0":
            raise RuntimeError(f"OKX error {data.get('code')}: {data.get('msg')}")
        return list(data.get("data") or [])

    def _okx(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        inst, bar = okx_inst_id(symbol), OKX_BAR[timeframe]
        rows = self._okx_get(
            "/api/v5/market/candles",
            {"instId": inst, "bar": bar, "limit": str(min(limit, OKX_RECENT_MAX))},
        )
        # Rows come newest first; page further back when more bars are wanted than one call returns
        while rows and len(rows) < limit:
            older = self._okx_get(
                "/api/v5/market/history-candles",
                {
                    "instId": inst,
                    "bar": bar,
                    "after": str(rows[-1][0]),
                    "limit": str(min(OKX_HISTORY_MAX, limit - len(rows))),
                },
            )
            if not older:
                break
            rows.extend(older)
            time.sleep(self.page_pause)
        return self._parse_okx(rows[:limit], symbol, timeframe)

    def _okx_history(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]:
        inst, bar = okx_inst_id(symbol), OKX_BAR[timeframe]
        rows: list[list[str]] = []
        cursor, start_ms = _ms(end), _ms(start)
        while cursor > start_ms:
            batch = self._okx_get(
                "/api/v5/market/history-candles",
                {"instId": inst, "bar": bar, "after": str(cursor), "limit": str(OKX_HISTORY_MAX)},
            )
            if not batch:
                break
            rows.extend(batch)
            oldest = min(int(r[0]) for r in batch)
            if oldest >= cursor:
                break  # no progress; stop instead of looping forever
            cursor = oldest
            time.sleep(self.page_pause)
        return [c for c in self._parse_okx(rows, symbol, timeframe) if start <= c.open_time < end]

    def _parse_okx(self, rows: list[list[str]], symbol: str, timeframe: str) -> list[Candle]:
        """[ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm], newest first → Candles oldest first."""
        fetched = datetime.now(timezone.utc)
        minutes = tf_to_minutes(timeframe)
        by_open: dict[datetime, Candle] = {}
        for row in rows:
            open_time = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
            by_open[open_time] = Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=open_time,
                close_time=open_time + timedelta(minutes=minutes),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[6] if len(row) > 6 else row[5]),  # base-currency volume
                source=self.source,
                fetched_at=fetched,
            )
        return [by_open[t] for t in sorted(by_open)]

    # -------------------------------------------------------------- Binance
    def _binance(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": TF_MAP[timeframe], "limit": limit}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            raw = r.json()
        return self._parse_binance(raw, symbol, timeframe)

    def _binance_history(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]:
        out: dict[datetime, Candle] = {}
        cursor = start
        with httpx.Client(timeout=self.timeout) as client:
            while cursor < end:
                r = client.get("https://fapi.binance.com/fapi/v1/klines", params={
                    "symbol": symbol, "interval": TF_MAP[timeframe], "startTime": _ms(cursor),
                    "endTime": _ms(end), "limit": 1500,
                })
                r.raise_for_status()
                batch = self._parse_binance(r.json(), symbol, timeframe)
                if not batch:
                    break
                for c in batch:
                    out[c.open_time] = c
                cursor = max(c.open_time for c in batch) + timedelta(minutes=tf_to_minutes(timeframe))
                time.sleep(self.page_pause)
        return sorted(out.values(), key=lambda c: c.open_time)

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

    # ---------------------------------------------------------------- Bybit
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
