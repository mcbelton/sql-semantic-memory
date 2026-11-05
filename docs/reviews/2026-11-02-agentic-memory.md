# Independent review: bounded source-linked agentic memory

**Verdict: approve.** R1–R3 are resolved in the rechecked uncommitted snapshot. Fresh final verification at
`2026-11-01T22:56:59-08:00` passes all seven gates; see final disposition below.

Reviewed the uncommitted feature against baseline `b204e65539059316670335e20bcf98cf00d11df1`
(also HEAD). The committed Mermaid fix is baseline, not part of this review. Read all changed hunks,
surrounding integrations, both new modules, all five new test files, full ADR 0012 and REQ-AMEM-01..09.
Instructions: `AGENTS.md`, applicable documentation/evidence instructions, evidence-driven-development process
and `docs/reviews/checklist.md`. No implementation edits, delegation, full verification/eval rerun, or user-KB
rebuild were performed. Reproductions used disposable temporary stores and in-process clients, without sockets.

## Findings and resolutions

Line numbers in this table identify the original reviewed snapshot. Original severities are retained;
fixed-snapshot locations and proof are recorded in the bounded recheck below.

| ID | Severity | File:line | Issue | Concrete fix | Resolution |
|---|---|---|---|---|---|
| R1 | **blocking** | `sqlmem/memory_lifecycle.py:255-263`, `:721-746` | The private index commits before the authoritative transaction. A later authoritative rollback leaves an index stamped with an uncommitted event sequence. The next successful mutation can reuse that sequence and incorrectly skip rebuilding. Accepted content becomes unsearchable across reopen. Reproduced with real `SQLITE_FULL`, not just injected failure. Violates AMEM-01/04/06/09. | Publish the projection only from committed authoritative state, or use rollback/crash-safe state identities that cannot alias different histories. Keep projection contents and its generation atomic. Add the capacity-failure/retry/reopen lexical-recall regression below; merely invalidating an in-memory cache on exceptions does not cover process crashes. | **Resolved in uncommitted fixed snapshot**; see bounded recheck. |
| R2 | **blocking** | `sqlmem/llm.py:255-270` | `timeout=remaining` is an HTTP per-operation/inactivity timeout, not an absolute deadline. The synchronous SDK call can keep reading indefinitely while each read succeeds within that timeout; the monotonic check runs only after the entire response returns. The advertised 60-second total bound therefore does not bound in-flight learning. Violates AMEM-03 and ADR 0012. | Enforce an absolute deadline during transport/response consumption with cancellation/closure of in-flight work, not only after return. Preserve the three-attempt/no-repair/no-fallback contract. Add a socket-free slow-drip transport test that proves consumption stops at the deadline, rather than only rejecting an already-late reply. | **Resolved in uncommitted fixed snapshot**; see bounded recheck. |
| R3 | **major** | `sqlmem/memory_lifecycle.py:345-346`; caller `sqlmem/kb.py:450-451` | Every canonical table name is passed as a hint, then the entire list is rejected above 8 KiB. A valid 150-table catalog with 9,451 bytes of names makes both public `memory_task` and `learn_conversation` unusable, even for table-independent memory. CLI/MCP callers cannot reduce this internally generated field. | Deterministically select hints within the byte budget, disclose omissions and retain full-catalog table validation. Add public-facade tests above the hint budget, including a table-independent proposal and validation against omitted table names. | **Resolved in uncommitted fixed snapshot**; see bounded recheck. |

### R1: real store-capacity rollback poisons the next generation

Run with the project interpreter from the repository root. This is a reduced version of the review probe:

```python
import tempfile
from pathlib import Path
from sqlmem.memory_lifecycle import LifecycleStore

with tempfile.TemporaryDirectory() as directory:
    store = LifecycleStore(Path(directory))
    try:
        store.submit_conversation("chat", [{"role": "user", "content": "source"}])
        con = store._connection()
        pages = con.execute("PRAGMA page_count").fetchone()[0]
        con.execute(f"PRAGMA max_page_count={pages}")

        def proposal(body):
            return {
                "task_id": store.memory_task("chat")["task_id"],
                "items": [
                    {
                        "type": "semantic",
                        "key": "fact",
                        "text": body,
                        "steps": [],
                        "tables": [],
                        "message_indices": [0],
                        "base_revision": 0,
                    }
                ],
            }

        try:
            store.save_memory(proposal("X" * 2000))
        except ValueError as error:
            print(error)
        print(store._seq(con), store._index.meta("lifecycle_generation"))
        print(store.save_memory(proposal("CommittedCanary"))["accepted"])
        print(len(store.recall_memory()["items"]))
        print(len(store.recall_memory("CommittedCanary")["items"]))
        store.close()
        store = LifecycleStore(Path(directory))
        print(len(store.recall_memory("CommittedCanary")["items"]))
    finally:
        store.close()
```

