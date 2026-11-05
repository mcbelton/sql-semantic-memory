---
name: cross-engine-testing
description: 'Run the sqlmem cross-engine tests on SQLite, DuckDB, PostgreSQL 18, MariaDB 11.4 and SQL Server: start servers with scripts/engines.ps1 (Windows, no Docker) or compose.yaml (Docker), set SQLMEM_TEST_URLS and SQLMEM_MSSQL_ODBC, run verify.py --require-engines, troubleshoot ports, ODBC drivers and LocalDB. Use for SQL, dialect, scan, read-only guard or time-limit changes.'
argument-hint: 'Optional: engines to include'
---

# Cross-engine testing

`tests/test_dialects.py::test_end_to_end_on_engine` runs the same scenario (mixed-case and reserved names, several
schemas, declared and inferred joins, knowledge-graph verification, read-only enforcement, time limits) on every
URL in `SQLMEM_TEST_URLS`; `tests/test_mssql.py` adds SQL Server specifics through `SQLMEM_MSSQL_ODBC`.

## Procedure (Windows, no admin, no Docker)
1. `.\scripts\engines.ps1 start` - downloads PostgreSQL and MariaDB once to `%LOCALAPPDATA%\sqlmem-engines`,
   starts them on 127.0.0.1:54329 and :33069, starts SQL Server LocalDB, and prints the settings.
2. `.\scripts\engines.ps1 env | Invoke-Expression` - sets `SQLMEM_TEST_URLS` and `SQLMEM_MSSQL_ODBC` in this shell.
3. `python scripts/verify.py --require-engines` - the `trace` gate fails unless the cross-engine scenario passed
   on all five engines (`tests/test_mssql.py` is reported separately as `mssql-integration`).
4. `.\scripts\engines.ps1 stop` when done.

## Procedure (Docker: Linux, macOS, Windows)
1. `export MSSQL_SA_PASSWORD="$(openssl rand -hex 12)Aa1"` then `docker compose up -d --wait`.
2. Export `SQLMEM_TEST_URLS` (all three server URLs, SQL Server included) and `SQLMEM_MSSQL_ODBC` exactly as
   shown at the top of `compose.yaml`; CI builds the same values in the `engines` job of `.github/workflows/ci.yml`.
3. `python scripts/verify.py --require-engines`, then `docker compose down -v`.

## Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| `Data source name not found` | no Microsoft ODBC driver | install "ODBC Driver 18 for SQL Server" (17 also works) |
| PostgreSQL/MariaDB port already in use | an earlier run still active | `.\scripts\engines.ps1 status`, then `stop` |
| `sqllocaldb.exe not found` | LocalDB not installed | install SQL Server Express LocalDB, or test SQL Server with Docker |
| test id missing in the `trace` line | URL not in `SQLMEM_TEST_URLS` | re-run step 2 in the same shell |
| scratch schema left behind after a crash | test killed mid-run | drop schemas named `sqlmem_t_*` |

## Evidence
Report the `trace` gate line (it lists every engine with its outcome) and the engine versions in the evidence
record.
