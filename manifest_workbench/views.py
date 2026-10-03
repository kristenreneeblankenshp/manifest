"""Sheet views for CISC-001 and MOPS-002, reference documents, the sheet index and cell reader."""

from __future__ import annotations

import datetime as dt
import json
from importlib import resources

from . import render as R
from . import schema as S
from .engine import blank

PEW_PRINCIPLE = (
    'MOPS-002 CONTROL PRINCIPLE — The certified portfolio remains the system of record. The '
    'Portfolio Engineering Workspace is a controlled scenario environment. No proposed change '
    'becomes operational until it is supported by evidence, approved through governance and '
    'incorporated into a newly certified MFPDF version.')
CISC_RULE = (
    'Operating Rule: the workbench is an executive decision-support interface. It does not modify '
    'the frozen portfolio merely because a band is breached, and it never authorizes automatic '
    'trades. The correct weekly output may be "NO COMMITTEE ACTION REQUIRED."')

# Every worksheet of the v0.4 workbook and the command that covers it.
SHEETS = (
    ('00 CISC Dashboard', 'cisc', 'Five-panel Chief Investment Steward Console'),
    ('01 Dashboard Controls', 'controls', 'Weekly operating inputs and composite alignment score'),
    ('02 Decision Center', 'decision-center', 'Decisions required this week; manual decision register'),
    ('03 Research Intelligence', 'intel', 'Research intelligence workspace (six sections)'),
    ('04 Committee Operations', 'committee', "Actions, publications, calendar, certifications, notebook"),
    ('05 Workbench Guide', 'doc workbench-guide', 'Operating guide and freeze record'),
    ('Executive Summary', 'doc executive-summary', 'MFPDF certification summary'),
    ('Certified Allocation', 'portfolio', 'Certified MFPDF allocation, bands and actual weights'),
    ('Sleeve Summary', 'portfolio sleeves', 'MFPDF sleeve allocation summary'),
    ('Rebalancing', 'doc rebalancing', 'Rebalancing control framework'),
    ('Sources & Certification', 'doc sources', 'Sources, reconciliation and certification record'),
    ('99 Dashboard Data', 'dashboard-data', 'Dashboard calculations: sleeves, top holdings, alerts'),
    ('06 PEW Control Center', 'pew', 'MOPS-002 Portfolio Engineering Workspace control center'),
    ('07 Mandate & Constraints', 'mandate', 'PEW-001 mandate and control register'),
    ('08 Sleeve Architecture', 'sleeves', 'PEW-002 sleeve architecture'),
    ('09 Role Assignment', 'roles', 'PEW-003 portfolio role assignment'),
    ('10 Candidate Comparison', 'pew004', 'PEW-004 candidate comparison'),
    ('11 Conviction', 'conviction', 'PEW-005 conviction and thesis control'),
    ('12 Allocation Lab', 'lab', 'PEW-006 allocation lab scenario'),
    ('13 Validation & Cert', 'validation', 'PEW-007 validation tests and certification workflow'),
    ('14 PEW Guide', 'doc pew-guide', 'MOPS-002 operating guide'),
    ('98 PEW Lists', 'lists', 'PEW controlled lists'),
    ('15 MOPS-002 Freeze Record', 'doc freeze-record', 'MOPS-002 certification and freeze record'),
    ('16 RCC-001 Control Center', 'rcc001', 'Executive research control center'),
    ('97 RCC Lists', 'lists', 'RCC controlled lists'),
    ('18 RCC-002 Evidence Ledger', 'evidence', 'Research intake and evidence ledger'),
    ('17 RCC-002 Control Center', 'rcc002', 'Evidence ledger control center'),
    ('19 RCC-003 Control Center', 'rcc003', 'MIAR dossier control center'),
    ('20 RCC-003 MIAR Registry', 'miar', 'MIAR dossier registry'),
    ('21 RCC-003 MIAR Review Log', 'review', 'MIAR review and certification log'),
    ('22 RCC-004 Control Center', 'rcc004', 'MASR registry and candidate pipeline control center'),
    ('23 RCC-004 MASR Registry', 'masr', 'Controlled MASR registry'),
    ('24 RCC-004 Candidate Pipeline', 'pipeline', 'MASR candidate pipeline'),
)

