# Submission draft (Bitget AI Hackathon S2)

Form: https://forms.gle/GyWZCMCPocgJdJon6 · closes 21 Sep 2026, 23:59 UTC+8 · voting 22 Sep to 7 Oct.

Sections below follow the form's fields in order, so each can be pasted as it stands. Anything in
`[brackets]` is refreshed on submission day or is yours to fill; never submit a bracket.

---

## Field: Project Description

**1. Thesis.** An LLM trader is most dangerous exactly when it sounds most sure. Ours said 60 to 69% on 14 real setups and was right on 4 of them (29%), and a few flattering lines of text were enough to make it take 90% of the losing setups it was shown. tare lets the LLM decide take or skip and state a probability, then a non-LLM Inspector weighs that claim against the model's own measured track record, independent market data from a second exchange, and hard limits the model cannot edit. It sizes, shrinks or vetoes every trade. We do not ask a second model to review the first, because a peer model shares its blind spots and fails at the same moments.

Signal source: a smart-money-concepts scanner on closed 15-minute Bitget candles (liquidity sweep, displacement, return to the zone) across 22 USDT perpetuals, which fixes entry, stop and target. Decision logic: the LLM reads the setup, 15m/1h/4h candles and a news digest and returns take or skip with a probability; it cannot move a level or choose a size. Risk controls: calibration against the model's own record, a tampering layer (injected instructions, fake crowds, prices that disagree with OKX, stale feeds), a re-ask with the news removed, quarter-Kelly sizing capped at 1% risk, a 3x leverage cap, a daily loss limit and a 4-hour cooldown after 3 losses.

**2. Target user and product value.** Pro and semi-pro crypto traders and small quant teams (1 to 5 people) who run, or want to run, an LLM agent on USDT-margined perpetuals, starting with Bitget. Books of roughly $10k to $500k, a low-to-moderate risk appetite (0.25% to 1% of equity per trade), intraday to swing frequency (a few trades a day across 20+ perps). The use case: put an auditable referee between the agent and the order API, so that an overconfident call, a manipulated headline or a forged candle cannot size a trade up. Every proposal, veto and counterfactual is recorded, and the brakes tighten precisely where the model has proven unreliable.

