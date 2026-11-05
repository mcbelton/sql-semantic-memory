# Status and handoff

Living document: **read it at the start of a session, update it before the session ends** (AGENTS.md rule 10).
Last updated: 2026-11-05 (UTC), after moving to Python 3.11-3.15 and fixing the first public CI failures.

## Where things stand

- **Python support**: Python 3.11 is the minimum; CI tests 3.11-3.14 on Ubuntu and latest stable 3.15.2 on
  Ubuntu quality gates, Windows and macOS; the cross-engine job uses 3.14 until pyodbc publishes 3.15 wheels.
  On 3.15, `local` and `mssql` extras are unavailable ([ADR 0014](design/adr/0014-python-311-minimum-and-315-primary.md)).
  Full local gates pass on 3.11.9 and 3.15.2: 349 passed/1 skipped, 88% coverage, 51/51 requirements, BM25 24/24.
  The viewer test now proves active sockets are destroyed promptly and accepts macOS resets
  ([evidence](evidence/2026-11-05-python-311-315-ci-fixes.md),
  [review](reviews/2026-11-05-python-311-315-ci-fixes.md)).
  [CI run 41965908923](https://github.com/mcbelton/sql-semantic-memory/actions/runs/41965908923) is green on `fa9b0bb`:
  8/8 jobs, including macOS/3.15 and all five database engines.
- **Public**: [mcbelton/sql-semantic-memory](https://github.com/mcbelton/sql-semantic-memory), licensed under
  [MIT](../LICENSE); GitHub detects `MIT`, and private vulnerability reporting is enabled.
  `origin` is `https://github.com/mcbelton/sql-semantic-memory.git`. The recreated repository starts from scrubbed
  root commit `06577ce`; older commit IDs in records are local provenance.
  The [first public CI run](https://github.com/mcbelton/sql-semantic-memory/actions/runs/41962266224) failed on
  Ubuntu/3.10 and macOS; those failures are addressed by the Python support change above. See the
  [publication evidence](evidence/2026-11-05-github-publication.md) for commands, results and limitations.
- Reviewed the uncommitted VS Code migration of six prompts to skills:
  [changes requested](reviews/2026-11-03-prompt-to-skill-migration.md). Static checks found six valid headers
  and unchanged bodies, but all nine relative references are broken and all six custom-agent selections
  were removed. The migration remains unfixed; rebase the links and preserve agent routing before accepting it.
  Live VS Code invocation and full runtime gates were not run for this customization-only review.
- Added the [Azure AKS/Service Fabric companion](design/duckdb-azure-aks-service-fabric.md): AKS Linux and
  Standard managed Service Fabric Windows alternatives, Azure services/identity, explicit hosting overhead,
  manifests, command examples, scaling and acceptance guidance.
  Five diagrams parsed/rendered; five Kubernetes objects, two XML manifests, five PowerShell snippets and
  sizing/governance arithmetic passed focused checks
  ([evidence](evidence/2026-11-03-duckdb-azure-documentation.md),
  [review and author response](reviews/2026-11-03-duckdb-azure-documentation.md)).
  No Azure resources were provisioned or load-tested. The owned diagram helper is stopped.
  The review found no Azure-documentation defect but withheld approval after its broader full verification
  failed the memory cancellation test; the author retained that finding under the docs-only scope exception.
  Runtime gates were not green in that review: tests reported 1 failed/348 passed/1 skipped, coverage 88%,
  traceability 50/51 with `REQ-AMEM-03` unproven. No memory/runtime files were changed by this documentation task.
  Final local documentation checks passed 99 relative links/anchors across eight files and whitespace checks;
  Azure resources, SDK/API/schema validation and workload measurements remain future implementation work.
- Added a standalone [DuckDB AWS architecture proposal](design/duckdb-scalable-analytics-architecture.md)
  based on the supplied 100 TB/1,000-user scaling discussion: system/component/UML diagrams, query scheduling,
  worker sizing, Kubernetes examples, security and reliability boundaries, costs and deployment acceptance plan.
  All eight Mermaid diagrams parsed and rendered as SVGs; two YAML examples and capacity/cost arithmetic
  passed focused checks. Independent review approved with no actionable findings
  ([evidence](evidence/2026-11-03-duckdb-architecture-documentation.md),
  [review](reviews/2026-11-03-duckdb-architecture-documentation.md)).
  This is documentation, not an implemented `sqlmem` feature or accepted infrastructure decision.
  Cloud deployment, current pricing, load/failure tests and production SLOs remain unverified; full Python
  gates were not rerun for this Markdown-only change. The temporary loopback diagram server is stopped.
- Private agentic memory is implemented and independently approved: working/session, episodic, semantic and
  procedural records; sanitized conversation sources; automatic inferred updates with revision history;
  outcome feedback; reversible archive compaction, history and restore. CLI/MCP/library share nine operations.
  Final verification: all gates PASS, 353 tests, 90% coverage, 51/51 requirements, all five engines passed;
  BM25 and fastembed retrieval remain 24/24. The 36 resource warnings and other limitations are documented
  ([evidence](evidence/2026-11-02-agentic-memory.md), [review](reviews/2026-11-02-agentic-memory.md),
  [ADR 0012](design/adr/0012-bounded-source-linked-agentic-memory.md)).
  Feature changes are included in the new GitHub publication snapshot; no new conversation memories were added
  to the user's KB.
  Final evidence was checked against all seven generated gate rows and nine new requirement rows; final
  documentation lint/format and whitespace checks passed. Test servers and temporary viewers are stopped.
- Corrected the scan sequence diagram's literal semicolon using Mermaid's `#59;` entity. All six runtime-flow
  diagrams passed parsing and browser SVG rendering; the original scan label is preserved
  ([evidence](evidence/2026-11-01-mermaid-runtime-flows.md),
  [review and author response](reviews/2026-11-01-mermaid-runtime-flows.md)). Markdown-only change:
  no full Python gates rerun. The review's request for full gates was answered with this docs-only limitation.
- sqlmem 0.2.0 is complete and verified locally: every gate passes with all five engines on commit `b990f05`
  ([evidence](evidence/2026-10-30-repository-baseline.md), [review](reviews/2026-10-30-repository-hardening.md)).
- New chart feature: project `sqlmem-chart` skill, `create_chart` MCP tool, offline ECharts HTML and a
  matching project canvas with optional 3D. Final gates: 248 tests, 89% coverage, retrieval 24/24,
  42/42 requirements, all five engines passed
  ([evidence](evidence/2026-10-30-chart-visualization.md), [review](reviews/2026-10-30-chart-visualization.md)).

## Next steps (in order)

1. **Repair the prompt-to-skill migration before treating it as approved.**
   Rebase the nine broken relative references and preserve the six custom-agent selections documented in the
   [review](reviews/2026-11-03-prompt-to-skill-migration.md). Those pre-existing customization findings are not
   changed by publication or the Python support update.

2. **Move Python 3.15 extras when upstream wheels exist.**
   When onnxruntime and pyodbc publish 3.15 wheels, move the engine job to 3.15 and remove the `local`/`mssql`
   README limitation. Keep CI green; if the earlier intermittent cancellation failure recurs, preserve the
   requirement and use the [review](reviews/2026-11-03-duckdb-azure-documentation.md) as the starting point.

3. **Restart the sqlmem MCP server** in VS Code to expose the new memory lifecycle tools (and `create_chart`
   for processes predating charts). Follow the [private memory workflow](../README.md#private-source-linked-agentic-memory):
   submit selected sanitized turns, request `memory_task`, and save the agent's inferred proposals with
   `save_memory`; alternatively explicitly call configured-model learning. Supply a session for working
   memory, and use feedback/history/archive recall/restore as needed. MCP cannot see arbitrary host chats.
   No separate sqlmem API key is needed for the host-agent task/save route.
   Stop the server before any `pip install -e`, which rewrites the locked `sqlmem.exe`.

## Local context (this machine)

| What | Where |
|---|---|
| Repository | `D:\dev\sql-semantic-memory`, its own git repository (`D:\dev` holds several repositories and is never committed) |
| Python | `.venv` (3.14.7); `build\venv311` (3.11.9 minimum) and `build\venv315` (3.15.2 primary, per-user install under `%LOCALAPPDATA%\Programs\Python\Python315`) with `mcp,llm,duckdb,dev` |
| Example database | Expected at `D:\dev\sql-semantic-memory\dbs\AdventureWorks2025.db` (ignored; not verified present on this machine) |
| Test database servers | `.\scripts\engines.ps1 start`, `env`, `stop`; binaries cached in `%LOCALAPPDATA%\sqlmem-engines` |
| Commit identity | repository-local: `Belton Albert <8398342+mcbelton@users.noreply.github.com>` |
| VS Code | open this folder (`.vscode/mcp.json` starts the MCP server for it) or `D:\dev\dev.code-workspace` |

## Recent decisions

- [ADR 0009](design/adr/0009-value-matches-do-not-displace-retrieved-tables.md): value-matched tables are added after
  retrieved tables (eval back to 24/24).
- [ADR 0010](design/adr/0010-evidence-driven-development.md): evidence-driven development with requirement
  traceability.
- Review finding 7: the knowledge-graph verification budget uses `time.perf_counter()`.
- Both `D:\dev\.vscode\mcp.json` and the project's `.vscode/mcp.json` now point directly at the local `dbs` copy.
  The project configuration no longer uses a database input prompt, so cached inputs cannot select the old file.
  Both configurations passed fresh MCP `run_sql` checks (19,820 customers); all verification gates passed
  ([evidence](evidence/2026-10-30-mcp-database-location.md)).
  Restart `adventureworks-memory` in VS Code to apply the change.
- The generated catalog retains its original scan provenance. Pass `--db dbs\AdventureWorks2025.db` explicitly
  for data checks, as shown in the README; no rescan or knowledge-graph rebuild is needed just to change the MCP path.
- [ADR 0011](design/adr/0011-bounded-offline-chart-visualization.md): one controlled offline ECharts renderer,
  private `<kb>\build\charts` artifacts and a loopback-only project canvas. GL uses a reviewed reproducible
  CSP-only vendor patch; no Python runtime dependency was added. HTML contains data and must stay private.
- Canvas `sqlmem-chart` is loaded in this session and was verified with real 2D/3D AdventureWorks examples,
  refresh/show/download and reopening the same instance. Test database servers are stopped.
