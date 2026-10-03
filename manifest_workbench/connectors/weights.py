"""Actual portfolio weights from a broker positions CSV.

Reads the positions download most brokers provide (Merrill, Schwab, Fidelity and
similar): the header row is found automatically past any preamble, and weights come
from a weight / % of account column, or from market value, or from quantity × price.
``preview`` shows what will change; ``apply`` writes Certified Allocation column I.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re

from .. import ops
from ..engine import blank
from . import ConnectorError, log_run

SYMBOL = ('symbol', 'ticker', 'security symbol', 'symbol/cusip', 'sym')
WEIGHT = ('% of account', '% of acct', '% of portfolio', 'percent of account', 'percent of portfolio',
          'portfolio %', 'weight', 'weight %', '% of total', 'allocation', 'pct of account',
          '% of holdings', 'percent of holdings')
VALUE = ('market value', 'mkt value', 'current value', 'value', 'market value ($)', 'mkt val (market value)',
         'position value', 'total value')
QUANTITY = ('quantity', 'qty', 'shares', 'qty (quantity)')
PRICE = ('price', 'last price', 'current price', 'price ($)', 'closing price')
SKIP_SYMBOLS = ('TOTAL', 'ACCOUNT TOTAL', 'CASH', 'CASH & CASH INVESTMENTS', 'PENDING ACTIVITY',
                'CASH AND MONEY MARKET', '--')


def normalize(symbol: str) -> str:
    s = symbol.strip().upper().replace(' ', '')
    s = re.sub(r'[/\-]', '.', s)
    return s.rstrip('*')


def _num(text):
    if text is None:
        return None
    t = str(text).strip().replace('$', '').replace(',', '').replace('%', '')
    neg = t.startswith('(') and t.endswith(')')
    t = t.strip('()')
    if t in ('', '--', 'N/A', 'n/a'):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def parse(text: str) -> dict:
    rows = list(csv.reader(io.StringIO(text.lstrip('﻿'))))
    header_at = None
    for i, r in enumerate(rows):
        cells = [c.strip().lower() for c in r]
        if any(c in SYMBOL for c in cells):
            header_at = i
            break
    if header_at is None:
        raise ConnectorError('No Symbol / Ticker column found. Is this a positions download?')
    header = [c.strip().lower() for c in rows[header_at]]

    def col(options):
        return next((header.index(o) for o in options if o in header), None)

    s, w, v, q, p = col(SYMBOL), col(WEIGHT), col(VALUE), col(QUANTITY), col(PRICE)
    if w is None and v is None and (q is None or p is None):
        raise ConnectorError('No weight, market value or quantity × price columns found')
    positions = {}
    for r in rows[header_at + 1:]:
        if len(r) <= s or blank(r[s]):
            continue
        sym = normalize(r[s])
        if sym in SKIP_SYMBOLS or sym.startswith('TOTAL') or not re.match(r'^[A-Z][A-Z0-9.]{0,9}$', sym):
            continue
        weight = _num(r[w]) if w is not None and w < len(r) else None
        value = _num(r[v]) if v is not None and v < len(r) else None
        if value is None and q is not None and p is not None and max(q, p) < len(r):
            qty, price = _num(r[q]), _num(r[p])
            value = qty * price if qty is not None and price is not None else None
        if weight is None and value is None:
            continue
        pos = positions.setdefault(sym, {'weight': 0.0 if weight is not None else None, 'value': 0.0})
        if weight is not None:
            pos['weight'] = (pos['weight'] or 0.0) + weight
        pos['value'] += value or 0.0
    if not positions:
        raise ConnectorError('No positions found in the file')
    basis = 'weight' if all(p['weight'] is not None for p in positions.values()) else 'value'
    if basis == 'weight':
        total = sum(p['weight'] for p in positions.values())
        scale = 100.0 if total > 1.5 else 1.0  # percent points vs fractions
        weights = {k: p['weight'] / scale for k, p in positions.items()}
    else:
        total = sum(p['value'] for p in positions.values())
        if total <= 0:
            raise ConnectorError('Position market values sum to zero')
        weights = {k: p['value'] / total for k, p in positions.items()}
    return {'basis': basis, 'weights': weights}


def preview(store: dict, text: str, missing_as_zero: bool = True) -> dict:
    parsed = parse(text)
    weights = parsed['weights']
    holdings = [r['symbol'] for r in store['portfolio']]
    rows = []
    for r in store['portfolio']:
        new = weights.get(normalize(r['symbol']))
        if new is None and missing_as_zero:
            new = 0.0
        rows.append({'symbol': r['symbol'], 'target': r.get('target_weight'), 'current': r.get('actual_weight'),
                     'new': new, 'in_file': normalize(r['symbol']) in weights})
    extra = sorted(k for k in weights if k not in {normalize(h) for h in holdings})
    return {'basis': parsed['basis'], 'rows': rows, 'not_in_portfolio': extra,
            'extra_weight': sum(weights[k] for k in extra),
            'matched': sum(1 for r in rows if r['in_file']),
            'missing': [r['symbol'] for r in rows if not r['in_file']],
            'new_total': sum(r['new'] or 0 for r in rows)}


def apply(store: dict, result: dict, actor: str, today: dt.date, filename: str = '') -> str:
    changed = 0
    for row in result['rows']:
        if row['new'] is None:
            continue
        pos, rec = ops.find(store, 'portfolio', row['symbol'])
        value = round(row['new'], 6)
        if rec.get('actual_weight') != value:
            ops.audit(store, actor, 'set', 'portfolio', row['symbol'], 'actual_weight',
                      rec.get('actual_weight'), value)
            rec['actual_weight'] = value
            changed += 1
    text = (f"{result['matched']} of {len(result['rows'])} holdings matched ({result['basis']} basis); "
            f"{changed} weights changed; {len(result['not_in_portfolio'])} positions not in the certified "
            f"portfolio ({result['extra_weight'] * 100:.2f}%)")
    log_run(store, 'weights', actor, text + (f' — {filename}' if filename else ''),
            [f"Not in portfolio: {', '.join(result['not_in_portfolio'])}"] if result['not_in_portfolio'] else [],
            {'matched': result['matched'], 'changed': changed})
    return text
