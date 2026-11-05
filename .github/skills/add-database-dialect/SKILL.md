---
name: add-database-dialect
description: 'Add or harden support for a SQL engine in sqlmem (Oracle, Snowflake, Databricks, BigQuery, Trino, ClickHouse, Db2 or a new driver): SQLAlchemy dialect, INFORMATION_SCHEMA fallback in scan, read-only session, per-query time limit, guard rules, cross-engine test target, docs. Use when a scan, query or time limit fails on a specific database.'
argument-hint: 'Database engine and SQLAlchemy URL scheme'
---

# Add a database dialect

sqlmem talks to databases only through SQLAlchemy (see ADR 0002). Supporting an engine means proving the five
contracts below on that engine, not adding a code path per engine.

## Contracts to prove
1. **Reflection** (`sqlmem/scan.py`): tables, views, columns, keys, indexes and comments are found. When the
   driver's reflection is missing or broken, the `INFORMATION_SCHEMA` fallback fills them (reported as `NOTE`).
2. **Profiling** (`scan.py`): row counts, null %, ranges and value dictionaries use portable SQL with sampling.
3. **Read-only** (`sqlmem/db.py`): `make_engine` opens a read-only session where the engine supports one; the guard
   `check_readonly(sql, dialect)` rejects engine-specific write or side-effect syntax.
4. **Time limits** (`db.time_limit`): a per-query timeout that cancels the statement and leaves the connection
   usable.
5. **Quoting**: identifiers rendered with the dialect's preparer (`Table.sql_name`).

## Procedure
1. Install the dialect as an optional extra in `pyproject.toml` (lazy import, ADR if it is a new dependency).
2. Run `sqlmem scan --kb kb/tmp --db <url>` on a sample database; read every `NOTE`/`ERROR` line.
3. Add the engine to `tests/test_dialects.py`: a `HEAVY` query that runs for minutes (for the time-limit test),
   scratch schema create/drop in `scratch()`, and any expected differences.
4. Run the scenario: `SQLMEM_TEST_URLS="<url>" python -m pytest tests/test_dialects.py -v` until it passes.
5. Implement the missing contract pieces in `db.py` / `scan.py` with small, tested dialect branches.
6. Update the "Supported databases" table in `README.md` (Tested vs. same code path), `docs/requirements.md`
   (REQ-SCAN-04 text) and, for CI coverage, `compose.yaml` plus the `engines` job.
7. Run `python scripts/verify.py --require-engines` and record evidence.
