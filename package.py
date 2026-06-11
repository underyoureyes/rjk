"""
Build distribution zips for the RJK Reporting Framework.

Usage:
    python package.py

Outputs (next to the project root, NOT inside it):
    ../rjk_dist/rjk_app.zip          — full app, ready to run
    ../rjk_dist/rjk_test_hello.zip   — single hello_world.py for scan testing
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
OUT  = ROOT.parent / "rjk_dist"
OUT.mkdir(exist_ok=True)

APP_FILES = [
    "app.py",
    "launch.py",
    "requirements.txt",
    ".env.example",
    "CLAUDE.md",
    "reports/demo/frosty_treats/sales/daily_product_sales.sql",
    "reports/demo/stock_market/prices/daily_close_prices.sql",
    "data/mock/daily_close_prices.json",
    "scripts/fetch_real_prices.py",
    "src/RJK/__init__.py",
    "src/RJK/audit/__init__.py",
    "src/RJK/audit/audit_service.py",
    "src/RJK/config/__init__.py",
    "src/RJK/config/loader.py",
    "src/RJK/discovery/__init__.py",
    "src/RJK/discovery/report_discovery.py",
    "src/RJK/parser/__init__.py",
    "src/RJK/parser/sql_metadata_parser.py",
    "src/RJK/runners/__init__.py",
    "src/RJK/runners/base.py",
    "src/RJK/runners/mock_runner.py",
    "src/RJK/runners/odbc_runner.py",
    "src/RJK/services/__init__.py",
    "src/RJK/services/aggregation_service.py",
    "src/RJK/services/chart_service.py",
    "src/RJK/services/data_scanner.py",
    "src/RJK/services/export_service.py",
    "src/RJK/services/report_service.py",
    "src/RJK/ui/__init__.py",
    "src/RJK/ui/layout.py",
    "templates/index.html",
]


def build_app_zip():
    path = OUT / "rjk_app.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in APP_FILES:
            src = ROOT / f
            if not src.exists():
                print(f"  WARNING: missing {f}")
                continue
            z.write(src, f"rjk/{f}")
    print(f"rjk_app.zip        {path.stat().st_size:>10,} bytes   {path}")


def build_hello_zip():
    path = OUT / "rjk_test_hello.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("hello_world.py", 'print("Hello, World!")\n')
    print(f"rjk_test_hello.zip {path.stat().st_size:>10,} bytes   {path}")


if __name__ == "__main__":
    print(f"Building packages -> {OUT}\n")
    build_app_zip()
    build_hello_zip()
    print("\nDone.")
