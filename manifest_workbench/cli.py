"""Command-line interface and interactive console for the Manifest Workbench."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import json
import os
import shlex
import sys
from pathlib import Path

from . import __version__
from . import engine
from . import lists as L
from . import ops
from . import render as R
from . import schema as S
from . import store as ST
from .engine import blank, same

CONTROL_PRINCIPLE = (
    'MOPS-003 CONTROL PRINCIPLE — Research identifies and evaluates change. Portfolio Engineering '
    'designs the response. Committee governance authorizes the response. The certified MFPDF '
    'remains the sole portfolio system of record. RCC-004 controls registry identity, eligibility, '
    'stage gates and referral; it does not alter allocations, authorize trading or independently '
    'admit a security to the certified portfolio.')

# Fields echoed after an edit so the operator sees the recomputed control state.
STATUS_FIELDS = {
    'portfolio': ('band_status', 'rebalancing_action'),
    'conviction': ('effective_conviction', 'conviction_score', 'decision_state'),
    'pew004': ('base_score', 'final_score', 'eligibility_gate', 'recommended_action', 'status'),
    'evidence': ('completeness', 'control_status', 'referral_eligibility'),
    'miar': ('research_freshness', 'dossier_completeness', 'control_status', 'required_action',
             'rcc007_referral'),
    'review': ('control_status',),
    'masr': ('eligibility_gate', 'exception_requirement', 'control_status', 'required_action'),
    'pipeline': ('gate_result', 'control_status', 'next_action'),
}

# Default list-view columns per table.
LIST_COLUMNS = {
    'portfolio': ('sleeve', 'symbol', 'security_type', 'target_weight', 'lower_band', 'upper_band',
                  'actual_weight', 'variance', 'band_status', 'rebalancing_action',
                  'conviction_tier', 'research_status'),
    'conviction': ('symbol', 'sleeve', 'current_conviction', 'proposed_conviction',
                   'effective_conviction', 'conviction_score', 'thesis_status', 'research_status',
                   'decision_state'),
    'pew004': ('candidate_id', 'symbol', 'candidate_type', 'comparison_group', 'base_score',
               'close_decision', 'zacks_overlay', 'final_score', 'eligibility_gate',
               'recommended_action', 'status'),
    'evidence': ('evidence_id', 'date_received', 'ticker', 'activity_type', 'materiality',
                 'status', 'verified', 'due_date', 'days_open', 'control_status',
                 'referral_eligibility'),
    'miar': ('ticker', 'miar_id', 'record_status', 'research_owner', 'review_cadence',
             'next_review', 'research_freshness', 'dossier_completeness', 'control_status',
             'rcc007_referral'),
    'review': ('review_id', 'review_date', 'ticker', 'review_type', 'reviewer', 'proposed_status',
               'certification_rec', 'control_status'),
    'masr': ('masr_id', 'ticker', 'security', 'record_class', 'registry_status', 'eligibility_gate',
             'exception_requirement', 'current_stage', 'control_status'),
    'pipeline': ('candidate_id', 'ticker', 'candidate_type', 'stage', 'gate_result', 'due_date',
                 'days_open', 'control_status', 'next_action'),
}
STATUS_COLUMNS = {'band_status', 'decision_state', 'eligibility_gate', 'recommended_action',
                  'status', 'control_status', 'referral_eligibility', 'research_freshness',
                  'dossier_completeness', 'rcc007_referral', 'gate_result', 'exception_requirement'}
# Tables whose "status" column is an operator input rather than a computed state.
INPUT_STATUS_TABLES = {'evidence'}


class App:
    def __init__(self, args):
        self.path = Path(args.data) if args.data else ST.default_path()
        self.style = R.Style.detect(force_off=args.no_color)
        self.today = args.as_of or _env_date() or dt.date.today()
        self.actor = args.by or os.environ.get('MANIFEST_USER') or _user()
        self._store = None

    # ------------------------------------------------------------------ io

    @property
    def store(self):
        if self._store is None:
            self._store = ST.load(self.path)
        return self._store

    def save(self):
        ST.save(self.path, self.store)

    def wb(self) -> engine.Workbench:
        return engine.Workbench(self.store, self.today)

    def out(self, text=''):
        print(text)

    # ------------------------------------------------------------------ shared views

    def header(self, heading, subtitle=''):
        stamp = f'As of {self.today.isoformat()}  ·  Founders Edition v1.0  ·  {self.path}'
        self.out(R.title(self.style, heading, subtitle))
        self.out(self.style.paint('  ' + stamp, R.DIM))

    def rows_for(self, table_name, rows, columns):
        table = S.TABLES[table_name]
        fields = [table.field(c) for c in columns]
        headers = [f.header for f in fields]
        body = [[R.fmt(r.get(f.key), f.vtype) for f in fields] for r in rows]
        status = [f.header for f in fields if f.key in STATUS_COLUMNS
                  and not (f.key == 'status' and table_name in INPUT_STATUS_TABLES)]
        return R.table(self.style, headers, body, status_cols=status)

    def controls_table(self, controls):
        headers = ['#', 'Control / Trigger', 'Count', 'State', 'Required Action', 'Authority',
                   'Destination']
        body = [[str(c['priority']), c['control'], str(c['count']), c['state'], c['action'],
                 c['authority'], c['destination']] for c in controls]
        return R.table(self.style, headers, body, status_cols=['State'], max_col=44)

    def echo_status(self, table_name, key):
        wb = self.wb()
        table = S.TABLES[table_name]
        row = _find_computed(wb, table_name, key)
        if row is None:
            return
        for fkey in STATUS_FIELDS[table_name]:
            f = table.field(fkey)
            value = R.fmt(row.get(fkey), f.vtype)
            shown = self.style.status(value) if f.vtype == S.TEXT else value
            self.out(f'    {f.header:<28} {shown}')
        missing = engine.missing_fields(table_name, row)
        if missing:
            names = ', '.join(f'{k} ({table.field(k).col})' for k in missing)
            self.out(self.style.paint(f'    Missing required: {names}', R.AMBER))


def _user():
    try:
        return getpass.getuser()
    except Exception:  # pragma: no cover
        return 'operator'


def _env_date():
    raw = os.environ.get('MANIFEST_AS_OF')
    return dt.date.fromisoformat(raw) if raw else None


def _find_computed(wb, table_name, key):
    rows = wb.table(table_name)
    field = S.KEYS[table_name]
    for r in rows:
        if same(r.get(field), key) or (table_name == 'masr' and same(r.get('masr_id'), key)):
            return r
    return None


def _date(text):
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a date (YYYY-MM-DD)") from None


# =========================================================================== commands

def cmd_init(app: App, args):
    if app.path.exists() and not args.force:
        raise ops.OpError(f'{app.path} already exists; use --force to replace it')
    if args.from_xlsx:
        from .xlsx_import import import_workbook
        store, problems = import_workbook(args.from_xlsx)
        for p in problems:
            app.out(app.style.paint(f'  warning: {p}', R.AMBER))
        source = args.from_xlsx
    else:
        store, source = ST.seed_store(), 'bundled Manifest Workbench v0.4 inputs'
    ops.audit(store, app.actor, 'init', 'workbench', str(source))
    app._store = store
    app.save()
    counts = ', '.join(f'{k}: {len(store[k])}' for k in ST.TABLE_KEYS)
    app.out(f'Initialised {app.path} from {source}\n  {counts}')


def cmd_dashboard(app: App, args):
    wb = app.wb()
    one, four, three, two = wb.rcc001(), wb.rcc004(), wb.rcc003(), wb.rcc002()
    totals = wb.portfolio_totals()
    app.header('CHIEF INVESTMENT STEWARD CONSOLE — MOPS-003 RESEARCH COMMAND',
               'CISC-001 visual foundation · MFPDF v1.0 remains the sole portfolio-allocation '
               'authority · Automatic trading is not authorized.')
    app.out(R.section(app.style, 'Executive research state'))
    s = one['state']
    app.out(R.tiles(app.style, [
        ('RESEARCH READINESS', s['readiness']),
        ('CERTIFIED HOLDINGS', s['certified_holdings']),
        ('TARGET TOTAL', totals['certification']),
        ('ACTUAL WEIGHTS', f"{totals['actual_loaded']} / {totals['positions']} loaded"),
        ('CONVICTION ASSIGNED', f"{s['conviction_assigned']} / {s['certified_holdings']}"),
        ('CONTROL EXCEPTIONS', s['control_exceptions']),
    ]))
    app.out(R.section(app.style, 'Module state'))
    body = [
        ['RCC-002 Evidence Ledger', two['state']['readiness'],
         f"{two['state']['total_records']} records · {two['state']['open']} open · "
         f"{two['state']['overdue']} overdue"],
        ['RCC-003 MIAR Dossier Control', three['state']['readiness'],
         f"{three['state']['coverage']} · {three['state']['control_exceptions']} exceptions"],
        ['RCC-004 MASR Registry', four['state']['readiness'],
         f"{four['state']['capacity']} · {four['state']['control_exceptions']} exceptions"],
        ['RCC-004 Candidate Pipeline', four['state']['stage_gates'],
         f"{four['state']['active_candidates']} active · {four['state']['routing']}"],
    ]
    app.out(R.table(app.style, ['Module', 'State', 'Detail'], body, status_cols=['State'], max_col=60))
    app.out(R.section(app.style, 'Decisions required this week'))
    decisions = _decision_queue(wb)
    if decisions:
        app.out(R.table(app.style, ['Where', 'Record', 'State', 'Required Action'], decisions[:15],
                        status_cols=['State'], max_col=52))
        if len(decisions) > 15:
            app.out(app.style.paint(f'  … {len(decisions) - 15} more; see rcc002 / rcc003 / rcc004',
                                    R.DIM))
    else:
        app.out(app.style.paint('  NO COMMITTEE ACTION REQUIRED', R.GREEN, R.BOLD))
    app.out()
    app.out(R.paragraph(CONTROL_PRINCIPLE))


def _decision_queue(wb):
    out = []
    for r in wb.pipeline_exceptions():
        out.append(['Candidate Pipeline', f"{r['candidate_id']} {r['ticker']}", r['control_status'],
                    r['next_action']])
    for r in wb.evidence_exceptions():
        out.append(['Evidence Ledger', r['evidence_id'], r['control_status'], ''])
    grouped = {}
    for r in wb.masr_exceptions():
        grouped.setdefault((r['control_status'], r['required_action']), []).append(r['ticker'])
    for (state, action), tickers in grouped.items():
        label = ', '.join(tickers[:4]) + (f' +{len(tickers) - 4} more' if len(tickers) > 4 else '')
        out.append(['MASR Registry', label, state, action])
    grouped = {}
    for r in wb.miar_exceptions():
        grouped.setdefault((r['control_status'], r['required_action']), []).append(r['ticker'])
    for (state, action), tickers in grouped.items():
        label = ', '.join(tickers[:4]) + (f' +{len(tickers) - 4} more' if len(tickers) > 4 else '')
        out.append(['MIAR Registry', label, state, action])
    return out


def cmd_rcc001(app: App, args):
    d = app.wb().rcc001()
    s = d['state']
    app.header('MOPS-003 — RESEARCH COMMAND CENTER (RCC)',
               'RCC-001 Executive Research Control Center · RCC-001 through RCC-004 installed; '
               'RCC-005 — Zacks / Merrill Research Crosswalk is the next module.')
    app.out(R.section(app.style, 'Executive research state'))
    app.out(R.tiles(app.style, [
        ('RESEARCH READINESS', s['readiness']), ('CERTIFIED HOLDINGS', s['certified_holdings']),
        ('RCC ACTIVITY RECORDS', s['activity_records']),
        ('CONVICTION ASSIGNED', s['conviction_assigned']),
        ('THESIS STATUS ASSIGNED', s['thesis_assigned']),
        ('MFPDF RESEARCH STATUS', s['mfpdf_research_status']),
        ('CONTROL EXCEPTIONS', s['control_exceptions']),
    ]))
    app.out(R.section(app.style, 'Research control exceptions'))
    app.out(app.controls_table(d['controls']))
    app.out(R.section(app.style, 'Research intelligence snapshot'))
    app.out(R.table(app.style, ['Activity Type', 'Count'], [[a, str(n)] for a, n in d['snapshot']]))
    app.out(R.section(app.style, 'MOPS-003 module roadmap'))
    app.out(R.table(app.style, ['Module', 'Workspace', 'Status', 'Authority'],
                    [list(r) for r in d['roadmap']], status_cols=['Status']))
    app.out('\n' + R.paragraph('RESEARCH SIGNAL → EVIDENCE REVIEW → MIAR UPDATE → THESIS ASSESSMENT '
                               '→ CONVICTION DECISION → PORTFOLIO-ENGINEERING REFERRAL'))


def cmd_rcc002(app: App, args):
    d = app.wb().rcc002()
    s = d['state']
    app.header('MOPS-003 — RCC-002 RESEARCH INTAKE & EVIDENCE LEDGER', 'RCC-002 Control Center')
    app.out(R.tiles(app.style, [
        ('TOTAL EVIDENCE RECORDS', s['total_records']), ('OPEN / UNDER REVIEW', s['open']),
        ('CRITICAL / HIGH', s['critical_high']), ('OVERDUE', s['overdue']),
        ('UNVERIFIED', s['unverified']), ('REFERRALS READY', s['referrals_ready']),
        ('RCC-002 READINESS', s['readiness']), ('MIAR ACTIONS', s['miar_actions']),
        ('THESIS / CONVICTION', s['thesis_conviction_actions']),
        ('PEW REFERRALS', s['pew_referrals']),
    ]))
    app.out(R.section(app.style, 'Evidence activity summary'))
    app.out(R.table(app.style, ['Activity Type', 'Total', 'Open', 'Critical / High', 'Unverified',
                                'Overdue', 'Referral Ready'],
                    [[a['activity'], str(a['total']), str(a['open']), str(a['critical_high']),
                      str(a['unverified']), str(a['overdue']), str(a['referral_ready'])]
                     for a in d['activity']]))
    app.out(R.section(app.style, 'Routing summary'))
    app.out(R.table(app.style, ['Control', 'Count', 'Operating Meaning'],
                    [[c, str(n), m] for c, n, m in d['routing']]))
    app.out(R.section(app.style, 'Materiality / direction profile'))
    rows = [[m, str(n), d_, str(k)] for (m, n), (d_, k) in
            zip(d['materiality'] + [('', '')] * 5, d['direction'])]
    app.out(R.table(app.style, ['Materiality', 'Records', 'Direction', 'Records'], rows))


def cmd_rcc003(app: App, args):
    d = app.wb().rcc003()
    s = d['state']
    app.header('MOPS-003 — RCC-003 MIAR DOSSIER CONTROL', 'RCC-003 Control Center')
    app.out(R.tiles(app.style, [
        ('TOTAL MIAR RECORDS', s['total_records']), ('DOSSIERS COMPLETE', s['dossiers_complete']),
        ('CURRENT', s['current']), ('DUE / OVERDUE', s['due_overdue']),
        ('MATERIAL EVENTS', s['material_events']), ('CONTROL EXCEPTIONS', s['control_exceptions']),
        ('RCC-003 READINESS', s['readiness']), ('DOSSIER COVERAGE', s['coverage']),
        ('EVIDENCE / MIAR ACTIONS', s['miar_actions']), ('RCC-007 REFERRALS', s['rcc007_referrals']),
    ]))
    app.out(R.section(app.style, 'MIAR control exceptions'))
    app.out(app.controls_table(d['controls']))
    app.out(R.section(app.style, 'Sleeve MIAR coverage'))
    app.out(R.table(app.style, ['Sleeve', 'Records', 'Complete', 'Current', 'Update Due',
                                'Review Due', 'Overdue', 'Material', 'Setup', 'Coverage',
                                'Primary Control State'],
                    [[x['sleeve'], str(x['records']), str(x['complete']), str(x['current']),
                      str(x['update_due']), str(x['review_due']), str(x['overdue']),
                      str(x['material_event']), str(x['setup_required']),
                      f"{x['coverage'] * 100:.0f}%", x['primary']] for x in d['sleeves']],
                    status_cols=['Primary Control State']))
    lg = d['log']
    app.out(R.section(app.style, 'MIAR review log'))
    app.out(f"  {lg['entries']} entries · {lg['complete']} complete · {lg['exceptions']} exceptions · "
            f"{lg['certification_pending']} certification pending · "
            f"{lg['rcc007_escalations']} RCC-007 escalations")


def cmd_rcc004(app: App, args):
    d = app.wb().rcc004()
    s = d['state']
    app.header('MOPS-003 — RCC-004 MASR REGISTRY & CANDIDATE PIPELINE',
               'RCC-004 governs canonical MASR identity, approved and conditional non-holdings, '
               'candidate stage gates, external-research exceptions, committee disposition and '
               'controlled referral to PEW-004.')
    app.out(R.section(app.style, 'Executive MASR & candidate state'))
    app.out(R.tiles(app.style, [
        ('MASR RECORDS LOADED', s['records_loaded']), ('CERTIFIED HOLDINGS', s['certified_holdings']),
        ('APPROVED NON-HOLDINGS', s['approved_non_holdings']),
        ('ACTIVE CANDIDATES', s['active_candidates']), ('PEW-004 REFERRALS', s['pew_referrals']),
        ('CONTROL EXCEPTIONS', s['control_exceptions']),
    ]))
    app.out(R.section(app.style, 'Readiness, capacity & routing state'))
    app.out(R.tiles(app.style, [
        ('RCC-004 READINESS', s['readiness']), ('MASR CONTROLLED CAPACITY', s['capacity']),
        ('CANDIDATE STAGE GATES', s['stage_gates']), ('COMMITTEE / PEW ROUTING', s['routing']),
    ], per_row=2))
    app.out(R.section(app.style, 'MASR & candidate control exceptions'))
    app.out(app.controls_table(d['controls']))
    app.out(R.section(app.style, 'Registry composition'))
    app.out(R.table(app.style, ['Registry Class', 'Records', 'Control Clear', 'Exceptions'],
                    [[c, str(n), str(k), str(e)] for c, n, k, e in d['composition']]))
    app.out(R.section(app.style, 'Pipeline snapshot'))
    app.out(R.table(app.style, ['Candidate Stage', 'Records', 'Gate Pass', 'Control Exceptions'],
                    [[c, str(n), str(k), str(e)] for c, n, k, e in d['stages']]))
    app.out()
    app.out(R.paragraph(CONTROL_PRINCIPLE))


# --------------------------------------------------------------------------- table commands

def _filter(rows, args):
    out = rows
    for attr, key in (('stage', 'stage'), ('klass', 'record_class'), ('status', 'registry_status'),
                      ('sleeve', 'sleeve'), ('ticker', 'ticker')):
        want = getattr(args, attr, None)
        if want:
            out = [r for r in out
                   if engine.fold(want) in engine.fold(str(r.get(key) or r.get('symbol') or ''))]
    return out


def cmd_list(app: App, args):
    wb = app.wb()
    name = args.table
    rows = wb.table(name)
    if name == 'masr':
        rows = [r for r in rows if not blank(r.get('ticker'))]
    if name == 'pew004' and not args.all:
        rows = [r for r in rows if not blank(r.get('symbol'))]
    rows = _filter(rows, args)
    if getattr(args, 'exceptions', False):
        rows = [r for r in rows if _is_exception(name, r)]
    columns = LIST_COLUMNS[name]
    if args.columns:
        columns = [S.TABLES[name].field(c).key for c in args.columns.split(',')]
    table = S.TABLES[name]
    app.header(f'{table.sheet.upper()}', f'{len(rows)} record(s) shown · capacity {table.capacity}')
    app.out(app.rows_for(name, rows, columns))
    if name == 'portfolio':
        t = wb.portfolio_totals()
        app.out(f"\n  PORTFOLIO TOTAL  target {t['target_total'] * 100:.2f}% "
                f"({app.style.status(t['certification'])})  ·  actual {t['actual_total'] * 100:.2f}%"
                f"  ·  actual weights {t['actual_loaded']} / {t['positions']} loaded "
                f"({app.style.status(t['actual_state'])})")
    if name == 'pew004' and not args.all:
        app.out(app.style.paint(f'  {20 - len(rows)} open slot(s) hidden; use --all to show them',
                                R.DIM))


def _is_exception(name, r):
    state = r.get('control_status') or r.get('decision_state') or r.get('band_status') or ''
    return state not in ('CONTROL CLEAR', 'INACTIVE / CLOSED', 'OPEN — ON TRACK', 'CLOSED',
                         'COMPLETE', 'NO CHANGE', 'Within band', '')


def cmd_show(app: App, args):
    wb = app.wb()
    row = _find_computed(wb, args.table, args.key)
    if row is None:
        raise ops.OpError(f"No {args.table} record '{args.key}'")
    table = S.TABLES[args.table]
    key = row.get(S.KEYS[args.table])
    app.header(f'{table.sheet.upper()} — {key}')
    locked = ()
    if args.table == 'masr' and row.get('_linked') is not None:
        locked = S.MASR_CERTIFIED_LINKED + S.MASR_CERTIFIED_LOCKED
        app.out(app.style.paint('  Certified Portfolio Holding: identity, class and status are '
                                'linked to the certified MFPDF.', R.DIM))
    app.out(R.record(app.style, table, row, locked_keys=locked))
    if args.table == 'pipeline':
        app.out(R.section(app.style, 'Stage history'))
        _print_history(app, row['candidate_id'])


def cmd_set(app: App, args):
    ops.set_fields(app.store, args.table, args.key, args.assignments, app.actor, app.today)
    app.save()
    app.out(f'Updated {args.table} {args.key}:')
    app.echo_status(args.table, args.key)


def cmd_add(app: App, args):
    rec = ops.add_record(app.store, args.table, args.assignments, app.actor, app.today)
    app.save()
    key = rec.get(S.KEYS[args.table])
    app.out(f'Added {args.table} record {key}:')
    if args.table == 'pipeline':
        wb = app.wb()
        if _find_computed(wb, 'masr', rec['ticker']) is None:
            app.out(app.style.paint(
                f"  note: no RCC-004 MASR registry record for {rec['ticker']}. Create or reconcile "
                f"it ('masr add ticker={rec['ticker']} ...') before the MIAR Review stage.", R.AMBER))
    app.echo_status(args.table, key)


def cmd_advance(app: App, args):
    before, after = ops.advance(app.store, args.key, app.actor, app.today, target=args.to)
    app.save()
    app.out(f'{args.key}: {before} → {after}')
    app.echo_status('pipeline', args.key)


def cmd_history(app: App, args):
    ops.find(app.store, 'pipeline', args.key)
    app.header(f'CANDIDATE STAGE HISTORY — {args.key.upper()}')
    _print_history(app, args.key)


def _print_history(app, candidate_id):
    events = [e for e in app.store['audit'] if e.get('table') == 'pipeline'
              and same(e.get('record'), candidate_id)]
    rows = []
    for e in events:
        if e['action'] == 'add':
            rows.append([e['ts'], e['actor'], 'Created (Intake)', ''])
        else:
            rows.append([e['ts'], e['actor'], e['field'] or '', f"{R.fmt(e['old'])} → {R.fmt(e['new'])}"])
    if not rows:
        app.out(app.style.paint('  No recorded changes since the record was loaded.', R.DIM))
    else:
        app.out(R.table(app.style, ['When', 'By', 'Change', 'Old → New'], rows, max_col=60))


def cmd_sleeves(app: App, args):
    wb = app.wb()
    app.header('MFPDF v1.0 — SLEEVE ALLOCATION SUMMARY')
    rows = wb.sleeve_summary()
    body = [[r['sleeve'], str(r['positions']), str(r['equities']), str(r['etfs']),
             f"{r['target'] * 100:.2f}%"] for r in rows]
    total = sum(r['target'] for r in rows)
    body.append(['TOTAL', str(sum(r['positions'] for r in rows)), '', '', f'{total * 100:.2f}%'])
    app.out(R.table(app.style, ['Production Sleeve', 'Positions', 'Equities', 'ETFs',
                                'Target Allocation'], body))


def cmd_lists(app: App, args):
    if not args.name:
        app.header('CONTROLLED VALIDATION LISTS', 'Do not modify without a documented MOPS-003 amendment.')
        app.out(R.table(app.style, ['List', 'Values'],
                        [[k, str(len(v))] for k, v in L.REGISTRY.items()]))
        return
    values = L.REGISTRY.get(args.name)
    if values is None:
        raise ops.OpError(f"Unknown list '{args.name}'. Try: {', '.join(L.REGISTRY)}")
    app.header(f'CONTROLLED LIST — {args.name}')
    for v in values:
        app.out(f'  {v}')


def cmd_fields(app: App, args):
    table = S.TABLES[args.table]
    app.header(f'{table.sheet.upper()} — FIELDS',
               "Refer to a field by key or worksheet column, e.g. 'market_cap=180' or 'T=180'. "
               'Only input fields can be edited.')
    body = [[f.col, f.key, f.header, f.kind, f.vtype,
             ', '.join(map(str, f.choices)) if f.choices else ''] for f in table.fields]
    app.out(R.table(app.style, ['Col', 'Key', 'Header', 'Kind', 'Type', 'Controlled Values'], body,
                    max_col=60))


def cmd_export(app: App, args):
    wb = app.wb()
    table = S.TABLES[args.table]
    rows = wb.table(args.table)
    if args.table == 'masr':
        rows = [r for r in rows if not blank(r.get('ticker'))]
    out = Path(args.path)
    fmt = args.format or ('json' if out.suffix.lower() == '.json' else 'csv')
    if fmt == 'json':
        data = [{f.key: _jsonable(r.get(f.key)) for f in table.fields} for r in rows]
        out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    else:
        with open(out, 'w', newline='', encoding='utf-8-sig') as fh:
            w = csv.writer(fh)
            w.writerow([f'{f.header} ({f.col})' for f in table.fields])
            for r in rows:
                w.writerow([R.fmt(r.get(f.key), f.vtype) for f in table.fields])
    app.out(f'Exported {len(rows)} {args.table} record(s) to {out} ({fmt}, as of {app.today})')


def _jsonable(v):
    return v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v


def cmd_audit(app: App, args):
    events = app.store['audit']
    if args.table:
        events = [e for e in events if e.get('table') == args.table]
    if args.record:
        events = [e for e in events if same(e.get('record'), args.record)]
    events = events[-args.limit:] if args.limit else events
    app.header('AUDIT TRAIL', f'{len(events)} event(s)')
    app.out(R.table(app.style, ['When', 'By', 'Action', 'Table', 'Record', 'Field', 'Old', 'New'],
                    [[e['ts'], e['actor'], e['action'], e['table'], str(e['record']),
                      e.get('field') or '', R.fmt(e.get('old')), R.fmt(e.get('new'))]
                     for e in events]))


def cmd_guide(app: App, args):
    app.header('RCC-004 OPERATING STANDARD')
    steps = [
        ('1 — Register', 'Assign canonical MASR identity and record class', 'Research Operations'),
        ('2 — Classify', 'Record admission basis, sleeve, role and security type', 'Research Committee'),
        ('3 — Evidence', 'Complete MIAR, Integrity, MICS, empirical and evidence controls',
         'Assigned Reviewer'),
        ('4 — Test', 'Apply eligibility, market-cap and external-research exception gates',
         'Research Committee'),
        ('5 — Advance', 'Move the candidate through controlled stage gates', 'Research Operations'),
        ('6 — Decide', 'Record committee disposition and decision date', 'Stewardship Committee'),
        ('7 — Refer', 'Link qualified candidates to PEW-004 Candidate Comparison',
         'Portfolio Engineering'),
    ]
    app.out(R.table(app.style, ['Step', 'Required Action', 'Authority'], [list(s) for s in steps],
                    max_col=70))
    app.out(R.section(app.style, 'Hard controls'))
    for line in (
            'One unique canonical MASR ID per active security',
            'Certified MFPDF holdings remain certified unless governance changes them',
            'No candidate reaches PEW-004 without an RCC-004 registry record',
            'MIAR, Integrity, MICS and empirical evidence precede admission',
            'Zacks #1 / #2 bias applies only to genuinely close decisions',
            'Sub-$50B Zacks elections and Zacks #4 / #5 require exceptions',
            'Merrill No Rating or restricted research requires documentation',
            'RCC-004 may not change allocations or authorize trading'):
        app.out(f'  • {line}')
    app.out(R.section(app.style, 'Weekly workflow'))
    for line in (
            '1  portfolio set SYMBOL actual_weight=…   load actual weights (Certified Allocation I)',
            '2  conviction set SYMBOL proposed_conviction=… thesis_status=…',
            '3  miar set SYMBOL miar_id=… record_status=… research_owner=… review_cadence=…',
            '4  evidence add …                        one record per verified research signal',
            '5  masr set / masr add                   canonical MASR identity and eligibility inputs',
            '6  pipeline add / pipeline advance       candidate stage gates',
            '7  rcc004 / dashboard                    review exceptions; "no action" is a valid outcome'):
        app.out(f'  {line}')
    app.out()
    app.out(R.paragraph(CONTROL_PRINCIPLE))


# =========================================================================== parser

TABLE_ALIASES = {
    'portfolio': 'Certified Allocation (MFPDF)',
    'conviction': 'PEW-005 conviction & thesis control',
    'pew004': 'PEW-004 candidate comparison',
    'evidence': 'RCC-002 evidence ledger',
    'miar': 'RCC-003 MIAR dossier registry',
    'review': 'RCC-003 MIAR review log',
    'masr': 'RCC-004 MASR registry',
    'pipeline': 'RCC-004 candidate pipeline',
}
ADDABLE = {'evidence', 'review', 'masr', 'pipeline'}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='manifest-workbench',
        description='Manifest Workbench console — CISC-001 / MOPS-003 RCC-004 MASR Registry & '
                    'Candidate Pipeline (Founders Edition v1.0, workbook v0.4). Run without a '
                    'command for the interactive console.')
    p.add_argument('--data', help=f'data file (default: $MANIFEST_DATA or ./{ST.DEFAULT_DATA_FILE})')
    p.add_argument('--as-of', type=_date, help="evaluate TODAY() as this date (YYYY-MM-DD)")
    p.add_argument('--by', help='operator name recorded in the audit trail')
    p.add_argument('--no-color', action='store_true', help='disable ANSI colour')
    p.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    sub = p.add_subparsers(dest='command', metavar='COMMAND')

    c = sub.add_parser('init', help='create the data file from the bundled v0.4 inputs or a workbook')
    c.add_argument('--force', action='store_true', help='replace an existing data file')
    c.add_argument('--from-xlsx', metavar='PATH', help='import inputs from a Manifest Workbench .xlsx')
    c.set_defaults(func=cmd_init)

    for name, func, text in (
            ('dashboard', cmd_dashboard, 'executive console: readiness, module state, decision queue'),
            ('rcc001', cmd_rcc001, 'RCC-001 executive research control center'),
            ('rcc002', cmd_rcc002, 'RCC-002 evidence ledger control center'),
            ('rcc003', cmd_rcc003, 'RCC-003 MIAR dossier control center'),
            ('rcc004', cmd_rcc004, 'RCC-004 MASR registry & candidate pipeline control center'),
            ('guide', cmd_guide, 'RCC-004 operating standard, hard controls and weekly workflow')):
        sub.add_parser(name, help=text).set_defaults(func=func)

    for name, text in TABLE_ALIASES.items():
        t = sub.add_parser(name, help=text)
        ts = t.add_subparsers(dest='action', metavar='ACTION')
        lp = ts.add_parser('list', help='list records')
        lp.add_argument('--columns', help='comma-separated field keys or column letters')
        lp.add_argument('--exceptions', action='store_true', help='only records with open exceptions')
        lp.add_argument('--sleeve')
        lp.add_argument('--ticker')
        lp.add_argument('--all', action='store_true', help='include open slots (pew004)')
        if name == 'pipeline':
            lp.add_argument('--stage')
        if name == 'masr':
            lp.add_argument('--class', dest='klass', help='record class filter')
            lp.add_argument('--status', help='registry status filter')
        lp.set_defaults(func=cmd_list, table=name)
        sp = ts.add_parser('show', help='show one record with every field')
        sp.add_argument('key')
        sp.set_defaults(func=cmd_show, table=name)
        ep = ts.add_parser('set', help='edit input fields: set KEY field=value ...')
        ep.add_argument('key')
        ep.add_argument('assignments', nargs='+', metavar='field=value')
        ep.set_defaults(func=cmd_set, table=name)
        if name in ADDABLE:
            ap = ts.add_parser('add', help='add a record: add field=value ...')
            ap.add_argument('assignments', nargs='*', metavar='field=value')
            ap.set_defaults(func=cmd_add, table=name)
        fp = ts.add_parser('fields', help='list fields, columns and controlled values')
        fp.set_defaults(func=cmd_fields, table=name)
        xp = ts.add_parser('export', help='export computed records to CSV or JSON')
        xp.add_argument('path')
        xp.add_argument('--format', choices=('csv', 'json'))
        xp.set_defaults(func=cmd_export, table=name)
        if name == 'pipeline':
            av = ts.add_parser('advance', help='advance a candidate once its current stage gate passes')
            av.add_argument('key')
            av.add_argument('--to', help='target stage (default: next stage)')
            av.set_defaults(func=cmd_advance)
            hp = ts.add_parser('history', help='stage and field history of a candidate')
            hp.add_argument('key')
            hp.set_defaults(func=cmd_history)
        if name == 'portfolio':
            ts.add_parser('sleeves', help='sleeve allocation summary').set_defaults(func=cmd_sleeves)
        t.set_defaults(func=cmd_list, table=name, action='list', columns=None, exceptions=False,
                       sleeve=None, ticker=None, all=False, stage=None, klass=None, status=None)

    lp = sub.add_parser('lists', help='controlled validation lists')
    lp.add_argument('name', nargs='?')
    lp.set_defaults(func=cmd_lists)

    ap = sub.add_parser('audit', help='audit trail of every edit')
    ap.add_argument('--table')
    ap.add_argument('--record')
    ap.add_argument('--limit', type=int, default=50)
    ap.set_defaults(func=cmd_audit)
    return p


SHELL_HELP = """\
Commands (same as the command line; type 'help COMMAND' or 'COMMAND -h' for options):
  dashboard                      executive console and decision queue
  rcc001 | rcc002 | rcc003 | rcc004   research control centers
  portfolio [list|show|set|sleeves]  certified MFPDF allocation and bands
  conviction [list|show|set]     PEW-005 conviction & thesis
  pew004 [list|show|set]         PEW-004 candidate comparison
  evidence [list|show|add|set]   RCC-002 evidence ledger
  miar [list|show|set]           RCC-003 MIAR registry
  review [list|show|add|set]     RCC-003 MIAR review log
  masr [list|show|add|set]       RCC-004 MASR registry
  pipeline [list|show|add|set|advance|history]  RCC-004 candidate pipeline
  <table> fields | <table> export PATH
  lists [NAME] · audit · guide · as-of YYYY-MM-DD · quit