DOCS = {
    'workbench-guide': '05 Workbench Guide',
    'pew-guide': '14 PEW Guide',
    'freeze-record': '15 MOPS-002 Freeze Record',
    'executive-summary': 'Executive Summary',
    'rebalancing': 'Rebalancing',
    'sources': 'Sources & Certification',
}


def column_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch.upper()) - 64
    return n


def _pct(v, places=2):
    return '' if v in ('', None) else f'{v * 100:.{places}f}%'


def _num(v):
    return R.fmt(v, S.NUMBER)


def _kv(app, pairs, width=34):
    for label, value in pairs:
        shown = app.style.status(str(value)) if isinstance(value, str) else str(value)
        app.out(f'  {label:<{width}} {shown}')


def _table(app, headers, rows, status=(), max_col=40):
    app.out(R.table(app.style, headers, [[R.fmt(c) if not isinstance(c, str) else c for c in r]
                                         for r in rows], status_cols=list(status), max_col=max_col))


# =========================================================================== 00 CISC Dashboard

def cmd_cisc(app, args):
    wb = app.wb()
    cisc = wb.cisc()
    con, d = cisc.console, cisc.data
    report = R.fmt(con['report_date'], S.DATE)
    app.header('CHIEF INVESTMENT STEWARD CONSOLE (CISC)',
               f'MANIFEST INSTITUTIONAL INVESTMENT SYSTEM · CISC-001 EXECUTIVE CONSOLE v1.0 · '
               f'Report date {report}')

    app.out(R.section(app.style, '1 · Executive status'))
    app.out(R.tiles(app.style, [
        ('COMPOSITE ALIGNMENT', f"{con['score']:+.2f}"), ('TREND', f"{con['trend']:+.2f}"),
        ('CONFIDENCE', _pct(con['confidence'], 0)), ('PREVIOUS WEEK', f"{con['previous_week']:+.2f}"),
        ('CLASSIFICATION', con['classification']), ('CURRENT POSTURE', con['posture']),
    ]))
    _kv(app, [('Institutional compass', con['compass']),
              ('Executive recommendation', con['recommendation']),
              ('', con['detail']), ('', con['next_review'])])

    app.out(R.section(app.style, '2 · Portfolio health'))
    _table(app, ['Sleeve', 'Target', 'Actual', 'Variance'],
           [[s['sleeve'], _pct(s['target']), _pct(s['actual']), _pct(s['variance'])]
            for s in d['sleeves']])
    app.out(R.section(app.style, 'Top 10 holdings'))
    _table(app, ['Rank', 'Holding', 'Weight', 'Role', 'Conviction'],
           [[str(t['rank']), t['symbol'], _pct(t['weight']), t['role'], t['conviction']]
            for t in con['top10']], max_col=48)
    app.out(app.style.paint('  ' + con['ranking_basis'] + ' — ' + con['ranking_note'], R.DIM))
    app.out(R.section(app.style, 'Allocation alerts'))
    alerts = [a for a in con['alerts'] if a['symbol']]
    if alerts:
        _table(app, ['Rank', 'Holding', 'Actual', 'Target', 'Variance', 'Status', 'Action'],
               [[str(a['rank']), a['symbol'], _pct(a['actual']), _pct(a['target']),
                 _pct(a['variance']), a['band_status'], a['action']] for a in alerts],
               status=['Status'])
    app.out('  ' + app.style.status(con['alert_note']))
    app.out(app.style.paint('  ' + con['completeness_line'] +
                            '  ·  OUTSIDE BAND = REVIEW REQUIRED • NO AUTOMATIC TRADING', R.DIM))

    app.out(R.section(app.style, '3 · Research intelligence'))
    r = con['research']
    for label, key in (('Companies requiring review', 'review'), ('Earnings this week', 'events'),
                       ('Zacks Rank changes', 'zacks'), ('Merrill research updates', 'merrill'),
                       ('MIAR updates', 'miar'), ('Thesis / conviction reviews', 'thesis')):
        entries = [e for e in r[key] if e != 'No entry loaded'] or ['No entry loaded']
        app.out(f'  {label:<30} ' + app.style.paint(entries[0], R.DIM if entries[0] == 'No entry loaded'
                                                    else ''))
        for e in entries[1:]:
            app.out(f"  {'':<30} {e}")

    app.out(R.section(app.style, '4 · Committee operations'))
    _table(app, ['Pending Actions', 'Count'],
           [[label, _pct(v, 0) if label == 'Data Completeness' else str(v)] for label, v in con['pending']],
           status=['Count'])
    _kv(app, [('MWIR', con['mwir']), ('', con['mwir_status']), ('', con['mwir_last']),
              ('', con['mwir_next'])])
    _kv(app, [('Operational calendar', con['calendar'][0])] +
        [('', e) for e in con['calendar'][1:]])
    _kv(app, [('Certification status', con['certifications'][0])] +
        [('', e) for e in con['certifications'][1:] if e.strip(' —/')])
    _kv(app, [("Steward's notebook", ' · '.join(con['notebook']))])

    app.out(R.section(app.style, '5 · Manifest Decision Center — what decisions are actually required this week?'))
    app.out('  ' + app.style.paint(con['decision_state'], R.BOLD) if not app.style.enabled
            else '  ' + app.style.status(con['decision_state']))
    app.out(R.tiles(app.style, [tuple(t.split('\n', 1)) for t in con['tiles']]))
    app.out(R.paragraph(con['summary']))
    app.out(app.style.paint('\n  DASHBOARD • PORTFOLIO • RESEARCH • COMMITTEE ROOM • PUBLICATIONS • '
                            "LIBRARY — type 'sheets' for every worksheet and its command", R.DIM))


