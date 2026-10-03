"""Generic list / record editor for every workbook table."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import ops
from .. import schema as S
from ..cli import LIST_COLUMNS, STATUS_COLUMNS
from ..engine import blank
from .auth import actor
from .common import back, mutate, set_fields, wb
from .filters import today

bp = Blueprint('tables', __name__)


def _can_add(spec):
    return spec.mode == 'slots' or spec.name in ops.ID_FORMATS or spec.name == 'masr'


def _table(name):
    table = S.TABLES.get(name)
    if table is None:
        abort(404)
    return table


def _key_of(table, row, i):
    if table.mode == 'slots':
        return str(i + 1)
    if table.mode == 'positional':
        return row.get('symbol') or row.get('ticker')
    return row.get(table.key) or str(i + 1)


@bp.route('/t/<table>')
def listing(table):
    spec = _table(table)
    if spec.mode == 'single':
        return redirect(url_for('tables.record', table=table, key='_'))
    w = wb()
    rows = w.table(table)
    if table == 'masr':
        rows = [r for r in rows if not blank(r.get('ticker'))]
    keyed = [(_key_of(spec, r, i), r) for i, r in enumerate(rows)]
    if spec.mode == 'slots':
        keyed = [(k, r) for k, r in keyed if any(not blank(v) for f, v in r.items() if not f.startswith('_'))]
    q = request.args.get('q', '').strip().lower()
    if q:
        keyed = [(k, r) for k, r in keyed if q in ' '.join(str(v) for v in r.values()).lower()]
    cols = [c for c in (LIST_COLUMNS.get(table) or spec.keys()) if c != '_slot']
    fields = [spec.field(c) for c in cols]
    extra = {}
    if table == 'sleeves':
        extra['totals'] = w.pew().sleeve_totals()
    if table == 'portfolio':
        extra['totals'] = w.portfolio_totals()
    return render_template('table.html', spec=spec, rows=keyed, fields=fields, status_cols=STATUS_COLUMNS,
                           q=q, extra=extra, can_add=_can_add(spec))


@bp.route('/t/<table>/<key>', methods=['GET', 'POST'])
def record(table, key):
    spec = _table(table)
    k = None if spec.mode == 'single' else key
    if request.method == 'POST':
        values = {f: v for f, v in request.form.items() if f not in ('_csrf', 'next')}
        n = mutate(lambda s: set_fields(s, table, k, values))
        if n is not None:
            flash(f'Saved ({n} change(s)).' if n else 'No changes.', 'ok' if n else 'warn')
        return back('tables.record', table=table, key=key)
    w = wb()
    try:
        if spec.mode == 'single':
            row = w.record(table)
        else:
            pos, _ = ops.find(w.store, table, key)
            rows = w.table(table)
            row = rows[pos] if pos < len(rows) else {}
    except ops.OpError:
        abort(404)
    locked = ()
    if table == 'masr' and row.get('_linked') is not None:
        locked = S.MASR_CERTIFIED_LINKED + S.MASR_CERTIFIED_LOCKED
    if table == 'mandate' and row.get('_computed'):
        locked = ('operating_value', 'status')
    from ..engine import missing_fields
    history = [e for e in reversed(w.store['audit']) if e.get('table') == table
               and str(e.get('record')).lower() in (str(key).lower(), str(row.get(spec.key, '')).lower())][:30]
    return render_template('record.html', spec=spec, row=row, key=key, locked=locked,
                           missing=missing_fields(table, row) if table in ('evidence', 'miar', 'review', 'masr',
                                                                            'pipeline') else [],
                           history=history, status_cols=STATUS_COLUMNS)


@bp.route('/t/<table>/new', methods=['GET', 'POST'])
def new(table):
    spec = _table(table)
    if not _can_add(spec):
        abort(404)
    if request.method == 'POST':
        pairs = [f'{k}={v}' for k, v in request.form.items() if k not in ('_csrf', 'next') and v.strip()]
        rec = mutate(lambda s: ops.add_record(s, table, pairs, actor(), today()))
        if rec and rec is not True:
            flash('Record added.', 'ok')
            if spec.mode == 'slots':
                return redirect(url_for('tables.listing', table=table))
            return redirect(url_for('tables.record', table=table, key=rec.get(spec.key)))
    return render_template('record_new.html', spec=spec)


@bp.route('/t/<table>/<key>/clear', methods=['POST'])
def clear(table, key):
    mutate(lambda s: ops.clear_record(s, table, key, actor()), 'Row cleared (audited).')
    return redirect(url_for('tables.listing', table=table))
