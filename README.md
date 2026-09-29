# manifest

`manifest-workbench` is a console application built from the workbook
**Manifest Workbench — CISC-001 / MOPS-003 RCC-004 MASR Registry & Candidate Pipeline v0.4**
(`spec/`). It runs the MOPS-003 research command chain (RCC-001 through RCC-004) from
the terminal, plus the certified MFPDF portfolio, PEW-004 and PEW-005 data that chain depends on.

The app stores only the workbook's input cells in a JSON file. It recalculates every
formula column the way the workbook does. A golden test checks the engine against every
cached formula result in the v0.4 workbook: more than 3,000 cells, plus the control-center
cells, with no mismatches.

The app follows the MOPS-003 control principle. Research identifies and evaluates change,
Portfolio Engineering designs the response and committee governance authorizes it. The
certified MFPDF remains the only portfolio system of record. The app never changes
certified target weights and has no trading function.

## Install and run

```bash
pip install .                 # or: pip install '.[xlsx]' to import .xlsx workbooks
manifest-workbench            # interactive console (creates ./manifest_workbench.json on first run)
manifest-workbench rcc004     # or run any command directly
python -m manifest_workbench  # equivalent, without installing
```

The app only needs the Python 3.9+ standard library. Importing a `.xlsx` file needs `openpyxl`.

## What maps to what

| Workbook sheet | Command | Notes |
|---|---|---|
| 16 RCC-001 Control Center | `rcc001` | readiness, exceptions, intelligence snapshot, roadmap |
| 17 RCC-002 Control Center | `rcc002` | evidence state, activity, routing and materiality profile |
| 18 RCC-002 Evidence Ledger | `evidence list/show/add/set` | 200 records, `EVD-YYYYMMDD-###` |
| 19 RCC-003 Control Center | `rcc003` | MIAR state, exceptions, sleeve coverage |
| 20 RCC-003 MIAR Registry | `miar list/show/set` | one dossier per certified holding |
| 21 RCC-003 MIAR Review Log | `review list/show/add/set` | 200 records, `MIR-YYYYMMDD-###` |
| 22 RCC-004 Control Center | `rcc004` | MASR and candidate state, exceptions, composition, stages |
| 23 RCC-004 MASR Registry | `masr list/show/add/set` | 150 slots; 47 certified rows linked to the MFPDF |
| 24 RCC-004 Candidate Pipeline | `pipeline list/show/add/set/advance/history` | 200 records, `MCP-YYYYMMDD-###` |
| Certified Allocation / Sleeve Summary | `portfolio list/show/set/sleeves` | bands, variance, actual-weight loading |
| 10 Candidate Comparison (PEW-004) | `pew004 list/show/set` | scoring, Zacks close-decision overlay, eligibility |
| 11 Conviction (PEW-005) | `conviction list/show/set` | effective conviction, decision state |
| 97 / 98 lists, data validation | `lists [NAME]` | controlled values |
| 00 CISC Dashboard (research view) | `dashboard` | readiness, module state, decisions required this week |

The other sheets are not part of this application: the CISC panels 01–05, Executive Summary,
Rebalancing, Sources & Certification, 99 Dashboard Data, PEW-001/002/003/006/007 and the
MOPS-002 freeze record.

## Everyday use

```bash
manifest-workbench dashboard                     # what needs a decision this week
manifest-workbench pipeline list --exceptions
manifest-workbench masr show EMR                 # every field, with column letter and kind

# edit input fields: use a field key, a unique key prefix or the worksheet column letter
manifest-workbench masr set VRT masr_id=MASR-0023 T=45 zacks=2 merrill=buy
manifest-workbench miar set VRT miar_id=MIAR-0023 integrity_score=82 mics_score=77 \
    record_status=active research_owner="Research Ops" review_cadence=quarterly \
    last_full_review=2026-09-01
manifest-workbench portfolio set NVDA actual_weight=2.9%

# add records (IDs are generated when omitted)
manifest-workbench evidence add ticker=VRT activity_type="company review" ...
manifest-workbench pipeline add ticker=PWR candidate_type=new source=other owner="Research Committee" due_date=2026-10-31

# stage gates
manifest-workbench pipeline advance MCP-20260824-001            # next stage, only if the current gate passes
manifest-workbench pipeline advance MCP-20260824-001 --to "On Watch"
manifest-workbench pipeline history MCP-20260824-001

manifest-workbench masr fields                   # field keys, columns, controlled values
manifest-workbench pipeline export pipeline.csv  # computed view to CSV (or .json)
manifest-workbench audit                         # who changed what, when
```

