# Changelog

All notable changes. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
semantic versioning (minor bumps may break while < 1.0).

## [Unreleased]

### Added
- MIT [license](LICENSE) for public distribution; package metadata declares the license and includes its text.
- [Azure AKS and Service Fabric companion designs](docs/design/duckdb-azure-aks-service-fabric.md) for the
  standalone DuckDB analytics proposal, including deployment examples, Azure identities, resource governance
  and separate instance/node scaling; documentation only, no cloud resources provisioned.
- Standalone proposed [DuckDB analytics architecture on AWS](docs/design/duckdb-scalable-analytics-architecture.md)
  for 100 TB and 1,000 connected users, with architecture/UML diagrams, worker sizing, scheduling,
  Kubernetes examples, cost assumptions and a production acceptance plan; no runtime behavior changed.
- Bounded private source-linked working/episodic/semantic/procedural memory with SQLite revision history,
  sanitized originals, automatic key-based acceptance/replacement, outcome feedback and reversible archiving.
  Nine library/CLI/MCP operations support keyless caller task/save and explicit Ollama/Azure/OpenAI-compatible
  learning with memory-specific request/reply/deadline limits. Separate BM25 recall/context budget preserves
  schema/legacy retrieval; private paths are ignored. Legacy JSONL behavior is unchanged.
- Project `sqlmem-chart` skill and `create_chart` MCP tool for private offline ECharts visualizations from
  classified retrieved rows or guarded SQL, with a matching project canvas, interactive controls and optional 3D.
- Pinned Apache ECharts and ECharts GL assets with bundled licenses; no additional Python runtime dependency.

### Changed
- The canonical public repository is now [mcbelton/sql-semantic-memory](https://github.com/mcbelton/sql-semantic-memory);
  security reports use GitHub private vulnerability reporting.
- The VS Code AdventureWorks MCP configuration uses the local `dbs\AdventureWorks2025.db` copy directly instead
  of prompting for a database path. Place the database in the Git-ignored `dbs/` folder before starting the server.

### Fixed
- Declare HTTPX directly in the `llm` extra so clean installs retain the memory identity transport when newer
  OpenAI/MCP SDKs depend on `httpx2` instead ([ADR 0013](docs/design/adr/0013-declare-httpx-transport-dependency.md)).
- Private memory projection publication now follows the authoritative commit, with atomic index generations;
  capacity rollbacks cannot poison later lexical recall. Memory learning cancels in-flight response consumption
  at its absolute deadline, and large catalogs receive bounded table hints with explicit omissions.
- Escape a semicolon in the scan sequence diagram so the runtime flows render in Mermaid Markdown previews.

## [0.2.0] - 2026-10-30

### Added
- Knowledge graph: composite entity keys, explicit `on` joins, `polymorphic` references expanded into one verified
  relation per target, rejection of fan-out join paths, per-query time limits and an overall verification budget
  (items that run out of time are saved unverified).
- `KnowledgeBase.close()` to release the search index.
- Retrieval evaluation (`python -m evals.run_retrieval`) with per-embedder gates; the BM25 gate runs in every test run.
- Evidence-driven development: requirement IDs with traceable tests, `scripts/verify.py` (ruff, mypy strict, pyright,
  pytest + coverage, eval, traceability → `build/evidence/`), CI for Python 3.10–3.13 on Linux, Windows and macOS
  plus a cross-engine job (PostgreSQL 18, MariaDB 11.4, SQL Server 2022), `scripts/engines.ps1` and `compose.yaml`.
- Agent team, skills, prompts, instructions and a formatting hook for GitHub Copilot; architecture, design, ADRs,
  testing and process documentation.

### Changed
- Context packs: tables that contain a literal from the question are added after the retrieved tables instead of
  displacing them (ADR 0009); restores 24/24 on the AdventureWorks eval for BM25 and fastembed.
- Fully typed package (`py.typed`), checked with mypy `--strict` and pyright; ruff lint and formatting.
- The interactive knowledge-graph HTML template moved to `sqlmem/assets/knowledge-graph.html`.
- Requires `mcp>=2.0` for the MCP extra. The `dev` extra includes `mcp`, `llm` and `duckdb` and pins the gate tools.
- Optional packages (`fastembed`, `pyodbc`) are imported dynamically, so type checking is clean with any set of extras.

### Fixed
- The knowledge-graph verification budget is measured with `time.perf_counter()`; `time.monotonic()` ticks only every
  15.6 ms on Windows before Python 3.13, so budgets could overrun.

## [0.1.0]

- Scan, semantic model, hybrid search, context packs, memories, MCP server, read-only guard, multi-engine support,
  LLM configuration and the first knowledge-graph generation.
