import csv
import io


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
        except ImportError as exc:
            raise RuntimeError("openpyxl is not installed") from exc

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name[:31]  # Excel sheet name limit

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
            ws.append([row.get(h) for h in headers])

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
