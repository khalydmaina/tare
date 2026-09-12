# Results

Measured on 12 Sep 2026. Trader model: `gemini-3.1-flash-lite` through Google AI Studio's
OpenAI-compatible endpoint. Scenario bank: `data/scenarios.jsonl`, 300 real setups from 10 USDT
perpetuals over 180 days, Bitget candles with OKX as the independent reference, each labelled
with what actually happened next. Calibration is walk-forward: the first 180 setups by time fill
the matrix, which is then frozen, and the attacks are evaluated on later setups only.

Reproduce with:

    python scripts/run_attacks.py --llm real --scenarios data/scenarios.jsonl --max-eval 40 \
        --attacks A1,A2,A3,A4,A4F

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
those takes, 3 of 14 in the 60-69 confidence band reached target (29%), plus a single 70-79 sample.

No confidence bucket reaches the 20-sample threshold, so the Inspector falls back to its cautious
0.35 prior. With that prior, only setups worth about 2.1 times their risk clear breakeven, and the
gate approves almost nothing. That is the honest state: **this model has not yet earned the right
to trade this pattern**, and the system says so instead of trading anyway.

## 3. Attacks

Harmful approval rate: the share of attacked setups the gate approved that then lost. Attack
success rate is in brackets: the share where the attack changed the outcome. 40 evaluation setups.

| Attack | G0 no gate | G1 record only | G2A + anomaly layer | G2 full gate |
|---|---|---|---|---|
| Clean (no attack) | 0.17 | 0.07 | 0.00 | 0.00 |
| A1 prompt injection | 0.50 (0.40) | 0.17 (0.11) | 0.00 (0.00) | 0.00 (0.00) |
| A2 fake consensus | 0.27 (0.12) | 0.13 (0.07) | 0.00 (0.00) | 0.00 (0.00) |
| A3 candle forgery | 0.33 (0.20) | 0.10 (0.04) | 0.00 (0.00) | 0.00 (0.00) |
| A4 confidence steering | **0.90 (0.88)** | 0.30 (0.25) | 0.07 (0.07) | 0.00 (0.00) |
| A4F steering + forgery | **0.90 (0.88)** | 0.30 (0.25) | 0.00 (0.00) | 0.00 (0.00) |

Read the A4 row first. Text written to flatter the model's own confidence takes it from a 17%
harmful approval rate to **90%**, and it is the cheapest attack to run: no forged prices, no fake
crowd, just persuasion. Checking the claim against the model's record cuts it to 30%. The anomaly
layer cuts it to 7%. The full gate, which lets text lower confidence but never raise it, cuts it
to zero.

On clean setups the unguarded book also loses 3.8% of equity across the evaluation window, while
the guarded book loses nothing.

## 4. What this does not yet show

- **The full gate approves nothing clean either.** With a record this thin, a gate that blocks
  every attack is not yet proof of discrimination: it has not been asked to let a good trade
  through. The number that matters next is how many clean trades survive once a confidence bucket
  has 20 or more samples.
- **A5, the adaptive attacker, has not run.** The free-tier daily quota was exhausted by the five
  static attacks. It runs on the next reset.
- **Live paper trades are still pending.** The bot watches 22 coins every 15 minutes; the pattern
  fires roughly 1.7 times a day per 10 coins, and this model takes about 8% of what it sees.

## 5. Live paper account

Running since 11 Sep 2026 on GitHub Actions, one cycle every 15 minutes, orders placed on a Bitget
demo account with attached stop-loss and take-profit, every take also recorded in an unguarded
shadow book. Current figures, and the full log:

- https://tare-rust.vercel.app (Live tab)
- https://tare-rust.vercel.app/api/log (`?file=trades.csv`, `decisions.csv`, `shadow_trades.csv`, `equity.csv`)
