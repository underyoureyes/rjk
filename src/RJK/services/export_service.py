import csv
import io
from datetime import date, datetime
from typing import Optional


def _coerce(val):
    """Convert ISO date strings to date objects so Excel writes real date cells."""
    if isinstance(val, str) and len(val) == 10:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            pass
    return val


class ExportService:
    def to_csv(self, rows: list[dict]) -> bytes:
        if not rows:
            return b""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def to_excel(self, rows: list[dict], sheet_name: str = "Report") -> bytes:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError as exc:
            raise RuntimeError("openpyxl is not installed") from exc

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name[:31]

        if not rows:
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        headers = list(rows[0].keys())
        ws.append(headers)

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="003087")
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill

        for row in rows:
            ws.append([_coerce(row.get(h)) for h in headers])

        # Apply date format to columns that contain date objects
        for col_idx, header in enumerate(headers, start=1):
            col_vals = [row.get(header) for row in rows]
            if any(isinstance(_coerce(v), date) for v in col_vals):
                col_letter = get_column_letter(col_idx)
                for cell in ws[col_letter][1:]:   # skip header row
                    if isinstance(cell.value, date):
                        cell.number_format = "YYYY-MM-DD"

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def to_pdf(self, rows: list[dict], title: str = "Report", params: str = "") -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            )
        except ImportError as exc:
            raise RuntimeError("reportlab is not installed") from exc

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            leftMargin=1 * cm, rightMargin=1 * cm,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )
        styles = getSampleStyleSheet()
        story = [Paragraph(title, styles['Title'])]
        if params:
            story.append(Paragraph(f"<i>{params}</i>", styles['Normal']))
        story.append(Spacer(1, 0.3 * cm))

        if not rows:
            story.append(Paragraph("No data", styles['Normal']))
            doc.build(story)
            return buf.getvalue()

        headers = list(rows[0].keys())
        data = [headers] + [[str(row.get(h, '')) for h in headers] for row in rows]

        page_w = landscape(A4)[0] - 2 * cm
        col_w = page_w / len(headers)
        tbl = Table(data, colWidths=[col_w] * len(headers), repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0),  (-1, 0),  colors.HexColor('#003087')),
            ('TEXTCOLOR',    (0, 0),  (-1, 0),  colors.white),
            ('FONTNAME',     (0, 0),  (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0),  (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#f0f4f8')]),
            ('GRID',         (0, 0),  (-1, -1), 0.3, colors.HexColor('#cccccc')),
            ('ALIGN',        (0, 0),  (-1, -1), 'LEFT'),
            ('VALIGN',       (0, 0),  (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',  (0, 0),  (-1, -1), 3),
            ('RIGHTPADDING', (0, 0),  (-1, -1), 3),
            ('TOPPADDING',   (0, 0),  (-1, -1), 2),
            ('BOTTOMPADDING',(0, 0),  (-1, -1), 2),
        ]))
        story.append(tbl)
        doc.build(story)
        return buf.getvalue()

    def to_ppt(self, rows: list[dict], title: str = "Report", params: str = "") -> bytes:
        try:
            from pptx import Presentation
            from pptx.dml.color import RGBColor
            from pptx.util import Inches, Pt
        except ImportError as exc:
            raise RuntimeError("python-pptx is not installed") from exc

        _BRAND   = RGBColor(0, 48, 135)    # #003087
        _WHITE   = RGBColor(255, 255, 255)
        _ALT_ROW = RGBColor(240, 244, 248)
        _MAX_ROWS_PER_SLIDE = 35
        _MAX_ROWS = 500

        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        # Title slide
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = title
        slide.placeholders[1].text = params or f"{len(rows):,} rows"

        if not rows:
            buf = io.BytesIO()
            prs.save(buf)
            return buf.getvalue()

        headers = list(rows[0].keys())
        display = rows[:_MAX_ROWS]
        truncated = len(rows) > _MAX_ROWS

        for start in range(0, len(display), _MAX_ROWS_PER_SLIDE):
            chunk = display[start:start + _MAX_ROWS_PER_SLIDE]
            slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank

            # Slide sub-title text box
            tb = slide.shapes.add_textbox(Inches(0.2), Inches(0.05), Inches(12.9), Inches(0.45))
            tf = tb.text_frame
            tf.text = f"{title}  —  rows {start + 1}–{start + len(chunk)}"
            run = tf.paragraphs[0].runs[0]
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = _BRAND

            # Table
            tbl_rows = len(chunk) + 1
            shape = slide.shapes.add_table(
                tbl_rows, len(headers),
                Inches(0.2), Inches(0.55), Inches(12.9), Inches(6.8),
            )
            tbl = shape.table
            col_w = int(Inches(12.9) / len(headers))
            for ci in range(len(headers)):
                tbl.columns[ci].width = col_w

            # Header row
            for ci, h in enumerate(headers):
                cell = tbl.cell(0, ci)
                cell.text = h
                cell.fill.solid()
                cell.fill.fore_color.rgb = _BRAND
                p = cell.text_frame.paragraphs[0]
                p.font.color.rgb = _WHITE
                p.font.bold = True
                p.font.size = Pt(7)

            # Data rows
            for ri, row in enumerate(chunk, start=1):
                for ci, h in enumerate(headers):
                    cell = tbl.cell(ri, ci)
                    cell.text = str(row.get(h, ''))
                    p = cell.text_frame.paragraphs[0]
                    p.font.size = Pt(6.5)
                    if ri % 2 == 0:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = _ALT_ROW

        if truncated:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = "Note: truncated"
            slide.placeholders[1].text = (
                f"This export shows the first {_MAX_ROWS:,} of {len(rows):,} rows. "
                "Use CSV or Excel export for the full dataset."
            )

        buf = io.BytesIO()
        prs.save(buf)
        return buf.getvalue()
