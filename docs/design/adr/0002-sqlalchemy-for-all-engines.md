# 0002. Talk to every database through SQLAlchemy

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-SCAN-01, REQ-SCAN-04, QA-ENGINES

## Context

Users point sqlmem at SQLite files, DuckDB, PostgreSQL, MySQL/MariaDB, SQL Server and cloud warehouses. Writing and
maintaining one metadata reader per engine does not scale; drivers' reflection support also varies (DuckDB's
dialect lacks index reflection, some drivers miss comments or keys).

## Options

1. **Native catalogs per engine** (`pg_catalog`, `sys.*`, ...): complete but N implementations to test.
2. **SQLAlchemy reflection only**: one code path, but gaps where a dialect is incomplete.
3. **SQLAlchemy reflection with a standard `INFORMATION_SCHEMA` fallback**, plus small dialect branches only for
   read-only sessions and time limits.

## Decision

We use option 3. Scanning, profiling and querying go through SQLAlchemy Core; when reflection is missing or fails,
`scan.py` reads columns and keys from `INFORMATION_SCHEMA` and reports a `NOTE`. Dialect-specific code is limited to
`db.py` (read-only session, time limit) and the guard's quoting rules.

## Consequences

- New engines usually work by installing their SQLAlchemy dialect (README "Supported databases").
- Third-party dialects can lag SQLAlchemy releases (pin `SQLAlchemy<2.1` when needed).
- Every dialect branch must be covered by the cross-engine scenario.

## Verification

`tests/test_dialects.py::test_end_to_end_on_engine` on SQLite, DuckDB, PostgreSQL 18, MariaDB 11.4 and SQL Server
(CI `engines` job; locally `scripts/engines.ps1`), and `tests/test_mssql.py`. QA-ENGINES in the traceability matrix.
