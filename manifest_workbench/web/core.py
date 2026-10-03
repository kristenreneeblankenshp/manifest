"""Console, decision hub, actions, candidate pipeline, control centers and engineering pages."""

from __future__ import annotations

import datetime as dt

from flask import Blueprint, abort, flash, render_template, request, session, url_for

from .. import mwir as MW
from .. import ops
from .. import reports as RP
from .. import reviews as RV
from ..connectors import last_run
from ..connectors.research import open_items
from ..engine import CLOSED_STAGES, blank
from ..views import SHEETS
from .auth import actor, repo
from .common import back, mutate, set_fields, wb
from .filters import today

bp = Blueprint('core', __name__)

PIPELINE_COLUMNS = ('Intake', 'Evidence Gathering', 'MIAR Review', 'Eligibility Review', 'Candidate Comparison',
                    'Committee Review', 'Approved for MASR', 'Referred to PEW-004', 'On Watch')

# Worksheet -> web page.
SHEET_PAGES = {
    '00 CISC Dashboard': '/', '01 Dashboard Controls': '/controls', '02 Decision Center': '/decisions',
    '03 Research Intelligence': '/intel', '04 Committee Operations': '/actions',
    '05 Workbench Guide': '/doc/workbench-guide', 'Executive Summary': '/doc/executive-summary',
    'Certified Allocation': '/t/portfolio', 'Sleeve Summary': '/t/sleeves', 'Rebalancing': '/doc/rebalancing',
    'Sources & Certification': '/doc/sources', '99 Dashboard Data': '/',
    '06 PEW Control Center': '/pew', '07 Mandate & Constraints': '/t/mandate',
    '08 Sleeve Architecture': '/t/sleeves', '09 Role Assignment': '/t/roles',
    '10 Candidate Comparison': '/t/pew004', '11 Conviction': '/t/conviction', '12 Allocation Lab': '/lab',
    '13 Validation & Cert': '/validation', '14 PEW Guide': '/doc/pew-guide', '98 PEW Lists': '/lists',
    '15 MOPS-002 Freeze Record': '/doc/freeze-record', '16 RCC-001 Control Center': '/rcc/1',
    '97 RCC Lists': '/lists', '18 RCC-002 Evidence Ledger': '/t/evidence', '17 RCC-002 Control Center': '/rcc/2',
    '19 RCC-003 Control Center': '/rcc/3', '20 RCC-003 MIAR Registry': '/t/miar',
    '21 RCC-003 MIAR Review Log': '/t/review', '22 RCC-004 Control Center': '/rcc/4',
    '23 RCC-004 MASR Registry': '/t/masr', '24 RCC-004 Candidate Pipeline': '/pipeline',
}


@bp.route('/')
def console():
    w = wb()
    cisc = w.cisc()
    store = w.store
    current = {}
    for kind in (RV.WEEKLY, RV.MONTHLY, RV.QUARTERLY):
        review = RV.get(store, kind, today())
        rid, start, end, due = RV.period(kind, today())
        done, total = RV.progress(w, review) if review else (0, len(RV.CHECKLISTS[kind]))
        current[kind] = {'id': rid, 'review': review, 'done': done, 'total': total, 'end': end,
                         'start': start}
    # this week's steps reuse the weekly review's live checks, so the two always agree
    wk = current[RV.WEEKLY]
    review = wk['review'] or {'id': wk['id'], 'kind': RV.WEEKLY, 'start': wk['start'].isoformat(),
                              'end': wk['end'].isoformat(), 'items': {}}
    checks = {r['key']: r for r in RV.evaluate(w, review)}
    mwir = store['reports'].get(RP.report_id('mwir', today())[0])
    mwir_cert = MW.model(mwir['doc'], MW.snapshot(store))['cert'] if mwir and mwir.get('doc') else None
    return render_template('console.html', con=cisc.console, c=cisc.controls, d=cisc.data, dc=cisc.decision,
                           rcc1=w.rcc001()['state'], rcc4=w.rcc004()['state'], pew=w.pew().control,
                           reviews=current, inbox=len(open_items(store)), checks=checks, mwir=mwir,
                           mwir_cert=mwir_cert, mwir_label=MW.label(mwir['doc']) if mwir_cert else '', zacks_as_of=MW.snapshot(store).get('as_of'),
                           runs={k: last_run(store, k) for k in ('zacks', 'weights', 'research')})


@bp.route('/as-of', methods=['POST'])
def set_as_of():
    raw = request.form.get('as_of', '').strip()
    if raw:
        try:
            dt.date.fromisoformat(raw)
            session['as_of'] = raw
        except ValueError:
            flash('Use a valid date.', 'error')
    else:
        session.pop('as_of', None)
    return back()


# --------------------------------------------------------------------------- decisions

