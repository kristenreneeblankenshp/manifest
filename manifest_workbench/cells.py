"""Every formula cell of the Manifest Workbench v0.4, computed by the engine.

``workbook_cells(wb)`` returns ``{sheet: {cell: value}}`` covering all 13,950
formula cells in the workbook. It is the basis of the golden test and of the
``cell`` command, which reads any calculated cell by sheet and reference.
"""

from __future__ import annotations

from . import schema as S
from .cisc import CISC, as_datetime
from .engine import blank, isin
from .pew import PEW

ROW_TABLES = [name for name, t in S.TABLES.items() if t.mode != 'single']


def workbook_cells(wb, pew: PEW = None, cisc: CISC = None) -> dict:
    pew = pew or PEW(wb)
    cisc = cisc or CISC(wb, pew)
    cells = {}

    def put(sheet, ref, value):
        cells.setdefault(sheet, {})[ref] = value

    views = {'portfolio': wb.portfolio, 'conviction': wb.conviction, 'pew004': wb.pew004,
             'evidence': wb.evidence, 'miar': wb.miar, 'review': wb.review, 'masr': wb.masr,
             'pipeline': wb.pipeline, 'composite': cisc.controls['components'],
             'mandate': pew.mandate, 'sleeves': pew.sleeves, 'roles': pew.roles,
             'scenario': pew.scenario, 'workflow': pew.workflow, 'changes': pew.changes}
    for name, rows in views.items():
        table = S.TABLES[name]
        count = table.capacity if table.mode in ('register', 'slots', 'fixed') else len(rows)
        for i in range(count):
            row = rows[i] if i < len(rows) else None
            excel_row = table.first_row + i
            for f in table.fields:
                computed = f.kind in (S.AUTO, S.LINK) or (name == 'mandate' and row and row.get('_computed')
                                                          and f.key in ('operating_value', 'status'))
                if not computed:
                    continue
                value = '' if row is None else row.get(f.key, '')
                if name == 'workflow' and f.key in ('scenario_id', 'scenario_name'):
                    continue
                put(table.sheet, f'{f.col}{excel_row}', _excel(value))
        if name == 'workflow':
            for i, row in enumerate(rows):
                put(table.sheet, f'H{38 + i}', row['scenario_id'])
                put(table.sheet, f'I{38 + i}', row['scenario_name'])

    for row in wb.masr:  # certified rows link identity and role to the MFPDF (B, C, G, H, I)
        pos = row.get('_linked')
        if pos is not None:
            for col, key in (('B', 'ticker'), ('C', 'security'), ('G', 'sleeve'), ('H', 'role'),
                             ('I', 'security_type')):
                put(S.MASR.sheet, f'{col}{S.MASR.first_row + pos}', row.get(key))

    singles = {'controls': cisc.controls, 'lab': pew.lab, 'validation': pew.certification}
    for name, rec in singles.items():
        for f in S.TABLES[name].fields:
            if f.kind == S.AUTO:
                put(S.TABLES[name].sheet, f.col, rec.get(f.key, ''))

    _mfpdf(wb, put)
    _registers(wb, put)
    _rcc(wb, put)
    _pew(wb, pew, put)
    _cisc(wb, pew, cisc, put)
    return cells


def _excel(v):
    return v


# --------------------------------------------------------------------------- MFPDF sheets

def _mfpdf(wb, put):
    t = wb.portfolio_totals()
    put('Certified Allocation', 'F53', t['target_total'])
    put('Certified Allocation', 'I53', t['actual_total'])
    put('Certified Allocation', 'J53', t['actual_total'] - t['target_total'])
    put('Certified Allocation', 'K53', t['certification'])
    put('Executive Summary', 'B9', t['target_total'])
    for i, s in enumerate(wb.sleeve_summary()):
        r = 4 + i
        for col, key in (('B', 'positions'), ('C', 'equities'), ('D', 'etfs'), ('E', 'target'),
                         ('F', 'target')):
            put('Sleeve Summary', f'{col}{r}', s[key])
    total = sum(s['target'] for s in wb.sleeve_summary())
    put('Sleeve Summary', 'E12', total)
    put('Sleeve Summary', 'F12', total)
    conv = wb.conviction
    put('11 Conviction', 'F52', sum(1 for r in conv if r['current_conviction'] != 'Unassigned'))
    put('11 Conviction', 'H52', sum(1 for r in conv if r['effective_conviction'] != 'Unassigned'))
    put('11 Conviction', 'O52', sum(1 for r in conv if r['decision_state'] != 'NO CHANGE'))
    put('10 Candidate Comparison', 'B11', 1.0)


