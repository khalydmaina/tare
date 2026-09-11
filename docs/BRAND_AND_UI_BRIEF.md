# Brand & UI Brief

> **LOCKED BRAND (2026-09-11):** Product ships as **tare**.  
> Canonical kit: [`../brand/tare/`](../brand/tare/) — PDF, logos, `tokens.css` / `tokens.json`.  
> This brief remains the *product/UX* source of truth. Where naming conflicts, **tare** wins over “The Prosecutor.”

**Audience for this document:** a design / brand agent producing or extending brand kit + UI.  
**Product repo:** `/home/rahman/prosecutor`  
**Hackathon:** Bitget AI × Crypto Hackathon, Genesis Season 2 — Agentic Trading / Open Theme  

Read this end to end before inventing visuals. Do **not** invent a second product story. Do **not** turn this into generic “AI crypto trading bot” neon-cyber branding.

---

## 1. What this product is (plain language)

**Name:** The Prosecutor  

**One-liner:** An AI trader with brakes that tighten exactly where the AI has proven it can’t be trusted — and that still hold when someone tries to game them.

**What it does in one paragraph:**  
A rules-based market-structure engine finds trade setups. An LLM decides whether to take or skip each setup and states a **confidence** (its probability that take-profit hits before stop-loss). A separate, **non-LLM Inspector** then approves, shrinks, or vetoes the trade using (1) how often that confidence level was actually right in the past, (2) independent market data the trader can’t fake, and (3) hard risk limits the model cannot change. Everything is logged. A “shadow” book shows what would have happened if the Inspector had stayed silent. An attack lab tries to poison the trader’s inputs on purpose, so we can prove the brakes work.

**What it is not:**
- Not a “smarter LLM that reviews another LLM”
- Not a signal group, not a meme coin launcher, not a DeFi yield product
- Not a black-box “AI alpha” flex
- Not colorful Web3 carnival branding

**The core argument (brand spine):**  
A second AI reviewing the first shares the same blind spots. When the trader is fooled, the peer reviewer tends to fail at the same moment. The Prosecutor’s Inspector never asks another model. It judges **measured track record** and **independent evidence**.

---

## 2. Who this is for

| Audience | What they care about | What the UI must prove in seconds |
|---|---|---|
| Hackathon judges & voters | Novelty + rigor + demo clarity | “This isn’t just another LLM trader — it has brakes, and we attack them.” |
| Crypto / agentic-trading builders | Trust, risk, adversarial robustness | Calibration vs stated confidence; veto with numbers; green vs red equity |
| Technical reviewers | Honesty under attack | Attack Lab: A4 slips past calibration-only, full gate catches it |

**User job-to-be-done (primary surface = Flight Recorder dashboard):**  
“Show me, live, whether the AI is overconfident — and whether the gate stopped a bad trade.”

**Secondary surface = marketing / README / demo video:**  
“Explain the shared-blind-spots idea in 20 seconds, then prove it with the Attack Lab.”

---

## 3. Brand metaphor & naming system

### Metaphor
**Court / prosecution / evidence / flight recorder** — not casino, not rocket, not “degen.”

- The **Trader** proposes.
- The **Inspector** cross-examines with independent evidence.
- The **Flight Recorder** is the black box: every proposal, veto, and counterfactual is logged.
- The **Attack Lab** is the cross-examination under hostile counsel.

### Product vocabulary (use consistently)

| Term | Meaning | UI label style |
|---|---|---|
| Prosecutor | Product name | Title case; never “ProsecutorAI” or “Prosecutor Bot” |
| Flight Recorder | Dashboard / event log | Prefer over “Dashboard” in hero copy |
| Inspector | Non-LLM gate | Never “AI reviewer” |
| Trader | LLM + SMC setup layer | OK as “Trader” |
| Confidence | Stated P(TP before SL), 0–100 | Always define once near first use |
| Calibrated probability | Empirical / Wilson-adjusted hit rate | Short label: “Calibrated p” |
| Veto / Approve / Shrink | Decision kinds | Hard verbs; no soft euphemisms |
| Shadow book | Unguarded counterfactual | “Shadow (unguarded)” vs “Guarded” |
| Gate G0 / G1 / G2 | Unguarded / calibration / full | Keep codes; tooltip the expansion |
| Attack A1–A5 | Named adversarial scenarios | Show ID + short name |

