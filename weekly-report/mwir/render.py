"""Draw the MWIR PDF from a computed Report.

Layout follows the published MWIR: navy header band, gold kicker, cards and
cream call-out boxes, US Letter portrait. Pages are drawn top-down with a
cursor; if any page's content runs past the footer, rendering raises
LayoutError so an overflowing report is never published silently.
"""

from __future__ import annotations

import io
import math
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from .model import FAIL, PASS, WARN, Report, pct, zone_for

W, H = letter
M = 36  # side margin
HEADER_H = 72
FOOTER_Y = 40
CONTENT_TOP = H - HEADER_H - 22
CONTENT_BOTTOM = FOOTER_Y + 16

NAVY = HexColor("#13294B")
GOLD = HexColor("#D4A62A")
INK = HexColor("#1D2B3A")
MUTED = HexColor("#5B6B7F")
RULE = HexColor("#D6DCE4")
ROW = HexColor("#F2F4F7")
TRACK = HexColor("#E6EAF0")
CREAM = HexColor("#FFF6D8")
CREAM_EDGE = HexColor("#E8D9A8")
GREEN = HexColor("#2E7D4F")
RED = HexColor("#B03A2E")
AMBER = HexColor("#B7791F")

FONT, BOLD = "Helvetica", "Helvetica-Bold"

BODY = ParagraphStyle("body", fontName=FONT, fontSize=9, leading=12.5, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.5, leading=10)
TINY = ParagraphStyle("tiny", parent=BODY, fontSize=6.8, leading=9, textColor=MUTED)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7, leading=8.6)
LEAD = ParagraphStyle("lead", parent=BODY, fontSize=9.5, leading=13)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)


class LayoutError(Exception):
    pass


def _p(text: str, style=BODY) -> Paragraph:
    return Paragraph(text, style)


def esc(text) -> str:
    return escape(str(text))


