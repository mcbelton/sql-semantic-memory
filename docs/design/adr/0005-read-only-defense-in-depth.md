# 0005. Read-only access in depth

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-SAFE-01, REQ-SAFE-02, REQ-SAFE-03, REQ-SCAN-02

## Context

SQL reaches the database from three untrusted sources: AI agents (`run_sql`), LLM proposals (knowledge-graph
filters and joins) and YAML edited by people. sqlmem must never change data, must not hang the agent, and must not
leak personal data into its files.

## Options

1. **Trust the login**: require a read-only database account and nothing else.
2. **Guard only**: parse/inspect SQL and reject anything that is not a plain query.
3. **Defense in depth**: guard + read-only sessions where the engine supports them + rollback after every query +
   per-query time limits + recommendation of a read-only login.

## Decision

We use option 3. `check_readonly` accepts exactly one comment-free `SELECT`/`WITH` statement without write or
side-effect keywords and rejects quoting tricks that engines parse differently. `make_engine` opens SQLite and
DuckDB read-only and sets PostgreSQL, MySQL and MariaDB sessions read-only. `run_select` caps rows, rolls back and
runs inside `time_limit`. Sensitive columns are profiled without storing values.

## Consequences

- Some legitimate SQL is rejected (comments, multiple statements); agents get an actionable error message.
- SQL Server, Oracle and warehouses have no read-only session mode: a read-only login stays recommended.

## Verification

Parametrized allow/block tests (`test_readonly_guard_*`), `test_run_select_is_read_only_and_capped`, the cross-engine
write attempt (`UPDATE` must fail with a read-only error on SQLite, DuckDB, PostgreSQL, MariaDB), time-limit tests on
every engine, and `test_scan_never_captures_sensitive_values`. See the [security design](../security.md).
