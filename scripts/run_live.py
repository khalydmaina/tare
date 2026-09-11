#!/usr/bin/env python3
"""Live paper loop: candle close → SMC → LLM → Inspector → broker + shadow."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.config import ConfigBundle  # noqa: E402
from core.schemas import AccountState, Action, DecisionKind, GateContext  # noqa: E402
from data.bitget_feed import BitgetFeed  # noqa: E402
from data.reference_feed import ReferenceFeed  # noqa: E402
from data.sentiment_feed import SentimentFeed  # noqa: E402
from execution.bitget_broker import PaperBroker  # noqa: E402
from execution.shadow_book import ShadowBook  # noqa: E402
from inspector.behavior import BehaviorState  # noqa: E402
from inspector.calibration import CalibrationMatrix  # noqa: E402
from inspector.gate import decide  # noqa: E402
from recorder.db import FlightRecorder  # noqa: E402
from trader.candidates import find_candidates  # noqa: E402
from trader.llm_trader import LLMTrader  # noqa: E402
from trader.sim_trader import SimTrader  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tare.live")


def atr_pct(candles, period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(-period, 0):
        c = candles[i]
        prev = candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
        trs.append(tr)
    atr = sum(trs) / len(trs)
    return atr / candles[-1].close if candles[-1].close else 0.0


def regime_from_atr_history(values: list[float], current: float) -> str:
    if len(values) < 10:
        return "mid"
    s = sorted(values)
    t1, t2 = s[len(s) // 3], s[(2 * len(s)) // 3]
    if current <= t1:
        return "low"
    if current >= t2:
        return "high"
    return "mid"


def _synth_klines(symbol: str, timeframe: str, limit: int, start: float = 100.0):
    from datetime import datetime, timedelta, timezone

    from core.schemas import Candle

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


def settings_probe(cfg: ConfigBundle) -> bool:
    return bool((cfg.settings.get("llm") or {}).get("ablation_probe", True))


def run_cycle(cfg: ConfigBundle, rec: FlightRecorder, trader: LLMTrader, cal: CalibrationMatrix,
              bitget: BitgetFeed, ref: ReferenceFeed, sentiment: SentimentFeed,
              broker: PaperBroker, shadow: ShadowBook, atr_hist: list[float],
              gate_config: str, mock_llm: bool = False, offline: bool = False,
              behavior: BehaviorState | None = None) -> None:
    behavior = behavior if behavior is not None else BehaviorState()
    sim = SimTrader(trader)
    ablation_on = bool(settings_probe(cfg)) and gate_config == "G2"
    settings = cfg.settings
    symbols = settings["market"]["symbols"]
    entry_tf = settings["market"]["entry_tf"]
    limit = settings["market"]["candle_limit"]
    account = broker.account.to_account_state()

    for symbol in symbols:
        try:
            if offline:
                raise RuntimeError("offline mode")
            c15 = bitget.fetch_klines(symbol, entry_tf, limit)
            c1h = bitget.fetch_klines(symbol, "1h", limit)
            c4h = bitget.fetch_klines(symbol, "4h", limit)
            r15 = ref.fetch_klines(symbol, entry_tf, limit)
        except Exception as exc:
            if not offline:
                # Never trade or calibrate on made-up candles in a real run.
                log.warning("%s: feed fetch failed (%s); skipping symbol this cycle", symbol, exc)
                continue
            log.warning("offline mode: using synthetic candles")
            base = {"BTCUSDT": 95000.0, "ETHUSDT": 3500.0, "SOLUSDT": 180.0}.get(symbol, 100.0)
            c15 = _synth_klines(symbol, entry_tf, limit, base)
            c1h = _synth_klines(symbol, "1h", limit, base)
            c4h = _synth_klines(symbol, "4h", limit, base)
            r15 = _synth_klines(symbol, entry_tf, limit, base * 1.00005)
        sent = sentiment.fetch([symbol])

        atrp = atr_pct(c1h)
        atr_hist.append(atrp)
        regime = regime_from_atr_history(atr_hist[-30 * 24 :], atrp)  # rough trailing

        cycle_id = rec.insert_cycle(
            symbol, cfg.limits_hash, settings["llm"]["prompt_version"], regime
        )
        setups = find_candidates(c15, c1h, c4h, symbol, settings.get("smc", {}))
        log.info("%s: %d setups", symbol, len(setups))

        for setup in setups:
            setup_id = rec.insert_setup(cycle_id, setup)
            digest = SentimentFeed.digest(sent)
            indicators = {
                "atr_pct_1h": atrp,
                "regime": regime,
                "setup_score": setup.setup_score,
                "bias": setup.bias,
            }
            tfs = {"15m": c15[-30:], "1h": c1h[-30:], "4h": c4h[-30:]}
            use_sim = mock_llm or trader._client is None

            def ask(dig: str):
                if use_sim:
                    return sim.propose(setup, tfs, dig)
                return trader.propose(setup, tfs, dig, indicators)

            proposal = ask(digest)
            pid = rec.insert_proposal(setup_id, proposal)

            # M2 ablation probe: same setup, sentiment stripped. One extra call,
            # only when the Trader wants to take (skips need no second opinion).
            ablation = None
            if ablation_on and proposal.action == Action.TAKE:
                ablation = ask("(no sentiment items)")

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
            )
            decision = decide(proposal, ctx, settings, cfg.limits, cal, gate_config=gate_config)
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

            if proposal.action == Action.TAKE:
                pos = shadow.open_from_proposal(
                    proposal, symbol=symbol, last_price=c15[-1].close, proposal_id=pid
                )
                if pos is not None:
                    rec.insert_shadow(
                        pid,
                        proposal.entry,
                        proposal.sl,
                        proposal.tp,
                        pos.size,
                        symbol,
                        proposal.side.value,
                    )

            if decision.kind in (DecisionKind.APPROVE, DecisionKind.SHRINK) and decision.size > 0:
                order = broker.place_order(
                    symbol=symbol,
                    side=proposal.side.value,
                    size=decision.size,
                    entry=proposal.entry,
                    sl=proposal.sl,
                    tp=proposal.tp,
                    last_price=c15[-1].close,
                )
                rec.insert_order(
                    did,
                    order.get("order_id", ""),
                    order.get("fill_price", proposal.entry),
                    order.get("fees", 0.0),
                    symbol,
                    proposal.side.value,
                    decision.size,
                )
                account = broker.account.to_account_state()

        if sent:
            behavior.record_sentiment(SentimentFeed.aggregate_score(sent))
        rec.insert_equity("guarded", broker.account.equity)
        rec.insert_equity("shadow", shadow.equity)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Single cycle then exit")
    parser.add_argument("--gate", default="G2", choices=["G0", "G1", "G2A", "G2"])
    parser.add_argument("--interval", type=int, default=900, help="Seconds between cycles if looping")
    parser.add_argument("--mock-llm", action="store_true", help="No API calls; mock proposals")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use synthetic candles when exchange DNS/API is unavailable",
    )
    args = parser.parse_args()

    cfg = ConfigBundle()
    db_path = os.getenv("TARE_DB", os.getenv("PROSECUTOR_DB", cfg.settings["recorder"]["db_path"]))
    rec = FlightRecorder(ROOT / db_path if not Path(db_path).is_absolute() else db_path)
    rec.set_status("running", f"gate={args.gate}")

    cal_path = ROOT / "data" / "calibration.json"
    if cal_path.exists():
        cal = CalibrationMatrix.load(cal_path)
    else:
        cal = CalibrationMatrix.from_settings(cfg.settings)

    trader = LLMTrader(cfg.settings)
    bitget = BitgetFeed(paper=True)
    ref = ReferenceFeed(cfg.settings["market"].get("reference_venue", "binance"))
    sentiment = SentimentFeed(cfg.settings["market"].get("sentiment_lookback_hours", 6))
    equity0 = float(os.getenv("PAPER_EQUITY", "10000"))
    broker = PaperBroker(starting_equity=equity0)
    shadow = ShadowBook(starting_equity=equity0)
    atr_hist: list[float] = []
    behavior_path = ROOT / "data" / "behavior_state.json"
    behavior = BehaviorState.load(behavior_path)
    use_mock = args.mock_llm or not os.getenv("XAI_API_KEY")

    def cycle() -> None:
        try:
            cfg.reload()
            run_cycle(
                cfg, rec, trader, cal, bitget, ref, sentiment, broker, shadow, atr_hist,
                args.gate, mock_llm=use_mock, offline=args.offline, behavior=behavior,
            )
            cal.save(cal_path)
            behavior.save(behavior_path)
        except Exception:
            log.exception("cycle failed")

    if args.once:
        cycle()
        rec.set_status("stopped", "once complete")
        return

    # Prefer APScheduler on 15m; fallback sleep loop
    try:
        from core.clock import CandleCloseScheduler

        sched = CandleCloseScheduler(cfg.settings["market"]["entry_tf"])
        sched.start(cycle)
        log.info("scheduler started; also running immediate cycle")
        cycle()
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        rec.set_status("stopped", "keyboard")
    except Exception:
        log.exception("scheduler failed; using sleep loop")
        while True:
            cycle()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
