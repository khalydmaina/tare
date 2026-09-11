# RULES_NOTES (Day-1 confirmations)

Fill these from the Bitget hackathon rules page / Discord. Defaults below are assumptions used in code until confirmed.

## Scoring

- [ ] Confirm paper-trading metrics (Sharpe, max DD, win rate) weight in score
- [ ] Confirm whether judges read Bitget account directly or self-reported `RESULTS.md`

**Assumption in this repo:** paper metrics matter → keep `run_live.py` up on a VPS early.

## Submission

- [ ] Repo URL format
- [ ] Demo video length limit (spec assumes ~3 minutes)
- [ ] Write-up length
- [ ] Required demo link (dashboard public URL)

## Paper trading (Bitget)

- [ ] Agentic / demo sub-account setup steps
- [ ] Demo API key scopes
- [ ] Symbol naming on demo (code uses `BTCUSDT`, `ETHUSDT`, `SOLUSDT` + `USDT-FUTURES`)
- [ ] Rate limits
- [ ] Supported order types (code assumes market + attached SL/TP)

**Env vars:** `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_PASSPHRASE`

Without keys, `PaperBroker` simulates fills locally so the pipeline still runs.

## LLM access

- [ ] Hackathon-provided endpoint / quota (if any)
- Exact model ID must come from the endpoint's model list

**Current default (SpaceXAI / xAI OpenAI-compatible):**

| Field | Value |
|---|---|
| Base URL | `https://api.x.ai/v1` |
| Model | `grok-4.5` |
| Key env | `XAI_API_KEY` |

Switch provider by editing `config/settings.yaml` (`llm.base_url`, `llm.model`, `llm.api_key_env`).

## Results reporting

- [ ] Official: exchange-read vs self-report
- Flight Recorder SQLite + `docs/RESULTS.md` support self-report either way
