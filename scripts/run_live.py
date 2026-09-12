#!/usr/bin/env python3
"""Live paper loop. Every 15m candle close:

1. close guarded and shadow positions that hit TP, SL or the timeout; record the outcomes
2. feed every shadow outcome (each Trader take, approved or vetoed) into the calibration matrix
3. closed candles → SMC → LLM → Inspector → broker + shadow (each closed bar at most once)
4. save broker, shadow, behaviour and calibration state so a restart resumes where it stopped

--mock-llm and --offline are plumbing modes. They write to data/mock/ and never touch the
real Flight Recorder or calibration matrix.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.clock import closed_candles  # noqa: E402
from core.config import ConfigBundle, db_path  # noqa: E402
from core.schemas import Action, Candle, DecisionKind, GateContext, OutcomeResult, Proposal  # noqa: E402
from data.bitget_feed import BitgetFeed  # noqa: E402
from data.reference_feed import ReferenceFeed  # noqa: E402
from data.sentiment_feed import SentimentFeed  # noqa: E402
from execution.bitget_broker import PaperBroker, PaperModeAccount  # noqa: E402
from execution.labeler import resolve  # noqa: E402
from execution.shadow_book import ShadowBook  # noqa: E402
from inspector.behavior import BehaviorState  # noqa: E402
from inspector.calibration import CalibrationMatrix, bucket_label  # noqa: E402
from inspector.gate import decide  # noqa: E402
from inspector.regime import LOOKBACK_BARS, atr_pct_series, regime_from_history  # noqa: E402
from recorder.db import FlightRecorder  # noqa: E402
from trader.candidates import find_candidates  # noqa: E402
from trader.llm_trader import LLMTrader  # noqa: E402
from trader.sim_trader import SimTrader  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tare.live")

NO_SENTIMENT = "(no sentiment items)"
REGIME_1H_BARS = LOOKBACK_BARS + 20  # 30 days of 1h bars for the ATR% tercile
FETCH_WORKERS = 4  # 22 coins x 4 calls at once trips Bitget's per-address rate limit
FETCH_ATTEMPTS = 2


def _synth_klines(symbol: str, timeframe: str, limit: int, start: float = 100.0) -> list[Candle]:
    minutes = {"15m": 15, "1h": 60, "4h": 240}.get(timeframe, 15)
    out = []
    t0 = datetime.now(timezone.utc) - timedelta(minutes=minutes * limit)
    px = start
    for i in range(limit):
        o = px
        c = px * (1.0005 if i % 5 else 0.9996)
        h, l = max(o, c) * 1.001, min(o, c) * 0.999
        ot = t0 + timedelta(minutes=minutes * i)
        out.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=ot,
                close_time=ot + timedelta(minutes=minutes),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1000 + i,
                source="synth",
            )
        )
        px = c
    return out


def settings_probe(cfg: Any) -> bool:
    return bool((cfg.settings.get("llm") or {}).get("ablation_probe", True))


def _bars_after(candles: list[Candle], opened_at: datetime) -> list[Candle]:
    """Bars containing time after the entry; the bar in progress at entry counts."""
    return [c for c in candles if c.close_time > opened_at]


def _price_inside(proposal: Proposal, price: float) -> bool:
    """A take can only be entered while price is still between its SL and TP."""
    lo, hi = sorted((proposal.sl, proposal.tp))
    return lo < price < hi


def snapshot_calibration(rec: FlightRecorder, cal: CalibrationMatrix) -> None:
    for lo, hi in cal.buckets:
        label = bucket_label(lo, hi)
        for regime in cal.regimes:
            cell = cal.get_cell(label, regime)
            rec.insert_calibration_snapshot(f"{label}|{regime}", cell.n, cell.wins, cell.wilson(cal.z))


def resolve_open_positions(
    rec: FlightRecorder,
    broker: PaperBroker,
    shadow: ShadowBook,
    cal: CalibrationMatrix,
    candles_by_symbol: dict[str, list[Candle]],
    timeout_bars: int,
) -> dict[str, int]:
    """Close every guarded and shadow position whose TP, SL or timeout has been reached."""
    closed = {"guarded": 0, "shadow": 0}

    for pos in list(broker.account.positions.values()):
        bars = _bars_after(candles_by_symbol.get(pos.symbol, []), pos.opened_at)
        if not bars:
            continue
        out = resolve(pos.fill_price, pos.sl, pos.tp, pos.side, bars, timeout_bars=timeout_bars)
        if out.result == OutcomeResult.OPEN:
            continue
        broker.close_order(pos.order_id, price=out.exit_price)
        if pos.meta.get("db_id") is not None:
            rec.insert_outcome(
                "real", int(pos.meta["db_id"]), out.result.value, out.r_multiple,
                out.bars_held, out.exit_price,
            )
        closed["guarded"] += 1
        log.info("guarded %s %s closed: %s r=%.2f", pos.symbol, pos.side.value,
                 out.result.value, out.r_multiple)

    for pid, spos in list(shadow.open_positions.items()):
        bars = _bars_after(candles_by_symbol.get(spos.symbol, []), spos.opened_at)
        if not bars:
            continue
        out = shadow.resolve_position(pid, bars, timeout_bars=timeout_bars)
        if out.result == OutcomeResult.OPEN:
            continue
        if spos.meta.get("db_id") is not None:
            rec.insert_outcome(
                "shadow", int(spos.meta["db_id"]), out.result.value, out.r_multiple,
                out.bars_held, out.exit_price,
            )
        # Calibration learns from every take the Trader made, approved or vetoed, so the
        # matrix measures the model rather than the gate's own selection of trades.
        if spos.meta.get("confidence") is not None and spos.meta.get("regime"):
            cal.update_from_outcome(int(spos.meta["confidence"]), str(spos.meta["regime"]),
                                    out.result.value)
        closed["shadow"] += 1

    return closed


def run_cycle(
    cfg: Any,
    rec: FlightRecorder,
    trader: LLMTrader,
    cal: CalibrationMatrix,
    bitget: Any,
    ref: Any,
    sentiment: Any,
    broker: PaperBroker,
    shadow: ShadowBook,
    gate_config: str,
    *,
    mock_llm: bool = False,
    offline: bool = False,
    behavior: Optional[BehaviorState] = None,
    now: Optional[datetime] = None,
    processed_bars: Optional[dict[str, str]] = None,
) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    behavior = behavior if behavior is not None else BehaviorState()
    sim = SimTrader(trader)
    settings, limits = cfg.settings, cfg.limits
    ablation_on = settings_probe(cfg) and gate_config == "G2"
    market = settings["market"]
    entry_tf = market["entry_tf"]
    limit = int(market["candle_limit"])
    timeout_bars = int(settings["calibration"]["timeout_bars"])
    prompt_version = "sim" if mock_llm else settings["llm"]["prompt_version"]

    cooldown = limits.get("consecutive_loss_cooldown") or {}
    if isinstance(cooldown, dict):
        broker.account.loss_cooldown = (int(cooldown.get("losses", 3)), float(cooldown.get("hours", 4)))
    broker.account.roll_day(now)

    symbols = list(market["symbols"])

    def fetch(symbol: str) -> tuple[list[Candle], list[Candle], list[Candle], list[Candle]]:
        # Both exchanges rate-limit per address, and one 429 should not cost a coin its cycle
        for attempt in range(FETCH_ATTEMPTS):
            try:
                return (
                    bitget.fetch_klines(symbol, entry_tf, limit),
                    bitget.fetch_klines(symbol, "1h", max(limit, REGIME_1H_BARS)),
                    bitget.fetch_klines(symbol, "4h", limit),
                    ref.fetch_klines(symbol, entry_tf, limit),
                )
            except Exception:
                if attempt == FETCH_ATTEMPTS - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError("unreachable")

    # Four calls per coin, so the coins run side by side: 25 of them still fit in one cycle
    fetched: dict[str, tuple[list[Candle], list[Candle], list[Candle], list[Candle]]] = {}
    if not offline and symbols:
        with ThreadPoolExecutor(max_workers=min(FETCH_WORKERS, len(symbols))) as pool:
            pending = {pool.submit(fetch, s): s for s in symbols}
            for done in as_completed(pending):
                symbol = pending[done]
                try:
                    fetched[symbol] = done.result()
                except Exception as exc:
                    # Never trade or calibrate on made-up candles in a real run.
                    log.warning("%s: feed fetch failed (%s); skipping symbol this cycle", symbol, exc)

    feeds: dict[str, tuple[list[Candle], list[Candle], list[Candle], list[Candle]]] = {}
    for symbol in symbols:  # settings order, whatever order the fetches finished in
        if symbol in fetched:
            feeds[symbol] = fetched[symbol]
        elif offline:
            base = {"BTCUSDT": 95000.0, "ETHUSDT": 3500.0, "SOLUSDT": 180.0}.get(symbol, 100.0)
            feeds[symbol] = (
                _synth_klines(symbol, entry_tf, limit, base),
                _synth_klines(symbol, "1h", REGIME_1H_BARS, base),
                _synth_klines(symbol, "4h", limit, base),
                _synth_klines(symbol, entry_tf, limit, base * 1.00005),
            )

    # 1. Settle whatever hit TP / SL / timeout before judging anything new
    closed = resolve_open_positions(
        rec, broker, shadow, cal, {s: f[0] for s, f in feeds.items()}, timeout_bars
    )
    if closed["shadow"]:
        snapshot_calibration(rec, cal)
    stats = {"setups": 0, "takes": 0, "orders": 0, "already_processed": 0, "model_failed": 0,
             "closed_guarded": closed["guarded"], "closed_shadow": closed["shadow"],
             "feeds_failed": len(market["symbols"]) - len(feeds)}
    account = broker.account.to_account_state()

    for symbol, (c15_all, c1h_all, c4h_all, r15_all) in feeds.items():
        # 2. Decide on closed bars only; the forming bar holds a few seconds of data
        c15, c1h, c4h, r15 = [closed_candles(s, now) for s in (c15_all, c1h_all, c4h_all, r15_all)]
        if not (c15 and c1h and c4h and c15_all):
            log.warning("%s: no closed candles; skipping symbol this cycle", symbol)
            continue
        if processed_bars is not None:
            # A late or doubled trigger inside the same 15m bar must not trade it twice
            bar = c15[-1].open_time.isoformat()
            if processed_bars.get(symbol) == bar:
                stats["already_processed"] += 1
                continue
            processed_bars[symbol] = bar
        last_price = c15_all[-1].close
        sent = sentiment.fetch([symbol])
        atr_series = atr_pct_series(c1h)
        atrp = atr_series[-1] if atr_series else 0.0
        regime = regime_from_history(atr_series[-LOOKBACK_BARS:], atrp) if atr_series else "mid"

        cycle_id = rec.insert_cycle(symbol, cfg.limits_hash, prompt_version, regime)
        setups = find_candidates(c15, c1h[-limit:], c4h, symbol, settings.get("smc", {}))
        log.info("%s: %d setups (regime=%s)", symbol, len(setups), regime)

        for setup in setups:
            stats["setups"] += 1
            setup_id = rec.insert_setup(cycle_id, setup)
            digest = SentimentFeed.digest(sent)
            indicators = {
                "atr_pct_1h": atrp,
                "regime": regime,
                "setup_score": setup.setup_score,
                "bias": setup.bias,
            }
            tfs = {"15m": c15[-30:], "1h": c1h[-30:], "4h": c4h[-30:]}

            def ask(dig: str) -> Proposal:
                if mock_llm:
                    p = sim.propose(setup, tfs, dig)
                    p.prompt_version = "sim"
                    return p
                return trader.propose(setup, tfs, dig, indicators)

            proposal = ask(digest)
            # A dead key or a spent quota returns an empty proposal the Inspector then
            # vetoes, which reads like an ordinary veto. Count it so it cannot hide.
            if proposal.invalid_output:
                stats["model_failed"] += 1
                log.warning("%s: the model did not answer (%s)", symbol, proposal.rationale)
            pid = rec.insert_proposal(setup_id, proposal)

            # M2 ablation probe: same setup, sentiment stripped. One extra call,
            # only when the Trader wants to take (skips need no second opinion).
            ablation = ask(NO_SENTIMENT) if ablation_on and proposal.action == Action.TAKE else None
            if ablation is not None and ablation.invalid_output:
                stats["model_failed"] += 1

            ctx = GateContext(
                account=account,
                regime=regime,  # type: ignore[arg-type]
                trader_candles=c15[-50:],
                reference_candles=r15[-50:],
                sentiment=sent,
                setup_score=setup.setup_score,
                trailing_confidences=behavior.trailing(),
                sentiment_history_scores=behavior.sentiment_history(),
                ablation_confidence=ablation.confidence if ablation else None,
                ablation_action=ablation.action.value if ablation else None,
                as_of=now,
            )
            decision = decide(proposal, ctx, settings, limits, cal, gate_config=gate_config)
            # Only non-anomalous observations feed the M1/S2 baselines, so an
            # attacker cannot slowly drag the baseline toward their target.
            if decision.reason != "input_anomaly" and proposal.confidence > 0:
                behavior.record_proposal(setup.setup_score, proposal.confidence)
            did = rec.insert_decision(pid, decision)
            log.info(
                "decision %s conf=%s -> %s (%s)",
                proposal.action.value,
                proposal.confidence,
                decision.kind.value,
                decision.reason,
            )

            if proposal.action != Action.TAKE:
                continue
            stats["takes"] += 1
            if not _price_inside(proposal, last_price):
                log.info("%s: price %.6f is already past SL/TP; take not entered", symbol, last_price)
                continue

            spos = shadow.open_from_proposal(
                proposal, symbol=symbol, last_price=last_price, proposal_id=pid
            )
            if spos is not None:
                sid = rec.insert_shadow(
                    pid, proposal.entry, proposal.sl, proposal.tp, spos.size, symbol,
                    proposal.side.value,
                )
                spos.meta.update({"db_id": sid, "confidence": proposal.confidence, "regime": regime})

            if decision.kind in (DecisionKind.APPROVE, DecisionKind.SHRINK) and decision.size > 0:
                try:
                    order = broker.place_order(
                        symbol=symbol,
                        side=proposal.side.value,
                        size=decision.size,
                        entry=proposal.entry,
                        sl=proposal.sl,
                        tp=proposal.tp,
                        last_price=last_price,
                    )
                except Exception as exc:
                    log.warning("%s: order not placed (%s)", symbol, exc)
                    continue
                oid = rec.insert_order(
                    did, order["order_id"], order["fill_price"], order["fees"],
                    order["symbol"], order["side"], order["size"],
                )
                broker.account.positions[order["order_id"]].meta.update(
                    {"db_id": oid, "proposal_id": pid, "decision_id": did}
                )
                account = broker.account.to_account_state()
                stats["orders"] += 1

        if sent:
            behavior.record_sentiment(SentimentFeed.aggregate_score(sent))

    rec.insert_equity("guarded", broker.account.equity)
    rec.insert_equity("shadow", shadow.equity)
    return stats


def sandbox_dir() -> Path:
    return ROOT / "data" / "mock"


def state_paths(sandbox: bool) -> dict[str, Path]:
    base = sandbox_dir() if sandbox else ROOT / "data"
    return {
        "state": base / "live_state.json",
        "calibration": base / "calibration.json",
        "behavior": base / "behavior_state.json",
    }


def save_state(
    path: Path,
    broker: PaperBroker,
    shadow: ShadowBook,
    processed_bars: Optional[dict[str, str]] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(
            {
                "broker": broker.account.to_dict(),
                "shadow": shadow.to_dict(),
                "processed_bars": processed_bars or {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)


def load_state(path: Path, equity: float) -> tuple[PaperModeAccount, ShadowBook]:
    if not path.exists():
        return PaperModeAccount(equity), ShadowBook(starting_equity=equity)
    data = json.loads(path.read_text(encoding="utf-8"))
    return PaperModeAccount.from_dict(data["broker"]), ShadowBook.from_dict(data["shadow"])


def load_processed_bars(path: Path) -> dict[str, str]:
    """Newest closed bar already traded per symbol, so a restarted run skips it."""
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("processed_bars") or {})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Single cycle then exit (non-zero if it failed)")
    parser.add_argument("--gate", default="G2", choices=["G0", "G1", "G2A", "G2"])
    parser.add_argument("--interval", type=int, default=900,
                        help="Seconds between cycles if the scheduler cannot start")
    parser.add_argument("--mock-llm", action="store_true",
                        help="Simulated trader, no API calls (plumbing only; writes to data/mock/)")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Synthetic candles when exchange DNS/API is unavailable (writes to data/mock/)",
    )
    args = parser.parse_args()

    cfg = ConfigBundle()
    trader = LLMTrader(cfg.settings)
    if trader._client is None and not args.mock_llm:
        sys.exit(
            "No LLM API key found (LLM_API_KEY, XAI_API_KEY, or the variable named in "
            "llm.api_key_env). Add it to .env, or pass --mock-llm to run the simulated trader on purpose."
        )

    sandbox = args.mock_llm or args.offline
    paths = state_paths(sandbox)
    rec = FlightRecorder(sandbox_dir() / "tare.db" if sandbox else db_path(cfg.settings))
    equity0 = float(os.getenv("PAPER_EQUITY", "10000"))
    account, shadow = load_state(paths["state"], equity0)
    processed_bars = load_processed_bars(paths["state"])
    broker = PaperBroker(starting_equity=equity0, account=account)

    real_cal = ROOT / "data" / "calibration.json"
    if paths["calibration"].exists():
        cal = CalibrationMatrix.load(paths["calibration"])
    elif real_cal.exists():
        cal = CalibrationMatrix.load(real_cal)
    else:
        cal = CalibrationMatrix.from_settings(cfg.settings)
    cal.unfreeze()  # live outcomes append to the matrix
    behavior = BehaviorState.load(paths["behavior"])

    bitget = BitgetFeed(paper=True)
    ref = ReferenceFeed(cfg.settings["market"].get("reference_venue", "okx"))
    sentiment = SentimentFeed(cfg.settings["market"].get("sentiment_lookback_hours", 6))

    trader_note = "SIMULATED-trader" if args.mock_llm else f"llm={trader.model}"
    offline_note = " offline-candles" if args.offline else ""

    def current_note() -> str:
        """Where fills actually went, not where they were configured to go.

        The keys being present only means the bot tried the exchange. If Bitget rejected
        the order the fill was simulated, and the status must say that rather than keep
        advertising demo-account fills.
        """
        if broker.fills == "bitget-demo" and not broker._has_keys:
            fills_note = "fills=local-sim-no-keys"
        elif not broker._use_api:
            fills_note = "fills=local-sim"
        elif broker.api_failures:
            fills_note = "fills=local-sim-after-reject"
        else:
            fills_note = "fills=bitget-demo-api"
        return f"gate={args.gate} {trader_note} {fills_note}{offline_note}"

    note = current_note()
    if sandbox:
        log.warning("Plumbing mode: writing to %s; nothing recorded there is evidence", sandbox_dir())
    if account.positions or shadow.open_positions:
        log.info("resumed %d guarded and %d shadow open positions",
                 len(account.positions), len(shadow.open_positions))
    rec.set_status("running", note)
    snapshot_calibration(rec, cal)
    lock = threading.Lock()
    last = {"ok": True}

    def set_health(text: str) -> None:
        # The status row is what the dashboard and export show, so a dead feed is visible there
        try:
            rec.set_status("running", f"{current_note()} | {text}")
        except Exception:
            log.exception("could not write bot status")

    def cycle() -> None:
        if not lock.acquire(blocking=False):
            log.warning("previous cycle still running; skipping this trigger")
            return
        stamp = f"last cycle {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z"
        try:
            cfg.reload()
            stats = run_cycle(
                cfg, rec, trader, cal, bitget, ref, sentiment, broker, shadow, args.gate,
                mock_llm=args.mock_llm, offline=args.offline, behavior=behavior,
                processed_bars=processed_bars,
            )
            log.info("cycle done %s equity guarded=%.2f shadow=%.2f", stats,
                     broker.account.equity, shadow.equity)
            n_symbols = len(cfg.settings["market"]["symbols"])
            if stats["feeds_failed"]:
                log.warning("%d of %d symbols had no market data this cycle",
                            stats["feeds_failed"], n_symbols)
            # A cycle that found setups but got no answer for any of them is a failed
            # cycle, not a quiet one: the run should go red and the health line say why.
            mute = stats["setups"] > 0 and stats["model_failed"] >= stats["setups"]
            # An order the exchange refused is a broken execution path, so the run goes red
            # even though the bot carried on with a simulated fill.
            rejected = broker.api_failures[-1]["error"] if broker.api_failures else ""
            last["ok"] = stats["feeds_failed"] < n_symbols and not mute and not rejected
            failed = f", {stats['model_failed']} model calls failed" if stats["model_failed"] else ""
            refused = f", SIMULATED FILL: bitget refused the order ({rejected})" if rejected else ""
            set_health(f"{stamp}: {n_symbols - stats['feeds_failed']}/{n_symbols} feeds ok, "
                       f"{stats['setups']} setups, {stats['orders']} orders{failed}{refused}")
        except Exception:
            last["ok"] = False
            log.exception("cycle failed")
            set_health(f"{stamp}: FAILED, see logs")
        finally:
            try:
                cal.save(paths["calibration"])
                behavior.save(paths["behavior"])
                save_state(paths["state"], broker, shadow, processed_bars)
            except Exception:
                last["ok"] = False
                log.exception("saving state failed")
            lock.release()

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        if args.once:
            cycle()
        else:
            scheduler = None
            try:
                from core.clock import CandleCloseScheduler

                scheduler = CandleCloseScheduler(cfg.settings["market"]["entry_tf"])
                scheduler.start(cycle)
                log.info("scheduler started; also running an immediate cycle")
            except Exception:
                log.exception("scheduler failed; using a sleep loop every %ss", args.interval)
                scheduler = None
            cycle()
            while True:
                time.sleep(60 if scheduler else args.interval)
                if scheduler is None:
                    cycle()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        # Keep the last health line, so a stopped bot still says how its final cycle went.
        # Under --once an outside scheduler (GitHub Actions cron) runs the bot, so it stays
        # "running"; the website judges staleness from updated_at instead.
        if not args.once:
            rec.set_status("stopped", rec.get_status().get("note") or note)
    if args.once and not last["ok"]:
        sys.exit(1)  # a scheduler (GitHub Actions) should see a failed cycle as a failed run


if __name__ == "__main__":
    main()
