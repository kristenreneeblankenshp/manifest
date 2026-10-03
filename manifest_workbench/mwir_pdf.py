"""Render the official 8-page MWIR (11 x 8.5 in landscape) with ReportLab.

Layout follows the console's HTML preview (``web/static/mwir.css``) at 0.75 pt per CSS pixel.
Long narrative blocks shrink their type to fit their space instead of spilling off the page.
"""

from __future__ import annotations

import datetime as dt
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph

from . import mwir as MW

W, H = landscape(LETTER)            # 792 x 612
ML, MR, MT, MB = 42, 42, 30, 24     # page padding (40/56/32 px)
CW = W - ML - MR                    # content width

INK, NAVY, BRASS, MUTED, SOFT = (HexColor(c) for c in ('#1a1d24', '#1d2b4a', '#8a6a2e', '#5b5f68', '#3a3d45'))
RULE, HAIR, PAPER, TINT, WARN = (HexColor(c) for c in ('#cfcac0', '#ebe8e1', '#fdfcf9', '#f1eee6', '#843710'))
SANS, BOLD, SERIF, MONO, MONOB = 'Helvetica', 'Helvetica-Bold', 'Times-Bold', 'Courier', 'Courier-Bold'

# Characters outside the PDF standard fonts' encoding, mapped to safe equivalents.
SAFE = str.maketrans({'≤': '<=', '≥': '>=', '→': '->', '←': '<-', '✓': 'v', '✗': 'x', '−': '-',
                      ' ': ' ', ' ': ' ', ' ': ' '})


def _safe(text) -> str:
    text = str(text if text is not None else '').translate(SAFE)
    return text.encode('cp1252', errors='replace').decode('cp1252')


def _style(size, font=SANS, color=INK, leading=None):
    return ParagraphStyle('s', fontName=font, fontSize=size, leading=leading or size * 1.42, textColor=color,
                          alignment=TA_LEFT)


class Page:
    """Drawing helpers with a top-down y coordinate."""

    def __init__(self, c, v, n, final):
        self.c, self.v, self.n, self.final = c, v, n, final

    def y(self, top):
        return H - top

    def text(self, x, top, s, font=SANS, size=9, color=INK, space=0.0, align='left'):
        s = _safe(s)
        c = self.c
        c.setFillColor(color)
        width = stringWidth(s, font, size) + space * max(len(s) - 1, 0)
        if align == 'right':
            x -= width
        elif align == 'center':
            x -= width / 2
        t = c.beginText(x, self.y(top) - size * 0.8)
        t.setFont(font, size)
        t.setCharSpace(space)
        t.textLine(s)
        if space:
            t.setCharSpace(0)  # text state persists across text objects in PDF
        c.drawText(t)
        return width

    def fit(self, s, font, size, width):
        s = _safe(s)
        if stringWidth(s, font, size) <= width:
            return s
        while s and stringWidth(s + '…', font, size) > width:
            s = s[:-1]
        return s.rstrip() + '…'

    def para(self, x, top, width, html, size=9.4, font=SANS, color=INK, max_h=None, leading=1.45, min_scale=0.72):
        """Draw a wrapped paragraph; shrink to fit max_h. Returns the height used."""
        scale = 1.0
        while True:
            st = _style(size * scale, font, color, size * scale * leading)
            p = Paragraph(html, st)
            _, h = p.wrap(width, 10_000)
            if max_h is None or h <= max_h or scale <= min_scale:
                break
            scale -= 0.04
        p.drawOn(self.c, x, self.y(top) - h)
        return h

    def rect(self, x, top, w, h, fill=None, stroke=None, width=0.75):
        c = self.c
        if fill is not None:
            c.setFillColor(fill)
        if stroke is not None:
            c.setStrokeColor(stroke)
            c.setLineWidth(width)
        c.rect(x, self.y(top) - h, w, h, stroke=1 if stroke is not None else 0, fill=1 if fill is not None else 0)

    def hline(self, x, top, w, color=HAIR, width=0.75):
        c = self.c
        c.setStrokeColor(color)
        c.setLineWidth(width)
        c.line(x, self.y(top), x + w, self.y(top))

    def chip(self, x, top, s, bg, fg, size=8.25, h=11, max_w=None):
        s = self.fit(s, BOLD, size, (max_w or 400) - 9)
        w = stringWidth(s, BOLD, size) + 9
        self.rect(x, top, w, h, fill=HexColor(bg))
        self.text(x + 4.5, top + (h - size) / 2 + 0.6, s, BOLD, size, HexColor(fg))
        return w

    def kicker(self, x, top, s, size=8.25, color=BRASS, align='left'):
        return self.text(x, top, s, MONOB, size, color, space=size * 0.14, align=align)

    def label(self, x, top, s, size=8.25):
        return self.text(x, top, s, MONOB, size, MUTED, space=size * 0.12)

    def head(self, kicker, title, extra=''):
        top = MT
        self.kicker(ML, top, kicker)
        self.text(ML, top + 13, title, SERIF, 22.5, NAVY)
        top += 13 + 26
        if extra:
            top += self.para(ML, top, CW, escape(_safe(extra)), 9, color=MUTED) + 3
        top += 6
        self.hline(ML, top, CW, NAVY, 1.5)
        return top + 11

    def foot(self, left='MANIFEST MWIR'):
        top = H - MB - 14
        self.hline(ML, top, CW, RULE)
        self.text(ML, top + 6, left, MONO, 8.25, MUTED, space=0.8)
        self.text(W - MR, top + 6, f"WEEK ENDING {self.v['m']['week_upper']} · {self.n}/8", MONO, 8.25, MUTED,
                  space=0.8, align='right')
        return top

    def box(self, x, top, w, kicker, html, size=9.75, max_h=None, fill=TINT):
        inner = w - 24
        st = _style(size, SANS, INK, size * 1.5)
        p = Paragraph(html, st)
        _, h = p.wrap(inner, 10_000)
        if max_h and h + 30 > max_h:
            h = max_h - 30
        self.rect(x, top, w, h + 30, fill=fill, stroke=RULE)
        self.kicker(x + 12, top + 9, kicker)
        self.para(x + 12, top + 22, inner, html, size, max_h=h + 1, leading=1.5)
        return h + 30

    def watermark(self):
        if self.final:
            return
        c = self.c
        c.saveState()
        c.setFillColor(HexColor('#a3262a'))
        c.setFillAlpha(0.07)
        c.translate(W / 2, H / 2)
        c.rotate(28)
        c.setFont(BOLD, 120)
        c.drawCentredString(0, -40, 'DRAFT')
        c.restoreState()