Observed using the initial 15-page database:

```text
store_full: private. Back up with SQLite backup API and relocate; originals are not deleted.
1 2
1
1
0
0
```

After rollback there were zero authoritative items. After the subsequent successful save, empty-query recall
returned `CommittedCanary`, but the private index still contained the rolled-back text. Explicit
`refresh_index()` repaired lexical recall to one result. A separate trigger-induced finalization failure
reproduced the same rollback/reused-sequence behavior. Existing
`test_capacity_rollback_and_consistent_backup` checks empty-query recall after a different full-store path;
`test_projection_failure_commits_and_next_recall_repairs` covers index failure, not authoritative failure
after a successful index refresh.

### R2: socket-free slow-response proof

Used the installed OpenAI SDK with an `httpx.HTTPTransport` backed by
`httpcore.ConnectionPool(network_backend=Backend())`, where the injected backend returns an in-memory
`httpcore.NetworkStream`. No DNS, sockets, real endpoint or model were used.

The stream returned an HTTP 200 header and a valid chat-completion JSON body in four successive body fragments.
Each `read()` advanced an injected monotonic clock by 20 seconds and recorded the timeout passed by httpcore.
`LLM("openai:stub", client=sdk, memory_mode=True, clock=lambda: now[0])` consumed all five reads before
`complete_memory_json("static", "data")` raised:

```text
result= model_deadline: learning exceeded 60 seconds
simulated elapsed seconds= 100.0
(time, per-read timeout)= [(20.0, 60.0), (40.0, 60.0), (60.0, 60.0), (80.0, 60.0), (100.0, 60.0)]
```

The real installed `httpcore._backends.sync.SyncStream.read` likewise sets the socket timeout and calls
`recv` for each read. A real slow-drip response can therefore exceed the deadline without any individual read
timing out. The existing late-reply tests prove no late application, not timely interruption.

### R3: public-facade large-catalog proof

In a temporary `KnowledgeBase(..., embedder="none")`, save a catalog with objects having these canonical names:

```python
names = [f"schema_{i:03d}.orders_with_a_descriptive_business_table_name_{i:03d}" for i in range(150)]
```

Each object used its corresponding schema/name/fqn and an empty columns list. Submit
`[{"role": "user", "content": "Prefer concise responses."}]` as conversation `chat`.
Both `kb.memory_task("chat")` and `kb.learn_conversation("chat", injected_stub)` returned:

```text
size_limit: table_hints. Use 0..8192 UTF-8 bytes.
```

The canonical hint list was 9,451 UTF-8 bytes; the model stub was never called. This is not an oversized
caller-supplied conversation or proposal: it is a valid catalog and an internally generated prompt component.

## Evidence checked

- Read fresh `build/evidence/summary.md`: **PASS**, timestamp `2026-11-01T22:27:01-08:00`,
  commit `b204e6553905 + 21 uncommitted file(s) (main)`.
  All seven gates pass: lint, format, mypy, pyright, tests, eval, trace.
- Supplied verification: **341 passed, 37 warnings**, coverage **90%**; **51/51 requirements**.
  Engine trace: SQLite, DuckDB, PostgreSQL, MySQL and SQL Server passed, including `mssql-integration`.
  Checked supporting test/eval logs, traceability and recorded retrieval outcomes.
- `build/evidence/tests.json` records all six tests in `test_memory_retrieval.py` passing, including saturation,
  source/index recovery, session isolation, public-document exclusion and actual bounded-context feedback selection.
- Inspected `build/agentic-memory-after-bm25.json`: full **24/24**, mean recall **1.0**, average tables **4.88**;
  KG ablation **23/24**, mean recall **0.9792**.
- Inspected `build/agentic-memory-after-fastembed.json`: full **24/24**, mean recall **1.0**, average tables **4.5**;
  KG ablation **22/24**, mean recall **0.9514**.
- Reviewer ran only three existing targeted tests:
  `test_memory_lifecycle.py::test_capacity_rollback_and_consistent_backup`,
  `test_memory_lifecycle.py::test_projection_failure_commits_and_next_recall_repairs`,
  `test_memory_llm_bounds.py::test_memory_deadline_prevents_apply_or_more_attempts`:
  **3 passed in 0.49s**. These passing tests do not cover the demonstrated failures above.