def _registers(wb, put):
    ev = [r for r in wb.evidence if not blank(r.get('evidence_id'))]
    closed = ('Closed — No Action', 'Closed — Incorporated')
    put('18 RCC-002 Evidence Ledger', 'AC6', len(ev))
    put('18 RCC-002 Evidence Ledger', 'AC7', sum(1 for r in ev if not isin(r.get('status'), closed)))
    put('18 RCC-002 Evidence Ledger', 'AC8', len(wb.evidence_exceptions()))
    put('18 RCC-002 Evidence Ledger', 'AC9',
        sum(1 for r in ev if r['referral_eligibility'] == 'ELIGIBLE FOR ROUTING'))
    put('18 RCC-002 Evidence Ledger', 'AC10', sum(1 for r in ev if r['control_status'] == 'OVERDUE'))
    m = wb.miar
    put('20 RCC-003 MIAR Registry', 'X6', len(m))
    put('20 RCC-003 MIAR Registry', 'X7', sum(1 for r in m if r['dossier_completeness'] == 'COMPLETE'))
    put('20 RCC-003 MIAR Registry', 'X8', len(wb.miar_exceptions()))
    put('20 RCC-003 MIAR Registry', 'X9', sum(1 for r in wb.review if not blank(r.get('review_id'))))
    put('20 RCC-003 MIAR Registry', 'X10', sum(r['miar_actions_pending'] for r in m))
    rv = [r for r in wb.review if not blank(r.get('review_id'))]
    put('21 RCC-003 MIAR Review Log', 'R6', len(rv))
    put('21 RCC-003 MIAR Review Log', 'R7', sum(1 for r in rv if r['control_status'] == 'COMPLETE'))
    put('21 RCC-003 MIAR Review Log', 'R8', sum(1 for r in rv if r['control_status'] != 'COMPLETE'))
    put('21 RCC-003 MIAR Review Log', 'R9',
        sum(1 for r in rv if r['control_status'] == 'CERTIFICATION REQUIRED'))
    put('21 RCC-003 MIAR Review Log', 'R10',
        sum(1 for r in rv if r.get('certification_rec') == 'Escalate to RCC-007'))
    s4 = wb.rcc004()['state']
    put('23 RCC-004 MASR Registry', 'AE6', s4['records_loaded'])
    put('23 RCC-004 MASR Registry', 'AE7', s4['certified_holdings'])
    put('23 RCC-004 MASR Registry', 'AE8', s4['approved_non_holdings'])
    put('23 RCC-004 MASR Registry', 'AE9', len(wb.masr_exceptions()))
    put('23 RCC-004 MASR Registry', 'AE10',
        sum(r.get('pipeline_records') or 0 for r in wb.masr if not blank(r.get('ticker'))))
    pipe = [r for r in wb.pipeline if not blank(r.get('candidate_id'))]
    put('24 RCC-004 Candidate Pipeline', 'AM6', len(pipe))
    put('24 RCC-004 Candidate Pipeline', 'AM7', sum(1 for r in pipe if r['gate_result'] == 'PASS — STAGE GATE'))
    put('24 RCC-004 Candidate Pipeline', 'AM8', len(wb.pipeline_exceptions()))
    put('24 RCC-004 Candidate Pipeline', 'AM9', sum(1 for r in pipe if r['control_status'] == 'OVERDUE'))
    put('24 RCC-004 Candidate Pipeline', 'AM10', s4['pew_referrals'])


