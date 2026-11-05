# Evidence: bounded source-linked agentic memory

| | |
|---|---|
| Date | 2026-11-02 (UTC) |
| Commit | Uncommitted working tree based on `b204e65539059316670335e20bcf98cf00d11df1` |
| Verified snapshot | `b204e6553905 + 25 uncommitted file(s) (main)`, generated `2026-11-01T22:56:59-08:00` |
| Requirements | REQ-AMEM-01..09; preserves REQ-MEM-01/02 and REQ-RET-03/05 |
| Review | [Independent review and resolved findings](../reviews/2026-11-02-agentic-memory.md) |
| CI run | Not run |

## Change

[ADR 0012](../design/adr/0012-bounded-source-linked-agentic-memory.md) adds private working, episodic,
semantic and procedural memory without changing the legacy JSONL store. Submitted conversations are sanitized,
retained with source links, and used by either the host agent's task/save workflow or explicit configured-model
learning. Structurally valid inferred proposals are accepted automatically; scoped-key updates preserve earlier
revisions. Feedback affects private recall, while compaction archives active records without deleting sources.
The CLI, MCP and library expose the same lifecycle, including history, archive recall and restoration.

The authoritative `private/memory.sqlite3` is not a disposable index. Its separate derived BM25 projection
cannot displace schema retrieval hits, and private material is excluded from public generated documentation.
Only documentation/evidence/handoff completion follows the verified code/test snapshot above.

## Verification

Commands, from the repository root:

```powershell
.\scripts\engines.ps1 start
.\scripts\engines.ps1 env | Invoke-Expression
.\.venv\Scripts\python.exe scripts\verify.py --require-engines
```

Copied from `build/evidence/summary.md`:

| Gate | Verdict | Time | Summary |
|---|---|---|---|
| lint | PASS | 0.3s | All checks passed! |
| format | PASS | 0.3s | 123 files already formatted |
| mypy | PASS | 1.3s | Success: no issues found in 48 source files |
| pyright | PASS | 32.6s | 0 errors, 0 warnings, 0 informations |
| tests | PASS | 147.3s | 353 passed, 36 warnings in 144.33s (0:02:24); coverage 90% (min 85%) |
| eval | PASS | 1.8s | Retrieval eval [none]: full 24/24, mean recall 1.00, avg tables 4.9, concepts shown 24, 0.1s; Gate: full >= 24, mean recall >= 1.0 -> PASS |
| trace | PASS | 0.0s | 51/51 requirements proven by passing tests; engines: duckdb=passed, mssql=passed, mssql-integration=passed, mysql=passed, postgresql=passed, sqlite=passed |

### Requirements

Copied rows from `build/evidence/traceability.md`:

| Requirement | Status | Passed | Failed | Skipped | Evidence |
|---|---|---|---|---|---|
| REQ-AMEM-01 | proven | 13 | 0 | 0 | test_memory_interfaces.py::test_cli_build_closes_private_connections_it_opens (x2), test_memory_lifecycle.py::test_busy_writer_returns_explicit_error, test_memory_lifecycle.py::test_capacity_rollback_and_consistent_backup, test_memory_lifecycle.py::test_concurrent_first_writers_and_cached_schema_version_check, test_memory_lifecycle.py::test_concurrent_writers_serialize_and_schema_fails_closed, test_memory_lifecycle.py::test_projection_contents_and_generation_roll_back_atomically, test_memory_lifecycle.py::test_projection_failure_commits_and_next_recall_repairs, test_memory_lifecycle.py::test_projection_refresh_only_observes_committed_matching_source_snapshot, test_memory_lifecycle.py::test_real_capacity_rollback_retry_and_reopen_lexical_recall, test_memory_lifecycle.py::test_source_edits_are_immutable_and_do_not_rewrite_items, test_memory_lifecycle.py::test_source_revisions_retries_history_restore, test_memory_retrieval.py::test_memory_recall_rebuilds_both_disposable_indexes_without_losing_sources |
| REQ-AMEM-02 | proven | 54 | 0 | 0 | test_memory_interfaces.py::test_all_mcp_tools_annotations_and_keyless_workflow, test_memory_interfaces.py::test_cli_file_errors_do_not_echo_contents (x2), test_memory_learning.py::test_model_errors_are_safe_and_apply_nothing, test_memory_lifecycle.py::test_injection_and_inert_sql_are_never_executed, test_memory_lifecycle.py::test_private_symlink_escape_is_rejected, test_memory_lifecycle.py::test_proposal_batch_limits_and_procedural_boundaries, test_memory_lifecycle.py::test_proposal_validation_is_atomic (x14), test_memory_lifecycle.py::test_public_boundaries_fail_explicitly (x11), test_memory_lifecycle.py::test_reject_bad_messages_without_source (x5), test_memory_lifecycle.py::test_sanitized_sources_tasks_indexes_and_feedback, test_memory_lifecycle.py::test_sanitizer_credential_and_phone_patterns (x8), test_memory_lifecycle.py::test_source_bounds_before_and_after_sanitizing (x6), test_memory_llm_bounds.py::test_streaming_sdk_value_errors_are_sanitized, test_memory_retrieval.py::test_context_keeps_working_state_session_scoped_and_visibly_untrusted |
| REQ-AMEM-03 | proven | 22 | 0 | 0 | test_memory_interfaces.py::test_mcp_explicit_learning_awaits_cancellable_transport, test_memory_learning.py::test_explicit_model_learning_uses_same_validator_and_all_types, test_memory_learning.py::test_injected_client_deadline_rejects_late_reply_without_writes, test_memory_learning.py::test_memory_llm_options_disable_retry_and_bound_reply (x3), test_memory_learning.py::test_model_errors_are_safe_and_apply_nothing, test_memory_learning.py::test_only_explicit_learning_calls_model, test_memory_lifecycle.py::test_injection_and_inert_sql_are_never_executed, test_memory_lifecycle.py::test_large_catalog_task_hints_are_bounded_and_omissions_remain_valid, test_memory_llm_bounds.py::test_memory_deadline_prevents_apply_or_more_attempts, test_memory_llm_bounds.py::test_memory_disables_sdk_retries_and_no_provider_fallback, test_memory_llm_bounds.py::test_memory_negotiation_has_three_attempts_and_remaining_deadline, test_memory_llm_bounds.py::test_memory_rejects_bad_reply_once (x4), test_memory_llm_bounds.py::test_streaming_sdk_value_errors_are_sanitized, test_memory_transport.py::test_absolute_deadline_cancels_and_closes_in_flight_read, test_memory_transport.py::test_absolute_deadline_stops_slow_drip_before_consuming_whole_body, test_memory_transport.py::test_async_azure_identity_uses_and_closes_cancellable_httpx_transport, test_memory_transport.py::test_identity_httpx_bridge_reads_form_response_and_closes |
| REQ-AMEM-04 | proven | 29 | 0 | 0 | test_memory_learning.py::test_explicit_model_learning_uses_same_validator_and_all_types, test_memory_lifecycle.py::test_atomic_conflicts_stale_tasks_and_support, test_memory_lifecycle.py::test_busy_writer_returns_explicit_error, test_memory_lifecycle.py::test_concurrent_first_writers_and_cached_schema_version_check, test_memory_lifecycle.py::test_concurrent_writers_serialize_and_schema_fails_closed, test_memory_lifecycle.py::test_projection_refresh_only_observes_committed_matching_source_snapshot, test_memory_lifecycle.py::test_proposal_batch_limits_and_procedural_boundaries, test_memory_lifecycle.py::test_proposal_validation_is_atomic (x14), test_memory_lifecycle.py::test_real_capacity_rollback_retry_and_reopen_lexical_recall, test_memory_lifecycle.py::test_reject_bad_messages_without_source (x5), test_memory_lifecycle.py::test_source_edits_are_immutable_and_do_not_rewrite_items, test_memory_lifecycle.py::test_source_revisions_retries_history_restore |
| REQ-AMEM-05 | proven | 18 | 0 | 0 | test_memory_lifecycle.py::test_caps_compaction_manifest_and_recovery, test_memory_lifecycle.py::test_explicit_compaction_is_bounded_and_archive_events_visible, test_memory_lifecycle.py::test_item_history_cursor_revision_selection_and_restore_stale, test_memory_lifecycle.py::test_public_boundaries_fail_explicitly (x11), test_memory_lifecycle.py::test_session_eligibility_cursor_and_source_pages, test_memory_lifecycle.py::test_source_revisions_retries_history_restore, test_memory_retrieval.py::test_context_keeps_working_state_session_scoped_and_visibly_untrusted, test_memory_retrieval.py::test_memory_recall_rebuilds_both_disposable_indexes_without_losing_sources |
| REQ-AMEM-06 | proven | 21 | 0 | 0 | test_memory_lifecycle.py::test_capacity_rollback_and_consistent_backup, test_memory_lifecycle.py::test_caps_compaction_manifest_and_recovery, test_memory_lifecycle.py::test_explicit_compaction_is_bounded_and_archive_events_visible, test_memory_lifecycle.py::test_global_caps_and_batch_overflow (x4), test_memory_lifecycle.py::test_just_restored_low_usefulness_item_can_be_rearchived_idempotently, test_memory_lifecycle.py::test_public_boundaries_fail_explicitly (x11), test_memory_lifecycle.py::test_real_capacity_rollback_retry_and_reopen_lexical_recall, test_memory_retrieval.py::test_compaction_removes_active_context_not_recoverable_evidence |
| REQ-AMEM-07 | proven | 4 | 0 | 0 | test_memory_lifecycle.py::test_feedback_idempotence_order_correction_and_stale, test_memory_lifecycle.py::test_feedback_usefulness_is_clamped_and_has_source_provenance, test_memory_lifecycle.py::test_just_restored_low_usefulness_item_can_be_rearchived_idempotently, test_memory_retrieval.py::test_helpful_feedback_improves_bounded_context_selection_without_schema_changes |
| REQ-AMEM-08 | proven | 11 | 0 | 0 | test_memory_interfaces.py::test_all_mcp_tools_annotations_and_keyless_workflow, test_memory_interfaces.py::test_cli_build_closes_private_connections_it_opens (x2), test_memory_interfaces.py::test_cli_file_errors_do_not_echo_contents (x2), test_memory_interfaces.py::test_cli_restore_feedback_and_no_config_learning, test_memory_interfaces.py::test_mcp_explicit_learning_awaits_cancellable_transport, test_memory_interfaces.py::test_mcp_submit_feedback_compact_restore_history_and_errors, test_memory_interfaces.py::test_nested_cli_task_save_history_recall_and_errors, test_memory_learning.py::test_only_explicit_learning_calls_model, test_memory_lifecycle.py::test_large_catalog_task_hints_are_bounded_and_omissions_remain_valid |
| REQ-AMEM-09 | proven | 12 | 0 | 0 | test_memory_interfaces.py::test_cli_build_closes_private_connections_it_opens (x2), test_memory_lifecycle.py::test_projection_contents_and_generation_roll_back_atomically, test_memory_lifecycle.py::test_projection_failure_commits_and_next_recall_repairs, test_memory_lifecycle.py::test_projection_refresh_only_observes_committed_matching_source_snapshot, test_memory_lifecycle.py::test_real_capacity_rollback_retry_and_reopen_lexical_recall, test_memory_retrieval.py::test_compaction_removes_active_context_not_recoverable_evidence, test_memory_retrieval.py::test_context_keeps_working_state_session_scoped_and_visibly_untrusted, test_memory_retrieval.py::test_helpful_feedback_improves_bounded_context_selection_without_schema_changes, test_memory_retrieval.py::test_memory_recall_rebuilds_both_disposable_indexes_without_losing_sources, test_memory_retrieval.py::test_private_memory_is_excluded_from_public_docs_and_graph, test_memory_retrieval.py::test_saturated_agentic_memory_preserves_schema_hits_tables_and_examples |

