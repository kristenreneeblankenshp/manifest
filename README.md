# manifest

`manifest-workbench` is a console application built from the workbook
**Manifest Workbench — CISC-001 / MOPS-003 RCC-004 MASR Registry & Candidate Pipeline v0.4**
(`spec/`). It covers all 33 worksheets:

- the CISC-001 Chief Investment Steward Console
- the certified MFPDF portfolio
- the MOPS-002 Portfolio Engineering Workspace (PEW-001 to PEW-007)
- the MOPS-003 research command chain (RCC-001 to RCC-004)

The app stores only the workbook's input cells in a JSON file and recalculates everything
else the way the workbook does. The golden test checks the engine against **every formula
cell in the workbook, on every sheet**: 13,950 cells, with no missing cells and no mismatches.

The app never changes certified target weights and has no trading function. Engineering
scenarios live in a separate layer, and certified data can change only through a new certified
MFPDF version.

## Install and run

```bash
pip install .                 # or: pip install '.[xlsx]' to import .xlsx workbooks
manifest-workbench            # interactive console, opening on the CISC dashboard
                              # (creates ./manifest_workbench.json on first run)
manifest-workbench sheets     # every worksheet and the command that opens it
python -m manifest_workbench  # equivalent, without installing
```

The app only needs the Python 3.9+ standard library. Importing a `.xlsx` file needs `openpyxl`.

## Sheets and commands

| Worksheet | Command | Editable tables |
|---|---|---|
| 00 CISC Dashboard | `cisc` | fed by the sheets below |
| 01 Dashboard Controls | `controls` | `controls`, `composite` |
| 02 Decision Center | `decision-center` | `decisions` (manual decision register) |
| 03 Research Intelligence | `intel` | `intel-review`, `intel-events`, `intel-zacks`, `intel-merrill`, `intel-miar`, `intel-thesis` |
| 04 Committee Operations | `committee` | `actions`, `priorities`, `questions`, `projects`, `publications`, `calendar`, `certifications` |
| 99 Dashboard Data | `dashboard-data` | calculated |
| Certified Allocation / Sleeve Summary | `portfolio`, `portfolio sleeves` | `portfolio` (actual weights, MFPDF conviction, research status) |
| Executive Summary · Rebalancing · Sources & Certification | `doc executive-summary` · `doc rebalancing` · `doc sources` | reference |
| 05 Workbench Guide | `doc workbench-guide` | reference |
| 06 PEW Control Center | `pew` | calculated |
| 07 Mandate & Constraints (PEW-001) | `mandate` | operating value, status and notes of the non-formula controls |
| 08 Sleeve Architecture (PEW-002) | `sleeves` | committee notes |
| 09 Role Assignment (PEW-003) | `roles` | functional role, priority, eligibility, evidence, decision |
| 10 Candidate Comparison (PEW-004) | `pew004` | candidate scoring inputs |
| 11 Conviction (PEW-005) | `conviction` | proposed conviction, thesis, risk, horizon |
| 12 Allocation Lab (PEW-006) | `lab` | `lab` (scenario header), `scenario` (scenario weights, rationale) |
| 13 Validation & Cert (PEW-007) | `validation` | `validation` (thresholds, proposed version), `workflow`, `changes` |
| 14 PEW Guide · 15 MOPS-002 Freeze Record | `doc pew-guide` · `doc freeze-record` | reference |
| 16 RCC-001 Control Center | `rcc001` | calculated |
| 17 / 18 RCC-002 | `rcc002`, `evidence` | evidence ledger (200 records, `EVD-YYYYMMDD-###`) |
| 19 / 20 / 21 RCC-003 | `rcc003`, `miar`, `review` | MIAR registry; review log (200 records, `MIR-YYYYMMDD-###`) |
| 22 / 23 / 24 RCC-004 | `rcc004`, `masr`, `pipeline` | MASR registry (150 slots); candidate pipeline (200 records, `MCP-YYYYMMDD-###`) |
| 97 RCC Lists · 98 PEW Lists | `lists [NAME]` | controlled values |

Other commands:

- `dashboard` shows the MOPS-003 research view.
- `guide` shows the RCC-004 operating standard.
- `cell SHEET REF` reads any calculated cell, for example `cell "13 Validation" J12`.
- `audit` shows the audit trail.

## Everyday use

Every table command takes `list`, `show`, `set`, `fields` and `export`. Registers and list
tables also take `add`, and list tables take `clear`.

```bash
manifest-workbench cisc                               # the five-panel console
manifest-workbench portfolio set NVDA actual_weight=2.9%

# research intelligence and committee lists: add, edit by row number or key, clear
manifest-workbench intel-review add symbol=MU company="Micron" reason="Memory cycle" status=decision
manifest-workbench actions add action="Load Q4 weights" owner="Portfolio Operations" status=open
manifest-workbench decisions add decision="Review MU conviction" committee_decision=yes status=open
manifest-workbench intel-review clear 1

# weekly dashboard controls and composite score
manifest-workbench controls set report_date=today previous_week_score=0.62 confidence=70%
manifest-workbench composite set "Macro Regime" score=0.4

# engineering scenario (never touches certified weights)
manifest-workbench scenario set NVDA scenario_weight=3.18% rationale="AI capex; funded from JEPQ"
manifest-workbench scenario set JEPQ scenario_weight=2.52% rationale="Source of funds"
manifest-workbench lab                                # funding, bands, turnover, readiness
manifest-workbench validation                         # VAL-001..018, workflow, change register
manifest-workbench workflow set "Portfolio Engineering" status=approved reviewed_by=CIS review_date=today

# research chain
manifest-workbench masr set VRT masr_id=MASR-0023 T=45 zacks=2 merrill=buy
manifest-workbench pipeline advance MCP-20260824-001  # only if the current stage gate passes
```