def _b(label, text):
    return f'<font name="{BOLD}" color="#1d2b4a">{escape(_safe(label))}</font> {escape(_safe(text))}'


def _e(text):
    return escape(_safe(text))


# =========================================================================== pages

def _cover(p, v):
    d, m = v['d'], v['m']
    p.kicker(ML, MT, 'OFFICIAL PUBLICATION · FROZEN DELIVERABLES')
    p.kicker(W - MR, MT, f"PUBLISHED {m['pub_long']}", align='right')
    top = MT + 16
    p.text(ML, top, 'Weekly Institutional Report', SERIF, 28.5, NAVY)
    top += 34
    p.text(ML, top, d.get('headline', ''), BOLD, 11.25, INK, space=0.45)
    top += 17
    top += p.para(ML, top, 675, _e(d.get('subhead')), 9.75, color=SOFT, max_h=44, leading=1.5) + 8
    p.hline(ML, top, CW, NAVY, 1.5)
    top += 12

    # gauge card
    gw, gh = 247.5, 196
    p.rect(ML, top, gw, gh, fill=white, stroke=RULE)
    p.label(ML + 10.5, top + 10.5, 'MANIFEST INSTITUTIONAL GAUGE')
    cx, cy, r = ML + gw / 2, p.y(top + 24 + 90), 75
    c = p.c
    c.setLineWidth(16.5)
    for color, start, extent in (('#a3262a', 108, 72), ('#c2571a', 81, 27), ('#c9971c', 54, 27),
                                 ('#2f6f4f', 0, 54)):
        c.setStrokeColor(HexColor(color))
        c.arc(cx - r, cy - r, cx + r, cy + r, start, extent)
    c.saveState()
    c.translate(cx, cy)
    c.rotate(-v['zone']['deg'])
    c.setFillColor(INK)
    path = c.beginPath()
    path.moveTo(0, 0)
    path.lineTo(-3, 1.5)
    path.lineTo(0, 64.5)
    path.lineTo(3, 1.5)
    path.close()
    c.drawPath(path, stroke=0, fill=1)
    c.restoreState()
    c.setFillColor(INK)
    c.circle(cx, cy, 6, stroke=0, fill=1)
    p.text(cx, top + 124, str(v['zone']['value']), SERIF, 33, NAVY, align='center')
    zl = v['zone']['label']
    zw = stringWidth(zl, BOLD, 9) + 0.54 * len(zl) + 18
    p.rect(cx - zw / 2, top + 164, zw, 18, fill=HexColor(v['zone']['color']))
    p.text(cx, top + 168.5, zl, BOLD, 9, white, space=0.54, align='center')

    # compass card
    x0, w0 = ML + gw + 18, CW - gw - 18
    p.rect(x0, top, w0, gh, fill=white, stroke=RULE)
    p.label(x0 + 12, top + 9, 'INSTITUTIONAL COMPASS')
    p.hline(x0, top + 25, w0, RULE)
    row = top + 25
    lh = (gh - 25) / len(v['compass'])
    for item in v['compass']:
        p.text(x0 + 12, row + lh / 2 - 4.5, item['label'], BOLD, 9, SOFT, space=0.54)
        p.text(x0 + 12 + 144, row + lh / 2 - 6, p.fit(item['value'], MONO, 11.25, 110), MONO, 11.25, NAVY)
        p.text(x0 + 12 + 265, row + lh / 2 - 4.5, p.fit(item['note'], SANS, 9, w0 - 290), SANS, 9, MUTED)
        row += lh
        if row < top + gh - 1:
            p.hline(x0, row, w0, HAIR)
    top += gh + 14

    # executive summary
    p.kicker(ML, top, 'EXECUTIVE SUMMARY', 9)
    top += 15
    foot = H - MB - 14
    if d.get('footnote'):
        p.para(ML, foot - 34, CW, _e(d.get('footnote')), 8.5, color=MUTED, max_h=28)
    avail = (foot - 40 - top) / 2 - 6
    colw = (CW - 21) / 2
    for i, (label, text) in enumerate(v['exec_paras']):
        x = ML + (i % 2) * (colw + 21)
        y = top + (i // 2) * (avail + 8)
        p.para(x, y, colw, _b(label, text), 9.4, max_h=avail)


def _signals(p, v):
    d = v['d']
    top = p.head('MFSO COMPONENT ARCHITECTURE', 'Institutional Signal Dashboard')
    p.label(ML, top, 'COMPONENT SCORES · 0–10', 9)
    top += 16
    colw = (CW - 30) / 2
    comps = v['components']
    half = (len(comps) + 1) // 2
    for i, comp in enumerate(comps):
        x = ML + (i // half) * (colw + 30)
        y = top + (i % half) * 18
        p.text(x, y + 1.5, p.fit(comp['name'], SANS, 9.75, 108), SANS, 9.75, INK)
        p.rect(x + 121.5, y + 2, colw - 121.5 - 30, 9, fill=HAIR)
        p.rect(x + 121.5, y + 2, (colw - 151.5) * comp['pct'] / 100, 9, fill=HexColor(comp['color']))
        p.text(x + colw, y + 1, str(comp['score']), MONO, 9.75, NAVY, align='right')
    top += half * 18 + 12

    # risk tape + interpretation
    tw = 247.5
    p.label(ML, top, 'WEEKLY RISK TAPE', 9)
    p.label(ML + tw + 21, top, 'SIGNAL INTERPRETATION', 9)
    top += 15
    p.hline(ML, top, tw, NAVY)
    y = top
    for t in v['tape']:
        lw_ = p.text(ML, y + 5, p.fit(t['label'], SANS, 9.75, 120), SANS, 9.75, SOFT)
        p.text(ML + tw, y + 5, p.fit(t['value'], MONO, 9.75, tw - lw_ - 10), MONO, 9.75, INK, align='right')
        y += 20
        p.hline(ML, y, tw, HAIR)
    bottom_box = H - MB - 14 - 12 - 32 - 10
    # decision rule box height first, so interpretation can use the rest
    st = _style(9.75, SANS, INK, 14.6)
    _, rh = Paragraph(_e(d.get('decisionRule')), st).wrap(CW - 24, 10_000)
    rh = min(rh, 80)
    box_top = bottom_box - (rh + 30)
    iy, ix, iw = top, ML + tw + 21, CW - tw - 21
    bullets = v['interpretation']
    space = box_top - 10 - top
    size = 9.75
    while size > 7.5:
        hs = [Paragraph(_e(b), _style(size, leading=size * 1.45)).wrap(iw - 12, 10_000)[1] + 4.5 for b in bullets]
        if sum(hs) <= space:
            break
        size -= 0.25
    for b in bullets:
        p.c.setFillColor(INK)
        p.c.circle(ix + 3, p.y(iy + size * 0.75), 1.4, stroke=0, fill=1)
        iy += p.para(ix + 12, iy, iw - 12, _e(b), size, leading=1.45) + 4.5
    p.box(ML, box_top, CW, 'DECISION RULE', _e(d.get('decisionRule')), 9.75, max_h=rh + 30)
    ptop = bottom_box + 4
    p.rect(ML, ptop, CW, 32, fill=NAVY)
    p.kicker(ML + 13.5, ptop + 12, 'OFFICIAL POSTURE', 8.25, HexColor('#d9c79e'))
    p.text(ML + 135, ptop + 10.5, p.fit(d.get('officialPosture'), BOLD, 10.5, CW - 150), BOLD, 10.5, white,
           space=0.42)


def _macro(p, v):
    d = v['d']
    top = p.head('RATES · INFLATION · EARNINGS · GEOPOLITICS', 'Macro Stewardship & Event Map')
    events = v['events']
    ev_h = 22 + 22 * max(len(events), 1)
    foot = H - MB - 14
    ev_top = foot - 10 - ev_h
    colw = (CW - 24) / 2
    rows = (len(v['macro']) + 1) // 2
    cell_h = (ev_top - 12 - top) / rows - 12
    for i, (title, text) in enumerate(v['macro']):
        x = ML + (i % 2) * (colw + 24)
        y = top + (i // 2) * (cell_h + 12)
        p.hline(x, y, colw, RULE)
        p.kicker(x, y + 6, title, 9, NAVY)
        p.para(x, y + 20, colw, _e(text), 9.75, max_h=cell_h - 20, leading=1.5)
    p.kicker(ML, ev_top, f"FORWARD EVENT GATES · {d.get('gatesWeek') or ''}", 9)
    y = ev_top + 16
    p.hline(ML, y, CW, NAVY, 1.5)
    for e in events:
        p.text(ML, y + 7, p.fit(e[0], MONOB, 9.75, 66), MONOB, 9.75, NAVY)
        p.text(ML + 79.5, y + 7, p.fit(e[1], BOLD, 9.75, 160), BOLD, 9.75, INK)
        p.text(ML + 256.5, y + 7, p.fit(e[2], SANS, 9.75, CW - 258), SANS, 9.75, SOFT)
        y += 22
        p.hline(ML, y, CW, RULE)


def _allocation(p, v):
    d = v['d']
    top = p.head('MFPDF BASELINE · MRGES-001 EXECUTABLE CHANNEL', 'Allocation & Implementation Dashboard')
    rw = 300
    lw = CW - rw - 24
    p.label(ML, top, f"EXECUTABLE SLEEVE ALLOCATION · {v['stats']['total_fmt']}", 9)
    p.label(ML + lw + 24, top, 'TOP 10 EXECUTABLE TARGETS', 9)
    y = top + 16
    for s in v['sleeve_alloc']:
        p.text(ML, y + 1.5, p.fit(s['name'], SANS, 9.75, 146), SANS, 9.75, INK)
        track = lw - 150 - 57
        p.rect(ML + 159, y + 1, track, 10.5, fill=HAIR)
        p.rect(ML + 159, y + 1, track * s['bar'] / 100, 10.5, fill=NAVY)
        p.text(ML + lw, y + 1.5, s['fmt'], MONO, 9.75, NAVY, align='right')
        y += 16.5
    left_end = y
    x = ML + lw + 24
    y = top + 16
    for lbl, xo, al in (('TICKER', 0, 'left'), ('TARGET', 120, 'right'), ('APPROVED BAND', rw, 'right')):
        p.text(x + xo, y, lbl, BOLD, 8.25, SOFT, space=0.5, align=al)
    y += 12
    p.hline(x, y, rw, NAVY, 1.5)
    for t in v['top10']:
        p.text(x, y + 3.5, t['ticker'], MONOB, 9.75, NAVY)
        p.text(x + 120, y + 3.5, t['current_fmt'], MONO, 9.75, INK, align='right')
        p.text(x + rw, y + 3.5, t['band'], MONO, 9.75, MUTED, align='right')
        y += 16.5
        p.hline(x, y, rw, HAIR)
    top = max(left_end, y) + 12
    bw = (CW - 18) / 2
    st = _style(9, SANS, INK, 13.5)
    hb = max(Paragraph(_e(d.get(k)), st).wrap(bw - 24, 10_000)[1] for k in ('reconciliation', 'bandStandard'))
    hb = min(hb, 95)
    p.box(ML, top, bw, 'MRGES-001 CHANNEL RECONCILIATION', _e(d.get('reconciliation')), 9, max_h=hb + 30)
    p.box(ML + bw + 18, top, bw, 'TARGET / BAND STANDARD', _e(d.get('bandStandard')), 9, max_h=hb + 30)
    top += hb + 30 + 12
    p.kicker(ML, top, 'CAPITAL DEPLOYMENT HIERARCHY', 9)
    top += 16
    foot = H - MB - 14
    tiers = v['hierarchy']
    space = (foot - 8 - top) / max(len(tiers), 1)
    for i, t in enumerate(tiers):
        p.text(ML, top - 1, str(i + 1), SERIF, 13.5, BRASS)
        top += p.para(ML + 28.5, top, CW - 28.5, _e(t), 9.75, max_h=space - 4) + 4.5


def _matrix(p, v, page):
    d = v['d']
    top = p.head('HOLDING-BY-HOLDING WEIGHT GUIDANCE', f"Holding Action Matrix · {page['roman']}",
                 'MFPDF = frozen analytical baseline. Current = MRGES executable recommendation. Actual = not supplied.')
    cols = [('SLEEVE', 66, 'left'), ('TICKER', 43.5, 'left'), ('MFPDF', 46.5, 'right'), ('CURRENT', 46.5, 'right'),
            ('BAND', 79.5, 'right'), ('GUIDANCE', 112.5, 'left'), ('RATIONALE', None, 'left'), ('STATUS', 82.5, 'left')]
    gap = 7.5
    fixed = sum(w for _, w, _ in cols if w) + gap * (len(cols) - 1)
    cols = [(n, w or CW - fixed, a) for n, w, a in cols]
    xs, x = [], ML
    for _, w, _ in cols:
        xs.append(x)
        x += w + gap
    for (n, w, a), x in zip(cols, xs):
        p.text(x + (w if a == 'right' else 0), top, n, BOLD, 8.25, SOFT, space=0.5, align=a)
    top += 12
    p.hline(ML, top, CW, NAVY, 1.5)
    rows = page['rows']
    foot = H - MB - 14
    fine_h = 30 if d.get('matrixDisclaimer') else 0
    rh = min(15.5, (foot - fine_h - 10 - top) / max(len(rows), 1))
    size = 9 if rh >= 14 else 8
    for r in rows:
        y = top + (rh - size) / 2
        vals = [r['sleeve'], r['ticker'], r['mfpdf_fmt'], r['current_fmt'], r['band'], None, r.get('rationale'),
                r.get('status')]
        fonts = [(SANS, MUTED), (MONOB, NAVY), (MONO, MUTED), (MONO, INK), (MONO, INK), None, (SANS, INK),
                 (SANS, INK)]
        for (n, w, a), x, val, f in zip(cols, xs, vals, fonts):
            if n == 'GUIDANCE':
                p.chip(x, top + (rh - 11) / 2, r.get('guidance') or '', r['chip_bg'], r['chip_fg'], 7.5, 11, w)
                continue
            fs = size - (0.75 if n == 'STATUS' else 0)
            p.text(x + (w if a == 'right' else 0), y, p.fit(val or '', f[0], fs, w), f[0], fs, f[1], align=a)
        top += rh
        p.hline(ML, top, CW, HAIR)
    if fine_h:
        p.para(ML, foot - 8 - fine_h + 4, CW, _e(d.get('matrixDisclaimer')), 8.5, color=MUTED, max_h=fine_h - 4)


def _zacks(p, v):
    zk = v['zk']
    top = MT
    p.kicker(ML, top, f"ZACKS UNIVERSE SCREEN · DATA AS OF {zk['as_of_upper']}")
    p.text(ML, top + 13, 'Holdings Validation Screen', SERIF, 22.5, NAVY)
    tiles_w = 4 * 52 + 3 * 4.5
    rule_h = p.para(ML, top + 41, CW - tiles_w - 20,
           'Rule: market cap above $100B and Zacks Rank 1–3 (1 Strong Buy · 2 Buy · 3 Hold). Tier 1 = Rank 1 or 2. '
           'ETFs show their ETF rank and are not held to the market-cap rule.', 9, color=MUTED)
    tx = W - MR - tiles_w
    for t in zk['tiles']:
        p.rect(tx, top + 8, 52, 40, fill=HexColor(t['bg']))
        p.text(tx + 26, top + 12, str(t['n']), SERIF, 18, HexColor(t['fg']), align='center')
        p.text(tx + 26, top + 35, t['label'], BOLD, 7.5, HexColor(t['fg']), space=0.6, align='center')
        tx += 56.5
    top = max(top + 54, top + 41 + rule_h + 6)
    p.hline(ML, top, CW, NAVY, 1.5)
    top += 10
    colw = (CW - 21) / 2
    cols = [('TICKER', 42, 'left'), ('ZACKS RANK', None, 'left'), ('MKT CAP', 54, 'right'), ('NEXT ER', 48, 'right'),
            ('SCREEN', 52.5, 'left')]
    gap = 6
    fixed = sum(w for _, w, _ in cols if w) + gap * 4
    cols = [(n, w or colw - fixed, a) for n, w, a in cols]
    foot = H - MB - 14
    box_h = 60
    rows_space = foot - 10 - box_h - 10 - top - 14
    n_rows = max(len(zk['cols'][0]), 1)
    rh = min(14.25, rows_space / n_rows)
    size = 9 if rh >= 13 else 8
    for ci, col in enumerate(zk['cols']):
        x0 = ML + ci * (colw + 21)
        xs, x = [], x0
        for _, w, _ in cols:
            xs.append(x)
            x += w + gap
        for (n, w, a), x in zip(cols, xs):
            p.text(x + (w if a == 'right' else 0), top, n, BOLD, 7.5, SOFT, space=0.45, align=a)
        y = top + 11
        p.hline(x0, y, colw, NAVY, 1.5)
        for z in col:
            ty = y + (rh - size) / 2
            p.text(xs[0], ty, z['ticker'], MONOB, size, NAVY)
            p.text(xs[1], ty, p.fit(z['rank_label'], SANS, size, cols[1][1]), SANS, size, INK)
            p.text(xs[2] + cols[2][1], ty, z['cap'], MONO, size, HexColor(z['cap_color']), align='right')
            p.text(xs[3] + cols[3][1], ty, z['er'], MONO, size, HexColor(z['er_color']), align='right')
            p.chip(xs[4], y + (rh - 10.5) / 2, z['screen'], z['bg'], z['fg'], 7.5, 10.5, cols[4][1])
            y += rh
            p.hline(x0, y, colw, HAIR)
    html = (f'<font name="{BOLD}" color="#843710">Review:</font> {_e(zk["review_text"])}<br/>'
            f'<font name="{BOLD}">Earnings within 21 days of publication:</font> {_e(zk["soon_text"])}<br/>'
            f'<font color="#5b5f68">A name under review is flagged, not dropped automatically. Framework overrides '
            f'still apply. {_e(zk["alias_text"])}</font>')
    st = _style(9, leading=13)
    _, hh = Paragraph(html, st).wrap(CW - 24, 10_000)
    hh = min(hh, box_h + 10)
    btop = foot - 10 - hh - 18
    p.rect(ML, btop, CW, hh + 18, fill=TINT, stroke=RULE)
    p.para(ML + 12, btop + 9, CW - 24, html, 9, max_h=hh + 1, leading=1.45)


def _certification(p, v):
    d, m = v['d'], v['m']
    top = p.head('PUBLICATION CONTROL RECORD', 'Certification, Client Brief & Sources')
    st = _style(9.75, leading=14.6)
    _, bh = Paragraph(_e(d.get('clientBrief')), st).wrap(CW - 24, 10_000)
    bh = min(bh, 92)
    p.box(ML, top, CW, 'CLIENT EXECUTIVE BRIEF', _e(d.get('clientBrief')), 9.75, max_h=bh + 30)
    top += bh + 30 + 10
    foot = H - MB - 14
    fresh = f'<font name="{BOLD}">DATA-FRESHNESS CERTIFICATION:</font> {_e(d.get("freshness"))}'
    _, fh = Paragraph(fresh, _style(9, leading=13)).wrap(CW, 10_000)
    fh = min(fh, 40)
    bottom = foot - 8 - 14 - fh - 6
    colw = (CW - 36) / 3

    def items(x, y, values, size=9):
        for val in values:
            h = p.para(x, y + 2, colw, _e(val), size, leading=1.3, max_h=40)
            y += h + 4.5
            p.hline(x, y, colw, HAIR)
        return y

    # deliverables + certification result
    p.label(ML, top, 'FROZEN DELIVERABLES APPLIED', 9)
    y = items(ML, top + 15, v['deliverables'])
    p.label(ML, y + 10, 'CERTIFICATION RESULT', 8.25)
    p.text(ML, y + 24, v['cert']['label'], BOLD, 11.25, HexColor(v['cert']['color']))
    if d.get('_override'):
        p.para(ML, y + 40, colw, _e(f"Issued under override: {d['_override']}"), 8, color=WARN, max_h=30)
    # control assertions
    x = ML + colw + 18
    p.label(x, top, 'CONTROL ASSERTIONS', 9)
    y = top + 15
    space = bottom - y
    size = 9 if len(v['assertions']) * 17 <= space else 8
    rh = min(17, space / max(len(v['assertions']), 1))
    for a in v['assertions']:
        lw_ = p.text(x, y + 3, p.fit(a['label'], SANS, size, colw * 0.52), SANS, size, INK)
        p.text(x + colw, y + 3, p.fit(a['result'], MONO, size, colw - lw_ - 6), MONO, size, HexColor(a['color']),
               align='right')
        y += rh
        p.hline(x, y, colw, HAIR)
    # sources
    x = ML + 2 * (colw + 18)
    p.label(x, top, 'PRIMARY EVIDENCE & MARKET SOURCES', 9)
    y = top + 15
    srcs = v['sources']
    size = 9
    while size > 7 and sum(Paragraph(_e(s), _style(size, leading=size * 1.3)).wrap(colw, 10_000)[1] + 4.5
                           for s in srcs) > bottom - y:
        size -= 0.5
    for s in srcs:
        y += p.para(x, y + 2, colw, _e(s), size, leading=1.3) + 4.5
        p.hline(x, y, colw, HAIR)
    p.para(ML, bottom + 4, CW, fresh, 9, max_h=fh + 1, leading=1.45)
    p.text(ML, foot - 8 - 12, f"Prepared for Manifest Institutional Investment System · Publication date: "
                              f"{m['pub_short']}", SANS, 9, MUTED)


# =========================================================================== entry point

def render(draft: dict, path, final: bool = False, snap: dict = None) -> None:
    doc = dict(draft['doc'])
    if final and draft.get('override'):
        doc['_override'] = draft['override']
    v = MW.model(doc, snap or draft.get('zacks') or MW.bundled_snapshot())
    c = rl_canvas.Canvas(str(path), pagesize=(W, H))
    c.setTitle(f"MWIR — Week ending {v['m']['week_upper'].title()}")
    c.setAuthor(draft.get('issued_by') or draft.get('created_by') or 'Manifest Workbench')
    c.setSubject('Manifest Weekly Institutional Report')
    pages = [_cover, _signals, _macro, _allocation,
             lambda p, v: _matrix(p, v, v['matrix_pages'][0]), lambda p, v: _matrix(p, v, v['matrix_pages'][1]),
             _zacks, _certification]
    lefts = {7: 'MANIFEST MWIR · SOURCE: ZACKS INVESTMENT RESEARCH'}
    for n, fn in enumerate(pages, start=1):
        p = Page(c, v, n, final)
        c.setFillColor(PAPER)
        c.rect(0, 0, W, H, stroke=0, fill=1)
        p.watermark()
        fn(p, v)
        left = lefts.get(n, 'MANIFEST MWIR')
        if not final:
            left += f" · DRAFT {dt.date.today().isoformat()}"
        p.foot(left)
        c.showPage()
    c.save()
