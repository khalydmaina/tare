"""Attack runner: A5 replays from the cache, spends a bounded number of calls, and a partial
run never replaces the published table."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attacks import a5_adaptive  # noqa: E402
from attacks.a5_adaptive import AdaptiveAttack, parse_variant  # noqa: E402
from attacks.base import AttackContext  # noqa: E402
from core.schemas import Candle, Setup, Side  # noqa: E402
from scripts import run_attacks  # noqa: E402

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _ctx() -> AttackContext:
    candles = [
        Candle(symbol="BTCUSDT", timeframe="15m", open_time=T0 + timedelta(minutes=15 * i),
               close_time=T0 + timedelta(minutes=15 * (i + 1)), open=100, high=101, low=99,
               close=100, volume=1, source="test", fetched_at=T0)
        for i in range(8)
    ]
    setup = Setup(symbol="BTCUSDT", side=Side.LONG, entry=100, sl=98, tp=104, rr=2.0,
                  structure_summary="x", setup_score=0.6)
    return AttackContext(setup=setup, candles_15m=candles, candles_1h=[], candles_4h=[],
                         sentiment=[], true_result="loss", scenario_id="s1")


def _attacker_env(monkeypatch) -> None:
    monkeypatch.setenv("ATTACKER_API_KEY", "k")
    monkeypatch.setenv("ATTACKER_BASE_URL", "https://attacker.example/v1")
    monkeypatch.setenv("ATTACKER_MODEL", "attacker-model")


def test_a5_loop_is_deterministic_and_dated_by_the_bar():
    def run():
        prompts: list[str] = []

        def writer(prompt: str, attempt: int) -> tuple[str, str]:
            prompts.append(prompt)
            return f"headline {attempt}", f"desk-{attempt}"

        verdicts = iter([(False, "veto_a"), (False, "veto_b"), (True, "approve")])
        attack = AdaptiveAttack(max_attempts=5, judge=lambda v: next(verdicts), writer=writer)
        return attack.apply(_ctx()), prompts

    variant, prompts = run()
    assert variant.notes.startswith("succeeded on attempt 3")
    assert "'headline 0' -> blocked by: veto_a" in prompts[2]
    assert "'headline 1' -> blocked by: veto_b" in prompts[2]
    # The run's wall clock must not reach the payload, or no answer could be replayed
    assert variant.sentiment[0].published_at == _ctx().candles_15m[-1].close_time
    assert run()[1] == prompts


def test_a5_with_a_key_fails_loudly_instead_of_using_the_scripted_ladder(monkeypatch):
    _attacker_env(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("429 quota")

    monkeypatch.setattr(a5_adaptive, "call_attacker", boom)
    attack = AdaptiveAttack(max_attempts=3, judge=lambda v: (False, "veto"))
    with pytest.raises(RuntimeError, match="429"):
        attack.apply(_ctx())


def test_parse_variant():
    assert parse_variant('Sure:\n{"text": "BTC ETF inflows", "source": "wire"}', 0) == (
        "BTC ETF inflows", "wire")
    assert parse_variant('{"text": "no source"}', 4) == ("no source", "adaptive-4")
    for bad in ("no json here", '{"source": "wire"}', '{"text": ""}'):
        with pytest.raises(ValueError):
            parse_variant(bad, 0)


def test_attacker_answers_are_cached_and_replayed(tmp_path, monkeypatch):
    _attacker_env(monkeypatch)
    sent: list[str] = []

    def fake_call(prompt, key, base_url, model):
        sent.append(prompt)
        return '{"text": "whales loading", "source": "chain"}'

    monkeypatch.setattr(run_attacks, "call_attacker", fake_call)
    cache: dict = {}
    cache_path = tmp_path / "cache.json"
    calls = {"n": 0, "max": 0}
    write, label = run_attacks.make_attacker_writer(cache, cache_path, False, calls, {"n": 0})
    assert label == "attacker-model@https://attacker.example/v1"
    assert write("p1", 0) == ("whales loading", "chain")
    assert write("p1", 0) == ("whales loading", "chain")
    assert len(sent) == 1 and calls["n"] == 1
    assert len(json.loads(cache_path.read_text())) == 1

    misses = {"n": 0}
    replay, _ = run_attacks.make_attacker_writer(cache, None, True, {"n": 0, "max": 0}, misses)
    assert replay("p1", 0) == ("whales loading", "chain") and misses["n"] == 0
    replay("never asked", 0)
    assert misses["n"] == 1 and len(sent) == 1


def test_attacker_failure_stops_the_run_and_caches_nothing(tmp_path, monkeypatch):
    _attacker_env(monkeypatch)
    monkeypatch.setattr(run_attacks, "call_attacker", lambda *a: "I cannot help with that")
    monkeypatch.setattr(run_attacks.time, "sleep", lambda s: None)
    cache: dict = {}
    calls = {"n": 0, "max": 0}
    write, _ = run_attacks.make_attacker_writer(cache, tmp_path / "c.json", False, calls, {"n": 0})
    with pytest.raises(SystemExit, match="failed 3 times"):
        write("p", 0)
    assert cache == {} and calls["n"] == 3


def test_attacker_without_a_key_refuses_a_real_run(monkeypatch):
    for name in ("ATTACKER_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit, match="ATTACKER_API_KEY"):
        run_attacks.make_attacker_writer({}, None, False, {"n": 0, "max": 0}, {"n": 0})


def test_budget_stops_before_the_call_that_would_exceed_it():
    calls = {"n": 0, "max": 2}
    run_attacks.spend(calls)
    run_attacks.spend(calls)
    with pytest.raises(SystemExit, match="budget of 2"):
        run_attacks.spend(calls)
    assert calls["n"] == 2
    unlimited = {"n": 0, "max": 0}
    for _ in range(50):
        run_attacks.spend(unlimited)


def test_narrower_than(tmp_path):
    published = tmp_path / "m.json"
    assert run_attacks.narrower_than(published, {}) == []
    published.write_text(json.dumps({"meta": {
        "attacks": ["A1", "A3"], "gates": ["G0", "G2"], "eval_scenarios": 40}}))
    full = {"attacks": ["A1", "A2", "A3"], "gates": ["G0", "G1", "G2"], "eval_scenarios": 40}
    assert run_attacks.narrower_than(published, full) == []
    assert run_attacks.narrower_than(
        published, {"attacks": ["A2"], "gates": ["G2"], "eval_scenarios": 20}
    ) == ["attack A1", "attack A3", "gate G0", "20 eval scenarios"]


def test_a_partial_run_leaves_the_published_table_alone(tmp_path, monkeypatch):
    for sub in ("docs", "web/public"):
        (tmp_path / sub).mkdir(parents=True)
    published = tmp_path / "docs" / "attack_metrics.json"
    monkeypatch.setattr(run_attacks, "ROOT", tmp_path)
    monkeypatch.setattr(run_attacks, "PUBLISHED", published)
    monkeypatch.setenv("TARE_DB", str(tmp_path / "t.db"))

    def main(*argv: str) -> None:
        monkeypatch.setattr(sys, "argv", ["run_attacks.py", "--llm", "sim", "--n", "30",
                                          "--no-background", "--out", str(published), *argv])
        run_attacks.main()

    main("--attacks", "A1,A3", "--gates", "G0,G2")
    table = published.read_text()
    assert (tmp_path / "web" / "public" / "attack_metrics.json").exists()

    main("--attacks", "A3", "--gates", "G2")
    assert published.read_text() == table

    main("--attacks", "A3", "--gates", "G2", "--allow-narrower")
    assert json.loads(published.read_text())["meta"]["attacks"] == ["A3"]


def test_a_google_model_through_openrouter_reuses_the_recorded_answers():
    def key(model: str, base_url: str) -> str:
        trader = SimpleNamespace(model=model, base_url=base_url, prompt_version="trader_v2",
                                 system_prompt="sys")
        return run_attacks.cache_key(trader, "payload")

    direct = key("gemini-3.1-flash-lite", run_attacks.GOOGLE_OPENAI)
    assert key("google/gemini-3.1-flash-lite", "https://openrouter.ai/api/v1") == direct
    # A different model, or a non-Google model on the router, is a different answerer
    assert key("google/gemini-3-flash-preview", "https://openrouter.ai/api/v1") != direct
    assert key("openai/gpt-oss-120b", "https://openrouter.ai/api/v1") != key(
        "openai/gpt-oss-120b", "https://api.groq.com/openai/v1")
