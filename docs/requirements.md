# Requirements

Every requirement has a stable ID. Tests prove requirements by carrying a marker such as
`@pytest.mark.req("REQ-KG-06")`; [scripts/verify.py](../scripts/verify.py) turns the markers and test outcomes
into the traceability matrix (`build/evidence/traceability.md`). Quality gates (`QA`) are proven by tool runs;
tests of the development tooling itself (verification script, agent hook) carry the gate they protect.

Rules (enforced by `tests/conftest.py` and `scripts/verify.py`):

- A test may only reference IDs listed here (above *Retired*); an unknown or retired ID stops the test run.
- Every `REQ-*` ID needs at least one passing test, otherwise verification fails.
- IDs are never reused. Retire a requirement by moving its row to *Retired* with the reason.
- A change in behavior updates the requirement text in the same pull request as the code and tests.

## Functional requirements

### Scan (facts)

| ID | Requirement | Proven by |
|---|---|---|
| REQ-SCAN-01 | `scan` records every table, view and column with types, primary/foreign keys, indexes, row counts and a data profile (null %, ranges, value dictionaries) in `catalog.json`. | tests |
| REQ-SCAN-02 | Columns that look personal are flagged `sensitive`; only statistics, never values, are stored for them. | tests |
| REQ-SCAN-03 | The scan scope can be narrowed with schema, include and exclude filters. | tests |
| REQ-SCAN-04 | Any SQLAlchemy dialect works; when reflection is missing or broken, metadata comes from `INFORMATION_SCHEMA`. Tested on SQLite, DuckDB, PostgreSQL, MariaDB and SQL Server. | tests (cross-engine) |

### Semantic model (knowledge)

| ID | Requirement | Proven by |
|---|---|---|
| REQ-SEM-01 | `semantic.yaml` adds business meaning (descriptions, synonyms, code values, glossary, metrics, examples) on top of the catalog; unknown tables or columns produce warnings, not failures. | tests |
| REQ-SEM-02 | Undeclared joins are inferred from key naming, and housekeeping columns repeated across many tables are hidden from search and context. | tests |
| REQ-SEM-03 | `draft` writes a complete `semantic.yaml` skeleton that keeps curated content and optionally fills gaps with LLM suggestions. | tests |
| REQ-SEM-04 | `build` regenerates the docs, `graph.json` and the search index from the source files alone. | tests |

### Retrieval

| ID | Requirement | Proven by |
|---|---|---|
| REQ-RET-01 | Search fuses SQLite FTS5 BM25 with dense-vector similarity using Reciprocal Rank Fusion. | tests |
| REQ-RET-02 | Literals in a question are linked to the exact stored values of the columns that contain them. | tests |
| REQ-RET-03 | The context pack contains SQL rules, value matches, knowledge-graph concepts, memories, definitions, verified examples, table cards and join paths; tables that contain a literal from the question are added without displacing retrieved tables. | tests |
| REQ-RET-04 | Join planning connects the chosen tables over declared, curated and inferred keys, adding bridge tables. | tests |
| REQ-RET-05 | On the AdventureWorks evaluation (`evals/retrieval_cases.yaml`), retrieval meets the gate defined for the embedder. | tests + eval |

### Memory

| ID | Requirement | Proven by |
|---|---|---|
| REQ-MEM-01 | Memories persist in `memories.jsonl`, are searchable immediately and can be forgotten. | tests |
| REQ-MEM-02 | Memories are validated before they are stored: a known kind, non-empty text, the verified SQL for `query` memories, and existing tables. | tests |

### Agentic memory (implementation contract)

[ADR 0012](design/adr/0012-bounded-source-linked-agentic-memory.md) specifies the schema, limits and interfaces.
These are new acceptance criteria, **not claims of implemented or verified behavior**. Legacy REQ-MEM-01/02
remain unchanged; the new memory lane does not confer database verification.

