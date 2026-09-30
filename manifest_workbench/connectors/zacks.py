"""Zacks Rank and market capitalization.

Two ways in, both applied identically:

* **API** — your Zacks data subscription. The endpoint is configured in Settings as a
  URL template (``{ticker}`` is replaced per security) with the API key sent as a query
  parameter or header, and the response fields mapped by name or dotted path.
* **CSV** — a Zacks screen or portfolio download (Ticker, Zacks Rank, Market Cap).

Applying results updates the RCC-004 MASR registry (T Market Cap, U Zacks Rank) and
PEW-004 candidate rows, logs every rank change to Research Intelligence and records it as
a complete RCC-002 evidence record so it flows through the normal verification gates.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import urllib.parse

from .. import ops
from ..engine import blank, same
from . import ConnectorError, http_json, log_run, setting

DEFAULTS = {
    'zacks_url': '',                 # e.g. https://api.example.com/v1/rank?symbol={ticker}
    'zacks_auth': 'query',           # 'query' or 'header'
    'zacks_key_name': 'api_key',     # query parameter or header name
    'zacks_rank_field': 'zacks_rank',
    'zacks_market_cap_field': 'market_cap',
    'zacks_market_cap_unit': 'M',    # unit of the returned market cap: B, M or raw dollars
    'evidence_reviewer': 'Research Committee',
}
UNIT_TO_BILLIONS = {'B': 1.0, 'M': 1e-3, 'RAW': 1e-9}


def config(store: dict) -> dict:
    cfg = {k: setting(store, k, default=v) for k, v in DEFAULTS.items()}
    cfg['api_key'] = setting(store, 'zacks_api_key', env='ZACKS_API_KEY')
    return cfg


def universe(store: dict) -> list:
    """Tickers the workbench tracks: certified holdings, MASR records and PEW-004 candidates."""
    seen = []
    for sym in ([r.get('symbol') for r in store['portfolio']]
                + [r.get('ticker') for r in store['masr'] if r.get('_linked') is None]
                + [r.get('symbol') for r in store['pew004']]):
        if not blank(sym) and sym.upper() not in seen:
            seen.append(sym.upper())
    return seen


# --------------------------------------------------------------------------- fetch

def _path(obj, path: str):
    for part in path.split('.'):
        if isinstance(obj, list):
            obj = obj[int(part)] if part.isdigit() and int(part) < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def _rank(value):
    if value in (None, ''):
        return None
    text = str(value).strip().lstrip('#')
    digits = ''.join(ch for ch in text if ch.isdigit())[:1]
    rank = int(digits) if digits else None
    return rank if rank in (1, 2, 3, 4, 5) else None


def _number(value):
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace('$', '').replace(',', '').strip()
    mult = 1.0
    if text[-1:].upper() in ('B', 'M', 'K', 'T'):
        mult = {'T': 1e12, 'B': 1e9, 'M': 1e6, 'K': 1e3}[text[-1].upper()]
        text = text[:-1]
    try:
        return float(text) * mult if mult != 1.0 else float(text)
    except ValueError:
        return None


def _to_billions(value, unit):
    n = _number(value)
    if n is None:
        return None
    if isinstance(value, str) and value.strip()[-1:].upper() in ('B', 'M', 'K', 'T'):
        return round(n / 1e9, 3)  # the suffix already scaled it to dollars
    return round(n * UNIT_TO_BILLIONS.get(str(unit).upper(), 1e-3), 3)


def fetch(store: dict, tickers=None, get_json=http_json) -> tuple:
    """Query the configured Zacks endpoint. Returns ({ticker: result}, [errors])."""
    cfg = config(store)
    if not cfg['zacks_url']:
        raise ConnectorError('The Zacks endpoint is not configured. Enter it in Settings → Data '
                             'connections, or upload a Zacks CSV instead.')
    if not cfg['api_key']:
        raise ConnectorError('No Zacks API key. Set ZACKS_API_KEY on the server or enter it in Settings.')
    results, errors = {}, []
    for ticker in tickers or universe(store):
        url = cfg['zacks_url'].replace('{ticker}', urllib.parse.quote(ticker))
        headers = {'Accept': 'application/json'}
        if cfg['zacks_auth'] == 'header':
            headers[cfg['zacks_key_name']] = cfg['api_key']
        else:
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}{urllib.parse.urlencode({cfg['zacks_key_name']: cfg['api_key']})}"
        try:
            data = get_json(url, headers)
        except ConnectorError as exc:
            errors.append(f'{ticker}: {exc}')
            continue
        if isinstance(data, list):
            data = next((d for d in data if isinstance(d, dict)
                         and same(str(d.get('ticker') or d.get('symbol') or ticker), ticker)), data[:1] or [{}])
            data = data[0] if isinstance(data, list) else data
        if isinstance(data, dict) and ticker in data and isinstance(data[ticker], dict):
            data = data[ticker]
        rank = _rank(_path(data, cfg['zacks_rank_field']))
        cap = _to_billions(_path(data, cfg['zacks_market_cap_field']), cfg['zacks_market_cap_unit'])
        if rank is None and cap is None:
            errors.append(f'{ticker}: response had no {cfg["zacks_rank_field"]} / '
                          f'{cfg["zacks_market_cap_field"]}')
            continue
        results[ticker] = {'rank': rank, 'market_cap': cap}
    return results, errors


CSV_TICKER = ('ticker', 'symbol')
CSV_RANK = ('zacks rank', 'zacks_rank', 'zacksrank', 'rank')
CSV_CAP = ('market cap (mil)', 'market cap ($mil)', 'market cap (m)', 'market cap ($b)', 'market cap (b)',
           'market cap', 'market_cap', 'mkt cap')


def parse_csv(text: str) -> tuple:
    """Parse a Zacks screen / portfolio download. Returns ({ticker: result}, [errors])."""
    rows = list(csv.reader(io.StringIO(text.lstrip('﻿'))))
    header_at = next((i for i, r in enumerate(rows)
                      if any(c.strip().lower() in CSV_TICKER for c in r)), None)
    if header_at is None:
        raise ConnectorError('No Ticker / Symbol column found in the CSV')
    header = [c.strip().lower() for c in rows[header_at]]

    def col(options):
        return next((header.index(o) for o in options if o in header), None)

    t, r, m = col(CSV_TICKER), col(CSV_RANK), col(CSV_CAP)
    if r is None and m is None:
        raise ConnectorError('No Zacks Rank or Market Cap column found in the CSV')
    unit = 'B' if m is not None and '(b' in header[m] or (m is not None and '$b' in header[m]) else 'M'
    results, errors = {}, []
    for row in rows[header_at + 1:]:
        if len(row) <= t or blank(row[t]):
            continue
        ticker = row[t].strip().upper()
        rank = _rank(row[r]) if r is not None and r < len(row) else None
        cap = _to_billions(row[m], unit) if m is not None and m < len(row) else None
        if rank is None and cap is None:
            errors.append(f'{ticker}: no usable rank or market cap')
            continue
        results[ticker] = {'rank': rank, 'market_cap': cap}
    return results, errors


# --------------------------------------------------------------------------- apply

def apply(store: dict, results: dict, actor: str, today: dt.date, source: str) -> dict:
    """Write results into the registry and candidate comparison; log rank changes."""
    cfg = config(store)
    changes, updated_masr, updated_pew = [], 0, 0
    portfolio = {r['symbol'].upper(): r for r in store['portfolio']}
    for ticker, res in results.items():
        try:
            pos, rec = ops.find(store, 'masr', ticker)
        except ops.OpError:
            rec = None
        if rec is not None:
            prior = rec.get('zacks_rank')
            if _set(store, 'masr', ticker, rec, 'zacks_rank', res['rank'], actor) | \
                    _set(store, 'masr', ticker, rec, 'market_cap', res['market_cap'], actor):
                updated_masr += 1
            if res['rank'] is not None and prior not in (None, '') and int(prior) != res['rank']:
                changes.append((ticker, int(prior), res['rank']))
        for row in store['pew004']:
            if same(row.get('symbol'), ticker):
                if _set(store, 'pew004', row['candidate_id'], row, 'zacks_rank', res['rank'], actor) | \
                        _set(store, 'pew004', row['candidate_id'], row, 'market_cap', res['market_cap'], actor):
                    updated_pew += 1
    evidence_ids = []
    for ticker, prior, current in changes:
        _log_intel(store, ticker, prior, current, today, source)
        evidence_ids.append(_log_evidence(store, ticker, prior, current, today, source, actor,
                                          cfg['evidence_reviewer'], portfolio))
    return {'updated_masr': updated_masr, 'updated_pew004': updated_pew, 'rank_changes': changes,
            'evidence': evidence_ids}


def _set(store, table, label, rec, field, value, actor) -> bool:
    if value is None or rec.get(field) == value:
        return False
    old = rec.get(field)
    rec[field] = value
    ops.audit(store, actor, 'set', table, label, field, old, value)
    return True


def _log_intel(store, ticker, prior, current, today, source):
    rows = store.setdefault('intel-zacks', [])
    entry = {'date': today.isoformat(), 'symbol': ticker, 'prior_rank': prior, 'current_rank': current,
             'direction': 'Upgrade' if current < prior else 'Downgrade', 'notes': f'Pulled from {source}'}
    rows.insert(0, entry)
    del rows[8:]
    while len(rows) < 8:
        rows.append({})


def _log_evidence(store, ticker, prior, current, today, source, actor, reviewer, portfolio):
    holding = portfolio.get(ticker)
    try:
        _, masr = ops.find(store, 'masr', ticker)
    except ops.OpError:
        masr = {}
    downgrade = current > prior
    weak = current in (4, 5)
    record_type = 'Certified Holding' if holding else (
        'MASR Non-Holding' if masr.get('record_class') == 'MASR Approved Non-Holding' else 'Research Candidate')
    subject = (holding or {}).get('security') or masr.get('security') or ticker
    pairs = {
        'date_received': today.isoformat(), 'evidence_date': today.isoformat(),
        'record_type': record_type, 'ticker': ticker, 'subject': subject,
        'activity_type': 'Zacks Rank Change', 'category': 'External Rating / Ranking',
        'materiality': 'High' if weak else 'Moderate',
        'direction': 'Negative' if downgrade else 'Positive',
        'reliability': 'Secondary — Verified', 'source_type': 'Zacks Rank',
        'publisher': 'Zacks Investment Research', 'source_ref': source,
        'summary': f'Zacks Rank changed from #{prior} to #{current}'
                   + (' — Zacks #4/#5 requires exception review.' if weak else '.'),
        'thesis_sensitivity': 'Medium', 'reviewer': reviewer,
        'due_date': (today + dt.timedelta(days=7)).isoformat(), 'status': 'New', 'verified': 'Yes',
        'miar_action': 'None', 'thesis_impact': 'Under Review' if weak else 'None',
        'conviction_rec': 'Watch' if weak else 'No Change', 'candidate_replacement': 'None',
        'pew_referral': 'No', 'disposition': 'Pending',
    }
    rec = ops.add_record(store, 'evidence', [f'{k}={v}' for k, v in pairs.items()], actor, today)
    return rec['evidence_id']


def run(store: dict, actor: str, today: dt.date, get_json=http_json, csv_text: str = None,
        source: str = None) -> dict:
    """Fetch (or parse) and apply in one step; records the run in the data log."""
    if csv_text is not None:
        results, errors = parse_csv(csv_text)
        source = source or f'Zacks CSV upload {today.isoformat()}'
    else:
        results, errors = fetch(store, get_json=get_json)
        source = source or f'Zacks API {today.isoformat()}'
    summary = apply(store, results, actor, today, source)
    text = (f"{len(results)} securities read; {summary['updated_masr']} registry and "
            f"{summary['updated_pew004']} PEW-004 rows updated; {len(summary['rank_changes'])} rank changes")
    log_run(store, 'zacks', actor, text, errors, {'read': len(results), **{
        k: v for k, v in summary.items() if isinstance(v, int)}})
    summary.update({'read': len(results), 'errors': errors, 'text': text})
    return summary
