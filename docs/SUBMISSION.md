# Submission draft (Bitget AI Hackathon S2)

Deadline: 21 Sep 2026, 23:59 UTC+8. Fields follow the Google Form. Anything in `[brackets]` gets filled in once measured; never submit a placeholder.

## Track

**Agentic Trading → Open Theme** (a risk-controlled trading agent that doubles as an agent evaluation benchmark)

## Project Description

**1. Thesis.** An LLM trader is most dangerous exactly when it sounds most sure. When it says 90%, its record may say [41%]. tare lets the LLM decide take or skip and state a probability, then a non-LLM Inspector weighs that claim against the model's own measured track record, independent market data from a second exchange, and hard limits the model cannot edit. It sizes, shrinks or vetoes every trade. We do not ask a second model to review the first, because a peer model shares its blind spots and fails at the same moments.

**2. Target user.** Teams and quant traders who want to run LLM trading agents with real money but need a risk layer they can audit: every proposal, veto and counterfactual is recorded, and the brakes tighten precisely where the model has proven unreliable, including when someone feeds it manipulated news or forged candles.

**3. Validation data.**
- Scenario bank: [N] real setups from [10] USDT perpetuals over [180] days (Bitget candles, OKX as the independent reference), each labelled with what actually happened next.
- Attack evaluation with the real model: harmful approval rate for 6 attacks (prompt injection, fake consensus, candle forgery, confidence steering, steering plus forgery, adaptive attacker) under 4 gate settings. Headline: [G1 approved X% of steered losing trades; the full gate G2 approved Y%].
- Paper trading log (run during the competition): [return, max drawdown, Sharpe, win rate, trades], guarded book versus an unguarded shadow book on the same setups.

**4. Progress.** Working end to end: SMC setup finder, LLM trader, Inspector (calibration, anomaly checks, news-removed re-ask, hard limits), guarded and shadow books, Flight Recorder (SQLite), website and Streamlit dashboard, attack suite, [58] automated tests. The live paper bot runs every 15 minutes on GitHub Actions and publishes its log to the `paper-log` branch.

**5. Deliverables.** Public repo, live website (landing page plus Flight Recorder with Live, Attack Lab and Results), paper trading log, results report (`docs/RESULTS.md`), [demo video].

**6. AI Trading take.** Confidence is a claim, not a size. Agents should be judged by their record, and text they read should be allowed to talk them out of a trade but never into one.

## Role of the LLM in your project

- **Models:** [openai/gpt-oss-120b on Groq for the live bot; qwen3.8-max via the hackathon endpoint for the attack evaluation].
- **What it does:** for each setup the SMC scanner finds, the LLM reads the setup, recent candles on 15m/1h/4h and the news digest, and returns take or skip plus its probability that take-profit is hit before stop-loss. It cannot change entry, stop, target or size.
- **What it does not do:** it never sizes, vetoes or reviews itself. The Inspector is deterministic code. When the LLM wants to take a trade, the Inspector asks it again with the news removed; if it would skip without the news, the trade is vetoed, otherwise the lower confidence is used.
- **Also used for:** the adaptive attacker (A5) generates attack variants against the full gate.

## Event → decision → execution flow

1. A 15-minute candle closes on Bitget (10 USDT perpetuals).
2. Positions that hit take-profit, stop-loss or the 12-hour limit are closed and recorded; shadow outcomes update the calibration record.
3. The SMC scanner looks for a liquidity sweep, displacement and a return to the zone on the latest closed candle.
4. The LLM proposes take or skip with a probability.
5. The Inspector checks hard limits, tampering signals (injected instructions, fake crowds, prices that disagree with OKX, stale feeds), re-asks without the news, looks up the calibrated probability for that confidence range, and sizes with quarter Kelly capped at 1% risk.
6. Approved or shrunk trades are placed on the paper book with attached stop-loss and take-profit; every take, approved or not, also opens in the shadow book.
7. Everything lands in the Flight Recorder, the paper log, the dashboard and the website.

## Submission Materials Link (one field)

- Repo: https://github.com/khalydmaina/tare [make public before submitting]
- Demo: [https://khalydmaina.github.io/tare/]
- Paper trading log: https://github.com/khalydmaina/tare/tree/paper-log/paper_log
- Results: https://github.com/khalydmaina/tare/blob/main/docs/RESULTS.md
- Video: [link]

## X post (required; must include #BitgetHackathon and @Bitget_AI)

> My AI trader says it's 90% sure. Its own record says [41%]. So I built tare: a non-LLM referee that weighs every trade against the model's track record, cross-checks prices, and blocks news-steered trades. Live paper log + attack lab: [link] #BitgetHackathon @Bitget_AI
