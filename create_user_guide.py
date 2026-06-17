"""
create_user_guide.py — generates RJK_User_Guide.pdf
Run from the project root:  python create_user_guide.py
Output: ../rjk_dist/RJK_User_Guide.pdf
"""

from pathlib import Path
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.platypus.flowables import Flowable

# ── Palette ──────────────────────────────────────────────────────────────────
BLUE   = HexColor("#003087")
LBLUE  = HexColor("#1565c0")
TEAL   = HexColor("#0891b2")
GREEN  = HexColor("#2ea043")
AMBER  = HexColor("#d97706")
LGREY  = HexColor("#f0f4f8")
GREY   = HexColor("#6b7280")
BORDER = HexColor("#d1d5db")

PW, PH = A4   # 595 × 841 pts
TODAY  = date.today().strftime("%d %B %Y")
OUT    = Path(__file__).parent.parent / "rjk_dist" / "RJK_User_Guide.pdf"

# ── Paragraph styles ─────────────────────────────────────────────────────────
_ss = getSampleStyleSheet()

def _ps(base, **kw):
    return ParagraphStyle(base + str(id(kw)), parent=_ss[base], **kw)

COVER_TITLE = _ps("Title",   fontSize=32, textColor=white,    alignment=TA_CENTER, leading=40)
COVER_SUB   = _ps("Normal",  fontSize=14, textColor=HexColor("#cce0ff"), alignment=TA_CENTER)
COVER_DATE  = _ps("Normal",  fontSize=10, textColor=HexColor("#93c5fd"), alignment=TA_CENTER)
H1  = _ps("Heading1", textColor=BLUE,  fontSize=18, spaceAfter=8,  spaceBefore=16)
H2  = _ps("Heading2", textColor=BLUE,  fontSize=13, spaceAfter=6,  spaceBefore=12)
H3  = _ps("Heading3", textColor=LBLUE, fontSize=11, spaceAfter=4,  spaceBefore=8)
BOD = _ps("Normal",   fontSize=10, leading=15, spaceAfter=5)
SML = _ps("Normal",   fontSize=9,  leading=13, textColor=GREY, spaceAfter=3)
BUL = _ps("Normal",   fontSize=10, leading=14, leftIndent=14, spaceAfter=3)
COD = _ps("Code",     fontSize=9,  leading=14, leftIndent=8, backColor=LGREY)
TBH = _ps("Normal",   fontSize=9,  textColor=white, alignment=TA_CENTER)
TBC = _ps("Normal",   fontSize=9,  leading=13)

def sp(n=8):  return Spacer(1, n)
def hr():     return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6, spaceBefore=6)
def h1(t):    return Paragraph(t, H1)
def h2(t):    return Paragraph(t, H2)
def h3(t):    return Paragraph(t, H3)
def p(t):     return Paragraph(t, BOD)
def sml(t):   return Paragraph(t, SML)
def bul(t):   return Paragraph(f"<bullet>•</bullet> {t}", BUL)
def code(t):  return Paragraph(t, COD)


# ── Custom Flowables ─────────────────────────────────────────────────────────



