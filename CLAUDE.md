# RJK Report Framework — Claude Code Project

## What this project does

A FastAPI + ag-Grid SQL reporting framework. Authors write SQL reports with embedded YAML metadata (title, description, params, mock data); the framework discovers them automatically, renders a parameter toolbar in the browser, runs the SQL (or generates mock data), and displays results in ag-Grid with CSV/Excel export and sign-off workflow.

**Live at:** `http://localhost:8000` (run `python launch.py`)

---

## Tech stack

- **FastAPI** — REST API + HTML serving
- **ag-Grid 32** — results grid
- **Bootstrap 5.3.3** — UI framework (dark blue #003087 navbar, matching ii-scraper style)
- **SQLite** — audit log (`data/audit.db`)
- **PyYAML** — parses metadata from SQL comments
- **openpyxl** — Excel export
- **pyodbc** — (optional) real DB connections when `MOCK_MODE=false`

---

## Project structure

```
rjk/
├── app.py                      ← FastAPI entry point
├── launch.py                   ← starts uvicorn + opens browser
├── requirements.txt
├── pytest.ini
├── .env.example
├── reports/                    ← SQL report files
│   ├── frosty_treats/sales/
│   │   └── daily_product_sales.sql
│   └── stock_market/prices/
│       └── daily_close_prices.sql
├── src/RJK/
│   ├── config/loader.py        ← Config dataclass, env vars
│   ├── parser/sql_metadata_parser.py  ← extracts YAML from /* ... */
│   ├── discovery/report_discovery.py  ← walks reports/, builds tree
│   ├── runners/
│   │   ├── base.py             ← abstract BaseRunner
│   │   ├── mock_runner.py      ← cartesian-product mock data
│   │   └── odbc_runner.py      ← real DB via pyodbc
│   ├── audit/audit_service.py  ← SQLite audit log + sign-offs
│   ├── services/
│   │   ├── report_service.py   ← orchestrates run + audit
│   │   └── export_service.py   ← CSV + Excel export
│   └── ui/layout.py            ← serves index.html
├── templates/index.html        ← single-file SPA
├── data/                       ← audit.db lives here (gitignored)
└── tests/
    ├── test_metadata_parser.py
    ├── test_report_discovery.py
    ├── test_mock_runner.py
    ├── test_audit_service.py
    ├── test_export_service.py
    └── test_app.py             ← full integration tests
```

---

## SQL report format

Each `.sql` file starts with a `/* ... */` YAML metadata block:

```sql
/*
title: "My Report"
description: "What this report shows"
owner: "Team Name"
tags: [tag1, tag2]
params:
  sales_date:
    type: date
    label: "Sales Date"
    default: "today"
  region:
    type: select
    label: "Region"
    options: [ALL, North, South, East]
    default: ALL
mock:
  dimensions:
    FLAVOUR: [Vanilla, Chocolate, Strawberry]
    REGION: [North, South]
    SALES_DATE:
      - "today-6"
      - "today"
  derived:
    MONTH:
      month_start_of: SALES_DATE
  numerics:
    UNITS_SOLD: {min: 10, max: 500, decimals: 0}
    REVENUE: {min: 5.00, max: 250.00, decimals: 2}
*/

SELECT ... FROM ... WHERE sales_date <= :sales_date
```

The `mock` block defines the cartesian-product dimensions and random numeric columns used when `MOCK_MODE=true`.

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Serve SPA |
| GET | `/api/reports` | Discover all reports + tree |
| GET | `/api/reports/meta?path=` | Metadata for one report |
| POST | `/api/reports/run` | Run report, return JSON rows |
| POST | `/api/reports/export/csv` | Run + download CSV |
| POST | `/api/reports/export/excel` | Run + download Excel |
| GET | `/api/audit` | Audit log (runs + sign-offs) |
| POST | `/api/signoff` | Record a sign-off |

---

## Environment variables

Copy `.env.example` to `.env`:

```bash
MOCK_MODE=true              # false = use real DB via pyodbc
DB_CONN_STRING=             # pyodbc connection string
REPORTS_ROOT=reports        # path to SQL reports directory
AUDIT_DB_PATH=data/audit.db # SQLite audit file
```

---

## Running locally

```bash
pip install -r requirements.txt
python launch.py            # starts server + opens browser
# or
uvicorn app:app --reload
```

## Running tests

```bash
pytest --tb=short
```

Tests run from the project root and use the real seed SQL files plus tmp_path for the audit DB.

---

## Seed reports

Two seed reports:

| File | Rows | Key dimensions |
|---|---|---|
| `frosty_treats/sales/daily_product_sales.sql` | 672 | FLAVOUR(8)×REGION(6)×SALES_DATE(14 rolling days) |
| `stock_market/prices/daily_close_prices.sql` | ~3,650 | TICKER(7)×CLOSE_DATE(~522 weekdays, last 2 years) |

---

## Style guide

Matches `underyoureyes/ii-scraper` look and feel:
- Bootstrap 5.3.3 + Bootstrap Icons 1.11.3
- ag-Grid Community 32.3.3
- Dark blue navbar `#003087`
- Dark terminal log console (`#0d1117` background)
- Grid toolbar with row count badge

---

## Working style

Ask before implementing any ambiguous change. Batch questions into one message. See `docs/conventions.md` in ii-scraper for Python coding standards.
