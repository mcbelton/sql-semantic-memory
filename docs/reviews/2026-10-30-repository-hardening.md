# Review: repository hardening (typing, gates, traceability, retrieval fix, agent setup)

| | |
|---|---|
| Date | 2026-10-30 |
| Reviewer | independent `code-review` agent (fresh context), checklist [checklist.md](checklist.md) |
| Scope | the whole tree before the initial commit: `sqlmem/` typing edits and `select_tables`, `KnowledgeBase.close`, `tests/conftest.py` plugin, `evals/`, `scripts/verify.py`, `scripts/hooks/`, `scripts/engines.ps1`, `compose.yaml`, `.github/workflows/`, `pyproject.toml` |
| Verdict | changes requested → **approved after fixes** (all findings resolved before the initial commit) |

## Findings

| # | Severity | Location | Finding | Resolution |
|---|---|---|---|---|
| 1 | blocking | `.github/skills/retrieval-evaluation/SKILL.md` | The staged copy failed `ruff format --check` (ruff formats Python blocks in Markdown); the fix existed only in the working tree. | Re-staged; `format` gate PASS on the committed tree. |
| 2 | major | `scripts/hooks/format_edited.py`, `.github/hooks/format-python.json` | The hook formatted any `.py` path found anywhere in the payload, including files an agent only *read* and third-party files in `.venv` (ruff ignores `exclude` for explicit paths); its findings were emitted as `systemMessage`, which the Copilot harness does not give to the model; stdin was decoded with the console code page; `apply_patch` edits were missed. | Rewritten: only edit tools, only tool *arguments* (never results), paths from `apply_patch` headers, excluded folders skipped and `--force-exclude` passed to ruff, UTF-8 payload decoding, `additionalContext` output (top-level and `hookSpecificOutput`), Copilot hook file format (`version: 1`, `postToolUse`, `bash`/`powershell`). Pinned by `tests/test_hooks.py` (13 tests). |
| 3 | minor | `scripts/verify.py`, `tests/conftest.py` | Rows moved to `## Retired` would still be parsed as active: the trace gate would demand tests for them and markers could still reference them. | One parser (`verify.requirement_rows`) stops at `## Retired`; `conftest.known_requirements` reuses it. `tests/test_verify.py::test_retired_requirements_are_neither_required_nor_accepted`. |
| 4 | minor | `scripts/verify.py`, `compose.yaml` | `--require-engines` counted the SQL Server integration test alone as `mssql=passed`; the compose recipe left SQL Server out of `SQLMEM_TEST_URLS`, so QA-ENGINES could be reported proven without the cross-engine scenario on SQL Server. | Only `test_end_to_end_on_engine[...]` counts per engine; the integration test is reported as `mssql-integration`. Compose recipe includes the SQL Server URL (URL-safe throwaway password). `tests/test_verify.py::test_engines_count_only_the_cross_engine_scenario`. |
| 5 | minor | `scripts/engines.ps1` | `stop` trusted PIDs from `pids.json`, which can outlive a reboot; a reused PID could kill an unrelated process, and a failure left the state file behind. | `Get-OwnProcess` stops a process only when its executable path is the expected `postgres.exe` / `mariadbd.exe`; the state file is removed in `finally`. Checked against the running servers and a foreign PID. |

## Found while verifying the fixes (not in the review)

| # | Severity | Location | Finding | Resolution |
|---|---|---|---|---|
| 6 | blocking for CI | `sqlmem/kb.py`, `sqlmem/store.py`, `tests/test_mssql.py` | Simulating the CI quality job (extras `mcp,llm,duckdb,dev`): pyright reported 3 unresolved imports for the optional `fastembed` and `pyodbc` packages. | Optional packages are imported dynamically (`importlib.import_module`, `pytest.importorskip`); pyright 0 errors in both the full and the CI environment. The `dev` extra now includes `mcp,llm,duckdb` and pins ruff, mypy and pyright. |
| 7 | major | `sqlmem/kgraph.py` (`_Checker`) | On Windows with Python < 3.13, `time.monotonic()` ticks every 15.6 ms (`GetTickCount64`), so a verification budget could overrun by one tick; `test_verification_budget_saves_items_unverified` failed 11/12 runs on Python 3.10.21. | The budget uses `time.perf_counter()` (QueryPerformanceCounter, 0.1 µs): 20/20 runs pass on Python 3.10.21. |
| 8 | minor | `pyproject.toml` / coverage | Coverage in the CI-like environment was 85.70% against the 85% gate. | `test_cli_explore_memory_validate_and_stats_commands` covers the remaining CLI commands: 87.64% (CI-like), 87.12% (Python 3.10). |

## Areas reviewed without findings

`render.select_tables` / `render_context` (empty rankings, already-chosen value tables, ordering, cap, "other tables"
list), `KnowledgeBase.close()`, the evidence recorder and fixtures, `evals/run_retrieval.py` (ablation restore, gate
selection, index closed before temp cleanup), `verify.py` exit codes and git detection, CI workflows (action tags
exist, secret masking, `GITHUB_ENV` writes), `pyproject.toml`, and the annotation-only edits in `sqlmem/` (no runtime
change; every `zip(strict=True)` zips equal-length sequences).

## Evidence

Final verification of the fixed tree: [evidence record](../evidence/2026-10-30-repository-baseline.md).
