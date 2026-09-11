"""Live loop: trades close, outcomes and calibration are recorded, and the bot keeps trading."""

from __future__ import annotations

import sqlite3
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import load_limits, load_settings  # noqa: E402
from core.schemas import Candle, Setup, Side  # noqa: E402
from execution.bitget_broker import PaperBroker  # noqa: E402
from execution.shadow_book import ShadowBook  # noqa: E402
from inspector.calibration import CalibrationMatrix  # noqa: E402
from recorder.db import FlightRecorder  # noqa: E402
from scripts import run_live  # noqa: E402
from trader.llm_trader import LLMTrader  # noqa: E402

SYMBOL = "BTCUSDT"
TF_NAME = {15: "15m", 60: "1h", 240: "4h"}


def _floor(ts: datetime, minutes: int) -> datetime:
    epoch = int(ts.timestamp())
    return datetime.fromtimestamp(epoch - epoch % (minutes * 60), tz=timezone.utc)


def _bars(minutes: int, n: int, last_open: datetime, price: float = 100.0,
          source: str = "bitget") -> list[Candle]:
    out = []
    for k in range(n):
        ot = last_open - timedelta(minutes=minutes * (n - 1 - k))
        out.append(Candle(
            symbol=SYMBOL, timeframe=TF_NAME[minutes], open_time=ot,
            close_time=ot + timedelta(minutes=minutes), open=price, high=price * 1.001,
            low=price * 0.999, close=price, volume=100.0, source=source, fetched_at=ot,
        ))
    return out


