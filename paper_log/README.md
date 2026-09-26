# tare paper trading log

Generated 2026-09-26 18:45 UTC by `scripts/export_paper_log.py` from the live bot's Flight Recorder.

- Bot status: `running` · gate=G2 llm=gemini-3.1-flash-lite fills=local-sim | last cycle 2026-09-26 18:45Z: 22/22 feeds ok, 0 setups, 0 orders
- Running since: 2026-09-11T19:25:48.414128+00:00
- Prompt versions: trader_v2

| Book | Return | Max drawdown | Sharpe (annualised, 15m marks) | Closed trades | Win rate |
|---|---|---|---|---|---|
| Guarded (Inspector sizes or vetoes) | +1.96% | 0.91% | 3.85 | 7 | 43% |
| Shadow (every take, no Inspector) | +1.34% | 4.93% | 1.23 | 16 | 44% |

Cycles 30418 · setups 56 · AI proposals 56 · takes 17 · vetoes 10 · orders 7

Files: `decisions.csv` (every AI proposal and the Inspector's verdict), `trades.csv` (guarded orders and outcomes), `shadow_trades.csv` (every take, unguarded), `equity.csv`.
