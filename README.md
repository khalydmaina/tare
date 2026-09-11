# tare

**Zero the confidence. Weigh the record.**

An AI trader with brakes that tighten exactly where the model has proven it can’t be trusted - and that hold when someone tries to game them.

**Hackathon:** Bitget AI × Crypto Hackathon, Genesis Season 2 - Agentic Trading / Open Theme  
**Brand kit:** [`brand/tare/`](brand/tare/) - logos, tokens, 15-page PDF

> **Name:** *tare* (tair) - the weight you subtract so the scale reads true.  
> Gross = stated confidence · Tare = Inspector correction · Net = calibrated probability.  
> Formerly referred to in early docs as “The Prosecutor.”

## 30-second explanation

A deterministic SMC engine finds setups. An LLM decides take/skip and states a confidence (probability that TP hits before SL). A non-LLM **Inspector** sizes or vetoes every proposal using a calibration matrix, independent market data, and hard limits the model cannot touch. A **shadow book** records what would have happened without the Inspector. An **attack suite** tries to inflate confidence and slip losses past the gate.

**What we test:** calibration gates can be beaten without ever claiming high confidence. Steer the model into a bucket that has historically been right and calibration approves the loss (A4). The fix is an ablation probe: re-ask the Trader with the news removed, and never let text raise confidence (G2). `docs/RESULTS.md` reports whether that holds on a real model, including if it does not.

## Shared blind spots (why not a second LLM?)

1. A reviewer model shares training quirks and prompt-injection surfaces with the trader model.
2. When the trader is fooled by forged structure or poisoned sentiment, a peer LLM is likely fooled the same way.
3. The Inspector never asks another model - it judges measured hit rates and independent feeds.

## Architecture

```text
Trader feed (Bitget) + sentiment → SMC → LLM proposal
                                      ↓
Reference feed (Binance) --------→ INSPECTOR → approve/shrink/veto
                                      ↓
                         Bitget paper + Shadow book → Flight Recorder → Dashboard
```

## Quick start

```bash
cd tare
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # XAI_API_KEY, BITGET_* keys

pytest                                   # 31 tests
python scripts/run_attacks.py --llm sim  # offline plumbing check (NOT evidence)

cd web && npm install && npm run dev     # http://localhost:5173 and /app
```

## Producing the real numbers

```bash
# 1. Real scenario bank: Bitget futures candles + Binance reference, SMC walk-forward,
#    every setup labelled with what actually happened next. No LLM cost.
python scripts/build_scenarios.py --days 45 --symbols BTCUSDT,ETHUSDT,SOLUSDT

# 2. Check C1's cross-venue threshold against real basis before trusting it
python scripts/measure_basis.py --days 30

# 3. Attack evaluation with the real Trader model (candles blinded before the prompt).
#    First 60% of scenarios fill the calibration matrix, attacks run on the rest.
#    Responses are cached in data/llm_cache.json so re-runs are free.
python scripts/run_attacks.py --scenarios data/scenarios.jsonl --llm real \
    --max-eval 120 --save-calibration

# 4. Write docs/RESULTS.md (refuses to present sim output as evidence)
python scripts/export_results.py

# 5. Live paper loop on the VPS (G2 = full gate incl. ablation probe)
python scripts/run_live.py --gate G2
```

## Gate configs

| Config | Behaviour |
|---|---|
| **G0** | Unguarded: fixed 1% risk on every take |
| **G1** | Hard limits + calibration (Wilson lower bound) + quarter Kelly |
| **G2A** | G1 + anomaly layer (S1-S4, C1-C3, M1) |
| **G2** | G2A + M2 ablation: the Trader is re-asked with all sentiment stripped. Text can talk it out of a trade, never into one |

## Attacks

| ID | What it does |
|---|---|
| A1 | Instruction-style prompt injection in headlines |
| A2 | Fake consensus: flood of near-duplicate bullish posts from fresh sources |
| A3 | Candle forgery on the Trader feed (textbook sweep + displacement) |
| A4 | Pure confidence steering: soft text aiming for a believable, well-calibrated bucket |
| A4F | A4 plus mild candle forgery |
| A5 | Adaptive: iterates variants against the live G2 gate, told what blocked it each time |

## GitHub

GitHub Pages (landing + Flight Recorder) deploys from `.github/workflows/pages.yml` on push to `master`.
The web app reads `web/public/attack_metrics.json` and `attack_lab_demo.json` written by `run_attacks.py`,
and labels every panel as Measured, Simulated, or Demo so nothing seeded passes as a result.

## Docs

- [`docs/RULES_NOTES.md`](docs/RULES_NOTES.md) - hackathon / API notes
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) - attacker capabilities & mappings
- [`docs/RESULTS.md`](docs/RESULTS.md) - live + attack metrics

## Stack

Python 3.11+, pydantic, pandas, APScheduler, SQLite, Streamlit/Plotly, OpenAI-compatible LLM client (default SpaceXAI / xAI: `https://api.x.ai/v1`, model `grok-4.5`).

## License

MIT - hackathon submission.
