"""Template filters and globals."""

from __future__ import annotations

import datetime as dt

from flask import session

from .. import render as R
from .. import schema as S
from .auth import can_edit, csrf_token, current_user

GREEN = {s.upper() for s in R.GREEN_STATES} | {'COMPLETED', 'APPROVED', 'ISSUED', 'PUBLISHED', 'CLOSED', 'READY',
                                                'SCENARIO TOTAL PASS', 'BASELINE', 'READY TO ISSUE NEW MFPDF',
                                                'CHECK PASSING', 'SIGNED OFF'}
NEUTRAL = {'NEW', 'OPEN', 'PLANNED', 'SCHEDULED', 'DRAFT', 'PENDING', 'IN PROGRESS', 'IN REVIEW', 'UNDER REVIEW',
           'NOT STARTED', 'NOT REQUIRED'}


def status_class(value) -> str:
    text = str(value or '').strip().upper()
    if not text:
        return ''
    if text in GREEN or text.startswith('PASS'):
        return 'ok'
    if any(m in text for m in R.RED_MARKERS) or text in ('REJECTED', 'NOT READY'):
        return 'bad'
    if text in NEUTRAL:
        return 'neutral'
    return 'warn'


def cell(value, vtype=S.TEXT):
    return R.fmt(value, vtype)


def pct(value, places=2):
    if value in ('', None):
        return ''
    return f'{value * 100:.{places}f}%'


def today():
    raw = session.get('as_of')
    try:
        return dt.date.fromisoformat(raw) if raw else dt.date.today()
    except ValueError:
        return dt.date.today()


def register(app):
    app.jinja_env.filters.update(status=status_class, cell=cell, pct=pct)
    app.jinja_env.globals.update(csrf_token=csrf_token, current_user=current_user, can_edit=can_edit,
                                 today=today, S=S)