### Taglines (pick one primary; others are alternates)

1. **Primary:** “Brakes where the model can’t be trusted.”
2. “Confidence on trial.”
3. “Not another LLM judge. Evidence.”
4. “Guarded green. Unguarded red.”

### Tone of voice
- Precise, calm, slightly severe — like an expert witness, not a hype account
- Short sentences; numbers over adjectives
- Willing to show bad results (honesty is a brand feature)
- Dry wit OK once (“This AI is 90% sure. Historically, when it says 90%, it’s right 41% of the time.”)
- Never: “revolutionary,” “unleash,” “next-gen,” “moon,” rocket emojis, purple gradients

---

## 4. Visual north star (locked direction)

### Thesis
**Forensic trading terminal.** Near-monochrome dark canvas. Typography does the authority work. Color is scarce and semantic: **green = guarded / survived the gate**, **red = shadow / veto / harm**. White is structure and text. No third accent rainbow.

Think: black-box flight recorder + courtroom evidence board + serious quant terminal — **not** Binance yellow carnival, not Solana purple cyberpunk, not “AI SaaS indigo.”

### Existing product constraints (already shipping in Streamlit)
Current dashboard already commits to:
- Background `#0a0a0a`
- Text near-white `#f0f0f0` / headings `#ffffff`
- Guarded equity line: green `#22c55e`
- Shadow equity line: red `#ef4444`
- Veto flash: deep red panel `#7f1d1d` + border `#ef4444`, subtle pulse
- Tight letter-spacing on headings
- Minimal chrome; data first

**Brand kit and any redesign must preserve these semantic roles.** You may refine tokens, type, spacing, and layout — do not replace green/red meanings or add a decorative brand purple/blue as a primary accent.

### Reference mood keywords (for research agents)
- Forensic / evidence / flight recorder / black box
- Editorial monochrome SaaS
- Dark technical data infrastructure
- Courtroom transcript, not crypto Twitter
- Linear / Bloomberg terminal restraint (mood only — do not clone)

### Anti-references (explicitly reject)
- Neon cyberpunk grids, glitch overlays, circuit-board textures
- Gradient mesh heroes, glassmorphism stacks, floating 3D coins
- Mascot robots, scales-of-justice clipart as the whole identity (a **minimal** mark is OK)
- “Calm editorial” cream + terracotta + decorative italic word-swap (current AI-slop pattern)
- Rainbow charts, 6 accent colors, pill soup

---

## 5. Brand kit deliverables (what to produce)

Create a kit an implementer can use without asking follow-ups:

### 5.1 Logo / wordmark
- **Wordmark:** “The Prosecutor” — primary lockup
- **Short mark:** “Prosecutor” or monogram `P` in a severe geometric form (square or stamped seal — not a cartoon gavel)
- **Optional symbol:** minimal black-box / recorder rectangle, or a simple vertical “evidence bar” — one shape, high contrast
- Provide: full lockup, icon-only, inverted (for light surfaces if needed), favicon 32/64
- Clear space = height of the “P” (or mark) on all sides
- Do **not** add “AI”, “.xyz”, lightning bolts, or chain links into the mark

### 5.2 Color tokens (roles, not decoration)

| Token | Suggested hex (refine OK) | Role — do not repurpose |
|---|---|---|
| `bg.canvas` | `#0A0A0A` | App / page background |
| `bg.panel` | `#111111` | Cards, chart plot area |
| `bg.panel-elevated` | `#161616` | Hover / selected rows |
| `border.subtle` | `#222222` | Dividers, chart grid |
| `border.strong` | `#333333` | Focus rings (non-danger) |
| `text.primary` | `#F0F0F0` | Body |
| `text.muted` | `#A3A3A3` | Labels, captions |
| `text.inverse` | `#0A0A0A` | Text on light buttons only |
| `accent.guarded` | `#22C55E` | Guarded equity, approve, “held” |
| `accent.danger` | `#EF4444` | Shadow equity, veto, harmful |
| `accent.danger-deep` | `#7F1D1D` | Veto flash background |
| `accent.neutral` | `#FFFFFF` | Primary UI chrome, gauges, bars |

