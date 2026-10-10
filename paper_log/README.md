# tare paper trading log

Generated 2026-10-10 22:30 UTC by `scripts/export_paper_log.py` from the live bot's Flight Recorder.

- Bot status: `running` · gate=G2 llm=gemini-3.1-flash-lite fills=local-sim | last cycle 2026-10-10 22:30Z: 22/22 feeds ok, 0 setups, 0 orders
- Running since: 2026-09-11T19:25:48.414128+00:00
- Prompt versions: trader_v2

| Book | Return | Max drawdown | Sharpe (annualised, 15m marks) | Closed trades | Win rate |
|---|---|---|---|---|---|
| Guarded (Inspector sizes or vetoes) | +1.66% | 1.20% | 2.33 | 8 | 38% |
| Shadow (every take, no Inspector) | -2.71% | 6.23% | -1.32 | 22 | 36% |

Cycles 60205 · setups 97 · AI proposals 97 · takes 22 · vetoes 14 · orders 8

Files: `decisions.csv` (every AI proposal and the Inspector's verdict), `trades.csv` (guarded orders and outcomes), `shadow_trades.csv` (every take, unguarded), `equity.csv`.
