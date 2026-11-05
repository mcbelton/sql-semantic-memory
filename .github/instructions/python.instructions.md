---
description: "Use when writing or changing Python code in sqlmem: typing, errors, SQL safety, dialect-neutral SQL, performance and dependencies."
applyTo: "**/*.py"
---
# Python code in sqlmem

- Target Python 3.11+ (tested on 3.11–3.15). Every function in `sqlmem/` is fully annotated and passes
  `mypy --strict` and pyright (`standard`) with zero findings. Prefer precise types (`dict[str, Any]` at JSON/YAML
  boundaries only) and narrow `Optional` values explicitly instead of `# type: ignore` (an unnecessary ignore is an
  error).
- Ruff decides formatting and import order (`ruff format`, line length 120). Don't hand-format.
- **SQL safety**: run every SQL text that comes from users, LLMs or YAML through `db.check_readonly(sql, dialect)`
  and execute it with `db.run_select` (row cap, rollback, time limit). Never build SQL by concatenating values; quote
  identifiers with the dialect's preparer (`Table.sql_name`, `Column.sql_name`).
- **Dialect-neutral**: code must work on SQLite, DuckDB, PostgreSQL, MySQL/MariaDB and SQL Server. Use SQLAlchemy
  reflection with the `INFORMATION_SCHEMA` fallback in `scan.py`; keep dialect branches small and covered by
  `tests/test_dialects.py`.
- **Privacy**: never persist values of columns flagged `sensitive`; secrets come from the environment, never from
  `sqlmem.json` or code.
- **Errors**: raise `ValueError`/`PlanError` with a message that tells the user or the LLM how to fix the input
  (e.g. "Did you mean ...", "give the target's key, or write the join with on"). MCP tools turn them into `ToolError`.
- **Output**: the CLI prints; library code returns values and logs progress through the `log` callback.
- **Performance**: don't load all rows; profile with `LIMIT`/sampling as `scan.py` does. Bound loops that call the
  database by the verification budget (`kgraph._Checker`).
- **Dependencies**: optional features use extras in `pyproject.toml` and import lazily inside the function.
  A new runtime dependency needs an ADR.
- Keep comments for non-obvious *why*; names and types should explain the *what*.
