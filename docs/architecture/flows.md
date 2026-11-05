# Runtime flows

## 1. Scan: database → facts

```mermaid
sequenceDiagram
    actor U as User
    participant C as cli scan
    participant D as db
    participant S as scan
    participant DB as Database
    participant K as KnowledgeBase
    U->>C: sqlmem scan --kb kb/x --db URL
    C->>D: resolve_url + make_engine(readonly)
    D-->>C: engine (read-only session where supported)
    C->>S: scan_database(engine, ScanOptions)
    S->>DB: reflect schemas, tables, views, keys, indexes, comments
    alt reflection missing or broken
        S->>DB: INFORMATION_SCHEMA queries (NOTE in output)
    end
    par workers
        S->>DB: profile columns (counts, nulls, ranges, value dictionaries#59; sampled)
    end
    Note over S: sensitive columns: statistics only, no values
    S-->>C: catalog dict
    C->>K: save_catalog → catalog.json, then build
```

## 2. Build: files → docs and index

```mermaid
sequenceDiagram
    participant K as KnowledgeBase
    participant M as SemanticModel
    participant R as render
    participant I as Index (store)
    K->>M: catalog.json + semantic.yaml + knowledge_graph.yaml
    M-->>K: tables, columns, joins (declared, curated, inferred), value index, graph
    K->>R: build_chunks(model, memories)
    R-->>K: ~1 chunk per table, column, metric, term, example, entity, relation, memory
    K->>I: replace_all(chunks): FTS5 rows + vectors (embedded only when the content hash changed)
    K->>R: table_doc, overview_doc, kg_doc, kg_html, graph_json
    R-->>K: docs/ + graph.json written
```

## 3. Context pack for a question (`get_sql_context`)

```mermaid
sequenceDiagram
    actor A as Agent
    participant MS as MCP server
    participant K as KnowledgeBase
    participant I as Index
    participant R as render
    participant M as SemanticModel
    A->>MS: get_sql_context("helmet revenue by country")
    MS->>K: context(question, max_tables)
    K->>I: search(question, k=40, rrf_k=10)
    I-->>K: hits = RRF(BM25 ranks, vector ranks)
    K->>R: render_context(model, question, hits)
    R->>R: rank_tables (weighted by chunk kind)
    R->>M: match_values(question) → literals found in value dictionaries
    R->>R: select_tables: top tables + value-matched tables (never displacing)
    R->>M: connect(chosen) → bridge tables + join conditions
    R-->>A: rules, value matches, graph concepts and joins, memories, definitions, examples, table cards, join paths
```

## 4. Knowledge graph: propose → verify → save

```mermaid
sequenceDiagram
    actor A as Agent or LLM
    participant MS as MCP server / cli graph
    participant K as KnowledgeBase
    participant G as kgraph
    participant DB as Database
    A->>MS: knowledge_graph_task(part)
    MS->>K: kg_prompt(part) → schema digest + names already defined
    A->>MS: save_knowledge_graph(entities, relations)
    MS->>K: import_kg(graph, engine, timeout, budget)
    K->>G: normalize → plan_relation (keys, via, on, polymorphic, fan-out check)
    loop each entity and relation, until the budget is used
        G->>DB: run_select(filter / join measurement) with time limit
        DB-->>G: row counts, key uniqueness, pairs, unmatched rows
    end
    G-->>K: Report (accepted, unverified, dropped with reasons)
    K->>K: merge_graphs → knowledge_graph.yaml, rebuild
    MS-->>A: report text (what to fix for dropped items)
```

## 5. `run_sql`: the safety boundary

```mermaid
sequenceDiagram
    actor A as Agent
    participant MS as MCP server
    participant D as db
    participant DB as Database
    A->>MS: run_sql(sql, max_rows)
    MS->>D: run_select(engine, sql, min(max_rows, row_cap), timeout=query_timeout)
    D->>D: check_readonly(sql, dialect): one SELECT/WITH, no comments, no write/side-effect words
    alt rejected
        D-->>A: ToolError "Only SELECT ..." (actionable)
    end
    D->>DB: execute inside time_limit (statement_timeout / max_execution_time / interrupt / driver timeout)
    Note over DB: session is read-only where the engine supports it
    DB-->>D: rows (fetch max_rows + 1)
    D->>DB: rollback
    D-->>A: Markdown table (+ "truncated")
```

## 6. Memory

This is the existing JSONL workflow; ADR 0012 leaves it intact.

```mermaid
sequenceDiagram
    actor A as Agent
    participant MS as MCP server
    participant K as KnowledgeBase
    participant ST as MemoryStore
    participant I as Index
    A->>MS: remember(kind, text, sql?)
    MS->>K: remember(...)
    K->>ST: validate (known kind, text, SQL for query memories, existing tables), append to memories.jsonl
    K->>I: upsert(memory chunk) — searchable immediately
    MS-->>A: "Saved ... (id)"
```

## 7. Proposed agentic memory: submitted sources → automatic revisions → separate recall

[ADR 0012](../design/adr/0012-bounded-source-linked-agentic-memory.md) is the normative contract; this flow is
planned, not evidence of implementation. Every operation is synchronous and bounded; no chat monitoring/daemon.

```mermaid
sequenceDiagram
    actor A as Caller
    participant K as CLI or MCP via KnowledgeBase
    participant L as LifecycleStore
    participant M as Caller model or explicit configured LLM
    participant I as Private derived BM25
    A->>K: submit_conversation(id, selected messages, session)
    K->>L: sanitize, check bounds and source revision, commit immutable source
    A->>K: memory_task(id)
    K-->>A: task_id, static instructions, untrusted source data, proposal schema
    A->>M: reason over task data
    Note over M,K: Alternatively explicit learn_conversation uses configured client
    A->>K: save_memory(proposal)
    K->>L: validate whole batch and concurrency
    L->>L: automatically accept, append revisions and lineage, archive cap overflow
    L-->>K: commit report, inferred not database-verified
    K->>I: refresh current heads and eligibility, record generation
    K-->>A: accepted IDs, revisions, archived IDs, warnings
    A->>K: recall_memory(query, session)
    K->>I: filter eligible heads before separate ranking
    K-->>A: bounded untrusted items with revision and source links
    A->>K: memory_history or restore_memory
    K->>L: page sanitized originals/history or append restored head
```

Feedback adds idempotent outcome events; correction appends a sanitized source and replacement revision.
Explicit compact archives at most 100 working/episodic heads and records exact revision manifests, never deletes
originals. Automatic caps apply to all four types. History/include-archived recall and restore are explicit.
`context` runs flow 3's schema selection unchanged, then appends at most five private recalled items within
8 KiB. Private hits do not enter schema ranking, value/table/bridge budgets or verified-example sections.