class ArchDiagram(Flowable):
    """Three-tier architecture diagram."""
    def __init__(self): Flowable.__init__(self); self.width=14*cm; self.height=8.5*cm
    def wrap(self, *a): return self.width, self.height

    def draw(self):
        c = self.canv
        W, H = self.width, self.height

        def box(x, y, w, h, fill, title, sub=""):
            c.setFillColor(fill); c.setStrokeColor(white); c.setLineWidth(1)
            c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
            c.setFillColor(white); c.setFont("Helvetica-Bold", 9)
            ty = y + h/2 + (5 if sub else 0)
            c.drawCentredString(x + w/2, ty, title)
            if sub:
                c.setFont("Helvetica", 7.5); c.setFillColor(HexColor("#cce0ff") if fill == BLUE else HexColor("#d1fae5"))
                c.drawCentredString(x + w/2, y + h/2 - 9, sub)

        def darrow(x, y1, y2, label=""):
            c.setStrokeColor(GREY); c.setFillColor(GREY); c.setLineWidth(1.5)
            c.line(x, y1, x, y2)
            ph = c.beginPath(); ph.moveTo(x-4, y2+7); ph.lineTo(x+4, y2+7); ph.lineTo(x, y2); ph.close()
            c.drawPath(ph, fill=1, stroke=0)
            if label:
                c.setFont("Helvetica", 7); c.setFillColor(GREY)
                c.drawString(x+5, (y1+y2)/2 - 4, label)

        m = 0.3*cm
        # Row 1 – Browser
        box(m, H-1.8*cm, W-2*m, 1.5*cm, LBLUE, "Browser — Single Page Application",
            "Bootstrap 5.3  ·  ag-Grid 32  ·  Plotly.js  ·  SheetJS")
        darrow(W/2, H-1.8*cm, H-2.8*cm, "HTTP/REST")

        # Row 2 – FastAPI
        box(m, H-4.3*cm, W-2*m, 1.4*cm, BLUE, "FastAPI Backend  (app.py)",
            "Report Service  ·  Audit Service  ·  Export  ·  Chart  ·  Admin")
        # Three down arrows
        for frac in [1/6, 1/2, 5/6]:
            darrow(W*frac, H-4.3*cm, H-5.3*cm)

        # Row 3 – three stores
        sw = (W - 4*m) / 3
        stores = [
            (GREEN,  "reports/*.sql",    "SQL + YAML metadata"),
            (TEAL,   "SQLite audit.db",  "Runs · Sign-offs · Persist"),
            (AMBER,  "MySQL (optional)", "Aggregation storage"),
        ]
        for i, (col, t, s) in enumerate(stores):
            bx = m + i*(sw + m)
            box(bx, H-7*cm, sw, 1.6*cm, col, t, s)

        c.setFont("Helvetica", 7); c.setFillColor(GREY)
        c.drawString(m, 0.2*cm, "* JSON file storage is used when MYSQL_URL is not configured.")


