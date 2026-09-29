"""Controlled edits: validation, locks, stage gates and the audit trail.

Every write goes through this module so the workbook's operating rules hold:
calculated and linked cells are never overwritten, certified MFPDF data is
locked, record identifiers are unique and immutable, controlled fields accept
only their validation-list values, and a candidate advances only after its
current stage gate passes.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Iterable, Optional

from . import engine
from . import schema as S
from .engine import blank, same


class OpError(Exception):
    pass


ID_FORMATS = {
    'evidence': ('evidence_id', 'EVD', 'date_received'),
    'review': ('review_id', 'MIR', 'review_date'),
    'pipeline': ('candidate_id', 'MCP', 'intake_date'),
}

# Linear stage order used by `pipeline advance`.
STAGE_PATH = ('Intake', 'Evidence Gathering', 'MIAR Review', 'Eligibility Review',
              'Candidate Comparison', 'Committee Review', 'Approved for MASR',
              'Referred to PEW-004')
STAGE_RANK = {**{s: i for i, s in enumerate(STAGE_PATH)},
              'On Watch': len(STAGE_PATH), 'Rejected': len(STAGE_PATH) + 1,
              'Closed': len(STAGE_PATH) + 1, 'Removed': len(STAGE_PATH) + 1}


# --------------------------------------------------------------------------- value parsing

def _canon(text: str) -> str:
    text = unicodedata.normalize('NFKC', str(text)).replace('—', '-').replace('–', '-')
    return re.sub(r'\s+', ' ', text).strip().casefold()


def match_choice(field: S.Field, raw) -> object:
    """Return the canonical list value for ``raw`` (exact, dash-insensitive or unique prefix)."""
    choices = field.choices
    if field.vtype == S.INT:
        try:
            value = int(str(raw).strip().lstrip('#'))
        except ValueError:
            raise OpError(f"{field.header}: '{raw}' is not one of {list(choices)}") from None
        if value not in choices:
            raise OpError(f"{field.header}: {value} is not one of {list(choices)}")
        return value
    wanted = _canon(raw)
    exact = [c for c in choices if _canon(c) == wanted]
    if exact:
        return exact[0]
    prefix = [c for c in choices if _canon(c).startswith(wanted)]
    if len(prefix) == 1:
        return prefix[0]
    hint = f' (ambiguous: {prefix})' if prefix else ''
    raise OpError(f"{field.header}: '{raw}' is not a controlled value{hint}. "
                  f"Allowed: {', '.join(map(str, choices))}")


def parse_value(field: S.Field, raw, today: dt.date):
    """Parse command-line text into a stored value. Empty text clears the field."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ''):
        return None
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if field.choices is not None:
        return match_choice(field, text)
    if field.vtype == S.DATE:
        if text.lower() == 'today':
            return today.isoformat()
        try:
            return dt.date.fromisoformat(text).isoformat()
        except ValueError:
            raise OpError(f"{field.header}: '{text}' is not a date (use YYYY-MM-DD)") from None
    if field.vtype in (S.NUMBER, S.INT):
        try:
            value = float(text.replace(',', '').lstrip('$'))
        except ValueError:
            raise OpError(f"{field.header}: '{text}' is not a number") from None
        return int(value) if value.is_integer() else value
    if field.vtype == S.PERCENT:
        pct = text.endswith('%')
        try:
            value = float(text.rstrip('%'))
        except ValueError:
            raise OpError(f"{field.header}: '{text}' is not a weight (e.g. 3.02% or 0.0302)") from None
        # Weights above 1 are read as percentage points: no single position may exceed 4%.
        return value / 100 if pct or value > 1 else value
    return text


def parse_assignments(table: S.Table, pairs: Iterable[str], today: dt.date) -> dict:
    out = {}
    for pair in pairs:
        if '=' not in pair:
            raise OpError(f"Expected field=value, got '{pair}'")
        name, raw = pair.split('=', 1)
        try:
            field = table.field(name)
        except KeyError as exc:
            raise OpError(str(exc.args[0])) from None
        out[field.key] = (field, parse_value(field, raw, today))
    return out


# --------------------------------------------------------------------------- record lookup

def find(store: dict, table: str, key: str) -> tuple:
    """Locate a stored record by its primary key; returns (index, record)."""
    rows = store[table]
    if table in ('portfolio', 'conviction', 'miar'):
        for pos, alloc in enumerate(store['portfolio']):
            if same(alloc.get('symbol'), key):
                while len(rows) <= pos:
                    rows.append({})
                return pos, rows[pos]
        raise OpError(f"'{key}' is not a certified MFPDF holding")
    if table == 'masr':
        for pos, r in enumerate(rows):
            linked = r.get('_linked')
            ticker = store['portfolio'][linked]['symbol'] if linked is not None else r.get('ticker')
            if same(ticker, key) or same(r.get('masr_id'), key):
                return pos, r
        raise OpError(f"No MASR registry record for '{key}'")
    field = S.KEYS[table]
    for pos, r in enumerate(rows):
        if same(r.get(field), key):
            return pos, r
    raise OpError(f"No {table} record '{key}'")


