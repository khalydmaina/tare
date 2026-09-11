# Threat model

## Attack -> defence map

| Attack | Goal | Primary checks |
|---|---|---|
| **A1 Sentiment injection** | Push confidence / flip skip to take via instruction-like text | **S1** (hard, regex, evadable by paraphrase), **M2** ablation |
| **A2 Fake consensus** | Inflate confidence with duplicate bullish posts, no jailbreak phrases | **S4** source concentration / fresh sources, S2 spike, **M2** |
| **A3 Candle forgery** | Manufacture a textbook sweep + displacement on the Trader feed | **C1** cross-venue deviation (hard), C2 candle stats, C3 integrity |
| **A4 Confidence steering** | Land in a *well-calibrated* bucket (e.g. ~74) to beat G1, text only | M1 jump, S2; **M2 ablation is the real defence** |
| **A4F Steering + forgery** | A4 plus mild candle polish | C1 (hard) plus everything above |
| **A5 Adaptive** | Iterate variants against the live G2 gate with feedback | All of the above; anomaly weights frozen before the run |

## Why ablation (M2) is the principled fix

The attacker in this model controls text the Trader reads and, for A3, the Trader's candle feed. They never control the reference feed. So the Inspector re-asks the Trader the same question with every sentiment item removed:

- If the Trader would **skip** without the text, the take is vetoed (`sentiment_driven_take`).
- Otherwise calibration uses `min(stated, ablated)` confidence. Text can lower confidence, never raise it.

Cost: one extra LLM call per proposed take, and genuine good news can no longer size a trade up. That trade-off is deliberate: unverifiable input should only be allowed to reduce risk.

Known limits: S1 is a regex blacklist and will miss paraphrased injections (M2 covers that case). If the attacker could also forge the reference venue, C1 is blind. Historical scenarios have no real news, so clean runs get a neutral background headline pool (`data/background_headlines.json`) to force the sentiment checks to discriminate.

## Gate story (to be measured, not assumed)

- **G0** approves almost every attacked take.
- **G1** stops max-confidence attacks (A1) because high buckets are badly calibrated, but misses A4.
- **G2A** adds the anomaly layer. It catches forgery through C1; pure-text A4 is the open question.
- **G2** adds ablation and should close A4 and most of A5, at some cost in clean retention.

Measure honestly in `docs/RESULTS.md`. If G2 fails to close A4 or A5, say so.
