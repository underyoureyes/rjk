"""
Playwright end-to-end UI tests for the RJK Reporting Framework.

These tests start a real uvicorn server, open Chromium, and verify that user
interactions (clicking buttons, selecting reports, switching tabs) produce the
expected visible changes.  They catch the class of bug where a button click
silently does nothing in the browser.

Run:
    pytest tests/test_ui_playwright.py -v --headed    # with visible browser
    pytest tests/test_ui_playwright.py -v             # headless (default)
"""

import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

# Make src importable when running directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Server fixture
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """Start a real uvicorn server for the session and yield its base URL."""
    port = _free_port()
    url  = f"http://127.0.0.1:{port}"

    server = uvicorn.Server(uvicorn.Config("app:app", host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until server is accepting connections
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                break
        except OSError:
            time.sleep(0.2)
    else:
        pytest.fail("Test server did not start in time")

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def page(live_server, browser):
    """Open a fresh page for each test, navigate to the app, wait for load."""
    pg = browser.new_page()
    pg.goto(live_server, wait_until="networkidle")
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIRST_REPORT_TITLE = "Ice Cream Daily Sales"
TIMEOUT = 10_000   # ms


def _select_first_report(page):
    """Expand the report tree and click the first visible leaf report."""
    # Wait for the tree to render (API call completes)
    page.wait_for_selector(".tree-folder", timeout=TIMEOUT)
    # Depth-0 folders are auto-expanded; click any closed (non-open) visible folders
    # to reveal nested content. Repeat a few times to handle deep nesting.
    for _ in range(5):
        # Click only closed (not yet open) folders that are currently visible
        closed = page.locator(".tree-folder:not(.open)").all()
        expanded = False
        for folder in closed:
            if folder.is_visible():
                folder.click()
                page.wait_for_timeout(150)
                expanded = True
        if not expanded:
            break
    # Wait for at least one report to become visible and click the first one
    page.wait_for_selector(".tree-report:visible", timeout=TIMEOUT)
    page.locator(".tree-report").filter(has=page.locator(":visible")).first.click()
    page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Basic page load
# ---------------------------------------------------------------------------

class TestPageLoad:

    def test_page_title_contains_rjk(self, page):
        assert "RJK" in page.title()

    def test_main_tabs_visible(self, page):
        # Top-level tabs are always visible
        for attr_val in ["tab-reports", "tab-audit", "tab-admin"]:
            assert page.locator(f'[data-tab="{attr_val}"]').is_visible(), f"Tab '{attr_val}' not visible"

    def test_sub_tabs_visible_after_report_selection(self, page):
        # Sub-tabs only appear after a report is selected (report-panel is hidden by default)
        _select_first_report(page)
        for attr_val in ["tab-raw-data", "tab-aggs", "tab-reporting"]:
            assert page.locator(f'[data-report-tab="{attr_val}"]').is_visible(), f"Sub-tab '{attr_val}' not visible"

    def test_sidebar_has_reports(self, page):
        # At least one folder or report should appear in the sidebar
        page.wait_for_selector(".tree-folder, .tree-report", timeout=TIMEOUT)
        count = page.locator(".tree-folder, .tree-report").count()
        assert count > 0, "Report tree is empty"

    def test_run_button_hidden_before_report_selected(self, page):
        # The param toolbar Run button should not be present until a report is selected
        run_btns = page.locator("#param-toolbar button.btn-rjk")
        assert run_btns.count() == 0 or not run_btns.first.is_visible()

    def test_export_button_disabled_before_run(self, page):
        _select_first_report(page)
        btn = page.locator("#btn-export-dropdown")
        assert btn.is_disabled(), "Export dropdown should be disabled before running a report"


# ---------------------------------------------------------------------------
# Report selection
# ---------------------------------------------------------------------------

class TestReportSelection:

    def test_selecting_report_shows_param_toolbar(self, page):
        _select_first_report(page)
        # A Run Report button should appear in the param toolbar
        page.wait_for_selector("#param-toolbar button.btn-rjk", timeout=TIMEOUT)
        assert page.locator("#param-toolbar button.btn-rjk").is_visible()

    def test_selecting_report_shows_panel(self, page):
        _select_first_report(page)
        # #report-panel is hidden by default and becomes visible after selection
        page.wait_for_selector("#report-panel:not([style*='display: none'])", timeout=TIMEOUT)
        assert page.locator("#report-panel").is_visible(), "Report panel should be visible after selection"

    def test_selecting_report_shows_run_button(self, page):
        _select_first_report(page)
        page.wait_for_selector("#param-toolbar button.btn-rjk", timeout=TIMEOUT)
        btn = page.locator("#param-toolbar button.btn-rjk")
        assert btn.is_visible()
        assert "Run" in btn.inner_text()


# ---------------------------------------------------------------------------
# Run report
# ---------------------------------------------------------------------------

class TestRunReport:

    def _run(self, page):
        _select_first_report(page)
        page.wait_for_selector("#param-toolbar button.btn-rjk", timeout=TIMEOUT)
        page.locator("#param-toolbar button.btn-rjk").click()
        # Wait for row-count-badge to appear (means run completed)
        page.wait_for_selector("#row-count-badge:not([style*='display: none'])", timeout=TIMEOUT)

    def test_run_shows_row_count_badge(self, page):
        self._run(page)
        badge = page.locator("#row-count-badge")
        assert badge.is_visible()
        text = badge.inner_text()
        assert text.strip() != "", "Row count badge should not be empty after run"

    def test_run_shows_grid_rows(self, page):
        self._run(page)
        # ag-Grid renders rows with role=row; wait for at least one data row
        page.wait_for_selector(".ag-row", timeout=TIMEOUT)
        row_count = page.locator(".ag-row").count()
        assert row_count > 0, "Grid should have at least one data row after run"

    def test_run_enables_export_dropdown(self, page):
        self._run(page)
        btn = page.locator("#btn-export-dropdown")
        assert not btn.is_disabled(), "Export dropdown should be enabled after successful run"

    def test_run_shows_scan_banner(self, page):
        self._run(page)
        # The scan banner should appear (clean or flagged)
        banner = page.locator("#scan-banner")
        assert banner.is_visible(), "Scan banner should be visible after run"

    def test_run_button_re_enables_after_run(self, page):
        self._run(page)
        btn = page.locator("#param-toolbar button.btn-rjk")
        assert not btn.is_disabled(), "Run button should be re-enabled after run completes"

    def test_row_count_badge_shows_number(self, page):
        self._run(page)
        badge_text = page.locator("#row-count-badge").inner_text()
        # Badge format is e.g. "672 rows" — should contain a digit
        assert any(c.isdigit() for c in badge_text), f"Badge '{badge_text}' should contain row count"


# ---------------------------------------------------------------------------
# Export dropdown
# ---------------------------------------------------------------------------

class TestExportDropdown:

    def _run_first(self, page):
        _select_first_report(page)
        page.wait_for_selector("#param-toolbar button.btn-rjk", timeout=TIMEOUT)
        page.locator("#param-toolbar button.btn-rjk").click()
        page.wait_for_selector("#row-count-badge:not([style*='display: none'])", timeout=TIMEOUT)

    def test_export_dropdown_opens(self, page):
        self._run_first(page)
        page.locator("#btn-export-dropdown").click()
        page.wait_for_selector(".dropdown-menu.show", timeout=TIMEOUT)
        assert page.locator(".dropdown-menu.show").is_visible()

    def _open_dropdown(self, page):
        page.locator("#btn-export-dropdown").click()
        page.wait_for_selector(".dropdown-menu.show", timeout=TIMEOUT)

    def test_export_dropdown_has_csv(self, page):
        self._run_first(page)
        self._open_dropdown(page)
        assert page.locator(".dropdown-menu.show a:has-text('CSV')").is_visible()

    def test_export_dropdown_has_excel(self, page):
        self._run_first(page)
        self._open_dropdown(page)
        assert page.locator(".dropdown-menu.show a:has-text('Excel')").is_visible()

    def test_export_dropdown_has_pdf(self, page):
        self._run_first(page)
        self._open_dropdown(page)
        assert page.locator(".dropdown-menu.show a:has-text('PDF')").is_visible()

    def test_export_dropdown_has_powerpoint(self, page):
        self._run_first(page)
        self._open_dropdown(page)
        assert page.locator(".dropdown-menu.show a:has-text('PowerPoint')").is_visible()

    def test_csv_download_triggered(self, page):
        self._run_first(page)
        with page.expect_download(timeout=TIMEOUT) as dl_info:
            self._open_dropdown(page)
            page.locator(".dropdown-menu.show a:has-text('CSV')").click()
        download = dl_info.value
        assert download.suggested_filename.endswith(".csv")

    def test_excel_download_triggered(self, page):
        self._run_first(page)
        with page.expect_download(timeout=TIMEOUT) as dl_info:
            self._open_dropdown(page)
            page.locator(".dropdown-menu.show a:has-text('Excel')").click()
        download = dl_info.value
        assert download.suggested_filename.endswith(".xlsx")


# ---------------------------------------------------------------------------
# Tab navigation
# ---------------------------------------------------------------------------

class TestTabNavigation:

    def test_aggs_tab_shows_controls(self, page):
        _select_first_report(page)  # sub-tabs only visible after report selection
        page.locator('[data-report-tab="tab-aggs"]').click()
        page.wait_for_selector("#tab-aggs", timeout=TIMEOUT)
        assert page.locator("#tab-aggs").is_visible()

    def test_reporting_tab_shows_dataset_panel(self, page):
        _select_first_report(page)  # sub-tabs only visible after report selection
        page.locator('[data-report-tab="tab-reporting"]').click()
        page.wait_for_selector("#tab-reporting", timeout=TIMEOUT)
        assert page.locator("#tab-reporting").is_visible()

    def test_reporting_tab_no_data_shows_message(self, page):
        _select_first_report(page)  # sub-tabs only visible after report selection
        page.locator('[data-report-tab="tab-reporting"]').click()
        page.wait_for_selector("#rpt-dataset-list", timeout=TIMEOUT)
        page.wait_for_timeout(600)
        list_text = page.locator("#rpt-dataset-list").inner_text()
        assert len(list_text.strip()) > 0, "Dataset list should show guidance when empty"

    def test_audit_tab_loads_grids(self, page):
        page.locator('[data-tab="tab-audit"]').click()
        page.wait_for_selector("#audit-runs-grid", timeout=TIMEOUT)
        assert page.locator("#audit-runs-grid").is_visible()

    def test_switching_back_to_raw_data_restores_grid(self, page):
        # Run a report, switch away, come back
        _select_first_report(page)
        page.locator("#param-toolbar button.btn-rjk").click()
        page.wait_for_selector("#row-count-badge:not([style*='display: none'])", timeout=TIMEOUT)

        page.locator('[data-report-tab="tab-aggs"]').click()
        page.wait_for_timeout(200)
        page.locator('[data-report-tab="tab-raw-data"]').click()
        page.wait_for_timeout(300)

        # Grid and badge should still be visible
        assert page.locator("#row-count-badge").is_visible()


# ---------------------------------------------------------------------------
# Grid search
# ---------------------------------------------------------------------------

class TestGridSearch:

    def test_search_filters_rows(self, page):
        _select_first_report(page)
        page.locator("#param-toolbar button.btn-rjk").click()
        page.wait_for_selector("#row-count-badge:not([style*='display: none'])", timeout=TIMEOUT)

        before = page.locator(".ag-row").count()
        page.locator("#grid-search").fill("Vanilla")
        page.wait_for_timeout(400)
        after = page.locator(".ag-row").count()

        # Filtered rows should be ≤ total rows
        assert after <= before, "Filtering should not increase visible row count"

    def test_clearing_search_restores_rows(self, page):
        _select_first_report(page)
        page.locator("#param-toolbar button.btn-rjk").click()
        page.wait_for_selector("#row-count-badge:not([style*='display: none'])", timeout=TIMEOUT)

        page.locator("#grid-search").fill("Vanilla")
        page.wait_for_timeout(400)
        filtered = page.locator(".ag-row").count()

        page.locator("#grid-search").fill("")
        page.wait_for_timeout(400)
        restored = page.locator(".ag-row").count()

        assert restored >= filtered, "Clearing search should restore rows"