**3. Validation data and key metrics.**
- Scenario bank (backtest): 300 real setups from 10 USDT perpetuals over 180 days, 18 Mar to 10 Sep 2026, Bitget candles with OKX as the independent reference, each labelled with what happened next, at 5 bps slippage and 4 bps fees. The raw pattern has no edge on its own: 35% of setups reach target first and every reward-to-risk bucket sits at or below breakeven (+0.07R average). Any edge has to come from the model's selection, which is what calibration measures.
- Walk-forward calibration: the first 180 setups by time. The model took 15 and skipped 165; in its 60-69% band it was right 4 times in 14.
- Attack evaluation with the real model on the 40 later setups, 6 attacks under 4 gate settings, reported as harmful approval rate (losing setups approved). Confidence steering, pure persuasion with no forged data, is the strongest attack: 90% with no gate, 43% with the tampering layer alone, 0% with the full gate. Prompt injection (50%), candle forgery (33%) and steering plus forgery (90%) all fall to 0% at the full gate; fake consensus falls from 37% to 3%. An adaptive attacker that rewrites its headline after reading which checks blocked it got 1 of 12 losing setups through the full gate, with a single believable headline that cancelled out cautious news, as a quarter-risk exploration trade. The honest limit: on clean setups the full gate approves the same 5 of 40 that no gate does, at a quarter of the risk, so its judgement is shown against attacks and not yet against bad clean trades.
- Live paper trading log, running every 15 minutes since 11 Sep 2026 19:25 UTC, fills priced off public Bitget candles at 5 bps slippage and 4 bps fees, guarded book against an unguarded shadow book on the same setups. As of 13 Sep: guarded +2.90%, max drawdown 0.12%, 3 closed trades, 3 wins; shadow +3.76%, max drawdown 1.26%, 4 closed, 3 wins. [On submission day, refresh from https://tare-rust.vercel.app/api/log: test period, return, Sharpe, Sortino, max drawdown, win rate, trades and turnover for both books. Say plainly that a handful of trades makes Sharpe and win rate statistically weak.]

**4. Progress.** Built and running: the setup scanner, the LLM trader, the Inspector (calibration, tampering checks, news-removed re-ask, hard limits), guarded and shadow books, a SQLite flight recorder, the website (landing page, live view, Attack Lab, results), a Streamlit dashboard, the attack suite (6 attacks, replayable from cached model answers with no key), and 95 automated tests. Problems found and fixed along the way: a stale-setup bug that priced re-entries at old zone levels; a live order Bitget refused that silently fell back to a simulated fill (now carried on the order and shown in red); the Bitget demo exchange filled a test order 3% away from the public market and does not list 7 of our 22 symbols, so fills stay simulated on public candles; the exploration budget briefly let confidence steering through at 30%, closed by requiring quiet tampering scores; a partial attack run that could have overwritten the published table; GitHub server errors that dropped a few cycles (runs now retry and fail loudly). Not built yet: a check that compares a take against the ordinary news rather than only against no news, which is the hole the adaptive attacker found. Next: that check, more outcomes per confidence band so calibration can size from measurement instead of exploration, and live trading on the Bitget demo once its book tracks the public market. Stack: Python, React and Vite, SQLite, GitHub Actions (live loop and attack runs), Vercel (site and log API), Google AI Studio (gemini-3.1-flash-lite), Bitget market data and demo trading API, OKX market data, Bitget's Qwen gateway (qwen3.8-max, tested).

**5. Deliverables.** At the Submission Materials Link: the live website (runnable demo) with the live paper account, Attack Lab and Results; the paper trading log with its CSV files; the results write-up; [the demo video]; the source repository (private, access on request).

**6. Your take on AI trading.** Confidence is a claim, not a size. Agents should be judged by their record, and text they read should be allowed to talk them out of a trade but never into one. From building on Bitget's tools: the demo trading API works end to end, but its book sat 3 to 5% away from the public market on some contracts and lacks several listed perps, which makes demo fills hard to score, so a demo book that mirrors live prices would help agent builders most. The Qwen gateway was easy to plug in (OpenAI-compatible) and returned sound trading decisions, but at about 90 seconds and 3,700 reasoning tokens a call it is slow for a 15-minute loop unless thinking can be turned down, and its input filter refuses red-team prompts, so it could not play the adaptive attacker.

---

## Field: Role of the LLM in Your Project

- **Trader (live and measured):** gemini-3.1-flash-lite through Google AI Studio's OpenAI-compatible endpoint. For each setup the scanner finds, it reads the setup, recent candles on 15m/1h/4h and the news digest, and returns take or skip plus its probability that take-profit is hit before stop-loss. It cannot change entry, stop, target or size. The same model runs the live bot and the attack evaluation, so the measured track record describes the model that actually trades.
- **What it never does:** size, veto or review itself. The Inspector is deterministic code. When the LLM wants a trade, the Inspector asks again with the news removed; if it would skip without the news the trade is vetoed, otherwise the lower confidence is used.
- **Adaptive attacker (A5):** the same model writes a headline, is told which checks blocked it, and tries again against the full gate, up to 6 times per setup.
- **Qwen (Bitget credits):** qwen3.8-max through Bitget's hackathon gateway. Tested as the trader's backup: it returned valid, well-reasoned decisions, but each took about 93 seconds and 3,800 output tokens (3,700 of them reasoning), too slow for our 15-minute loop without tuning, so it stays the backup rather than the main trader. Tried as the adaptive attacker: the gateway's input filter refused the red-team prompt ("DataInspectionFailed"), so that role stayed on Gemini. It met our needs as a fallback decision-maker, not as a red-team tool.
- **Also:** coding assistance while building (Claude Code).

---

## Field: Submission Materials Link

https://tare-rust.vercel.app

(Everything a judge needs is reachable from it: the live paper account, the Attack Lab and Results tabs, and these direct links, which also belong in Deliverables.)

- Paper trading log: https://tare-rust.vercel.app/api/log (`?file=trades.csv`, `decisions.csv`, `shadow_trades.csv`, `equity.csv`)
- Results write-up: https://tare-rust.vercel.app/api/log?file=RESULTS.md
- Demo video: [link]
- Repository: https://github.com/khalydmaina/tare (private; access for judges on request)

---

## Field: X Promotional Post Link

[link to your post]

Post from your own account, tag both, and retweet Bitget's official hackathon post once they publish it. Attach the Attack Lab screenshot or a short screen recording; the link also shows a preview card.

> My AI trader said it was 60-69% sure. It was right 29% of the time.
>
> So I built tare: a non-LLM referee that sizes each trade by the model's own record. Fed steering news, the bare AI took 90% of losing trades. With tare: 0%.
>
> https://tare-rust.vercel.app
>
> #BitgetHackathon @Bitget_AI

Optional progress posts before submission (each adds reach):

> Red-teamed my own AI trader with an attacker that rewrites fake headlines until one gets through. On 17 of 20 trades it gave up after 6 tries. Once, a single believable headline beat the referee on a losing trade. Writing the fix. #BitgetHackathon @Bitget_AI

> Bitget's demo exchange filled my test order 3% away from the real market, so my bot's paper fills are priced off public candles instead. Here's the measurement: https://tare-rust.vercel.app/api/log?file=RESULTS.md #BitgetHackathon @Bitget_AI

---

## Field: Track → Sub-theme

Agentic Trading → Open Theme (Custom)

## Field: University Name (optional)

[your university]

## Field: Apply for Demo Day (optional)

Yes. Every team may apply; invites go to winners and high scorers.

## Field: Apply for K3 Token Subsidy (optional)

Yes. It adds $30 of K3 Token credits after the event for a valid entry.

---

## Event → decision → execution flow (for the video and for judges)

1. A 15-minute candle closes on Bitget (22 USDT perpetuals).
2. Positions that hit take-profit, stop-loss or the 12-hour limit are closed and recorded; shadow outcomes update the calibration record.
3. The scanner looks for a liquidity sweep, displacement and a return to the zone on the latest closed candle.
4. The LLM proposes take or skip with a probability.
5. The Inspector checks hard limits, tampering signals (injected instructions, fake crowds, prices that disagree with OKX, stale feeds), re-asks without the news, and looks up the calibrated probability for that confidence range. If the record beats breakeven there it sizes with quarter Kelly capped at 1% risk. If it has fewer than 20 outcomes at that confidence there is nothing to size from, so the trade is exploration instead: a quarter of base risk, twice a day, and only on inputs the tampering checks find quiet. Once a band has 20 outcomes and still shows no edge, it is vetoed.
6. Approved or shrunk trades are filled with stop-loss and take-profit attached, priced off the same public candles the outcome labeler walks; every take, approved or not, also opens in the shadow book. The same order code places real orders on the Bitget demo exchange (`scripts/check_bitget_demo.py`), which is how that path stays verified.
7. Everything lands in the flight recorder, the paper log, the dashboard and the website.