# --------------------------------------------------------------------------- audit

def audit(store: dict, actor: str, action: str, table: str, record: str,
          field: Optional[str] = None, old=None, new=None) -> None:
    store['audit'].append({
        'ts': dt.datetime.now().isoformat(timespec='seconds'),
        'actor': actor, 'action': action, 'table': table, 'record': record,
        'field': field, 'old': old, 'new': new,
    })


# --------------------------------------------------------------------------- edits

def _check_editable(store: dict, table: S.Table, record: dict, field: S.Field) -> None:
    if field.kind in (S.AUTO, S.LINK):
        raise OpError(f'{field.header} ({field.col}) is calculated/linked and cannot be edited')
    if field.kind == S.LOCKED:
        raise OpError(f'{field.header} ({field.col}) is certified MFPDF data. Changes require a '
                      'new certified MFPDF version through PEW-007; the workbench may not alter it')
    if table.name == 'masr' and record.get('_linked') is not None:
        if field.key in S.MASR_CERTIFIED_LINKED:
            raise OpError(f'{field.header} is linked to the certified MFPDF for certified holdings')
        if field.key in S.MASR_CERTIFIED_LOCKED:
            raise OpError('Certified Portfolio Holdings remain certified unless governance changes '
                          f'the MFPDF; {field.header} cannot be edited here')
    if table.name in ID_FORMATS and field.key == ID_FORMATS[table.name][0]:
        raise OpError(f'{field.header} is immutable once assigned')


def set_fields(store: dict, table_name: str, key: str, pairs: Iterable[str], actor: str,
               today: dt.date) -> dict:
    """Apply field=value edits to one record. Returns the updated stored record."""
    table = S.TABLES[table_name]
    pos, record = find(store, table_name, key)
    changes = parse_assignments(table, pairs, today)
    if not changes:
        raise OpError('Nothing to change')
    for fkey, (field, value) in changes.items():
        _check_editable(store, table, record, field)
        _check_unique(store, table_name, fkey, value, record)
    if table_name == 'pipeline' and 'stage' in changes:
        _check_stage_move(store, record, changes['stage'][1], today)
    label = _label(store, table_name, record, pos)
    for fkey, (field, value) in changes.items():
        old = record.get(fkey)
        if old == value:
            continue
        if value is None:
            record.pop(fkey, None)
        else:
            record[fkey] = value
        audit(store, actor, 'set', table_name, label, fkey, old, value)
    return record


def add_record(store: dict, table_name: str, pairs: Iterable[str], actor: str,
               today: dt.date) -> dict:
    """Create a record in a register (evidence, review, masr, pipeline)."""
    if table_name not in ('evidence', 'review', 'masr', 'pipeline'):
        raise OpError(f'Records cannot be added to {table_name}')
    table = S.TABLES[table_name]
    rows = store[table_name]
    if len(rows) >= table.capacity:
        raise OpError(f'{table.sheet} is at its controlled capacity of {table.capacity} records')
    changes = parse_assignments(table, pairs, today)
    record = {}
    for fkey, (field, value) in changes.items():
        if field.kind in (S.AUTO, S.LINK):
            raise OpError(f'{field.header} ({field.col}) is calculated and cannot be entered')
        if value is not None:
            record[fkey] = value

    if table_name in ID_FORMATS:
        id_key, prefix, date_key = ID_FORMATS[table_name]
        record.setdefault(date_key, today.isoformat())
        if blank(record.get(id_key)):
            record[id_key] = next_id(store, table_name, record[date_key])
        pattern = rf'^{prefix}-\d{{8}}-\d{{3}}$'
        if not re.match(pattern, record[id_key]):
            raise OpError(f'{table.field(id_key).header} must follow {prefix}-YYYYMMDD-###')
        if any(same(r.get(id_key), record[id_key]) for r in rows):
            raise OpError(f'Duplicate {table.field(id_key).header} {record[id_key]} is blocked')

    if table_name == 'review':
        if blank(record.get('ticker')):
            raise OpError('A review must name one certified holding (ticker=...)')
        find(store, 'miar', record['ticker'])
    if table_name == 'masr':
        if blank(record.get('ticker')):
            raise OpError('A registry record requires a ticker')
        record['ticker'] = record['ticker'].upper()
        for fkey in ('ticker', 'masr_id'):
            _check_unique(store, 'masr', fkey, record.get(fkey), record)
    if table_name == 'pipeline':
        if blank(record.get('ticker')):
            raise OpError('A candidate requires a ticker (ticker=...)')
        record['ticker'] = record['ticker'].upper()
        record.setdefault('stage', 'Intake')
        if record['stage'] != 'Intake':
            raise OpError("New candidates enter at 'Intake'; advance them through the stage gates")
    if table_name == 'evidence' and not blank(record.get('ticker')):
        record['ticker'] = record['ticker'].upper()

    rows.append(record)
    audit(store, actor, 'add', table_name, _label(store, table_name, record))
    return record


