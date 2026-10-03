"""The official Manifest Weekly Institutional Report (MWIR).

A port of the browser MWIR builder (``mwir/``) into the workbench, so the weekly report is built
from the workbench's own data:

* each week's draft starts from the previous week's MWIR (holdings, guidance, narrative);
* the holdings file (``Date, Symbol, Weights``) sets the executable targets, and tickers new to the
  report take their sleeve, MFPDF baseline and role from the certified portfolio;
* the Zacks validation screen reads the Zacks snapshot that the Zacks connector keeps current;
* control assertions and the certification result are calculated, never typed.

The document keeps the browser builder's field names, so a builder export can be imported as-is.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
import io
import json
import re
from importlib import resources

SLEEVES = (
    ('Strategic', 'Strategic Anchors'),
    ('Growth', 'Growth Compounders'),
    ('Digital', 'Digital Infrastructure / AI'),
    ('Industrials', 'Industrials / Infrastructure'),
    ('Financial', 'Financial Infrastructure'),
    ('Healthcare', 'Healthcare Leadership'),
    ('Energy', 'Energy / Natural Resources'),
    ('Income', 'Income / Risk Management'),
    ('Unassigned', 'Unassigned'),
)
SLEEVE_NAME = dict(SLEEVES)
SLEEVE_ORDER = {k: i for i, (k, _) in enumerate(SLEEVES)}
# certified-portfolio sleeve -> MWIR sleeve key
WORKBENCH_SLEEVE = {
    'Strategic Anchors': 'Strategic', 'Growth Compounders': 'Growth',
    'Digital Infrastructure & AI': 'Digital', 'Industrials & Infrastructure': 'Industrials',
    'Financial Infrastructure': 'Financial', 'Healthcare Leadership': 'Healthcare',
    'Energy & Natural Resources': 'Energy', 'Income & Risk Management': 'Income',
}

GUIDANCE = ('SELECTIVE ADD', 'MAINTAIN', 'MAINTAIN / NO CHASE', 'HOLD <= TARGET', 'EVENT HOLD', 'TRIM', 'EXIT')
CHIP = {
    'SELECTIVE ADD': ('#dcebe1', '#1f5a3c'), 'MAINTAIN': ('#eceae4', '#3a3d45'),
    'MAINTAIN / NO CHASE': ('#f4e6c8', '#6e4a0c'), 'HOLD <= TARGET': ('#f4e6c8', '#6e4a0c'),
    'EVENT HOLD': ('#f5dccd', '#843710'), 'TRIM': ('#f5dccd', '#843710'), 'EXIT': ('#f2d6d7', '#861c22'),
}
SCREEN = {
    'TIER 1': ('#dcebe1', '#1f5a3c'), 'PASS': ('#eceae4', '#3a3d45'), 'REVIEW': ('#f5dccd', '#843710'),
    'ETF': ('#e1e6f0', '#1d2b4a'), 'NO DATA': ('#f2d6d7', '#861c22'),
}
PASS, FAIL, WARN, SOFT = '#1f5a3c', '#a3262a', '#843710', '#3a3d45'
RANK_TEXT = {1: 'Strong Buy', 2: 'Buy', 3: 'Hold', 4: 'Sell', 5: 'Strong Sell'}

COMPASS = (('DELTA / GAMMA', 'deltaGamma', 'deltaNote'), ('FED RANGE', 'fedRange', 'fedNote'),
           ('HY OAS', 'hyOas', 'hyNote'), ('10Y UST', 'tenY', 'tenYNote'), ('VIX', 'vix', 'vixNote'))
HOLDING_FIELDS = ('ticker', 'sleeve', 'mfpdf', 'current', 'guidance', 'rationale', 'status')

# Editor layout: (key, label, rows, hint)
TEXT_FIELDS = {
    'signals': (
        ('tape', 'Weekly risk tape', 6, 'One per line: Label | Value'),
        ('interpretation', 'Signal interpretation', 6, 'One bullet per line'),
        ('decisionRule', 'Decision rule', 4, ''),
        ('officialPosture', 'Official posture', 2, ''),
    ),
    'narrative': (
        ('headline', 'Posture headline', 2, ''), ('subhead', 'Posture sub-line', 3, ''),
        ('execPosture', 'Executive summary · Portfolio posture', 4, ''),
        ('execImplementation', 'Executive summary · Implementation', 4, ''),
        ('execIncremental', 'Executive summary · Incremental capital', 3, ''),
        ('execControl', 'Executive summary · Control boundary', 3, ''),
        ('footnote', 'Page 1 footnote', 2, ''),
        ('macroRates', 'Macro · Rates & liquidity', 4, ''), ('macroInflation', 'Macro · Inflation', 3, ''),
        ('macroCredit', 'Macro · Credit & stress', 3, ''), ('macroEarnings', 'Macro · Earnings', 3, ''),
        ('macroGeo', 'Macro · Geopolitics / oil', 3, ''),
        ('clientBrief', 'Client executive brief', 5, ''),
    ),
    'controls': (
        ('gatesWeek', 'Event gates heading', 1, 'e.g. WEEK OF SEP 28'),
        ('events', 'Forward event gates', 4, 'One per line: DATE | Event | Action'),
        ('hierarchy', 'Capital deployment hierarchy', 4, 'One tier per line, in priority order'),
        ('reconciliation', 'MRGES-001 channel reconciliation', 4, ''),
        ('bandStandard', 'Target / band standard', 3, ''),
        ('strategicTarget', 'Frozen Strategic Anchors total (%)', 1,
         'The control check compares the sleeve total with this'),
        ('matrixDisclaimer', 'Holding matrix disclaimer', 3, ''),
        ('deliverables', 'Frozen deliverables applied', 4, 'One per line'),
        ('disclosures', 'Disclosed control items', 4, 'One per line: Label | Result'),
        ('sources', 'Primary evidence & sources', 6, 'One per line'),
        ('freshness', 'Data-freshness certification', 3, ''),
    ),
}
SCALAR_FIELDS = ('weekEnding', 'pubDate', 'composite', 'compositeChange') + \
    tuple(k for c in COMPASS for k in c[1:]) + tuple(f[0] for fs in TEXT_FIELDS.values() for f in fs)


# --------------------------------------------------------------------------- bundled data

def _bundled():
    text = resources.files('manifest_workbench').joinpath('data/mwir_seed.json').read_text('utf-8')
    return json.loads(text)


def seed_doc() -> dict:
    """The 28 Aug 2026 MWIR, the starting example."""
    return _bundled()['doc']


def bundled_snapshot() -> dict:
    return _bundled()['zacks']


def snapshot(store: dict) -> dict:
    """The Zacks snapshot: maintained by the Zacks connector, else the bundled 25 Sep 2026 one."""
    snap = store.get('zacks') or {}
    return snap if snap.get('data') else bundled_snapshot()


def zacks_for(snap: dict, ticker: str):
    key = (snap.get('alias') or {}).get(ticker) or ticker
    raw = (snap.get('data') or {}).get(key)
    if not raw:
        return None
    return dict(raw, key=key)


# --------------------------------------------------------------------------- helpers

def num(v) -> float:
    try:
        n = float(str(v).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return 0.0
    return n if n == n and abs(n) != float('inf') else 0.0


def pct(v) -> str:
    return f'{num(v):.2f}%'


def lines(text) -> list:
    return [x.strip() for x in str(text or '').split('\n') if x.strip()]


def pipes(text) -> list:
    return [[p.strip() for p in line.split('|')] for line in lines(text)]


def band(target: float) -> str:
    lo, hi = max(1.0, target * 0.75), min(4.0, target * 1.25)
    return f'{_round2(lo)}–{_round2(hi)}%'


def _round2(x: float) -> str:
    # round the exact binary value half-up, as JavaScript's toFixed does (3.775 -> 3.77)
    from decimal import ROUND_HALF_UP, Decimal
    return str(Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _num_text(v: float) -> str:
    return f'{v:.4f}'.rstrip('0').rstrip('.')


def parse_date(value):
    value = (value or '').strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', value)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', value)
    if m:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return dt.date(y, int(m[1]), int(m[2]))
    return None


def _long(d):
    return f'{d.day} {d:%b}'.upper() + f' {d.year}' if d else '—'


def _short(d):
    return f'{d.day} {d:%b} {d.year}' if d else '—'


def label(doc: dict) -> str:
    we = parse_date(doc.get('weekEnding'))
    return f'Week ending {we:%b} {we.day}, {we.year}' if we else 'Week ending —'


def week_dates(review_start: dt.date) -> tuple:
    """Week ending (the Friday before) and publication date (the review Monday)."""
    return review_start - dt.timedelta(days=3), review_start


# --------------------------------------------------------------------------- new week

def new_doc(store: dict, prior: dict = None, review_start: dt.date = None) -> dict:
    """Start a week's MWIR from the prior week's document (or the 28 Aug example)."""
    doc = copy.deepcopy(prior) if prior else seed_doc()
    if review_start:
        we, pub = week_dates(review_start)
        doc['weekEnding'], doc['pubDate'] = we.isoformat(), pub.isoformat()
        doc['gatesWeek'] = f'WEEK OF {pub:%b} {pub.day}'.upper()
    if not str(doc.get('strategicTarget') or '').strip():
        doc['strategicTarget'] = strategic_target(store)
    return doc


def strategic_target(store: dict) -> str:
    """The certified Strategic Anchors sleeve total, in percent."""
    total = sum(r.get('target_weight') or 0 for r in store.get('portfolio', [])
                if r.get('sleeve') == 'Strategic Anchors' and not str(r.get('symbol', '')).startswith('BRK'))
    brk = sum(r.get('target_weight') or 0 for r in store.get('portfolio', [])
              if str(r.get('symbol', '')).startswith('BRK'))
    # BRK.B is analytical only; its weight is redistributed inside the sleeve
    return f'{(total + brk) * 100:.2f}' if total else ''


def certified(store: dict) -> dict:
    """Certified portfolio rows by ticker, translated into MWIR terms."""
    out = {}
    for r in store.get('portfolio', []):
        sym = str(r.get('symbol') or '').upper()
        if sym:
            out[sym] = {'sleeve': WORKBENCH_SLEEVE.get(r.get('sleeve'), 'Unassigned'),
                        'mfpdf': _num_text((r.get('target_weight') or 0) * 100),
                        'role': r.get('role') or '', 'security': r.get('security') or ''}
    return out


# --------------------------------------------------------------------------- holdings file

def import_csv(store: dict, doc: dict, text: str) -> tuple:
    """Load a Date, Symbol, Weights holdings file. Returns (message, ok)."""
    rows = list(csv.reader(io.StringIO(text.lstrip('﻿'))))
    if not rows:
        raise ValueError('The file is empty.')
    head = [c.strip().lower() for c in rows[0]]

    def col(*names):
        return next((head.index(n) for n in names if n in head), -1)
    i_sym, i_w, i_d = col('symbol', 'ticker'), col('weights', 'weight'), col('date')
    if i_sym < 0 or i_w < 0:
        raise ValueError('Could not find Symbol and Weights columns in the header row.')
    parsed, date = [], None
    for r in rows[1:]:
        sym = (r[i_sym] if i_sym < len(r) else '').strip().upper()
        try:
            w = float((r[i_w] if i_w < len(r) else '').replace('%', '').strip())
        except ValueError:
            continue
        if not sym:
            continue
        parsed.append((sym, w))
        if date is None and 0 <= i_d < len(r) and r[i_d].strip():
            date = r[i_d].strip()
    if not parsed:
        raise ValueError('No holdings rows found under the header.')
    decimal = all(w <= 1 for _, w in parsed)
    prior = {h['ticker']: h for h in doc.get('holdings', [])}
    cert = certified(store)
    holdings, added, unassigned, seen = [], [], [], set()
    for sym, w in parsed:
        cur = _num_text(w * 100 if decimal else w)
        seen.add(sym)
        if sym in prior:
            holdings.append(dict(prior[sym], current=cur))
            continue
        c = cert.get(sym)
        holdings.append({'ticker': sym, 'sleeve': c['sleeve'] if c else 'Unassigned',
                         'mfpdf': c['mfpdf'] if c else cur, 'current': cur, 'guidance': 'MAINTAIN',
                         'rationale': c['role'] if c else '', 'status': 'EVIDENCE HOLD'})
        (added if c else unassigned).append(sym)
    dropped = [t for t in prior if t not in seen]
    doc['holdings'] = holdings
    when = parse_date(date)
    if when:
        doc['weekEnding'] = when.isoformat()
        doc['pubDate'] = (when + dt.timedelta(days=3)).isoformat()
    total = sum(num(h['current']) for h in holdings)
    msg = [f"Loaded {len(holdings)} holdings{f' dated {date}' if date else ''} · total {total:.2f}%."]
    if added:
        msg.append('New, filled from the certified portfolio: ' + ', '.join(added))
    if unassigned:
        msg.append('New and not in the certified portfolio (set sleeve + rationale): ' + ', '.join(unassigned))
    if dropped:
        msg.append('Dropped vs prior: ' + ', '.join(dropped))
    return '\n'.join(msg), not unassigned


def fill_baseline(store: dict, doc: dict) -> int:
    """Set each holding's MFPDF baseline (and unassigned sleeves) from the certified portfolio."""
    cert, n = certified(store), 0
    for h in doc.get('holdings', []):
        c = cert.get(h.get('ticker', '').upper())
        if not c:
            continue
        if h.get('mfpdf') != c['mfpdf']:
            h['mfpdf'] = c['mfpdf']
            n += 1
        if h.get('sleeve') in (None, '', 'Unassigned'):
            h['sleeve'] = c['sleeve']
            n += 1
    return n