Legacy evidence remains `REQ-MEM-01` proven by two passing tests and `REQ-MEM-02` by one.
The original compatibility baseline command, `python -m pytest tests\test_sqlmem.py tests\test_llm.py -q`,
reported `60 passed in 11.45s` before feature implementation.

### Red, then green and independent acceptance

- Initial feature tests reported missing library/CLI APIs; the parent's retrieval acceptance test failed with
  `AttributeError: 'KnowledgeBase' object has no attribute 'submit_conversation'` (`1 failed in 0.67s`).
- `python -m pytest tests\test_memory_retrieval.py -q --durations=6` reported `6 passed in 28.88s`.
  The saturation case saves 2,336 semantic records, leaving 2,080 archived at the 256 active-item cap. It asserts
  identical schema hit IDs/scores, table context, index counts and public-document bytes before and after.
  The final full suite reruns these tests.
- `test_helpful_feedback_improves_bounded_context_selection_without_schema_changes` proves helpful feedback
  moves an otherwise excluded relevant memory into the five-item context budget without changing schema hits.
- An installed `sqlmem.exe` subprocess smoke workflow passed submit/task/save/recall/feedback/compact/history/
  restore across process exits. It recovered a submitted source and restored an archived item using a temporary
  copy of the example KB, removed on exit. No model endpoint was contacted.
- The integrated browser parsed and rendered all 12 diagrams in the changed architecture views using VS Code's
  existing Mermaid bundle. Temporary loopback viewers were stopped.

