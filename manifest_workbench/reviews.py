"""Weekly, monthly and quarterly review cycles.

Checklists follow the workbook's operating workflows: the CISC weekly workflow
(05 Workbench Guide), the RCC research workflow, the monthly allocation review and MOR
publication (04 Committee Operations calendar), and the quarterly engineering review,
sleeve / conviction cadence and scheduled rebalancing review (14 PEW Guide, Rebalancing).

Items with an automatic check read live workbench state; the operator confirms each
item (with an optional note) and signs the review off once every item is done.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable, Optional

from .connectors import last_run
from .engine import Workbench, blank

WEEKLY, MONTHLY, QUARTERLY = 'weekly', 'monthly', 'quarterly'
LABELS = {WEEKLY: 'Weekly review', MONTHLY: 'Monthly review', QUARTERLY: 'Quarterly review'}


@dataclass(frozen=True)
class Item:
    key: str
    text: str
    source: str
    check: Optional[Callable] = None   # (wb, review) -> (ok: bool, detail: str)
    link: str = ''


def period(kind: str, on: dt.date) -> tuple:
    """(review id, start, end, due) for the period containing ``on``."""
    if kind == WEEKLY:
        start = on - dt.timedelta(days=on.weekday())
        end = start + dt.timedelta(days=6)
        year, week, _ = on.isocalendar()
        return f'weekly-{year}-W{week:02d}', start, end, start  # Monday workflow
    if kind == MONTHLY:
        start = on.replace(day=1)
        end = (start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
        return f'monthly-{on:%Y-%m}', start, end, end
    q = (on.month - 1) // 3 + 1
    start = dt.date(on.year, 3 * q - 2, 1)
    end = (dt.date(on.year + (q == 4), (3 * q) % 12 + 1, 1)) - dt.timedelta(days=1)
    return f'quarterly-{on.year}-Q{q}', start, end, end


# --------------------------------------------------------------------------- checks

def _ran(connector):
    def check(wb, review):
        run = last_run(wb.store, connector)
        if not run:
            return False, 'Never run'
        when = run['ts'][:10]
        return when >= review['start'], f"Last run {when}: {run['summary']}"
    return check


def _report_issued(kind):
    def check(wb, review):
        issued = [r for r in wb.store.get('reports', {}).values()
                  if r.get('type') == kind and r.get('status') == 'Issued'
                  and (r.get('review_id') == review['id']
                       or review['start'] <= (r.get('issued') or '')[:10] <= review['end'])]
        return (True, f"Issued {issued[-1]['issued'][:10]} (v{issued[-1].get('version', 1)})") if issued \
            else (False, 'Not issued for this period')
    return check


def _controls_dated(wb, review):
    d = wb.store.get('controls', {}).get('report_date') or ''
    return review['start'] <= d <= review['end'], f'Report date {d or "not set"}'


def _weights(wb, review):
    t = wb.portfolio_totals()
    loaded = t['actual_loaded'] == t['positions']
    run = last_run(wb.store, 'weights')
    fresh = bool(run) and run['ts'][:10] >= review['start']
    return loaded and fresh, (f"{t['actual_loaded']} / {t['positions']} loaded; "
                              + (f"last load {run['ts'][:10]}" if run else 'no CSV loaded yet'))


def _conviction(wb, review):
    n = sum(1 for r in wb.conviction if r['effective_conviction'] != 'Unassigned')
    return n == len(wb.conviction), f'{n} / {len(wb.conviction)} effective convictions assigned'


def _inbox(wb, review):
    n = sum(1 for i in wb.store.get('inbox', []) if i.get('status') == 'New')
    pulled, detail = _ran('research')(wb, review)
    return pulled and n == 0, f'{detail} · {n} items awaiting triage'


def _evidence(wb, review):
    n = len(wb.evidence_exceptions())
    return n == 0, f'{n} evidence control exceptions'


def _rcc(wb, review):
    s = wb.rcc001()['state']
    return s['readiness'] in ('ACTIVE', 'RCC READY — NO EVIDENCE LOADED'), \
        f"{s['readiness']} · {s['control_exceptions']} control exceptions"


def _decision_center(wb, review):
    dc = wb.cisc().decision
    return dc['state'] != 'DATA UPDATE REQUIRED', f"{dc['state']} · {dc['total_decisions']} committee decisions"


def _bands(wb, review):
    d = wb.cisc().data
    return d['missing_actual'] == 0 and d['band_breaches'] == 0, \
        f"{d['band_breaches']} band exceptions · {d['missing_actual']} actual weights missing"


def _sleeves_live(wb, review):
    d = wb.cisc().data
    off = [s['sleeve'] for s in d['sleeves'] if abs(s['variance']) > 0.02]
    return d['missing_actual'] == 0 and not off, ('Sleeves within 2 points of target' if not off
                                                  else 'Review: ' + ', '.join(off))


def _pipeline(wb, review):
    exc = wb.pipeline_exceptions()
    overdue = sum(1 for r in exc if r['control_status'] == 'OVERDUE')
    return not exc, f'{len(exc)} candidate exceptions ({overdue} overdue)'


def _manual_decisions(wb, review):
    n = wb.cisc().decision['manual_decisions']
    return n == 0, f'{n} manual committee decisions open'


def _actions(wb, review):
    today = wb.today.isoformat()
    late = [a for a in wb.store.get('actions', []) if a and a.get('status') in ('Open', 'In Progress')
            and not blank(a.get('due_date')) and a['due_date'] < today]
    return not late, f'{len(late)} operating actions past due'


def _mandate(wb, review):
    m = wb.pew().mandate
    open_ = [r['control_id'] for r in m if str(r.get('status', '')).startswith(('INPUT', 'FAIL', 'MONITOR'))]
    return not open_, ('All mandate controls active or passing' if not open_
                       else 'Attention: ' + ', '.join(open_))


def _sleeve_arch(wb, review):
    states = {s['sleeve']: s['decision_state'] for s in wb.pew().sleeves}
    bad = [k for k, v in states.items() if v != 'BASELINE']
    return not bad, 'All sleeves at baseline' if not bad else f'{len(bad)} sleeves need review'


def _conviction_review(wb, review):
    n = sum(1 for r in wb.conviction if r['decision_state'] != 'NO CHANGE')
    return n == 0, f'{n} conviction / thesis decisions outstanding'


def _miar(wb, review):
    s = wb.rcc003()['state']
    return s['due_overdue'] == 0 and s['material_events'] == 0 and s['control_exceptions'] == 0, \
        f"{s['coverage']} · {s['due_overdue']} due/overdue · {s['material_events']} material events"


def _validation(wb, review):
    pew = wb.pew()
    if pew.lab['changed_positions'] == 0:
        return True, 'No scenario proposed; certified baseline preserved'
    return pew.readiness() == 'READY', f"Scenario {pew.lab['scenario_status']} · validation {pew.readiness()}"


def _roles(wb, review):
    rs = wb.pew().role_summary()
    return rs['review_items'] == 0, f"{rs['passed']} role controls passed · {rs['review_items']} review items"


CHECKLISTS = {
    WEEKLY: (
        Item('controls', 'Update report date, composite score components and confidence',
             '05 Workbench Guide · step 1', _controls_dated, '/controls'),
        Item('weights', 'Load all 47 actual portfolio weights (broker CSV)',
             '05 Workbench Guide · step 2', _weights, '/data'),
        Item('zacks', 'Pull Zacks Rank and market capitalization', 'PEW-001-18/19 · RCC-005 inputs',
             _ran('zacks'), '/data'),
        Item('research', 'Pull research and triage the inbox', 'RCC-002 · research intake',
             _inbox, '/data#inbox'),
        Item('conviction', 'Assign conviction and research status', '05 Workbench Guide · step 3',
             _conviction, '/t/conviction'),
        Item('evidence', 'Review materiality, reliability and routing', '17 RCC-002 Control Center',
             _evidence, '/rcc/2'),
        Item('rcc', 'Monitor research readiness and exceptions', '16 RCC-001 Control Center', _rcc, '/rcc/1'),
        Item('decisions', 'Review the Manifest Decision Center', '05 Workbench Guide · step 5',
             _decision_center, '/decisions'),
        Item('mird', 'Publish the MIRD weekly risk dashboard', '04 Committee Operations · publications',
             _report_issued('mird'), '/reports'),
        Item('mwir', 'Publish the MWIR and related dashboards', '05 Workbench Guide · step 6',
             _report_issued('mwir'), '/mwir'),
    ),
    MONTHLY: (
        Item('bands', 'Monthly allocation review: certified band exceptions', 'Rebalancing · 04 calendar',
             _bands, '/t/portfolio'),
        Item('sleeves', 'Sleeve allocation versus certified targets', '99 Dashboard Data · Sleeve Summary',
             _sleeves_live, '/cisc'),
        Item('pipeline', 'Candidate pipeline: overdue or blocked stage gates', '22 RCC-004 Control Center',
             _pipeline, '/pipeline'),
        Item('manual', 'Resolve manual committee decisions', '02 Decision Center', _manual_decisions,
             '/decisions'),
        Item('actions', 'Close or re-date past-due operating actions', '04 Committee Operations', _actions,
             '/actions'),
        Item('mor', 'Publish the MOR', '04 Committee Operations · publications', _report_issued('mor'),
             '/reports'),
    ),
    QUARTERLY: (
        Item('mandate', 'PEW-001 mandate & constraints review', '14 PEW Guide · annual / material review',
             _mandate, '/t/mandate'),
        Item('sleeve-arch', 'PEW-002 sleeve architecture review', '14 PEW Guide · quarterly',
             _sleeve_arch, '/t/sleeves'),
        Item('roles', 'PEW-003 portfolio role review', '14 PEW Guide', _roles, '/t/roles'),
        Item('conviction', 'PEW-005 conviction & thesis review', '14 PEW Guide · quarterly',
             _conviction_review, '/t/conviction'),
        Item('miar', 'RCC-003 MIAR dossier cadence and freshness', '19 RCC-003 Control Center', _miar,
             '/rcc/3'),
        Item('rebalance', 'Scheduled portfolio-level reconciliation', 'Rebalancing · quarterly review',
             _bands, '/t/portfolio'),
        Item('validation', 'PEW-006 / PEW-007 scenario validation (if a scenario is proposed)',
             '13 Validation & Cert', _validation, '/validation'),
        Item('qer', 'Issue the quarterly engineering review', '04 calendar · quarterly engineering review',
             _report_issued('qer'), '/reports'),
        Item('mipr', 'Issue the MIPR institutional portfolio review', '04 Committee Operations · publications',
             _report_issued('mipr'), '/reports'),
    ),
}


# --------------------------------------------------------------------------- state

def get(store: dict, kind: str, on: dt.date, create: bool = False) -> Optional[dict]:
    rid, start, end, due = period(kind, on)
    review = store.setdefault('reviews', {}).get(rid)
    if review is None and create:
        review = {'id': rid, 'kind': kind, 'start': start.isoformat(), 'end': end.isoformat(),
                  'due': due.isoformat(), 'status': 'Not Started', 'items': {}, 'notes': '',
                  'signed_by': None, 'signed_at': None}
        store['reviews'][rid] = review
    return review


def evaluate(wb: Workbench, review: dict) -> list:
    """Checklist rows with live check results and confirmations."""
    rows = []
    for item in CHECKLISTS[review['kind']]:
        state = review['items'].get(item.key, {})
        ok, detail = item.check(wb, review) if item.check else (None, '')
        rows.append({'key': item.key, 'text': item.text, 'source': item.source, 'link': item.link,
                     'auto_ok': ok, 'detail': detail, 'done': bool(state.get('done')),
                     'by': state.get('by'), 'at': state.get('at'), 'note': state.get('note', '')})
    return rows


def progress(wb: Workbench, review: dict) -> tuple:
    rows = evaluate(wb, review)
    return sum(1 for r in rows if r['done']), len(rows)


def confirm(store: dict, review_id: str, key: str, actor: str, note: str = '', done: bool = True,
            wb: Workbench = None) -> None:
    review = store['reviews'][review_id]
    if review['status'] == 'Completed':
        raise ValueError('This review is signed off; reopen it to make changes')
    items = {i.key: i for i in CHECKLISTS[review['kind']]}
    if key not in items:
        raise ValueError(f'Unknown checklist item {key}')
    if done and wb is not None and items[key].check:
        ok, detail = items[key].check(wb, review)
        if not ok and not note.strip():
            raise ValueError(f'Check not met ({detail}). Add a note explaining the exception to confirm anyway.')
    review['items'][key] = {'done': done, 'by': actor, 'at': dt.datetime.now().isoformat(timespec='seconds'),
                            'note': note.strip()}
    review['status'] = 'In Progress'
    _log(store, actor, review_id, f"{'confirmed' if done else 'reopened'} {key}", note)


def sign_off(store: dict, review_id: str, actor: str, wb: Workbench, notes: str = '') -> None:
    review = store['reviews'][review_id]
    rows = evaluate(wb, review)
    open_ = [r['text'] for r in rows if not r['done']]
    if open_:
        raise ValueError('Confirm every item before signing off: ' + '; '.join(open_))
    review.update({'status': 'Completed', 'signed_by': actor,
                   'signed_at': dt.datetime.now().isoformat(timespec='seconds'), 'notes': notes.strip()})
    _log(store, actor, review_id, 'signed off', notes)


def reopen(store: dict, review_id: str, actor: str, reason: str) -> None:
    review = store['reviews'][review_id]
    review.update({'status': 'In Progress', 'signed_by': None, 'signed_at': None})
    _log(store, actor, review_id, 'reopened', reason)


def _log(store, actor, review_id, what, note):
    store['audit'].append({'ts': dt.datetime.now().isoformat(timespec='seconds'), 'actor': actor,
                           'action': 'review', 'table': 'reviews', 'record': review_id, 'field': what,
                           'old': None, 'new': note or None})