class Flowchart(Flowable):
    """Main workflow flowchart — top-to-bottom with two decision branches."""

    ITEMS = [
        # (shape, colour, label, note)
        ("oval",    GREEN,  "START",                          ""),
        ("rect",    BLUE,   "Launch App",                     "python launch.py  →  opens browser at localhost:8000"),
        ("rect",    BLUE,   "Browse Report Tree",             "Click a folder in the left sidebar to expand it"),
        ("rect",    BLUE,   "Select Report & Set Parameters", "Choose dates, regions, or other parameter values"),
        ("rect",    BLUE,   "Click  Run Report",              "Results load into the Raw Data grid"),
        ("rect",    BLUE,   "Review Results  (Raw Data tab)", "Sort, search, show/hide columns"),
        ("diamond", AMBER,  "Need to\nAggregate?",            "NO → export CSV/Excel directly"),
        ("rect",    LBLUE,  "Aggs Tab — Configure",          "Choose group-by columns and value aggregations"),
        ("rect",    LBLUE,  "Preview Aggregation",           "Click Preview to verify the summarised rows"),
        ("rect",    LBLUE,  "Sign Off Aggregation",          "Enter your name and notes, click Sign Off"),
        ("rect",    LBLUE,  "Persist Dataset",               "Saves approved data; appears in Reporting tab"),
        ("diamond", AMBER,  "Create\nChart?",                 "NO → review the Audit tab"),
        ("rect",    TEAL,   "Reporting Tab — Select Dataset", "Pick from persisted datasets or current raw run"),
        ("rect",    TEAL,   "Choose Chart Type & Axes",       "Bar, line, scatter, pie, histogram; X/Y/colour"),
        ("rect",    TEAL,   "Generate Chart",                 "Click Generate — interactive Plotly chart renders"),
        ("rect",    TEAL,   "Export Chart",                   "Download PDF, PowerPoint slide, or PNG image"),
        ("rect",    HexColor("#7c3aed"), "Review Audit Trail","Sign-offs · persist details · all report runs"),
        ("oval",    GREEN,  "END",                            ""),
    ]

    BOX_W  = 4.5 * cm
    BOX_H  = 0.85 * cm
    DIA_W  = 3.0 * cm
    DIA_H  = 1.1 * cm
    OVAL_W = 2.2 * cm
    OVAL_H = 0.7 * cm
    GAP    = 0.48 * cm
    NOTE_X = 0.3 * cm   # right of box right edge

    def __init__(self):
        Flowable.__init__(self)
        self.width  = 15 * cm
        self.height = self._total_height()

    def _item_h(self, shape):
        return {"oval": self.OVAL_H, "rect": self.BOX_H, "diamond": self.DIA_H}[shape]

    def _total_height(self):
        total = sum(self._item_h(s) for s, *_ in self.ITEMS)
        total += self.GAP * (len(self.ITEMS) - 1)
        return total + 1 * cm

    def wrap(self, *a): return self.width, self.height

    def _centres(self):
        """Return list of (cx, cy) centre points for each item, top→bottom."""
        CX = self.width * 0.30
        centres = []
        y = self.height - 0.5 * cm
        for shape, *_ in self.ITEMS:
            h = self._item_h(shape)
            y -= h / 2
            centres.append((CX, y))
            y -= h / 2 + self.GAP
        return centres

    def _draw_shape(self, c, cx, cy, shape, fill, label):
        c.setFillColor(fill)
        c.setStrokeColor(white)
        c.setLineWidth(0.8)
        w = {"oval": self.OVAL_W, "rect": self.BOX_W, "diamond": self.DIA_W}[shape]
        h = self._item_h(shape)

        if shape == "oval":
            c.ellipse(cx - w/2, cy - h/2, cx + w/2, cy + h/2, fill=1, stroke=1)
        elif shape == "rect":
            c.roundRect(cx - w/2, cy - h/2, w, h, 5, fill=1, stroke=1)
        elif shape == "diamond":
            hw, hh = w/2, h/2
            pts = [cx, cy+hh,  cx+hw, cy,  cx, cy-hh,  cx-hw, cy]
            path = c.beginPath()
            path.moveTo(pts[0], pts[1])
            for i in range(2, 8, 2): path.lineTo(pts[i], pts[i+1])
            path.close()
            c.drawPath(path, fill=1, stroke=1)

        # Label (multi-line)
        lines = label.split("\n")
        c.setFillColor(white)
        lh = 9
        c.setFont("Helvetica-Bold" if shape == "oval" else "Helvetica-Bold" if shape == "diamond" else "Helvetica", 8)
        ty = cy + (len(lines) - 1) * lh / 2
        for ln in lines:
            c.drawCentredString(cx, ty - 2.5, ln)
            ty -= lh

    def _darrow(self, c, cx, y_top, y_bot):
        c.setStrokeColor(GREY); c.setFillColor(GREY); c.setLineWidth(1.2)
        c.line(cx, y_top, cx, y_bot + 5)
        ph = c.beginPath(); ph.moveTo(cx-3.5, y_bot+7); ph.lineTo(cx+3.5, y_bot+7); ph.lineTo(cx, y_bot); ph.close()
        c.drawPath(ph, fill=1, stroke=0)

    def draw(self):
        c   = self.canv
        cxs = self._centres()
        CX  = cxs[0][0]

        # decision indices
        D1 = 6   # "Aggregate?"
        D2 = 11  # "Create Chart?"

        # Draw main arrows first
        for i in range(len(self.ITEMS) - 1):
            shape_cur  = self.ITEMS[i][0]
            shape_next = self.ITEMS[i+1][0]
            cy_cur     = cxs[i][1]
            cy_next    = cxs[i+1][1]
            top  = cy_cur  - self._item_h(shape_cur)  / 2
            bot  = cy_next + self._item_h(shape_next) / 2
            self._darrow(c, CX, top, bot)

        # Draw shapes (on top of arrows)
        for i, (shape, fill, label, note) in enumerate(self.ITEMS):
            cx, cy = cxs[i]
            self._draw_shape(c, cx, cy, shape, fill, label)

            # Side note
            if note:
                nw = self.width - CX - self.BOX_W/2 - 0.4*cm
                nx = CX + self.BOX_W/2 + 0.4*cm
                c.setFont("Helvetica", 7); c.setFillColor(GREY)
                # simple text wrap (two lines max)
                words = note.split()
                line1, line2 = "", ""
                for w in words:
                    test = (line1 + " " + w).strip()
                    if c.stringWidth(test, "Helvetica", 7) < nw:
                        line1 = test
                    else:
                        line2 = (line2 + " " + w).strip()
                c.drawString(nx, cy + 3, line1)
                if line2:
                    c.drawString(nx, cy - 7, line2)

        # YES labels on decisions
        for di in [D1, D2]:
            cx, cy = cxs[di]
            c.setFont("Helvetica-Bold", 7.5); c.setFillColor(GREEN)
            c.drawString(cx - 5, cy - self.DIA_H/2 - 10, "YES ↓")

        # NO branch for D1 — Export box to the right
        self._draw_no_branch(c, cxs[D1], "NO → Export CSV / Excel", TEAL)
        # NO branch for D2 — Skip to Audit
        self._draw_no_branch(c, cxs[D2], "NO → Skip to Audit Trail", HexColor("#7c3aed"))

    def _draw_no_branch(self, c, centre, label, col):
        cx, cy = centre
        bx = cx + self.DIA_W/2          # right tip of diamond
        ex = cx + self.DIA_W/2 + 0.35*cm
        bw = self.width - ex - 0.15*cm
        bh = 0.65*cm
        # horizontal arrow from diamond tip
        c.setStrokeColor(GREY); c.setFillColor(GREY); c.setLineWidth(1.2)
        c.line(bx, cy, ex, cy)
        ph = c.beginPath(); ph.moveTo(ex+5, cy-3.5); ph.lineTo(ex+5, cy+3.5); ph.lineTo(ex+12, cy); ph.close()
        c.drawPath(ph, fill=1, stroke=0)
        # label box
        c.setFillColor(col); c.setStrokeColor(white); c.setLineWidth(0.6)
        c.roundRect(ex+12, cy - bh/2, bw, bh, 4, fill=1, stroke=1)
        c.setFillColor(white); c.setFont("Helvetica", 7.5)
        c.drawCentredString(ex + 12 + bw/2, cy - 3.5, label)