def _controls(put, sheet, controls, count_col, state_col):
    for i, c in enumerate(controls):
        put(sheet, f'{count_col}{18 + i}', c['count'])
        put(sheet, f'{state_col}{18 + i}', c['state'])


def _rcc(wb, put):
    d = wb.rcc001()
    s = d['state']
    sh = '16 RCC-001 Control Center'
    for ref, key in (('A7', 'readiness'), ('G7', 'certified_holdings'), ('K7', 'activity_records'),
                     ('O7', 'conviction_assigned'), ('S7', 'thesis_assigned'),
                     ('G12', 'mfpdf_research_status'), ('M12', 'control_exceptions')):
        put(sh, ref, s[key])
    _controls(put, sh, d['controls'], 'C', 'D')
    for i, (_, n) in enumerate(d['snapshot']):
        put(sh, f'K{18 + i}', n)

    d = wb.rcc002()
    s = d['state']
    sh = '17 RCC-002 Control Center'
    for ref, key in (('A7', 'total_records'), ('E7', 'open'), ('I7', 'critical_high'), ('M7', 'overdue'),
                     ('Q7', 'unverified'), ('U7', 'referrals_ready'), ('A13', 'readiness'),
                     ('G13', 'miar_actions'), ('M13', 'thesis_conviction_actions'),
                     ('S13', 'pew_referrals')):
        put(sh, ref, s[key])
    for i, a in enumerate(d['activity'][:11]):
        for col, key in zip('BCDEFG', ('total', 'open', 'critical_high', 'unverified', 'overdue',
                                       'referral_ready')):
            put(sh, f'{col}{18 + i}', a[key])
    for col in 'BCDEFG':  # row 29 has no activity label; an empty criterion matches no text entry
        put(sh, f'{col}29', 0)
    for i, (_, n, _) in enumerate(d['routing']):
        put(sh, f'J{18 + i}', n)
    for i, (_, n) in enumerate(d['materiality']):
        put(sh, f'P{18 + i}', n)
    for i, (_, n) in enumerate(d['direction']):
        put(sh, f'P{24 + i}', n)

    d = wb.rcc003()
    s = d['state']
    sh = '19 RCC-003 Control Center'
    for ref, key in (('A7', 'total_records'), ('E7', 'dossiers_complete'), ('I7', 'current'),
                     ('M7', 'due_overdue'), ('Q7', 'material_events'), ('U7', 'control_exceptions'),
                     ('A13', 'readiness'), ('G13', 'coverage'), ('M13', 'miar_actions'),
                     ('S13', 'rcc007_referrals')):
        put(sh, ref, s[key])
    _controls(put, sh, d['controls'], 'D', 'E')
    for i, x in enumerate(d['sleeves']):
        for col, key in zip('OPQRSTUVWX', ('records', 'complete', 'current', 'update_due', 'review_due',
                                           'overdue', 'material_event', 'setup_required', 'coverage',
                                           'primary')):
            put(sh, f'{col}{18 + i}', x[key])

    d = wb.rcc004()
    s = d['state']
    sh = '22 RCC-004 Control Center'
    for ref, key in (('A7', 'records_loaded'), ('E7', 'certified_holdings'), ('I7', 'approved_non_holdings'),
                     ('M7', 'active_candidates'), ('Q7', 'pew_referrals'), ('U7', 'control_exceptions'),
                     ('A13', 'readiness'), ('G13', 'capacity'), ('M13', 'stage_gates'), ('S13', 'routing')):
        put(sh, ref, s[key])
    _controls(put, sh, d['controls'], 'D', 'E')
    for i, (_, n, clear, exc) in enumerate(d['composition']):
        put(sh, f'O{18 + i}', n)
        put(sh, f'P{18 + i}', clear)
        put(sh, f'Q{18 + i}', exc)
    by_stage = {st: rest for st, *rest in d['stages']}
    for i, stage in enumerate(SHEET_STAGES):
        n, gate, exc = by_stage[stage]
        put(sh, f'S{18 + i}', n)
        put(sh, f'T{18 + i}', gate)
        put(sh, f'U{18 + i}', exc)