# =========================================================================== 01 / 02 / 03 / 04 / 99

def cmd_controls(app, args):
    wb = app.wb()
    c = wb.cisc().controls
    app.header('MANIFEST WORKBENCH — DASHBOARD CONTROLS',
               "CISC-001 | Founders Edition v1.0 | Weekly operating inputs: 'controls set field=value', "
               "'composite set COMPONENT score=… weight=…'")
    _kv(app, [(f.header, R.fmt(c.get(f.key), f.vtype)) for f in S.CONTROLS.fields
              if f.kind != S.AUTO])
    app.out(R.section(app.style, 'Composite components'))
    _table(app, ['Component', 'Score (-1 to +1)', 'Weight', 'Contribution'],
           [[r['component'], _num(r.get('score')), _pct(r.get('weight'), 0), f"{r['contribution']:.3f}"]
            for r in c['components']] +
           [['TOTAL / COMPOSITE', '', _pct(c['weight_total'], 0), f"{c['composite_score']:.3f}"]])
    app.out(R.section(app.style, 'Derived indicators'))
    _kv(app, [('Composite Alignment Score', f"{c['composite_score']:.2f}"),
              ('Weekly Change', f"{c['weekly_change']:+.2f}"), ('Current Posture', c['posture']),
              ('Compass Bias', c['compass_bias']), ('Score Classification', c['classification'])])
    app.out(R.section(app.style, 'Posture thresholds (change only by committee action)'))
    _table(app, ['Score Floor', 'Score Ceiling', 'Posture'],
           [['0.50', '1.00', 'Maintain / Opportunistic'], ['0.10', '0.49', 'Maintain / Balanced'],
            ['-0.09', '0.09', 'Hold / Disciplined'], ['-0.34', '-0.10', 'Defensive / Selective'],
            ['-1.00', '-0.35', 'Reduce Risk']])


