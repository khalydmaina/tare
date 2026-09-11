# tare brand — installed kit

**Location:** `brand/tare/`  
**Source zip:** `Tare_Brand_Kit (1).zip`  
**Version:** 1.1

## What “tare” means

*tare* (pronounced **tair**) — the weight you subtract so a scale reads true.

| Scale term | Product meaning |
|---|---|
| Gross | Stated confidence (what the LLM claims) |
| Tare | Inspector correction (calibration + anomaly + limits) |
| Net | Calibrated probability (what you should size on) |

**Primary line:** Zero the confidence. Weigh the record.

## Kit contents

| Path | Use |
|---|---|
| `Tare_Brand_Kit.pdf` | 15-page brand book |
| `tokens/tokens.css` | CSS variables for UI |
| `tokens/tokens.json` | Machine-readable tokens |
| `logos/tare-mark.svg` | Scale mark (white gross + red net) |
| `logos/tare-wordmark.svg` | Lowercase Poppins Bold wordmark |
| `logos/tare-lockup-*.png` | Mark + wordmark |
| `logos/tare-icon-*.png` | App icons / favicons |
| `logos/tare-system-board.png` | Full system board reference |

## Color verdicts (do not repurpose)

- `#22C55E` green → guarded / survived the gate / net after tare  
- `#EF4444` red → shadow / veto / harm / icon net mass  
- Everything else → black / gray / white  

## Applied in repo

- Flight Recorder dashboard loads `brand/tare/tokens/tokens.css` + lockup + favicon  
- README product name set to **tare**  

## Open

```bash
xdg-open brand/tare/Tare_Brand_Kit.pdf   # or open on Windows
streamlit run dashboard/app.py           # http://localhost:8501
```