- During the final snapshot check, observed and read the parent's concurrent cleanup follow-up:
  the `contextlib` import and temporary-store ownership in `KnowledgeBase.build` (`sqlmem/kb.py:217-223`),
  plus the new parameterized
  `tests/test_memory_interfaces.py::test_cli_build_closes_private_connections_it_opens`.
  Independently ran only those new success/error cases: **2 passed in 1.67s**.
  The existing persistent lifecycle branch remains caller-owned; the new temporary branch closes on both
  normal return and refresh failure. This does not resolve R1/R2/R3.

## Checklist assessment

- **Correctness/history/concurrency:** inspected optimistic checks, retry reports, immutable revisions,
  inherited/support lineage, feedback, restore and archive caps. R1 remains a transaction/recovery defect;
  R3 is an availability defect at the generated-hint boundary.
- **SQL safety/portability:** new memory prose is inert; lifecycle SQL uses static statements and bound values.
  No new user/model SQL execution or dialect branch was introduced. Existing engine proof is in the supplied gates.
- **Privacy/trust/session boundaries:** inspected pre-write sanitization, private-path checks/ignore rules,
  static system instructions, untrusted JSON data, working-session eligibility and separate private BM25 storage.
  The new negative tests and retrieval acceptance tests exercise these boundaries. No additional high-confidence
  content leak or instruction-promotion defect was established.
- **Finite work/model use:** explicit learning is the only new model route; no fallback or repair loop found.
  R2 prevents accepting the total-latency claim as proven.
- **Typing/tests/docs:** gated typing/style passed; requirement mappings and documentation/ADR were read.
  No request for lossless summaries, automatic original deletion, model training or perfect heuristic DLP is
  inferred from the user's requirements.

## Gaps and risks

- The parent owns durable evidence/status updates. Before-eval summaries, installed-command checks and browser
  Mermaid rendering were supplied by the parent; they were not independently rerun. After-eval files were read
  directly; the unchanged-before/after claim still relies on the parent's baseline record.
- The parent reported a tightly coupled connection-leak follow-up for the **37 ResourceWarnings**. Per request,
  this review did not duplicate its diagnosis/reproduction. The observed `kb.py`/interface-test follow-up was
  inspected and its two targeted cases passed as recorded above. The available full verification summary still
  predates those edits; elimination of all 37 warnings and fresh full gates are not declared proven here.
- No full verification/eval was rerun, no real model/remote endpoint was contacted, and no user KB was rebuilt.
  The supplied passing gates are necessary but do not override the targeted counterexamples.
- Approval requires resolution of R1/R2 and resolution or explicit justification of R3, regression tests for the
  exact failures, independent inspection of any follow-up diff, and fresh required verification evidence for the
  resulting feature snapshot.

## Same-task bounded recheck — fixed uncommitted snapshot

The initial disposition above was changes requested. At the parent's request, rechecked only R1–R3 and
temporary-private-store closure against the follow-up, still based on `b204e65539059316670335e20bcf98cf00d11df1`.
Read the affected lifecycle/projection, LLM/transport, facade, CLI/MCP and regression-test changes, plus the
follow-up README/CHANGELOG claims. No implementation edits, full gates/evals, external endpoint calls or
user-KB rebuilds were performed by this reviewer.

### Resolutions

- **R1 — resolved, original severity blocking.** In `sqlmem/memory_lifecycle.py:250-277`, the report and
  authoritative mutation commit before projection publication. A second `BEGIN IMMEDIATE` serializes projection
  refresh with writers, obtaining heads and sequence from the same committed snapshot.
  `sqlmem/memory_lifecycle.py:758-782` passes generation metadata into
  `sqlmem/store.py:248-275`, which commits chunks and generation in the same index transaction.
  Cache/status failure after the source commit remains advisory (`index_pending`), rather than rolling back
  accepted source history. The exact real-full/retry/reopen regression now passes without an intervening
  refresh that would mask sequence aliasing. Atomic-publication and independent-connection snapshot checks
  also pass.
- **R2 — resolved, original severity blocking.** `sqlmem/llm.py:266-368` uses an awaited async streaming
  operation under `asyncio.wait_for`, per-chunk deadline/size checks and scoped response/client cleanup.
  It does not implement deadline enforcement by abandoning a worker thread. Owned transports are constructed
  inside the operation; sync callers use `asyncio.run`, active-loop callers have the explicit
  `acomplete_memory_json` entry point. The legacy non-memory synchronous path is retained.
  `sqlmem/llm_transport.py` bridges async Azure identity through the same cancellable HTTPX boundary.
  The slow-drip test stops at 60 simulated seconds before consuming the full body; the real-time blocked-read
  test observes cancellation and response closure. Negotiation remains at most three requests, with no SDK
  retries, JSON repair or provider fallback. Completion-envelope and extracted-content limits are checked.