**Rule:** If it isn’t guarded/survived → green, or veto/shadow/harm → red, it should be white/gray/black.

### 5.3 Typography
- **Display / product name:** tight tracking, grotesque or neo-grotesk (e.g. Inter Tight, Geist, IBM Plex Sans, Neue Haas-like). Prefer **sans**, not decorative serif.
- **UI / data:** tabular figures mandatory for prices, %, R-multiples, confidence
- **Mono (optional, limited):** for order IDs, hashes, `limits_hash`, raw JSON expand — IBM Plex Mono / JetBrains Mono / Geist Mono
- Scale suggestion:  
  - Display 32–40  
  - Section 20–24  
  - Body 14–16  
  - Meta / table 12–13  
- Headings: slight negative letter-spacing; avoid all-caps walls except tiny labels (`VETO`, `G2`, `A4`)

### 5.4 Radius, stroke, elevation
- Radius: **2–6px** max (closer to stamped metal than soft SaaS). Prefer 4px.
- Borders: 1px; prefer border over shadow
- Shadows: almost none; if used, very tight and dark
- Density: **high information density** on the Flight Recorder; marketing page can breathe more but stay severe

### 5.5 Motion
- Default: instant or 120–200ms ease
- **Veto flash:** the only dramatic motion — short pulse/opacity, not confetti
- Charts: no bounce; no animated gradient fills
- Attack Lab compare: cross-fade or instant tab switch; emphasize state change with color, not parallax

### 5.6 Iconography
- Stroke icons, 1.5–2px, geometric
- Domains: shield-off / brake, gauge, book/ledger, waveform, alert triangle, lock (for limits hash)
- Avoid: rockets, coins with faces, brain-in-chip clichés

### 5.7 Imagery & diagram language
- Prefer **product UI screenshots** and **simple diagram lines** over stock photos
- Architecture diagrams: monochrome boxes + one green and one red line max
- Demo video stills: dial, veto banner, green/red equity overlay, Attack Lab three-column G0|G1|G2

---

## 6. Product surfaces to design

### A. Flight Recorder (primary product UI)

**Purpose:** Live operator / judge view of the bot.

**Header strip (always visible):**
1. Bot status — `running` / `halted` / `kill-switch` (status is a stamped pill, not a cute badge)
2. Equity (guarded)
3. Today’s P&L
4. Open positions count
5. Optional: limits hash (mono, truncated)

**Panels (required):**

1. **Overconfidence dial**  
   - Two readings: **Stated confidence** vs **Calibrated p**  
   - Visual: dual-needle or needle + threshold mark  
   - Below: bar chart of overconfidence gap by confidence bucket  

2. **Veto indicator**  
   - On veto: red flash banner with reason **and numbers**  
   - Example copy: `VETO — no_calibrated_edge · p_adj 0.29 < breakeven 0.33 · anomaly 0.12`  
   - Must feel like an alarm that still reads as professional  

3. **Equity curves**  
   - Same axis: **Guarded (green)** vs **Shadow unguarded (red)**  
   - Annotate max drawdown for each  
   - This is the emotional punch of the product — protect it visually  

4. **Reliability diagram**  
   - Stated confidence (x) vs actual hit rate (y)  
   - Diagonal “perfect calibration” reference  
   - Point size = sample size `n`  

5. **Decision log**  
   - Dense table: time, symbol, side, action, confidence, decision, reason, p_adj, anomaly, size  
   - Row expand → anomaly breakdown JSON / checklist of which sensors fired  

