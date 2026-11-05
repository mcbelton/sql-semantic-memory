# Evidence: MCP database location

| | |
|---|---|
| Date | 2026-10-30 |
| Commit | Uncommitted working tree based on `7cef09c014a5a84ffc6050870ed5c2b652c3a528` |
| Requirements | No package behavior or requirement IDs changed; existing 33 requirements remain proven |
| Review | [MCP database location review](../reviews/2026-10-30-mcp-database-location.md) |
| CI run | Not run for this change |

## Change

The database was copied into the project's local `dbs` folder. Both the project and parent workspace MCP
configurations now select that file. The project configuration uses a workspace-relative argument instead of an
input prompt, avoiding cached selections of the old location. README commands explicitly select the new file,
including graph verification, rather than relying on the generated catalog's original scan path.
The owner's existing `dbs/**` ignore rule is preserved; no database or generated catalog was changed.

## Verification

Command: `.\.venv\Scripts\python.exe scripts\verify.py`

Copied from `build/evidence/summary.md` (2026-10-30T17:46:00-07:00, base `7cef09c014a5` plus five uncommitted files):

| Gate | Verdict | Time | Summary |
|---|---|---|---|
| lint | PASS | 1.2s | All checks passed! |
| format | PASS | 0.3s | 96 files already formatted |
| mypy | PASS | 1.6s | Success: no issues found in 31 source files |
| pyright | PASS | 30.9s | 0 errors, 0 warnings, 0 informations |
| tests | PASS | 47.4s | 100 passed, 1 skipped, 34 warnings in 40.52s; coverage 88% (min 85%) |
| eval | PASS | 3.8s | Retrieval eval [none]: full 24/24, mean recall 1.00, avg tables 4.9, concepts shown 24, 0.2s; Gate: full >= 24, mean recall >= 1.0 -> PASS |
| trace | PASS | 0.0s | 33/33 requirements proven by passing tests; engines: duckdb=passed, sqlite=passed |

### MCP and database checks

For each configuration, a temporary MCP SDK stdio client initialized the configured server, listed its tools,
and called `run_sql` with `SELECT COUNT(*) AS customer_count FROM Sales__Customer`. Before launch, the resolved
`--db` argument was checked against the existing `D:\dev\sql-semantic-memory\dbs\AdventureWorks2025.db` file.
Both returned these checked results, and the temporary client/server processes exited:

```text
PASS D:\dev: database=D:\dev\sql-semantic-memory\dbs\AdventureWorks2025.db; tools=12; customer_count=19820
PASS D:\dev\sql-semantic-memory: database=D:\dev\sql-semantic-memory\dbs\AdventureWorks2025.db; tools=12; customer_count=19820
```

Reproducible database check:

```powershell
.\.venv\Scripts\sqlmem.exe query --db dbs\AdventureWorks2025.db 'SELECT COUNT(*) AS customer_count FROM Sales__Customer'
# customer_count = 19820 (1 row)
git check-ignore -- dbs\AdventureWorks2025.db
# "dbs\\AdventureWorks2025.db"
git ls-files -- dbs
# no tracked files
git diff --check
# exit 0
```

## Gaps and risks

- VS Code's existing server still needs restarting; protocol checks used fresh temporary server processes,
  not the active VS Code connection.
- The parent workspace configuration is outside this repository and is not included in its Git history.
- The generated catalog retains the original scan path. Data checks should pass the new `--db` explicitly;
  regenerating scan facts solely to relocate this local file was deliberately avoided.
- PostgreSQL, MariaDB and SQL Server were not configured for this run. The SQL Server integration test was skipped
  because `SQLMEM_MSSQL_ODBC` was unset; the test gate reported 34 warnings, including SQLite `ResourceWarning`s.
- No SQL, dialect, retrieval, knowledge-graph or package source code changed. No additional cross-engine run,
  fastembed comparison or new requirement tests were needed for this configuration-only change.
