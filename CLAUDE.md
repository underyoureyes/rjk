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
│   └── consumer/cards/cabm/model_results/
│       ├── agg_gcl_factors.sql
│       ├── vmx_gcl_rates_model.sql
│       └── vmx_gcl_rates_ratio.sql
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
  run_date:
    type: date
    label: "Run Date"
    default: "today"
  segment:
    type: select
    label: "Segment"
    options: [ALL, PRIME, NEAR_PRIME]
    default: ALL
mock:
  dimensions:
    SEGMENT: [PRIME, NEAR_PRIME, SUB_PRIME]
    RISK_BAND: [BAND_1, BAND_2]
  numerics:
    SCORE: {min: 0.0, max: 1.0, decimals: 4}
    N: {min: 100, max: 10000, decimals: 0}
*/

SELECT ... FROM ... WHERE run_date = :run_date
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

Three seed reports under `reports/consumer/cards/cabm/model_results/`:

| File | Rows | Key dimensions |
|---|---|---|
| `agg_gcl_factors.sql` | 27,000 | SEGMENT(3)×RISK_BAND(5)×FACTOR_NAME(10)×PRODUCT_TYPE(5)×ACCOUNT_AGE_BAND(6)×CHANNEL(6) |
| `vmx_gcl_rates_model.sql` | 10,800 | MODEL_VERSION(3)×SEGMENT(3)×SCORE_BAND(10)×PRODUCT_TYPE(5)×CHANNEL(6)×RUN_DATE(4) |
| `vmx_gcl_rates_ratio.sql` | 18,900 | RATIO_TYPE(7)×SEGMENT(3)×PRODUCT_TYPE(6)×REGION(6)×AS_OF_DATE(25 monthly) |

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