def upcoming_events(store: dict, doc: dict, days: int = 7) -> list:
    """Event-gate lines for holdings reporting earnings in the publication week."""
    snap, pub = snapshot(store), parse_date(doc.get('pubDate'))
    if not pub:
        return []
    names = {k: v['security'] for k, v in certified(store).items()}
    out = []
    for h in doc.get('holdings', []):
        z = zacks_for(snap, h.get('ticker', ''))
        er = parse_date((z or {}).get('er') or '')
        if er and 0 <= (er - pub).days <= days:
            out.append((er, f"{er:%b} {er.day}".upper() + f" | {names.get(h['ticker'], h['ticker'])}"
                        f" | Earnings gate: hold {h['ticker']} at or below target into results; reassess after release."))
    return [line for _, line in sorted(out)]


# --------------------------------------------------------------------------- calculated view

def model(doc: dict, snap: dict) -> dict:
    """Everything the report shows, derived from the document and the Zacks snapshot."""
    we, pd_ = parse_date(doc.get('weekEnding')), parse_date(doc.get('pubDate'))
    m = {'week_upper': _long(we), 'pub_long': _long(pd_), 'pub_short': _short(pd_)}

    c = max(0.0, min(100.0, num(doc.get('composite'))))
    c = int(c) if c == int(c) else c
    if c >= 70:
        zone = {'label': 'GREEN · CONSTRUCTIVE', 'color': '#2f6f4f'}
    elif c >= 55:
        zone = {'label': 'YELLOW · NEUTRAL / RISK CONTROL', 'color': '#9a6f0e'}
    elif c >= 40:
        zone = {'label': 'ORANGE · DEFENSIVE', 'color': '#b04e14'}
    else:
        zone = {'label': 'RED · RISK-OFF', 'color': '#a3262a'}
    zone.update(value=c, deg=round(c * 1.8 - 90, 1))

    hs = doc.get('holdings') or []
    total = sum(num(h.get('current')) for h in hs)
    total_ok = abs(total - 100) < 0.01
    rows = []
    for i, h in enumerate(hs):
        chip = CHIP.get(h.get('guidance'), CHIP['MAINTAIN'])
        rows.append(dict(h, idx=i, mfpdf_fmt=pct(h.get('mfpdf')), current_fmt=pct(h.get('current')),
                         band=band(num(h.get('current'))), chip_bg=chip[0], chip_fg=chip[1],
                         sleeve_name=SLEEVE_NAME.get(h.get('sleeve'), h.get('sleeve') or '')))
    matrix = sorted(rows, key=lambda r: (SLEEVE_ORDER.get(r.get('sleeve'), 99), r['idx']))
    half = (len(matrix) + 1) // 2
    matrix_pages = [{'roman': 'I', 'num': 5, 'rows': matrix[:half]},
                    {'roman': 'II', 'num': 6, 'rows': matrix[half:]}]

    sleeve_totals = [{'key': k, 'name': n, 'v': sum(num(h.get('current')) for h in hs if h.get('sleeve') == k)}
                     for k, n in SLEEVES]
    sleeve_totals = [s for s in sleeve_totals if s['v'] > 0 or s['key'] != 'Unassigned']
    max_s = max([s['v'] for s in sleeve_totals] + [1])
    sleeve_alloc = [{'name': s['name'], 'fmt': f"{s['v']:.2f}%", 'bar': round(s['v'] / max_s * 100, 1)}
                    for s in sleeve_totals]
    top10 = sorted(rows, key=lambda r: (-num(r.get('current')), r['idx']))[:10]

    strategic = next((s['v'] for s in sleeve_totals if s['key'] == 'Strategic'), 0.0)
    strat_raw = str(doc.get('strategicTarget') or '').strip()
    strat_target = num(strat_raw)
    strat_ok = not strat_raw or abs(strategic - strat_target) < 0.015
    brk = sum(1 for h in hs if str(h.get('ticker', '')).startswith('BRK') and num(h.get('current')) > 0)
    over_cap = sum(1 for h in hs if num(h.get('current')) > 4.0001)
    unassigned = sum(1 for h in hs if h.get('sleeve') not in SLEEVE_NAME or h.get('sleeve') == 'Unassigned')
    checks = [
        ('Executable holdings', f"{len(hs)} / {'PASS' if hs else 'FAIL'}", bool(hs)),
        ('Executable target total', f"{total:.2f}% / {'PASS' if total_ok else 'FAIL'}", total_ok),
        ('Strategic Anchors', f"{strategic:.2f}% / " + ('PASS' if strat_ok else f'CHECK vs {strat_target:.2f}%'),
         strat_ok),
        ('BRK.B executable rows', f"{brk} / {'PASS' if brk == 0 else 'FAIL'}", brk == 0),
        ('Positions above 4.00% cap', f"{over_cap} / {'PASS' if over_cap == 0 else 'FAIL'}", over_cap == 0),
        ('Unassigned sleeves', f"{unassigned} / {'PASS' if unassigned == 0 else 'FAIL'}", unassigned == 0),
    ]
    all_ok = all(ok for _, _, ok in checks)

    zk = zacks_screen(rows, snap, pd_)
    z_ok = zk['counts']['REVIEW'] == 0 and zk['counts']['NO DATA'] == 0
    # Screen exceptions are amber and do not block publication: the framework may keep names
    # the screen would drop.
    assertions = [{'label': lbl, 'result': res, 'color': PASS if ok else FAIL} for lbl, res, ok in checks]
    assertions.append({'label': 'Zacks screen exceptions',
                       'result': f"{zk['counts']['REVIEW'] + zk['counts']['NO DATA']} / {'PASS' if z_ok else 'REVIEW'}",
                       'color': PASS if z_ok else WARN})
    assertions += [{'label': p[0], 'result': p[1] if len(p) > 1 else '', 'color': SOFT}
                   for p in pipes(doc.get('disclosures'))]
    cert = {'label': 'PUBLISHED / FROZEN', 'color': PASS, 'ok': True} if all_ok else \
        {'label': 'HOLD · CONTROLS FAILING', 'color': FAIL, 'ok': False}

    components = []
    for k in doc.get('components') or []:
        s = max(0.0, min(10.0, num(k.get('score'))))
        s = int(s) if s == int(s) else s
        col = '#2f6f4f' if s >= 7 else '#b08314' if s >= 5 else '#c2571a' if s >= 3 else '#a3262a'
        components.append({'name': k.get('name', ''), 'score': s, 'pct': s * 10, 'color': col})

    return {
        'd': doc, 'm': m, 'zone': zone, 'rows': rows, 'matrix_pages': matrix_pages,
        'sleeve_alloc': sleeve_alloc, 'top10': top10,
        'stats': {'count': len(hs), 'total': total, 'total_fmt': f'{total:.2f}%', 'total_ok': total_ok,
                  'strategic': strategic},
        'checks': checks, 'assertions': assertions, 'cert': cert, 'zk': zk, 'components': components,
        'compass': [{'label': 'CURRENT COMPOSITE', 'value': f'{c} / 100',
                     'note': f"{doc.get('compositeChange') or '0'} w/w"}] +
                   [{'label': lbl, 'value': doc.get(v) or '', 'note': doc.get(n) or ''} for lbl, v, n in COMPASS],
        'tape': [{'label': p[0], 'value': p[1] if len(p) > 1 else ''} for p in pipes(doc.get('tape'))],
        'interpretation': lines(doc.get('interpretation')),
        'exec_paras': [('Portfolio posture:', doc.get('execPosture')), ('Implementation:', doc.get('execImplementation')),
                       ('Incremental capital:', doc.get('execIncremental')),
                       ('Control boundary:', doc.get('execControl'))],
        'macro': [('RATES & LIQUIDITY', doc.get('macroRates')), ('INFLATION', doc.get('macroInflation')),
                  ('CREDIT & STRESS', doc.get('macroCredit')), ('EARNINGS', doc.get('macroEarnings')),
                  ('GEOPOLITICS / OIL', doc.get('macroGeo'))],
        'events': [p + [''] * (3 - len(p)) for p in pipes(doc.get('events'))],
        'hierarchy': lines(doc.get('hierarchy')),
        'deliverables': lines(doc.get('deliverables')), 'sources': lines(doc.get('sources')),
    }


