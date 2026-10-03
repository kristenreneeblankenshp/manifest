# Manifest MWIR builder

A standalone command-line tool that publishes the **Weekly Institutional Report** as the
7-page PDF in the official layout. It does not depend on the workbench package. Run every
command below from this `weekly-report/` directory.

The workbench web console has its own MWIR *draft* under **Reports**, built from live workbook
data. This tool produces the published weekly PDF from the holdings CSV and a weekly inputs file.

Builds the Manifest **Weekly Institutional Report** (MWIR) PDF from two inputs:

1. **Holdings CSV**: the dynamic holdings template (`Date, Symbol, Weights`; extra template columns are ignored). This is the source of the executable target weights.
2. **Week file** (`weeks/YYYY-MM-DD.yaml`): the narrative, scores, market tape, event gates and per-holding guidance for the week.

Standing rules (bands, sleeves, gauge thresholds, allowed guidance actions, expected position count) live in `config/policy.yaml`.

The tool computes everything that can be derived, so those numbers are never typed by hand:

| Computed | From |
|---|---|
| Approved bands per holding | target × 75%–125%, 1.00% floor, 4.00% cap (policy) |
| Sleeve allocation and bars | sum of CSV weights by sleeve |
| Top 10 executable targets | CSV weights, ties in file order |
| MRGES-001 reconciliation text | `excluded:` names (e.g. BRK.B) and the computed sleeve total |
| Gauge zone and colour, component bar colours | policy thresholds |
| Control assertions and certification result | see below |
| Drift (BELOW / IN / ABOVE BAND) | only when `--actual` weights are supplied |
| Page numbers `n/N` | holding matrix paginates automatically |

## Setup

```bash
pip install reportlab PyYAML    # or: pip install -r requirements.txt from the repo root
```

## Weekly run

```bash
# 1. Start this week's file from last week's (dates roll, status -> draft,
#    prior composite carried forward)
python -m mwir new-week weeks/2026-08-28.yaml

# 2. Save the new holdings CSV to holdings/2026-09-04.csv and edit
#    weeks/2026-09-04.yaml: scores, tape, narrative, gates, guidance changes.

# 3. Run controls only
python -m mwir check weeks/2026-09-04.yaml

# 4. Set `status: official` and build
python -m mwir build weeks/2026-09-04.yaml
# -> out/Manifest_MWIR_Week_Ending_2026-09-04_Official.pdf
```

Options: `--holdings FILE` overrides the CSV named in the week file. `--actual FILE` adds an Actual column and drift status, using account weights in the same template format. `--out FILE` sets the output path.

Exit codes: `0` certified, `1` a control failed (the PDF is still written, marked **NOT CERTIFIED**), `2` input error, `3` text overflows a page.

### Placeholders in text

Prose can reference computed values so it never disagrees with the tables: `{total}`, `{positions}`, `{composite}`, `{week_ending}`, `{publication_date}`, `{sleeve:strategic}` (any sleeve key).

## Control assertions

| Check | Fails when |
|---|---|
| Holdings file date | CSV date ≠ `week_ending` |
| Executable holdings | count ≠ `expected_positions` |
| Executable target total | CSV weights don't sum to 100.00% |
| Guidance coverage | a CSV ticker has no guidance row, or a guidance row isn't in the CSV |
| `<excluded>` executable rows | an analytical-only name (BRK.B) appears in the CSV |
| Sleeve redistribution | the receiving sleeve's share of the model ≠ its share of the MFPDF baseline |
| Targets within cap | any target above the 4.00% cap |
| Guidance vocabulary | an action is not in `guidance_actions` (catches typos) |
| MFPDF baseline total | **warning** only: baseline doesn't sum to 100% |

A report is stamped **PUBLISHED / FROZEN** only when `status: official` and no check fails.

## Finding in the 28 Aug 2026 example

The published PDF asserts "Executable target total: 100.00% / PASS", but its own holding matrix sums to **96.98%**. The MFPDF baseline column also sums to 96.98% including BRK.B. The PDF describes a 46-position workbook but lists 45 holdings, so a position of about 3.02% appears to be missing. The normalised holdings CSV rescales the 45 names to 100%, which is why this tool shows COST at 3.60% where the PDF shows 3.49%. The tool reports the baseline gap as a warning.

## Assumptions to confirm

- **Gauge and component thresholds** in `config/policy.yaml` are placeholders. The automation spec lists the real green/yellow/orange/red cut-offs as an open question.
- **Composite, delta and gamma** are entered by hand. The formula has not been retrieved, and the report discloses this.
- **Band floor**: the 1.00% floor applies to the lower bound but never raises it above the target.

## Layout

```
mwir/model.py      load inputs, compute bands/sleeves/assertions (no drawing)
mwir/render.py     ReportLab PDF, US Letter
mwir/cli.py        build / check / new-week
config/policy.yaml standing rules
weeks/             one YAML per week (the archive of what was published)
holdings/          holdings CSVs
tests/             pytest
```
