# Submission draft (Bitget AI Base Camp Hackathon S2)

Form: https://forms.gle/GyWZCMCPocgJdJon6 - a Google Form with **20 fields**, not the 9 in our
earlier notes. Re-read live on 18 Sep 2026; every field below is in the form's real order.

**Deadline: before midnight 27 Sep 2026 (UTC+8)** = 17:00 on 27 Sep in Lagos (UTC+1).
The 20/21 Sep date in our earlier notes was wrong; the handbook's summary table, timeline, step
list and submission-requirements section all say 9/27. Judge review 22 Sep to 7 Oct, public voting
opens after the deadline, winners announced 8 Oct. The bot has to keep running through all of it.

Anything in `[brackets]` is yours to fill. Never submit a bracket.

---

## 1. Team Name *(required)*

[your team name]

Solo builders may use their own name or the project name, so `tare` works.

## 2. Team Lead Bitget UID, numbers only *(required)*

[your Bitget UID, digits only]

Bitget app or web, Profile, shown under your avatar. Used for eligibility checks.

## 3. Team Lead Email *(required)*

mainakhalid18@gmail.com

## 4. Team Lead Contact, Telegram handle or other *(required)*

[@your_telegram]

Telegram preferred. If you have none, the form accepts an X handle: @cipher_k1

## 5. Member Background *(required, checkboxes)*

[tick what applies] - Student · Developer · Researcher · Trader · Entrepreneur · Other

## 6. University Name *(optional)*

[your university, or leave blank]

Filling it enters the University Special Award pool. Blank if you are not applying.

## 7. Apply for Demo Day *(optional)*

Yes, I would like to apply

## 8. How did you hear about this event? *(required, checkboxes)*

[tick what applies] - Twitter / X · Telegram · Discord · University Announcement · Friend/Colleague · Other

## 9. Competition Track *(required, dropdown)*

Agentic Trading

## 10. Competition Sub-theme *(required, short text)*

Open Theme (Custom)

The five named sub-themes are Event-Driven, Market Sentiment, Earnings-Driven, Cross-Asset Execution
and Factor Discovery. tare is a risk layer underneath an agent rather than any of those, so Open
Theme is the honest fit. Trade-off: named sub-themes have 15 slots at 500 USDT; Open Theme competes
for the Grand Prize and the Open pool instead.

## 11. Project Name *(required)*

tare

## 12. One-line Project Summary *(required, hard limit 140 characters)*

An AI proposes trades. A non-LLM referee sizes or vetoes each one from the model's measured track record. Steering news: 90% harmful to 0%.

(139 characters.)

## 13. Project Description *(required)*

The form asks for five parts and says explicitly: "Do not repeat your deliverables list here."
The deliverables now live only in field 14.

**Part 1 - Thesis.** An LLM trader is most dangerous exactly when it sounds most sure. Ours said 60 to 69% on 14 real setups and was right on 4 of them (29%), and a few flattering lines of text were enough to make it take 90% of the losing setups it was shown. tare lets the LLM decide take or skip and state a probability, then a non-LLM Inspector weighs that claim against the model's own measured track record, independent market data from a second exchange, and hard limits the model cannot edit. It sizes, shrinks or vetoes every trade. We do not ask a second model to review the first, because a peer model shares its blind spots and fails at the same moments.

Signal source: a smart-money-concepts scanner on closed 15-minute Bitget candles (liquidity sweep, displacement, return to the zone) across 22 USDT perpetuals, which fixes entry, stop and target. Decision logic: the LLM reads the setup, 15m/1h/4h candles and a news digest and returns take or skip with a probability; it cannot move a level or choose a size. Risk controls: calibration against the model's own record, a tampering layer (injected instructions, fake crowds, prices that disagree with OKX, stale feeds), a re-ask with the news removed, quarter-Kelly sizing capped at 1% risk, a 3x leverage cap, a daily loss limit and a 4-hour cooldown after 3 losses.

**Part 2 - Target user and product value.** Pro and semi-pro crypto traders and small quant teams (1 to 5 people) who run, or want to run, an LLM agent on USDT-margined perpetuals, starting with Bitget. Books of roughly $10k to $500k, a low-to-moderate risk appetite (0.25% to 1% of equity per trade), intraday to swing frequency (a few trades a day across 20+ perps). The use case: put an auditable referee between the agent and the order API, so that an overconfident call, a manipulated headline or a forged candle cannot size a trade up. Every proposal, veto and counterfactual is recorded, and the brakes tighten precisely where the model has proven unreliable.

