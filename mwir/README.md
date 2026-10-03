# MWIR Report Builder

A browser tool that builds the weekly **Manifest Weekly Institutional Report (MWIR)** as an
8-page landscape PDF, in the layout of the 28 Aug 2026 official MWIR. Weekly inputs go in the
panel on the left, and the report on the right updates as you type.

It has no dependencies and no build step. Open `index.html` in a browser, or run the workbench
app (`cd app && npm start`) and go to <http://localhost:3000/mwir/>.

## Weekly use

1. **Holdings:** load the `Date, Symbol, Weights` CSV (the dynamic holdings template). Decimal
   weights are converted to percentages. Tickers carried over from last week keep their sleeve,
   guidance and rationale. New tickers are marked `Unassigned` and dropped tickers are listed.
2. **Signals:** composite score, compass values, the 10 component scores, risk tape,
   interpretation bullets and decision rule.
3. **Narrative:** headline, executive summary, macro sections and client brief.
4. **Controls & sources:** event gates, deployment hierarchy, reconciliation, deliverables and sources.
5. **Save as PDF / Print** prints landscape 11 × 8.5 in pages without the input panel. Turn on
   "Background graphics" in the print dialog.

Inputs are saved in the browser (`localStorage`). **Reset to 28 Aug example** reloads the example week.

## Report pages

| Page | Content | Calculated by the tool |
|---|---|---|
| 1 | Cover, gauge, compass, executive summary | gauge needle and zone |
| 2 | Institutional signal dashboard | component bars |
| 3 | Macro stewardship and event gates | — |
| 4 | Allocation and implementation | sleeve totals, top 10 targets, bands |
| 5–6 | Holding action matrix | bands, ordering by sleeve, page split |
| 7 | Zacks holdings validation screen | screen result per holding, review list, upcoming earnings |
| 8 | Certification, client brief and sources | control assertions, certification result |

**Bands** are 75–125% of the current target, floored at 1.00% and capped at 4.00%.

**Control assertions:** holdings present, total equals 100.00%, Strategic Anchors equals the
frozen total, no BRK.B executable rows, no position above 4.00% and no unassigned sleeves. If any
of these fail, the certification reads `HOLD · CONTROLS FAILING`. Zacks screen exceptions show in
amber but do not block publication, because the framework may keep names the screen would drop.

**Gauge zones** are an assumption until the framework's thresholds are supplied:
70 and above green, 55–69 yellow, 40–54 orange, below 40 red.

## Zacks data

`zacks.js` holds a Zacks snapshot: Zacks Rank, market cap and next earnings date for each
equity, and the ETF rank for ETFs. The page cannot call Zacks itself, so refresh the snapshot each
week by replacing `zacks.js` with the same shape. The current file is as of 25 Sep 2026.

The screen applies the spec's rule: market cap above $100B and Zacks Rank 1–3. Rank 1–2 is Tier 1.
`alias` maps holdings-file tickers that Zacks lists under another symbol (MMC is now MRSH).

## Known data points from the 28 Aug example

- The PDF's holding matrix lists 45 rows that total 96.99%, while the report states a 46-position,
  100.00% model. The example therefore shows `HOLD · CONTROLS FAILING` until the missing row is added.
- The normalized holdings CSV for 28 Aug totals 100.00% but its weights differ from the PDF (for example
  COST 3.60% versus 3.49%), so Strategic Anchors comes to 23.22% against the frozen 22.51%.

## Tests

```bash
node --test mwir/test.js
```