UNIQUE = {('masr', 'masr_id'): 'canonical MASR ID', ('masr', 'ticker'): 'ticker',
          ('miar', 'miar_id'): 'canonical MIAR ID'}


def _check_unique(store: dict, table_name: str, fkey: str, value, record: dict) -> None:
    """One canonical identifier and one active registry row per security."""
    what = UNIQUE.get((table_name, fkey))
    if what is None or blank(value):
        return
    for pos, other in enumerate(store[table_name]):
        if other is record:
            continue
        current = other.get(fkey)
        if table_name == 'masr' and fkey == 'ticker' and other.get('_linked') is not None:
            current = store['portfolio'][other['_linked']]['symbol']
        if same(current, value):
            raise OpError(f"Duplicate {what} '{value}' is blocked; it already belongs to "
                          f"{_label(store, table_name, other, pos)}. Reconcile the existing record")


def next_id(store: dict, table_name: str, on_date) -> str:
    id_key, prefix, _ = ID_FORMATS[table_name]
    stamp = engine.as_date(on_date).strftime('%Y%m%d')
    base = f'{prefix}-{stamp}-'
    used = [int(r[id_key][len(base):]) for r in store[table_name]
            if isinstance(r.get(id_key), str) and r[id_key].startswith(base)
            and r[id_key][len(base):].isdigit()]
    return f'{base}{max(used, default=0) + 1:03d}'


def _label(store, table_name, record, pos=None) -> str:
    if table_name in ('portfolio', 'conviction', 'miar') and pos is not None:
        return store['portfolio'][pos]['symbol']
    if table_name == 'masr':
        linked = record.get('_linked')
        return store['portfolio'][linked]['symbol'] if linked is not None else record.get('ticker', '?')
    return str(record.get(S.KEYS[table_name], '?'))


# --------------------------------------------------------------------------- stage gates

def _candidate_view(store: dict, record: dict, today: dt.date) -> dict:
    wb = engine.Workbench(store, today)
    for row in wb.pipeline:
        if same(row.get('candidate_id'), record.get('candidate_id')):
            return row
    raise OpError('Candidate not found')


def _check_stage_move(store: dict, record: dict, target: str, today: dt.date) -> None:
    current = record.get('stage')
    if target is None:
        raise OpError('Candidate Stage is required')
    if same(current, target):
        return
    if engine.isin(current, engine.CLOSED_STAGES):
        raise OpError(f"Candidate is {current}; closed records keep their final disposition. "
                      "Open a new candidate record (e.g. a Reinstatement Review) instead")
    backward = STAGE_RANK.get(target, 99) < STAGE_RANK.get(current, 0)
    if backward:
        return
    view = _candidate_view(store, record, today)
    if view['gate_result'] != engine.PASS_GATE:
        raise OpError(f"Stage gate at '{current}' is {view['gate_result']}. "
                      f"{view['next_action']} before advancing.")


def advance(store: dict, candidate_id: str, actor: str, today: dt.date,
            target: Optional[str] = None) -> tuple:
    """Move a candidate one stage forward (or to ``target``) once its current gate passes."""
    _, record = find(store, 'pipeline', candidate_id)
    current = record.get('stage')
    if target is None:
        if current not in STAGE_PATH or current == STAGE_PATH[-1]:
            raise OpError(f"No default next stage after '{current}'; use --to STAGE")
        target = STAGE_PATH[STAGE_PATH.index(current) + 1]
    else:
        target = match_choice(S.PIPELINE.field('stage'), target)
    if same(target, current):
        raise OpError(f"Candidate is already at '{current}'")
    if STAGE_RANK.get(target, 99) <= STAGE_RANK.get(current, 0):
        raise OpError(f"'{target}' is not ahead of '{current}'; use 'pipeline set' to move back")
    set_fields(store, 'pipeline', candidate_id, [f'stage={target}'], actor, today)
    return current, target