**Part 3 - Validation data and key metrics.**
- Scenario bank (backtest): 300 real setups from 10 USDT perpetuals over 180 days, 18 Mar to 10 Sep 2026, Bitget candles with OKX as the independent reference, each labelled with what happened next, at 5 bps slippage and 4 bps fees. The raw pattern has no edge on its own: 35% of setups reach target first and every reward-to-risk bucket sits at or below breakeven (+0.07R average). Any edge has to come from the model's selection, which is what calibration measures.
- Walk-forward calibration: the first 180 setups by time. The model took 15 and skipped 165; in its 60-69% band it was right 4 times in 14.
- Attack evaluation with the real model on the 40 later setups, 6 attacks under 4 gate settings, reported as harmful approval rate (losing setups approved). Confidence steering, pure persuasion with no forged data, is the strongest attack: 90% with no gate, 43% with the tampering layer alone, 0% with the full gate. Prompt injection (50%), candle forgery (33%) and steering plus forgery (90%) all fall to 0% at the full gate; fake consensus falls from 37% to 3%. An adaptive attacker that rewrites its headline after reading which checks blocked it got 1 of 12 losing setups through the full gate, with a single believable headline that cancelled out cautious news, as a quarter-risk exploration trade. The honest limit: on clean setups the full gate approves the same 5 of 40 that no gate does, at a quarter of the risk, so its judgement is shown against attacks and not yet against bad clean trades.
- Live paper trading log, running every 15 minutes since 11 Sep 2026 19:25 UTC, fills priced off public Bitget candles at 5 bps slippage and 4 bps fees, guarded book against an unguarded shadow book on the same setups. Test period 11 Sep 19:25 UTC to 18 Sep 14:00 UTC 2026 (6.8 days, 644 equity marks per book): guarded +1.96%, annualised Sharpe 5.83, Sortino 21.13, max drawdown 0.91%, 7 closed trades, 43% win rate, turnover 6.4x starting equity; shadow -1.36%, Sharpe -1.76, Sortino -2.24, max drawdown 4.93%, 9 closed trades, 33% win rate, turnover 19.7x. The gap between the books is the Inspector: it vetoed 3 of 10 takes and all three lost in the shadow book (two closed at -1R, one still open), and it cut every uncalibrated take to a quarter of base risk, so the losses both books shared cost the guarded book about a fifth as much. Stated plainly: 7 and 9 closed trades over one week are far too few for Sharpe, Sortino or win rate to be statistically meaningful. They describe this week, not a proven edge; the attack evaluation on 40 setups is the stronger evidence.
- How we would prove the product is used or distributed, labelled as the form asks. **Activation (targeted):** 10 teams running the Inspector in front of their own agent within 90 days of release; observed today is 0, because it is not released. **Trading volume (observed):** in the first week the shadow book pushed $196k of notional through the referee across 10 takes, of which $64k reached the exchange after sizing, so the referee cut gross exposure by 67%. **AUM (not applicable):** the book is paper, funded at a notional $10,000. **Retention (targeted):** an operator leaves it in front of their agent for 30 consecutive days. **Incremental fee (targeted):** a flat per-seat fee, deliberately not a share of volume, so the referee can never earn more by approving more. **Risk (observed, and the metric we actually optimise):** max drawdown of the guarded book against the unguarded book on identical setups, 0.91% against 4.93% this week.
- Every figure above is **observed** unless marked otherwise. Backtest and attack figures were measured 12-13 Sep 2026 and are reproducible from the repo; live figures were read from the running bot at 18 Sep 2026 14:00 UTC. Costs are inside every number rather than netted off afterwards: 5 bps slippage and 4 bps fees on each fill, in the backtest and in the paper book. Funding is not modelled, which flatters holds longer than 8 hours; the median trade is held 6 bars (90 minutes), so the effect is small but not zero.