| ID | Requirement / acceptance criteria | Proven by (planned) |
|---|---|---|
| REQ-AMEM-01 | Caller-submitted conversations feed four distinct memory types: session-scoped working state, episodic experiences, semantic knowledge and procedural prose workflows. Persist sanitized source revisions, item revisions, lineage and lifecycle events in private `private/memory.sqlite3`, never solely in derived indexes. Reopen/rebuild preserves IDs, source history and archived revisions. Legacy `remember`/`forget`/`memories`/`list_memories`, `MemoryStore` and existing JSONL fixtures retain their signatures, outputs and deletion semantics; no implicit migration or dual-write. | lifecycle reopen/rebuild and unchanged legacy roundtrip/interface tests |
| REQ-AMEM-02 | Sanitize before persistence, prompt construction, indexing or echo: redact ADR-defined credentials and common PII plus caller-declared literal redactions; retain only sanitized originals. Reject malformed/oversize input without partial writes; do not log content, raw provider errors or redaction literals. Label transcripts, model output and recalled workflows untrusted data; never execute embedded SQL, tools or instructions, or install them as system/developer instructions. Disclose heuristic sanitization limits, local plaintext retention and caller responsibility. | redaction canaries, injection, validation and error/log capture tests |
| REQ-AMEM-03 | Support keyless sqlmem-side Copilot/MCP task → proposal save, local Ollama and existing Azure/OpenAI-compatible LLM configurations through one proposal schema and validator. Within the new memory lane only explicit `learn_conversation` / `memory learn --llm` invokes a configured model; no implicit calls on submit, recall, build, feedback or compaction and no fallback provider. Existing explicitly configured schema embedding behavior remains unchanged. Enforce ADR prompt/reply/attempt/deadline limits. Tests/development use deterministic injected stubs, no network or real models. | parameterized provider/client stubs, call counters, deadline and no-network tests |
| REQ-AMEM-04 | Automatically accept structurally valid inferred proposals without human approval. Same scoped key updates one item; latest committed valid revision wins only after optimistic concurrency checks. Preserve superseded content, provenance and conflict decisions; reject stale tasks, duplicate keys and invalid batches atomically. Exact retries are no-ops. Inferred content is visibly not database-verified and cannot overwrite catalog, curated semantics, graph or legacy memories. | conflict, stale/retry, transaction rollback and trust-label tests |
| REQ-AMEM-05 | Recall active working memory only for the supplied session, alongside relevant long-term items, with stable IDs, revision/type/trust labels and source references. Archive/history/source access is explicit and paginated; a previous revision can be restored as a new head without losing later history. Never promise lossless semantic summaries: sanitized submitted originals and source lineage remain retrievable. | session isolation, pagination, archive/source recall and restore/reopen tests |
| REQ-AMEM-06 | Compaction archives, never deletes, originals or revisions. Automatically enforce ADR active-item caps after mutations; explicit bounded compaction archives older working/episodic heads and records an exact revision manifest. Archived/superseded content leaves active recall but remains recoverable. Enforce per-call and store-size bounds; at capacity return an actionable error, never silently truncate, evict sources or run an autonomous cleanup daemon. | cap boundaries, deterministic archive ordering, manifest/recovery and storage-full tests |
| REQ-AMEM-07 | Helpful/unhelpful feedback changes bounded usefulness used only within agentic recall/archiving; correction feedback automatically creates a source-linked replacement revision. Repeated feedback is idempotent; stale corrections fail without writes. No feedback implicitly trains a model, rewrites schema knowledge or grants verification. | feedback ranking, correction, idempotency and provenance tests |
| REQ-AMEM-08 | Library, CLI and MCP expose the exact ADR submit/task/save/learn/recall/history/restore/feedback/compact operations, limits, errors and structured reports. MCP sees only content explicitly submitted/imported by its caller, not host chat history. Task/save needs no sqlmem API key; client instructions describe submission, automatic acceptance, recall and explicit archive/source recovery. Mutating tools declare writes; legacy tool behavior remains intact. | library/CLI/MCP parity, tool annotation and client-workflow contract tests |
| REQ-AMEM-09 | Agentic chunks use a separate private derived index and separate recall budget, not the existing schema/legacy index hit pool or table ranking. Context may append at most five agentic items within 8 KiB; it must retain existing schema hits, table/value/bridge selection and verified-example sections. Private sources/content never enter generated tracked docs/graph. No lower retrieval gates: full hits AND table recall in `evals/retrieval_cases.yaml` stay at least current thresholds, including with adversarial memory saturation. | schema-hit equality and saturation tests; before/after BM25 and cached KB-embedder eval, KG ablation |

### Safety

