# sqlmem — semantic knowledge + long-term memory for an entire SQL database

Repository: [mcbelton/sql-semantic-memory](https://github.com/mcbelton/sql-semantic-memory). License: [MIT](LICENSE).

For a standalone infrastructure design, see [Scalable DuckDB analytics on AWS](docs/design/duckdb-scalable-analytics-architecture.md):
architecture, component/UML diagrams, query flow, worker sizing and deployment planning for 100 TB and
1,000 connected users. This is a proposed platform, not a feature implemented by `sqlmem`.
The [Azure companion](docs/design/duckdb-azure-aks-service-fabric.md) covers AKS and Service Fabric cluster
architectures and deployment guidance.

`sqlmem` turns a whole database into something an AI assistant can actually *understand*: what every table
means, how tables join, what the codes and flags stand for, which business metrics exist, which queries are
known to be correct — and it **keeps learning** from verified answers and corrections.
It works with any SQL database that has a SQLAlchemy driver (see [Supported databases](#supported-databases)) and
serves the knowledge to GitHub Copilot (or any agent) through an **MCP server**.

```text
                 scan (read-only)                      build                         serve
  SQL database ───────────────────▶ catalog.json ──┐                       ┌──▶ CLI:  context / search / table / path
                   schema, keys,      (FACTS)      │   docs/ (knowledge    │
                   row counts, data                ├─▶  cards, ER, graph   ├──▶ MCP:  get_sql_context, describe_table,
                   profile, value                  │   views) graph.json   │          get_knowledge_graph, run_sql,
                   dictionaries                    │   index.db (BM25 +    │          remember / forget, ...
  humans / LLM ───────────────────▶ semantic.yaml ─┤    dense vectors)  ───┘
                                    (KNOWLEDGE)    │
  LLM / Copilot ── sqlmem graph ──▶ knowledge_graph.yaml (ENTITIES + RELATIONS, verified against the data)
  agents / users ── remember ─────▶ memories.jsonl ┘
                                    (MEMORY)
```

| Layer | File | Produced by | Contains |
|---|---|---|---|
| **Facts** | `catalog.json` | `sqlmem scan` (automatic) | every table/view/column, types, PK/FK, indexes, row counts, null %, ranges, value dictionaries, DB comments (`MS_Description`), stored procedures |
| **Knowledge** | `semantic.yaml` | you, `sqlmem draft --llm`, or Copilot | business descriptions, synonyms, code meanings (`1 = Shipped`), SQL gotchas, extra/conditional joins, glossary, metric definitions, verified example queries |
| **Knowledge graph** | `knowledge_graph.yaml` | `sqlmem graph` (an LLM or Copilot proposes, sqlmem verifies) | business entities (Customer, Reseller, Sales Order ...) mapped to tables + filters, and named relations between them with verified joins |
| **Memory** | `memories.jsonl` | `remember` (CLI or MCP, e.g. by Copilot) | learned facts, rules, preferences, corrections, verified question → SQL pairs |
| **Private agentic memory** | `private/memory.sqlite3` | explicitly submitted conversations + caller/model proposals | sanitized source revisions, inferred working/episodic/semantic/procedural memory, lineage, feedback and reversible archives |

`docs/`, `graph.json`, `index.db` and `private/memory-index.db` are derived and can be regenerated with
`sqlmem build`. **`private/memory.sqlite3` is authoritative, not disposable.**

## Quick start (AdventureWorks2025, already built in `kb/adventureworks2025`)

Clone and install:

```powershell
git clone https://github.com/mcbelton/sql-semantic-memory.git
cd sql-semantic-memory
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[local,mcp,llm,duckdb,dev]"
```

The knowledge base is committed except its derived search index: after cloning, run
`sqlmem build --kb kb\adventureworks2025` once (the MCP server does this automatically). Commands that touch data
(`query`, `validate`, `graph --check`, `scan`) need the AdventureWorks2025 SQLite database. Place a local copy in
`dbs\AdventureWorks2025.db`; database files in `dbs/` are ignored by Git and are not committed.

```powershell
cd D:\dev\sql-semantic-memory
$kb = "kb\adventureworks2025"
$db = "dbs\AdventureWorks2025.db"

.\.venv\Scripts\sqlmem.exe context --kb $kb "Which vendors supply helmets?"   # prompt-ready context pack
.\.venv\Scripts\sqlmem.exe search  --kb $kb "promotion discount percent" -k 5
.\.venv\Scripts\sqlmem.exe table   --kb $kb Sales.SalesOrderHeader            # full knowledge card
.\.venv\Scripts\sqlmem.exe path    --kb $kb Production.ProductCategory Sales.SalesTerritory
.\.venv\Scripts\sqlmem.exe graph   --kb $kb --check --db $db                   # re-verify the knowledge graph
.\.venv\Scripts\sqlmem.exe query   --db $db "SELECT COUNT(*) FROM Sales__Customer"

# re-scan after schema/data changes (keeps semantic.yaml and memories)
.\.venv\Scripts\sqlmem.exe scan --kb $kb --db $db --exclude "__datapilot*"
.\.venv\Scripts\sqlmem.exe validate --kb $kb --db $db   # re-run all example queries
```

Browse the generated knowledge in [kb/adventureworks2025/docs/README.md](kb/adventureworks2025/docs/README.md) and
the knowledge graph in [knowledge-graph.md](kb/adventureworks2025/docs/knowledge-graph.md) or the
[interactive view](kb/adventureworks2025/docs/knowledge-graph.html) (open it in a browser).

## Use it from GitHub Copilot (MCP)

[.vscode/mcp.json](.vscode/mcp.json) registers the server when this repository is open in VS Code, using
`dbs\AdventureWorks2025.db` without an input prompt (on Linux/macOS change the command to `.venv/bin/sqlmem` and
use `/` path separators in the database argument). Start it from the MCP
view (or when Copilot Chat asks), then ask data questions in Agent mode. Tools:

| Tool | Purpose |
|---|---|
| `get_sql_context(question)` | **call first** – relevant tables/columns with meaning, codes, ranges, value matches, business concepts and relations from the knowledge graph, join paths, metrics, verified examples and memories |
| `describe_table`, `list_tables`, `find_join_path`, `search_knowledge`, `get_knowledge_graph` | drill down / explore |
| `run_sql(sql)` | read-only, row-capped, time-limited validation query (only when `--db` is given) |
| `create_chart(source, spec, enable_3d=False)` | private offline interactive HTML from classified retrieved rows or a guarded SQL query; optional project canvas |
| `remember(text, kind, question, sql, tables)`, `forget`, `list_memories` | long-term memory |
| `knowledge_graph_task(part)`, `save_knowledge_graph(entities, relations)` | let Copilot itself build the knowledge graph (see below) |
| `submit_conversation`, `memory_task`, `save_memory`, `learn_conversation` | explicit private conversation learning (keyless caller task/save or configured model) |
| `recall_memory`, `memory_history`, `restore_memory`, `memory_feedback`, `compact_memory` | session-aware inferred recall, source recovery, feedback and reversible archiving |

Time limits keep tool calls short. Each SQL statement is cancelled after 30 s (`sqlmem mcp --query-timeout`).
One `save_knowledge_graph` call spends at most 90 s on data checks (`--save-budget`). Items it couldn't check in
time are saved and listed as unverified; check them later with `sqlmem graph --check`. Cancellation works on
SQLite, DuckDB, PostgreSQL, MySQL/MariaDB and SQL Server; other engines rely on server-side limits.

Server config for another workspace (stdio, absolute paths):

```json
{
  "servers": {
    "adventureworks-memory": {
      "type": "stdio",
      "command": "D:\\dev\\sql-semantic-memory\\.venv\\Scripts\\sqlmem.exe",
      "args": ["mcp", "--kb", "D:\\dev\\sql-semantic-memory\\kb\\adventureworks2025",
               "--db", "D:\\dev\\sql-semantic-memory\\dbs\\AdventureWorks2025.db"]
    }
  }
}
```

## Private source-linked agentic memory

This is a bounded synchronous lifecycle, **not** a daemon, online model training, automatic workflow execution
or a promise of lossless summaries. Existing `remember`, `forget`, `memories`/`list_memories` and
`memories.jsonl` are unchanged; there is no migration or mirroring between stores.

On a user-authorized learning request, Copilot (or another MCP caller):

1. Selects and pre-sanitizes messages, then calls `submit_conversation(conversation_id, messages, session_id)`.
   MCP cannot observe host chat history; it sees only explicitly submitted messages.
2. Calls `memory_task(conversation_id)`. Its static instructions and untrusted user JSON describe a proposal.
   The caller reasons with its own model and calls `save_memory(proposal)`. **No separate sqlmem API key or
   sqlmem-side model call** is needed; the host Copilot service may itself be remote.
3. Valid proposals are **automatically accepted**, not queued for approval. Same type/session/key replaces
   one item after task/base-revision concurrency checks; old revisions, sources and conflict decisions remain.
   Stale errors require a fresh task. Different keys can contain unresolved inferred contradictions.
4. Supplies `session_id` to `recall_memory`/`get_sql_context`, inspects trust/source labels, and sends
   helpful/unhelpful/correction feedback after outcomes. Uses history, explicit archive recall and restore for recovery.

Alternatively, explicitly call `learn_conversation` or CLI `memory learn --llm`. Ollama, Azure OpenAI and
OpenAI-compatible endpoints use the existing saved/environment configuration (`--llm` > `SQLMEM_LLM` >
saved `llm`; analogous base-URL precedence). Only explicit learning contacts a configured model in this lane:
one JSON reply, no repair/fallback, no SDK retries, at most three unsupported-parameter negotiation requests
within a 60-second deadline. A remote Ollama host is not local-only.
Configured memory learning uses a cancellable async streaming transport under an absolute timeout, including
in-flight body consumption; it closes responses rather than abandoning worker threads. The completion envelope
is bounded to 256 KiB and extracted reply content to 64 KiB. Legacy non-memory LLM calls keep their synchronous
behavior. SDK injection for this bounded helper requires an async streaming SDK; injected library
`complete_json(system, user)` test/caller stubs remain supported. Async callers can await
`LLM.acomplete_memory_json` rather than nesting an event loop.

Messages are a local JSON array with **exactly** `role` and `content` fields:

```json
[{"role":"user","content":"Revenue excludes cancelled orders."}]
```

Save replies have exactly this shape (copy `task_id` from the task; table names must be canonical existing names):

```json
{"task_id":"<returned task id>","items":[
  {"type":"semantic","key":"revenue_basis","text":"Revenue excludes cancelled orders.",
   "steps":[],"tables":[],"message_indices":[0],"base_revision":0}
]}
```

Types are `working` (requires the source's nonempty session), `episodic`, `semantic` and `procedural`
(requires 1..16 prose steps). Only working is session-scoped. `base_revision=0` creates; updates require the
current head revision, including archived heads. SQL in prose is inert, **inferred, not database-verified**;
sources, model output and recalled workflows are untrusted data, never privileged instructions.

All nine nested CLI commands use `--kb` **before** the operation. Files are explicit bounded local UTF-8 JSON,
not YAML, URLs, attachments or imports of files mentioned in a transcript. Task output goes to stdout only:

```powershell
sqlmem memory --kb $kb submit --conversation chat_1 --file messages.json --session task_1
# Optional: --redact-file literals.json (a JSON array of literal strings)
sqlmem memory --kb $kb task --conversation chat_1
# Have the caller's model answer, then save its exact reply to a caller-chosen JSON file.
sqlmem memory --kb $kb save --file reply.json
sqlmem memory --kb $kb learn --conversation chat_1 --llm ollama:my-model
# Bare --llm uses saved/environment config; optional --base-url explicitly selects an endpoint.
sqlmem memory --kb $kb recall "revenue" --session task_1 --limit 10
sqlmem memory --kb $kb history --conversation chat_1 --revision 1
sqlmem memory --kb $kb history --id am_ID --limit 10
sqlmem memory --kb $kb feedback am_ID --feedback-id outcome_1 --outcome helpful --expected-revision 1
sqlmem memory --kb $kb compact --keep 100
sqlmem memory --kb $kb recall --include-archived
sqlmem memory --kb $kb restore am_ID --revision 1 --expected-revision 2
sqlmem context --kb $kb "revenue" --session task_1
```

Library `KnowledgeBase` methods and MCP tools have those operation names (CLI `submit` →
`submit_conversation`, `task` → `memory_task`, `save` → `save_memory`, etc.). Library learning accepts an
injected `complete_json(system, user)` client; MCP accepts `llm=""`, `base_url=""`. Reports are JSON objects:
`operation`, `items`, accepted/unchanged/archived counts, source references, `inferred`, `index_pending`,
warnings and `next_cursor`. Recall records carry `memory_id`, revision, type, status, text, trust and sources.
Pass the opaque `next_cursor` as `--cursor` to continue; mutations expire cursors. Source history pages at most
ten messages and discloses the latest revision. Errors identify code/field and advice, without input values;
CLI exits 2 and MCP reports a tool error. Index failure does not undo a committed source; `index_pending`
requests rebuilding on the next recall.
The authoritative transaction commits before private projection publication. Projection chunks and generation
commit atomically from one committed source snapshot, so rollback/crash recovery cannot confuse reused sequences.
Large catalogs use a deterministic subset of table-name hints within 8 KiB and report `table_hints_omitted`;
all canonical catalog tables, including omitted hints, remain valid proposal table references.

Active caps are working 128 total/32 per session, episodic 128, semantic 256 and procedural 128.
Overflow archives at most 32 heads per mutation, lowest usefulness then oldest revision/ID first. Feedback
usefulness is clamped to [-3,3] and breaks raw-BM25 ties only within private recall. Explicit compaction archives
at most 100 working/episodic heads per call; `remaining` asks for another call. It does **not** delete originals
or necessarily shrink disk usage. Restore appends a new head and rechecks caps; it may itself be archived.
Archived and superseded revisions remain accessible through history. Sources are retained within a 1-GiB
authoritative SQLite ceiling; full storage rejects writes with backup/relocation advice, never automatic deletion.

Conversation bounds: 1..100 messages, 8 KiB/message and 32 KiB canonical JSON; roles exactly
user/assistant/system/tool. IDs/keys are opaque `[A-Za-z0-9_-]{1,64}` (empty session allowed).
Up to 32 literal redactions of 256 bytes each; tasks at most 64 KiB; proposals at most 64 KiB/32 items,
2 KiB text/item, 512 bytes/step and 16 tables. Recall query at most 2 KiB; read limits 1..50.
Inputs are validated before and after sanitization, not silently truncated.

**Privacy limitations:** deterministic heuristics redact common credentials, private keys, emails, phone-like
numbers, US SSNs and Luhn-valid cards, plus caller literals. They can miss names, addresses, international/
obfuscated PII, domain-specific secrets and sensitive database values, or over-redact legitimate numbers.
Callers must pre-sanitize and omit sensitive material. Sanitized originals are not byte-identical originals;
removed secrets cannot be restored. Local SQLite/backups are plaintext, not encryption or full DLP.
Private paths are Git-ignored and reject symlink/reparse escapes; Unix owner-only permissions are applied where
supported, while Windows ACLs are inherited. Git ignore is not access control. Explicit configured learning
can send sanitized source/excerpts to its endpoint; host-agent privacy is outside sqlmem's control.

Back up authoritative memory using `kb.lifecycle().backup(new_local_path)` (SQLite's consistent backup API),
or a closed SQLite connection—not a live-file copy. Protect backups with the same access controls. Close with
`kb.close()` to release both stores and indexes. Neither private content nor source transcripts enter public
docs/graph/semantics/JSONL. Schema/legacy search and its budgets are unchanged; context may append up to five
untrusted inferred private items within a separate additional 8 KiB, with explicit omission/recovery advice.

## Interactive charts from retrieved data

Ask Copilot: **"Chart these results"**, **"Show sales by territory as an interactive bar chart"**, or
**"Plot these three measures as a 3D scatter chart and open the canvas"**. The project
[sqlmem-chart skill](.github/skills/sqlmem-chart/SKILL.md) guides explicit visualization requests; ordinary
data questions do not generate files. Restart the MCP server after updating sqlmem to expose `create_chart`.

The renderer uses **Apache ECharts 5.6.0 (Apache-2.0)** and optional **ECharts GL 2.1.0 (BSD-3-Clause)**.
Both are free for commercial use under their respective licenses; attribution and dependency notices ship
with the package and HTML. They provide broad native charting, not full Highcharts feature parity.
The pinned GL build has a reproducible, hash-checked CSP patch for its fixed internal size expressions, avoiding
dynamic code execution without relaxing the HTML security policy.
All runtime assets are embedded: no CDN, remote fonts, data uploads, Python chart dependency or internet connection.

Supported mappings cover bar/column, line/area/time, pie/donut, scatter/bubble, heatmap, treemap/sunburst,
candlestick, boxplot, radar, funnel, gauge, graph, sankey, and explicitly enabled scatter3D/bar3D/grid surfaces.
Financial plots use supplied OHLC/statistics, not an automatic stock-indicator engine; maps, Gantt, equation
surfaces, arbitrary plugins and raw chart JavaScript/options are not supported.

Example MCP arguments for already retrieved, non-sensitive rows:

```json
{
  "source": {
    "kind": "rows",
    "columns": [
      {"name": "territory", "kind": "string", "sensitivity": "non_sensitive"},
      {"name": "revenue", "kind": "number", "sensitivity": "non_sensitive"}
    ],
    "rows": [["North", 42000], ["South", 31000]],
    "source_truncated": false
  },
  "spec": {
    "type": "bar",
    "mapping": {"x": "territory", "y": ["revenue"]},
    "options": {"title": "Revenue by territory", "theme": "dark"}
  }
}
```

Alternatively use `source: {kind: "sql", sql: "SELECT ...", columns: [...], max_rows: 50}`.
SQL result names/order must match declared columns; the existing guard, query timeout and server row cap apply.
Rows mode needs no database connection and does not query again. Always declare completeness:
`source_truncated: true` means partial, `false` means complete, and `null` means unknown. Tool results report the
plotted row count, completeness and warnings; they do not automatically count, aggregate or sample your data.
For 3D, set the separate `enable_3d: true` argument. Missing WebGL produces an explicit warning with the table
retained, not a substituted 2D chart.

Output lives under `<kb>\build\charts\<random-id>.html`, ignored by Git and never ingested into memories/search.
The HTML contains plotted data: keep it private and delete it yourself when no longer needed. Only explicitly
non-sensitive columns are accepted, with conservative catalog/name checks; declarations are not automatic DLP
or proof of arbitrary SQL-expression lineage. Pass only aggregated, approved business data.

Open the HTML directly for interactive tooltips, legends and zoom where applicable, light/dark theme, reset,
PNG download and an accessible data table. To show the same HTML in VS Code, load the workspace
[chart canvas extension](.github/extensions/sqlmem-chart/extension.mjs), then open canvas `sqlmem-chart` with
`{path: artifact.path, outputRoot: the HTML parent folder}`. It uses a bounded loopback-only viewer, not a public
web server. Actions are `refresh({})`, `show_chart({chart_id})` and `download_html({})`.
The HTML remains usable without the canvas; the extension needs a Copilot host supporting the canvas SDK and Node.
See [ADR 0011](docs/design/adr/0011-bounded-offline-chart-visualization.md) for mappings, caps and safety boundaries.

## Build knowledge for your own database

```powershell
# 1. FACTS: scan everything (read-only). SQL Server via ODBC (Windows auth shown; Azure SQL: add
#    Authentication=ActiveDirectoryInteractive;). Any SQLAlchemy URL also works, e.g. postgresql+psycopg://...
sqlmem scan --kb kb\mydb --odbc "Driver={ODBC Driver 18 for SQL Server};Server=myserver;Database=MyDb;Trusted_Connection=yes;Encrypt=yes;"
#    large databases: --schema Sales --include "dbo.Fact*" --exclude "*_bak" --profile-rows 50000 --workers 8

# 2. KNOWLEDGE: draft semantic.yaml (all tables/columns; DB comments reused), optionally LLM-filled
sqlmem draft --kb kb\mydb                                        # skeleton -> semantic.draft.yaml
sqlmem draft --kb kb\mydb --llm                                  # fill gaps with the configured LLM (see below)
#    review, rename to semantic.yaml (or use --in-place), add glossary/metrics/examples, then:
sqlmem build --kb kb\mydb
sqlmem validate --kb kb\mydb --odbc "..."                         # every example query must still run

# 3. KNOWLEDGE GRAPH: business entities + relations, proposed by an LLM and verified against the data
sqlmem graph --kb kb\mydb --odbc "..."                            # see "Knowledge graph with an LLM" below

# 4. MEMORY: grows while you (or Copilot) work
sqlmem remember --kb kb\mydb "Revenue excludes cancelled orders (Status = 6)" --kind rule
sqlmem remember --kb kb\mydb "Top customers by revenue" --kind query --question "Who are our best customers?" --sql "SELECT ..."
```

Tip: GitHub Copilot can do step 2 for you — ask it to read `kb\mydb\docs` and fill the empty descriptions in
`semantic.yaml`, then review the diff.

## Knowledge graph with an LLM

The knowledge graph turns tables into the **business concepts** people talk about and the **relations** between
them, e.g. *Reseller Customer* = `Sales__Customer WHERE StoreID IS NOT NULL`, *Reseller Customer --places-->
Reseller Order*, *Vendor --supplies--> Product* (via `Purchasing__ProductVendor`). The LLM only *proposes*;
`sqlmem` accepts an item only if every table and column exists, the filter is safe SQL, a join path exists and -
with a database connection - the filter and join actually run. It also records row counts, joined pairs and
the cardinality observed in the data, and corrects cardinalities the data contradicts. Rejected items come back
with the reason. The result lands in `knowledge_graph.yaml` (editable; your edits survive regeneration) and is
used by `get_sql_context`, search, `graph.json`, [knowledge-graph.md](kb/adventureworks2025/docs/knowledge-graph.md)
(Mermaid) and an interactive `docs/knowledge-graph.html`.

There are three ways to provide the LLM - pick one:

**A. GitHub Copilot - nothing to configure.** With the MCP server running, ask Copilot (Agent mode):
*"Build the knowledge graph for this database with knowledge_graph_task and save_knowledge_graph."* Copilot reads
the task, proposes the graph, gets the validation report and fixes rejected items itself. Without MCP, use any
chat: `sqlmem graph --kb K --export-prompt prompt.md`, paste it, save the JSON answer, then
`sqlmem graph --kb K --import answer.json`. The AdventureWorks graph here (54 entities, 72 relations) was made
this way.

**B. An API model - automated, repeatable.** Configure once per knowledge base, then run `sqlmem graph`:

```powershell
# Azure OpenAI / Microsoft Foundry (recommended: keyless Entra ID)
$env:AZURE_OPENAI_ENDPOINT = "https://<resource>.openai.azure.com"     # or https://<resource>.services.ai.azure.com
az login                                    # needs the "Cognitive Services OpenAI User" role on the resource
#   ...or use a key instead:  $env:AZURE_OPENAI_API_KEY = "<key>"
sqlmem llm --kb kb\mydb --llm azure-openai:<deployment-name> --save   # saves the choice, sends a test request

# OpenAI
$env:OPENAI_API_KEY = "<key>"
sqlmem llm --kb kb\mydb --llm openai:gpt-4.1 --save

# Any OpenAI-compatible server (LM Studio, vLLM, other gateways)
sqlmem llm --kb kb\mydb --llm openai:<model> --base-url http://localhost:1234/v1 --save

sqlmem llm --kb kb\mydb                      # show the current setting and test it
sqlmem graph --kb kb\mydb --odbc "..."       # generate + verify against the data + rebuild
```

**C. A local model - data never leaves the machine.** Install [Ollama](https://ollama.com), `ollama pull <model>`,
then `sqlmem llm --kb kb\mydb --llm ollama:<model> --save` (`$env:OLLAMA_HOST` if it is not on localhost:11434).
Small local models follow the rules less reliably; the validation still keeps their mistakes out.

How the setting is resolved: `--llm` flag, else `$env:SQLMEM_LLM`, else `llm` in `<kb>\sqlmem.json` (written by
`--save`; it never contains keys - those are read only from environment variables or Entra ID). The same setting is
used by `sqlmem draft --llm`. Models that reject JSON mode or a custom temperature are handled automatically, and
an invalid JSON answer is sent back once for repair.

Useful options of `sqlmem graph`:

| Option | Effect |
|---|---|
| `--db/--odbc` | database to verify against (default: `$SQLMEM_DB`, or the scanned SQLite file); `--no-verify` = schema checks only |
| `--verify-timeout S` | stop each verification query after S seconds (default 120, `0` = no limit); slower checks are saved as *unverified* and listed in the report |
| `--replace` | let new definitions overwrite existing entities/relations (default: existing entries win) |
| `--max-chars N` | prompt size per part; larger schemas are split into parts by domain and later parts reuse earlier entity names |
| `--export-prompt FILE [--part N]` / `--import FILE` | bring-your-own-LLM workflow (the answer may contain prose or a code fence) |
| `--check` | re-validate the saved graph after editing it or after a re-scan (failing entries are kept, not deleted) |

Each entity: `name, kind (core/event/reference/role), description, synonyms, table, key, label, filter, is_a,
attributes`; each relation: `subject, predicate, object, cardinality, via, on, polymorphic, condition, description`.

### Keys, join columns and polymorphic references

```yaml
entities:
  - {name: Product Inventory, table: Production__ProductInventory, key: [ProductID, LocationID]}  # composite key
relations:
  - {subject: Sales Order, predicate: ships_to, object: Address,
     via: [Sales__SalesOrderHeader.ShipToAddressID]}          # pick one of several links (ShipTo vs BillTo)
  - {subject: Legacy Note, predicate: about, object: Sale,
     on: "legacy_notes.sale_no = sales.sale_id"}               # columns that are not a declared foreign key
  - subject: Archived Inventory Transaction                    # one column, several target tables
    predicate: for_order
    polymorphic:
      column: ReferenceOrderID                                 # holds a sales, purchase or work order id ...
      type_column: TransactionType                             # ... depending on this column
      targets:
        - {type: S, object: Sales Order, predicate: for_sales_order}
        - {type: P, object: Purchase Order, predicate: for_purchase_order}
        - {type: W, object: Work Order, predicate: for_work_order}
```

- **`key`** is a column or a list of columns; without it the table's primary key is used, composite keys included.
  Cardinality is measured on the full key, and a key that is not unique in the data is reported.
- **`via`**: `Table.Column` picks the column when tables are linked more than once (bill-to vs ship-to address, or
  a bill of materials' assembly vs component column). A warning lists the alternatives when you don't pick one.
- **`on`** gives the join columns for links the schema doesn't declare. Rows whose value matches nothing are
  counted as `unmatched`.
- **`polymorphic`** is expanded into one relation per target. Each joins the reference column to the target
  entity's key, restricted to its type values. Type values that don't occur in the data, and stored type values
  without a target, are reported. Each branch counts its unmatched references.
- **Fan-out protection.** sqlmem won't add tables on its own if the join would go many-to-one and then
  one-to-many through them. For example, archived transactions → product → all order lines of that product
  pairs rows that only share a product, and on AdventureWorks that is millions of rows. Such a relation is
  rejected and the message says to use `on` or `polymorphic`. A path you spell out in `via` is accepted, with a
  warning.
- **Explicit links feed the planner.** `on` and polymorphic links become join paths for `get_sql_context` and
  docs, shown as `[kg; ...]`.

### `semantic.yaml` reference

```yaml
database:
  name: MyDb
  description: What the business does and what the data covers.
  dialect_notes: ["Dates are UTC", "Amounts are in EUR"]        # rules injected into every context
  housekeeping_columns: [ModifiedDate, rowguid]                # optional; otherwise detected automatically
domains: {Sales: "Orders and customers"}
tables:
  Sales.Orders:                                                # name as in catalog (Schema.Table or Table)
    description: One row per customer order.
    synonyms: [orders, sales, invoices]
    grain: one row per order
    notes: ["Net revenue = SUM(SubTotal)"]
    hidden: false                                              # true = exclude from knowledge
    columns:
      Status: {description: Order status, values: {1: Open, 5: Shipped}}
      ShipDate: Date the order left the warehouse.             # plain string = description
relationships:                                                 # joins that are not declared as FKs
  - {from: Sales.Orders.RepId, to: HR.Employee.EmployeeId, condition: "", description: Sales rep}
glossary:  [{term: Reseller, synonyms: [dealer], definition: "...", sql: "...", tables: [Sales.Store]}]
metrics:   [{name: Revenue, synonyms: [sales], definition: "...", sql: "SUM(Sales.Orders.SubTotal)"}]
examples:  [{question: Revenue by year, sql: "SELECT ..."}]   # verified question -> SQL pairs
```

## Supported databases

`sqlmem` only talks to databases through SQLAlchemy (reflection + generic SQL), so any SQL engine with a
SQLAlchemy dialect works. When a driver's reflection is missing or broken, columns and keys are read from the
standard `INFORMATION_SCHEMA` instead (reported as `NOTE` lines during `scan`).

| Status | Databases | Notes |
|---|---|---|
| **Tested** (`tests/test_dialects.py`, same scenario on each) | SQLite 3.50 · SQL Server 2025 · PostgreSQL 18.6 · MariaDB 11.4 (MySQL dialect) · DuckDB 2.0 | mixed-case/reserved names, multiple schemas, declared + inferred joins, materialized views (PostgreSQL); DuckDB uses the INFORMATION_SCHEMA fallback |
| **Same code path, not tested here** | Azure SQL Database / Managed Instance, SQL database in Fabric, Fabric Warehouse / Synapse SQL (SQL Server dialect) · MySQL 8 · Azure Database for PostgreSQL/MySQL, Amazon RDS/Aurora, Supabase, Neon | |
| **Should work via third-party dialects (not tested)** | Oracle (`oracledb`) · Snowflake (`snowflake-sqlalchemy`) · Databricks (`databricks-sqlalchemy`) · BigQuery (`sqlalchemy-bigquery`) · Redshift · Trino/Presto · ClickHouse · Db2 | third-party dialects can lag SQLAlchemy releases; if one fails to import, pin `"SQLAlchemy>=2.0,<2.1"` |
| **Not supported** | MongoDB, Cosmos DB (NoSQL API), Redis, Elasticsearch, raw CSV/Excel/Parquet files | load files into SQLite/DuckDB first |

Connection examples (put credentials in `$env:SQLMEM_DB` rather than on the command line):

```powershell
sqlmem scan --kb kb\x --odbc "Driver={ODBC Driver 18 for SQL Server};Server=tcp:srv.database.windows.net;Database=Db;Authentication=ActiveDirectoryInteractive;Encrypt=yes;"
sqlmem scan --kb kb\x --db "postgresql+psycopg://user:pwd@host:5432/db" --schema public   # pip install "psycopg[binary]"
sqlmem scan --kb kb\x --db "mysql+pymysql://user:pwd@host:3306/db"                       # pip install pymysql
sqlmem scan --kb kb\x --db "duckdb:///C:/data/analytics.duckdb"                          # pip install duckdb-engine
sqlmem scan --kb kb\x --db "oracle+oracledb://user:pwd@host:1521/?service_name=PDB1"     # pip install oracledb
sqlmem scan --kb kb\x --db "snowflake://user:pwd@account/db/schema?warehouse=WH"         # pip install snowflake-sqlalchemy
```

Things to know per engine:

- **Which schemas are scanned**: SQL Server and PostgreSQL scan all user schemas of the database; Oracle scans
  the login's own schema; everything else scans the database/schema named in the URL. Override with
  `--schema` (repeatable). Explicitly scanned schemas are always part of table names (`schema.table`).
- **Pay-per-query warehouses** (BigQuery bills bytes scanned, `LIMIT` doesn't reduce it; Snowflake/Databricks
  bill compute): profiling reads every column. Start with `--include`, `--no-profile` or `--no-values`.
- **Big databases**: narrow with `--schema/--include/--exclude`, cap work with `--profile-rows`, `--workers`.
- Add engine-specific SQL rules (date functions, quoting, time zones) to `dialect_notes` in `semantic.yaml`;
  they are injected into every context.

## How retrieval works

1. **Hybrid search** over ~1 chunk per table, column, metric, term, example and memory: SQLite FTS5 BM25
   (Porter stemming, identifier splitting `OrderDate` → `order date`) fused with dense-vector similarity
   (local `BAAI/bge-small-en-v1.5` via fastembed — no data leaves the machine) using Reciprocal Rank Fusion.
2. **Value linking**: literals in the question (`helmets`, `Germany`, `mountain bikes`) are matched against
   captured value dictionaries → the right table/column and the *exact* literal (`'Helmets'`, padding included).
3. **Table ranking** aggregates hits per table; **join planning** connects them with the cheapest paths over
   declared, curated and inferred keys (adding bridge tables), conditional joins included.
4. The **context pack** = SQL rules + value matches + business concepts and relations from the knowledge graph
   (table/filter mappings and ready-to-use joins) + memories + metric/glossary definitions + similar verified
   queries + compact table cards (codes, ranges, nulls, FKs) + ON-clauses. A parent entity's relations also
   match its subtypes (e.g. *Sales Order ships to Address* for a question about online orders).

Measured with the committed evaluation (`python -m evals.run_retrieval`, 24 AdventureWorks questions, see
[evals/retrieval_cases.yaml](evals/retrieval_cases.yaml)): the context names every table a correct SQL needs in
**24/24** questions with fastembed (22/24 with the knowledge graph ignored) and 24/24 with BM25 alone (23/24
without the graph), with 4.5-4.9 tables per context on average. Numbers and the commit they belong to are in the
[evidence records](docs/evidence/README.md); the BM25 result is a gate in every test run.

## Safety and privacy

- Scanning and `run_sql` are read-only in two layers:
  1. Queries must be one `SELECT`/`WITH` statement, with no comments and no write/side-effect keywords or
     functions (DML/DDL/EXEC/INTO/COPY/`set_config`/file readers…). Quoting tricks that engines parse
     differently (backslash escapes, dollar or q-quotes) are rejected. Results are row-capped and every
     query is rolled back.
  2. The database itself enforces read-only where it can: SQLite and DuckDB files are opened read-only;
     PostgreSQL, MySQL and MariaDB sessions are read-only.

  SQL Server, Oracle and cloud warehouses have no such session mode, so give `sqlmem` a **read-only login**
  (always recommended anyway).
- Columns that look personal (names, e-mail, phone, birth date, card numbers, passwords, national IDs…) are
  flagged `sensitive`: statistics only, **no values** are stored. Extend with `--sensitive "regex"`, override
  per column in `semantic.yaml`, or use `--no-values` to store no data values at all.
- Passwords are never written to `catalog.json`. Embeddings are local by default; Azure OpenAI is opt-in.
- What an LLM sees (`sqlmem graph`, `draft --llm`): schema, descriptions and the captured value lists/ranges of
  non-sensitive columns. Use a local model (Ollama), Copilot, or `draft --no-values` if that must not leave the
  machine. LLM-written filters and joins are executed through the same read-only guard and time limits as `run_sql`.

## Commands

`scan`, `build`, `draft`, `graph`, `llm`, `context`, `search`, `table`, `path`, `tables`, `remember`, `forget`,
`memories`, `query`, `validate`, `stats`, `mcp` — see `sqlmem <command> -h`. `--kb` defaults to `$SQLMEM_KB`, `--db` to `$SQLMEM_DB`.
Embedders: `fastembed[:model]` (default when installed), `azure-openai:<deployment>`, `openai:<model>`,
`ollama:<model>`, `none` (BM25 only). Vectors are cached by content hash, so rebuilds only embed what changed.

## Development

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -e ".[local,mcp,llm,mssql,postgres,mysql,duckdb,dev]"
#   Stop the MCP server in VS Code before (re)installing: pip rewrites sqlmem.exe, which is locked while it runs.
python scripts/verify.py          # ruff, ruff format, mypy --strict, pyright, pytest + coverage, eval, traceability
#   -> evidence in build/evidence/ (summary.md, traceability.md, junit.xml, coverage.xml, logs/)
# All five engines (portable PostgreSQL + MariaDB + SQL Server LocalDB on Windows; or `docker compose up -d --wait`):
.\scripts\engines.ps1 start; .\scripts\engines.ps1 env | Invoke-Expression
python scripts/verify.py --require-engines
.\scripts\engines.ps1 stop
```

The repository is built for **evidence-driven, agent-assisted development**: requirements with IDs
([docs/requirements.md](docs/requirements.md)) proven by marked tests, one verification command, committed review and
evidence records, and a GitHub Copilot agent team (orchestrator, architect, implementer, test engineer, reviewer,
evidence auditor, KB curator) with skills and prompts in `.github/`. Start with [AGENTS.md](AGENTS.md),
[CONTRIBUTING.md](CONTRIBUTING.md) and the [documentation index](docs/README.md) (architecture, design and ADRs,
testing, process).

## Related Microsoft options

- **Descriptions inside SQL Server**: `MS_Description` extended properties are picked up automatically by `scan`.
- **SQL Server 2025 / Azure SQL / SQL database in Fabric** have a native `VECTOR` type, so the same chunks and
  embeddings could be stored and searched inside the database itself.
- **Microsoft Fabric data agents** offer a managed version of the knowledge layer (instructions + example
  queries over lakehouses, warehouses, semantic models and KQL databases) if your data lives in Fabric.

## License

sqlmem is released under the [MIT License](LICENSE). Bundled third-party chart assets keep their own licenses and
notices in [sqlmem/assets/vendor/](sqlmem/assets/vendor/).
