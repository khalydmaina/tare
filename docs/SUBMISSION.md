# Submission draft (Bitget AI Hackathon S2)

Deadline: 21 Sep 2026, 23:59 UTC+8. Fields follow the Google Form. Anything in `[brackets]` gets filled in once measured; never submit a placeholder.

## Track

**Agentic Trading → Open Theme** (a risk-controlled trading agent that doubles as an agent evaluation benchmark)

## Project Description

**1. Thesis.** An LLM trader is most dangerous exactly when it sounds most sure. Ours said 60 to 69% on 14 real setups and was right on 4 of them (29%), and a few flattering lines of text were enough to make it take 90% of the losing setups it was shown. tare lets the LLM decide take or skip and state a probability, then a non-LLM Inspector weighs that claim against the model's own measured track record, independent market data from a second exchange, and hard limits the model cannot edit. It sizes, shrinks or vetoes every trade. We do not ask a second model to review the first, because a peer model shares its blind spots and fails at the same moments.

**2. Target user.** Teams and quant traders who want to run LLM trading agents with real money but need a risk layer they can audit: every proposal, veto and counterfactual is recorded, and the brakes tighten precisely where the model has proven unreliable, including when someone feeds it manipulated news or forged candles.

**3. Validation data.**
- Scenario bank: 300 real setups from 10 USDT perpetuals over 180 days (Bitget candles, OKX as the independent reference), each labelled with what actually happened next. The raw pattern has no edge on its own: 35% of setups reach target first, and every reward-to-risk bucket sits at or below its breakeven rate. Whatever edge exists has to come from the model's selection, which is what the calibration measures.
- Attack evaluation with the real model on 40 later setups: harmful approval rate (losing setups approved) under 4 gate settings for 6 attacks: prompt injection, fake consensus, candle forgery, confidence steering, steering plus forgery, and an adaptive attacker that rewrites its headline after reading which checks blocked it. Headline: confidence steering, pure persuasion with no forged data, is the strongest attack. It lifts harmful approvals from 17% to 90% with no gate; the anomaly layer alone cuts that to 43%, and the full gate G2 to 0%. Every attack that forges something (injection, candles) is stopped outright by the anomaly layer. The honest limit: on clean setups G2 approves the same 5 of 40 that no gate does, at a quarter of the risk, so its judgement is shown against attacks and not yet against bad clean trades. The red team also found the gate's weak spot: the adaptive attacker got 1 of 12 losing setups through the full gate with one believable headline that cancelled out cautious news, and fake consensus got 1 of 25 through, both only as quarter-risk exploration trades.
- Paper trading log (run during the competition): [return, max drawdown, Sharpe, win rate, trades], guarded book versus an unguarded shadow book on the same setups.

**4. Progress.** Working end to end: SMC setup finder, LLM trader, Inspector (calibration, anomaly checks, news-removed re-ask, hard limits), guarded and shadow books, Flight Recorder (SQLite), website and Streamlit dashboard, attack suite, 94 automated tests. The live paper bot runs every 15 minutes on GitHub Actions over 22 USDT perpetuals and publishes its log to the `paper-log` branch and to the website. Fills are simulated on public Bitget candles at 5 bps slippage and 4 bps fees: the demo exchange is wired up and verified, but it does not list 7 of the 22 symbols and filled a test order 3% away from the public market, so a demo-filled book could not be scored against the candles the outcomes are labelled on (docs/RESULTS.md section 5).

**5. Deliverables.** Live website (landing page plus Flight Recorder with Live, Attack Lab and Results), paper trading log, results report (`docs/RESULTS.md`), [demo video], source repository.

**6. AI Trading take.** Confidence is a claim, not a size. Agents should be judged by their record, and text they read should be allowed to talk them out of a trade but never into one.

## Role of the LLM in your project

- **Model:** gemini-3.1-flash-lite through Google AI Studio's OpenAI-compatible endpoint, used for both the live bot and the attack evaluation, so the measured track record describes the model that actually trades.
- **What it does:** for each setup the SMC scanner finds, the LLM reads the setup, recent candles on 15m/1h/4h and the news digest, and returns take or skip plus its probability that take-profit is hit before stop-loss. It cannot change entry, stop, target or size.
- **What it does not do:** it never sizes, vetoes or reviews itself. The Inspector is deterministic code. When the LLM wants to take a trade, the Inspector asks it again with the news removed; if it would skip without the news, the trade is vetoed, otherwise the lower confidence is used.
- **Also used for:** the adaptive attacker (A5), which writes a headline, sees which checks blocked it, and tries again against the full gate.

## Event → decision → execution flow

1. A 15-minute candle closes on Bitget (22 USDT perpetuals).
2. Positions that hit take-profit, stop-loss or the 12-hour limit are closed and recorded; shadow outcomes update the calibration record.
3. The SMC scanner looks for a liquidity sweep, displacement and a return to the zone on the latest closed candle.
4. The LLM proposes take or skip with a probability.
5. The Inspector checks hard limits, tampering signals (injected instructions, fake crowds, prices that disagree with OKX, stale feeds), re-asks without the news, and looks up the calibrated probability for that confidence range. If the record beats breakeven there it sizes with quarter Kelly capped at 1% risk. If it has fewer than 20 outcomes at that confidence there is nothing to size from, so the trade is exploration instead: a quarter of base risk, twice a day, and only on inputs the tampering checks find quiet, because confidence steering aims at exactly those unmeasured buckets. Once a bucket has 20 outcomes and still shows no edge, it is vetoed.
6. Approved or shrunk trades are filled with their stop-loss and take-profit attached, priced off the same public candles the outcome labeler walks; every take, approved or not, also opens in the shadow book. The same order code places real orders on the Bitget demo exchange (`scripts/check_bitget_demo.py`), which is how that path stays verified.
7. Everything lands in the Flight Recorder, the paper log, the dashboard and the website.

## Submission Materials Link (one field)

- Demo and live paper account: https://tare-rust.vercel.app
- Paper trading log: https://tare-rust.vercel.app/api/log (`?file=trades.csv`, `decisions.csv`, `shadow_trades.csv`, `equity.csv`)
- Results: https://tare-rust.vercel.app/api/log?file=RESULTS.md (the attack table is also on the site's Results tab)
- Repo: https://github.com/khalydmaina/tare (private; access for judges on request)
- Video: [link]

## X post (required; must include #BitgetHackathon and @Bitget_AI)

> My AI trader said 60-69% sure on 14 real setups. It was right on 4. So I built tare: a non-LLM referee that checks every trade against the model's own record and blocks news-steered trades. Live paper log + attack lab: https://tare-rust.vercel.app #BitgetHackathon @Bitget_AI