"""


def shell(app: App, parser: argparse.ArgumentParser):
    try:
        import readline  # noqa: F401  (line editing / history when available)
    except ImportError:  # pragma: no cover
        pass
    try:
        cmd_dashboard(app, None)
    except ST.StoreError as exc:
        print(exc)
        return 1
    print("\nType 'help' for commands, 'quit' to exit.")
    while True:
        try:
            line = input('\nmanifest> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ('quit', 'exit', 'q'):
            return 0
        if line in ('help', '?'):
            print(SHELL_HELP)
            continue
        try:
            words = shlex.split(line)
        except ValueError as exc:
            print(f'error: {exc}')
            continue
        if words[0] == 'help':
            words = words[1:] + ['-h']
        if words[0] in ('as-of', 'asof') and len(words) == 2:
            try:
                app.today = dt.date.fromisoformat(words[1])
                print(f'Evaluating as of {app.today}')
            except ValueError:
                print('error: use as-of YYYY-MM-DD')
            continue
        try:
            args = parser.parse_args(words)
        except SystemExit:
            continue
        if getattr(args, 'command', None) is None:
            continue
        if args.as_of:
            app.today = args.as_of
        if args.by:
            app.actor = args.by
        run(app, args)


def run(app: App, args) -> int:
    try:
        args.func(app, args)
        return 0
    except (ops.OpError, ST.StoreError, KeyError, ValueError, RuntimeError, OSError) as exc:
        msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        print(app.style.paint(f'error: {msg}', R.RED), file=sys.stderr)
        return 1


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = App(args)
    if args.command is None:
        if not app.path.exists():
            store = ST.seed_store()
            ops.audit(store, app.actor, 'init', 'workbench', 'bundled Manifest Workbench v0.4 inputs')
            app._store = store
            app.save()
            print(f'Created {app.path} from the bundled Manifest Workbench v0.4 inputs.')
        return shell(app, parser)
    return run(app, args)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
