# Design

| Document | Topic |
|---|---|
| [retrieval.md](retrieval.md) | how a question becomes a context pack: chunks, hybrid search, ranking, value linking, join planning |
| [knowledge-graph.md](knowledge-graph.md) | entities and relations, planning and verification, keys, `via`/`on`/polymorphic |
| [security.md](security.md) | threat model and controls: read-only access, time limits, privacy, secrets, supply chain |
| [duckdb-scalable-analytics-architecture.md](duckdb-scalable-analytics-architecture.md) | proposed standalone AWS analytics platform for 100 TB and 1,000 connected users: architecture, UML, scheduling, sizing and deployment plan; not implemented by sqlmem |
| [duckdb-azure-aks-service-fabric.md](duckdb-azure-aks-service-fabric.md) | Azure companion: alternative AKS Linux and managed Service Fabric Windows architectures, sizing, deployment examples, identity and scaling boundaries |

## Architecture decision records

| ADR | Decision | Status |
|---|---|---|
| [0001](adr/0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](adr/0002-sqlalchemy-for-all-engines.md) | Talk to every database through SQLAlchemy (with `INFORMATION_SCHEMA` fallback) | Accepted |
| [0003](adr/0003-knowledge-base-as-files.md) | Keep the knowledge base as plain files in git | Accepted |
| [0004](adr/0004-hybrid-retrieval.md) | Hybrid retrieval: BM25 and vectors fused with RRF | Accepted |
| [0005](adr/0005-read-only-defense-in-depth.md) | Read-only access in depth | Accepted |
| [0006](adr/0006-llm-proposes-sqlmem-verifies.md) | The LLM proposes, sqlmem verifies the knowledge graph | Accepted |
| [0007](adr/0007-composite-keys-and-polymorphic-relations.md) | Composite keys, explicit joins and polymorphic relations | Accepted |
| [0008](adr/0008-time-bounded-verification.md) | Time-bounded verification and queries | Accepted |
| [0009](adr/0009-value-matches-do-not-displace-retrieved-tables.md) | Value matches add tables; they never displace retrieved tables | Accepted |
| [0010](adr/0010-evidence-driven-development.md) | Evidence-driven development with requirement traceability | Accepted |
| [0011](adr/0011-bounded-offline-chart-visualization.md) | Bounded user-requested offline ECharts, guarded MCP tool and project canvas | Proposed |
| [0012](adr/0012-bounded-source-linked-agentic-memory.md) | Bounded private source-linked agentic memory; automatic revisions and archive-only compaction; supersedes 0003 only for new private memory | Proposed |
| [0013](adr/0013-declare-httpx-transport-dependency.md) | Declare the existing HTTPX transport dependency in the LLM extra | Proposed |

New ADR: copy [the template](adr/0000-template.md) (skill `write-adr`).