def cmd_decision_center(app, args):
    wb = app.wb()
    dc = wb.cisc().decision
    app.header('MANIFEST DECISION CENTER', 'What decisions are actually required this week?')
    _table(app, ['Decision Metric', 'Current State', 'Governance Rule', 'Result'], [
        ['Decision State', dc['state'], 'Committee Meeting', dc['meeting']],
        ['Data Completeness', _pct(dc['completeness'], 0), 'Automatic Trading', 'PROHIBITED'],
        ['Missing Actual Weights', str(dc['missing_actual']), 'Current Weight Basis', dc['weight_basis']],
        ['Allocation Decisions', str(dc['allocation_decisions']), 'Rebalance Policy', 'Band-Based'],
        ['Research / Conviction Decisions', str(dc['research_decisions']), 'No-Action State', 'AUTHORIZED'],
        ['Manual Committee Decisions', str(dc['manual_decisions']), '', ''],
        ['Open Operating Actions', str(dc['open_actions']), '', ''],
        ['Total Committee Decisions', str(dc['total_decisions']), '', ''],
        ['Highest Priority', dc['priority'], '', ''],
    ], status=['Current State', 'Result'], max_col=44)
    app.out(R.section(app.style, 'System decision queue'))
    _table(app, ['ID', 'Category', 'Trigger', 'Decision Required', 'Authority', 'Status'],
           [[q['id'], q['category'], q['trigger'], q['decision'], q['authority'], q['status']]
            for q in dc['queue']], status=['Status'])
    app.out(R.section(app.style, 'Manual decision register'))
    app.out(app.rows_for('decisions', _filled(wb.table('decisions')), LIST_DECISIONS))
    app.out()
    app.out(R.paragraph(CISC_RULE))


LIST_DECISIONS = ('id', 'date_opened', 'category', 'decision', 'owner', 'due_date',
                  'committee_decision', 'status')


def _filled(rows):
    return [r for r in rows if any(not blank(v) for k, v in r.items() if not k.startswith('_'))]


def cmd_intel(app, args):
    wb = app.wb()
    app.header('RESEARCH INTELLIGENCE WORKSPACE',
               'Populate only verified current research. The dashboard reads the first active entries '
               "from each section. Edit with 'intel-review add …', 'intel-events set 2 …', 'intel-zacks clear 1'.")
    for name in S.INTEL_TABLES:
        table = S.TABLES[name]
        app.out(R.section(app.style, table.title.split(': ', 1)[-1]))
        app.out(app.rows_for(name, _filled(wb.table(name)), ('_slot',) + tuple(table.keys())))


def cmd_committee(app, args):
    wb = app.wb()
    app.header("COMMITTEE OPERATIONS & STEWARD'S NOTEBOOK",
               'Operating actions remain distinct from committee decisions. Use the explicit decision flag.')
    for name in S.COMMITTEE_TABLES:
        table = S.TABLES[name]
        app.out(R.section(app.style, table.title.split(': ', 1)[-1]))
        app.out(app.rows_for(name, _filled(wb.table(name)), ('_slot',) + tuple(table.keys())))


def cmd_dashboard_data(app, args):
    wb = app.wb()
    d = wb.cisc().data
    app.header('99 DASHBOARD DATA', 'Calculations behind the CISC portfolio-health and decision panels.')
    _kv(app, [('Missing Actual Weights', d['missing_actual']), ('Band Breaches', d['band_breaches']),
              ('Actual Portfolio Total', _pct(d['actual_total'])),
              ('Data Completeness', _pct(d['completeness'], 0)), ('Ranking Basis', d['ranking_basis']),
              ('Open Research Decisions', d['research_decisions']),
              ('Open Operating Actions', d['open_actions']),
              ('Committee-Decision Actions', d['committee_actions'])])
    app.out(R.section(app.style, 'Holdings ranking and alert scores'))
    _table(app, ['Rank', 'Symbol', 'Sleeve', 'Target', 'Actual', 'Ranking Weight', 'Band Status',
                 'Alert Score', 'Alert Rank'],
           [[str(h['rank']), h['symbol'], h['sleeve'], _pct(h['target']),
             '' if h['_actual_blank'] else _pct(h['actual']), _pct(h['ranking_weight']),
             h['band_status'], _pct(h['alert_score']), str(h['alert_rank'])]
            for h in sorted(d['holdings'], key=lambda h: h['rank'])], status=['Band Status'])