# ── Page header / footer callback ────────────────────────────────────────────
def _on_page(canvas, doc):
    canvas.saveState()
    # Header bar
    canvas.setFillColor(BLUE)
    canvas.rect(0, PH - 1.5*cm, PW, 1.5*cm, fill=1, stroke=0)
    canvas.setFillColor(white); canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(2*cm, PH - 0.95*cm, "RJK Reporting Framework — User Guide")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PW - 2*cm, PH - 0.95*cm, TODAY)
    # Footer
    canvas.setStrokeColor(BORDER); canvas.setLineWidth(0.4)
    canvas.line(2*cm, 1.3*cm, PW - 2*cm, 1.3*cm)
    canvas.setFont("Helvetica", 8); canvas.setFillColor(GREY)
    canvas.drawString(2*cm, 0.7*cm, "CONFIDENTIAL — FOR INTERNAL USE ONLY")
    canvas.drawRightString(PW - 2*cm, 0.7*cm, f"Page {doc.page}")
    canvas.restoreState()

def _on_first_page(canvas, doc):
    canvas.saveState()
    # Full-bleed cover
    canvas.setFillColor(BLUE)
    canvas.rect(0, 0, PW, PH, fill=1, stroke=0)
    # Upper accent panel
    canvas.setFillColor(HexColor("#1e5bbf"))
    canvas.rect(0, PH * 0.52, PW, PH * 0.48, fill=1, stroke=0)
    # Decorative grid lines on lower half
    canvas.setStrokeColor(HexColor("#1a4a8a")); canvas.setLineWidth(0.4)
    for i in range(0, int(PW) + 40, 40):
        canvas.line(i, 0, i, PH * 0.52)
    # Title
    canvas.setFillColor(white); canvas.setFont("Helvetica-Bold", 36)
    canvas.drawCentredString(PW/2, PH * 0.70, "RJK Reporting Framework")
    canvas.setFont("Helvetica", 20); canvas.setFillColor(HexColor("#93c5fd"))
    canvas.drawCentredString(PW/2, PH * 0.63, "User Guide")
    # Divider
    canvas.setStrokeColor(HexColor("#3b82f6")); canvas.setLineWidth(1.5)
    canvas.line(PW*0.2, PH*0.59, PW*0.8, PH*0.59)
    # Version / date
    canvas.setFont("Helvetica", 11); canvas.setFillColor(HexColor("#93c5fd"))
    canvas.drawCentredString(PW/2, PH*0.55, f"Version 1.0   ·   {TODAY}")
    # Feature bullets
    canvas.setFont("Helvetica", 11); canvas.setFillColor(HexColor("#dbeafe"))
    canvas.drawCentredString(PW/2, PH*0.42, "A FastAPI + ag-Grid SQL reporting platform")
    canvas.setFont("Helvetica", 9.5); canvas.setFillColor(HexColor("#93c5fd"))
    for i, ln in enumerate([
        "Discover SQL reports automatically  ·  Parameter toolbars",
        "Sign-off workflow  ·  Aggregations  ·  Interactive Plotly charts",
        "Full audit trail  ·  CSV / Excel / PDF / PowerPoint export",
        "Admin rename & soft-delete  ·  PII / sensitive-data scanner",
    ]):
        canvas.drawCentredString(PW/2, PH*0.36 - i*16, ln)
    # Footer
    canvas.setFont("Helvetica", 8); canvas.setFillColor(HexColor("#60a5fa"))
    canvas.drawCentredString(PW/2, 1.5*cm, "CONFIDENTIAL — FOR INTERNAL USE ONLY")
    canvas.restoreState()