| ID | Requirement | Proven by |
|---|---|---|
| REQ-SAFE-01 | Only a single comment-free `SELECT`/`WITH` statement without write or side-effect keywords passes the SQL guard; engine-specific quoting tricks are rejected. | tests |
| REQ-SAFE-02 | Database sessions are read-only where the engine supports it; results are row-capped and every query is rolled back. | tests (cross-engine) |
| REQ-SAFE-03 | Every query has a time limit; a timeout leaves the connection usable, and MCP tools stay within their time budget. | tests |

### LLM access

| ID | Requirement | Proven by |
|---|---|---|
| REQ-LLM-01 | The model is resolved from the command line, then environment, then the KB config; Azure OpenAI (Entra ID or key), OpenAI, Ollama and OpenAI-compatible servers are supported. | tests |
| REQ-LLM-02 | JSON replies are extracted robustly, and request parameters that a model rejects are dropped and retried. | tests |
| REQ-LLM-03 | `sqlmem llm` saves and tests the configuration without storing secrets. | tests |

### Knowledge graph

| ID | Requirement | Proven by |
|---|---|---|
| REQ-KG-01 | LLM-proposed entities and relations are validated against the schema and the data: filters run, joins are measured, cardinality is computed. | tests |
| REQ-KG-02 | Imports merge into the existing graph unless `replace` is set; `check` keeps broken edits so they can be fixed. | tests |
| REQ-KG-03 | Large schemas are split into tasks, and later tasks reuse names defined earlier. | tests |
| REQ-KG-04 | Entities have single or composite keys (the primary key by default); explicit keys are checked for uniqueness. | tests |
| REQ-KG-05 | Relations can pin their join with `via` columns (also when two keys point to the same table) or state an explicit `on` join for tables without a declared foreign key. | tests |
| REQ-KG-06 | A polymorphic reference (`polymorphic: {column, type_column, targets}`) becomes one verified relation per target that reloads and feeds join planning; mistakes produce actionable errors. | tests |
| REQ-KG-07 | Join paths that fan out through a shared table are rejected, and ambiguous direct links are reported. | tests |
| REQ-KG-08 | Verification is time-bounded: items that cannot be checked in time are saved unverified, not dropped. | tests |
| REQ-KG-09 | The graph is used everywhere: docs, `graph.json`, search chunks and context packs. | tests |
| REQ-KG-10 | The CLI exports tasks, imports replies and re-checks the saved graph. | tests |

### Interfaces

| ID | Requirement | Proven by |
|---|---|---|
| REQ-MCP-01 | The MCP server exposes context, search, describe, list, join-path, memory, knowledge-graph and `run_sql` tools, and returns actionable errors. | tests |
| REQ-CLI-01 | The CLI covers scan, build, search, context, memory and query end to end. | tests |

### Chart visualization

[ADR 0011](design/adr/0011-bounded-offline-chart-visualization.md) defines the interfaces, chart/mapping matrix and
limits. Marked chart, MCP, canvas, skill and vendor tests provide traceability; browser checks and package
verification complement those tests. See the change's evidence record for measured results and remaining gaps.