def zacks_screen(rows: list, snap: dict, pub: dt.date = None) -> dict:
    """Market cap above $100B and Zacks Rank 1-3; Tier 1 is Rank 1-2. ETFs carry their ETF rank."""
    as_of = parse_date(snap.get('as_of'))
    ref = pub or as_of or dt.date.today()
    counts = dict.fromkeys(SCREEN, 0)
    reviews, soon, aliases, out = [], [], [], []
    for r in rows:
        ticker = r.get('ticker')
        if not ticker:
            continue
        z = zacks_for(snap, ticker)
        rank_label, cap, er, cap_bad, er_soon = '—', '—', '—', False, False
        if not z:
            screen = 'NO DATA'
        elif z.get('etf'):
            screen = 'ETF'
            rank_label = f"ETF {z['rank']} · {z.get('text') or ''}" if z.get('rank') else 'ETF · unranked'
        elif not z.get('rank') and not z.get('cap'):
            screen = 'NO DATA'
        else:
            rank = z.get('rank')
            rank_label = f"{rank} · {z.get('text') or RANK_TEXT.get(rank, '')}" if rank else 'not ranked'
            capm = z.get('cap')
            if capm:
                cap = f"${capm / 1000:.{2 if capm < 1_000_000 else 0}f}B"
                cap_bad = capm <= 100_000
            erd = parse_date(z.get('er') or '')
            if erd:
                er = f'{erd:%b} {erd.day}'
                days = (erd - ref).days
                er_soon = -7 <= days <= 21
                if er_soon:
                    soon.append(f'{ticker} {er}')
            why = []
            if cap_bad:
                why.append(f'cap {cap}')
            if rank and rank > 3:
                why.append(f"Rank {rank} {z.get('text') or RANK_TEXT.get(rank, '')}".strip())
            if not rank:
                why.append('no Zacks Rank')
            if why:
                screen = 'REVIEW'
                reviews.append(f"{ticker} ({', '.join(why)})")
            else:
                screen = 'TIER 1' if rank <= 2 else 'PASS'
        if z and z['key'] != ticker:
            aliases.append(f"{ticker} is listed by Zacks as {z['key']}.")
        counts[screen] += 1
        bg, fg = SCREEN[screen]
        out.append({'ticker': ticker, 'rank_label': rank_label, 'cap': cap, 'er': er, 'screen': screen,
                    'bg': bg, 'fg': fg, 'cap_color': WARN if cap_bad else '#1a1d24',
                    'er_color': WARN if er_soon else SOFT})
    half = (len(out) + 1) // 2
    return {
        'as_of': _short(as_of) if as_of else 'not loaded', 'as_of_upper': _long(as_of) if as_of else 'NOT LOADED',
        'source': snap.get('source') or '', 'matched': len(out) - counts['NO DATA'], 'counts': counts,
        'tiles': [{'label': k, 'n': counts[k], 'bg': SCREEN[k][0], 'fg': SCREEN[k][1]}
                  for k in ('TIER 1', 'PASS', 'REVIEW', 'ETF')],
        'rows': out, 'cols': [out[:half], out[half:]],
        'review_text': '; '.join(reviews) + '.' if reviews else 'none.',
        'soon_text': ', '.join(soon) + '.' if soon else 'none.',
        'alias_text': ' '.join(aliases),
    }


