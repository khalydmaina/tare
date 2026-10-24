# tare paper trading log

Generated 2026-10-24 18:30 UTC by `scripts/export_paper_log.py` from the live bot's Flight Recorder.

- Bot status: `running` · gate=G2 llm=gemini-3.1-flash-lite fills=local-sim | last cycle 2026-10-24 18:30Z: 22/22 feeds ok, 0 setups, 0 orders
- Running since: 2026-09-11T19:25:48.414128+00:00
- Prompt versions: trader_v2

| Book | Return | Max drawdown | Sharpe (annualised, 15m marks) | Closed trades | Win rate |
|---|---|---|---|---|---|
| Guarded (Inspector sizes or vetoes) | +1.82% | 1.22% | 2.09 | 9 | 33% |
| Shadow (every take, no Inspector) | -3.11% | 7.89% | -1.18 | 26 | 35% |

Cycles 89135 · setups 138 · AI proposals 138 · takes 26 · vetoes 17 · orders 9

Files: `decisions.csv` (every AI proposal and the Inspector's verdict), `trades.csv` (guarded orders and outcomes), `shadow_trades.csv` (every take, unguarded), `equity.csv`.