@bp.route('/decisions')
def decisions():
    w = wb()
    store = w.store
    pew = w.pew()
    items = {
        'pipeline': [r for r in w.pipeline if r['control_status'] == 'COMMITTEE DECISION REQUIRED'
                     or (r.get('stage') == 'Committee Review' and r['gate_result'].startswith('PASS'))],
        'masr': [r for r in w.masr if r.get('control_status') == 'COMMITTEE DISPOSITION REQUIRED'],
        'pew004': [r for r in w.pew004 if r['status'] == 'COMMITTEE DECISION REQUIRED'],
        'conviction': [r for r in w.conviction if r['decision_state'] != 'NO CHANGE'],
        'bands': [r for r in w.portfolio if r['band_status'] in ('Below band', 'Above band')],
        'workflow': [r for r in pew.workflow if r.get('status') == 'Pending'],
        'manual': [dict(r, _slot=i + 1) for i, r in enumerate(store['decisions']) if r],
    }
    return render_template('decisions.html', dc=w.cisc().decision, items=items,
                           lists=_lists())


def _lists():
    from .. import lists as L
    return L


@bp.route('/decisions/new', methods=['POST'])
def decision_new():
    fields = {k: request.form.get(k, '') for k in ('decision', 'category', 'evidence', 'recommendation',
                                                    'authority', 'owner', 'due_date', 'committee_decision')}
    pairs = [f'{k}={v}' for k, v in fields.items() if v.strip()] + [f'date_opened={today().isoformat()}',
                                                                     'status=Open']
    mutate(lambda s: ops.add_record(s, 'decisions', pairs, actor(), today()),
           'Decision added to the register.')
    return back('core.decisions')


@bp.route('/decisions/<int:slot>/resolve', methods=['POST'])
def decision_resolve(slot):
    values = {'status': request.form.get('status', ''), 'resolution': request.form.get('resolution', '')}
    mutate(lambda s: set_fields(s, 'decisions', str(slot), values), 'Decision recorded.')
    return back('core.decisions')


# --------------------------------------------------------------------------- actions & notebook

@bp.route('/actions')
def actions():
    store = repo().read()
    tables = {name: [dict(r, _slot=i + 1) for i, r in enumerate(store[name]) if r]
              for name in ('actions', 'priorities', 'questions', 'projects', 'publications', 'calendar',
                           'certifications')}
    return render_template('actions.html', t=tables)


@bp.route('/actions/<table>/new', methods=['POST'])
def action_new(table):
    if table not in ('actions', 'priorities', 'questions', 'projects', 'calendar', 'publications',
                     'certifications'):
        abort(404)
    pairs = [f'{k}={v}' for k, v in request.form.items() if k not in ('_csrf', 'next') and v.strip()]
    mutate(lambda s: ops.add_record(s, table, pairs, actor(), today()), 'Added.')
    return back('core.actions')


@bp.route('/actions/<table>/<int:slot>/status', methods=['POST'])
def action_status(table, slot):
    mutate(lambda s: set_fields(s, table, str(slot), {'status': request.form.get('status', '')}), 'Updated.')
    return back('core.actions')


@bp.route('/actions/<table>/<int:slot>/clear', methods=['POST'])
def action_clear(table, slot):
    mutate(lambda s: ops.clear_record(s, table, str(slot), actor()), 'Removed from the list (audited).')
    return back('core.actions')


# --------------------------------------------------------------------------- pipeline board

@bp.route('/pipeline')
def pipeline():
    w = wb()
    cards = [r for r in w.pipeline if r.get('candidate_id')]
    columns = [(stage, [c for c in cards if c.get('stage') == stage]) for stage in PIPELINE_COLUMNS]
    closed = [c for c in cards if c.get('stage') in CLOSED_STAGES]
    masr = {r['ticker']: r for r in w.masr if r.get('ticker')}
    pew_ids = [r['candidate_id'] for r in w.pew004]
    return render_template('pipeline.html', columns=columns, closed=closed, masr=masr, pew_ids=pew_ids,
                           state=w.rcc004()['state'])


@bp.route('/pipeline/<cid>/advance', methods=['POST'])
def pipeline_advance(cid):
    target = request.form.get('to') or None
    res = mutate(lambda s: ops.advance(s, cid, actor(), today(), target=target))
    if res:
        flash(f'{cid}: {res[0]} → {res[1]}', 'ok')
    return back('core.pipeline')


@bp.route('/pipeline/<cid>/update', methods=['POST'])
def pipeline_update(cid):
    values = {k: v for k, v in request.form.items() if k not in ('_csrf', 'next')}
    if values.get('committee_disposition') and not values.get('disposition_date'):
        values['disposition_date'] = today().isoformat()
    if values.get('stage') in CLOSED_STAGES:
        values.setdefault('closed_by', actor())
        values.setdefault('closed_date', today().isoformat())
    mutate(lambda s: set_fields(s, 'pipeline', cid, values), f'{cid} updated.')
    return back('core.pipeline')


@bp.route('/pipeline/new', methods=['POST'])
def pipeline_new():
    pairs = [f'{k}={v}' for k, v in request.form.items() if k not in ('_csrf', 'next') and v.strip()]
    rec = mutate(lambda s: ops.add_record(s, 'pipeline', pairs, actor(), today()))
    if rec and rec is not True:
        flash(f"Candidate {rec['candidate_id']} created at Intake.", 'ok')
    return back('core.pipeline')


