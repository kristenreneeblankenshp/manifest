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

It runs two ways over the same engine:

- a **hosted web console** for day-to-day operation: one-click data pulls, decisions,
  reviews and report PDFs (see [Web console](#web-console) below)
- a **terminal console** (`manifest-workbench`) that covers every sheet from the command line

The weekly MWIR is built inside the web console, in the official 8-page layout of the
`mwir/` browser builder (see [MWIR](#mwir) below). The standalone builder in `mwir/` still
works on its own, and its saved documents can be imported into the console.

## Install and run

```bash
pip install .                 # or: pip install '.[xlsx]' to import .xlsx workbooks
manifest-workbench            # interactive console, opening on the CISC dashboard
                              # (creates ./manifest_workbench.json on first run)
manifest-workbench sheets     # every worksheet and the command that opens it
python -m manifest_workbench  # equivalent, without installing
```

The app only needs the Python 3.9+ standard library. Importing a `.xlsx` file needs `openpyxl`.

## Web console

```bash
pip install '.[web]'
manifest-workbench serve            # http://127.0.0.1:8000; data in ./data
```

On first visit the console asks you to create the administrator account. Then everything
the workbook asked you to do by hand happens in the browser:

| Area | What it does |
|---|---|
| **Console** | The CISC-001 five-panel view, led by **This week**: six steps (pull Zacks, actual weights, research and triage, decide, MWIR, sign off) that turn green as the weekly review's live checks pass. Each step has its action button. |
| **MWIR** | The official 8-page Weekly Institutional Report, edited beside a live preview. See [MWIR](#mwir). |
| **Data connections** | **Zacks**: one click updates Zacks Rank and market cap across the MASR registry and PEW-004 candidates, through your subscription's API or by uploading a Zacks screen CSV. Each rank change goes into Research Intelligence and becomes a complete RCC-002 evidence record. **Weights**: upload the broker positions CSV (weight, market value or quantity × price, with symbols like `BRK/B` normalised), check the preview and apply. **Research**: new SEC EDGAR 8-K/10-Q/10-K filings, plus your Zacks research feed if configured, arrive in a triage inbox. From there, one click logs an item as prefilled evidence, queues it for review or dismisses it. |
| **Decisions** | Everything waiting on a decision in one place: candidates awaiting committee disposition, MASR dispositions, PEW-004 comparisons, conviction assignments, band exceptions, certification reviews and the manual decision register. Each item is decided in place. |
| **Actions & notebook** | Actions, priorities, open questions, projects, publications, calendar and certifications, with inline status changes. |
| **Candidate pipeline** | A board by stage. A candidate advances only once its stage gate passes, and each card has disposition and closure controls. |
| **Allocation lab / Validation** | Enter scenario weights and rationale in a grid. Record each certification workflow decision, stamped with your name and date. |
| **Every sheet** | A form for every input table, with calculated columns shown read-only, locked certified fields, missing-field warnings and per-record history. `All workbook sheets` maps each worksheet to its page. |
| **Reviews** | Weekly, monthly and quarterly checklists taken from the Workbench Guide, PEW guide and RCC-004 standard. Each item is checked live against the data. An item whose check fails can be confirmed only with an exception note. Sign-off needs every item, and reopening a signed-off review needs a reason. |
| **Reports** | Drafts of the MIRD, MOR (monthly), Quarterly Engineering Review and MIPR, built from live data. You can edit any narrative, hide sections, add your own sections, refresh the data (your edits are kept) and preview. Draft PDFs carry a DRAFT watermark. **Issue** produces the final PDF as a numbered version and updates the publication row in Committee Operations. |
| **Audit trail** | Every edit, pull, decision, sign-off and issue, with who made it and the old and new values. |

**Navigation.** The sidebar follows the operating cycle: *Operate* (console, decisions, actions),
*Weekly cycle* (data and inbox, MWIR, reviews, reports), *Research*, *Portfolio* and *System*. Hub
pages (Research, Portfolio, Engineering) carry sub-tabs for their registers and workspaces.
**Jump to…** in the top bar (Ctrl/⌘ K) opens any page or workbook table by name.

Roles: **admin** (users and connector settings), **editor** (everything else) and **viewer**
(read-only). Add users under *Settings & users*, or with `manifest-workbench user NAME --role editor`.
The **As of** date in the top bar evaluates the workbook's `TODAY()` as a chosen date.

### MWIR

Each week's MWIR opens from *MWIR* in the sidebar (or step 5 on the console):

1. **Start this week's MWIR.** It starts from last week's document, so holdings, sleeves,
   guidance, rationale and narrative carry forward. Week ending (the Friday) and publication date
   (the Monday) are set from the review week.
2. **Load the holdings file** (`Date, Symbol, Weights`, the dynamic holdings template). Decimal
   weights become percentages. Tickers new this week take their sleeve, MFPDF baseline and role
   from the certified portfolio, and only names outside it are left `Unassigned`. Dropped tickers
   are listed.
3. **Edit** holdings, signals (composite, compass, component scores, risk tape), narrative, and
   controls and sources. Changes save as you type and the 8-page preview beside the editor
   updates. *Add this week's earnings to event gates* writes gate lines for holdings that report
   during the publication week.
4. **Issue.** The final PDF is versioned, the week's Zacks data is frozen with it, the MWIR row
   in Committee Operations is updated and the weekly review's MWIR item passes. If control
   assertions are failing (`HOLD · CONTROLS FAILING`), issuing needs an override reason, which
   is printed on page 8 and recorded in the audit trail. *Reopen to revise* issues a new version.

The calculations match the browser builder:
- **Bands:** 75–125% of target, floored at 1.00% and capped at 4.00%.
- **Control assertions:** holdings present, a 100.00% total, Strategic Anchors matching the frozen
  total (defaulted from the certified portfolio, 22.51%), no BRK.B executable rows, nothing above
  4.00%, and no unassigned sleeves.
- **Zacks screen:** market cap above $100B and Zacks Rank 1–3, with Rank 1–2 as Tier 1. ETFs carry
  their ETF rank, and MMC is listed by Zacks as MRSH.
- **Gauge zones:** 70+ green, 55–69 yellow, 40–54 orange, below 40 red. These are an assumption
  until the framework's thresholds are supplied.

The screen reads the **Zacks snapshot**. Every Zacks pull, by API or CSV, updates it with Zacks
Rank, market cap and next earnings date. CSVs may carry a `Next EPS Report Date` column, and the
API field is set in *Settings*. Until the first pull it uses the 25 Sep 2026 snapshot that ships
with `mwir/zacks.js`. *More → Export* downloads the document as JSON, and *Import* accepts that
file or a document saved by the browser builder.

### Connector setup

- **Zacks.** Under *Settings*, enter your subscription's endpoint as a URL template with
  `{ticker}`, say whether the key goes in the query string or a header, and give the response
  field names for rank and market cap. Dotted paths such as `data.zacks_rank` work, as does
  the unit of market cap. Keep the key in `ZACKS_API_KEY` on the server rather than in the
  data file if you can. Until the API is configured, the CSV upload works with any Zacks
  screen export that has Ticker plus Zacks Rank and/or Market Cap columns.
- **SEC EDGAR.** The SEC requires a contact e-mail on automated requests. Set it in
  *Settings* or in `SEC_CONTACT_EMAIL`. ETFs are skipped.
- **Merrill.** Merrill has no public research API, so Merrill status stays a manual field.
  Positions come in through the broker CSV upload.

### Hosting

The app is one Python process with a JSON data file guarded by a file lock, so run a
**single instance with a persistent disk**. The disk holds the data file, issued PDFs and
the session key.

```bash
docker compose up -d                       # builds the image; data in the manifest-data volume
# or any container host (Render, Fly.io, Railway, a VM):
docker build -t manifest-workbench .
docker run -p 8000:8000 -v manifest-data:/data manifest-workbench
```

The image runs `gunicorn 'manifest_workbench.web:create_app()'` with one worker and eight
threads. On a platform without Docker, use the same command after `pip install '.[web]'`.

| Variable | Purpose |
|---|---|
| `MANIFEST_DATA_DIR` | Data directory (default `./data`, `/data` in the image). |
| `MANIFEST_SECRET_KEY` | Session signing key. If unset, one is generated and stored in the data directory. |
| `MANIFEST_ADMIN_USER`, `MANIFEST_ADMIN_PASSWORD` | Create the first administrator while no users exist. Otherwise use the `/setup` page. |
| `MANIFEST_SECURE_COOKIES=1` | Set this when served over HTTPS, which you should use in production. |
| `MANIFEST_PROXY=1` | Trust `X-Forwarded-*` headers from a reverse proxy or platform load balancer. It is on in the image. |
| `ZACKS_API_KEY`, `SEC_CONTACT_EMAIL` | Connector credentials. These override *Settings*. |

To start from your own workbook instead of the bundled v0.4 inputs:
`manifest-workbench --data data/manifest_workbench.json init --from-xlsx workbook.xlsx --force`.
Back up the data directory like any database.

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
pip install -e '.[web,xlsx]'
python -m unittest discover -s tests -t .   # the golden test needs openpyxl; web tests need the web extra
```

- `engine.py`: MFPDF, PEW-004/005 and RCC-001 to RCC-004.
- `pew.py`: PEW-001, 002, 003, 006 and 007, and the PEW control center.
- `cisc.py`: dashboard controls, 99 Dashboard Data, Decision Center and the console.
- `cells.py`: maps every formula cell to an engine value, for the golden test and `cell`.
- `schema.py`: every table, its fields, kinds and validation lists.
- `ops.py`: controlled edits.
- `cli.py`, `views.py` and `render.py`: the console.
- `xlsx_import.py`: workbook import.
- `repo.py`: the locked data file shared by web requests.
- `connectors/`: Zacks (API and CSV), broker weights CSV and research (SEC EDGAR, Zacks research).
- `reviews.py`: weekly, monthly and quarterly review checklists and sign-off.
- `reports.py` and `pdf.py`: report drafts (MIRD, MOR, QER, MIPR, and the MWIR lifecycle) and PDF rendering.
- `mwir.py` and `mwir_pdf.py`: the official MWIR (port of the `mwir/` builder) and its 8-page landscape PDF.
- `web/`: the Flask console (auth, pages, templates and styles).