6. **Attack Lab tab** (demo centerpiece)  
   - Controls: scenario picker + attack picker (`clean`, `A1`…`A4`)  
   - Output: **three columns G0 | G1 | G2** side by side  
   - Each column: APPROVED / VETO, reason, confidence, anomaly, **checks fired**  
   - Narrative cue to support in UI microcopy: “A4 is built to beat calibration-only. G2 should catch it.”  

7. **Results tab**  
   - HAR / ASR table from harness  
   - Reliability curves clean vs attacked  

**States to design explicitly:**
- Empty (no proposals yet)
- Running healthy
- Veto just fired
- Kill-switch / halted
- Attack Lab with recorded replay (demo-safe if live breaks)

### B. Marketing / landing (for judges & voters)

Suggested section order (severe, short):

1. **Hook** — overconfidence quote with real numbers  
2. **Shared blind spots** — 3 sentences max  
3. **How it works** — Trader → Inspector → Shadow → Recorder (diagram)  
4. **Proof** — screenshot strip: dial + veto + green/red equity  
5. **Attack Lab** — A4 story in one frame  
6. **Results** — compact metrics table  
7. **CTA** — repo / live dashboard / demo video  

Do **not** default to generic “Hero → 6 feature cards → pricing → FAQ.” There is no pricing. Features are evidence panels.

### C. Demo video frames (brand-consistent)
Match the build’s storyboard (~3 min):
- 0:00 Hook with real overconfidence numbers  
- 0:20 Shared blind spots  
- 0:50 Live dial + veto + equity  
- 1:30 Attack Lab A4 vs G1 vs G2  
- 2:30 Results + repo  

UI chrome in video should match the brand kit exactly.

---

## 7. Information design rules (non-negotiable)

1. **Numbers beat metaphors.** Every veto shows `reason` + intermediates (`p_cal`, `p_adj`, `p_be`, `anomaly`).
2. **One definition of confidence everywhere:** probability TP hits before SL.
3. **Green/red semantic lock:** guarded vs unguarded / harm. Never swap.
4. **G0 / G1 / G2 always comparable side-by-side** in Attack Lab.
5. **Honesty aesthetic:** if a metric looks bad, the UI still shows it (no hiding rows).
6. **LLM is not the hero visually.** The Inspector / brakes / evidence are the hero.
7. **Limits are sacred:** show that risk config is read-only (hash). Optional small “sealed” treatment.

---

## 8. Copy deck (starter)

### Microcopy
- Status: `RUNNING` · `HALTED` · `KILL SWITCH`
- Decisions: `APPROVE` · `SHRINK` · `VETO` · `SKIP`
- Books: `Guarded` · `Shadow (unguarded)`
- Dial subtitle: `Stated confidence vs calibrated probability`
- Empty: `No proposals yet. Waiting for the next 15m close.`
- Attack Lab helper: `Attacks only change Trader inputs. The Inspector’s reference feed stays clean.`

### Hook lines
- “This AI trader is 90% sure. Historically, when it says 90%, it’s right 41% of the time.”
- “Another LLM won’t save you. Shared blind spots fail at the same moment.”
- “We don’t ask a model to grade a model. We ask the record.”

### About blurb (50 words)
The Prosecutor is an agentic paper trader with a non-LLM Inspector. Setups come from market structure; an LLM proposes take/skip and a confidence. The Inspector sizes or vetoes using calibration, independent data, and hard limits. A shadow book and attack lab prove what the brakes catch — and what they miss.

---

## 9. Component inventory for UI system

Design these once; reuse everywhere:

| Component | Notes |
|---|---|
| Status pill | Running / Halted / Kill-switch |
| Metric tile | Label + value + delta; tabular nums |
| Veto banner | Danger-deep bg, monospace-ish numbers |
| Dual gauge | Stated vs calibrated |
| Equity chart | Green/red dual series |
| Reliability scatter | Diagonal reference |
| Decision table | Dense, expandable anomaly |
| Gate column card | G0/G1/G2 compare |
| Check chips | `S1` `C1` `M1` fired — small, stamped |
| Attack / scenario selects | Severe form controls, not playful |
| Sealed hash chip | `limits_hash: a1b2…` |

