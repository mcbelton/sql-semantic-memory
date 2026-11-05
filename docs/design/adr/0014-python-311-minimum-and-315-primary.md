# 0014. Require Python 3.11 and use Python 3.15 as the primary version

- Status: Proposed
- Date: 2026-11-05
- Requirements: QA-TESTS, QA-TYPES, REQ-AMEM-01, REQ-AMEM-09, REQ-CHART-01

## Context

The first public CI run failed only on Python 3.10, which reached end of life in October 2026:
`datetime.fromisoformat()` rejected a valid fractional ISO timestamp (REQ-CHART-01), and SQLite
exceptions had no `sqlite_errorcode`, so a recoverable projection failure surfaced as `store_failed`
(REQ-AMEM-01/09). The [publication evidence](../../evidence/2026-11-05-github-publication.md) records the run.
Python 3.15.2 is the latest stable release on python.org. The owner chose to support 3.11 through 3.15.

## Options

1. **Keep Python 3.10 and add compatibility code:** widest support, but custom ISO parsing and SQLite error
   classification for an end-of-life runtime add risk and maintenance.
2. **Require Python 3.11 and test 3.11-3.15:** uses standard-library behavior that works across the supported range;
   drops only an end-of-life runtime.
3. **Require Python 3.15 only:** simplest matrix and newest features, but excludes supported runtimes with no
   project need.

## Decision

We require Python 3.11 or later and test every supported minor version: 3.11-3.14 on Ubuntu and the
latest stable 3.15 on Ubuntu quality gates, Windows and macOS. Copilot setup uses 3.15. The cross-engine job uses
3.14 while `pyodbc` has no 3.15 wheel. Ruff, mypy and pyright target 3.11, so code cannot rely on features newer
than the floor.

## Consequences

- The Python 3.10-only failures are removed without new parsing or error-code compatibility layers.
- SQLite result-code handling uses named `sqlite3` constants available from 3.11.
- Python 3.10 users must upgrade. Adding a future Python release requires its own CI validation.
- On Python 3.15, optional `local` (fastembed via onnxruntime) and `mssql` (pyodbc) cannot install from wheels
  until upstream publishes them. Use Python 3.11-3.14 for those features; move the engine job when wheels exist.
- Features introduced after 3.11 remain forbidden in package code until the floor is raised again.

## Verification

- Python 3.11: full `scripts/verify.py` gates.
- Python 3.15: full test suite with `DeprecationWarning` visible and full `scripts/verify.py` gates.
- Python 3.10: both CI failures reproduce locally before the floor change.
- CI runs the configured 3.11-3.15 matrix and the cross-engine job on Python 3.14.
- `pip download --only-binary=:all:` confirms onnxruntime/pyodbc wheels for 3.14 and none for 3.15.
