# Testing strategy

## Levels

| Level | Where | What it proves | Runs |
|---|---|---|---|
| Unit / component | `tests/test_sqlmem.py`, `test_kgraph*.py`, `test_llm.py` | scan, model, retrieval, memory, guard, knowledge graph, LLM client behavior on a small shop database | every `pytest` run (< 1 min) |
| Interface | MCP tests (`test_mcp_*`), CLI tests (`test_cli_*`) | tools and commands end to end, error messages | every run |
| Cross-engine | `tests/test_dialects.py`, `tests/test_mssql.py` | the same scenario on SQLite, DuckDB, PostgreSQL, MariaDB, SQL Server | SQLite + DuckDB always; others with `SQLMEM_TEST_URLS` / `SQLMEM_MSSQL_ODBC` (CI `engines` job) |
| Evaluation | `evals/run_retrieval.py`, `tests/test_eval_gate.py` | retrieval quality on 24 AdventureWorks questions | BM25 gate every run; fastembed locally |
| Tooling | `tests/test_verify.py`, `tests/test_hooks.py` | traceability rules of `verify.py`; the agent formatting hook | every run |
| Static | ruff, mypy (strict), pyright | style, bugs, types | `scripts/verify.py`, CI |

## Rules

- **Traceability**: each test is marked `@pytest.mark.req(...)` with the requirement IDs it proves
  ([requirements](../requirements.md)). `scripts/verify.py` fails when a requirement has no passing test.
- **Determinism**: tests use the `hash:256` embedder, a seeded generated database (`tests/conftest.py::_make_db`),
  and a local stub server instead of real LLMs. No network access.
- **Red/green for bugs**: a fix comes with a test that failed before it.
- **Negative tests for safety**: every guard rule has a blocked example; every engine must reject a write.
- **Behavior over implementation**: assert what users and agents see (context text, reports, YAML, errors).

## Fixtures

| Fixture | Scope | Provides |
|---|---|---|
| `db_path` | session | generated SQLite shop database (customers, products, orders, order items, sales reps, a view) |
| `engine` | session | read-only engine on it (disposed at the end) |
| `catalog` | session | `scan_database` result |
| `kb` | test | built knowledge base in a temp folder with `SEMANTIC` overlay (closed after the test) |
| `shop` | test (`test_kgraph_advanced.py`) | database with composite keys and polymorphic references |

## Coverage

Line + branch coverage of `sqlmem/` is measured by `scripts/verify.py` (minimum 85%, `COVERAGE_MIN`). Uncovered
code is mostly engine-specific branches exercised only by the cross-engine job (SQL Server timeouts, MySQL session
settings) and CLI error paths.

## Running

```powershell
python -m pytest -q                                   # everything available locally
python -m pytest tests/test_kgraph_advanced.py -q    # one area
python scripts/verify.py                              # all gates + evidence
.\scripts\engines.ps1 start; .\scripts\engines.ps1 env | Invoke-Expression
python scripts/verify.py --require-engines            # all five engines must pass
```