---

## 10. Gate & attack cheat-sheet (so UI labels stay accurate)

### Gates
| ID | Meaning | UI short |
|---|---|---|
| G0 | Unguarded — fixed 1% risk on takes | Unguarded |
| G1 | Limits + calibration + sizing | Calibration |
| G2 | G1 + anomaly layer | Full gate |

### Attacks
| ID | Name | What it tries |
|---|---|---|
| A1 | Sentiment injection | Instruction-like headlines → max confidence |
| A2 | Fake consensus | Duplicate bullish flood from fresh sources |
| A3 | Candle forgery | Rewrite trader candles into textbook setup |
| A4 | Confidence steering | Land in a *well-calibrated* bucket (~74) to beat G1 |
| A5 | Adaptive | Iterates variants (stretch goal) |

**Expected demo narrative to support in layout:**  
G1 catches crude A1; **A4 is the hole**; **G2 closes A4** and shows which checks fired.

---

## 11. Do / Don’t for the brand agent

### Do
- Keep monochrome discipline; spend color only on meaning
- Make Attack Lab and green/red equity the memorable visual move
- Use real product terms from this brief
- Design for dark-first; light mode optional and secondary
- Optimize for a 3-minute judge demo glanceability

### Don’t
- Rebrand as generic AI crypto SaaS
- Add a second accent family (blue/purple/gold) “for energy”
- Soften veto alarms into friendly toast notifications
- Hide the shadow book (it is the moral of the product)
- Invent features not in the build (social trading, NFTs, mobile app, etc.)
- Use scales-of-justice stock art as a full illustration system

---

## 12. Success criteria for the brand kit + UI

The kit and UI succeed if a stranger can answer yes to all:

1. In 5 seconds: “This is about **distrusting AI confidence**, not celebrating it.”
2. In 15 seconds: they can point to **stated vs calibrated** and **green vs red equity**.
3. In 60 seconds: they understand **why a second LLM is the wrong fix**.
4. In the Attack Lab: they see **A4 pass G1 and fail G2** without reading a paper.
5. Nothing looks like default Streamlit theme, Binance promo, or Midjourney “AI trading” aesthetic.

---

## 13. Implementation notes for engineers

- Live dashboard today: Streamlit + Plotly at `dashboard/app.py` (functional, not final brand polish).
- Brand kit should be framework-agnostic (tokens + Figma/HTML mock), then optionally applied back to Streamlit CSS or a future web UI.
- Data source: SQLite flight recorder (`data/prosecutor.db`); demo seed via `scripts/seed_demo_db.py`.
- Prefer designing against **seeded demo data + Attack Lab JSON** so visuals don’t depend on live exchange DNS.

---

## 14. One-page brief (paste to kick off a design agent)

```text
Designing brand kit + Flight Recorder UI polish for The Prosecutor
(Bitget AI hackathon agentic trader) on web.

Goal: Make judges instantly grasp “AI trader with evidence-based brakes,”
especially stated vs calibrated confidence, veto-with-numbers, guarded(green)
vs shadow(red) equity, and Attack Lab G0/G1/G2 (A4 hole closed by G2).

Tone: Forensic, severe, honest, monochrome. Expert witness — not degen hype.

Must remember: A second LLM shares blind spots; Inspector never uses an LLM.
Color is semantic only (green guarded / red danger). Confidence = P(TP before SL).

Constraints: Dark-first; high density dashboard; no purple/cyber/neon; no fake
features; preserve product vocabulary (Inspector, Flight Recorder, Shadow, G0–G2, A1–A5).

Research needed: styles (editorial monochrome / dark technical / fintech restraint)
+ screens (trading/ops dashboards, reliability charts, alert banners, compare columns).

Path: brand kit (logo, tokens, type, components) → dashboard mock → optional landing.
```

---

*Source of truth for behavior: `docs/PROSECUTOR_BUILD.md` and the running app. This brief is the source of truth for brand meaning and UI priorities.*