Global options go before the command. `--data PATH` or `$MANIFEST_DATA` sets the data file.
`--as-of YYYY-MM-DD` or `$MANIFEST_AS_OF` sets the date used for TODAY(). `--by NAME` or
`$MANIFEST_USER` sets the operator name recorded in the audit trail. `--no-color` turns off colour.

Controlled-list values are matched without regard to case or dash style, and a unique prefix
is enough. For example, `stage=referred` means `Referred to PEW-004`, and `status="Closed - No Action"`
means `Closed — No Action`. Weights accept `3.1%`, `0.031` or `3.1`. An empty value (`field=`)
clears a field.

## Controls the app enforces

- **Only input fields can be edited.** Calculated and linked fields are rejected. Certified
  MFPDF data is locked: symbols, target weights, sleeves and roles, and the identity and
  class of the 47 certified registry rows. Changing it requires a new certified MFPDF version.
- **One identity per security.** Duplicate canonical MASR IDs, MIAR IDs and registry tickers
  are blocked. Record IDs must follow `EVD-`, `MIR-` or `MCP-YYYYMMDD-###` and cannot change.
- **Controlled vocabularies.** Every validation-listed field accepts only values from its list.
- **Stage gates.** New candidates enter at `Intake`. A candidate moves forward only after its
  current stage gate passes; moving back is always allowed. Closed, rejected and removed
  candidates keep their final disposition.
- **Capacity.** The limits are 150 MASR slots and 200 records each for the pipeline, evidence
  ledger and review log.
- **Audit trail.** Every edit records a timestamp, the operator, the field, and the old and new values.
- After every edit, the app shows the record's recalculated control status. It also names any
  required fields that are still missing.

## Importing a workbook

```bash
pip install openpyxl
manifest-workbench init --force --from-xlsx path/to/Manifest_Workbench_v0_4.xlsx
```

The import reads only the input (yellow) cells and the certified schedule. Formula cells are
ignored and recalculated. The bundled data (`manifest_workbench/data/seed.json`) is exactly
the v0.4 workbook's inputs, and the golden test checks that.

## Findings from the v0.4 workbook

- **Non-holding candidates cannot pass eligibility yet.** The RCC-003 MIAR registry has rows
  only for the 47 certified holdings. RCC-004 reads the MIAR ID, status, freshness and scores
  from that range. Candidates such as EMR or HUBB therefore always show `MIAR SETUP REQUIRED`
  and `NOT ELIGIBLE`, and cannot pass the Eligibility Review gate until RCC-003 covers
  non-holdings. The app reproduces this behaviour as is.
- **All 10 candidates are overdue.** The workbook's saved results were calculated as of
  2026-08-24. The 10 Barron's roundtable candidates were due on 2026-09-23, so on any later
  date they all show `OVERDUE`.
- **Two conviction vocabularies.** Certified Allocation uses `Tier 1/2/3`, while PEW-005 scores
  only `Tier 1 — Anchor`, `Tier 2 — Core` and `Tier 3 — Opportunistic`. An MFPDF tier with
  no PEW-005 proposal therefore scores 0.
- **Blank lookups.** In desktop Excel, an `INDEX` onto an empty cell returns `0` rather than a
  blank. That can hide "MIAR ID missing" checks. The app treats missing data as missing, which
  matches the results saved in the file.
- **Fuller summary tables.** The RCC-004 pipeline snapshot lists 8 of the 12 stages, and the
  RCC-002 activity table leaves out `Other Research Signal`. The app shows every stage and
  activity type.

## Development

```bash
python -m unittest discover -s tests -t .   # the golden test needs openpyxl
```

- `manifest_workbench/engine.py`: the formula port. Each field is annotated with its worksheet column.
- `schema.py`: every column of every sheet, with its kind (input, calc, link or locked) and validation list.
- `ops.py`: controlled edits, stage gates and the audit trail.
- `cli.py` and `render.py`: the commands, the interactive console and terminal rendering.
- `xlsx_import.py`: workbook import.