### Retrieval evaluation

Before commands:

```powershell
.\.venv\Scripts\python.exe -m evals.run_retrieval --ablate-kg
.\.venv\Scripts\python.exe -m evals.run_retrieval --embedder kb --ablate-kg
```

The before/after console summaries are unchanged:

| Embedder | Before full / recall / average tables | After full / recall / average tables | Without KG, before and after |
|---|---|---|---|
| none (BM25) | 24/24 / 1.00 / 4.9 | 24/24 / 1.00 / 4.9 | 23/24 / 0.98 / 4.2 |
| fastembed | 24/24 / 1.00 / 4.5 | 24/24 / 1.00 / 4.5 | 22/24 / 0.95 / 4.0 |

Numbers above are copied at the console's displayed precision; no improvement is inferred from rounding.
Final after commands also wrote detailed JSON:

```powershell
.\.venv\Scripts\python.exe -m evals.run_retrieval --ablate-kg --out build\agentic-memory-after-bm25.json
.\.venv\Scripts\python.exe -m evals.run_retrieval --embedder kb --ablate-kg --out build\agentic-memory-after-fastembed.json
```

The JSON after results are BM25 full `24`, recall `1.0`, average tables `4.88`; without KG full `23`,
recall `0.9792`, average `4.21`. Fastembed (`BAAI/bge-small-en-v1.5`) full `24`, recall `1.0`,
average `4.5`; without KG full `22`, recall `0.9514`, average `3.96`.
Both full-hit and mean-recall gates pass. Fastembed runs used the existing cached local embedder, not a
conversation-learning endpoint.

### Cross-engine

The final trace gate above proves the common scenario passed on each engine. Versions were read from the
running local servers through `run_select`, plus the installed SQLite/DuckDB runtimes:

| Engine | Version | Outcome |
|---|---|---|
| SQLite | 3.50.4 | passed |
| DuckDB | 2.0.0 | passed |
| PostgreSQL | 18.6 | passed |
| MariaDB | 11.4.5 | passed |
| SQL Server LocalDB | 17.0.4025.3 | passed, including separate SQL Server integration |

After verification, `.\scripts\engines.ps1 stop` followed by `status` reported all owned servers stopped.

## Review outcome

The independent review found two blocking issues and one major issue, all corrected and independently
rechecked. Original severities and reproductions remain in the linked review:

- R1: publish private projection only from committed source state, with atomic index contents/generation.
  Real `SQLITE_FULL` rollback/retry/reopen and projection-snapshot regressions pass.
- R2: cancel in-flight async response consumption at the absolute deadline, with bounded reply/attempts and
  scoped cleanup. Slow-drip and blocked-read tests pass; the reviewer also observed no remaining operation
  tasks or open owned clients in its socket-free cancellation probe.
- R3: select deterministic table hints within the prompt budget, report omissions, and validate against the
  entire catalog. The 150-table public-facade regression passes.

The reviewer reran `28 passed in 8.03s` for the fixed areas. The final all-PASS gate run follows that recheck;
the review record carries the final disposition.

## Gaps and risks

- Conversation learning requires submitted content/imports; MCP cannot observe arbitrary host conversations.
  Automatic acceptance is structural, not proof of truth: records remain visibly inferred. Same-key updates
  resolve scoped conflicts; unrelated keys are not a general semantic contradiction solver.
- Sanitization is heuristic, not DLP. Callers must omit sensitive database values and pre-sanitize content.
  Only sanitized originals are recoverable; removed secrets cannot be restored. Local SQLite/backups are
  plaintext; Git ignore is not encryption or access control.
- Compaction reduces active recall, not necessarily disk usage. Original sources/revisions are never
  automatically purged, and the bounded store fails explicitly at capacity. No lossless-summary, host
  prompt-injection immunity or online-model-training claim is made.
- Real Ollama, Azure OpenAI and OpenAI generation endpoints were not exercised. New learning/transport tests
  use in-process clients/transports without sockets, including provider selection and Azure identity cleanup.
- The final suite reports 36 SQLite resource warnings. The implementation diagnosis reproduced general
  public-index/SQLAlchemy warnings on pre-feature HEAD; unrelated legacy ownership was not refactored.
  A feature-coupled temporary private-store leak was fixed with success/error closure regressions.
- CI, other operating systems and other Python versions were not run for this change.
- Existing VS Code MCP processes must restart to load the new tools. No user KB was populated with inferred
  conversation content during development; the feature remains uncommitted and unpushed at this handoff.