**Part 4 - Progress.** Built and running: the setup scanner, the LLM trader, the Inspector (calibration, tampering checks, news-removed re-ask, hard limits), guarded and shadow books, a SQLite flight recorder, the website (landing page, live view, Attack Lab, results), a Streamlit dashboard, the attack suite (6 attacks, replayable from cached model answers with no key), and 95 automated tests. Problems found and fixed along the way: a stale-setup bug that priced re-entries at old zone levels; a live order Bitget refused that silently fell back to a simulated fill (now carried on the order and shown in red); the Bitget demo exchange filled a test order 3% away from the public market and does not list 7 of our 22 symbols, so fills stay simulated on public candles; the exploration budget briefly let confidence steering through at 30%, closed by requiring quiet tampering scores; a partial attack run that could have overwritten the published table; GitHub server errors that dropped a few cycles (runs now retry and fail loudly). Not built yet: a check that compares a take against the ordinary news rather than only against no news, which is the hole the adaptive attacker found. Next: that check, more outcomes per confidence band so calibration can size from measurement instead of exploration, and live trading on the Bitget demo once its book tracks the public market. Stack: Python, React and Vite, SQLite, GitHub Actions (live loop and attack runs), Vercel (site and log API), Google AI Studio (gemini-3.1-flash-lite), Bitget market data and demo trading API, OKX market data, Bitget's Qwen gateway (qwen3.8-max, tested).

**Part 5 - Your take on AI Trading.** Confidence is a claim, not a size. Agents should be judged by their record, and text they read should be allowed to talk them out of a trade but never into one. From building on Bitget's tools: the demo trading API works end to end, but its book sat 3 to 5% away from the public market on some contracts and lacks several listed perps, which makes demo fills hard to score, so a demo book that mirrors live prices would help agent builders most. The Qwen gateway was easy to plug in (OpenAI-compatible) and returned sound trading decisions, but at about 90 seconds and 3,700 reasoning tokens a call it is slow for a 15-minute loop unless thinking can be turned down, and its input filter refuses red-team prompts, so it could not play the adaptive attacker.

---

## 14. Submission Material Links *(required, one link per line, each labelled)*

"No access request should be required during review."

```
Project / live demo: https://tare-rust.vercel.app
Code, public repo with full README: https://github.com/khalydmaina/tare
Run records - decisions, every AI proposal with the Inspector's verdict and reason: https://tare-rust.vercel.app/api/log?file=decisions.csv
Run records - guarded orders, timestamp / instrument / direction / fill price / quantity / fees / outcome / R multiple / exit: https://tare-rust.vercel.app/api/log?file=trades.csv
Run records - unguarded shadow book, the same setups with no Inspector: https://tare-rust.vercel.app/api/log?file=shadow_trades.csv
Run records - account balance at every 15-minute mark, both books: https://tare-rust.vercel.app/api/log?file=equity.csv
Results write-up, backtest, attack suite and the honest limits: https://tare-rust.vercel.app/api/log?file=RESULTS.md
Demo video, 2:04: [public X post or public YouTube link]
```

Three handbook requirements this field has to satisfy, checked one by one:

- **"GitHub repos must be public with a complete README."** The repo is still private. It has to be
  flipped before submitting, and "access on request" is explicitly not allowed.
- **Agentic Trading run records must carry "timestamp, instrument, direction, price, quantity, and
  account balance change".** The first five are columns in `trades.csv`; the balance is in
  `equity.csv`. Both are listed and labelled so a judge does not have to hunt for the sixth.
- **"Demo video: 3 minutes or less, as a public X post or public YouTube link."** Ours is 2:04, but
  it is not public anywhere yet. A file served from our own site does not meet that wording.

## 15. Role of the LLM / AI in Your Project *(required)*

- **Trader (live and measured):** gemini-3.1-flash-lite through Google AI Studio's OpenAI-compatible endpoint. For each setup the scanner finds, it reads the setup, recent candles on 15m/1h/4h and the news digest, and returns take or skip plus its probability that take-profit is hit before stop-loss. It cannot change entry, stop, target or size. The same model runs the live bot and the attack evaluation, so the measured track record describes the model that actually trades.
- **What it never does:** size, veto or review itself. The Inspector is deterministic code. When the LLM wants a trade, the Inspector asks again with the news removed; if it would skip without the news the trade is vetoed, otherwise the lower confidence is used.
- **Adaptive attacker (A5):** the same model writes a headline, is told which checks blocked it, and tries again against the full gate, up to 6 times per setup.
- **Qwen (Bitget credits):** qwen3.8-max through Bitget's hackathon gateway. Tested as the trader's backup: it returned valid, well-reasoned decisions, but each took about 93 seconds and 3,800 output tokens (3,700 of them reasoning), too slow for our 15-minute loop without tuning, so it stays the backup rather than the main trader. Tried as the adaptive attacker: the gateway's input filter refused the red-team prompt ("DataInspectionFailed"), so that role stayed on Gemini. It met our needs as a fallback decision-maker, not as a red-team tool.
- **Also:** coding assistance while building (Claude Code).