Global options go before the command:

- `--data PATH` or `$MANIFEST_DATA` sets the data file.
- `--as-of YYYY-MM-DD` or `$MANIFEST_AS_OF` sets the date used for TODAY().
- `--by NAME` or `$MANIFEST_USER` sets the operator name in the audit trail.
- `--no-color` turns off colour.

Fields can be named by key, unique key prefix or worksheet column letter (`T=45`).
Controlled-list values match without regard to case or dash style, and a unique prefix is
enough. Weights accept `3.1%`, `0.031` or `3.1`. An empty value (`field=`) clears a field.

Records in list tables can be addressed by key, unique key prefix or row number (`3` or `#3`).

## Controls the app enforces

- **Only input fields can be edited.**
  - Calculated and linked fields are rejected.
  - Certified MFPDF data is locked. Changing it requires a new certified MFPDF version.
  - Frozen governance text is locked, including the adopted mandate standards, sleeve
    purposes, workflow stages, composite component names and console identity. Changing it
    requires a documented amendment.
  - The formula rows of the mandate register (PEW-001-09 to 12, 25 and 26) cannot be overwritten.
- **One identity per record.** These duplicates are blocked: canonical MASR and MIAR IDs,
  registry tickers, and action, decision, question and project IDs. RCC record IDs follow
  `EVD-`, `MIR-` or `MCP-YYYYMMDD-###` and cannot change. Missing IDs are generated.
- **Controlled vocabularies.** Every validation-listed field accepts only values from its list.
- **Stage gates.** A candidate moves forward only after its current gate passes.
- **Scenario isolation.** Scenario weights live in `scenario`. The certified allocation stays
  unchanged.
- **Capacity.** Each register and list keeps its worksheet size, for example 150 MASR slots,
  8 rows per research section and 20 manual decisions.
- **Audit trail.** Every edit, addition and cleared row is recorded with the time, operator,
  field, and old and new values.
- **Older data files.** A data file created before a sheet was covered gets that sheet's
  v0.4 inputs on load. Existing entries are kept.

## Importing a workbook

```bash
pip install openpyxl
manifest-workbench init --force --from-xlsx path/to/Manifest_Workbench_v0_4.xlsx
```

The import reads only the input cells. The bundled data (`manifest_workbench/data/seed.json`)
is exactly the v0.4 workbook's inputs, and the golden test checks that. The reference sheets
are bundled as `data/docs.json`.

## Findings from the v0.4 workbook

- **Non-holding candidates cannot pass eligibility yet.** The RCC-003 MIAR registry has rows
  only for the 47 certified holdings, and RCC-004 reads MIAR identity, status, freshness and
  scores from that range. Candidates such as EMR or HUBB therefore stay `NOT ELIGIBLE` until
  RCC-003 covers non-holdings. The app reproduces this behaviour as is.
- **All 10 candidates are overdue.** The workbook's saved results were calculated as of
  2026-08-24. The 10 Barron's roundtable candidates were due on 2026-09-23, so on any later
  date they show `OVERDUE`.
- **PEW-001 can never show FAIL.** The PEW Control Center checks the mandate register for the
  exact text `FAIL`. The mandate's own tests report `FAIL — ABOVE OPERATING CEILING`, so a
  failed hard constraint would still show the module as `ACTIVE`.
- **Hardcoded equity limits in the mandate.** The mandate register uses fixed values of 38
  and 41 for its equity-count tests. PEW-007 has its own thresholds, and changing them in
  `validation` does not change the mandate.
- **Two conviction vocabularies.** Certified Allocation uses `Tier 1/2/3`, while PEW-005 scores
  only `Tier 1 — Anchor`, `Tier 2 — Core` and `Tier 3 — Opportunistic`.
- **Blank cells.** The saved results treat a direct link to an empty cell as displaying `0`
  while still counting as blank (for example, actual weights in 99 Dashboard Data and the
  Allocation Lab). Lookups of empty cells return blank. The app follows both. In desktop
  Excel, both would read as `0`, which could hide "missing" checks.
- **Prototype console inputs.** The dashboard controls are marked
  `PROTOTYPE VALUES — LIVE INPUTS REQUIRED`. The composite score of +0.62 comes from
  placeholder component scores.

## Development

```bash
python -m unittest discover -s tests -t .   # the golden test needs openpyxl
```

- `engine.py`: MFPDF, PEW-004/005 and RCC-001 to RCC-004.
- `pew.py`: PEW-001, 002, 003, 006 and 007, and the PEW control center.
- `cisc.py`: dashboard controls, 99 Dashboard Data, Decision Center and the console.
- `cells.py`: maps every formula cell to an engine value, for the golden test and `cell`.
- `schema.py`: every table, its fields, kinds and validation lists.
- `ops.py`: controlled edits.
- `cli.py`, `views.py` and `render.py`: the console.
- `xlsx_import.py`: workbook import.
