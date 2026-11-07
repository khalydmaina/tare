# tare paper trading log

Generated 2026-11-07 19:45 UTC by `scripts/export_paper_log.py` from the live bot's Flight Recorder.

- Bot status: `running` · gate=G2 llm=gemini-3.1-flash-lite fills=local-sim | last cycle 2026-11-07 19:45Z: 22/22 feeds ok, 0 setups, 0 orders
- Running since: 2026-09-11T19:25:48.414128+00:00
- Prompt versions: trader_v2

| Book | Return | Max drawdown | Sharpe (annualised, 15m marks) | Closed trades | Win rate |
|---|---|---|---|---|---|
| Guarded (Inspector sizes or vetoes) | +1.75% | 1.22% | 1.74 | 10 | 30% |
| Shadow (every take, no Inspector) | -8.93% | 12.23% | -3.01 | 33 | 27% |

Cycles 118637 · setups 181 · AI proposals 181 · takes 33 · vetoes 23 · orders 10

Files: `decisions.csv` (every AI proposal and the Inspector's verdict), `trades.csv` (guarded orders and outcomes), `shadow_trades.csv` (every take, unguarded), `equity.csv`.