# --------------------------------------------------------------------------- control centers

@bp.route('/rcc/<int:n>')
def rcc(n):
    w = wb()
    fn = {1: w.rcc001, 2: w.rcc002, 3: w.rcc003, 4: w.rcc004}.get(n)
    if fn is None:
        abort(404)
    return render_template('rcc.html', n=n, d=fn())


@bp.route('/research')
def research_home():
    w = wb()
    return render_template('research.html', s1=w.rcc001()['state'], s2=w.rcc002()['state'],
                           s3=w.rcc003()['state'], s4=w.rcc004()['state'],
                           inbox=len(open_items(w.store)))


@bp.route('/intel')
def intel():
    from .. import schema as S
    store = repo().read()
    sections = [(S.TABLES[n], [dict(r, _slot=i + 1) for i, r in enumerate(store[n]) if r]) for n in S.INTEL_TABLES]
    return render_template('intel.html', sections=sections)


@bp.route('/controls')
def controls():
    w = wb()
    return render_template('controls.html', c=w.cisc().controls)


@bp.route('/pew')
def pew():
    w = wb()
    p = w.pew()
    return render_template('pew.html', c=p.control, sleeves=p.sleeves)


@bp.route('/lab', methods=['GET', 'POST'])
def lab():
    if request.method == 'POST':
        def save(store):
            n = 0
            for pos, alloc in enumerate(store['portfolio']):
                sym = alloc['symbol']
                w_ = request.form.get(f'w_{sym}')
                r_ = request.form.get(f'r_{sym}')
                if w_ is None:
                    continue
                n += set_fields(store, 'scenario', sym, {'scenario_weight': w_, 'rationale': r_ or ''})
            n += set_fields(store, 'lab', None, {k: request.form.get(k, '') for k in
                                                 ('scenario_id', 'scenario_name', 'prepared_date')})
            return n
        n = mutate(save)
        if n is not None:
            flash(f'Scenario saved ({n} field change(s)). Certified weights are unchanged.', 'ok')
        return back('core.lab')
    w = wb()
    p = w.pew()
    inputs = w.store['scenario']
    rows = [{**(inputs[i] if i < len(inputs) else {}), **r} for i, r in enumerate(p.scenario)]
    return render_template('lab.html', lab=p.lab, rows=rows, sleeves=p.sleeves,
                           totals=p.sleeve_totals())


@bp.route('/validation')
def validation():
    w = wb()
    p = w.pew()
    return render_template('validation.html', p=p, cert=p.certification, tests=p.tests, workflow=p.workflow,
                           changes=p.changes)


@bp.route('/validation/workflow/<int:row>', methods=['POST'])
def workflow_decide(row):
    status = request.form.get('status', '')
    values = {'status': status, 'reviewed_by': actor(), 'review_date': today().isoformat(),
              'evidence_ref': request.form.get('evidence_ref', ''), 'notes': request.form.get('notes', '')}
    mutate(lambda s: set_fields(s, 'workflow', str(row), values), f'Review stage recorded as {status}.')
    return back('core.validation')


# --------------------------------------------------------------------------- reference

@bp.route('/sheets')
def sheets():
    return render_template('sheets.html', sheets=[(s, c, d, SHEET_PAGES.get(s, '/')) for s, c, d in SHEETS])


@bp.route('/doc/<name>')
def doc(name):
    from ..views import DOCS, load_docs
    if name not in DOCS:
        abort(404)
    sheet = DOCS[name]
    cells = wb().cells().get(sheet, {})
    rows = []
    for _, row_cells in load_docs()[sheet]:
        out = []
        for col, v in row_cells:
            if isinstance(v, dict):
                v = cells.get(v['cell'], '')
                v = f'{v * 100:.2f}%' if isinstance(v, float) else v
            out.append(str(v))
        rows.append(out)
    return render_template('doc.html', sheet=sheet, rows=rows)


@bp.route('/lists')
def lists():
    from .. import lists as L
    return render_template('lists.html', lists=L.REGISTRY)


@bp.route('/audit')
def audit():
    events = list(reversed(repo().read()['audit']))[:300]
    return render_template('audit.html', events=events)


@bp.app_template_global()
def stage_next(stage):
    if stage in PIPELINE_COLUMNS[:-2]:
        return PIPELINE_COLUMNS[PIPELINE_COLUMNS.index(stage) + 1]
    return None


@bp.app_template_global()
def is_blank(v):
    return blank(v)


@bp.app_context_processor
def nav_counts():
    try:
        store = repo().read()
    except Exception:  # pragma: no cover
        return {}
    from .. import reports as RP
    from . import nav
    from .auth import current_user
    inbox = len(open_items(store))
    mwir = store['reports'].get(RP.report_id('mwir', today())[0])
    badges = {'inbox': inbox or None, 'mwir': (mwir or {}).get('status') or 'Start'}
    return {'nav_inbox': inbox, 'url_for': url_for, **nav.context(badges, current_user())}
