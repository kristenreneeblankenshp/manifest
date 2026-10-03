"""Shared helpers for the web views."""

from __future__ import annotations

from flask import flash, redirect, request, url_for

from .. import ops
from ..connectors import ConnectorError
from ..engine import Workbench
from .auth import actor, repo, safe_next
from .filters import today

ERRORS = (ops.OpError, ValueError, KeyError, ConnectorError)


def wb(store=None) -> Workbench:
    return Workbench(store if store is not None else repo().read(), today())


def mutate(fn, success=None):
    """Run ``fn(store)`` inside a locked transaction; flash errors instead of raising."""
    try:
        with repo().transaction() as store:
            result = fn(store)
    except ERRORS as exc:
        msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        flash(str(msg), 'error')
        return None
    if success:
        flash(success() if callable(success) else success, 'ok')
    return result if result is not None else True


def back(default='core.console', **kw):
    target = request.form.get('next') or request.args.get('next') or ''
    if safe_next(target):
        return redirect(target)
    return redirect(url_for(default, **kw))


def set_fields(store, table, key, form_values: dict):
    """Apply submitted values that differ from the stored ones (validated by ops)."""
    from .. import render as R
    from .. import schema as S
    spec = S.TABLES[table]
    _, rec = ops.find(store, table, key if spec.mode != 'single' else None)
    pairs = []
    for name, raw in form_values.items():
        try:
            f = spec.field(name)
        except KeyError:
            continue
        if f.kind not in (S.INPUT,) or name != f.key:
            continue
        current = R.fmt(rec.get(f.key), f.vtype)
        if f.vtype == S.PERCENT and rec.get(f.key) not in (None, ''):
            current = f'{rec[f.key] * 100:.2f}%'
        if (raw or '').strip() != current:
            pairs.append(f'{f.key}={raw}')
    if pairs:
        ops.set_fields(store, table, key if spec.mode != 'single' else None, pairs, actor(), today())
    return len(pairs)
