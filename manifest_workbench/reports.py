"""Report studio: MWIR, MIRD, MOR, quarterly engineering review and MIPR.

A report starts as a *draft*: a snapshot of the workbench tables for the period plus
an auto-written narrative per section. The operator edits narratives, hides sections or
adds commentary, refreshes the data if needed, previews, and then *issues* the report,
which renders the PDF, versions it and records the publication in Committee Operations.

The MWIR is the exception: it is the official 8-page weekly report (see ``mwir.py``), kept as
a document that carries forward week to week rather than as auto-written sections.
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

from . import mwir as MW
from . import reviews as RV
from .engine import Workbench

TYPES = {
    'mwir': {'code': 'MWIR', 'title': 'Weekly Institutional Report', 'cycle': RV.WEEKLY,
             'publication': 'MWIR'},
    'mird': {'code': 'MIRD', 'title': 'Weekly Risk Dashboard', 'cycle': RV.WEEKLY, 'publication': 'MIRD'},
    'mor': {'code': 'MOR', 'title': 'Monthly Report', 'cycle': RV.MONTHLY, 'publication': 'MOR'},
    'qer': {'code': 'QER', 'title': 'Quarterly Engineering Review', 'cycle': RV.QUARTERLY,
            'publication': 'Quarterly engineering review'},
    'mipr': {'code': 'MIPR', 'title': 'Institutional Portfolio Review', 'cycle': RV.QUARTERLY,
             'publication': 'MIPR'},
}

GOVERNANCE = ('This report is an executive decision-support publication. The certified MFPDF v1.0 '
              'remains the sole portfolio system of record. No figure in this report authorizes a '
              'trade; automatic trading is prohibited and committee review precedes any implementation. '
              'Scenario analysis does not modify the certified portfolio.')


def pct(v, places=2):
    return '' if v in ('', None) else f'{v * 100:.{places}f}%'


def fmt(v):
    if v is None:
        return ''
    if isinstance(v, float):
        return f'{v:.2f}'.rstrip('0').rstrip('.')
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    return str(v)


def table(title, columns, rows, empty='None'):
    return {'title': title, 'columns': list(columns), 'rows': [[fmt(c) for c in r] for r in rows],
            'empty': empty}


def section(key, title, narrative, tables=()):
    return {'key': key, 'title': title, 'include': True, 'narrative': narrative,
            'auto_narrative': narrative, 'tables': list(tables), 'custom': False}


def _in(date_text, start, end):
    return bool(date_text) and start <= str(date_text)[:10] <= end


# =========================================================================== shared sections

def _summary(wb, extra=''):
    cisc = wb.cisc()
    c, dc, d = cisc.controls, cisc.decision, cisc.data
    s1 = wb.rcc001()['state']
    text = (f"Decision state: {dc['state']}. Current posture is {c['posture']} with a composite alignment "
            f"score of {c['composite_score']:+.2f} ({c['classification']}; weekly change "
            f"{c['weekly_change']:+.2f}). {cisc.console['detail']} Highest priority: {dc['priority']}. "
            + extra)
    rows = [('Composite alignment score', f"{c['composite_score']:+.2f}"),
            ('Current posture', c['posture']), ('Confidence', pct(c.get('confidence'), 0)),
            ('Decision state', dc['state']), ('Committee decisions required', dc['total_decisions']),
            ('Data completeness', pct(dc['completeness'], 0)),
            ('Actual weights missing', d['missing_actual']), ('Research readiness', s1['readiness'])]
    return section('summary', 'Executive summary', text.strip(), [table('Key indicators', ('Indicator', 'Value'),
                                                                        rows)])


def _decisions(wb):
    dc = wb.cisc().decision
    manual = [r for r in wb.store.get('decisions', []) if r and r.get('status') in ('Open', 'In Review')]
    text = ('No committee action is required this week.' if dc['state'] == 'NO COMMITTEE ACTION REQUIRED' else
            f"{dc['state']}: {dc['total_decisions']} committee decision(s) identified. Meeting status: "
            f"{dc['meeting']}.")
    return section('decisions', 'Decisions required', text, [
        table('System decision queue', ('ID', 'Category', 'Trigger', 'Decision required', 'Status'),
              [(q['id'], q['category'], q['trigger'], q['decision'], q['status']) for q in dc['queue']]),
        table('Open manual decisions', ('ID', 'Decision', 'Owner', 'Due', 'Committee?', 'Status'),
              [(r.get('id'), r.get('decision'), r.get('owner'), r.get('due_date'), r.get('committee_decision'),
                r.get('status')) for r in manual], 'No open manual decisions')])


def _portfolio_health(wb):
    d = wb.cisc().data
    note = wb.cisc().console['alert_note']
    alerts = [a for a in d['alerts'] if a['symbol']]
    return section('portfolio', 'Portfolio health', f"{note} Ranking basis: {d['ranking_basis']}.", [
        table('Sleeve allocation', ('Sleeve', 'Target', 'Actual', 'Variance'),
              [(s['sleeve'], pct(s['target']), pct(s['actual']), pct(s['variance'])) for s in d['sleeves']]),
        table('Top 10 holdings', ('Rank', 'Holding', 'Weight', 'Role', 'Conviction'),
              [(t['rank'], t['symbol'], pct(t['weight']), t['role'], t['conviction']) for t in d['top10']]),
        table('Allocation alerts', ('Rank', 'Holding', 'Actual', 'Target', 'Variance', 'Status', 'Action'),
              [(a['rank'], a['symbol'], pct(a['actual']), pct(a['target']), pct(a['variance']), a['band_status'],
                a['action']) for a in alerts], 'No holdings outside certified bands')])


def _research(wb, start, end):
    s2 = wb.rcc002()['state']
    new_ev = [r for r in wb.evidence if _in(r.get('date_received'), start, end)]
    zacks = [r for r in wb.store.get('intel-zacks', []) if r and _in(r.get('date'), start, end)]
    review = [r for r in wb.store.get('intel-review', []) if r and r.get('symbol')]
    text = (f"{len(new_ev)} evidence record(s) logged this period; {s2['open']} open, {s2['critical_high']} "
            f"critical/high, {s2['overdue']} overdue and {s2['referrals_ready']} ready for routing. "
            f"{len(zacks)} Zacks Rank change(s) recorded.")
    return section('research', 'Research intelligence', text, [
        table('Zacks Rank changes', ('Date', 'Symbol', 'Prior', 'Current', 'Direction'),
              [(r.get('date'), r.get('symbol'), r.get('prior_rank'), r.get('current_rank'), r.get('direction'))
               for r in zacks], 'No rank changes this period'),
        table('Evidence logged this period', ('Evidence ID', 'Ticker', 'Activity', 'Materiality', 'Control'),
              [(r['evidence_id'], r.get('ticker'), r.get('activity_type'), r.get('materiality'),
                r['control_status']) for r in new_ev], 'No new evidence'),
        table('Companies requiring review', ('Symbol', 'Reason', 'Priority', 'Due', 'Status'),
              [(r.get('symbol'), r.get('reason'), r.get('priority'), r.get('due_date'), r.get('status'))
               for r in review], 'No companies in the review queue')])


def _pipeline(wb):
    s4 = wb.rcc004()['state']
    rows = [r for r in wb.pipeline if r.get('candidate_id')]
    text = (f"{s4['active_candidates']} active candidate(s); stage gates {s4['stage_gates']}; "
            f"{s4['pew_referrals']} referred to PEW-004; {s4['control_exceptions']} MASR / pipeline control "
            f"exceptions ({s4['readiness']}).")
    return section('pipeline', 'MASR candidate pipeline', text, [
        table('Candidates', ('Candidate', 'Ticker', 'Stage', 'Gate', 'Control', 'Next action'),
              [(r['candidate_id'], r.get('ticker'), r.get('stage'), r['gate_result'], r['control_status'],
                r['next_action']) for r in rows], 'No candidates')])


def _committee(wb, start, end):
    st = wb.store
    actions = [a for a in st.get('actions', []) if a and a.get('status') in ('Open', 'In Progress', 'Planned')]
    cal = [c for c in st.get('calendar', []) if c and c.get('event')]
    qs = [q for q in st.get('questions', []) if q and q.get('status') in ('Open', 'Pending Data')]
    return section('committee', 'Committee operations',
                   f'{len(actions)} open or planned operating action(s); {len(qs)} open committee question(s).', [
                       table('Operating actions', ('ID', 'Action', 'Owner', 'Due', 'Status'),
                             [(a.get('id'), a.get('action'), a.get('owner'), a.get('due_date'), a.get('status'))
                              for a in actions], 'No open actions'),
                       table('Questions for committee', ('ID', 'Question', 'Owner', 'Status'),
                             [(q.get('id'), q.get('question'), q.get('owner'), q.get('status')) for q in qs],
                             'No open questions'),
                       table('Operational calendar', ('Date', 'Event', 'Cadence', 'Status'),
                             [(c.get('date') or 'TBD', c.get('event'), c.get('cadence'), c.get('status'))
                              for c in cal])])


def _governance(text=GOVERNANCE):
    return section('governance', 'Governance statement', text)


# =========================================================================== report bodies

def _mird(wb, start, end):
    d = wb.cisc().data
    port = wb.portfolio
    breaches = [r for r in port if r['band_status'] in ('Below band', 'Above band')]
    live = d['missing_actual'] == 0
    weights = sorted((r.get('actual_weight') if live else r.get('target_weight')) or 0 for r in port)[::-1]
    masr_exc = [r for r in wb.masr if r.get('ticker') and r.get('exception_requirement') not in ('None', '',
                                                                                                    None)
                and r.get('exception_requirement') != 'Canonical MASR ID required']
    weak = [r for r in wb.masr if r.get('ticker') and r.get('zacks_rank') in (4, 5)]
    crit = [r for r in wb.evidence if r.get('evidence_id') and r.get('materiality') in ('Critical', 'High')
            and r['control_status'] not in ('CLOSED',)]
    miar = [r for r in wb.miar if r['research_freshness'] in ('OVERDUE', 'MATERIAL EVENT REVIEW', 'REVIEW DUE')]
    text = (f"{len(breaches)} holding(s) outside certified bands; top-10 concentration "
            f"{pct(sum(weights[:10]))} ({'actual' if live else 'target'} weights); largest position "
            f"{pct(weights[0] if weights else 0)}. {len(weak)} registry security(ies) at Zacks #4/#5; "
            f"{len(crit)} open critical/high evidence item(s); {len(miar)} MIAR dossier(s) due, overdue or under "
            'material-event review.' + ('' if live else f" {d['missing_actual']} actual weights are not loaded, "
                                                        'so band tests are not yet live.'))
    return [
        section('summary', 'Risk summary', text, [table('Risk indicators', ('Indicator', 'Value'), [
            ('Band exceptions', len(breaches)), ('Top-10 concentration', pct(sum(weights[:10]))),
            ('Largest position', pct(weights[0] if weights else 0)), ('Zacks #4/#5 securities', len(weak)),
            ('Critical / high evidence open', len(crit)), ('MIAR dossiers due or overdue', len(miar)),
            ('Actual weights missing', d['missing_actual'])])]),
        section('bands', 'Certified band exceptions',
                'Outside-band positions are reviewed by the Stewardship Committee; they are not traded '
                'automatically.', [table('Band exceptions', ('Symbol', 'Target', 'Lower', 'Upper', 'Actual',
                                                              'Status', 'Action'),
                                         [(r['symbol'], pct(r['target_weight']), pct(r['lower_band']),
                                           pct(r['upper_band']), pct(r.get('actual_weight')), r['band_status'],
                                           r['rebalancing_action']) for r in breaches],
                                         'No band exceptions' if live else 'Actual weights not loaded')]),
        section('sleeves', 'Sleeve variance', 'Sleeve allocation compared with certified targets.', [
            table('Sleeves', ('Sleeve', 'Target', 'Actual', 'Variance'),
                  [(s['sleeve'], pct(s['target']), pct(s['actual']), pct(s['variance'])) for s in d['sleeves']])]),
        section('external', 'External research exceptions',
                'Zacks #4/#5, sub-$50B Zacks elections and Merrill No Rating or restricted research require '
                'documented exception review.', [
                    table('Zacks #4 / #5', ('Ticker', 'Security', 'Zacks Rank', 'Market cap ($B)', 'Class'),
                          [(r['ticker'], r.get('security'), r.get('zacks_rank'), r.get('market_cap'),
                            r.get('record_class')) for r in weak], 'None'),
                    table('Eligibility exceptions', ('Ticker', 'Exception', 'Control status'),
                          [(r['ticker'], r['exception_requirement'], r['control_status']) for r in masr_exc],
                          'None')]),
        section('research', 'Research risk', 'Open critical / high evidence and MIAR freshness exceptions.', [
            table('Critical / high evidence', ('Evidence ID', 'Ticker', 'Summary', 'Control'),
                  [(r['evidence_id'], r.get('ticker'), r.get('summary'), r['control_status']) for r in crit],
                  'None'),
            table('MIAR freshness', ('Ticker', 'Freshness', 'Next review', 'Control'),
                  [(r['ticker'], r['research_freshness'], r.get('next_review'), r['control_status']) for r in miar],
                  'None')]),
        _governance()]


def _mor(wb, start, end):
    audit = [e for e in wb.store.get('audit', []) if _in(e.get('ts'), start, end)]
    decisions = [e for e in audit if e.get('table') == 'decisions']
    stage_moves = [e for e in audit if e.get('table') == 'pipeline' and e.get('field') == 'stage']
    ev = [r for r in wb.evidence if _in(r.get('date_received'), start, end)]
    weekly = [r for r in wb.store.get('reviews', {}).values() if r['kind'] == RV.WEEKLY
              and r['start'] <= end and r['end'] >= start]
    d = wb.cisc().data
    text = (f"Month summary: {len(ev)} evidence record(s) logged, {len(stage_moves)} candidate stage move(s), "
            f"{len(decisions)} decision-register change(s), {len(weekly)} weekly review(s) opened "
            f"({sum(1 for r in weekly if r['status'] == 'Completed')} signed off). "
            f"{d['band_breaches']} band exception(s) at month end.")
    return [
        _summary(wb, extra=text),
        _portfolio_health(wb),
        section('activity', 'Monthly activity', text, [
            table('Candidate stage moves', ('When', 'Candidate', 'From', 'To', 'By'),
                  [(e['ts'][:10], e['record'], e.get('old'), e.get('new'), e['actor']) for e in stage_moves], 'None'),
            table('Decision register changes', ('When', 'Record', 'Field', 'New value', 'By'),
                  [(e['ts'][:10], e['record'], e.get('field') or e['action'], fmt(e.get('new')), e['actor'])
                   for e in decisions], 'None'),
            table('Weekly reviews', ('Review', 'Status', 'Signed off by', 'Signed'),
                  [(r['id'], r['status'], r.get('signed_by') or '', (r.get('signed_at') or '')[:10])
                   for r in weekly], 'None')]),
        _research(wb, start, end), _pipeline(wb), _governance()]


def _qer(wb, start, end):
    pew = wb.pew()
    c = pew.control
    s3 = wb.rcc003()
    return [
        section('summary', 'PEW control state',
                f"Implementation state {c['implementation_state']}; certification state "
                f"{c['certification_state']}. Primary required action: {c['primary_action']}.",
                [table('MOPS-002 modules', ('Module', 'Workspace', 'Status', 'Open items'),
                       [(m[0], m[1], m[3], m[4]) for m in c['modules']])]),
        section('mandate', 'PEW-001 mandate & constraints', 'Adopted mandate controls and current state.', [
            table('Mandate register', ('Control', 'Objective / constraint', 'Classification', 'Value', 'Status'),
                  [(r['control_id'], r.get('objective'), r.get('classification'), _mandate_value(r),
                    r.get('status')) for r in pew.mandate])]),
        section('sleeves', 'PEW-002 sleeve architecture', f"Scenario total: {pew.sleeve_totals()['decision_state']}.", [
            table('Sleeves', ('Sleeve', 'Certified', 'Scenario', 'Delta', 'Conviction', 'Decision state'),
                  [(s['sleeve'], pct(s['certified_target']), pct(s['scenario']), pct(s['delta']),
                    pct(s['conviction_completeness'], 0), s['decision_state']) for s in pew.sleeves])]),
        section('roles', 'PEW-003 role assignment & PEW-005 conviction',
                '{passed} role controls passed, {review_items} review items, {replacement_candidates} '
                'replacement candidates.'.format(**pew.role_summary()) +
                f" {pew.conviction_assigned()} of 47 effective convictions assigned.", [
                    table('Role / conviction exceptions', ('Symbol', 'Role control', 'Conviction', 'Decision state'),
                          [(r['symbol'], x['control_status'], r['effective_conviction'], r['decision_state'])
                           for r, x in zip(wb.conviction, pew.roles)
                           if x['control_status'] != 'PASS' or r['decision_state'] != 'NO CHANGE'], 'None')]),
        section('lab', 'PEW-006 allocation lab',
                f"Scenario {pew.lab.get('scenario_id', '')} — {pew.lab.get('scenario_name', '')}: "
                f"{pew.lab['scenario_status']}; {pew.lab['changed_positions']} changed position(s), gross turnover "
                f"{pct(pew.lab['gross_turnover'])}.", [
                    table('Changed positions', ('Symbol', 'Certified', 'Scenario', 'Change', 'Band test', 'Validation'),
                          [(r['symbol'], pct(r['certified_target']), pct(r['effective_weight']), pct(r['change']),
                            r['band_test'], r['validation_state']) for r in pew.scenario if r['change'] != 0],
                          'Certified baseline preserved')]),
        section('validation', 'PEW-007 validation & certification',
                f"Overall readiness {pew.readiness()}; certification state "
                f"{pew.certification['certification_state']}.", [
                    table('Validation tests', ('Test', 'Validation test', 'Result', 'Status'),
                          [(t['id'], t['test'], fmt(t['result']) if not isinstance(t['result'], float)
                            else pct(t['result']), t['status']) for t in pew.tests]),
                    table('Certification workflow', ('Stage', 'Status', 'Reviewed by', 'Date'),
                          [(r.get('stage'), r.get('status'), r.get('reviewed_by'), r.get('review_date'))
                           for r in pew.workflow])]),
        section('miar', 'RCC-003 MIAR dossier cadence', f"{s3['state']['coverage']}; {s3['state']['readiness']}.", [
            table('Sleeve MIAR coverage', ('Sleeve', 'Records', 'Complete', 'Current', 'Due/overdue', 'Primary state'),
                  [(x['sleeve'], x['records'], x['complete'], x['current'],
                    x['update_due'] + x['review_due'] + x['overdue'], x['primary']) for x in s3['sleeves']])]),
        _governance()]


def _mipr(wb, start, end):
    s1 = wb.rcc001()['state']
    s4 = wb.rcc004()
    t = wb.portfolio_totals()
    return [
        _summary(wb),
        section('composition', 'Certified portfolio composition',
                f"Canonical Portfolio B: {t['positions']} positions, certified target {t['certification']}; "
                f"actual weights {t['actual_loaded']} / {t['positions']} loaded.", [
                    table('Certified allocation', ('Sleeve', 'Symbol', 'Security', 'Target', 'Actual', 'Band status',
                                                   'Conviction'),
                          [(r['sleeve'], r['symbol'], r['security'], pct(r['target_weight']),
                            pct(r.get('actual_weight')), r['band_status'], c['effective_conviction'])
                           for r, c in zip(wb.portfolio, wb.conviction)])]),
        _portfolio_health(wb),
        section('research', 'Research control state',
                f"Research readiness {s1['readiness']}; {s1['control_exceptions']} research control exceptions.", [
                    table('MASR registry composition', ('Class', 'Records', 'Control clear', 'Exceptions'),
                          [row for row in s4['composition'] if row[1]])]),
        _pipeline(wb), _governance()]


def _mandate_value(r):
    v = r.get('operating_value')
    if isinstance(v, float) and v < 1.5:
        return pct(v)
    return fmt(v)


BUILDERS = {'mird': _mird, 'mor': _mor, 'qer': _qer, 'mipr': _mipr}


# =========================================================================== lifecycle

def report_id(kind: str, on: dt.date) -> tuple:
    rid, start, end, _ = RV.period(TYPES[kind]['cycle'], on)
    return f"{kind}-{rid.split('-', 1)[1]}", rid, start, end


def period_label(kind, start, end):
    cycle = TYPES[kind]['cycle']
    if cycle == RV.WEEKLY:
        return f'Week ending {end:%b} {end.day}, {end.year}'
    if cycle == RV.MONTHLY:
        return f'{start:%B %Y}'
    return f'Q{(start.month - 1) // 3 + 1} {start.year}'


def create_draft(store: dict, kind: str, actor: str, today: dt.date) -> dict:
    if kind not in TYPES:
        raise ValueError(f'Unknown report type {kind}')
    rid, review_id, start, end = report_id(kind, today)
    existing = store['reports'].get(rid)
    if existing and existing['status'] == 'Draft':
        return existing
    wb = Workbench(store, today)
    t = TYPES[kind]
    draft = {
        'id': rid, 'type': kind, 'code': t['code'], 'review_id': review_id,
        'period_start': start.isoformat(), 'period_end': end.isoformat(),
        'period_label': period_label(kind, start, end),
        'title': f"{t['code']} — {t['title']}", 'subtitle': 'Manifest Institutional Investment System',
        'status': 'Draft', 'version': (existing or {}).get('version', 0),
        'files': (existing or {}).get('files', []),
        'created': dt.datetime.now().isoformat(timespec='seconds'), 'created_by': actor,
        'updated': None, 'updated_by': None, 'snapshot_as_of': today.isoformat(),
        'sections': [] if kind == 'mwir' else BUILDERS[kind](wb, start.isoformat(), end.isoformat()),
    }
    if kind == 'mwir':
        draft['layout'] = 'official'
        draft['title'] = 'MWIR — Weekly Institutional Report'
        draft['doc'] = copy.deepcopy(existing['doc']) if existing and existing.get('doc') \
            else MW.new_doc(store, _prior_mwir(store, start), start)
        draft['period_label'] = MW.label(draft['doc'])
    store['reports'][rid] = draft
    _audit(store, actor, rid, 'draft created')
    return draft


def refresh(store: dict, rid: str, actor: str, today: dt.date) -> dict:
    """Re-snapshot the data; edited narratives and inclusion choices are kept."""
    draft = _draft(store, rid)
    if draft.get('doc'):
        draft['snapshot_as_of'] = today.isoformat()  # the MWIR reads live data directly
        _touch(draft, actor)
        return draft
    wb = Workbench(store, today)
    fresh = {s['key']: s for s in BUILDERS[draft['type']](wb, draft['period_start'], draft['period_end'])}
    for sec in draft['sections']:
        new = fresh.get(sec['key'])
        if sec.get('custom') or new is None:
            continue
        edited = sec['narrative'] != sec['auto_narrative']
        sec['tables'] = new['tables']
        sec['auto_narrative'] = new['auto_narrative']
        if not edited:
            sec['narrative'] = new['narrative']
    draft['snapshot_as_of'] = today.isoformat()
    _touch(draft, actor)
    _audit(store, actor, rid, 'data refreshed')
    return draft


def edit(store: dict, rid: str, actor: str, title=None, subtitle=None, sections=None) -> dict:
    """Apply edits: sections maps key -> {'narrative', 'include', 'title'} (custom sections only for title)."""
    draft = _draft(store, rid)
    if title is not None:
        draft['title'] = title.strip() or draft['title']
    if subtitle is not None:
        draft['subtitle'] = subtitle.strip()
    for sec in draft['sections']:
        change = (sections or {}).get(sec['key'])
        if not change:
            continue
        if 'narrative' in change:
            sec['narrative'] = change['narrative'].replace('\r\n', '\n').strip()
        if 'include' in change:
            sec['include'] = bool(change['include'])
        if sec.get('custom') and change.get('title'):
            sec['title'] = change['title'].strip()
    _touch(draft, actor)
    return draft


def add_section(store: dict, rid: str, actor: str, title: str, narrative: str, after: str = None) -> dict:
    draft = _draft(store, rid)
    key = f"custom-{sum(1 for s in draft['sections'] if s.get('custom')) + 1}"
    sec = section(key, title.strip() or 'Commentary', narrative.strip())
    sec.update({'custom': True, 'auto_narrative': ''})
    keys = [s['key'] for s in draft['sections']]
    at = keys.index(after) + 1 if after in keys else max(len(keys) - 1, 0)
    draft['sections'].insert(at, sec)
    _touch(draft, actor)
    return draft


def remove_section(store: dict, rid: str, actor: str, key: str) -> dict:
    draft = _draft(store, rid)
    draft['sections'] = [s for s in draft['sections'] if not (s['key'] == key and s.get('custom'))]
    _touch(draft, actor)
    return draft


def reset_narrative(store: dict, rid: str, actor: str, key: str) -> dict:
    draft = _draft(store, rid)
    for sec in draft['sections']:
        if sec['key'] == key and not sec.get('custom'):
            sec['narrative'] = sec['auto_narrative']
    _touch(draft, actor)
    return draft


def issue(store: dict, rid: str, actor: str, today: dt.date, out_dir: Path, override: str = '') -> dict:
    """Render the final PDF, version it and record the publication."""
    from .pdf import render
    draft = _draft(store, rid)
    if draft.get('doc'):
        snap = MW.snapshot(store)
        cert = MW.model(draft['doc'], snap)['cert']
        if not cert['ok'] and not override.strip():
            raise ValueError('Control assertions are failing (HOLD · CONTROLS FAILING). Fix them, or give an '
                             'override reason to issue with the HOLD certification.')
        draft['zacks'] = copy.deepcopy(snap)  # freeze the screen data with the issued version
        draft['period_label'] = MW.label(draft['doc'])
        draft['certification'] = cert['label']
        draft['override'] = override.strip() or None
        if override.strip():
            _audit(store, actor, rid, f'issued with failing controls: {override.strip()}')
    draft['version'] = draft.get('version', 0) + 1
    draft.update({'status': 'Issued', 'issued': dt.datetime.now().isoformat(timespec='seconds'),
                  'issued_by': actor})
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{draft['id']}-v{draft['version']}.pdf"
    render(draft, out_dir / name, final=True)
    draft['files'].append({'version': draft['version'], 'file': name, 'issued': draft['issued'], 'by': actor})
    _record_publication(store, draft, today, actor)
    _audit(store, actor, rid, f"issued v{draft['version']}")
    return draft


def reopen(store: dict, rid: str, actor: str) -> dict:
    draft = store['reports'][rid]
    draft['status'] = 'Draft'
    _touch(draft, actor)
    _audit(store, actor, rid, 'reopened for revision')
    return draft


def _record_publication(store, draft, today, actor):
    name = TYPES[draft['type']]['publication']
    rows = store.setdefault('publications', [])
    cycle = TYPES[draft['type']]['cycle']
    nxt = today + dt.timedelta(days=7) if cycle == RV.WEEKLY else RV.period(
        cycle, dt.date.fromisoformat(draft['period_end']) + dt.timedelta(days=1))[3]
    values = {'latest_issue': f"{draft['period_label']} (v{draft['version']})",
              'last_published': today.isoformat(), 'next_due': nxt.isoformat(), 'status': 'Published'}
    row = next((r for r in rows if r and str(r.get('publication', '')).lower() == name.lower()), None)
    if row is None:
        free = next((i for i, r in enumerate(rows) if not r), None)
        if free is None:
            return
        rows[free] = row = {'publication': name, 'owner': 'Publication Division'}
    for k, v in values.items():
        if row.get(k) != v:
            store['audit'].append({'ts': dt.datetime.now().isoformat(timespec='seconds'), 'actor': actor,
                                   'action': 'set', 'table': 'publications', 'record': name, 'field': k,
                                   'old': row.get(k), 'new': v})
            row[k] = v


# =========================================================================== MWIR document

def _prior_mwir(store, start: dt.date):
    """The most recent earlier MWIR document, to carry forward."""
    prior = [r for r in store['reports'].values() if r.get('type') == 'mwir' and r.get('doc')
             and r['period_start'] < start.isoformat()]
    return max(prior, key=lambda r: r['period_start'])['doc'] if prior else None


def mwir_save(store: dict, rid: str, actor: str, form) -> dict:
    draft = _draft(store, rid)
    MW.apply_form(draft['doc'], form)
    draft['period_label'] = MW.label(draft['doc'])
    _touch(draft, actor)
    return draft


def mwir_import(store: dict, rid: str, actor: str, text: str, filename: str = '') -> tuple:
    draft = _draft(store, rid)
    msg, ok = MW.import_csv(store, draft['doc'], text)
    draft['period_label'] = MW.label(draft['doc'])
    _touch(draft, actor)
    _audit(store, actor, rid, f'holdings loaded from {filename or "CSV"}')
    return msg, ok


def mwir_import_json(store: dict, rid: str, actor: str, text: str) -> dict:
    draft = _draft(store, rid)
    draft['doc'] = MW.import_json(text)
    draft['period_label'] = MW.label(draft['doc'])
    _touch(draft, actor)
    _audit(store, actor, rid, 'document imported from the browser builder')
    return draft


def mwir_fill_baseline(store: dict, rid: str, actor: str) -> int:
    draft = _draft(store, rid)
    n = MW.fill_baseline(store, draft['doc'])
    _touch(draft, actor)
    return n


def mwir_add_events(store: dict, rid: str, actor: str) -> int:
    draft = _draft(store, rid)
    have = MW.lines(draft['doc'].get('events'))
    new = [e for e in MW.upcoming_events(store, draft['doc'])
           if not any(e.split('|')[1].strip() in h for h in have)]
    draft['doc']['events'] = '\n'.join(have + new)
    _touch(draft, actor)
    return len(new)


def _draft(store, rid):
    draft = store['reports'].get(rid)
    if draft is None:
        raise ValueError(f'No report {rid}')
    if draft['status'] != 'Draft':
        raise ValueError('This report is issued. Reopen it to revise and re-issue a new version.')
    return draft


def _touch(draft, actor):
    draft['updated'] = dt.datetime.now().isoformat(timespec='seconds')
    draft['updated_by'] = actor


def _audit(store, actor, rid, what):
    store['audit'].append({'ts': dt.datetime.now().isoformat(timespec='seconds'), 'actor': actor,
                           'action': 'report', 'table': 'reports', 'record': rid, 'field': what,
                           'old': None, 'new': None})
