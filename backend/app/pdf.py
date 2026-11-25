"""Server-side PDF report generation (ReportLab).

The report is built from the stored audit payload — never from sample data.
Layout: brand header/footer on every page, score dashboard, executive summary,
critical findings, per-pillar check tables, prioritised roadmap, methodology,
limitations and an AuriomHQ call to action.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)

from .config import settings

PAGE_W, PAGE_H = A4
MARGIN = 44
CONTENT_W = PAGE_W - 2 * MARGIN

INK = colors.HexColor("#14130F")
TEXT = colors.HexColor("#26241F")
MUTED = colors.HexColor("#6E6B62")
FAINT = colors.HexColor("#9A968C")
BORDER = colors.HexColor("#E2DED4")
SURFACE = colors.HexColor("#F7F5EF")
ACCENT = colors.HexColor("#C2410C")
PASS_C = colors.HexColor("#15803D")
WARN_C = colors.HexColor("#B45309")
FAIL_C = colors.HexColor("#B91C1C")
NEUTRAL_C = colors.HexColor("#8A8780")

FONT_DIR = __file__.rsplit("/", 1)[0] + "/assets/fonts"
REGISTERED = False


def _register_fonts() -> tuple[str, str, str, str, str]:
    global REGISTERED
    regular, medium, semibold, bold, mono = "Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Helvetica-Bold", "Courier"
    if not REGISTERED:
        try:
            pdfmetrics.registerFont(TTFont("Inter", f"{FONT_DIR}/Inter-Regular.ttf"))
            pdfmetrics.registerFont(TTFont("Inter-Medium", f"{FONT_DIR}/Inter-Medium.ttf"))
            pdfmetrics.registerFont(TTFont("Inter-SemiBold", f"{FONT_DIR}/Inter-SemiBold.ttf"))
            pdfmetrics.registerFont(TTFont("Inter-Bold", f"{FONT_DIR}/Inter-Bold.ttf"))
            pdfmetrics.registerFont(TTFont("FragmentMono", f"{FONT_DIR}/FragmentMono-Regular.ttf"))
            pdfmetrics.registerFontFamily("Inter", normal="Inter", bold="Inter-SemiBold",
                                          italic="Inter", boldItalic="Inter-SemiBold")
            regular, medium, semibold, bold, mono = "Inter", "Inter-Medium", "Inter-SemiBold", "Inter-Bold", "FragmentMono"
        except Exception:
            regular, medium, semibold, bold, mono = (
                "Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Helvetica-Bold", "Courier",
            )
        REGISTERED = True
    return regular, medium, semibold, bold, mono


FONTS = _register_fonts()
F_REG, F_MED, F_SEMI, F_BOLD, F_MONO = FONTS


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "h1": ParagraphStyle("h1", fontName=F_BOLD, fontSize=26, leading=30, textColor=INK, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName=F_SEMI, fontSize=14.5, leading=18, textColor=INK,
                             spaceBefore=16, spaceAfter=7),
        "h3": ParagraphStyle("h3", fontName=F_SEMI, fontSize=10.5, leading=14, textColor=INK,
                             spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", fontName=F_REG, fontSize=9.3, leading=14.2, textColor=TEXT,
                               alignment=TA_LEFT),
        "small": ParagraphStyle("small", fontName=F_REG, fontSize=8.2, leading=12, textColor=MUTED),
        "tiny": ParagraphStyle("tiny", fontName=F_REG, fontSize=7.2, leading=10, textColor=FAINT),
        "mono": ParagraphStyle("mono", fontName=F_MONO, fontSize=7.4, leading=10.5, textColor=MUTED),
        "eyebrow": ParagraphStyle("eyebrow", fontName=F_MONO, fontSize=7.4, leading=10,
                                  textColor=FAINT, spaceAfter=4),
        "evidence": ParagraphStyle("evidence", fontName=F_REG, fontSize=8.2, leading=11.6, textColor=MUTED),
        "cell": ParagraphStyle("cell", fontName=F_REG, fontSize=8, leading=10.6, textColor=TEXT),
        "cellStrong": ParagraphStyle("cellStrong", fontName=F_SEMI, fontSize=8, leading=10.6, textColor=INK),
        "code": ParagraphStyle("code", fontName=F_MONO, fontSize=7, leading=9.4, textColor=colors.HexColor("#4A463D")),
    }


S = _styles()


def _hex(color: colors.Color) -> str:
    return "#" + color.hexval()[2:]


def _status_color(status: str) -> colors.Color:
    return {"pass": PASS_C, "warning": WARN_C, "fail": FAIL_C}.get(status, NEUTRAL_C)


SEVERITY_ABBR = {"critical": "CRIT", "high": "HIGH", "medium": "MED", "low": "LOW", "informational": "INFO"}


def _status_label(status: str) -> str:
    return {"pass": "PASS", "warning": "WARN", "fail": "FAIL", "not_tested": "N/A"}.get(status, status.upper())


def _score_color(score: int | None) -> colors.Color:
    if score is None:
        return NEUTRAL_C
    if score >= 70:
        return PASS_C
    if score >= 45:
        return WARN_C
    return FAIL_C


def _fmt_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d %B %Y, %H:%M UTC")
    except ValueError:
        return value


# ---------------------------------------------------------------------------
# Custom flowables
# ---------------------------------------------------------------------------
class ScoreDashboard(Flowable):
    """Overall score + three pillar donuts."""

    def __init__(self, scores: dict[str, Any], band: dict[str, str]):
        super().__init__()
        self.scores = scores
        self.band = band
        self.height = 128

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        c = self.canv
        overall = self.scores.get("overall")
        # overall block
        c.setFillColor(SURFACE)
        c.setStrokeColor(BORDER)
        c.roundRect(0, 0, self.width, self.height, 10, stroke=1, fill=1)
        c.setFillColor(FAINT)
        c.setFont(F_MONO, 7)
        c.drawString(16, self.height - 20, "OVERALL AI VISIBILITY SCORE")
        c.setFillColor(INK)
        c.setFont(F_BOLD, 46)
        c.drawString(16, 46, str(overall) if overall is not None else "—")
        c.setFont(F_REG, 13)
        c.setFillColor(FAINT)
        c.drawString(16 + pdfmetrics.stringWidth(str(overall) if overall is not None else "—", F_BOLD, 46), 50, "/100")
        c.setFillColor(_score_color(overall))
        c.setFont(F_MED, 8.5)
        c.drawString(16, 26, str(self.band.get("label", "")).upper() + " READINESS")

        # pillar donuts
        pillars = self.scores.get("pillars", {})
        start_x = self.width * 0.42
        slot = (self.width - start_x - 8) / 3
        for index, pillar in enumerate(("seo", "aeo", "geo")):
            row = pillars.get(pillar, {})
            cx = start_x + slot * index + slot / 2
            cy = self.height / 2 + 6
            self._donut(c, cx, cy, 27, row.get("score"))
            c.setFillColor(INK)
            c.setFont(F_SEMI, 8.6)
            c.drawCentredString(cx, 20, row.get("label", pillar.upper()))
            c.setFillColor(FAINT)
            c.setFont(F_MONO, 6.6)
            c.drawCentredString(cx, 10, f"{row.get('passed', 0)}P · {row.get('warnings', 0)}W · {row.get('failed', 0)}F")

    def _donut(self, c: pdfcanvas.Canvas, cx: float, cy: float, r: float, score: int | None):
        thickness = 6
        c.setLineWidth(thickness)
        c.setStrokeColor(colors.HexColor("#ECE9E1"))
        c.circle(cx, cy, r, stroke=1, fill=0)
        if score is not None and score > 0:
            c.setStrokeColor(_score_color(score))
            c.setLineCap(1)
            c.arc(cx - r, cy - r, cx + r, cy + r, startAng=90, extent=-3.6 * score)
            c.setLineCap(0)
        c.setFillColor(INK)
        c.setFont(F_BOLD, 15)
        c.drawCentredString(cx, cy - 5, str(score) if score is not None else "—")


class StatusBars(Flowable):
    """Severity distribution / category performance bars."""

    def __init__(self, items: Iterable[tuple[str, float, str, str]], width_ratio: float = 1.0,
                 bar_height: int = 7, row_height: int = 19):
        super().__init__()
        self.items = list(items)
        self.width_ratio = width_ratio
        self.bar_height = bar_height
        self.row_height = row_height
        self.height = max(1, len(self.items) * row_height)

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        c = self.canv
        label_w = self.width * 0.30
        value_w = 34
        bar_w = self.width - label_w - value_w
        y = self.height - self.row_height
        for label, value, value_text, color_hex in self.items:
            c.setFillColor(TEXT)
            c.setFont(F_REG, 8)
            c.drawString(0, y + 5, label[:46])
            pct = max(0.0, min(1.0, value))
            c.setFillColor(colors.HexColor("#ECE9E1"))
            c.roundRect(label_w, y + 4, bar_w, self.bar_height, 3, stroke=0, fill=1)
            if pct > 0:
                c.setFillColor(colors.HexColor(color_hex))
                c.roundRect(label_w, y + 4, max(3, bar_w * pct), self.bar_height, 3, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.setFont(F_MONO, 7.2)
            c.drawRightString(self.width, y + 5, value_text)
            y -= self.row_height


class Rule(Flowable):
    def __init__(self, color=BORDER, thickness=0.7, space=4):
        super().__init__()
        self.color = color
        self.thickness = thickness
        self.space = space
        self.height = space

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.space

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.space / 2, self.width, self.space / 2)


class Pill(Flowable):
    """Small status chip used inside tables."""

    def __init__(self, text: str, color: colors.Color, width: int = 34):
        super().__init__()
        self.text = text
        self.color = color
        self.width = width
        self.height = 11

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.Color(self.color.red, self.color.green, self.color.blue, alpha=0.10))
        c.roundRect(0, 0, self.width, self.height, 5.5, stroke=0, fill=1)
        c.setFillColor(self.color)
        c.setFont(F_MONO, 6.4)
        c.drawCentredString(self.width / 2, 3.4, self.text)


# ---------------------------------------------------------------------------
# Document template
# ---------------------------------------------------------------------------
class ReportDoc(BaseDocTemplate):
    def __init__(self, buffer: io.BytesIO, report: dict[str, Any], **kwargs):
        self.report = report
        super().__init__(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN + 18, bottomMargin=MARGIN + 6,
                         title=f"AI Visibility Report — {report.get('site', {}).get('host', '')}",
                         author=settings.brand_name, subject="SEO / AEO / GEO visibility audit",
                         **kwargs)
        frame = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN - 26, id="main",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=self._decorate)])

    def _decorate(self, canvas: pdfcanvas.Canvas, doc: Any) -> None:
        canvas.saveState()
        # header
        canvas.setFillColor(INK)
        canvas.setFont(F_BOLD, 9)
        canvas.drawString(MARGIN, PAGE_H - MARGIN + 6, settings.brand_name)
        canvas.setFillColor(FAINT)
        canvas.setFont(F_MONO, 6.6)
        canvas.drawString(MARGIN + pdfmetrics.stringWidth(settings.brand_name, F_BOLD, 9) + 6,
                          PAGE_H - MARGIN + 6, "AI VISIBILITY REPORT")
        host = self.report.get("site", {}).get("host", "")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 6, host.upper()[:60])
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, PAGE_H - MARGIN - 2, PAGE_W - MARGIN, PAGE_H - MARGIN - 2)
        # footer
        canvas.line(MARGIN, MARGIN - 12, PAGE_W - MARGIN, MARGIN - 12)
        canvas.setFillColor(FAINT)
        canvas.setFont(F_MONO, 6.4)
        canvas.drawString(MARGIN, MARGIN - 24, settings.brand_url.replace("https://", ""))
        canvas.drawCentredString(PAGE_W / 2, MARGIN - 24,
                                 f"Generated {_fmt_date(self.report.get('generatedAt'))}")
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 24, f"PAGE {canvas.getPageNumber()}")
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def _cover(report: dict[str, Any]) -> list[Flowable]:
    site = report.get("site", {})
    story: list[Flowable] = []
    story.append(Paragraph("AI VISIBILITY AUDIT", S["eyebrow"]))
    url = site.get("url", "")
    story.append(Paragraph(escape(url), S["h1"]))
    meta_bits = [
        f"Audit date: {_fmt_date(report.get('generatedAt'))}",
        f"Pages analysed: {site.get('pagesAnalysed', 0)}",
        f"Crawl time: {round((site.get('durationMs') or 0) / 1000, 1)}s",
        f"HTTPS: {'yes' if site.get('httpsAvailable') else 'no'}",
        f"Homepage: HTTP {site.get('homepageStatus') or '—'}",
    ]
    story.append(Paragraph(" · ".join(meta_bits), S["small"]))
    story.append(Spacer(1, 14))
    story.append(ScoreDashboard(report.get("scores", {}), report.get("band", {})))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "SEO measures technical and content search readiness. AEO measures how answerable the content is. "
        "GEO estimates readiness for generative search. Scores are computed from the checks listed in this report "
        "— they are not rankings or traffic data.", S["tiny"]))
    return story


def _executive_summary(report: dict[str, Any]) -> list[Flowable]:
    summary = report.get("summary") or {}
    scores = report.get("scores", {})
    counts = scores.get("counts", {})
    story = [Paragraph("Executive summary", S["h2"])]
    story.append(Paragraph(escape(summary.get("executiveSummary", "")), S["body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Findings by severity", S["h3"]))
    sev = scores.get("severityCounts", {})
    total = max(1, sum(sev.values()))
    items = []
    for key, color in (("critical", "#B91C1C"), ("high", "#C2410C"), ("medium", "#B45309"),
                       ("low", "#6E6B62"), ("informational", "#9A968C")):
        count = sev.get(key, 0)
        items.append((f"{key.capitalize()} issues", count / total, str(count), color))
    story.append(StatusBars(items))
    story.append(Spacer(1, 12))

    findings = summary.get("keyFindings") or []
    if findings:
        story.append(Paragraph("Key findings", S["h3"]))
        for finding in findings[:5]:
            story.append(Paragraph(f"<b>{escape(finding.get('title', ''))}</b> — {escape(finding.get('detail', ''))}",
                                   S["body"]))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"{counts.get('pass', 0)} checks passed · {counts.get('warning', 0)} warnings · "
        f"{counts.get('fail', 0)} failures · {counts.get('not_tested', 0)} not tested.", S["small"]))
    return story


def _site_snapshot(report: dict[str, Any]) -> list[Flowable]:
    crawl = report.get("crawl", {})
    site = report.get("site", {})
    robots = crawl.get("robots", {})
    sitemap = crawl.get("sitemap", {})
    llms = crawl.get("llmsTxt", {})
    schema_types = sorted({t for page in crawl.get("pages", []) for t in page.get("schemaTypes", [])})
    rows = [
        ("Homepage", f"HTTP {site.get('homepageStatus') or '—'} · HTTPS {'yes' if site.get('httpsAvailable') else 'no'}"),
        ("Crawl", f"{site.get('pagesAnalysed', 0)} page(s) in {round((site.get('durationMs') or 0) / 1000, 1)}s"),
        ("robots.txt", "found" if robots.get("available") else f"missing (HTTP {robots.get('status') or '—'})"),
        ("XML sitemap", f"{sitemap.get('urlCount', 0)} URLs" if sitemap.get("available") else "not found"),
        ("llms.txt", "published" if llms.get("available") else "not found"),
        ("Structured data", ", ".join(schema_types[:6]) if schema_types else "none detected"),
        ("Broken links", str(len(crawl.get("brokenLinks", [])))),
        ("Inaccessible pages", str(len(crawl.get("inaccessiblePages", [])))),
    ]
    table = Table(
        [[Paragraph(escape(label), S["cell"]), Paragraph(escape(value), S["cell"])] for label, value in rows],
        colWidths=[CONTENT_W * 0.22, CONTENT_W * 0.78],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
    ]))
    return [KeepTogether([Paragraph("Site snapshot", S["h2"]), table])]


def _pillar_performance(report: dict[str, Any]) -> list[Flowable]:
    story = [Paragraph("Performance by category", S["h2"])]
    categories = report.get("scores", {}).get("categories", [])
    rows = []
    for cat in categories:
        score = cat.get("score")
        color = _score_color(score)
        rows.append([
            Paragraph(escape(f"{cat['pillar'].upper()} · {cat['category']}"), S["cell"]),
            Paragraph(f"<font color='{_hex(color)}'><b>{score if score is not None else '—'}</b></font>", S["cell"]),
            Paragraph(f"{cat['passed']} / {cat['warning']} / {cat['failed']}", S["cell"]),
            Paragraph(f"{cat['available']:.0f} pts available", S["cell"]),
        ])
    table = Table(rows, colWidths=[CONTENT_W * 0.46, CONTENT_W * 0.14, CONTENT_W * 0.22, CONTENT_W * 0.18])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), F_REG),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(table)
    story.append(Paragraph("Columns: passed / warnings / failed checks. Points are the total weight of the tested checks in that category.",
                           S["tiny"]))
    return story


def _critical_findings(report: dict[str, Any]) -> list[Flowable]:
    critical = report.get("criticalFindings") or []
    if not critical:
        return []
    story = [Paragraph("Critical findings", S["h2"]),
             Paragraph("These failures have the largest negative impact on how the site is discovered and understood.",
                       S["small"]), Spacer(1, 6)]
    for index, check in enumerate(critical[:6], start=1):
        block = [
            Paragraph(f"{index}. {escape(check['title'])}", S["h3"]),
            Paragraph(f"<font color='#6E6B62'>{escape(check['evidence'])}</font>", S["evidence"]),
            Spacer(1, 2),
            Paragraph(f"<b>Fix:</b> {escape(check['fix'])}", S["body"]),
        ]
        story.append(KeepTogether(block))
        story.append(Spacer(1, 8))
    return story


def _pillar_tables(report: dict[str, Any]) -> list[Flowable]:
    story: list[Flowable] = []
    labels = {"seo": "SEO — search engine optimisation", "aeo": "AEO — answer engine optimisation",
              "geo": "GEO — generative engine optimisation"}
    pillars = report.get("scores", {}).get("pillars", {})
    for pillar in ("seo", "aeo", "geo"):
        score = pillars.get(pillar, {}).get("score")
        story.append(Paragraph(f"{labels[pillar]} — score {score if score is not None else '—'}/100", S["h2"]))
        checks = report.get("checksByPillar", {}).get(pillar, [])
        header = [Paragraph("<b>Check</b>", S["cell"]), Paragraph("<b>Status</b>", S["cell"]),
                  Paragraph("<b>Sev.</b>", S["cell"]), Paragraph("<b>Weight</b>", S["cell"]),
                  Paragraph("<b>Evidence</b>", S["cell"])]
        rows = [header]
        for check in checks:
            status = check["status"]
            color = _status_color(status)
            chip = Pill(_status_label(status), color)
            rows.append([
                Paragraph(escape(check["title"]), S["cellStrong"]),
                chip,
                Paragraph(f"<font color='{_hex(color)}'>{SEVERITY_ABBR.get(check['severity'], check['severity'][:4].upper())}</font>", S["cell"]),
                Paragraph(str(check["weight"]), S["cell"]),
                Paragraph(escape(check["evidence"][:220]), S["cell"]),
            ])
        table = Table(rows, colWidths=[CONTENT_W * 0.22, CONTENT_W * 0.09, CONTENT_W * 0.07,
                                       CONTENT_W * 0.08, CONTENT_W * 0.54], repeatRows=1)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
        ]))
        story.append(table)
        story.append(Spacer(1, 8))
    return story


def _roadmap(report: dict[str, Any]) -> list[Flowable]:
    recommendations = report.get("recommendations") or {}
    roadmap = recommendations.get("roadmap") or []
    story = [Paragraph("Prioritised roadmap", S["h2"])]
    for phase in roadmap:
        if not phase.get("items"):
            continue
        story.append(Paragraph(escape(phase["title"]), S["h3"]))
        story.append(Paragraph(escape(phase.get("description", "")), S["small"]))
        story.append(Spacer(1, 4))
        rows = [[Paragraph("<b>Action</b>", S["cell"]), Paragraph("<b>Impact</b>", S["cell"]),
                 Paragraph("<b>Effort</b>", S["cell"]), Paragraph("<b>Guidance</b>", S["cell"])]]
        for item in phase["items"][:10]:
            rows.append([
                Paragraph(escape(item["title"]), S["cellStrong"]),
                Paragraph(escape(item["impact"]), S["cell"]),
                Paragraph(escape(item["difficulty"]), S["cell"]),
                Paragraph(escape(item["guidance"])[:260], S["cell"]),
            ])
        table = Table(rows, colWidths=[CONTENT_W * 0.24, CONTENT_W * 0.08, CONTENT_W * 0.09, CONTENT_W * 0.59],
                      repeatRows=1)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
        ]))
        story.append(table)
        story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Recommendations describe expected benefit for machine readability and discoverability. "
        "No specific ranking or traffic outcome is promised.", S["tiny"]))
    return story


def _drafts(report: dict[str, Any]) -> list[Flowable]:
    drafts = (report.get("recommendations") or {}).get("drafts") or {}
    if not drafts.get("titles") and not drafts.get("faqQuestions"):
        return []
    story = [Paragraph("Draft improvements generated from your content", S["h2"]),
             Paragraph(escape(drafts.get("note", "")), S["small"]), Spacer(1, 6)]
    if drafts.get("currentTitle") or drafts.get("titles"):
        story.append(Paragraph("Title options", S["h3"]))
        if drafts.get("currentTitle"):
            story.append(Paragraph(f"Current: {escape(drafts['currentTitle'])}", S["small"]))
        for title in drafts.get("titles", []):
            story.append(Paragraph(f"• {escape(title)}", S["body"]))
        story.append(Spacer(1, 6))
    if drafts.get("metaDescriptions"):
        story.append(Paragraph("Meta description options", S["h3"]))
        for meta in drafts["metaDescriptions"]:
            story.append(Paragraph(f"• {escape(meta)}", S["body"]))
        story.append(Spacer(1, 6))
    if drafts.get("faqQuestions"):
        story.append(Paragraph("FAQ questions to answer on the page", S["h3"]))
        story.append(Paragraph(" · ".join(escape(q) for q in drafts["faqQuestions"]), S["body"]))
        story.append(Spacer(1, 6))
    if drafts.get("headingOutline"):
        story.append(Paragraph("Suggested heading structure", S["h3"]))
        for item in drafts["headingOutline"][:10]:
            indent = 0 if item["level"] == 1 else 12
            story.append(Paragraph(f"{'&nbsp;' * indent}H{item['level']} — {escape(item['text'])}", S["cell"]))
    return story


def _methodology(report: dict[str, Any]) -> list[Flowable]:
    scores = report.get("scores", {})
    story = [Paragraph("Methodology", S["h2"])]
    for line in scores.get("explanation", []):
        story.append(Paragraph(f"• {escape(line)}", S["body"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Scoring model: each check has a fixed weight. Pass = full weight, warning = 50–70% credit, "
        "fail = 0, not tested = excluded from both earned and available points. "
        "Pillar score = 100 × earned ÷ available. Overall = weighted blend of SEO (40%), AEO (30%) and GEO (30%).",
        S["small"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Limitations", S["h2"]))
    for limitation in report.get("limitations", [])[:8]:
        story.append(Paragraph(f"• {escape(limitation)}", S["small"]))
    return story


def _cta(report: dict[str, Any]) -> list[Flowable]:
    story = [Spacer(1, 8), Rule(), Spacer(1, 6),
             Paragraph("Your website has opportunities to improve its search and AI visibility.", S["h3"]),
             Paragraph(
                 f"{settings.brand_name} is an AI growth partner building AI-ready websites, automation and "
                 "search visibility systems. If you would like these findings implemented — schema, answer-focused "
                 "content, entity cleanup, crawler access and technical fixes — we run a professional audit and a "
                 f"prioritised implementation plan.", S["body"]),
             Spacer(1, 6),
             Paragraph(
                 f"<b>Contact:</b> {escape(settings.contact_url)}"
                 + (f" · {escape(settings.contact_email)}" if settings.contact_email else "")
                 + f" · {escape(settings.brand_url)}", S["small"])]
    return story


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render_report(report: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = ReportDoc(buffer, report)
    story: list[Flowable] = []
    story += _cover(report)
    story.append(Spacer(1, 18))
    story += _executive_summary(report)
    story.append(Spacer(1, 4))
    story += _site_snapshot(report)
    story += _critical_findings(report)
    story += _pillar_performance(report)
    story += _pillar_tables(report)
    story.append(PageBreak())
    story += _roadmap(report)
    story.append(Spacer(1, 6))
    story += _drafts(report)
    story.append(PageBreak())
    story += _methodology(report)
    story += _cta(report)
    doc.build(story)
    return buffer.getvalue()
