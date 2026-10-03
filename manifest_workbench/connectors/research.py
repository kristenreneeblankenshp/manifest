"""Research pulls into a triage inbox.

Sources:

* **SEC EDGAR** — new filings (8-K, 10-Q, 10-K by default) for every tracked ticker, from
  EDGAR's public Atom feeds. The SEC asks callers to identify themselves; the contact
  e-mail in Settings is sent as the User-Agent.
* **Zacks research** (optional) — a JSON endpoint from your Zacks subscription returning
  research items (title, date, url, summary), configured like the rank endpoint.

Pulled items wait in ``store['inbox']`` until an operator logs them as RCC-002 evidence,
adds them to the research-review queue, or dismisses them. Nothing reaches the evidence
ledger unreviewed.
"""

from __future__ import annotations

import datetime as dt
import urllib.parse
import xml.etree.ElementTree as ET

from ..engine import blank
from . import ConnectorError, http_get, http_json, log_run, setting
from .zacks import _path, config as zacks_config, universe

EDGAR_URL = ('https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type={form}'
             '&dateb=&owner=include&count=10&output=atom')
ATOM = '{http://www.w3.org/2005/Atom}'
DEFAULT_FORMS = '8-K,10-Q,10-K'
# ETFs have no company filings worth triaging.
SKIP_TYPES = ('ETF',)


def _edgar_items(store, ticker, forms, since, get):
    contact = setting(store, 'sec_contact', env='SEC_CONTACT_EMAIL')
    if not contact:
        raise ConnectorError('Enter a contact e-mail in Settings (the SEC requires it for EDGAR access)')
    items = []
    for form in forms:
        url = EDGAR_URL.format(ticker=urllib.parse.quote(ticker), form=urllib.parse.quote(form))
        raw = get(url, {'User-Agent': f'Manifest Workbench {contact}', 'Accept': 'application/atom+xml'})
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            raise ConnectorError(f'EDGAR returned an unreadable feed for {ticker}') from None
        for entry in root.findall(f'{ATOM}entry'):
            updated = (entry.findtext(f'{ATOM}updated') or '')[:10]
            if updated and updated < since:
                continue
            link = entry.find(f'{ATOM}link')
            cat = entry.find(f'{ATOM}category')
            title = (entry.findtext(f'{ATOM}title') or '').strip()
            items.append({'source': 'SEC EDGAR', 'ticker': ticker, 'form': cat.get('term') if cat is not None
                          else form, 'title': title, 'date': updated,
                          'url': link.get('href') if link is not None else '',
                          'summary': (entry.findtext(f'{ATOM}summary') or '').strip()[:500]})
    return items


def _zacks_items(store, ticker, since, get_json):
    url = setting(store, 'zacks_research_url')
    if not url:
        return []
    cfg = zacks_config(store)
    full = url.replace('{ticker}', urllib.parse.quote(ticker))
    headers = {'Accept': 'application/json'}
    if cfg['zacks_auth'] == 'header':
        headers[cfg['zacks_key_name']] = cfg['api_key']
    else:
        full += ('&' if '?' in full else '?') + urllib.parse.urlencode({cfg['zacks_key_name']: cfg['api_key']})
    data = get_json(full, headers)
    records = _path(data, setting(store, 'zacks_research_list_field', default='items')) \
        if isinstance(data, dict) else data
    items = []
    for d in records or []:
        date = str(_path(d, setting(store, 'zacks_research_date_field', default='date')) or '')[:10]
        if date and date < since:
            continue
        items.append({'source': 'Zacks Research', 'ticker': ticker, 'form': 'Research',
                      'title': str(_path(d, setting(store, 'zacks_research_title_field', default='title')) or ''),
                      'date': date,
                      'url': str(_path(d, setting(store, 'zacks_research_url_field', default='url')) or ''),
                      'summary': str(_path(d, setting(store, 'zacks_research_summary_field',
                                                      default='summary')) or '')[:500]})
    return items