# The RCC-004 control center's pipeline snapshot lists these eight stages.
SHEET_STAGES = ('Intake', 'Evidence Gathering', 'MIAR Review', 'Eligibility Review',
                'Candidate Comparison', 'Committee Review', 'Referred to PEW-004', 'On Watch')


# --------------------------------------------------------------------------- MOPS-002

def _pew(wb, pew, put):
    tot = pew.sleeve_totals()
    sh = '08 Sleeve Architecture'
    for col, key in (('C', 'positions'), ('D', 'equities'), ('E', 'etfs'), ('F', 'certified_target'),
                     ('G', 'actual'), ('H', 'scenario'), ('I', 'delta'), ('M', 'conviction_assigned'),
                     ('N', 'conviction_completeness'), ('O', 'decision_state')):
        put(sh, f'{col}13', tot[key])
    rs = pew.role_summary()
    put('09 Role Assignment', 'F52', rs['passed'])
    put('09 Role Assignment', 'I52', rs['review_items'])
    put('09 Role Assignment', 'M52', rs['replacement_candidates'])
    lab = pew.lab
    sh = '12 Allocation Lab'
    put(sh, 'F58', lab['certified_total'])
    put(sh, 'I58', lab['actual_total'])
    put(sh, 'J58', lab['scenario_weight_total'])
    put(sh, 'K58', lab['scenario_total'])
    put(sh, 'L58', lab['change_total'])
    put(sh, 'R58', lab['gross_turnover'])
    sh = '13 Validation & Cert'
    for ref, key in (('J5', 'scenario_id'), ('J6', 'scenario_name'), ('J7', 'scenario_status'),
                     ('J8', 'certified_total'), ('J9', 'scenario_total'), ('J10', 'changed_positions'),
                     ('J11', 'gross_turnover')):
        put(sh, ref, lab.get(key, 0) if not blank(lab.get(key)) else 0)
    for i, t in enumerate(pew.tests):
        put(sh, f'C{16 + i}', t['result'])
        put(sh, f'E{16 + i}', t['status'])
    m = {r['control_id']: r for r in pew.mandate}
    put('14 PEW Guide', 'H38', m['PEW-001-25']['operating_value'])
    put('14 PEW Guide', 'J38', m['PEW-001-25']['status'])
    put('14 PEW Guide', 'H39', m['PEW-001-26']['operating_value'])
    put('14 PEW Guide', 'J39', m['PEW-001-26']['status'])
    c = pew.control
    sh = '06 PEW Control Center'
    for ref, key in (('A6', 'implementation_state'), ('G6', 'primary_action'), ('A11', 'certified_positions'),
                     ('D11', 'actual_loaded'), ('G11', 'conviction_assigned'), ('J11', 'scenario_changes'),
                     ('M11', 'certification_state')):
        put(sh, ref, c[key])
    for i, mod in enumerate(c['modules']):
        put(sh, f'D{18 + i}', mod[3])
        put(sh, f'E{18 + i}', mod[4])
    for i, q in enumerate(c['queue']):
        put(sh, f'C{29 + i}', q[2])
        put(sh, f'G{29 + i}', q[6])
    for i, s in enumerate(pew.sleeves):
        put(sh, f'R{5 + i}', s['sleeve'])
        put(sh, f'S{5 + i}', s['certified_target'])
        put(sh, f'T{5 + i}', s['scenario'])


# --------------------------------------------------------------------------- CISC-001

