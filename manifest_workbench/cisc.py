"""CISC-001 Chief Investment Steward Console.

Formula port of 00 CISC Dashboard, 01 Dashboard Controls, 02 Decision Center and
99 Dashboard Data. Research Intelligence (03) and Committee Operations (04) are
operating inputs that feed these panels.
"""

from __future__ import annotations

import datetime as dt

from .engine import as_date, blank, isin, num, same

MISSING = 'No entry loaded'


# --------------------------------------------------------------------------- Excel TEXT()

def text_date(value, fmt):
    d = as_date(value)
    if d is None:
        return ''
    if fmt == 'm/d':
        return f'{d.month}/{d.day}'
    if fmt == 'm/d/yyyy':
        return f'{d.month}/{d.day}/{d.year}'
    if fmt == 'dddd, mmm d, yyyy':
        return f"{d.strftime('%A')}, {d.strftime('%b')} {d.day}, {d.year}"
    raise ValueError(fmt)


def text_pct(value, places=0):
    return f'{(num(value) or 0) * 100:.{places}f}%'


def excel_str(value):
    """Value as Excel concatenates it (&)."""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class CISC:
    def __init__(self, wb, pew=None):
        self.wb = wb
        self.store = wb.store
        self.controls = self._controls()
        self.data = self._dashboard_data()
        self.decision = self._decision_center()
        self.console = self._console()

    # ------------------------------------------------------------------ 01 Dashboard Controls

    def _controls(self):
        c = dict(self.store.get('controls', {}))
        comps = []
        for src in self.store.get('composite', []):
            r = dict(src)
            r['contribution'] = (num(r.get('score')) or 0) * (num(r.get('weight')) or 0)    # D
            comps.append(r)
        score = sum(r['contribution'] for r in comps)                                       # D24 / B27
        c.update({'components': comps,
                  'weight_total': sum(num(r.get('weight')) or 0 for r in comps),            # C24
                  'composite_score': score,
                  'weekly_change': score - (num(c.get('previous_week_score')) or 0)})       # B28
        if score >= 0.10:                                                                   # B29
            c['posture'] = 'MAINTAIN STRATEGIC ALLOCATION'
        elif score > -0.10:
            c['posture'] = 'HOLD / MONITOR'
        elif score > -0.35:
            c['posture'] = 'DEFENSIVE TILT'
        else:
            c['posture'] = 'REDUCE RISK'
        if score >= 0.50:                                                                   # B30 / B31
            c['compass_bias'], c['classification'] = 'OPPORTUNISTIC', 'GREEN / STRONG ALIGNMENT'
        elif score >= 0.10:
            c['compass_bias'], c['classification'] = 'BALANCED', 'GREEN / POSITIVE ALIGNMENT'
        elif score > -0.10:
            c['compass_bias'], c['classification'] = 'DISCIPLINED', 'YELLOW / NEUTRAL'
        elif score > -0.35:
            c['compass_bias'], c['classification'] = 'DEFENSIVE', 'ORANGE / CAUTION'
        else:
            c['compass_bias'], c['classification'] = 'CAPITAL PRESERVATION', 'RED / RISK REDUCTION'
        return c

    # ------------------------------------------------------------------ 99 Dashboard Data

    def _dashboard_data(self):
        port = self.wb.portfolio
        missing = sum(1 for r in port if blank(r.get('actual_weight')))                     # B61
        breaches = sum(1 for r in port if r['band_status'] in ('Below band', 'Above band'))  # B62
        actual_total = sum(num(r.get('actual_weight')) or 0 for r in port)                  # B63
        live = missing == 0
        holdings = []
        for pos, r in enumerate(port):
            actual = num(r.get('actual_weight'))
            target = num(r.get('target_weight')) or 0
            h = {'source_row': 5 + pos, 'symbol': r.get('symbol'), 'security': r.get('security'),
                 'sleeve': r.get('sleeve'), 'target': target,
                 'actual': 0 if actual is None else actual, '_actual_blank': actual is None,
                 'role': r.get('role'), 'conviction': r.get('conviction_tier'),
                 'lower': r['lower_band'], 'upper': r['upper_band'],
                 'band_status': r['band_status'], 'action': r['rebalancing_action']}
            h['ranking_weight'] = h['actual'] if live else target                           # G
            if actual is None or not (actual < h['lower'] or actual > h['upper']):          # O
                h['alert_score'] = 0
            else:
                h['alert_score'] = abs(actual - target)
            holdings.append(h)
        _rank(holdings, 'ranking_weight', 'rank')                                           # H
        _rank(holdings, 'alert_score', 'alert_rank', skip_zero=True)                        # P
        by_rank = {h['rank']: h for h in holdings}
        by_alert = {h['alert_rank']: h for h in holdings if h['alert_rank'] != ''}
        top10 = []
        for n in range(1, 11):                                                              # R2:W11
            h = by_rank.get(n)
            top10.append({'rank': n, 'symbol': h['symbol'] if h else '',
                          'security': h['security'] if h else '',
                          'weight': h['ranking_weight'] if h else '', 'role': h['role'] if h else '',
                          'conviction': h['conviction'] if h else ''})
        alerts = []
        for n in range(1, 6):                                                               # R15:X19
            h = by_alert.get(n)
            if h is None:
                alerts.append({'rank': n, 'symbol': '', 'actual': '', 'target': '', 'variance': '',
                               'band_status': '', 'action': ''})
            else:
                alerts.append({'rank': n, 'symbol': h['symbol'], 'actual': h['actual'],
                               'target': h['target'], 'variance': h['actual'] - h['target'],
                               'band_status': h['band_status'], 'action': h['action']})
        sleeves = []
        for s in self.wb.sleeve_summary():                                                  # A2:D9
            actual = sum(num(r.get('actual_weight')) or 0 for r in port
                         if same(r.get('sleeve'), s['sleeve'])) if live else 0
            sleeves.append({'sleeve': s['sleeve'], 'target': s['target'], 'actual': actual,
                            'variance': actual - s['target']})

        def decision_required(table, field='status'):
            return sum(1 for r in self.store.get(table, []) if same(r.get(field), 'Decision Required'))

        research = (decision_required('intel-review') + decision_required('intel-merrill')     # B66
                    + decision_required('intel-thesis')
                    + sum(1 for r in port if same(r.get('research_status'), 'Decision Required')))
        actions = self.store.get('actions', [])
        return {
            'sleeves': sleeves, 'holdings': holdings, 'top10': top10, 'alerts': alerts,
            'missing_actual': missing, 'band_breaches': breaches, 'actual_total': actual_total,
            'completeness': (47 - missing) / 47,                                            # B64
            'ranking_basis': 'Actual Weight' if live else 'Target Weight',                  # B65
            'research_decisions': research,
            'open_actions': sum(1 for r in actions if isin(r.get('status'),                 # B67
                                                           ('Open', 'In Progress', 'Planned'))),
            'committee_actions': sum(1 for r in actions if same(r.get('committee_decision'), 'Yes')  # B68
                                     and isin(r.get('status'), ('Open', 'In Progress'))),
        }

    # ------------------------------------------------------------------ 02 Decision Center

    def _decision_center(self):
        d = self.data
        manual = sum(1 for r in self.store.get('decisions', [])                             # B11
                     if same(r.get('committee_decision'), 'Yes')
                     and isin(r.get('status'), ('Open', 'In Review')))
        total = d['band_breaches'] + d['research_decisions'] + manual                       # B13
        if d['missing_actual'] > 0:                                                         # B6
            state = 'DATA UPDATE REQUIRED'
        elif total > 0:
            state = 'COMMITTEE ACTION REQUIRED'
        else:
            state = 'NO COMMITTEE ACTION REQUIRED'
        meeting = {'COMMITTEE ACTION REQUIRED': 'CONVENE COMMITTEE',                         # E6
                   'DATA UPDATE REQUIRED': 'DEFER — COMPLETE DATA'}.get(state, 'NO MEETING REQUIRED')
        if d['missing_actual'] > 0:                                                         # B14
            priority = 'Load current actual portfolio weights'
        elif d['band_breaches'] > 0:
            priority = 'Review allocation-band exceptions'
        elif d['research_decisions'] > 0:
            priority = 'Resolve research or conviction decisions'
        elif manual > 0:
            priority = 'Resolve manual committee decisions'
        else:
            priority = 'Continue disciplined monitoring'
        m, b9, b10 = d['missing_actual'], d['band_breaches'], d['research_decisions']
        queue = [
            {'id': 'DC-SYS-001', 'category': 'Data Integrity',
             'trigger': f'{m} actual weights missing' if m > 0 else 'Actual weights complete',
             'decision': 'Data update required' if m > 0 else 'No data decision',
             'action': 'Load actual weights in Certified Allocation column I',
             'authority': 'Portfolio Operations', 'status': 'ACTION REQUIRED' if m > 0 else 'READY'},
            {'id': 'DC-SYS-002', 'category': 'Allocation', 'trigger': f'{b9} allocation-band exceptions',
             'decision': 'Committee allocation decision' if b9 > 0 else 'No allocation decision',
             'action': 'Review each band exception; add/trim only after committee review',
             'authority': 'Stewardship Committee',
             'status': 'PENDING DATA' if m > 0 else ('DECISION REQUIRED' if b9 > 0 else 'NO DECISION')},
            {'id': 'DC-SYS-003', 'category': 'Research', 'trigger': f'{b10} research / conviction decisions',
             'decision': 'Committee research decision' if b10 > 0 else 'No research decision',
             'action': 'Resolve items marked Decision Required',
             'authority': 'Research / Stewardship Committee',
             'status': 'DECISION REQUIRED' if b10 > 0 else 'NO DECISION'},
            {'id': 'DC-SYS-004', 'category': 'Manual Decisions',
             'trigger': f'{manual} manual committee decisions',
             'decision': 'Committee decision' if manual > 0 else 'No manual decision',
             'action': 'Resolve open manual committee decisions', 'authority': 'Stewardship Committee',
             'status': 'DECISION REQUIRED' if manual > 0 else 'NO DECISION'},
            {'id': 'DC-SYS-005', 'category': 'Publication', 'trigger': 'MWIR scheduled',
             'decision': 'No committee decision unless recommendation changes',
             'action': 'Complete institutional publication workflow', 'authority': 'Publication Division',
             'status': 'Operational'},
        ]
        return {'state': state, 'meeting': meeting, 'completeness': d['completeness'],
                'missing_actual': m, 'weight_basis': d['ranking_basis'], 'allocation_decisions': b9,
                'research_decisions': b10, 'manual_decisions': manual,
                'open_actions': d['open_actions'], 'total_decisions': total, 'priority': priority,
                'queue': queue}

    # ------------------------------------------------------------------ 00 CISC Dashboard

    def _console(self):
        c, d, dc = self.controls, self.data, self.decision
        st = self.store
        state = dc['state']
        recommendation = ('REVIEW IDENTIFIED DECISIONS' if state == 'COMMITTEE ACTION REQUIRED'
                          else 'MAINTAIN PORTFOLIO CONSTRUCTION')
        if state == 'DATA UPDATE REQUIRED':
            detail = 'Actual weights must be loaded before live rebalancing review.'
            summary = ('Complete the data update before convening the committee. No allocation '
                       'conclusion should be drawn from incomplete actual weights.')
        elif state == 'COMMITTEE ACTION REQUIRED':
            detail = 'Committee review required. No automatic trades are authorized.'
            summary = ('Review the identified decision queue. Committee review must precede any '
                       'implementation.')
        else:
            detail = 'No structural changes recommended. Continue disciplined monitoring.'
            summary = ('No structural portfolio or research decision is required. Continue '
                       'monitoring and complete normal operating work.')
        if d['missing_actual'] > 0:
            alert_note = (f"{d['missing_actual']} actual weights are not loaded. "
                          'Allocation alerts are not yet live.')
        elif d['band_breaches'] == 0:
            alert_note = 'All positions are within certified bands.'
        else:
            alert_note = f"Committee review required for {d['band_breaches']} allocation-band exceptions."

        def rows(table):
            return st.get(table, [])

        def slot(table, i):
            r = rows(table)
            return r[i] if i < len(r) else {}

        research = {
            'review': [_entry(slot('intel-review', i), 'symbol',
                              lambda r: f"{excel_str(r.get('symbol'))} — {excel_str(r.get('reason'))}")
                       for i in range(3)],
            'events': [_entry(slot('intel-events', i), 'symbol',
                              lambda r: f"{text_date(r.get('date'), 'm/d')}  {excel_str(r.get('symbol'))}"
                                        f" — {excel_str(r.get('event'))}") for i in range(4)],
            'zacks': [_entry(slot('intel-zacks', i), 'symbol',
                             lambda r: f"{excel_str(r.get('symbol'))}  #{excel_str(r.get('prior_rank'))}"
                                       f" → #{excel_str(r.get('current_rank'))}") for i in range(4)],
            'merrill': [_entry(slot('intel-merrill', i), 'symbol',
                               lambda r: f"{excel_str(r.get('symbol'))} — {excel_str(r.get('rating_action'))}")
                        for i in range(4)],
            'miar': [_entry(slot('intel-miar', i), 'symbol',
                            lambda r: f"{excel_str(r.get('symbol'))} — {excel_str(r.get('review_type'))}"
                                      f" / {excel_str(r.get('status'))}") for i in range(3)],
            'thesis': [_entry(slot('intel-thesis', i), 'symbol',
                              lambda r: f"{excel_str(r.get('symbol'))} — {excel_str(r.get('reason'))}")
                       for i in range(3)],
        }
        pub = slot('publications', 0)
        calendar = []
        for i in range(4):
            r = slot('calendar', i)
            if blank(r.get('event')):
                calendar.append('No event loaded')
            else:
                when = 'TBD' if blank(r.get('date')) else text_date(r.get('date'), 'm/d')
                calendar.append(f"{when} — {excel_str(r.get('event'))}")
        certs = [f"{excel_str(slot('certifications', i).get('record'))} — "
                 f"{excel_str(slot('certifications', i).get('version'))} / "
                 f"{excel_str(slot('certifications', i).get('status'))}" for i in range(4)]
        prios = sum(1 for r in rows('priorities') if isin(r.get('status'), ('Open', 'Planned')))
        questions = sum(1 for r in rows('questions') if isin(r.get('status'), ('Open', 'Pending Data')))
        projects = sum(1 for r in rows('projects') if isin(r.get('status'), ('Planned', 'In Progress')))
        return {
            'report_date': c.get('report_date'), 'recommendation': recommendation,
            'posture': c['posture'], 'detail': detail, 'score': c['composite_score'],
            'trend': c['weekly_change'], 'confidence': c.get('confidence'),
            'compass': f"DISCIPLINED   •   BALANCED   •   {c['compass_bias']}",
            'previous_week': c.get('previous_week_score'),
            'next_review': f"NEXT REVIEW: {text_date(c.get('next_review'), 'dddd, mmm d, yyyy')}",
            'classification': c['classification'],
            'top10': d['top10'], 'alerts': [a if a['symbol'] not in ('', 0) else
                                            {k: '' for k in a} for a in d['alerts']],
            'alert_note': alert_note,
            'ranking_basis': f"RANKING BASIS: {d['ranking_basis']}",
            'completeness_line': f"DATA COMPLETENESS: {text_pct(d['completeness'])}   |   "
                                 f"ACTUAL TOTAL: {text_pct(d['actual_total'], 2)}",
            'ranking_note': ('Actual weights incomplete — displaying certified target-weight ranking.'
                             if d['missing_actual'] > 0 else
                             'Actual weights complete — displaying live position ranking.'),
            'research': research,
            'mwir': excel_str(pub.get('publication')) if not blank(pub.get('publication')) else 0,
            'mwir_status': f"STATUS: {excel_str(pub.get('status'))}",
            'mwir_last': f"LAST PUBLISHED: {text_date(pub.get('last_published'), 'm/d/yyyy')}",
            'mwir_next': f"NEXT DUE: {text_date(pub.get('next_due'), 'm/d/yyyy')}",
            'calendar': calendar, 'certifications': certs,
            'notebook': [f'{prios} priorities', f'{questions} committee questions',
                         f'{projects} long-term projects'],
            'pending': [('Open / Planned Actions', d['open_actions']),
                        ('Research Decisions', d['research_decisions']),
                        ('Allocation Decisions', d['band_breaches']),
                        ('Committee Decisions', dc['total_decisions']),
                        ('Actual Weights Missing', d['missing_actual']),
                        ('Data Completeness', d['completeness']),
                        ('Decision State', state)],
            'decision_state': state,
            'tiles': [f"PRIMARY REQUIRED ACTION\n{dc['priority']}",
                      f"COMMITTEE DECISIONS\n{dc['total_decisions']}",
                      f"MEETING STATUS\n{dc['meeting']}",
                      f"DATA COMPLETENESS\n{text_pct(dc['completeness'])}",
                      'TRADING\nPROHIBITED'],
            'summary': summary,
        }


def _entry(row, key_field, render):
    return MISSING if blank(row.get(key_field)) else render(row)


def _rank(rows, field, out, skip_zero=False):
    """RANK(value, range, 0) + COUNTIF(range_to_here, value) - 1: descending, ties by order."""
    values = [r[field] for r in rows]
    seen = {}
    for r in rows:
        v = r[field]
        seen[v] = seen.get(v, 0) + 1
        if skip_zero and v == 0:
            r[out] = ''
            continue
        r[out] = 1 + sum(1 for x in values if x > v) + seen[v] - 1


def as_datetime(value):
    d = as_date(value)
    return dt.datetime(d.year, d.month, d.day) if d else None