# --------------------------------------------------------------------------- editing

def apply_form(doc: dict, form) -> None:
    """Apply an editor submission (a mapping with .get / .getlist like a Flask form)."""
    for key in SCALAR_FIELDS:
        if key in form:
            doc[key] = str(form.get(key)).replace('\r\n', '\n')
    for i, comp in enumerate(doc.get('components') or []):
        if f'comp_{i}' in form:
            comp['score'] = form.get(f'comp_{i}').strip()
    if 'h_count' in form:
        holdings = []
        for i in range(int(form.get('h_count') or 0)):
            if form.get(f'h_{i}_remove'):
                continue
            h = {f: (form.get(f'h_{i}_{f}') or '').strip() for f in HOLDING_FIELDS}
            h['ticker'] = h['ticker'].upper()
            if h['ticker'] or num(h['current']):
                holdings.append(h)
        if form.get('h_add'):
            holdings.append({'ticker': '', 'sleeve': 'Unassigned', 'mfpdf': '0', 'current': '0',
                             'guidance': 'MAINTAIN', 'rationale': '', 'status': 'EVIDENCE HOLD'})
        doc['holdings'] = holdings


def import_json(text: str) -> dict:
    """A document exported from the browser builder (its localStorage value) or from the console."""
    data = json.loads(text)
    if isinstance(data, dict) and 'doc' in data and isinstance(data['doc'], dict):
        data = data['doc']
    if not isinstance(data, dict) or not isinstance(data.get('holdings'), list):
        raise ValueError('This is not an MWIR document (no holdings list).')
    doc = seed_doc()
    for k, v in data.items():
        if k not in doc or k in ('holdings', 'components'):
            continue
        doc[k] = '' if v is None else str(v)
    doc['holdings'] = [{f: str(h.get(f) if h.get(f) is not None else '').strip() for f in HOLDING_FIELDS}
                       for h in data['holdings'] if isinstance(h, dict)]
    for h in doc['holdings']:
        h['ticker'] = h['ticker'].upper()
    if isinstance(data.get('components'), list):
        doc['components'] = [{'name': str(c.get('name', '')), 'score': str(c.get('score', ''))}
                             for c in data['components'] if isinstance(c, dict)]
    return doc