class StubFeed:
    def __init__(self) -> None:
        self.series: dict[str, list[Candle]] = {}

    def fetch_klines(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        return list(self.series[timeframe])[-limit:]


def _load_feeds(ns, last_open: datetime, tp_bar: datetime | None = None,
                price_now: float = 100.0) -> None:
    """15m bars up to a still-forming bar at `last_open`; optionally one bar that tags TP."""
    c15 = _bars(15, 201, last_open)
    for c in c15:
        if c.open_time == tp_bar:
            c.high, c.low, c.close = 102.5, 100.0, 101.0
    c15[-1].close = price_now
    ns.trader_feed.series = {
        "15m": c15,
        "1h": _bars(60, run_live.REGIME_1H_BARS, _floor(last_open, 60)),
        "4h": _bars(240, 200, _floor(last_open, 240)),
    }
    ns.ref_feed.series = {"15m": _bars(15, 201, last_open, source="binance")}


def _cycle(ns, now: datetime) -> dict[str, int]:
    return run_live.run_cycle(
        ns.cfg, ns.rec, ns.trader, ns.cal, ns.trader_feed, ns.ref_feed, ns.sentiment,
        ns.broker, ns.shadow, "G1", mock_llm=True, now=now,
    )


@pytest.fixture
def live(tmp_path, monkeypatch):
    settings = deepcopy(load_settings())
    settings["market"]["symbols"] = [SYMBOL]
    settings["llm"]["ablation_probe"] = False

    # An edge in the buckets the simulated trader lands in (it states ~78-86 here)
    cal = CalibrationMatrix.from_settings(settings)
    for regime in cal.regimes:
        for conf in (75, 85):
            for i in range(35):
                cal.update(conf, regime, won=i < 30)

    setup = Setup(symbol=SYMBOL, side=Side.LONG, entry=100.0, sl=99.0, tp=102.0, rr=2.0,
                  structure_summary="test sweep", setup_score=0.9)
    seen: list[Candle] = []

    def fake_candidates(c15, c1h, c4h, symbol, cfg):
        seen.append(c15[-1])
        return [setup]

    monkeypatch.setattr(run_live, "find_candidates", fake_candidates)
    return SimpleNamespace(
        cfg=SimpleNamespace(settings=settings, limits=load_limits(), limits_hash="test"),
        cal=cal,
        seen=seen,
        t0=_floor(datetime.now(timezone.utc), 15),
        trader_feed=StubFeed(),
        ref_feed=StubFeed(),
        rec=FlightRecorder(tmp_path / "live.db"),
        trader=LLMTrader(settings),
        broker=PaperBroker(api_key="", api_secret="", passphrase="", starting_equity=10_000.0),
        shadow=ShadowBook(starting_equity=10_000.0),
        sentiment=SimpleNamespace(fetch=lambda symbols: []),
    )


def test_trades_close_record_outcomes_and_keep_trading(live):
    ns = live
    _load_feeds(ns, last_open=ns.t0)
    first = _cycle(ns, ns.t0 + timedelta(seconds=1))
    assert first["takes"] == 1 and first["orders"] == 1
    assert len(ns.broker.account.positions) == 1 and len(ns.shadow.open_positions) == 1
    assert ns.seen[-1].close_time <= ns.t0 + timedelta(seconds=1)  # forming bar never reaches SMC
    assert ns.rec.fetch_outcomes() == []
    # The dashboard's decision log query (it used to select a column that does not exist)
    assert ns.rec.fetch_recent_decisions(5)[0]["symbol"] == SYMBOL

    cal_n = sum(c.n for c in ns.cal.cells.values())
    _load_feeds(ns, last_open=ns.t0 + timedelta(minutes=30), tp_bar=ns.t0, price_now=101.0)
    second = _cycle(ns, ns.t0 + timedelta(minutes=30, seconds=1))

    assert second["closed_guarded"] == 1 and second["closed_shadow"] == 1
    real, shadow = ns.rec.fetch_outcomes("real"), ns.rec.fetch_outcomes("shadow")
    assert [o["result"] for o in real] == ["win"] and [o["result"] for o in shadow] == ["win"]
    with sqlite3.connect(ns.rec.db_path) as conn:
        first_order_id = conn.execute("SELECT MIN(id) FROM orders").fetchone()[0]
    assert real[0]["ref_id"] == first_order_id
    assert ns.broker.account.equity > 10_000.0
    assert sum(c.n for c in ns.cal.cells.values()) == cal_n + 1
    # The old loop never closed anything, so max_per_symbol blocked every later take
    assert second["orders"] == 1 and len(ns.broker.account.positions) == 1


def test_take_not_entered_when_price_is_already_past_the_levels(live):
    ns = live
    _load_feeds(ns, last_open=ns.t0, price_now=98.5)  # below the long's SL
    stats = _cycle(ns, ns.t0 + timedelta(seconds=1))
    assert stats["takes"] == 1 and stats["orders"] == 0
    assert not ns.broker.account.positions and not ns.shadow.open_positions


def test_state_survives_a_restart(live, tmp_path):
    ns = live
    _load_feeds(ns, last_open=ns.t0)
    _cycle(ns, ns.t0 + timedelta(seconds=1))
    path = tmp_path / "state.json"
    run_live.save_state(path, ns.broker, ns.shadow)

    account, shadow = run_live.load_state(path, 10_000.0)
    (pos,) = account.positions.values()
    (spos,) = shadow.open_positions.values()
    assert pos.meta["db_id"] and (pos.sl, pos.tp) == (99.0, 102.0)
    assert spos.meta["confidence"] >= 60 and spos.meta["regime"] in ("low", "mid", "high")
    assert account.equity == pytest.approx(ns.broker.account.equity)
    assert shadow.equity == pytest.approx(ns.shadow.equity)


def test_refuses_to_run_without_an_llm_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_live.py", "--once"])
    with pytest.raises(SystemExit) as exc:
        run_live.main()
    assert "--mock-llm" in str(exc.value)


def test_a_dead_feed_is_counted_not_faked(live):
    ns = live

    class DeadFeed:
        def fetch_klines(self, *args, **kwargs):
            raise ConnectionError("handshake timed out")

    ns.trader_feed = DeadFeed()
    stats = _cycle(ns, ns.t0 + timedelta(seconds=1))
    assert stats["feeds_failed"] == 1 and stats["setups"] == 0
    assert not ns.seen  # SMC never ran on anything
    assert ns.rec.fetch_equity("guarded")  # the cycle still marks equity


def test_the_same_closed_bar_is_never_traded_twice(live, tmp_path):
    """GitHub's timer can fire twice inside one 15m bar; the second run must not re-enter."""
    ns = live
    _load_feeds(ns, last_open=ns.t0)
    processed: dict[str, str] = {}

    def run(now):
        return run_live.run_cycle(
            ns.cfg, ns.rec, ns.trader, ns.cal, ns.trader_feed, ns.ref_feed, ns.sentiment,
            ns.broker, ns.shadow, "G1", mock_llm=True, now=now, processed_bars=processed,
        )

    first = run(ns.t0 + timedelta(seconds=1))
    again = run(ns.t0 + timedelta(minutes=10))  # still inside the same bar
    assert first["orders"] == 1
    assert again["already_processed"] == 1 and again["setups"] == 0 and again["orders"] == 0

    path = tmp_path / "state.json"
    run_live.save_state(path, ns.broker, ns.shadow, processed)
    assert run_live.load_processed_bars(path) == processed
