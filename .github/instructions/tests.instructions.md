---
description: "Use when writing or changing tests: requirement markers, fixtures, determinism, cross-engine tests, assertions and evidence."
applyTo: "tests/**"
---
# Tests

- Every test carries `@pytest.mark.req("REQ-...")` with the IDs it proves (see `docs/requirements.md`). Add the
  requirement row first if it doesn't exist; an unknown ID stops the run.
- Bug fixes start with a test that fails for the reported reason (keep the failing output for the evidence record).
- Use the shared fixtures in `tests/conftest.py`: `db_path`/`engine` (the shop SQLite DB), `catalog`, `kb`
  (built with the deterministic `hash:256` embedder). Never depend on network access, real LLMs or model downloads;
  LLM tests use the local stub server in `tests/test_llm.py`.
- Assert behavior, not implementation details: check the user-visible text (context pack, error message, YAML) or
  the returned data. `pytest.raises` always has `match=` (escape literals with `re.escape`).
- MCP tool results: read them with `tool_text(result)` from `tests/conftest.py`.
- Cross-engine behavior goes into `tests/test_dialects.py::test_end_to_end_on_engine` so it runs on every engine in
  `SQLMEM_TEST_URLS`; SQL Server specifics into `tests/test_mssql.py`.
- Clean up what you open: dispose engines and close knowledge bases (`kb.close()`) in fixtures you add.
- Keep tests fast (the whole suite runs in well under a minute without external engines).