def _cisc(wb, pew, cisc, put):
    c, d, dc, con = cisc.controls, cisc.data, cisc.decision, cisc.console
    sh = '01 Dashboard Controls'
    put(sh, 'D24', c['composite_score'])

    sh = '99 Dashboard Data'
    for i, s in enumerate(d['sleeves']):
        r = 2 + i
        put(sh, f'A{r}', s['sleeve'])
        put(sh, f'B{r}', s['target'])
        put(sh, f'C{r}', s['actual'])
        put(sh, f'D{r}', s['variance'])
    for i, t in enumerate(d['top10']):
        r = 2 + i
        for col, key in zip('STUVW', ('symbol', 'security', 'weight', 'role', 'conviction')):
            put(sh, f'{col}{r}', t[key])
    for i, h in enumerate(d['holdings']):
        r = 12 + i
        for col, key in zip('BCDEFGHIJKLMNOP', ('symbol', 'security', 'sleeve', 'target', 'actual',
                                                 'ranking_weight', 'rank', 'role', 'conviction',
                                                 'lower', 'upper', 'band_status', 'action',
                                                 'alert_score', 'alert_rank')):
            put(sh, f'{col}{r}', h[key])
    for i, a in enumerate(d['alerts']):
        r = 15 + i
        for col, key in zip('STUVWX', ('symbol', 'actual', 'target', 'variance', 'band_status', 'action')):
            put(sh, f'{col}{r}', a[key])
    for ref, key in (('B61', 'missing_actual'), ('B62', 'band_breaches'), ('B63', 'actual_total'),
                     ('B64', 'completeness'), ('B65', 'ranking_basis'), ('B66', 'research_decisions'),
                     ('B67', 'open_actions'), ('B68', 'committee_actions')):
        put(sh, ref, d[key])

    sh = '02 Decision Center'
    for ref, key in (('B6', 'state'), ('E6', 'meeting'), ('B7', 'completeness'), ('B8', 'missing_actual'),
                     ('E8', 'weight_basis'), ('B9', 'allocation_decisions'), ('B10', 'research_decisions'),
                     ('B11', 'manual_decisions'), ('B12', 'open_actions'), ('B13', 'total_decisions'),
                     ('B14', 'priority')):
        put(sh, ref, dc[key])
    for i, q in enumerate(dc['queue'][:4]):
        put(sh, f'C{19 + i}', q['trigger'])
        put(sh, f'D{19 + i}', q['decision'])
        put(sh, f'G{19 + i}', q['status'])

    sh = '00 CISC Dashboard'
    put(sh, 'S1', as_datetime(con['report_date']))
    for ref, key in (('Q6', 'recommendation'), ('N9', 'posture'), ('Q10', 'detail'), ('C12', 'score'),
                     ('G12', 'trend'), ('G13', 'confidence'), ('K13', 'compass'), ('G14', 'previous_week'),
                     ('Q14', 'next_review'), ('G15', 'classification'), ('Q24', 'alert_note'),
                     ('J29', 'ranking_basis'), ('Q30', 'completeness_line'), ('J31', 'ranking_note'),
                     ('H48', 'mwir'), ('H51', 'mwir_status'), ('H53', 'mwir_last'), ('H55', 'mwir_next'),
                     ('C61', 'decision_state'), ('C69', 'summary')):
        put(sh, ref, con[key])
    for i, t in enumerate(con['top10']):
        r = 19 + i
        for col, key in zip('JKMNP', ('rank', 'symbol', 'weight', 'role', 'conviction')):
            put(sh, f'{col}{r}', t[key])
    for i, a in enumerate(con['alerts']):
        r = 19 + i
        for col, key in zip('QRSTUVX', ('rank', 'symbol', 'actual', 'target', 'variance', 'band_status',
                                        'action')):
            put(sh, f'{col}{r}', a[key])
    research = con['research']
    for col, key, rows in (('C', 'review', (36, 39, 42)), ('G', 'events', (36, 38, 40, 42)),
                           ('K', 'zacks', (36, 38, 40, 42)), ('O', 'merrill', (36, 38, 40, 42)),
                           ('S', 'miar', (36, 39, 42)), ('V', 'thesis', (36, 39, 42))):
        for r, text in zip(rows, research[key]):
            put(sh, f'{col}{r}', text)
    for r, text in zip((48, 50, 52, 54), con['calendar']):
        put(sh, f'M{r}', text)
    for r, text in zip((48, 50, 52, 54), con['certifications']):
        put(sh, f'R{r}', text)
    for r, text in zip((48, 51, 54), con['notebook']):
        put(sh, f'V{r}', text)
    for r, (_, value) in zip(range(49, 56), con['pending']):
        put(sh, f'G{r}', value)
    for col, text in zip('CHMRW', con['tiles']):
        put(sh, f'{col}65', text)
