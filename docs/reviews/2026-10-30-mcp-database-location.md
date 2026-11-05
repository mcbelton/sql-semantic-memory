# Independent review: MCP database location

| | |
|---|---|
| Date | 2026-10-30 |
| Verdict | **approve** |
| Base | `7cef09c014a5a84ffc6050870ed5c2b652c3a528`, uncommitted working tree |
| Evidence | [Change evidence](../evidence/2026-10-30-mcp-database-location.md) |

## Scope

Reviewed every changed hunk and its surrounding context in `.vscode/mcp.json`, `README.md`, `CHANGELOG.md`,
`docs/status.md`, and the owner's pre-existing `.gitignore` addition `dbs/**`; read the new evidence record in
full. Also reviewed the current `D:\dev\.vscode\mcp.json` outside the repository; no historical diff for that
external file is available in this repository. There are no staged changes.

This review covers only selecting the copied `dbs\AdventureWorks2025.db` database and documenting that selection.
No runtime modules, requirements, generated catalog, knowledge graph, or retrieval implementation changed.
No rescan, rebuild, full-suite rerun, commit, or push was performed. The only file written by this review is
this record.

## Findings

| Severity | File:line | Issue | Proposed fix |
|---|---|---|---|
| — | — | No blocking, major, or minor findings in the bounded change. | None. |

## Checklist assessment

- **Correctness and actionable guidance:** Independently parsed both MCP configurations, expanded workspace
  paths, and confirmed both `--db` arguments resolve to the existing
  `D:\dev\sql-semantic-memory\dbs\AdventureWorks2025.db`. Both select the existing project KB and executable;
  neither contains an input prompt. README data commands consistently pass the new database, including
  `graph --check --db $db`. Placement and server-restart instructions are explicit.
- **SQL safety and privacy:** No SQL execution path, `check_readonly`, `run_select`, row cap, timeout, or input
  validation changed. The recorded smoke query is an aggregate count, not sensitive column values. No secrets
  or credentials were introduced. Independently confirmed `git check-ignore -v -- dbs/AdventureWorks2025.db`
  matches `.gitignore:16`, `git ls-files -- dbs` returns no files, and `git diff --check` passes.
- **Portability, typing, and errors:** The configuration is explicitly Windows-oriented; README documents
  changing the executable and database separators on Linux/macOS. No dialect, type, dependency, or runtime
  error-message change requires additional implementation review or cross-engine proof.
- **Requirements and tests:** This is a connection-path change, not new package behavior. Existing automated
  requirement coverage plus the recorded live configuration checks are appropriate; no new requirement IDs
  or tests are needed. The traceability artifact reports all 33 requirements proven.
- **Retrieval and knowledge:** No retrieval or knowledge facts changed. Keeping generated catalog scan
  provenance intact while passing `--db` explicitly is appropriate; relocating the connection alone does not
  require a rescan or graph rebuild.
- **Documentation and ADRs:** README, changelog, handoff, and evidence agree on the new location and prompt
  removal. No architecture decision, dependency, or gate changed, so no ADR is required.

## Evidence checked

Accepted the fresh verification bundle rather than rerunning the suite, as requested:

- [`build/evidence/summary.md`](../../build/evidence/summary.md) and
  [`summary.json`](../../build/evidence/summary.json): **PASS**, timestamp `2026-10-30T17:46:00-07:00`,
  base `7cef09c014a5` plus five uncommitted files. Both MCP configurations and the executable README/changelog
  changes predate this run; the subsequent status/evidence edits document its results.
- All seven gate rows in the durable [evidence record](../evidence/2026-10-30-mcp-database-location.md)
  independently compared equal to the summary: lint, format, mypy, pyright, tests, eval, and trace **PASS**.
- [`junit.xml`](../../build/evidence/junit.xml) confirms 101 collected, zero failures/errors, one SQL Server
  skip because `SQLMEM_MSSQL_ODBC` was unset.
  [`logs/tests.log`](../../build/evidence/logs/tests.log) confirms **100 passed, 1 skipped, 34 warnings** and
  **88% displayed coverage** (87.64% combined coverage; minimum 85%).
- [`eval-retrieval.json`](../../build/evidence/eval-retrieval.json) confirms BM25 **24/24**, mean recall **1.00**;
  [`traceability.md`](../../build/evidence/traceability.md) confirms SQLite and DuckDB passed.
- The change evidence records fresh MCP SDK initialization, tool listing (**12 tools**), and
  `run_sql SELECT COUNT(*) AS customer_count FROM Sales__Customer` returning **19820** from both configured
  servers, plus the same direct CLI result. These live results are recorded author evidence, not a second
  protocol run by this reviewer; configuration resolution and ignore checks were independently repeated.

## Limits and disposition

The active VS Code server still needs restarting. The external parent configuration is not versioned here.
CI, PostgreSQL, MariaDB, and SQL Server were not run for this change; the SQL Server skip and SQLite resource
warnings are disclosed. These limitations do not block this configuration-only change.

**Approved within the stated scope; no requested changes.**