# =========================================================================== 06 / 12 / 13 PEW

def cmd_pew(app, args):
    wb = app.wb()
    pew = wb.pew()
    c = pew.control
    app.header('MOPS-002 — PORTFOLIO ENGINEERING WORKSPACE (PEW)',
               'PEW-001–PEW-007 | Founders Edition v1.0 — CERTIFIED & FROZEN | Certified MFPDF '
               'remains the sole system of record')
    app.out(R.tiles(app.style, [
        ('CURRENT IMPLEMENTATION STATE', c['implementation_state']),
        ('CERTIFIED POSITIONS', c['certified_positions']), ('ACTUAL WEIGHTS LOADED', c['actual_loaded']),
        ('CONVICTION ASSIGNED', c['conviction_assigned']), ('SCENARIO CHANGES', c['scenario_changes']),
        ('CERTIFICATION STATE', c['certification_state']),
    ]))
    _kv(app, [('Primary required action', c['primary_action'])], width=24)
    app.out(R.section(app.style, 'MOPS-002 module status'))
    _table(app, ['Module', 'Workspace', 'Current Status', 'Open Items', 'Next Required Action', 'Authority'],
           [[m[0], m[1], m[3], str(m[4]), m[5], m[6]] for m in c['modules']],
           status=['Current Status'], max_col=46)
    app.out(R.section(app.style, 'Engineering decision queue'))
    _table(app, ['#', 'Category', 'Trigger / Current State', 'Decision Required', 'Authority', 'Status'],
           [[str(q[0]), q[1], q[2], q[3], q[5], q[6]] for q in c['queue']], status=['Status'])
    app.out(R.section(app.style, 'Certified vs. scenario sleeve allocation'))
    _table(app, ['Sleeve', 'Certified Target', 'Scenario Allocation'],
           [[s['sleeve'], _pct(s['certified_target']), _pct(s['scenario'])] for s in pew.sleeves])
    app.out()
    app.out(R.paragraph(PEW_PRINCIPLE))


def cmd_lab(app, args):
    wb = app.wb()
    pew = wb.pew()
    lab = pew.lab
    app.header('MOPS-002 / PEW-006 — ALLOCATION ENGINEERING LAB',
               'Controlled scenario layer. The certified MFPDF portfolio remains unchanged until a new '
               "version is formally approved. Enter scenario weights with 'scenario set SYMBOL "
               "scenario_weight=… rationale=…'.")
    _kv(app, [('Scenario ID', lab.get('scenario_id', '')), ('Scenario Name', lab.get('scenario_name', '')),
              ('Prepared Date', R.fmt(lab.get('prepared_date'), S.DATE))], width=18)
    app.out(R.tiles(app.style, [
        ('SCENARIO STATUS', lab['scenario_status']), ('CERTIFIED TOTAL', _pct(lab['certified_total'])),
        ('SCENARIO TOTAL', _pct(lab['scenario_total'])), ('FUNDING BALANCE', _pct(lab['funding_balance'])),
        ('CHANGED POSITIONS', lab['changed_positions']), ('GROSS TURNOVER', _pct(lab['gross_turnover'])),
        ('BAND EXCEPTIONS', lab['band_exceptions']), ('CURRENT ACTUAL TOTAL', _pct(lab['actual_total'])),
        ('ACTUAL WEIGHTS LOADED', lab['actual_loaded']), ('IMPLEMENTATION READINESS', lab['readiness']),
    ]))
    rows = pew.scenario if getattr(args, 'all', False) else [r for r in pew.scenario if r['change'] != 0
                                                             or not blank(r.get('rationale'))]
    app.out(R.section(app.style, 'Scenario allocation schedule' +
                      ('' if getattr(args, 'all', False) else ' — changed positions (use --all for all 47)')))
    if rows:
        app.out(app.rows_for('scenario', rows, ('symbol', 'sleeve', 'certified_target', 'lower_band',
                                                'upper_band', 'scenario_weight', 'effective_weight',
                                                'change', 'funding', 'band_test', 'trigger',
                                                'validation_state')))
    else:
        app.out(app.style.paint('  No scenario changes: certified baseline preserved.', R.GREEN))


