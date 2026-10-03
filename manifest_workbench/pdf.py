"""PDF rendering for report drafts (ReportLab).

Navy / gold institutional styling after the CISC-001 visual standard. Drafts carry a
DRAFT watermark; issued reports carry the version and issuing officer.
"""

from __future__ import annotations

import datetime as dt
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

NAVY = colors.HexColor('#0B1F3A')
GOLD = colors.HexColor('#C9A227')
INK = colors.HexColor('#1B2430')
MUTED = colors.HexColor('#5B6675')
ZEBRA = colors.HexColor('#F3F5F8')
RULE = colors.HexColor('#D5DAE1')

BODY = ParagraphStyle('body', fontName='Helvetica', fontSize=9.2, leading=12.6, textColor=INK,
                      alignment=TA_LEFT, spaceAfter=5)
H1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.white)
SUB = ParagraphStyle('sub', fontName='Helvetica', fontSize=10.5, leading=14, textColor=GOLD)
H2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=NAVY,
                    spaceBefore=10, spaceAfter=4)
H3 = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=9.2, leading=12, textColor=MUTED,
                    spaceBefore=6, spaceAfter=3)
CELL = ParagraphStyle('cell', fontName='Helvetica', fontSize=7.6, leading=9.4, textColor=INK)
HEAD = ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=7.6, leading=9.4, textColor=colors.white)
NOTE = ParagraphStyle('note', fontName='Helvetica-Oblique', fontSize=8, leading=10, textColor=MUTED)


def _p(text, style):
    return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)


def _table(spec, width):
    cols = spec['columns']
    rows = spec['rows']
    if not rows:
        return [_p(spec['title'], H3), _p(spec.get('empty') or 'None', NOTE)]
    # Column widths proportional to content length, bounded.
    lengths = [max([len(str(c)) for c in cols] and [len(cols[i])] +
                   [len(str(r[i])) for r in rows if i < len(r)]) for i in range(len(cols))]
    lengths = [min(max(n, 9), 60) for n in lengths]
    total = sum(lengths)
    widths = [width * n / total for n in lengths]
    data = [[_p(c, HEAD) for c in cols]] + [[_p(c, CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [('BACKGROUND', (0, 0), (-1, 0), NAVY), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
             ('LINEBELOW', (0, 0), (-1, 0), 1.2, GOLD), ('LINEBELOW', (0, 1), (-1, -1), 0.25, RULE),
             ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
             ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5)]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(style))
    return [_p(spec['title'], H3), t]


def render(draft: dict, path, final: bool = False, snap: dict = None) -> None:
    if draft.get('doc'):  # the official MWIR layout
        from .mwir_pdf import render as render_mwir
        return render_mwir(draft, path, final, snap)
    wide = draft['type'] in ('mipr', 'qer')
    pagesize = landscape(LETTER) if wide else LETTER
    doc = SimpleDocTemplate(str(path), pagesize=pagesize, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch, title=draft['title'],
                            author=draft.get('issued_by') or draft.get('created_by') or '',
                            subject=draft.get('period_label', ''))
    width = pagesize[0] - 1.2 * inch
    stamp = (f"Issued {draft['issued'][:10]} by {draft.get('issued_by')} · version {draft['version']}"
             if final else f"DRAFT · data as of {draft.get('snapshot_as_of')} · generated "
                           f"{dt.date.today().isoformat()}")

    cover = Table([[_p(draft['title'], H1)], [_p(draft.get('subtitle') or '', SUB)],
                   [_p(f"{draft['period_label']}  ·  {stamp}", SUB)]], colWidths=[width])
    cover.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), NAVY), ('LINEBELOW', (0, -1), (-1, -1), 3, GOLD),
                               ('LEFTPADDING', (0, 0), (-1, -1), 14), ('TOPPADDING', (0, 0), (-1, 0), 14),
                               ('BOTTOMPADDING', (0, -1), (-1, -1), 12)]))
    story = [cover, Spacer(1, 12)]
    for sec in draft['sections']:
        if not sec.get('include', True):
            continue
        block = [_p(sec['title'], H2)]
        for para in [p for p in (sec.get('narrative') or '').split('\n\n') if p.strip()]:
            block.append(_p(para.strip(), BODY))
        story.append(KeepTogether(block))
        for spec in sec.get('tables', []):
            story.extend(_table(spec, width))
            story.append(Spacer(1, 6))

    code = draft.get('code', '')

    def decorate(canvas, doc_):
        canvas.saveState()
        w, h = pagesize
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(1)
        canvas.line(0.6 * inch, 0.55 * inch, w - 0.6 * inch, 0.55 * inch)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.6 * inch, 0.38 * inch,
                          f"Manifest Workbench · {code} · {draft['period_label']} · No automatic trading is authorized")
        canvas.drawRightString(w - 0.6 * inch, 0.38 * inch, f'Page {doc_.page}')
        if not final:
            canvas.setFont('Helvetica-Bold', 70)
            canvas.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.08))
            canvas.translate(w / 2, h / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, 'DRAFT')
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
