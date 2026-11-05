# Data model: the knowledge-base folder

A knowledge base is one folder. Existing public source files are text-based and reviewed in git; their indexes
and rendered views can be rebuilt with `sqlmem build` (ADR 0003). Proposed ADR 0012 introduces a separate private
authoritative lifecycle store: it is **not** derived, must be backed up and must never be committed.

```text
kb/<name>/
├── catalog.json            facts            (sqlmem scan)                     committed
├── semantic.yaml           knowledge        (humans, draft --llm, Copilot)    committed, curated
├── knowledge_graph.yaml    knowledge graph  (sqlmem graph / MCP, verified)    committed, curated
├── memories.jsonl          memory           (remember / forget)               committed
├── sqlmem.json             settings         (embedder, LLM spec; no secrets)  committed
├── graph.json              derived          (build)                           committed for browsing
├── docs/                   derived          (build): README, tables/*.md,     committed for browsing
│                                             knowledge-graph.md/.html
├── index.db                derived          (build): search index             NOT committed
└── private/                proposed ADR 0012: ignored, private, plaintext
    ├── .gitignore          created before content, ignores all private files
    ├── memory.sqlite3      AUTHORITATIVE sanitized sources/revisions/events    NOT committed
    └── memory-index.db     derived local BM25 current-head projection          NOT committed
```

## `catalog.json` (facts)

| Key | Content |
|---|---|
| `version`, `generated_at`, `duration_s`, `options` | provenance of the scan (scan options used) |
| `source` | `dialect`, `driver`, `server`, `server_version`, `database`, `path` (SQLite) and `url` rendered **without password** (`describe_source`) |
| `objects[]` | one per table/view: `fqn`, `schema`, `name`, `sql_name`, `type`, `comment`, `row_count`, `row_count_exact`, `primary_key`, `foreign_keys[]`, `unique`, `indexes[]`, `columns[]`, `profile_meta` |
| `objects[].columns[]` | `name`, `sql_name`, `type`, `kind`, `nullable`, `default`, `identity`, `computed`, `comment`, `sensitive`, `profile` (`null_pct`, `non_null`, `distinct`, `min`, `max`, `avg`, `values` = value dictionary with counts, `examples`) — no `values` or `examples` for sensitive columns |
| `routines[]` | stored procedures and functions (when the engine exposes them) |
| `errors[]` | per-stage problems (`stage`, `error`); the scan continues past them |

## `semantic.yaml` (curated knowledge)

```yaml
database: {name, description, dialect_notes: [...]}          # notes are injected into every context
domains: {Sales: "...", ...}
tables:
  Sales.SalesOrderHeader:
    description: ...
    synonyms: [orders, sales]
    grain: one row per order
    domain: Sales
    notes: [...]                                               # SQL gotchas
    hidden: false
    columns:
      Status: {description: ..., values: {1: In process, 5: Shipped}, sensitive: false}
relationships: [{from: a.col, to: b.col, condition: ...}]      # extra or conditional joins
glossary: [{term, definition, tables}]
metrics: [{name, synonyms, definition, sql}]
examples: [{question, sql, notes, tables}]                     # verified queries
```

A bare string is accepted wherever a mapping with only a description is expected.

## `knowledge_graph.yaml`

```yaml
generated: {...}                    # provenance of the last generation (model, time, report)
entities:
  - name: Store                     # business concept
    kind: core | role | event | reference
    description: ...
    synonyms: [reseller]
    table: Sales__Store
    filter: "PersonType = 'SC'"     # optional subset of the table
    key: [BusinessEntityID]         # default: primary key; composite allowed
    label: [Name]
    is_a: Customer                  # optional parent entity
    attributes: [...]
    rows: 701                       # measured
relations:
  - subject: Store
    predicate: has_contact
    object: Store Contact
    description: ...
    via: [Person__BusinessEntityContact.BusinessEntityID]  # or `on:` / `polymorphic:`; optional `condition:`
    cardinality: M:N                # measured
    join: "FROM ... JOIN ..."       # generated, executed and measured
    verified: {pairs: 753, unmatched: 0, cardinality: M:N}
```

## `memories.jsonl`

One JSON object per line: `id`, `kind` (`fact`, `rule`, `preference`, `correction`, `query`), `text`, `question`,
`sql`, `tables`, `created_at`, `source` (`cli`, `mcp`).

## `index.db` (SQLite, derived)

| Table | Content |
|---|---|
| `meta` | embedder spec, generation counter |
| `chunks` | `rid`, `id` (`table:…`, `column:…`, `entity:…`, `memory:…`), `kind`, `ref`, `title`, `text`, `keywords`, `tables` (JSON), `payload` (JSON), `hash` |
| `chunks_fts` | FTS5 over `title`, `text`, `keywords` (`porter unicode61 remove_diacritics 2`) |
| `vectors` | `rid`, content `hash`, `vec` (float32 blob) — reused when the hash is unchanged |

## Proposed private lifecycle schema (ADR 0012)

`memory.sqlite3` version 1 has `sources` (conversation ID/revision, sanitized messages/hash/session/redaction
metadata), `items` (stable `am_` ID, scoped type/key, head revision), immutable `revisions` (text, prose steps,
tables, active/archive status, origin, previous/restored-from revision), `lineage` (revision → source/message
indices), `events` (commit sequence, feedback, retry reports and exact archive manifests), and `meta`
(schema/index generation). See [ADR 0012](../design/adr/0012-bounded-source-linked-agentic-memory.md) for exact
columns, bounds, uniqueness and transaction rules. No content is implicitly copied to/from `memories.jsonl`.

Working items require a session; episodic, semantic and procedural items are KB-scoped. All are inferred, not
database-verified. Restore/archive append revisions, never remove originals; source edits append source
revisions. Feedback is an event plus sanitized source; correction also appends a content revision. No automatic
deletion or lossy-only source replacement. At the 1 GiB store ceiling writes stop with recovery advice.

`memory-index.db` uses existing `Index` chunk/FTS tables with no embedder; current heads are projected.
Type/session/status kinds filter eligibility before ranking: archived heads are only eligible on explicit
archive recall, never in the active context. Superseded versions and transcripts are not indexed.
Private generation mismatch triggers rebuild; neither derived index is authoritative. Original transcript
recall/history reads the lifecycle store, not FTS. Back up `memory.sqlite3` consistently via SQLite, including
its history; ignore all private SQLite journals/sidecars. Sanitization is heuristic and local storage is not
encrypted. Private content never enters generated tracked documents or `graph.json`.

## `sqlmem.json`

`{"embedder": "fastembed:BAAI/bge-small-en-v1.5", "llm": "azure-openai:<deployment>", "llm_base_url": ...}` —
names and endpoints only; keys come from the environment (`AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`) or Entra ID.