## 16. X Project Post URL *(required)*

https://x.com/cipher_k1/status/2099146240365670455

## 17. Did this team participate in S1? *(required)*

No

## 18. Material Additions Since S1 *(optional, S1 participants only)*

Leave blank.

## 19. Apply for Post-event Kimi K3 Token Credits, 30U per team *(required)*

Yes

## 20. Open to Playbook Review and Listing Discussion *(required)*

Yes

The form notes this "only collects interest and is not a listing or commercial commitment".

---

## The mandatory X requirement

The handbook is blunt: **"No X post = incomplete submission."** The post must carry #BitgetHackathon
and @Bitget_AI and introduce what you built. Ours is posted, a 4-post thread from @cipher_k1:
https://x.com/cipher_k1/status/2099146240365670455

**Still to do:** the official Bitget post to quote is now published, where the handbook previously
said TBD: https://x.com/Bitget_AI/status/2100519318824055159

Post from your own account as a 4-post thread, and retweet Bitget's official hackathon post once they publish it. The form takes the link to post 1, which carries both tags. Keep each post within 280 characters even with Premium, so none is cut off behind "Show more" in the timeline (X counts an arrow as 2 characters; post 3 is 268 counted that way).

**Post 1** · image: docs/media/link-card.png (the preview card, readable on a phone)

> My AI trader said it was 60-69% sure. It was right 29% of the time.
>
> So I built tare: a non-LLM referee that sizes each trade by the model's own record. Fed steering news, the bare AI took 90% of losing trades. With tare: 0%.
>
> https://tare-rust.vercel.app
>
> #BitgetHackathon @Bitget_AI

**Post 2** (reply to post 1) · image: docs/media/attack-lab.png

> How it works: the AI only proposes. A referee that is plain code, not another AI, decides.
>
> It checks the AI's hit rate at that confidence, looks for tampering, and asks the AI again with the news removed.
>
> Here a losing DOGE trade gets past everything except that last check.

**Post 3** (reply to post 2) · image: docs/media/results.png

> I attacked it 6 ways on real past setups. Losing trades approved, no referee vs full referee:
>
> Hidden commands: 50% → 0%
> Forged charts: 33% → 0%
> Fake crowd: 37% → 3%
> Steering news: 90% → 0%
>
> An AI attacker rewriting headlines got 1 of 12 through. Fixing that next.

**Post 4** (reply to post 3) · no image

> It's trading live on paper every 15 minutes across 22 coins, with a no-referee account beside it for comparison.
>
> Every proposal, veto and result is public:
> https://tare-rust.vercel.app/api/log

Optional progress posts before submission (each adds reach):

> Red-teamed my own AI trader with an attacker that rewrites fake headlines until one gets through. On 17 of 20 trades it gave up after 6 tries. Once, a single believable headline beat the referee on a losing trade. Writing the fix. #BitgetHackathon @Bitget_AI

> Bitget's demo exchange filled my test order 3% away from the real market, so my bot's paper fills are priced off public candles instead. Here's the measurement: https://tare-rust.vercel.app/api/log?file=RESULTS.md #BitgetHackathon @Bitget_AI

---

## Event → decision → execution flow (for the video and for judges)

1. A 15-minute candle closes on Bitget (22 USDT perpetuals).
2. Positions that hit take-profit, stop-loss or the 12-hour limit are closed and recorded; shadow outcomes update the calibration record.
3. The scanner looks for a liquidity sweep, displacement and a return to the zone on the latest closed candle.
4. The LLM proposes take or skip with a probability.
5. The Inspector checks hard limits, tampering signals (injected instructions, fake crowds, prices that disagree with OKX, stale feeds), re-asks without the news, and looks up the calibrated probability for that confidence range. If the record beats breakeven there it sizes with quarter Kelly capped at 1% risk. If it has fewer than 20 outcomes at that confidence there is nothing to size from, so the trade is exploration instead: a quarter of base risk, twice a day, and only on inputs the tampering checks find quiet. Once a band has 20 outcomes and still shows no edge, it is vetoed.
6. Approved or shrunk trades are filled with stop-loss and take-profit attached, priced off the same public candles the outcome labeler walks; every take, approved or not, also opens in the shadow book. The same order code places real orders on the Bitget demo exchange (`scripts/check_bitget_demo.py`), which is how that path stays verified.
7. Everything lands in the flight recorder, the paper log, the dashboard and the website.
