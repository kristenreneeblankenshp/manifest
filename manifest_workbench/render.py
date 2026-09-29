"""Terminal rendering: tables, record cards, executive tiles and status colours.

Colours follow the CISC-001 convention: green = passed / aligned, amber = input,
review or committee attention required, red = decision or control exception.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import textwrap

from . import schema as S

RESET, BOLD, DIM = '\033[0m', '\033[1m', '\033[2m'
RED, GREEN, AMBER, GOLD, BLUE, CYAN = '\033[31m', '\033[32m', '\033[33m', '\033[93m', '\033[34m', '\033[36m'

GREEN_STATES = {
    'PASS', 'PASS — STAGE GATE', 'CONTROL CLEAR', 'OPEN — ON TRACK', 'CLOSED', 'ELIGIBLE',
    'CERTIFIED HOLDING', 'CURRENT', 'COMPLETE', 'WITHIN BAND', 'NO ACTION', 'NO REFERRAL',
    'NO CHANGE', 'ACTIVE', 'ACTIVE — CONTROLS CLEAR', 'NO REFERRAL REQUIRED',
    'ELIGIBLE FOR ROUTING', 'CERTIFIED 100.00%', 'NO ACTIVE RECORDS', 'ACTIVE — INSTALLED',
    'INACTIVE / CLOSED', 'DECISION RECORDED', 'NONE', 'NO ACTIVE CANDIDATE', 'ADVANCE',
    'READY — NO CANDIDATES', 'READY — NO RECORDS LOADED', 'RCC READY — NO EVIDENCE LOADED',
}
RED_MARKERS = ('FAIL', 'DUPLICATE', 'OVERDUE', 'NOT ELIGIBLE', 'ERROR', 'MISMATCH', 'ESCALATE',
               'MATERIAL EVENT', 'BELOW BAND', 'ABOVE BAND', 'ACTION REQUIRED', 'BLOCK', '#VALUE!',
               'TICKER NOT FOUND')


class Style:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    @classmethod
    def detect(cls, force_off: bool = False) -> 'Style':
        on = (not force_off and 'NO_COLOR' not in os.environ and hasattr(sys.stdout, 'isatty')
              and sys.stdout.isatty())
        return cls(on)

    def paint(self, text: str, *codes: str) -> str:
        if not self.enabled or not codes or text == '':
            return text
        return ''.join(codes) + text + RESET

    def status(self, text: str) -> str:
        if not text:
            return text
        upper = str(text).upper()
        if upper in GREEN_STATES:
            return self.paint(text, GREEN)
        if any(m in upper for m in RED_MARKERS):
            return self.paint(text, RED)
        return self.paint(text, AMBER)


def width() -> int:
    return max(60, shutil.get_terminal_size((120, 40)).columns)


def fmt(value, vtype: str = S.TEXT) -> str:
    if value is None or value == '':
        return ''
    if vtype == S.PERCENT and isinstance(value, (int, float)):
        return f'{value * 100:.2f}%'
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, float):
        return f'{value:.2f}'.rstrip('0').rstrip('.') if not value.is_integer() else str(int(value))
    return str(value)


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:max(1, n - 1)] + '…'


def table(style: Style, headers, rows, status_cols=(), max_col=34, total_width=None) -> str:
    """Render rows (lists of already-formatted strings) as an aligned text table."""
    total_width = total_width or width()
    if not rows:
        return style.paint('  (no records)', DIM)
    ncol = len(headers)
    widths = [min(max_col, max(min(len(str(headers[i])), 10), *(len(r[i]) for r in rows)))
              for i in range(ncol)]
    budget = total_width - 2 * (ncol - 1) - 2
    # Shrink the widest free-text columns first; keep short columns (IDs, dates, codes) whole.
    for floor_cap in (16, 6):
        floor = [min(w, floor_cap) for w in widths]
        floor[0] = widths[0]  # the record key stays readable
        while sum(widths) > budget:
            slack = [w - f for w, f in zip(widths, floor)]
            if max(slack) <= 0:
                break
            widths[slack.index(max(slack))] -= 1
    status_idx = {headers.index(c) for c in status_cols if c in headers}
    out = ['  ' + '  '.join(style.paint(_clip(str(h), widths[i]).ljust(widths[i]), BOLD)
                            for i, h in enumerate(headers))]
    out.append('  ' + '  '.join('─' * w for w in widths))
    for r in rows:
        cells = []
        for i, cell in enumerate(r):
            text = _clip(cell, widths[i]).ljust(widths[i])
            cells.append(style.status(text.rstrip()) + ' ' * (len(text) - len(text.rstrip()))
                         if i in status_idx else text)
        out.append('  ' + '  '.join(cells).rstrip())
    return '\n'.join(out)


def title(style: Style, heading: str, subtitle: str = '') -> str:
    w = min(width(), 120)
    bar = '═' * w
    lines = [style.paint(bar, GOLD), style.paint(' ' + heading, BOLD, GOLD)]
    if subtitle:
        lines += [' ' + line for line in textwrap.wrap(subtitle, w - 2)]
    lines.append(style.paint(bar, GOLD))
    return '\n'.join(lines)


def section(style: Style, heading: str) -> str:
    return '\n' + style.paint(heading.upper(), BOLD, CYAN)


def tiles(style: Style, items, per_row=None) -> str:
    """Executive-state tiles: [(label, value), ...]."""
    w = min(width(), 120)
    tile_w = 24
    if per_row is None:
        per_row = max(1, (w - 2) // (tile_w + 3))
        rows = -(-len(items) // per_row)
        per_row = -(-len(items) // rows)  # balance the rows
    out = []
    for start in range(0, len(items), per_row):
        chunk = items[start:start + per_row]
        inner = [max(tile_w, len(str(label)) + 2, len(str(v)) + 2) for label, v in chunk]
        top = ' ' + ' '.join('┌' + '─' * n + '┐' for n in inner)
        labels = ' ' + ' '.join('│' + style.paint(_clip(' ' + str(label), n).ljust(n), DIM) + '│'
                                for (label, _), n in zip(chunk, inner))
        values = ' ' + ' '.join('│' + _tile_value(style, str(value), n) + '│'
                                for (_, value), n in zip(chunk, inner))
        bottom = ' ' + ' '.join('└' + '─' * n + '┘' for n in inner)
        out += [top, labels, values, bottom]
    return '\n'.join(out)


def _tile_value(style: Style, value: str, n: int) -> str:
    text = (' ' + value).ljust(n)
    if value.isdigit():
        return style.paint(text, BOLD)
    return ' ' + style.status(value) + ' ' * (n - len(value) - 1)


def record(style: Style, table: S.Table, row: dict, locked_keys=()) -> str:
    """Vertical record card listing every field with its column and kind."""
    marks = {S.INPUT: 'input', S.AUTO: 'calc', S.LINK: 'link', S.LOCKED: 'locked'}
    label_w = max(len(f.header) for f in table.fields) + 1
    value_w = max(20, min(width(), 140) - label_w - 16)
    lines = []
    for f in table.fields:
        kind = 'locked' if f.key in locked_keys else marks[f.kind]
        value = fmt(row.get(f.key), f.vtype)
        wrapped = textwrap.wrap(value, value_w) or ['']
        tag = style.paint(f'{f.col:>2} {kind:<6}', DIM)
        shown = style.status(wrapped[0]) if f.kind == S.AUTO and f.vtype == S.TEXT else wrapped[0]
        if kind == 'input':
            label = style.paint(f.header.ljust(label_w), BLUE)
        else:
            label = f.header.ljust(label_w)
        lines.append(f'  {tag}  {label} {shown}')
        for extra in wrapped[1:]:
            lines.append(' ' * (label_w + 14) + extra)
    return '\n'.join(lines)


def paragraph(text: str, indent: str = '  ') -> str:
    w = min(width(), 120) - len(indent)
    out = []
    for para in text.split('\n'):
        out.extend(textwrap.wrap(para, w, initial_indent=indent, subsequent_indent=indent) or [''])
    return '\n'.join(out)
