# Evidence: publish the project publicly under mcbelton on GitHub.com

| | |
|---|---|
| Date | 2026-11-05 (UTC) |
| Commit | Evidence captured before root commit `06577ce751f569c53d3e3981ca8e1c977fb07b57`; outcomes appended afterward |
| Requirements | REQ-AMEM-03, QA-TYPES, QA-TESTS |
| Review | [Publication review](../reviews/2026-11-05-github-publication.md) |
| CI run | [41962266224](https://github.com/mcbelton/sql-semantic-memory/actions/runs/41962266224): failure (2 of 7 jobs) |

## Change

Publish [mcbelton/sql-semantic-memory](https://github.com/mcbelton/sql-semantic-memory) as a public
MIT-licensed repository, configure `origin`, and update README, security reporting, changelog and handoff.
Remove previous hosting URLs, local account paths and session IDs before public visibility.
The repository starts from one initial snapshot commit; older commit IDs in records are local provenance.
A clean install exposed an undeclared `httpx` import: OpenAI 3.46.0 and MCP 2.3.0 now depend on `httpx2`.
Declare the already-used transport in `llm`, without changing request/cancellation behavior
([ADR 0013](../design/adr/0013-declare-httpx-transport-dependency.md)).

## Verification

### Red: clean-install failure

Commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp,llm,duckdb,dev]"
.\.venv\Scripts\python.exe scripts\verify.py --fix
```

Before the manifest fix, test collection failed at `tests/test_memory_transport.py:8` with
`ModuleNotFoundError: No module named 'httpx'`; mypy reported eight errors in two files and
pyright reported two unresolved imports. `pip show openai mcp` and `importlib.metadata.requires("openai")`
confirmed the installed SDKs require `httpx2`. `pip check` alone passed, so it did not detect the undeclared import.

### Green: installed declaration and full gates

Commands:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mcp,llm,duckdb,dev]" --quiet
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\verify.py --fix
```

`pip check`: `No broken requirements found.`
Gate table copied from the final pre-commit `build/evidence/summary.md`, after the license metadata changes,
for Windows/Python 3.14.7:

| Gate | Verdict | Time | Summary |
|---|---|---|---|
| lint | PASS | 0.1s | All checks passed! |
| format | PASS | 0.1s | 134 files already formatted |
| mypy | PASS | 0.6s | Success: no issues found in 48 source files |
| pyright | PASS | 4.2s | 0 errors, 0 warnings, 0 informations |
| tests | PASS | 32.4s | 349 passed, 1 skipped, 33 warnings in 31.24s; coverage 88% (min 85%) |
| eval | PASS | 0.7s | Retrieval eval [none]: full 24/24, mean recall 1.00, avg tables 4.9, concepts shown 24, 0.1s; Gate: full >= 24, mean recall >= 1.0 -> PASS |
| trace | PASS | 0.0s | 51/51 requirements proven by passing tests; engines: duckdb=passed, sqlite=passed |

### Package license metadata

`python -m build` produced `sqlmem-0.2.0.tar.gz` and `sqlmem-0.2.0-py3-none-any.whl`. A focused
inspection confirmed wheel metadata contains `License-Expression: MIT` and `License-File: LICENSE`, and both
wheel and sdist include `LICENSE`: `Package license metadata: PASS`.

### Requirements

Rows copied from `build/evidence/traceability.md`:

| ID | Status | Passed | Failed | Skipped | Evidence |
|---|---|---|---|---|---|
| REQ-AMEM-03 | proven | 22 | 0 | 0 | test_memory_interfaces.py::test_mcp_explicit_learning_awaits_cancellable_transport, test_memory_learning.py::test_explicit_model_learning_uses_same_validator_and_all_types, test_memory_learning.py::test_injected_client_deadline_rejects_late_reply_without_writes, test_memory_learning.py::test_memory_llm_options_disable_retry_and_bound_reply (x3), test_memory_learning.py::test_model_errors_are_safe_and_apply_nothing, test_memory_learning.py::test_only_explicit_learning_calls_model, test_memory_lifecycle.py::test_injection_and_inert_sql_are_never_executed, test_memory_lifecycle.py::test_large_catalog_task_hints_are_bounded_and_omissions_remain_valid, test_memory_llm_bounds.py::test_memory_deadline_prevents_apply_or_more_attempts, test_memory_llm_bounds.py::test_memory_disables_sdk_retries_and_no_provider_fallback, test_memory_llm_bounds.py::test_memory_negotiation_has_three_attempts_and_remaining_deadline, test_memory_llm_bounds.py::test_memory_rejects_bad_reply_once (x4), test_memory_llm_bounds.py::test_streaming_sdk_value_errors_are_sanitized, test_memory_transport.py::test_absolute_deadline_cancels_and_closes_in_flight_read, test_memory_transport.py::test_absolute_deadline_stops_slow_drip_before_consuming_whole_body, test_memory_transport.py::test_async_azure_identity_uses_and_closes_cancellable_httpx_transport, test_memory_transport.py::test_identity_httpx_bridge_reads_form_response_and_closes |
| QA-TYPES | proven | 0 | 0 | 0 | mypy: Success: no issues found in 48 source files; pyright: 0 errors, 0 warnings, 0 informations |
| QA-TESTS | proven | 0 | 0 | 0 | tests: 349 passed, 1 skipped, 33 warnings in 31.24s; coverage 88% (min 85%) |

### Repository publication checks

- The first private repository's initial commit contained previous-hosting references. With owner approval,
  `gh repo delete mcbelton/sql-semantic-memory --yes` deleted that private repository (0 forks), and
  `gh repo create mcbelton/sql-semantic-memory --private` recreated it before any visibility change.
- `gh repo view mcbelton/sql-semantic-memory --json nameWithOwner,isPrivate,isEmpty,url` returned
  `mcbelton/sql-semantic-memory`, `isPrivate: true`, `isEmpty: true`; the Actions runs API returned `0` runs and
  `git ls-remote origin` returned no refs.
- `git remote -v` shows the GitHub.com URL for fetch and push.
- Initial eligible-file inspection found no database, derived `index.db`, credential-file or private-memory
  paths; `.gitignore` excludes `.venv`, `build`, `dbs` and `private` content.
- A high-signal credential-pattern scan matched only the literal `private-key-canary` fixture in
  `tests/test_memory_lifecycle.py`, not a private key. This is not a comprehensive secret audit.
- Before commit, a case-insensitive scan of the staged tree and planned commit metadata must find no
  previous-hosting domain, previous account name or local session identifiers.
- Local documentation-link validation passed 77 relative file references across eight publication documents,
  including the new license and vendor-notice links. An exact-match check confirmed all seven gate rows.

### Planned publication steps

1. Create one orphan root commit from the scrubbed tree; confirm `git rev-list --count main` is `1`.
2. Push only `main`, never `--mirror` or local agent checkpoint refs; confirm the remote has only `HEAD` and
   `refs/heads/main` at that root.
3. Change visibility to public, enable private vulnerability reporting, then verify both through the GitHub API.
4. Record those outcomes and the first CI run in a follow-up handoff commit.

### Post-publication outcomes

- Root commit `06577ce751f569c53d3e3981ca8e1c977fb07b57` passed staged-tree and commit-metadata scans for the
  previous-hosting domain, previous account name and local session identifiers; `git rev-list --count main` was `1`.
- `git push -u origin refs/heads/main:refs/heads/main` pushed only `main`; `git ls-remote origin` returned exactly
  `HEAD` and `refs/heads/main` at the root commit.
- `gh repo edit ... --visibility public --accept-visibility-change-consequences` succeeded. `gh repo view`
  returned `visibility: PUBLIC`; the commits API returned `1`; `gh api .../license` returned `LICENSE`, `MIT`.
- `gh api --method PUT .../private-vulnerability-reporting` succeeded, then the GET endpoint returned `enabled: true`.
- First public CI run [41962266224](https://github.com/mcbelton/sql-semantic-memory/actions/runs/41962266224):
  conclusion `failure`. Quality gates, Windows/Python 3.13, Ubuntu/Python 3.11, Ubuntu/Python 3.12 and the
  PostgreSQL 18/MariaDB 11.4/SQL Server 2022 cross-engine job passed.
- Ubuntu/Python 3.10: `[tests] FAIL 2 failed, 347 passed, 1 skipped`; trace `48/51`, missing
  REQ-AMEM-01, REQ-AMEM-09 and REQ-CHART-01. Failing nodes:
  `tests/test_charts.py::test_fractional_datetime_order_is_chronological` (`sqlmem/charts.py:249`, ISO datetime
  rejection) and `tests/test_memory_lifecycle.py::test_projection_failure_commits_and_next_recall_repairs`
  (`store_failed: private` from `sqlmem/memory_lifecycle.py:193`).
- macOS/Python 3.13: `[tests] FAIL 1 failed, 348 passed, 1 skipped`; trace `50/51`, missing REQ-CHART-08.
  `tests/test_chart_canvas.py::test_chart_canvas` failed because Node test
  `viewer caps active requests at eight and closes open sockets` raised `ECONNRESET`.
- These failures are in inherited behavior, not the dependency, license or publication edits. They were not fixed in
  this publication scope.

### Independent review

The [reviewer record](../reviews/2026-11-05-github-publication.md) approved the first dependency/publication
scope. Its public-release recheck requested changes for push preconditions, premature results, stale review
status, the commit description, vulnerability-reporting verification and link-count freshness. This record
was revised to address them; the review record holds the final verdict.

## Gaps and risks

- Hosted CI ran the configured matrix: Python 3.10 and macOS failures remain open (see post-publication outcomes).
- PostgreSQL, MariaDB and SQL Server were not started; only SQLite and DuckDB ran. SQL/dialect logic was unchanged.
- The SQL Server integration test was skipped; the run reported 33 resource warnings. No gate was lowered.
- Fastembed evaluation was not run; retrieval behavior was not changed. The required BM25 gate passed.
- The earlier cancellation-test failure did not recur here; no root cause or general flake fix is claimed.
- The pre-existing prompt-to-skill migration remains changes-requested, including broken relative references and
  lost agent routing ([review](../reviews/2026-11-03-prompt-to-skill-migration.md)); publication does not resolve it.
- The repository starts from one initial snapshot commit; older commit IDs in records are local provenance.
- The full initial-snapshot whitespace check reports pre-existing extra EOF lines in generated KB table
  documents and carriage-return warnings in `dbo__DatabaseLog.md`. Those generated files were preserved;
  they are not part of the publication/dependency edits.