- **R3 — resolved, original severity major.** `sqlmem/memory_lifecycle.py:355-427` selects hints deterministically
  within 8 KiB, reporting omitted counts and warnings. Proposal validation continues against the entire catalog
  supplied by the facade. The regression exercises table-independent saving, a reference to an omitted valid
  table, repeated-task determinism and explicit learning with a 150-table catalog.
- **Temporary-private closure — rechecked.** The temporary `LifecycleStore` in
  `KnowledgeBase.build` remains scoped by `contextlib.closing`; the existing persistent-store branch remains
  caller-owned. Both success and refresh-error cases pass. This is not a claim that every ResourceWarning in
  the full suite has been eliminated.

### Independently rerun proof

Command: project interpreter, `-m pytest -q -p no:cacheprovider`, selecting:

- `tests/test_memory_lifecycle.py::test_real_capacity_rollback_retry_and_reopen_lexical_recall`
- `tests/test_memory_lifecycle.py::test_projection_contents_and_generation_roll_back_atomically`
- `tests/test_memory_lifecycle.py::test_projection_refresh_only_observes_committed_matching_source_snapshot`
- `tests/test_memory_lifecycle.py::test_large_catalog_task_hints_are_bounded_and_omissions_remain_valid`
- `tests/test_memory_lifecycle.py::test_concurrent_writers_serialize_and_schema_fails_closed`
- `tests/test_memory_lifecycle.py::test_projection_failure_commits_and_next_recall_repairs`
- All cases in `tests/test_memory_transport.py`, `tests/test_memory_llm_bounds.py`,
  `tests/test_memory_learning.py`
- `tests/test_memory_interfaces.py::test_cli_build_closes_private_connections_it_opens`
- `tests/test_memory_interfaces.py::test_mcp_explicit_learning_awaits_cancellable_transport`

Result: **28 passed in 8.03s**.

Additionally ran a socket-free active-event-loop probe with the real `AsyncOpenAI` SDK and in-memory HTTPX
transports. Awaited one successful operation and one operation blocked indefinitely in a response read, with a
0.1-second deadline. Observed:

```text
active-loop blocked read: model_deadline: learning exceeded 60 seconds
active-loop success: {'ok': True}
cancelled/closed: [True] [True]
owned HTTP clients closed: [True, True]
remaining operation tasks: 0
```

The supplied gate summary at `2026-11-01T22:50:43-08:00` records **353 passed, 36 warnings**, coverage **90%**,
**51/51 requirements**, all five engines plus SQL Server integration passing, and passing lint/mypy/pyright/eval.
Its overall verdict is **FAIL solely because this review's original Python fences need formatting**.
That failed run is not used to approve the change. Ran the requested
`.venv\Scripts\python.exe -m ruff format docs\reviews\2026-11-02-agentic-memory.md`, then checked only that file:
**1 file already formatted**. At that point the parent owned the final full verification rerun and updated
evaluation/evidence record. This bounded recheck is complete; no further implementation review is pending
unless the snapshot changes again.

## Final disposition — approve

Read the final `build/evidence/summary.md`: **PASS**, timestamp **2026-11-01T22:56:59-08:00**, snapshot
**`b204e6553905 + 25 uncommitted file(s) (main)`**. The parent confirms no implementation changes since the
bounded recheck. Original finding severities and resolved statuses remain recorded above.

| Gate | Final evidence |
|---|---|
| lint | PASS; all checks passed |
| format | PASS; 123 files already formatted |
| mypy | PASS; no issues in 48 source files |
| pyright | PASS; 0 errors, 0 warnings |
| tests | PASS; 353 passed, 36 warnings in 144.33s; coverage 90% |
| eval | PASS; full 24/24, mean recall 1.00 |
| trace | PASS; 51/51 requirements; SQLite, DuckDB, PostgreSQL, MySQL and SQL Server passed, including SQL Server integration |

Parent reports both final BM25/fastembed evaluations remain 24/24 with unchanged KG ablations; these were not
rerun by the reviewer. The earlier inspected detailed after-eval numbers and bounded recheck proof remain above.

**Remaining gaps:** the parent classifies the 36 remaining warnings as pre-existing. Their diagnosis and
remediation remain parent-owned; this review does not claim a warning-free run or independently establish every
warning's allocation origin. The temporary-private-store closure regression passed both success/error cases.
Durable evidence/status updates remain parent-owned. After the final gates, this approval update changes only
the review document; its requested Ruff formatting does not change implementation.