def cmd_validation(app, args):
    wb = app.wb()
    pew = wb.pew()
    cert, lab = pew.certification, pew.lab
    app.header('MOPS-002 / PEW-007 — PORTFOLIO SCENARIO VALIDATION & CERTIFICATION',
               'A portfolio scenario remains non-operational until every required review is complete '
               'and the Chief Investment Steward issues a newly certified MFPDF version.')
    app.out(R.tiles(app.style, [('OVERALL READINESS', cert['overall_readiness']),
                                ('CERTIFICATION STATE', cert['certification_state']),
                                ('SCENARIO', f"{lab.get('scenario_id', '')} — {lab.get('scenario_name', '')}"),
                                ('SCENARIO STATUS', lab['scenario_status'])], per_row=2))
    app.out(R.section(app.style, 'Materiality and construction controls'))
    _table(app, ['Validation Control', 'Value'],
           [[f.header, _pct(cert.get(f.key)) if f.vtype == S.PERCENT else R.fmt(cert.get(f.key), f.vtype)]
            for f in S.CERTIFICATION.fields if f.col.startswith('B')])
    app.out(R.section(app.style, 'Automated validation tests'))
    _table(app, ['Test', 'Validation Test', 'Current Result', 'Standard / Threshold', 'Status', 'Authority'],
           [[t['id'], t['test'], _result(t), t['standard'], t['status'], t['authority']]
            for t in pew.tests], status=['Status'], max_col=44)
    app.out(R.section(app.style, 'Formal portfolio scenario certification workflow'))
    app.out(app.rows_for('workflow', pew.workflow, ('stage', 'status', 'reviewed_by', 'review_date',
                                                    'evidence_ref', 'notes', 'blocking')))
    _kv(app, [('Proposed MFPDF Version', cert.get('proposed_version', '')),
              ('Effective Date', R.fmt(cert.get('effective_date'), S.DATE)),
              ('Certification State', cert['certification_state'])], width=24)
    changes = [r for r in pew.changes if any(not blank(r.get(k)) for k in ('symbol_sleeve', 'change_type',
                                                                          'certified_weight',
                                                                          'proposed_weight'))]
    app.out(R.section(app.style, 'Certification change register'))
    app.out(app.rows_for('changes', changes, ('change_id', 'symbol_sleeve', 'change_type', 'certified_weight',
                                              'proposed_weight', 'delta', 'rationale', 'outcome')))
    app.out(app.style.paint('  No scenario becomes operational until the new MFPDF is issued. '
                            'Automatic trading remains prohibited.', R.DIM))


def _result(t):
    v = t['result']
    if isinstance(v, float) and t['id'] in ('VAL-001', 'VAL-002', 'VAL-003', 'VAL-006', 'VAL-007', 'VAL-008'):
        return _pct(v, 4 if t['id'] in ('VAL-001', 'VAL-002') else 2)
    return R.fmt(v)


# =========================================================================== reference docs

def load_docs():
    text = resources.files('manifest_workbench').joinpath('data/docs.json').read_text('utf-8')
    return json.loads(text)