# ── Helpers for styled tables ─────────────────────────────────────────────────
def info_table(rows, col_widths=None):
    col_widths = col_widths or [4*cm, 11*cm]
    t = Table([[Paragraph(r[0], TBH), Paragraph(r[1], TBC)] for r in rows],
              colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,-1), BLUE),
        ("BACKGROUND",    (1,0), (1,-1), LGREY),
        ("ROWBACKGROUNDS",(1,0), (1,-1), [LGREY, white]),
        ("TEXTCOLOR",     (0,0), (0,-1), white),
        ("FONTNAME",      (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [LGREY, white]),
        ("BACKGROUND",    (0,0), (0,-1), BLUE),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    return t


# ── Document sections ────────────────────────────────────────────────────────
def _section_overview():
    return [
        h1("1.  What is the RJK Reporting Framework?"),
        p("RJK is a self-contained SQL reporting platform. Report authors write standard SQL "
          "files with a short YAML metadata block embedded in a comment. The framework "
          "discovers those files automatically at startup, renders a browser-based interface "
          "with parameter controls, and lets users run reports, aggregate results, sign off "
          "on them, persist approved datasets, and build interactive charts — all without "
          "writing any code."),
        sp(6),
        h2("Key capabilities"),
        bul("Auto-discovery of SQL reports — drop a <code>.sql</code> file in the <code>reports/</code> "
            "folder and it appears in the tree immediately on next launch."),
        bul("Parameter toolbar rendered from YAML metadata — date pickers, dropdowns, free-text."),
        bul("Mock mode (MOCK_MODE=true) generates realistic cartesian-product data so reports "
            "can be developed and demonstrated without a live database."),
        bul("ag-Grid results grid with sort, filter, search, column chooser, CSV and Excel export."),
        bul("Aggregation engine — group and summarise raw results; sign off and persist for governance."),
        bul("Reporting tab — interactive Plotly charts (bar, line, scatter, pie, histogram, area, box) "
            "with export to PDF, PowerPoint, and PNG."),
        bul("Audit trail — every report run and sign-off is logged to SQLite with full parameter capture."),
        bul("Admin operations — rename or soft-delete (trash) reports and folders without touching files."),
        sp(10),
        h2("Architecture"),
        sml("The application is a three-tier web app running entirely on a single machine."),
        sp(6),
        ArchDiagram(),
        sp(8),
        info_table([
            ("Browser (SPA)",     "Single-page application built with Bootstrap 5.3, ag-Grid 32, and Plotly.js. "
                                  "All user interaction happens here; no page reloads."),
            ("FastAPI backend",   "Python REST API (app.py). Serves the SPA and exposes ~30 endpoints for "
                                  "report discovery, running, exporting, charting, audit, and admin."),
            ("reports/*.sql",     "SQL files with embedded YAML metadata. The mock block defines synthetic "
                                  "data so no database is needed during development."),
            ("SQLite audit.db",   "Local database recording every report run, sign-off, and persist action. "
                                  "Created automatically in data/audit.db on first launch."),
            ("MySQL (optional)",  "When MYSQL_URL is set in .env, approved aggregations are persisted to a "
                                  "MySQL table instead of local JSON files."),
        ], col_widths=[3.8*cm, 11.2*cm]),
    ]


def _section_flowchart():
    return [
        PageBreak(),
        h1("2.  End-to-End Process Flow"),
        p("The diagram below shows the complete user journey from launching the application "
          "through to producing a signed-off chart or export. Decision points (amber diamonds) "
          "indicate optional paths."),
        sp(8),
        Flowchart(),
    ]


def _section_getting_started():
    return [
        PageBreak(),
        h1("3.  Getting Started"),
        h2("3.1  Prerequisites"),
        info_table([
            ("Python",        "3.10 or later (3.11+ recommended)"),
            ("pip packages",  "Install with:  pip install -r requirements.txt"),
            ("Database",      "Not required in MOCK_MODE=true (the default). For a real DB set "
                              "MOCK_MODE=false and DB_CONN_STRING in .env"),
            ("Browser",       "Any modern browser — Chrome, Edge, Firefox, Safari"),
        ], col_widths=[3*cm, 12*cm]),
        sp(8),
        h2("3.2  Starting the Application"),
        p("From the project root directory run:"),
        code("python launch.py"),
        p("This starts uvicorn on port 8000 and opens your default browser automatically. "
          "Alternatively run <code>uvicorn app:app --reload</code> for development with "
          "hot-reload."),
        sp(6),
        h2("3.3  Interface Layout"),
        sp(4),
        info_table([
            ("Top navbar",       "RJK logo, application title, and tab switcher (Raw Data | Aggs | Reporting | Audit)."),
            ("Left sidebar",     "Collapsible report tree. Click a folder to expand; click a report name to load it. "
                                 "Drag the right edge to resize. Admin users see a right-click context menu."),
            ("Parameter toolbar","Appears below the sidebar when a report is selected. Date pickers, dropdowns, and "
                                 "text inputs are rendered from the report's YAML metadata."),
            ("Main area",        "Changes with the active tab: report grid / aggregation grid / chart canvas / audit grids."),
            ("Log console",      "Collapsible panel at the bottom showing info, success, and error messages."),
        ], col_widths=[3.2*cm, 11.8*cm]),
    ]


def _section_raw_data():
    return [
        sp(10),
        h1("4.  Running Reports  —  Raw Data Tab"),
        h2("Step-by-step"),
        info_table([
            ("Step 1", "Select a report from the tree in the left sidebar."),
            ("Step 2", "Set parameter values in the toolbar (e.g. Sales Date, Region). "
                       "Sensible defaults are pre-filled from the SQL metadata."),
            ("Step 3", "Click  Run Report. The grid populates with results. A row count "
                       "badge shows how many rows were returned."),
            ("Step 4", "Use the  Search  box to filter rows, or click column headers to sort."),
            ("Step 5", "Click  Columns  to show or hide individual columns."),
            ("Step 6", "Click  Export  to download all rows as CSV or Excel."),
        ], col_widths=[2.5*cm, 12.5*cm]),
        sp(8),
        h2("Sign-off & Persist (from Raw Data tab)"),
        p("A persistent bar at the bottom of the Raw Data grid lets you sign off and persist "
          "the raw result set directly without going through the Aggs tab. Use this when you "
          "need to store the full dataset without summarising it."),
        bul("Signed By and Persisted By are auto-populated from your OS login."),
        bul("Click  Sign Off  to record approval in the audit log."),
        bul("Click  Persist  (becomes active after sign-off) to save the dataset."),
    ]


def _section_aggs():
    return [
        sp(10),
        h1("5.  Aggregations  —  Aggs Tab"),
        p("The Aggs tab lets you summarise raw report data by grouping on dimension columns "
          "and applying aggregation functions (sum, mean, count, min, max) to numeric columns. "
          "The result is a smaller, purpose-built dataset suitable for charting or sharing."),
        h2("Workflow"),
        info_table([
            ("Step 1", "Run a report on the Raw Data tab first — the Aggs tab needs source rows."),
            ("Step 2", "Switch to the  Aggs  tab. The source row count is shown in the badge."),
            ("Step 3", "Choose one or more  Group By  columns (dimensions, e.g. Region, Month)."),
            ("Step 4", "For each numeric column select an aggregation: Sum, Mean, Count, Min, or Max."),
            ("Step 5", "Click  Preview Aggregation  — the result grid appears below."),
            ("Step 6", "Review the  Control Totals  banner to verify aggregated values match source."),
            ("Step 7", "Click  Sign Off Aggregation  — enter your name and optional notes."),
            ("Step 8", "Once signed off,  Persist Dataset  becomes active. Click it to save "
                       "the dataset (to JSON or MySQL depending on configuration)."),
        ], col_widths=[2.5*cm, 12.5*cm]),
        sp(6),
        h2("Export"),
        p("Before or after persisting, click  Export  in the Aggregated Result toolbar to "
          "download the aggregated rows as CSV or Excel."),
    ]


def _section_reporting():
    return [
        sp(10),
        h1("6.  Reporting & Charts  —  Reporting Tab"),
        p("The Reporting tab turns a persisted (or live raw) dataset into an interactive "
          "Plotly chart. Charts can be exported as PDF, PowerPoint slides, or PNG images."),
        h2("Selecting a Dataset"),
        bul("Persisted datasets appear in the  Dataset  list on the left panel."),
        bul("Select  Raw data (current run)  to chart the most recently run report without persisting."),
        bul("Hover over a dataset name to see a tooltip with row count, report path, size, and creator."),
        sp(4),
        h2("Chart Controls"),
        info_table([
            ("Chart Type",    "Bar, Line, Scatter, Pie, Area, Histogram, or Box plot. "
                              "Click the icon buttons to switch type."),
            ("X-Axis",        "Select the column to use for the horizontal axis or category labels."),
            ("Y-Axis",        "Select the column to use for values (numeric columns preferred)."),
            ("Group / Colour","Optional. Split the series by a dimension column for multi-series charts."),
            ("Chart Title",   "Auto-filled from the dataset name; edit freely."),
            ("Show Legend",   "Toggle the chart legend on or off."),
        ], col_widths=[3*cm, 12*cm]),
        sp(6),
        h2("Generating & Exporting"),
        bul("Click  Generate Chart  — the chart renders in the panel on the right."),
        bul("Click  Export  → PDF, PowerPoint, or PNG to download the chart."),
        bul("The  Dataset Data  grid below the chart shows all rows from the selected dataset "
            "with its own Search, Export (CSV/Excel), and Columns controls."),
        sp(4),
        h2("Resizing Panels"),
        p("Drag the vertical handle between the controls panel and the chart area to adjust "
          "the split. The dataset list in the controls panel scrolls independently."),
    ]


def _section_audit():
    return [
        sp(10),
        h1("7.  Audit Trail  —  Audit Tab"),
        p("The Audit tab provides a full history of activity in two grids."),
        h2("Sign-offs & Persisted Data  (top grid)"),
        p("Every sign-off is recorded here with:"),
        info_table([
            ("Who / When",       "signed_off_by, signed_off_at"),
            ("Report",           "The SQL report path that was run"),
            ("Parameters",       "The exact parameter values used for the run"),
            ("Notes",            "Free-text notes entered at sign-off"),
            ("Persist details",  "Dataset name, format (JSON/MySQL), storage location, "
                                 "size in bytes, row count vs source row count"),
            ("Persisted By",     "The OS user who clicked Persist and when"),
        ], col_widths=[3.2*cm, 11.8*cm]),
        sp(6),
        h2("Report Runs  (bottom grid)"),
        p("Every report execution is logged with report path, parameters, run time, row count, "
          "and status (success / error). Use this to investigate what parameters produced a "
          "particular result set."),
        sp(4),
        h2("Exporting Audit Records"),
        p("Both grids have their own Export (CSV / Excel) and Columns chooser controls. "
          "Use Search to filter by user, date, or report name before exporting."),
    ]


def _section_admin():
    return [
        sp(10),
        h1("8.  Admin Operations"),
        p("Admin users see additional controls for managing the report library. "
          "Admin access is determined by the ACL configuration in <code>data/acl.json</code>."),
        h2("Right-Click Context Menu"),
        p("Right-click any report or folder name in the sidebar to access:"),
        info_table([
            ("Rename",        "Opens a modal dialog. Enter the new name and confirm. "
                              "The underlying file or folder is renamed on disk immediately."),
            ("Move to Trash", "Moves the report (or entire folder) to  reports/_trash/  with a "
                              "timestamp suffix. The item disappears from the tree. "
                              "Files can be recovered by moving them back manually."),
        ], col_widths=[3*cm, 12*cm]),
        sp(6),
        h2("Scanner Configuration"),
        p("The Admin tab (visible to admin users) lets you configure keyword lists for the "
          "built-in data scanner, which flags columns containing sensitive or PII data before "
          "a dataset is persisted."),
        h2("ACL Configuration"),
        p("Access control rules are stored in <code>data/acl.json</code> and are editable via the "
          "Admin tab. When <code>AUTH_ENABLED=false</code> (the default for local development) "
          "all users are treated as non-admin and admin operations are disabled."),
    ]


def _section_reference():
    return [
        PageBreak(),
        h1("9.  Quick Reference"),
        sp(6),
        h2("Key Keyboard / UI Shortcuts"),
        info_table([
            ("Run Report",          "Click  Run Report  button in the parameter toolbar"),
            ("Export Raw Data",     "Raw Data tab → Export → CSV or Excel"),
            ("Export Agg Data",     "Aggs tab → Aggregated Result toolbar → Export → CSV or Excel"),
            ("Export Chart",        "Reporting tab → Export dropdown → PDF / PPT / PNG"),
            ("Column Chooser",      "Any grid → Columns button → check/uncheck columns"),
            ("Search / Filter",     "Search box in any grid toolbar — filters all visible columns"),
            ("Resize Sidebar",      "Drag the right edge of the sidebar panel"),
            ("Resize Chart Panel",  "Drag the handle between controls and chart"),
            ("Admin: Rename",       "Right-click report or folder name → Rename"),
            ("Admin: Trash",        "Right-click report or folder name → Move to Trash"),
        ], col_widths=[4*cm, 11*cm]),
        sp(10),
        h2("API Endpoints"),
        sml("The REST API is self-documenting at  http://localhost:8000/docs  (FastAPI / Swagger UI)."),
        sp(4),
        info_table([
            ("GET  /api/reports",                   "List all discovered reports and the tree structure"),
            ("GET  /api/reports/meta?path=",        "Metadata for one report (title, params, description)"),
            ("POST /api/reports/run",               "Run a report and return JSON rows"),
            ("POST /api/reports/export/csv",        "Run a report and download as CSV"),
            ("POST /api/reports/export/excel",      "Run a report and download as Excel"),
            ("POST /api/aggs/persist",              "Persist an approved aggregation dataset"),
            ("GET  /api/aggs/persisted",            "List all persisted datasets"),
            ("GET  /api/aggs/persisted/{name}/rows","Fetch raw rows for a persisted dataset"),
            ("POST /api/reporting/chart",           "Generate a Plotly chart from a persisted dataset"),
            ("GET  /api/audit",                     "Fetch audit log (runs + sign-offs)"),
            ("POST /api/signoff",                   "Record a sign-off against a run"),
            ("PATCH /api/admin/fs/rename",          "Admin: rename a report file or folder"),
            ("DELETE /api/admin/fs/report",         "Admin: move a report to _trash/"),
        ], col_widths=[5.5*cm, 9.5*cm]),
        sp(10),
        h2("Environment Variables  (.env)"),
        info_table([
            ("MOCK_MODE",       "true (default) — generate synthetic data.  false — use real DB via pyodbc."),
            ("DB_CONN_STRING",  "pyodbc connection string (only used when MOCK_MODE=false)."),
            ("REPORTS_ROOT",    "Path to the SQL reports directory (default: reports)."),
            ("AUDIT_DB_PATH",   "Path to the SQLite audit database (default: data/audit.db)."),
            ("MYSQL_URL",       "SQLAlchemy MySQL URL for aggregation persistence (optional)."),
            ("AUTH_ENABLED",    "false (default) — disable ACL enforcement.  true — enforce admin rules."),
        ], col_widths=[3.5*cm, 11.5*cm]),
    ]


# ── Build ────────────────────────────────────────────────────────────────────
def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        topMargin=1.8*cm, bottomMargin=2*cm,
        leftMargin=2*cm,  rightMargin=2*cm,
        title="RJK Reporting Framework — User Guide",
        author="RJK",
    )

    story = []

    # Page 1 is the cover — drawn entirely by _on_first_page callback.
    # A single PageBreak pushes subsequent content to page 2.
    story.append(PageBreak())

    story += _section_overview()
    story += _section_flowchart()
    story += _section_getting_started()
    story += _section_raw_data()
    story += _section_aggs()
    story += _section_reporting()
    story += _section_audit()
    story += _section_admin()
    story += _section_reference()

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_page)
    print(f"User guide written: {OUT}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
