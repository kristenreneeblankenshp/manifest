"""Calculation engine.

A faithful port of the worksheet formulas of the Manifest Workbench v0.4 for the
certified MFPDF, PEW-004 / PEW-005 and the MOPS-003 research command chain
(RCC-001 through RCC-004). Each computed field carries the column letter of the
formula it reproduces.

Blank handling follows the intent of the workbook: a lookup of an empty cell
yields a blank (not zero), so "missing" data is reported as missing.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Iterable, Optional

from . import lists as L

CERTIFIED = 'Certified Portfolio Holding'
CLOSED_EVIDENCE = ('Closed — No Action', 'Closed — Incorporated')
CLOSED_STAGES = ('Rejected', 'Closed', 'Removed')
REFER_PEW004 = 'Yes — Refer to PEW-004'
PASS_GATE = 'PASS — STAGE GATE'

# PEW-004 base Manifest scoring weights and close-decision controls.
PEW004_WEIGHTS = {
    'mics': 0.25,
    'miar_integrity': 0.20,
    'empirical_rank': 0.20,
    'role_fit': 0.15,
    'valuation': 0.10,
    'diversification': 0.10,
}
ZACKS_OVERLAY_WEIGHT = 0.80
ZACKS_ELECTION_MARKET_CAP = 50  # $B
ZACKS_OVERLAY_POINTS = {1: 100, 2: 85, 3: 60, 4: 25}

# Stage sets used by the RCC-004 stage gate (24 Candidate Pipeline, column Z).
STAGES_NEED_MASR = ('MIAR Review', 'Eligibility Review', 'Candidate Comparison', 'Committee Review',
                    'Approved for MASR', 'Referred to PEW-004', 'On Watch', 'Rejected', 'Closed',
                    'Removed')
STAGES_NEED_ELIGIBILITY = ('Eligibility Review', 'Candidate Comparison', 'Committee Review',
                           'Approved for MASR', 'Referred to PEW-004', 'On Watch')
STAGES_NEED_EVIDENCE = ('Candidate Comparison', 'Committee Review', 'Approved for MASR',
                        'Referred to PEW-004', 'On Watch')
STAGES_NEED_DISPOSITION = ('Approved for MASR', 'Referred to PEW-004', 'On Watch', 'Rejected',
                           'Closed', 'Removed')

GATE_TO_CONTROL = {
    'FAIL — DUPLICATE ID': 'DUPLICATE CANDIDATE ID',
    'FAIL — INCOMPLETE': 'INCOMPLETE',
    'FAIL — MASR RECORD REQUIRED': 'MASR RECORD REQUIRED',
    'FAIL — ELIGIBILITY': 'ELIGIBILITY BLOCK',
    'FAIL — EVIDENCE': 'EVIDENCE REQUIRED',
    'FAIL — MIAR GATE': 'MIAR GATE BLOCK',
    'FAIL — COMMITTEE DISPOSITION': 'COMMITTEE DECISION REQUIRED',
    'FAIL — PEW REFERRAL': 'PEW REFERRAL INCOMPLETE',
}

# Fields whose absence makes a record INCOMPLETE (per each sheet's completeness formula).
REQUIRED = {
    'evidence': ('evidence_id', 'date_received', 'evidence_date', 'record_type', 'subject',
                 'activity_type', 'category', 'materiality', 'direction', 'reliability',
                 'source_type', 'publisher', 'source_ref', 'summary', 'thesis_sensitivity',
                 'reviewer', 'due_date', 'status', 'verified', 'miar_action', 'thesis_impact',
                 'conviction_rec', 'candidate_replacement', 'pew_referral', 'disposition'),
    'miar': ('miar_id', 'integrity_score', 'mics_score', 'record_status', 'research_owner',
             'review_cadence', 'last_full_review'),
    'review': ('review_date', 'ticker', 'review_type', 'reviewer', 'evidence_ids',
               'proposed_status', 'proposed_integrity', 'proposed_mics', 'thesis_assessment',
               'conviction_rec', 'findings', 'required_miar_action', 'certification_rec',
               'source_ref'),
    'masr': ('masr_id', 'record_class', 'registry_status', 'admission_basis', 'sleeve', 'role',
             'security_type'),
    'pipeline': ('intake_date', 'ticker', 'candidate_type', 'source', 'stage', 'owner', 'due_date'),
}
TICKERLESS_RECORD_TYPES = ('Portfolio-Level', 'Market / Macro', 'Other')


def missing_fields(table: str, row: dict) -> list:
    """Keys of the required fields that are blank on a record."""
    out = [k for k in REQUIRED.get(table, ()) if blank(row.get(k))]
    if table == 'evidence' and blank(row.get('ticker')) and \
            not isin(row.get('record_type'), TICKERLESS_RECORD_TYPES):
        out.append('ticker')
    return out


CADENCE_DAYS = {
    'Quarterly — 90 Days': 90,
    'Semiannual — 180 Days': 180,
    'Annual — 365 Days': 365,
    'Event-Driven': 0,
}


# --------------------------------------------------------------------------- helpers

def blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == '')


def fold(v):
    """Excel text comparison is case-insensitive."""
    return v.strip().casefold() if isinstance(v, str) else v


def same(a, b) -> bool:
    if blank(a) or blank(b):
        return blank(a) and blank(b)
    return fold(a) == fold(b)


def isin(v, options: Iterable) -> bool:
    return any(same(v, o) for o in options)


def as_date(v) -> Optional[dt.date]:
    if blank(v):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


def num(v):
    if blank(v):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def nz(v):
    """Excel returns "" rather than a blank from these lookups."""
    return '' if v is None else v


class Index:
    """Case-insensitive MATCH/COUNTIF helper over a list of rows."""

    def __init__(self, rows, key):
        self.rows = rows
        self.key = key
        self.counts = Counter(fold(r.get(key)) for r in rows if not blank(r.get(key)))

    def first(self, value):
        if blank(value):
            return None
        for r in self.rows:
            if same(r.get(self.key), value):
                return r
        return None

    def count(self, value) -> int:
        return 0 if blank(value) else self.counts.get(fold(value), 0)

    def where(self, value):
        return [r for r in self.rows if not blank(value) and same(r.get(self.key), value)]


def lookup(index: Index, value, field):
    """=IF(key="","",IFERROR(INDEX(field, MATCH(key, keys, 0)),""))"""
    if blank(value):
        return ''
    row = index.first(value)
    if row is None:
        return ''
    return nz(row.get(field))


# --------------------------------------------------------------------------- workbench

class Workbench:
    """Computed view of a data store as of a given date (the workbook's TODAY())."""

    def __init__(self, store: dict, today: Optional[dt.date] = None):
        self.store = store
        self.today = today or dt.date.today()
        self.portfolio = self._portfolio()
        self.conviction = self._conviction()
        self.pew004 = self._pew004()
        self.evidence = self._evidence()
        self.miar = self._miar()
        self.review = self._reviews()
        self.masr = self._masr()
        self.pipeline = self._pipeline()

    def table(self, name):
        return getattr(self, name)

    # ------------------------------------------------------------------ MFPDF

    def _portfolio(self):
        rows = []
        for src in self.store['portfolio']:
            r = dict(src)
            f = num(r.get('target_weight')) or 0.0
            r['lower_band'] = max(0.01, f * 0.75)                                    # G
            r['upper_band'] = min(0.04, f * 1.25)                                    # H
            i = num(r.get('actual_weight'))
            r['variance'] = '' if i is None else i - f                               # J
            if i is None:                                                            # K / L
                r['band_status'], r['rebalancing_action'] = 'Not entered', 'Enter actual weight'
            elif i < r['lower_band']:
                r['band_status'], r['rebalancing_action'] = 'Below band', 'Review / Add'
            elif i > r['upper_band']:
                r['band_status'], r['rebalancing_action'] = 'Above band', 'Review / Trim'
            else:
                r['band_status'], r['rebalancing_action'] = 'Within band', 'No action'
            rows.append(r)
        self.portfolio_index = Index(rows, 'symbol')
        return rows

    def portfolio_totals(self):
        target = sum(num(r.get('target_weight')) or 0 for r in self.portfolio)
        actual = sum(num(r.get('actual_weight')) or 0 for r in self.portfolio)
        loaded = sum(1 for r in self.portfolio if not blank(r.get('actual_weight')))
        return {
            'target_total': target,
            'actual_total': actual,
            'variance_total': actual - target,
            'certification': 'Certified 100.00%' if abs(target - 1.0) < 0.000001 else 'ERROR',
            'actual_loaded': loaded,
            'positions': len(self.portfolio),
            'actual_state': 'PASS' if loaded == len(self.portfolio) else 'INPUT REQUIRED',
        }

    def sleeve_summary(self):
        out = []
        for sleeve in L.SLEEVES:
            members = [r for r in self.portfolio if same(r.get('sleeve'), sleeve)]
            out.append({
                'sleeve': sleeve,
                'positions': len(members),
                'equities': sum(1 for r in members if same(r.get('security_type'), 'Equity')),
                'etfs': sum(1 for r in members if same(r.get('security_type'), 'ETF')),
                'target': sum(num(r.get('target_weight')) or 0 for r in members),
            })
        return out

    # ------------------------------------------------------------------ PEW-005

    def _conviction(self):
        rows = []
        for pos, alloc in enumerate(self.portfolio):
            src = self.store['conviction'][pos] if pos < len(self.store['conviction']) else {}
            r = dict(src)
            r.update({
                'sleeve': alloc.get('sleeve'), 'symbol': alloc.get('symbol'),
                'security': alloc.get('security'), 'security_type': alloc.get('security_type'),
                'certified_weight': alloc.get('target_weight'),
                'current_conviction': nz(alloc.get('conviction_tier')),
                'research_status': nz(alloc.get('research_status')),
            })
            g = r.get('proposed_conviction')
            h = r['current_conviction'] if blank(g) else g
            r['effective_conviction'] = h                                            # H
            r['conviction_score'] = {'Tier 1 — Anchor': 3, 'Tier 2 — Core': 2,       # I
                                     'Tier 3 — Opportunistic': 1}.get(h, 0)
            j, k = r.get('thesis_status'), r['research_status']
            if same(h, 'Unassigned'):                                                # O
                r['decision_state'] = 'ASSIGN CONVICTION'
            elif same(j, 'Impaired'):
                r['decision_state'] = 'REDUCE / REPLACE REVIEW'
            elif not blank(g):
                r['decision_state'] = 'COMMITTEE REVIEW'
            elif isin(k, ('Update Due', 'Review Due', 'Decision Required')):
                r['decision_state'] = 'RESEARCH REVIEW'
            else:
                r['decision_state'] = 'NO CHANGE'
            rows.append(r)
        self.conviction_index = Index(rows, 'symbol')
        return rows

    # ------------------------------------------------------------------ PEW-004

    def _pew004(self):
        rows = []
        for src in self.store['pew004']:
            r = dict(src)
            scores = [num(r.get(k)) for k in PEW004_WEIGHTS]
            complete = all(s is not None for s in scores)
            q = sum(s * w for s, w in zip(scores, PEW004_WEIGHTS.values())) if complete else ''
            r['base_score'] = q                                                      # Q
            j = num(r.get('zacks_rank'))
            r['zacks_overlay'] = '' if j is None else ZACKS_OVERLAY_POINTS.get(int(j), 0)  # S
            if q == '':                                                              # T
                t = ''
            elif same(r.get('close_decision'), 'Yes'):
                t = '#VALUE!' if r['zacks_overlay'] == '' else \
                    q * (1 - ZACKS_OVERLAY_WEIGHT) + r['zacks_overlay'] * ZACKS_OVERLAY_WEIGHT
            else:
                t = q
            r['final_score'] = t
            h = num(r.get('market_cap'))
            if blank(r.get('symbol')):                                               # U
                u = ''
            elif h is None or blank(r.get('merrill_status')) or j is None or not complete:
                u = 'DATA MISSING'
            elif same(r.get('candidate_type'), 'Candidate') and h < ZACKS_ELECTION_MARKET_CAP:
                u = 'MARKET CAP EXCEPTION'
            elif same(r.get('merrill_status'), 'No Rating'):
                u = 'MERRILL EXCEPTION'
            elif j >= 4:
                u = 'ZACKS EXCEPTION'
            else:
                u = 'ELIGIBLE'
            r['eligibility_gate'] = u
            if blank(r.get('symbol')):                                               # V
                v = ''
            elif q == '':
                v = 'COMPLETE SCORING'
            elif u != 'ELIGIBLE':
                v = 'DOCUMENT / COMMITTEE EXCEPTION'
            elif isinstance(t, str):
                v = t
            elif t >= 85:
                v = 'ADVANCE'
            elif t >= 75:
                v = 'RETAIN ON SHORT LIST'
            elif t >= 65:
                v = 'WATCH'
            else:
                v = 'REJECT / REPLACE'
            r['recommended_action'] = v
            w = r.get('committee_decision')
            if blank(r.get('symbol')):                                               # Y
                r['status'] = 'Open Slot'
            elif not blank(w) and not same(w, 'No Decision'):
                r['status'] = 'Decision Recorded'
            elif v == 'ADVANCE' or 'EXCEPTION' in v.upper():
                r['status'] = 'COMMITTEE DECISION REQUIRED'
            else:
                r['status'] = 'Under Review'
            rows.append(r)
        self.pew004_index = Index(rows, 'candidate_id')
        return rows

    # ------------------------------------------------------------------ RCC-002

    def _evidence(self):
        src_rows = self.store['evidence']
        ids = Index(src_rows, 'evidence_id')
        rows = []
        for src in src_rows:
            r = dict(src)
            e = r.get('ticker')
            if blank(e):                                                             # G
                r['sleeve'] = ''
            else:
                hit = self.portfolio_index.first(e)
                r['sleeve'] = hit['sleeve'] if hit else 'Candidate / Non-Holding'
            status = r.get('status')
            closed = isin(status, CLOSED_EVIDENCE)
            b, ab = as_date(r.get('date_received')), as_date(r.get('closed_date'))
            if blank(r.get('evidence_id')) or b is None:                             # AC
                r['days_open'] = ''
            elif closed and ab is not None:
                r['days_open'] = max(0, (ab - b).days)
            else:
                r['days_open'] = max(0, (self.today - b).days)
            inputs = [k for k in src if k != 'sleeve']
            if all(blank(r.get(k)) for k in inputs):                                 # AD
                ad = ''
            elif missing_fields('evidence', r):
                ad = 'INCOMPLETE'
            elif ids.count(r.get('evidence_id')) > 1:
                ad = 'DUPLICATE ID'
            else:
                ad = 'COMPLETE'
            r['completeness'] = ad
            u, x, z = r.get('verified'), r.get('conviction_rec'), r.get('pew_referral')
            s = as_date(r.get('due_date'))
            verified = isin(u, ('Yes', 'Exception Approved'))
            if blank(r.get('evidence_id')):                                          # AE
                ae = ''
            elif ad != 'COMPLETE':
                ae = ad
            elif same(r.get('record_type'), 'Certified Holding') and (
                    blank(e) or r['sleeve'] == 'Candidate / Non-Holding'):
                ae = 'HOLDING IDENTIFIER MISMATCH'
            elif isin(r.get('materiality'), ('Critical', 'High')) and (
                    same(u, 'No') or (same(r.get('reliability'), 'Unverified — Pending')
                                      and not same(u, 'Exception Approved'))):
                ae = 'VERIFY / ESCALATE'
            elif same(x, 'Unassigned'):
                ae = 'CONVICTION DECISION REQUIRED'
            elif s is not None and s < self.today and not closed:
                ae = 'OVERDUE'
            elif closed and blank(r.get('closed_date')):
                ae = 'CLOSE DATE REQUIRED'
            elif not closed and not blank(r.get('closed_date')):
                ae = 'STATUS / CLOSE DATE MISMATCH'
            elif not same(z, 'No') and not verified:
                ae = 'PEW REFERRAL BLOCKED'
            elif same(status, 'Awaiting Verification') and same(u, 'Yes'):
                ae = 'STATUS MISMATCH'
            elif closed:
                ae = 'CLOSED'
            else:
                ae = 'OPEN — ON TRACK'
            r['control_status'] = ae
            w = r.get('thesis_impact')
            if blank(r.get('evidence_id')):                                          # AF
                af = ''
            elif ad != 'COMPLETE':
                af = 'NOT ELIGIBLE'
            elif same(x, 'Unassigned'):
                af = 'NOT ELIGIBLE — CONVICTION UNASSIGNED'
            elif not verified:
                af = 'NOT ELIGIBLE — UNVERIFIED'
            elif (not same(r.get('miar_action'), 'None')
                  or (not same(w, 'None') and not same(w, 'Intact'))
                  or (not same(x, 'No Change') and not same(x, 'Not Applicable'))
                  or not same(r.get('candidate_replacement'), 'None')
                  or not same(z, 'No')):
                af = 'ELIGIBLE FOR ROUTING'
            else:
                af = 'NO REFERRAL REQUIRED'
            r['referral_eligibility'] = af
            rows.append(r)
        self.evidence_index = Index(rows, 'ticker')
        return rows

    def _evidence_counts(self, ticker):
        """(records, open records, open MIAR actions, open material-event reviews)"""
        recs = self.evidence_index.where(ticker)
        open_ = [r for r in recs if not isin(r.get('status'), CLOSED_EVIDENCE)]
        actions = [r for r in open_ if not blank(r.get('miar_action'))
                   and not same(r.get('miar_action'), 'None')]
        material = [r for r in open_ if same(r.get('miar_action'), 'Material Event Review')]
        return len(recs), len(open_), len(actions), len(material)

    # ------------------------------------------------------------------ RCC-003

    def _miar(self):
        review_index = Index(self.store['review'], 'ticker')
        ids = Index(self.store['miar'], 'miar_id')
        rows = []
        for pos, alloc in enumerate(self.portfolio):
            src = self.store['miar'][pos] if pos < len(self.store['miar']) else {}
            r = dict(src)
            b = alloc.get('symbol')
            r.update({
                'ticker': b, 'security': alloc.get('security'), 'sleeve': alloc.get('sleeve'),
                'security_type': alloc.get('security_type'), 'role': alloc.get('role'),
                'certified_weight': alloc.get('target_weight'),
                'mfpdf_research_status': nz(alloc.get('research_status')),
            })
            conv = self.conviction_index.first(b)
            r['effective_conviction'] = conv['effective_conviction'] if conv else 'Unassigned'  # I
            r['thesis_status'] = nz(conv.get('thesis_status')) if conv else ''                # J
            o = r.get('review_cadence')
            r['cadence_days'] = '' if blank(o) else CADENCE_DAYS.get(o, '')                 # P
            dates = [d for d in (as_date(r.get('last_full_review')),
                                 as_date(r.get('last_incremental'))) if d]
            s = max(dates) if dates else None
            r['latest_dossier_date'] = s or ''                                              # S
            p = r['cadence_days']
            t = s + dt.timedelta(days=p) if s and p not in ('', 0) else None
            r['next_review'] = t or ''                                                      # T
            r['review_log_entries'] = review_index.count(b)                                 # U
            v, w, x, y = self._evidence_counts(b)
            r['evidence_records'], r['open_evidence'] = v, w                                # V / W
            r['miar_actions_pending'], r['material_event_reviews'] = x, y                   # X / Y
            a, m = r.get('miar_id'), r.get('record_status')
            if y > 0:                                                                       # Z
                z = 'MATERIAL EVENT REVIEW'
            elif any(blank(r.get(k)) for k in ('miar_id', 'record_status', 'research_owner',
                                                'review_cadence')) or s is None:
                z = 'NOT INITIALIZED'
            elif isin(m, ('Suspended', 'Archived')):
                z = 'INACTIVE'
            elif same(o, 'Event-Driven'):
                z = 'CURRENT'
            elif t is None:
                z = 'NOT INITIALIZED'
            elif t < self.today:
                z = 'OVERDUE'
            elif (t - self.today).days <= 30:
                z = 'REVIEW DUE'
            elif (t - self.today).days <= 60:
                z = 'UPDATE DUE'
            else:
                z = 'CURRENT'
            r['research_freshness'] = z
            if missing_fields('miar', r):                                                   # AA
                aa = 'INCOMPLETE'
            elif ids.count(a) > 1:
                aa = 'DUPLICATE MIAR ID'
            else:
                aa = 'COMPLETE'
            r['dossier_completeness'] = aa
            if aa != 'COMPLETE':                                                            # AB
                ab = aa
            elif y > 0:
                ab = 'MATERIAL EVENT REVIEW'
            elif z in ('OVERDUE', 'REVIEW DUE'):
                ab = z
            elif x > 0:
                ab = 'MIAR ACTION PENDING'
            elif same(r['effective_conviction'], 'Unassigned') or blank(r['thesis_status']):
                ab = 'THESIS / CONVICTION SETUP'
            elif same(m, 'Draft'):
                ab = 'DRAFT — NOT CERTIFIED'
            elif same(m, 'Active') and (blank(r.get('certified_by'))
                                        or blank(r.get('certification_date'))):
                ab = 'CERTIFICATION REQUIRED'
            else:
                ab = 'CONTROL CLEAR'
            r['control_status'] = ab
            r['required_action'] = L.MIAR_REQUIRED_ACTION.get(ab, 'Review exception')      # AC
            if ab in ('MATERIAL EVENT REVIEW', 'MIAR ACTION PENDING', 'THESIS / CONVICTION SETUP'):
                r['rcc007_referral'] = 'REFER TO RCC-007'                                   # AD
            elif ab == 'CONTROL CLEAR':
                r['rcc007_referral'] = 'NO REFERRAL'
            else:
                r['rcc007_referral'] = 'HOLD PENDING MIAR UPDATE'
            rows.append(r)
        self.miar_index = Index(rows, 'ticker')
        return rows

    def _reviews(self):
        ids = Index(self.store['review'], 'review_id')
        certify = ('Certify Current', 'Certify with Exception')
        rows = []
        for src in self.store['review']:
            r = dict(src)
            c = r.get('ticker')
            hit = self.miar_index.first(c)
            r['security'] = '' if blank(c) else (hit['security'] if hit else 'TICKER NOT FOUND')  # D
            r['prior_status'] = lookup(self.miar_index, c, 'record_status')                 # H
            r['prior_integrity'] = lookup(self.miar_index, c, 'integrity_score')            # J
            r['prior_mics'] = lookup(self.miar_index, c, 'mics_score')                      # L
            rec = r.get('certification_rec')
            certifier = not blank(r.get('certified_by')) or not blank(r.get('certification_date'))
            if blank(r.get('review_id')):                                                   # U
                u = ''
            elif ids.count(r.get('review_id')) > 1:
                u = 'DUPLICATE REVIEW ID'
            elif missing_fields('review', r):
                u = 'INCOMPLETE'
            elif isin(rec, certify) and (blank(r.get('certified_by'))
                                         or blank(r.get('certification_date'))):
                u = 'CERTIFICATION REQUIRED'
            elif not isin(rec, certify) and certifier:
                u = 'CERTIFICATION MISMATCH'
            else:
                u = 'COMPLETE'
            r['control_status'] = u
            rows.append(r)
        return rows

    # ------------------------------------------------------------------ RCC-004

    def _masr(self):
        src_rows = []
        for src in self.store['masr']:
            r = dict(src)
            pos = r.get('_linked')
            if pos is not None and pos < len(self.portfolio):
                alloc = self.portfolio[pos]
                r.update({'ticker': alloc.get('symbol'), 'security': alloc.get('security'),
                          'sleeve': alloc.get('sleeve'), 'role': alloc.get('role'),
                          'security_type': alloc.get('security_type')})
            src_rows.append(r)
        ids = Index(src_rows, 'masr_id')
        tickers = Index(src_rows, 'ticker')
        pipe = Index(self.store['pipeline'], 'ticker')
        rows = []
        for r in src_rows:
            b = r.get('ticker')
            if blank(b):
                rows.append(r)
                continue
            r['certified_weight'] = lookup(self.portfolio_index, b, 'target_weight')        # J
            r['miar_id'] = lookup(self.miar_index, b, 'miar_id')                            # K
            r['miar_status'] = lookup(self.miar_index, b, 'record_status')                  # L
            r['research_freshness'] = lookup(self.miar_index, b, 'research_freshness')      # M
            r['integrity_score'] = lookup(self.miar_index, b, 'integrity_score')            # N
            r['mics_score'] = lookup(self.miar_index, b, 'mics_score')                      # O
            r['effective_conviction'] = lookup(self.miar_index, b, 'effective_conviction')  # P
            r['thesis_status'] = lookup(self.miar_index, b, 'thesis_status')                # Q
            total, open_, _, _ = self._evidence_counts(b)
            r['evidence_records'], r['open_evidence'] = total, open_                        # R / S

            a, d, e, f = r.get('masr_id'), r.get('record_class'), r.get('registry_status'), \
                r.get('admission_basis')
            k, l, m = r['miar_id'], r['miar_status'], r['research_freshness']
            n, o, w = r['integrity_score'], r['mics_score'], r.get('empirical_rank')
            t, u, v = num(r.get('market_cap')), num(r.get('zacks_rank')), r.get('merrill_status')
            certified = same(d, CERTIFIED)
            classification = ('record_class', 'registry_status', 'admission_basis', 'sleeve',
                              'role', 'security_type')
            sub50_election = same(f, 'Zacks Election') and (t is None or t < ZACKS_ELECTION_MARKET_CAP)
            zacks_45 = u in (4, 5)
            if certified:                                                                   # X
                x = 'CERTIFIED HOLDING'
            elif blank(a) or any(blank(r.get(key)) for key in classification):
                x = 'NOT ASSESSED'
            elif blank(k) or not same(l, 'Active') or isin(m, ('OVERDUE', 'MATERIAL EVENT REVIEW')) \
                    or blank(n) or blank(o) or blank(w):
                x = 'NOT ELIGIBLE'
            elif sub50_election or zacks_45 or isin(v, ('No Rating', 'Restricted / Unavailable')):
                x = 'ELIGIBLE WITH EXCEPTION'
            else:
                x = 'ELIGIBLE'
            r['eligibility_gate'] = x
            if blank(a):                                                                    # Y
                y = 'Canonical MASR ID required'
            elif not certified and (blank(k) or not same(l, 'Active') or not same(m, 'CURRENT')
                                    or blank(n) or blank(o) or blank(w)):
                y = 'Complete MIAR / scoring / empirical eligibility'
            elif sub50_election:
                y = 'Sub-$50B Zacks election exception'
            elif zacks_45:
                y = 'Zacks #4/#5 exception review'
            elif same(v, 'No Rating'):
                y = 'Merrill No Rating exception'
            elif same(v, 'Restricted / Unavailable'):
                y = 'Merrill restricted / unavailable exception'
            else:
                y = 'None'
            r['exception_requirement'] = y
            cands = pipe.where(b)
            r['pipeline_records'] = len(cands)                                              # Z
            r['current_stage'] = nz(cands[0].get('stage')) if cands else ''                 # AA
            if any(same(c.get('pew_referral'), REFER_PEW004) for c in cands):               # AC
                r['pew_referral_state'] = 'REFERRED — PEW-004'
            elif cands:
                r['pew_referral_state'] = 'CANDIDATE RECORD ACTIVE'
            else:
                r['pew_referral_state'] = 'NO ACTIVE CANDIDATE'
            ab = r.get('committee_disposition')
            if blank(a):                                                                    # AD
                ad = 'SETUP REQUIRED'
            elif ids.count(a) > 1:
                ad = 'DUPLICATE MASR ID'
            elif tickers.count(b) > 1:
                ad = 'DUPLICATE TICKER'
            elif any(blank(r.get(key)) for key in classification):
                ad = 'INCOMPLETE'
            elif blank(k) or blank(l):
                ad = 'MIAR SETUP REQUIRED'
            elif x == 'NOT ELIGIBLE':
                ad = 'NOT ELIGIBLE'
            elif y != 'None':
                ad = 'EXCEPTION REVIEW'
            elif not certified and isin(e, ('Active — Approved Non-Holding', 'Conditional',
                                            'Candidate — Committee Review')) \
                    and (blank(ab) or same(ab, 'Pending')):
                ad = 'COMMITTEE DISPOSITION REQUIRED'
            elif isin(e, ('Active — Approved Non-Holding', 'Conditional')) and (
                    blank(r.get('approved_by')) or blank(r.get('approval_date'))):
                ad = 'CERTIFICATION REQUIRED'
            elif isin(e, ('Rejected', 'Removed', 'Archived')):
                ad = 'INACTIVE / CLOSED'
            else:
                ad = 'CONTROL CLEAR'
            r['control_status'] = ad
            r['required_action'] = L.MASR_REQUIRED_ACTION.get(ad, 'Review exception')      # AE
            rows.append(r)
        self.masr_index = Index(rows, 'ticker')
        return rows

    def _pipeline(self):
        ids = Index(self.store['pipeline'], 'candidate_id')
        eligible = ('ELIGIBLE', 'ELIGIBLE WITH EXCEPTION', 'CERTIFIED HOLDING')
        rows = []
        for src in self.store['pipeline']:
            r = dict(src)
            c = r.get('ticker')
            for key, masr_key in (('security', 'security'), ('proposed_sleeve', 'sleeve'),  # D, I-V
                                  ('proposed_role', 'role'), ('masr_class', 'record_class'),
                                  ('masr_status', 'registry_status'),
                                  ('eligibility_gate', 'eligibility_gate'),
                                  ('exception_requirement', 'exception_requirement'),
                                  ('miar_status', 'miar_status'),
                                  ('research_freshness', 'research_freshness'),
                                  ('integrity_score', 'integrity_score'),
                                  ('mics_score', 'mics_score'),
                                  ('empirical_rank', 'empirical_rank'),
                                  ('market_cap', 'market_cap'), ('zacks_rank', 'zacks_rank'),
                                  ('merrill_status', 'merrill_status')):
                r[key] = lookup(self.masr_index, c, masr_key)
            r['evidence_records'] = '' if blank(c) else self.evidence_index.count(c)        # X
            ag = r.get('pew_candidate_id')
            r['pew_final_score'] = lookup(self.pew004_index, ag, 'final_score')             # AH
            r['pew_eligibility'] = lookup(self.pew004_index, ag, 'eligibility_gate')        # AI
            r['pew_status'] = lookup(self.pew004_index, ag, 'status')                       # AJ
            y = r.get('stage')
            if blank(r.get('candidate_id')):                                                # Z
                z = ''
            elif ids.count(r.get('candidate_id')) > 1:
                z = 'FAIL — DUPLICATE ID'
            elif missing_fields('pipeline', r):
                z = 'FAIL — INCOMPLETE'
            elif isin(y, STAGES_NEED_MASR) and blank(r['masr_class']):
                z = 'FAIL — MASR RECORD REQUIRED'
            elif isin(y, STAGES_NEED_ELIGIBILITY) and not isin(r['eligibility_gate'], eligible):
                z = 'FAIL — ELIGIBILITY'
            elif isin(y, STAGES_NEED_EVIDENCE) and r['evidence_records'] == 0:
                z = 'FAIL — EVIDENCE'
            elif isin(y, STAGES_NEED_EVIDENCE) and (not same(r['miar_status'], 'Active')
                                                    or not same(r['research_freshness'], 'CURRENT')):
                z = 'FAIL — MIAR GATE'
            elif isin(y, STAGES_NEED_DISPOSITION) and (blank(r.get('committee_disposition'))
                                                       or same(r.get('committee_disposition'), 'Pending')):
                z = 'FAIL — COMMITTEE DISPOSITION'
            elif same(y, 'Referred to PEW-004') and (not same(r.get('pew_referral'), REFER_PEW004)
                                                     or blank(ag) or blank(r['pew_status'])):
                z = 'FAIL — PEW REFERRAL'
            else:
                z = PASS_GATE
            r['gate_result'] = z
            b, aq = as_date(r.get('intake_date')), as_date(r.get('closed_date'))
            if b is None:                                                                   # AC
                r['days_open'] = ''
            else:
                r['days_open'] = ((aq or self.today) - b).days
            closed_stage = isin(y, CLOSED_STAGES)
            due = as_date(r.get('due_date'))
            if blank(r.get('candidate_id')):                                                # AK
                ak = ''
            elif z in GATE_TO_CONTROL:
                ak = GATE_TO_CONTROL[z]
            elif closed_stage and any(blank(r.get(k)) for k in ('closure_reason', 'closed_by',
                                                                 'closed_date')):
                ak = 'CLOSURE REQUIRED'
            elif due is not None and due < self.today and not closed_stage:
                ak = 'OVERDUE'
            elif closed_stage:
                ak = 'CLOSED'
            else:
                ak = 'OPEN — ON TRACK'
            r['control_status'] = ak
            r['next_action'] = '' if ak == '' else \
                L.CANDIDATE_REQUIRED_ACTION.get(ak, 'Review candidate exception')          # AL
            rows.append(r)
        return rows

    # ------------------------------------------------------------------ control centers

    def masr_exceptions(self):
        return [r for r in self.masr if not blank(r.get('ticker'))
                and r.get('control_status') not in ('CONTROL CLEAR', 'INACTIVE / CLOSED')]

    def pipeline_exceptions(self):
        return [r for r in self.pipeline if not blank(r.get('candidate_id'))
                and r.get('control_status') not in ('OPEN — ON TRACK', 'CLOSED')]

    def evidence_exceptions(self):
        return [r for r in self.evidence if not blank(r.get('evidence_id'))
                and r.get('control_status') not in ('OPEN — ON TRACK', 'CLOSED', '')]

    def miar_exceptions(self):
        return [r for r in self.miar if r.get('control_status') != 'CONTROL CLEAR']

    def rcc004(self):
        """22 RCC-004 Control Center."""
        masr = [r for r in self.masr if not blank(r.get('ticker'))]
        pipe = [r for r in self.pipeline if not blank(r.get('candidate_id'))]
        exceptions = len(self.masr_exceptions()) + len(self.pipeline_exceptions())
        pipe_ctl = Counter(r['control_status'] for r in pipe)
        masr_ctl = Counter(r['control_status'] for r in masr)
        if not masr:
            readiness = 'NOT INITIALIZED'
        elif exceptions > 0:
            readiness = 'SETUP / CONTROL EXCEPTIONS OPEN'
        elif not pipe:
            readiness = 'READY — NO CANDIDATES'
        else:
            readiness = 'ACTIVE'
        passed = sum(1 for r in pipe if r['gate_result'] == PASS_GATE)
        state = {
            'records_loaded': len(masr),
            'certified_holdings': sum(1 for r in masr if same(r.get('record_class'), CERTIFIED)),
            'approved_non_holdings': sum(
                1 for r in masr if same(r.get('record_class'), 'MASR Approved Non-Holding')
                and same(r.get('registry_status'), 'Active — Approved Non-Holding')),
            'active_candidates': sum(1 for r in pipe if not isin(r.get('stage'), CLOSED_STAGES)),
            'pew_referrals': sum(1 for r in pipe if same(r.get('pew_referral'), REFER_PEW004)),
            'control_exceptions': exceptions,
            'readiness': readiness,
            'capacity': f'{len(masr)} OF 150 SLOTS LOADED',
            'stage_gates': f'{passed} PASS / {len(pipe) - passed} BLOCKED',
            'routing': f"{pipe_ctl['COMMITTEE DECISION REQUIRED']} COMMITTEE / "
                       f"{pipe_ctl['PEW REFERRAL INCOMPLETE']} PEW BLOCKS",
        }
        controls = [
            ('Canonical MASR IDs missing', sum(1 for r in masr if blank(r.get('masr_id'))),
             'Assign the existing canonical MASR identifier to every active registry record',
             'Research Operations', '23 MASR Registry', 'Blocks canonical registry certification'),
            ('Duplicate MASR IDs or tickers',
             masr_ctl['DUPLICATE MASR ID'] + masr_ctl['DUPLICATE TICKER'],
             'Resolve duplicate identity before any admission or referral',
             'Research Operations', '23 MASR Registry', 'Prevents auditable security identity'),
            ('Registry classification incomplete', masr_ctl['INCOMPLETE'],
             'Complete record class, status, admission basis, sleeve, role and security type',
             'Research Committee', '23 MASR Registry', 'Blocks eligibility assessment'),
            ('MIAR / dossier gate exceptions', sum(1 for r in masr if blank(r.get('miar_id'))),
             'Complete RCC-003 MIAR identity and research controls',
             'Research Operations', '20 MIAR Registry', 'Blocks candidate advancement'),
            ('Eligibility or external-research exceptions',
             masr_ctl['NOT ELIGIBLE'] + masr_ctl['EXCEPTION REVIEW'],
             'Resolve market-cap, Zacks, Merrill or eligibility exception',
             'Research Committee', 'RCC-005 / Committee', 'Requires explicit documented judgment'),
            ('Candidate pipeline control exceptions', len(self.pipeline_exceptions()),
             'Resolve incomplete, overdue or blocked candidate stage gates',
             'Research Committee', '24 Candidate Pipeline', 'Prevents controlled candidate progression'),
            ('Committee dispositions pending',
             pipe_ctl['COMMITTEE DECISION REQUIRED'] + masr_ctl['COMMITTEE DISPOSITION REQUIRED'],
             'Record formal committee disposition and decision date',
             'Stewardship Committee', '24 Candidate Pipeline', 'No admission without governance'),
            ('PEW-004 referral blocks', pipe_ctl['PEW REFERRAL INCOMPLETE'],
             'Complete referral flag, PEW candidate ID and PEW linkage',
             'Portfolio Engineering', '10 Candidate Comparison',
             'No engineering review without controlled referral'),
        ]
        composition = []
        for cls in L.MASR_RECORD_CLASS:
            members = [r for r in masr if same(r.get('record_class'), cls)]
            clear = sum(1 for r in members if r['control_status'] == 'CONTROL CLEAR')
            composition.append((cls, len(members), clear, len(members) - clear))
        stages = []
        for stage in L.CANDIDATE_STAGE:
            members = [r for r in pipe if same(r.get('stage'), stage)]
            stages.append((stage, len(members),
                           sum(1 for r in members if r['gate_result'] == PASS_GATE),
                           sum(1 for r in members
                               if r['control_status'] not in ('OPEN — ON TRACK', 'CLOSED'))))
        return {'state': state, 'controls': _controls(controls), 'composition': composition,
                'stages': stages}

    def rcc003(self):
        """19 RCC-003 Control Center."""
        rows = self.miar
        fresh = Counter(r['research_freshness'] for r in rows)
        total = len(rows)
        complete = sum(1 for r in rows if r['dossier_completeness'] == 'COMPLETE')
        exceptions = len(self.miar_exceptions())
        due = fresh['UPDATE DUE'] + fresh['REVIEW DUE'] + fresh['OVERDUE']
        state = {
            'total_records': total,
            'dossiers_complete': complete,
            'current': fresh['CURRENT'],
            'due_overdue': due,
            'material_events': fresh['MATERIAL EVENT REVIEW'],
            'control_exceptions': exceptions,
            'readiness': 'NOT INITIALIZED' if total == 0 else (
                'SETUP / CONTROL EXCEPTIONS OPEN' if exceptions else 'ACTIVE — CONTROLS CLEAR'),
            'coverage': f'{complete} OF {total} COMPLETE',
            'miar_actions': sum(r['miar_actions_pending'] for r in rows),
            'rcc007_referrals': sum(1 for r in rows if r['rcc007_referral'] == 'REFER TO RCC-007'),
        }
        missing = lambda key: sum(1 for r in rows if blank(r.get(key)))  # noqa: E731
        controls = [
            ('Canonical MIAR IDs missing', missing('miar_id'),
             'Assign the existing canonical MIAR identifier to every certified holding',
             'Research Operations', '20 MIAR Registry', 'Blocks dossier certification'),
            ('Record status missing', missing('record_status'),
             'Assign dossier state and certification posture',
             'Research Committee', '20 MIAR Registry', 'Controls record lifecycle'),
            ('Research owners missing', missing('research_owner'),
             'Assign accountable research owner',
             'Research Operations', '20 MIAR Registry', 'Controls ownership and due dates'),
            ('Review cadence missing', missing('review_cadence'),
             'Assign annual, semiannual, quarterly or event-driven cadence',
             'Research Committee', '20 MIAR Registry', 'Controls freshness logic'),
            ('Full-review dates missing', missing('last_full_review'),
             'Enter last certified full-review date',
             'Research Operations', '20 MIAR Registry', 'Required for scheduled review'),
            ('Integrity / MICS fields missing', missing('integrity_score') + missing('mics_score'),
             'Complete the dual research-quality measures',
             'Research Committee', '20 MIAR Registry', 'Blocks complete dossier state'),
            ('Freshness due or overdue', due,
             'Complete incremental or full review as indicated',
             'Research Operations', '21 MIAR Review Log', 'Controls research currency'),
            ('Material-event / MIAR actions', fresh['MATERIAL EVENT REVIEW'] + state['miar_actions'],
             'Resolve evidence-driven MIAR action and determine RCC-007 referral',
             'Research Committee', '18 Evidence / 20 MIAR', 'May affect thesis or conviction'),
        ]
        sleeves = []
        for sleeve in L.SLEEVES:
            members = [r for r in rows if same(r.get('sleeve'), sleeve)]
            f = Counter(r['research_freshness'] for r in members)
            done = sum(1 for r in members if r['dossier_completeness'] == 'COMPLETE')
            setup = sum(1 for r in members if r['control_status'] != 'CONTROL CLEAR')
            if f['MATERIAL EVENT REVIEW']:
                primary = 'MATERIAL EVENT'
            elif f['OVERDUE']:
                primary = 'OVERDUE'
            elif f['REVIEW DUE']:
                primary = 'REVIEW DUE'
            elif setup:
                primary = 'SETUP REQUIRED'
            else:
                primary = 'CONTROL CLEAR'
            sleeves.append({
                'sleeve': sleeve, 'records': len(members), 'complete': done,
                'current': f['CURRENT'], 'update_due': f['UPDATE DUE'],
                'review_due': f['REVIEW DUE'], 'overdue': f['OVERDUE'],
                'material_event': f['MATERIAL EVENT REVIEW'], 'setup_required': setup,
                'coverage': done / len(members) if members else 0, 'primary': primary,
            })
        reviews = [r for r in self.review if not blank(r.get('review_id'))]
        log = {
            'entries': len(reviews),
            'complete': sum(1 for r in reviews if r['control_status'] == 'COMPLETE'),
            'exceptions': sum(1 for r in reviews if r['control_status'] != 'COMPLETE'),
            'certification_pending': sum(1 for r in reviews
                                         if r['control_status'] == 'CERTIFICATION REQUIRED'),
            'rcc007_escalations': sum(1 for r in reviews
                                      if same(r.get('certification_rec'), 'Escalate to RCC-007')),
        }
        return {'state': state, 'controls': _controls(controls), 'sleeves': sleeves, 'log': log}

    def rcc002(self):
        """17 RCC-002 Control Center."""
        rows = [r for r in self.evidence if not blank(r.get('evidence_id'))]
        open_ = [r for r in rows if not isin(r.get('status'), CLOSED_EVIDENCE)]
        exceptions = self.evidence_exceptions()

        def unverified(rs):
            return sum(1 for r in rs if same(r.get('verified'), 'No')) + \
                sum(1 for r in rs if same(r.get('reliability'), 'Unverified — Pending'))

        def crit_high(rs):
            return sum(1 for r in rs if isin(r.get('materiality'), ('Critical', 'High')))

        miar_actions = sum(1 for r in rows if not blank(r.get('miar_action'))
                           and not same(r.get('miar_action'), 'None'))
        thesis = sum(1 for r in rows if not blank(r.get('thesis_impact'))
                     and not isin(r.get('thesis_impact'), ('None', 'Intact')))
        conviction_any = sum(1 for r in rows if not blank(r.get('conviction_rec'))
                             and not isin(r.get('conviction_rec'), ('No Change', 'Not Applicable')))
        conviction_change = sum(1 for r in rows if not blank(r.get('conviction_rec'))
                                and not isin(r.get('conviction_rec'),
                                             ('No Change', 'Not Applicable', 'Unassigned')))
        pew = sum(1 for r in rows if not blank(r.get('pew_referral'))
                  and not same(r.get('pew_referral'), 'No'))
        state = {
            'total_records': len(rows),
            'open': len(open_),
            'critical_high': crit_high(rows),
            'overdue': sum(1 for r in rows if r['control_status'] == 'OVERDUE'),
            'unverified': unverified(rows),
            'referrals_ready': sum(1 for r in rows
                                   if r['referral_eligibility'] == 'ELIGIBLE FOR ROUTING'),
            'readiness': 'READY — NO RECORDS LOADED' if not rows else (
                'CONTROL EXCEPTIONS OPEN' if exceptions else 'ACTIVE — CONTROLS CLEAR'),
            'miar_actions': miar_actions,
            'thesis_conviction_actions': thesis + conviction_any,
            'pew_referrals': pew,
        }
        activity = []
        for act in L.ACTIVITY_TYPE:
            members = [r for r in rows if same(r.get('activity_type'), act)]
            activity.append({
                'activity': act, 'total': len(members),
                'open': sum(1 for r in members if not isin(r.get('status'), CLOSED_EVIDENCE)),
                'critical_high': crit_high(members), 'unverified': unverified(members),
                'overdue': sum(1 for r in members if r['control_status'] == 'OVERDUE'),
                'referral_ready': sum(1 for r in members
                                      if r['referral_eligibility'] == 'ELIGIBLE FOR ROUTING'),
            })
        routing = [
            ('MIAR action required', miar_actions, 'Update or review the asset record'),
            ('Thesis impact actionable', thesis, 'Route to thesis review'),
            ('Conviction change proposed', conviction_change, 'Route to conviction control'),
            ('Candidate / replacement', sum(1 for r in rows if not blank(r.get('candidate_replacement'))
                                            and not same(r.get('candidate_replacement'), 'None')),
             'Route to candidate comparison'),
            ('PEW referrals', pew, 'Engineering review requested'),
            ('Verification exceptions', sum(1 for r in rows if same(r.get('verified'), 'Exception Approved')),
             'Documented exception retained'),
            ('Closed records', len(rows) - len(open_), 'Evidence cycle completed'),
            ('Open control exceptions', len(exceptions), 'Must be resolved or exception-approved'),
        ]
        materiality = [(m, sum(1 for r in rows if same(r.get('materiality'), m))) for m in L.MATERIALITY]
        direction = [(d, sum(1 for r in rows if same(r.get('direction'), d))) for d in L.DIRECTION]
        return {'state': state, 'activity': activity, 'routing': routing,
                'materiality': materiality, 'direction': direction}

    def rcc001(self):
        """16 RCC-001 Executive Research Control Center."""
        conv = self.conviction
        unassigned = sum(1 for r in conv if same(r['effective_conviction'], 'Unassigned'))
        thesis_missing = sum(1 for r in conv if blank(r.get('thesis_status')))
        research_exc = sum(1 for r in self.portfolio if not blank(r.get('research_status'))
                           and not same(r.get('research_status'), 'Current'))
        evidence = [r for r in self.evidence if not blank(r.get('evidence_id'))]
        ev_exc = len(self.evidence_exceptions())
        miar_exc = len(self.miar_exceptions())
        masr_exc = len(self.masr_exceptions())
        pipe_exc = len(self.pipeline_exceptions())
        if unassigned or thesis_missing or miar_exc or masr_exc:
            readiness = 'RESEARCH SETUP INCOMPLETE'
        elif not evidence:
            readiness = 'RCC READY — NO EVIDENCE LOADED'
        elif ev_exc + pipe_exc > 0:
            readiness = 'RCC CONTROL EXCEPTIONS'
        else:
            readiness = 'ACTIVE'
        act = Counter(r.get('activity_type') for r in evidence)
        open_crit_high = sum(1 for r in evidence if isin(r.get('materiality'), ('Critical', 'High'))
                             and not isin(r.get('status'), CLOSED_EVIDENCE))
        earnings = act['Earnings / Guidance'] + act['Material Corporate Event']
        external = act['Zacks Rank Change'] + act['Merrill Research Update']
        state = {
            'readiness': readiness,
            'certified_holdings': sum(1 for r in self.portfolio if not blank(r.get('symbol'))),
            'activity_records': len(evidence),
            'conviction_assigned': sum(1 for r in conv if not blank(r['effective_conviction'])
                                       and not same(r['effective_conviction'], 'Unassigned')),
            'thesis_assigned': len(conv) - thesis_missing,
            'mfpdf_research_status': f"{sum(1 for r in self.portfolio if same(r.get('research_status'), 'Current'))}"
                                     f" CURRENT / {research_exc} EXCEPTIONS",
            'control_exceptions': unassigned + thesis_missing + research_exc + ev_exc + miar_exc
                                  + masr_exc + pipe_exc,
        }
        controls = [
            ('Conviction assignments missing', unassigned, 'Complete PEW-005 effective conviction',
             'Stewardship Committee', '11 Conviction', 'Blocks research and portfolio certification'),
            ('Thesis statuses missing', thesis_missing, 'Assign thesis state for every active holding',
             'Research Committee', 'RCC-007 (planned)', 'Blocks thesis and conviction certification'),
            ('Research status exceptions', research_exc, 'Review non-current MFPDF research records',
             'Research Operations', 'Certified Allocation', 'May trigger MIAR or thesis review',
             'REVIEW REQUIRED'),
            ('Companies requiring review', open_crit_high,
             'Resolve active review queue using verified evidence', 'Research Committee',
             '03 Research Intelligence', 'May require PEW referral', 'OPEN QUEUE', 'NO ACTIVE RECORDS'),
            ('MIAR dossier control exceptions', miar_exc,
             'Complete required MIAR identity, ownership, cadence, scores and review dates',
             'Research Operations', '20 RCC-003 MIAR Registry',
             'Controls research freshness and dossier readiness'),
            ('Earnings / event records', earnings, 'Load verified forward calendar and post-event reviews',
             'Research Operations', 'RCC-006 (planned)', 'Controls event readiness',
             'CALENDAR ACTIVE', 'NO ACTIVE RECORDS'),
            ('Zacks / Merrill changes', external, 'Record only verified external-research changes',
             'Research Committee', 'RCC-005 (planned)', 'Evidence input; never automatic authority',
             'EVIDENCE UPDATE', 'NO ACTIVE RECORDS'),
            ('MASR / candidate pipeline exceptions', masr_exc + pipe_exc,
             'Complete canonical registry setup and resolve candidate stage-gate exceptions',
             'Research Committee', '22–24 RCC-004', 'Controls security admission and PEW referral'),
        ]
        snapshot = [
            ('Company reviews', act['Company Review']),
            ('Earnings / events', earnings),
            ('Zacks changes', act['Zacks Rank Change']),
            ('Merrill updates', act['Merrill Research Update']),
            ('MIAR updates', sum(1 for r in evidence if not blank(r.get('miar_action'))
                                 and not same(r.get('miar_action'), 'None'))),
            ('Thesis assigned', sum(1 for r in evidence if not blank(r.get('thesis_impact'))
                                    and not same(r.get('thesis_impact'), 'None'))),
            ('Conviction assigned', sum(1 for r in evidence if not blank(r.get('conviction_rec'))
                                        and not isin(r.get('conviction_rec'),
                                                     ('No Change', 'Not Applicable', 'Unassigned')))),
            ('Active candidate records', sum(1 for r in self.pipeline if not blank(r.get('candidate_id'))
                                             and not isin(r.get('stage'), CLOSED_STAGES))),
        ]
        return {'state': state, 'controls': _controls(controls), 'snapshot': snapshot,
                'roadmap': ROADMAP}


def _controls(rows):
    """Priority-numbered exception rows: (count == 0 -> pass label, else fail label)."""
    out = []
    for i, row in enumerate(rows, 1):
        trigger, count, action, authority, destination, impact = row[:6]
        fail = row[6] if len(row) > 6 else 'ACTION REQUIRED'
        ok = row[7] if len(row) > 7 else 'PASS'
        out.append({'priority': i, 'control': trigger, 'count': count,
                    'state': ok if count == 0 else fail, 'action': action,
                    'authority': authority, 'destination': destination, 'impact': impact})
    return out


ROADMAP = [
    ('RCC-001', 'Executive Research Control Center', 'ACTIVE — INSTALLED', 'Chief Investment Steward'),
    ('RCC-002', 'Research Intake & Evidence Ledger', 'ACTIVE — INSTALLED', 'Research Committee'),
    ('RCC-003', 'MIAR Dossier Control', 'ACTIVE — INSTALLED', 'Research Operations'),
    ('RCC-004', 'MASR Candidate Pipeline', 'ACTIVE — INSTALLED', 'Research Committee'),
    ('RCC-005', 'Zacks / Merrill Crosswalk', 'NEXT MODULE', 'Stewardship Committee'),
    ('RCC-006', 'Earnings & Material-Event Monitor', 'PLANNED', 'Research Operations'),
    ('RCC-007', 'Thesis & Conviction Review Center', 'PLANNED', 'Research Committee'),
    ('RCC-008', 'Research Certification & Referral', 'PLANNED', 'Chief Investment Steward'),
]