def cmd_doc(app, args):
    if not args.name:
        app.header('REFERENCE DOCUMENTS')
        _table(app, ['Name', 'Worksheet'], [[k, v] for k, v in DOCS.items()])
        return
    name = args.name.lower()
    matches = [k for k in DOCS if k.startswith(name)]
    if len(matches) != 1:
        from .ops import OpError
        raise OpError(f"Unknown document '{args.name}'. Try: {', '.join(DOCS)}")
    sheet = DOCS[matches[0]]
    rows = load_docs()[sheet]
    cells = app.wb().cells().get(sheet, {})
    app.header(sheet.upper())
    block = []
    for _, cells_in_row in rows:
        values = []
        for col, v in cells_in_row:
            if isinstance(v, dict):
                v = cells.get(v['cell'], '')
                v = _pct(v) if isinstance(v, float) else R.fmt(v)
            values.append((col, R.fmt(v) if not isinstance(v, str) else v))
        if len(values) == 1:
            _flush(app, block)
            block = []
            text = values[0][1]
            app.out(R.paragraph(text) if len(text) > 60 else R.section(app.style, text))
            continue
        block.append(values)
    _flush(app, block)


def _flush(app, block):
    """Render a run of rows; side-by-side tables (separated by an empty column) render apart."""
    if not block:
        return
    used = sorted({column_index(col) for row in block for col, _ in row})
    # Merged cells leave gaps inside one table (A, D, H); a separate side-by-side table starts
    # after a gap that follows a run of at least two adjacent columns.
    segments, current, run = [], [used[0]], 1
    for c in used[1:]:
        if c - current[-1] > 1:
            if run >= 2:
                segments.append(current)
                current = []
            run = 0
        current.append(c)
        run += 1
    segments.append(current)
    for seg in segments:
        rows = [[dict((column_index(c), v) for c, v in row).get(i, '') for i in seg] for row in block]
        rows = [r for r in rows if any(r)]
        if not rows:
            continue
        header, body = rows[0], rows[1:]
        longest = max((len(v) for r in body for v in r), default=0)
        if len(seg) == 1:
            app.out('  ' + app.style.paint(header[0], R.BOLD))
            for r in body:
                app.out(R.paragraph(r[0], indent='    '))
        elif not body or (len(seg) <= 4 and longest <= 44):
            app.out(R.table(app.style, header, body or [[''] * len(seg)], max_col=70))
        else:
            for r in body:
                app.out('  ' + app.style.paint(r[0], R.BOLD))
                for h, v in zip(header[1:], r[1:]):
                    if v:
                        app.out(R.paragraph(f'{h}: {v}', indent='    '))
        app.out()


# =========================================================================== sheet index / cell

def cmd_sheets(app, args):
    app.header('WORKBOOK SHEETS', 'Every worksheet of the Manifest Workbench v0.4 and the command '
                                  'that covers it. Type the command to open the sheet.')
    _table(app, ['Worksheet', 'Command', 'Contents'], [list(s) for s in SHEETS], max_col=60)


def cmd_cell(app, args):
    from .ops import OpError
    cells = app.wb().cells()
    wanted = args.sheet.lower()
    names = [s for s, *_ in SHEETS]
    hits = [s for s in names if s.lower() == wanted] or [s for s in names if s.lower().startswith(wanted)] \
        or [s for s in names if wanted in s.lower()]
    if len(hits) != 1:
        raise OpError(f"Sheet '{args.sheet}' is ambiguous or unknown: {hits or names}")
    sheet = hits[0]
    ref = args.ref.upper().replace('$', '')
    if ref not in cells.get(sheet, {}):
        raise OpError(f'{sheet}!{ref} is not a formula cell. Input cells are shown by the sheet command '
                      f"('{next(c for s, c, _ in SHEETS if s == sheet)}').")
    value = cells[sheet][ref]
    shown = value.isoformat() if isinstance(value, (dt.date, dt.datetime)) else repr(value)
    app.out(f'{sheet}!{ref} = {shown}')