class Doc:
    def __init__(self, report: Report, path, total_pages: int | None = None):
        self.r = report
        self.total_pages = total_pages
        self.c = Canvas(path, pagesize=letter)
        week = report.week
        self.c.setTitle(
            f"Manifest MWIR - Week Ending {report.week_ending.strftime('%d %b %Y')}"
            f" - {'Official' if self._official else 'Draft'}"
        )
        self.c.setAuthor(report.policy["report"]["prepared_for"])
        self.c.setSubject("Weekly Institutional Report")
        self.pages: list = []
        self.headline = week.get("headline", "")
        self.y = CONTENT_TOP

    @property
    def _official(self) -> bool:
        return self.r.week.get("status", "draft") == "official" and self.r.certified

    # ---- primitives ---------------------------------------------------
    def para(self, text: str, x: float, y_top: float, width: float, style=BODY) -> float:
        p = _p(text, style)
        _, h = p.wrap(width, 10_000)
        p.drawOn(self.c, x, y_top - h)
        return h

    def para_height(self, text: str, width: float, style=BODY) -> float:
        return _p(text, style).wrap(width, 10_000)[1]

    def label(self, text: str, x: float, y: float, size=8.5, color=NAVY, font=BOLD):
        self.c.setFillColor(color)
        self.c.setFont(font, size)
        self.c.drawString(x, y, text)

    def card(self, x, y_top, w, h, fill=white, edge=RULE, width=1.2):
        c = self.c
        c.setStrokeColor(edge)
        c.setFillColor(fill)
        c.setLineWidth(width)
        c.roundRect(x, y_top - h, w, h, 7, stroke=1, fill=1)

    def need(self, y: float):
        if y < CONTENT_BOTTOM:
            raise LayoutError(
                f"Page {len(self.pages) + 1} ('{self.pages[-1] if self.pages else ''}') overflows by "
                f"{CONTENT_BOTTOM - y:.0f}pt; shorten the text for that page"
            )

    # ---- page chrome --------------------------------------------------
    def page(self, kicker: str, title: str):
        if self.pages:
            self.c.showPage()
        self.pages.append(title)
        c = self.c
        c.setFillColor(NAVY)
        c.rect(0, H - HEADER_H, W, HEADER_H, stroke=0, fill=1)
        self.label(kicker.upper(), M, H - 24, size=8, color=GOLD)
        self.label(title, M, H - 55, size=22, color=white)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.8)
        c.line(M, FOOTER_Y + 10, W - M, FOOTER_Y + 10)
        c.setFillColor(MUTED)
        c.setFont(FONT, 7)
        week = self.r.week_ending.strftime("%d %b %Y").upper()
        c.drawRightString(W - M, FOOTER_Y - 2, f"{self.r.policy['report']['short_name']}  |  WEEK ENDING {week}"
                          f"  |  {len(self.pages)}/{self.total_pages or '?'}")
        self.y = CONTENT_TOP

    def section(self, text: str, y: float | None = None, x: float = M) -> float:
        y = self.y if y is None else y
        self.label(text.upper(), x, y - 9)
        return y - 20

    # ---- pages ----------------------------------------------------------
    def cover(self):
        r, week = self.r, self.r.week
        kicker = "OFFICIAL PUBLICATION - FROZEN DELIVERABLES" if self._official else "DRAFT - NOT FOR DISTRIBUTION"
        self.page(kicker, "Weekly Institutional Report")
        y = self.y
        y -= self.para(f"<b>{esc(r.fill(week.get('headline', '')))}</b>", M, y, W - 2 * M,
                       ParagraphStyle("hl", parent=BODY, fontName=BOLD, fontSize=13, leading=16, textColor=NAVY))
        y -= 6
        y -= self.para(esc(r.fill(week.get("subhead", ""))), M, y, W - 2 * M, SMALL)
        y -= 18

        card_h = 178
        gw = 250
        self.card(M, y, gw, card_h)
        self.label("MANIFEST INSTITUTIONAL GAUGE", M + 16, y - 22)
        self.gauge(M + gw / 2, y - 118, 72)

        cx = M + gw + 16
        cw = W - M - cx
        self.card(cx, y, cw, card_h, edge=HexColor("#C9D1DC"), width=2)
        self.label("INSTITUTIONAL COMPASS", cx + 16, y - 22)
        g = week["gauge"]
        delta = g["composite"] - g["prior_composite"] if "prior_composite" in g else None
        rows = [["CURRENT COMPOSITE", f"{g['composite']} / 100",
                 f"{delta:+d} w/w" if delta is not None else ""]]
        if "delta" in g or "gamma" in g:
            rows.append(["DELTA / GAMMA", f"{g.get('delta', 0):+d} / {g.get('gamma', 0):+d}".replace("+0", "0"),
                         g.get("delta_gamma_note", "")])
        rows += [[a, b, n] for a, b, n in week.get("compass", [])]
        row_h = min(22, (card_h - 42) / max(len(rows), 1))
        ry = y - 46
        for lab, val, note in rows:
            self.label(str(lab).upper(), cx + 16, ry, size=6.5, color=MUTED)
            self.label(str(val), cx + 108, ry, size=9.5, color=NAVY)
            self.c.setFont(BOLD, 9.5)
            vx = cx + 108 + self.c.stringWidth(str(val), BOLD, 9.5) + 8
            self.label(str(note), vx, ry, size=9, color=INK, font=FONT)
            ry -= row_h
        y -= card_h + 22

        y = self.section("EXECUTIVE SUMMARY", y)
        for lead, text in week.get("executive_summary", []):
            y -= self.para(f"<b>{esc(lead)}:</b> {esc(r.fill(text))}", M, y, W - 2 * M) + 7
        self.need(y)
        if week.get("footnote"):
            self.para(esc(r.fill(week["footnote"])), M, CONTENT_BOTTOM + 14, W - 2 * M, TINY)

    def gauge(self, cx: float, cy: float, radius: float):
        c, r = self.c, self.r
        zones = sorted(r.policy["gauge_zones"], key=lambda z: z["min"])
        c.setLineWidth(13)
        for i, z in enumerate(zones):
            lo = z["min"]
            hi = zones[i + 1]["min"] if i + 1 < len(zones) else 100
            start = 180 - hi * 1.8
            p = c.beginPath()
            p.arc(cx - radius, cy - radius, cx + radius, cy + radius, startAng=start, extent=(hi - lo) * 1.8)
            c.setStrokeColor(HexColor(z["color"]))
            c.drawPath(p, stroke=1, fill=0)
        score = max(0, min(100, r.week["gauge"]["composite"]))
        ang = math.radians(180 - score * 1.8)
        c.setStrokeColor(NAVY)
        c.setLineWidth(2.5)
        tip = radius - 18
        c.line(cx, cy, cx + tip * math.cos(ang), cy + tip * math.sin(ang))
        c.setFillColor(NAVY)
        c.circle(cx, cy, 4, stroke=0, fill=1)
        c.setFont(BOLD, 24)
        c.drawCentredString(cx, cy - 30, str(r.week["gauge"]["composite"]))
        zone = r.gauge_zone()
        c.setFillColor(HexColor(zone["color"]))
        c.setFont(BOLD, 8)
        c.drawCentredString(cx, cy - 46, zone["label"])

    def signals(self):
        r, week = self.r, self.r.week
        self.page("MFSO COMPONENT ARCHITECTURE", "Institutional Signal Dashboard")
        y = self.section("COMPONENT SCORES - 0-10")
        comps = list((week.get("components") or {}).items())
        half = math.ceil(len(comps) / 2)
        colw = (W - 2 * M) / 2
        for i, (name, score) in enumerate(comps):
            col, row = divmod(i, half)
            x = M + 10 + col * colw
            yy = y - 8 - row * 26
            self.label(str(name), x, yy, size=9, color=INK, font=FONT)
            bx, bw = x + 106, colw - 150
            self.c.setFillColor(TRACK)
            self.c.roundRect(bx, yy - 2, bw, 9, 4, stroke=0, fill=1)
            color = HexColor(zone_for(score, r.policy["component_zones"])["color"])
            self.c.setFillColor(color)
            self.c.roundRect(bx, yy - 2, max(bw * score / 10, 8), 9, 4, stroke=0, fill=1)
            self.label(str(score), bx + bw + 10, yy, size=8.5)
        y -= half * 26 + 28

        colw2 = (W - 2 * M - 20) / 2
        top = y
        self.section("WEEKLY RISK TAPE", top)
        ty = top - 32
        for i, (name, val) in enumerate(week.get("risk_tape", [])):
            if i % 2 == 0:
                self.c.setFillColor(ROW)
                self.c.rect(M, ty - 6, colw2, 20, stroke=0, fill=1)
            self.label(str(name), M + 6, ty, size=8.5, color=INK, font=FONT)
            self.label(str(val), M + colw2 * 0.52, ty, size=8.5, color=INK, font=FONT)
            ty -= 20
        rx = M + colw2 + 20
        self.section("SIGNAL INTERPRETATION", top, x=rx)
        iy = top - 22
        for item in week.get("signal_interpretation", []):
            iy -= self.para(f"• {esc(r.fill(item))}", rx, iy, colw2, SMALL) + 5
        y = min(ty, iy) - 24

        text = esc(r.fill(week.get("decision_rule", "")))
        posture = esc(week.get("official_posture", ""))
        inner = W - 2 * M - 36
        h = 34 + self.para_height(text, inner, SMALL) + (26 if posture else 0) + 10
        self.need(y - h)
        self.card(M, y, W - 2 * M, h, fill=CREAM, edge=CREAM_EDGE)
        self.label("DECISION RULE", M + 18, y - 22)
        yy = y - 34
        yy -= self.para(text, M + 18, yy, inner, SMALL)
        if posture:
            self.para(f"<b>OFFICIAL POSTURE &nbsp;&nbsp;{posture}</b>", M + 18, yy - 12, inner,
                      ParagraphStyle("pos", parent=CENTER, fontSize=8.5, textColor=NAVY))

    def macro(self):
        r, week = self.r, self.r.week
        self.page("RATES - INFLATION - EARNINGS - GEOPOLITICS", "Macro Stewardship & Event Map")
        y = self.y
        for heading, text in week.get("macro", []):
            y = self.section(str(heading), y)
            y -= self.para(esc(r.fill(text)), M, y + 4, W - 2 * M) + 14
        gates = week.get("event_gates") or []
        if gates:
            y -= 6
            h = 40 + 38 * len(gates)
            self.need(y - h)
            self.card(M, y, W - 2 * M, h, fill=CREAM, edge=CREAM_EDGE)
            self.label(str(week.get("event_gates_title", "FORWARD EVENT GATES")).upper(), M + 18, y - 22)
            gy = y - 44
            for date, name, action in gates:
                self.c.setFillColor(NAVY)
                self.c.roundRect(M + 18, gy - 16, 52, 24, 4, stroke=0, fill=1)
                self.c.setFillColor(white)
                self.c.setFont(BOLD, 8.5)
                self.c.drawCentredString(M + 44, gy - 7, str(date))
                self.label(str(name), M + 84, gy, size=9)
                self.para(esc(r.fill(action)), M + 84, gy - 4, W - 2 * M - 110, SMALL)
                gy -= 38
            y -= h
        self.need(y)

    def allocation(self):
        r, week = self.r, self.r.week
        self.page("MFPDF BASELINE - MRGES-001 EXECUTABLE CHANNEL", "Allocation & Implementation Dashboard")
        y = self.y
        sleeves = r.policy["sleeves"]
        card_h = max(66 + 30 * (len(sleeves) - 1) + 16, 58 + 20 * 10 + 14)
        lw = 290
        self.card(M, y, lw, card_h)
        self.label(f"EXECUTABLE SLEEVE ALLOCATION - {pct(r.total)}", M + 16, y - 22)
        top = max(r.sleeve_totals.values()) or 1
        sy = y - 50
        step = (card_h - 66) / max(len(sleeves) - 1, 1)
        for key, s in sleeves.items():
            v = r.sleeve_totals[key]
            self.label(s["name"], M + 16, sy, size=8, color=INK, font=FONT)
            bx, bw = M + 138, 100
            self.c.setFillColor(TRACK)
            self.c.rect(bx, sy - 2, bw, 9, stroke=0, fill=1)
            self.c.setFillColor(HexColor(s["color"]))
            self.c.rect(bx, sy - 2, bw * v / top, 9, stroke=0, fill=1)
            self.c.setFillColor(INK)
            self.c.setFont(BOLD, 7.5)
            self.c.drawRightString(M + lw - 8, sy, pct(v))
            sy -= step

        tx = M + lw + 16
        tw = W - M - tx
        self.card(tx, y, tw, card_h)
        self.label("TOP 10 EXECUTABLE TARGETS", tx + 16, y - 22)
        cols = [("Ticker", 12), ("Target", 62), ("Approved band", 128)]
        hy = y - 40
        self.c.setFillColor(NAVY)
        self.c.rect(tx + 12, hy - 14, tw - 24, 18, stroke=0, fill=1)
        for name, off in cols:
            self.label(name, tx + 12 + off - 4, hy - 8, size=7, color=white)
        ry = hy - 14
        for i, h in enumerate(r.top10):
            if i % 2:
                self.c.setFillColor(ROW)
                self.c.rect(tx + 12, ry - 20, tw - 24, 20, stroke=0, fill=1)
            vals = [h.ticker, pct(h.current), f"{pct(h.band_lo)}-{pct(h.band_hi)}"]
            for (_, off), v in zip(cols, vals):
                self.label(v, tx + 12 + off - 4, ry - 13.5, size=7.5, color=INK, font=FONT)
            ry -= 20
        y -= card_h + 18

        b = r.policy["bands"]
        parts = []
        for ticker, e in (week.get("excluded") or {}).items():
            sleeve = r.policy["sleeves"][e["sleeve"]]["name"]
            n = sum(1 for h in r.holdings if h.sleeve == e["sleeve"])
            parts.append(
                f"<b>{esc(e.get('name', ticker))} ({esc(ticker)}):</b> MFPDF analytical baseline "
                f"{pct(float(e['mfpdf']))} - executable target 0.00% - excluded because {esc(e.get('reason', 'not executable'))}. "
                f"The {pct(float(e['mfpdf']))} is redistributed pro rata among the {n} eligible {esc(sleeve)} holdings, "
                f"bringing the sleeve to {pct(r.sleeve_totals[e['sleeve']])} of a {pct(r.total)} executable model."
            )
        actual = ("Actual weights were supplied; drift is classified against the bands on the holding matrix."
                  if r.actual_supplied else "Actual weights are not available; no drift classification is asserted.")
        standard = (
            f"Current recommendation equals the MRGES executable target unless an event gate says HOLD &lt;= TARGET. "
            f"Approved monitoring bands are {b['lower_pct_of_target']:g}%-{b['upper_pct_of_target']:g}% of target, "
            f"subject to the {pct(b['floor'])} floor and {pct(b['cap'])} cap. {actual}"
        )
        inner = W - 2 * M - 36
        std_w = inner - 118
        h = 34 + sum(self.para_height(p, inner, SMALL) + 10 for p in parts) + self.para_height(standard, std_w, TINY) + 22
        self.card(M, y, W - 2 * M, h, fill=CREAM, edge=CREAM_EDGE)
        self.label("MRGES-001 CHANNEL RECONCILIATION", M + 18, y - 22)
        yy = y - 34
        for p in parts:
            yy -= self.para(p, M + 18, yy, inner, SMALL) + 10
        self.label("TARGET / BAND STANDARD", M + 18, yy - 8, size=8)
        self.para(standard, M + 18 + 118, yy, std_w, TINY)
        y -= h + 18

        items = week.get("deployment_hierarchy") or []
        if items:
            texts = [f"<b>{i}</b>&nbsp;&nbsp;{esc(r.fill(t))}" for i, t in enumerate(items, 1)]
            h = 40 + sum(self.para_height(t, inner, SMALL) + 5 for t in texts) + 8
            self.need(y - h)
            self.card(M, y, W - 2 * M, h)
            self.label("CAPITAL DEPLOYMENT HIERARCHY", M + 18, y - 22)
            yy = y - 36
            for t in texts:
                yy -= self.para(t, M + 18, yy, inner, SMALL) + 5
            y -= h
        self.need(y)

    def matrix(self):
        r = self.r
        cols = [("Sleeve", 44), ("Ticker", 36), ("MFPDF", 34), ("Current", 36), ("Band", 58)]
        if r.actual_supplied:
            cols += [("Actual", 34)]
        cols += [("Guidance", 72), ("Rationale", 0), ("Status", 70)]
        fixed = sum(w for _, w in cols)
        tw = W - 2 * M
        cols = [(n, w or tw - fixed) for n, w in cols]
        row_h = 22
        note = ("MFPDF = frozen analytical baseline. Current = MRGES executable recommendation. Actual = "
                + ("supplied; Status shows drift against the band." if r.actual_supplied else "not supplied."))
        footer = ("No live trade authorization. Apply suitability, tax, liquidity, firm and supervisory controls "
                  "before any account action. "
                  + ("Actual weights are client-supplied and not reconciled to custody."
                     if r.actual_supplied else "Missing actual weights prevents drift and order-size certification."))
        per_page = int((CONTENT_TOP - 30 - 18 - (CONTENT_BOTTOM + 58)) // row_h)
        chunks = [r.holdings[i:i + per_page] for i in range(0, len(r.holdings), per_page)]
        for n, chunk in enumerate(chunks, 1):
            self.page("HOLDING-BY-HOLDING WEIGHT GUIDANCE", f"Holding Action Matrix - {_roman(n)}")
            y = self.y
            self.para(esc(note), M, y, tw, SMALL)
            y -= 30
            self.c.setFillColor(NAVY)
            self.c.rect(M, y - 18, tw, 18, stroke=0, fill=1)
            x = M
            for name, w in cols:
                self.label(name, x + 5, y - 12, size=6.8, color=white)
                x += w
            y -= 18
            for i, h in enumerate(chunk):
                if i % 2:
                    self.c.setFillColor(ROW)
                    self.c.rect(M, y - row_h, tw, row_h, stroke=0, fill=1)
                sleeve = r.policy["sleeves"][h.sleeve]["short"]
                vals = [sleeve, h.ticker, pct(h.mfpdf), pct(h.current), f"{pct(h.band_lo)}-{pct(h.band_hi)}"]
                if r.actual_supplied:
                    vals.append(pct(h.actual) if h.actual is not None else "n/a")
                vals += [h.guidance, h.rationale, h.drift or h.status]
                x = M
                for (name, w), v in zip(cols, vals):
                    color = INK
                    if name == "Status" and h.drift:
                        color = {"BELOW BAND": AMBER, "ABOVE BAND": RED}.get(h.drift, GREEN)
                    style = ParagraphStyle("c", parent=CELL, textColor=color,
                                           fontName=BOLD if name == "Ticker" else FONT)
                    p = _p(esc(v), style)
                    _, ph = p.wrap(w - 8, row_h)
                    p.drawOn(self.c, x + 5, y - row_h / 2 - ph / 2 + 1)
                    x += w
                y -= row_h
            fh = self.para_height(esc(footer), tw - 32, SMALL) + 24
            self.card(M, CONTENT_BOTTOM + fh + 4, tw, fh, fill=CREAM, edge=CREAM_EDGE)
            self.para(esc(footer), M + 16, CONTENT_BOTTOM + fh - 8, tw - 32, SMALL)

    def certification(self):
        r, week = self.r, self.r.week
        self.page("PUBLICATION CONTROL RECORD", "Certification, Client Brief & Sources")
        y = self.y
        inner = W - 2 * M - 36
        brief = esc(r.fill(week.get("client_brief", "")))
        h = 36 + self.para_height(brief, inner, BODY) + 12
        self.card(M, y, W - 2 * M, h, fill=CREAM, edge=CREAM_EDGE)
        self.label("CLIENT EXECUTIVE BRIEF", M + 18, y - 22)
        self.para(brief, M + 18, y - 34, inner)
        y -= h + 18

        colw = (W - 2 * M - 16) / 2
        top = y
        ly = self.section("FROZEN DELIVERABLES APPLIED", top)
        for d in week.get("frozen_deliverables", []):
            ly -= self.para(esc(r.fill(d)), M, ly + 2, colw, SMALL) + 3
        ly -= 10
        ly = self.section("CERTIFICATION RESULT", ly)
        certified = self._official
        result = ("PUBLISHED / FROZEN" if certified
                  else "NOT CERTIFIED - CONTROL FAILURES" if not r.certified else "DRAFT - NOT PUBLISHED")
        self.c.setFillColor(GREEN if certified else RED if not r.certified else AMBER)
        self.c.roundRect(M, ly - 20, colw, 26, 5, stroke=0, fill=1)
        self.c.setFillColor(white)
        self.c.setFont(BOLD, 10)
        self.c.drawCentredString(M + colw / 2, ly - 11, result)
        ly -= 32

        rx = M + colw + 16
        ry = self.section("CONTROL ASSERTIONS", top, x=rx)
        for a in r.assertions:
            color = {PASS: "#2E7D4F", FAIL: "#B03A2E", WARN: "#B7791F"}.get(a.result, "#5B6B7F")
            text = f"{esc(a.label)}: {esc(a.value)} / <font color='{color}'><b>{esc(a.result)}</b></font>"
            if a.detail and a.result != PASS:
                text += f"<br/><font size='6.5' color='#5B6B7F'>{esc(a.detail)}</font>"
            ry -= self.para(text, rx, ry + 2, colw, SMALL) + 3
        y = min(ly, ry) - 14

        y = self.section("PRIMARY EVIDENCE & MARKET SOURCES", y)
        for s in week.get("sources", []):
            y -= self.para(esc(s), M, y + 2, W - 2 * M, TINY) + 1.5
        if week.get("data_freshness"):
            y -= 8
            y -= self.para(f"<b>DATA-FRESHNESS CERTIFICATION:</b> {esc(r.fill(week['data_freshness']))}",
                           M, y, W - 2 * M, TINY)
        y -= 10
        y -= self.para(
            f"Prepared for {esc(r.policy['report']['prepared_for'])} - Publication date: "
            f"{r.publication_date.strftime('%d %b %Y')}", M, y, W - 2 * M,
            ParagraphStyle("prep", parent=TINY, textColor=NAVY, fontName=BOLD))
        self.need(y)

    # ---- output ---------------------------------------------------------
    def save(self):
        self.c.showPage()
        self.c.save()


def _roman(n: int) -> str:
    return ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"][n - 1] if n <= 8 else str(n)


def render(report: Report, path: str) -> int:
    """Render the report to `path`. Returns the page count.

    Drawn twice: the first pass (to memory) counts pages so every footer can
    read "n/N".
    """
    total = None
    for target in (io.BytesIO(), path):
        doc = Doc(report, target, total)
        doc.cover()
        doc.signals()
        doc.macro()
        doc.allocation()
        doc.matrix()
        doc.certification()
        total = len(doc.pages)
    doc.save()
    return total
