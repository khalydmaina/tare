# Results

Measured on 12 Sep 2026. Trader model: `gemini-3.1-flash-lite` through Google AI Studio's
OpenAI-compatible endpoint. Scenario bank: `data/scenarios.jsonl`, 300 real setups from 10 USDT
perpetuals over 180 days, Bitget candles with OKX as the independent reference, each labelled
with what actually happened next. Calibration is walk-forward: the first 180 setups by time fill
the matrix, which is then frozen, and the attacks are evaluated on later setups only.

Reproduce with:

    LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
    LLM_MODEL=gemini-3.1-flash-lite \
    python scripts/run_attacks.py --llm real --scenarios data/scenarios.jsonl --max-eval 40 \
        --attacks A1,A3,A4,A4F --cache-only

The two variables matter even with no key: each cached answer is filed under the model and
endpoint that gave it, so without them the replay looks for another model's answers and finds none.

`--cache-only` replays the model's recorded answers from `data/llm_cache.json`, so the table can
be re-derived with no API key and no quota, and re-measured after a change to the Inspector
without changing what the model said. It refuses to write anything if an answer is missing, so a
partial cache cannot pass as a finished run. Drop the flag, with a key set, to call the model for
real. The `Attack suite` workflow does exactly this on a runner, which is where the published
numbers come from: this network reaches neither the exchanges nor the model reliably.

## 1. The pattern itself has no edge

Of the 300 recorded setups, 35% reached target before stop. Every reward-to-risk bucket sits at
or below the rate it needs to break even:

| Reward-to-risk | Setups | Hit rate | Breakeven | Edge |
|---|---|---|---|---|
| under 1.6 | 154 | 38% | 40% | -2 pts |
| 1.6 to 2.1 | 99 | 36% | 36% | 0 pts |
| 2.1 and above | 47 | 23% | 28% | -5 pts |

Average outcome is +0.07R per setup, carried by a few large winners rather than by hit rate, which
is a wash once fees and slippage are counted. Tempting subsets (one coin at +10 points, mornings at
+8) are all inside one standard error across 19 comparisons, so they are noise, not signal.

**This is the point of the project.** The setup finder only proposes; any edge has to come from the
model's selection, and the Inspector's job is to find out whether that selection is real before it
sizes anything.

## 2. The model's measured record

Over the 180-setup calibration split, the model chose to take **15** setups and skipped 165. Of
those takes, 4 of 14 in the 60-69 confidence band reached target (29%), plus a single 70-79 sample
that did.

No confidence bucket reaches the 20-sample threshold, so there is no measured p_cal, only the
0.35 prior. A prior is not a measurement, and there is nothing in it to size a position from, so
while a bucket is unmeasured the Inspector treats a trade there as exploration: a quarter of base
risk, two a day, and only on inputs the anomaly layer finds quiet (see section 4). A bucket that
reaches 20 samples and still shows no edge is vetoed outright.

That threshold matters more than it looks. Wilson's lower bound on 6 wins in 21 is 0.14, which
needs about 6:1 reward-to-risk to clear breakeven, and these setups do not offer it. So the
moment this bucket is measured, the gate will stop trading the model in it. The exploration
budget is what buys the measurement, cheaply, instead of trading 1% of equity on a guess.

## 3. Attacks

Harmful approval rate: the share of attacked setups the gate approved that then lost. Attack
success rate is in brackets: the share where the attack changed the outcome. 40 evaluation setups,
`gemini-3.1-flash-lite`, measured 12 Sep 2026.

| Attack | G0 no gate | G1 record only | G2A + anomaly layer | G2 full gate |
|---|---|---|---|---|
| Clean (no attack) | 0.17 | 0.17 | 0.17 | 0.17 |
| A1 prompt injection | 0.50 (0.40) | 0.50 (0.40) | 0.00 (0.00) | 0.00 (0.00) |
| A3 candle forgery | 0.33 (0.20) | 0.33 (0.20) | 0.00 (0.00) | 0.00 (0.00) |
| A4 confidence steering | **0.90 (0.88)** | 0.90 (0.88) | 0.43 (0.44) | 0.00 (0.00) |
| A4F steering + forgery | **0.90 (0.88)** | 0.90 (0.88) | 0.00 (0.00) | 0.00 (0.00) |

Read the A4 row first. Text written to flatter the model's own confidence takes it from a 17%
harmful approval rate to **90%**, and it is the cheapest attack to run: no forged prices, no fake
crowd, just persuasion. The anomaly layer alone cuts it to 43%. The full gate, which lets text
lower confidence but never raise it, cuts it to zero. A1, A3 and A4F all forge something the
anomaly layer can see, and it stops them outright.

