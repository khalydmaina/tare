"""OKX reference feed: symbol mapping, parsing, and paging past OKX's per-request limits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from data.reference_feed import ReferenceFeed, okx_inst_id

END = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
STEP = timedelta(minutes=15)


def _row(open_time: datetime, price: float = 100.0) -> list[str]:
    ts = str(int(open_time.timestamp() * 1000))
    return [ts, str(price), str(price + 1), str(price - 1), str(price + 0.5), "10", "1.5", "150", "1"]


class FakeOkx(ReferenceFeed):
    """Serves consecutive 15m bars ending at END the way OKX pages them: newest first."""

    def __init__(self, n_bars: int) -> None:
        super().__init__("okx", page_pause=0)
        self.bars = [END - STEP * k for k in range(1, n_bars + 1)]
        self.calls: list[str] = []

    def _okx_get(self, path, params):
        self.calls.append(path.rsplit("/", 1)[-1])
        limit = int(params["limit"])
        if path.endswith("/candles"):
            return [_row(t) for t in self.bars[:limit]]
        after = datetime.fromtimestamp(int(params["after"]) / 1000, tz=timezone.utc)
        return [_row(t) for t in self.bars if t < after][:limit]


def test_symbols_map_to_usdt_perpetuals():
    assert okx_inst_id("BTCUSDT") == "BTC-USDT-SWAP"
    assert okx_inst_id("solusdt") == "SOL-USDT-SWAP"
    assert okx_inst_id("ETH-USDT-SWAP") == "ETH-USDT-SWAP"
    with pytest.raises(ValueError):
        okx_inst_id("BTCUSD")


def test_parse_orders_oldest_first_with_base_volume():
    candles = ReferenceFeed("okx")._parse_okx(
        [_row(END - STEP), _row(END - 2 * STEP, 90.0)], "BTCUSDT", "15m"
    )
    assert [c.open_time for c in candles] == [END - 2 * STEP, END - STEP]
    assert candles[0].close == 90.5 and candles[0].volume == 1.5
    assert candles[1].close_time == END and candles[1].source == "okx"


def test_fetch_pages_back_past_the_300_bar_limit():
    feed = FakeOkx(n_bars=1000)
    candles = feed.fetch_klines("BTCUSDT", "15m", limit=450)
    assert len(candles) == 450
    assert all(b.open_time - a.open_time == STEP for a, b in zip(candles, candles[1:]))
    assert candles[-1].open_time == END - STEP
    assert feed.calls == ["candles", "history-candles", "history-candles"]


def test_history_returns_exactly_the_window():
    feed = FakeOkx(n_bars=2000)
    start = END - timedelta(days=3)
    candles = feed.history("BTCUSDT", "15m", start, END)
    assert len(candles) == 3 * 96
    assert candles[0].open_time == start and candles[-1].open_time == END - STEP
    assert len({c.open_time for c in candles}) == len(candles)
