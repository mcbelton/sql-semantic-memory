# Evidence: repository baseline (sqlmem 0.2.0)

| | |
|---|---|
| Date | 2026-10-30 |
| Commit | `b990f0534c2327ed20481d4deb429837715d5c60` (clean working tree; this record is committed on top of it) |
| Requirements | all: REQ-SCAN-01..04, REQ-SEM-01..04, REQ-RET-01..05, REQ-MEM-01..02, REQ-SAFE-01..03, REQ-LLM-01..03, REQ-KG-01..10, REQ-MCP-01, REQ-CLI-01; QA-* |
| Review | [docs/reviews/2026-10-30-repository-hardening.md](../reviews/2026-10-30-repository-hardening.md) |
| CI run | not run yet (first push pending); CI uploads the same bundle as the `evidence-*` artifacts |

## Change

First commit of the repository: the typed `sqlmem` package (mypy `--strict`, pyright), requirement traceability,
`scripts/verify.py`, the retrieval evaluation with gates, CI for Python 3.10–3.13 on Linux, Windows and macOS plus a
cross-engine job, the Copilot agent team (agents, skills, prompts, instructions, hook) and the architecture, design,
testing and process documentation. Two behavior changes: value-matched tables no longer displace retrieved tables
([ADR 0009](../design/adr/0009-value-matches-do-not-displace-retrieved-tables.md)), and the knowledge-graph
verification budget is measured with `time.perf_counter()` (review finding 7).

## Verification

Command: `python scripts/verify.py --require-engines` on Windows 11 ARM64, Python 3.13.15, with
`scripts/engines.ps1` servers running.

| Gate | Verdict | Time | Summary |
|---|---|---|---|
| lint | PASS | 0.3s | All checks passed! |
| format | PASS | 0.3s | 94 files already formatted |
| mypy | PASS | 1.5s | Success: no issues found in 31 source files |
| pyright | PASS | 19.9s | 0 errors, 0 warnings, 0 informations |
| tests | PASS | 52.9s | 104 passed, 30 warnings in 41.30s; coverage 90% (min 85%) |
| eval | PASS | 2.2s | Retrieval eval [none]: full 24/24, mean recall 1.00, avg tables 4.9, concepts shown 24, 0.1s; Gate: full >= 24, mean recall >= 1.0 -> PASS |
| trace | PASS | 0.0s | 33/33 requirements proven by passing tests; engines: duckdb=passed, mssql=passed, mssql-integration=passed, mysql=passed, postgresql=passed, sqlite=passed |

The 30 warnings are `ResourceWarning`s for SQLite connections that are garbage-collected while coverage is active
(the CLI opens a knowledge base per command); they don't appear without coverage and don't affect results.

### Requirements

All 33 `REQ-*` rows are *proven* (at least one passing test, none failing); e.g. REQ-SAFE-01 by 33 tests,
REQ-KG-06 by 3, REQ-RET-05 by the BM25 eval gate. QA-LINT, QA-TYPES, QA-TESTS, QA-COVERAGE, QA-ENGINES and QA-TRACE
are proven by the gates above (QA-LINT also by 13 hook tests, QA-TRACE by 3 traceability tests). Full matrix:
`build/evidence/traceability.md` of the run.

### Retrieval evaluation (24 AdventureWorks questions)

| Embedder | Before ADR 0009 | After | Without knowledge graph (after) |
|---|---|---|---|
| none (BM25), CI gate | full 23/24, recall 0.99, 4.67 tables | **full 24/24, recall 1.00, 4.88 tables** | full 23/24, recall 0.98, 4.21 tables |
| fastembed `BAAI/bge-small-en-v1.5` (`--embedder kb`) | full 23/24, recall 0.99, 4.38 tables | **full 24/24, recall 1.00, 4.50 tables** | full 22/24, recall 0.95, 3.96 tables |
| hash:256 (test embedder) | full 23/24, recall 0.99 | full 23/24, recall 0.99 | full 21/24, recall 0.94 |

The knowledge graph adds 1 (BM25) to 2 (fastembed) fully answered questions; the remaining misses without it are the
business-term questions about store contacts and ship-to addresses.

### Cross-engine

| Engine | Version | Scenario (`test_end_to_end_on_engine`) | Other |
|---|---|---|---|
| SQLite | 3.50.4 | passed | |
| DuckDB | 2.0.0 (duckdb-engine) | passed | |
| PostgreSQL | 18.6 (portable, `scripts/engines.ps1`) | passed | |
| MariaDB | 11.4.5 (portable, MySQL dialect) | passed | |
| SQL Server | 17.0.4025.3 Express (LocalDB, SQL Server 2025) | passed | `test_mssql_scan_model_and_query` passed |

### Other environments (same tree, before the final amend that only typed `SEMANTIC` in `tests/conftest.py`)

| Environment | Result |
|---|---|
| Python 3.10.21 (AMD64, SQLAlchemy 2.0.55, numpy 2.2.6) — oldest CI version | 100 passed, 1 skipped (SQL Server not configured); coverage 87.12% |
| Python 3.13 x64 with the CI quality-job extras (`mcp,llm,duckdb,dev`, no `fastembed`/`pyodbc`) | 100 passed, 1 skipped; coverage 87.64%; pyright 0 errors |
| `test_verification_budget_saves_items_unverified` on Python 3.10 | before the perf_counter fix 1/12 runs passed; after 20/20 |
| VS Code Problems panel (repository and `D:\dev` workspace) | no errors; Pylance interpreter = `sql-semantic-memory/.venv` |
| Agent hook end to end (stdin payloads) | read payload: file unchanged; edit payload: fixed + formatted, `F821` returned as `additionalContext` |

## Gaps and risks

- CI has not run yet: Linux and macOS results, the Docker-based engine job (`compose.yaml`, SQL Server 2022 container,
  ODBC Driver 18) and Python 3.11/3.12 are verified only by the first CI run after the push.
- The Python 3.10 run used an x64 interpreter under emulation on ARM64 Windows, not Linux.
- `scripts/engines.ps1` was verified on this machine only (start, env, status, PID ownership check against the running
  servers and a foreign PID, and `stop` after the evidence run: both servers and LocalDB stopped, state file removed).
- Hook execution inside a live Copilot session (VS Code, CLI, cloud agent) is not verified; the payload contract was
  taken from the GitHub hooks reference and tested with synthetic payloads.
- The AdventureWorks database itself is not in the repository; data-dependent commands on the example KB need it.
