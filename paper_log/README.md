# tare paper trading log

Generated 2026-11-14 10:07 UTC by `scripts/export_paper_log.py` from the live bot's Flight Recorder.

- Bot status: `running` · gate=G2 llm=gemini-3.1-flash-lite fills=local-sim | last cycle 2026-11-14 10:07Z: 22/22 feeds ok, 0 setups, 0 orders
- Running since: 2026-09-11T19:25:48.414128+00:00
- Prompt versions: trader_v2

| Book | Return | Max drawdown | Sharpe (annualised, 15m marks) | Closed trades | Win rate |
|---|---|---|---|---|---|
| Guarded (Inspector sizes or vetoes) | +1.75% | 1.22% | 1.69 | 10 | 30% |
| Shadow (every take, no Inspector) | -9.94% | 13.21% | -3.25 | 34 | 26% |

Cycles 126469 · setups 199 · AI proposals 199 · takes 34 · vetoes 24 · orders 10

Files: `decisions.csv` (every AI proposal and the Inspector's verdict), `trades.csv` (guarded orders and outcomes), `shadow_trades.csv` (every take, unguarded), `equity.csv`.