def run(store: dict, actor: str, today: dt.date, get=http_get, get_json=http_json, days: int = 7,
        tickers=None) -> dict:
    since = (today - dt.timedelta(days=days)).isoformat()
    forms = [f.strip() for f in setting(store, 'sec_forms', default=DEFAULT_FORMS).split(',') if f.strip()]
    types = {r['symbol'].upper(): r.get('security_type') for r in store['portfolio']}
    tickers = tickers or [t for t in universe(store) if types.get(t) not in SKIP_TYPES]
    inbox = store.setdefault('inbox', [])
    known = {i['url'] for i in inbox if i.get('url')}
    added, errors = 0, []
    use_edgar = setting(store, 'sec_enabled', default='yes') != 'no'
    for ticker in tickers:
        found = []
        try:
            if use_edgar:
                found += _edgar_items(store, ticker, forms, since, get)
            found += _zacks_items(store, ticker, since, get_json)
        except ConnectorError as exc:
            errors.append(f'{ticker}: {exc}')
            if 'contact e-mail' in str(exc):
                break
            continue
        for item in found:
            if item['url'] and item['url'] in known:
                continue
            item.update({'id': _next_id(inbox, today), 'status': 'New', 'pulled': today.isoformat()})
            inbox.append(item)
            known.add(item['url'])
            added += 1
    text = f'{added} new research items from {len(tickers)} securities (last {days} days)'
    log_run(store, 'research', actor, text, errors, {'added': added})
    return {'added': added, 'errors': errors, 'text': text}


def _next_id(inbox, today):
    base = f"INB-{today.strftime('%Y%m%d')}-"
    used = [int(i['id'][len(base):]) for i in inbox if str(i.get('id', '')).startswith(base)]
    return f'{base}{max(used, default=0) + 1:03d}'


def open_items(store):
    return [i for i in store.get('inbox', []) if i.get('status') == 'New']


def evidence_defaults(store: dict, item: dict, today: dt.date) -> dict:
    """Pre-filled RCC-002 fields for logging an inbox item as evidence (operator confirms)."""
    holding = next((r for r in store['portfolio'] if r['symbol'].upper() == (item.get('ticker') or '').upper()),
                   None)
    form = (item.get('form') or '').upper()
    material = form == '8-K'
    return {
        'date_received': today.isoformat(), 'evidence_date': item.get('date') or today.isoformat(),
        'record_type': 'Certified Holding' if holding else 'Research Candidate',
        'ticker': item.get('ticker', ''), 'subject': (holding or {}).get('security') or item.get('ticker', ''),
        'activity_type': 'Material Corporate Event' if material else (
            'Company Review' if item.get('source') == 'SEC EDGAR' else 'Other Research Signal'),
        'category': 'Earnings and Guidance' if form in ('10-Q', '10-K') else 'Other',
        'materiality': 'Moderate', 'direction': 'Unclear',
        'reliability': 'Primary — Verified' if item.get('source') == 'SEC EDGAR' else 'Secondary — Verified',
        'source_type': 'Company Filing' if item.get('source') == 'SEC EDGAR' else 'Other',
        'publisher': item.get('source', ''), 'source_ref': item.get('url', ''),
        'summary': item.get('title', '') if blank(item.get('summary')) else
        f"{item.get('title', '')} — {item.get('summary', '')}"[:400],
        'thesis_sensitivity': 'Medium', 'reviewer': setting(store, 'evidence_reviewer',
                                                            default='Research Committee'),
        'due_date': (today + dt.timedelta(days=7)).isoformat(), 'status': 'Under Review', 'verified': 'Yes',
        'miar_action': 'Incremental Update' if form in ('10-Q', '10-K', '8-K') else 'None',
        'thesis_impact': 'Under Review', 'conviction_rec': 'No Change', 'candidate_replacement': 'None',
        'pew_referral': 'No', 'disposition': 'Pending',
    }