G1 no longer differs from G0, and that is the cost of the exploration budget: while every bucket
is unmeasured, the calibration layer can only shrink a trade, not refuse it, so on its own it
blocks nothing. Everything G2 blocks here, it blocks with the anomaly layer and the ablation
probe. The earlier table, measured before the budget existed, showed G1 cutting A4 to 0.30; that
column was doing work the gate no longer asks of it.

Adding the budget also opened a hole, which is worth stating because it is the kind a red team
looks for: confidence steering works by pushing the stated confidence into a bucket nothing has
been measured in, which is exactly where the probe is willing to trade. A4 at the full gate went
from 0.00 to **0.30** the moment probes were allowed. Probes now require an anomaly score under
0.5, which closed it. On the eval set the separation is wide (clean probes 0.31-0.41, firing the
M1 check alone; A4's 0.60-0.66, firing S2, M1 and M2 together), but 0.5 was chosen from that
sample and needs rechecking as the set grows.

**A2, fake consensus, is missing from this table.** It stamped the wall-clock minute into its fake
sources, so its old measurement cannot be replayed and its 40 answers are not in the cache. It is
now anchored to the bar under decision, and its row returns on the next run with model quota.

## 4. What this does not yet show

- **On clean setups the full gate selects exactly what no gate selects.** Both approve the same 5
  of 40 setups; G2 differs only in sizing them at a quarter of the risk. So the clean row's
  -0.95% against the unguarded -3.80% is position sizing, not judgement: precisely a quarter. The
  gate's discrimination is demonstrated against attacks, and not yet against bad clean trades.
- **Every trade the probe approved lost.** 5 approvals, 0 of the 10 winning setups, 5 of the 30
  losers, -0.95% of equity risk-weighted. That is consistent with the 29% hit rate, but it is not
  yet evidence of anti-selection either: five losses in a row happen 24% of the time at this base
  rate. It is a record where there was none, which is what the budget was for.
- **A5, the adaptive attacker, has not run.** It writes a headline, sees which checks blocked it,
  and tries again, up to 6 times on each of 20 setups: at most about 260 model calls against a free tier
  of 500 a day that the live bot shares. Its headlines are now cached like the trader's answers,
  so once measured it replays with no key like every other row, and a failed attacker call stops
  the run instead of quietly substituting a scripted line.
- **Live paper trades are still thin.** The bot watches 22 coins every 15 minutes; the pattern
  fires roughly 1.7 times a day per 10 coins, and this model takes about 8% of what it sees.

## 5. Why fills are simulated rather than sent to the Bitget demo exchange

The demo exchange is wired up and works: `scripts/check_bitget_demo.py` opens a real demo position
with attached stop and target through the bot's own order code, reads it back off the exchange, and
closes it. It is not the book of record, and the measurements below are why. Both were taken on
12 Sep 2026 from a GitHub runner, and the comparison is reproducible with
`--compare-prices` on the `Bitget demo check` workflow.

- **The demo book is not the public market.** A test LTCUSDT short of 29,236 USDT notional filled at
  55.74 while LTC was 54.08 on the public market: 3.1% of adverse entry, against the 5 bps of
  slippage the book models, and it closed 1.3% away again seconds later. Across the watchlist the
  demo last price sat within 0.25% of public for 8 of 15 quoted symbols, but 5.05% away on LTC and
  5.32% on DOT. Outcomes are labelled by walking public candles, so a fill several percent off the
  public market makes the return, drawdown and Sharpe describe neither market.
- **The demo exchange does not list seven of the 22 symbols.** ZEC, SUI, ENA, WLD, ONDO, ARB and TAO
  USDT perps all answer `40034 Parameter <symbol> does not exist`, so every order on those coins is
  refused however good the setup. One of the two live proposals so far was WLDUSDT.

So `execution.fills` in `config/settings.yaml` is `sim`: every fill is priced off the same public
candles the labeler scores the outcome against, at 5 bps slippage and 4 bps fees, which is what the
300-scenario bank used. The choice is explicit rather than inherited from whether API keys happen to
be set, the status line names the destination (`fills=sim`), and `trades.csv` carries a `fill` column
per order. The handbook allows paper trading; this keeps the paper coherent.

The first live order exposed the reverse of this in the bot itself. Bitget refused it with HTTP 400,
the broker fell back to a simulated fill with only a warning, and the status kept reporting fills on
the demo account, because the keys were set. The refusal is now carried on the order, named in the
health line, and turns the cycle red.

## 6. Live paper account

Running since 11 Sep 2026 on GitHub Actions, one cycle every 15 minutes, fills simulated on public
candles with attached stop-loss and take-profit, every take also recorded in an unguarded shadow
book. Current figures, and the full log:

- https://tare-rust.vercel.app (Live tab)
- https://tare-rust.vercel.app/api/log (`?file=trades.csv`, `decisions.csv`, `shadow_trades.csv`, `equity.csv`)