| ID | Requirement / acceptance criteria | Proven by |
|---|---|---|
| REQ-CHART-01 | One shared Python renderer accepts typed columns/rows and a discriminated chart type/mapping. Reject duplicate column names, ragged rows, incompatible mappings, unsupported scalar types, non-finite/out-of-range numbers and limit violations before writing. Enforce ADR 0011 caps without silent sampling, aggregation or chart substitution; preserve input order except documented structural normalization. | chart schema, normalization and boundary tests |
| REQ-CHART-02 | Support the ADR's bounded native ECharts chart/mapping matrix: bar/column, line/area/time, pie/donut, scatter/bubble, heatmap, treemap/sunburst, candlestick, boxplot, radar, funnel, gauge, graph and sankey. Expose a typed, family-specific allowlist of presentation options; reject raw ECharts options, unknown keys and executable/callback/resource-URL/plugin fields. Markup-like or URL-like data strings remain inert text. Validate hierarchy, edge and financial invariants with actionable errors. Highcharts parity is not required. | parameterized family/mapping and negative-option tests |
| REQ-CHART-03 | MCP `create_chart(source, spec)` accepts exactly one SQL or supplied-row source. SQL uses existing `run_select`/`check_readonly`, engine timeout, rollback and the smaller of requested/server/chart row caps; rows mode needs no engine and never queries. SQL truncation is exact; supplied rows declare complete/truncated/unknown. Both artifact and response report plotted count, truncation status and warnings; never imply that capped or unknown results are complete or issue an automatic count query. The tool declares local writes, not read-only/idempotent behavior. | MCP tests and the five-engine end-to-end chart scenario |
| REQ-CHART-04 | Generate one standalone HTML file usable offline via `file://` and the viewer, with embedded pinned Apache ECharts and optional echarts-gl, template, styles and data. Ship reviewed vendor versions, SHA-256 manifest, upstream licenses/NOTICE and bundled dependency notices in package assets and HTML. No CDN, remote fonts, telemetry, dynamic installation or new Python dependency; wheel and source distribution contain all required assets. | vendor/hash/license tests; wheel/sdist, extracted-wheel and offline browser checks |
| REQ-CHART-05 | Write only private, Git-ignored `build/charts` artifacts using generated IDs, contained paths and no overwrite of existing/user files. Reject known/declared sensitive and unclassified input columns; retain only mapped non-sensitive data, not SQL, credentials or unused columns. Treat classification declarations as a contract, not SQL-lineage/DLP proof. Escape data/labels, prohibit executable options and external resource requests, and apply the ADR CSP. Do not index, remember, upload or send chart data to an LLM; errors/logs must not echo rows, SQL or viewer tokens. | privacy, path/reparse, XSS and CSP tests; browser network-denial checks |
| REQ-CHART-06 | The shared HTML has a polished responsive light/dark layout, title/units, chart-appropriate tooltips, legend toggles, applicable zoom/pan, reset and local PNG download. Provide keyboard-operable controls, visible focus, accessible summary and a bounded data table; communicate empty data, partial/unknown results and render failures without hiding warnings. Controls work identically standalone and in canvas; no second chart renderer. | HTML/control and JavaScript behavior tests; browser interaction, export and visual checks |
| REQ-CHART-07 | Optional explicit 3D supports only scatter3D, bar3D and data-grid surface via the pinned echarts-gl bundle and the same typed API/limits. Nonempty surfaces require at least a complete 2x2 grid. Reject equations, arbitrary shaders/textures and unsupported 3D families. A disabled plugin, missing WebGL or context loss produces an actionable warning with the data table retained; never silently substitutes a 2D chart or downloads a dependency. | 3D mapping/enablement and CSP-build tests; browser WebGL success/failure checks |
| REQ-CHART-08 | A project-scoped Copilot canvas is only an opt-in local Node HTTP viewer of one generated HTML artifact. Bind `127.0.0.1:0`, use finite idle/lifetime/request limits, bounded connections, strict Host/route/action shapes and artifacts constrained to a canonical `build/charts` root. GET/HEAD `/` and `/download` only: no arbitrary paths, filesystem listings, SQL/render endpoints, CORS, credentials in URLs or host APIs. Validate raw show/refresh/download action inputs and preserve the chart CSP, uncached. Reject traversal, encoded separators, symlink escapes, unknown IDs, hosts, actions and HTTP write methods. | Node HTTP/action/path/lifecycle tests via pytest; live canvas SDK smoke checks |
| REQ-CHART-09 | A repository-local chart skill operates only on explicit user visualization requests: reuse retrieved rows when available, otherwise obtain SQL context and query through `create_chart`; choose supported mappings, classify data, disclose truncation and request clarification instead of inventing semantics. It returns the private HTML artifact and optionally opens the project canvas; never installs global skills, silently charts ordinary answers, uploads data or treats row text as instructions. | skill discovery/workflow contract test and explicit visualization demo |

## Quality gates

| ID | Requirement | Proven by |
|---|---|---|
| QA-LINT | `ruff check` and `ruff format --check` report nothing; the agent hook formats only files an edit tool changed. | verify: lint, format |
| QA-TYPES | `mypy` (strict) and `pyright` (the engine behind Pylance) report no errors or warnings. | verify: mypy, pyright |
| QA-TESTS | All tests pass on Python 3.10 to 3.13, on Linux and Windows. | verify: tests, CI matrix |
| QA-COVERAGE | Line and branch coverage of `sqlmem` stays at or above the threshold in `scripts/verify.py`. | verify: tests |
| QA-ENGINES | The cross-engine scenario (`test_end_to_end_on_engine`) passes on SQLite, DuckDB, PostgreSQL, MariaDB and SQL Server. | CI engines job, `scripts/engines.ps1` |
| QA-TRACE | Every active requirement is proven by at least one passing test; retired IDs are neither required nor accepted. | verify: traceability |

## Retired

None yet.
