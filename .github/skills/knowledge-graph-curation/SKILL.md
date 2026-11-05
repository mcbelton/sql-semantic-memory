---
name: knowledge-graph-curation
description: 'Build, extend and repair the business knowledge graph (entities, relations, keys, filters, via, on, polymorphic references) of a sqlmem knowledge base with an LLM (sqlmem graph) or with Copilot through the MCP tools knowledge_graph_task and save_knowledge_graph, then verify it against the data. Use when relations are dropped or unverified, keys are composite, joins fan out, or a new database is onboarded.'
argument-hint: 'Knowledge base folder or entities to work on'
---

# Knowledge-graph curation

The LLM (or Copilot) **proposes**; sqlmem **verifies** every filter and join against the data and keeps only what
checks out (ADR 0006). The graph lives in `kb/<name>/knowledge_graph.yaml`.

## Procedure
1. Generate or extend:
   - with a configured LLM: `sqlmem graph --kb <kb> --db <db>` (see `sqlmem llm` for setup);
   - with Copilot (no API key): call `knowledge_graph_task` (part 1..n), then `save_knowledge_graph` with the
     entities and relations for that part.
2. Read the report. For each dropped item, apply the matching fix and resubmit:

   | Problem reported | Fix |
   |---|---|
   | entity key is not unique / missing | set `key: [col1, col2]` (composite keys allowed) |
   | several direct links between the tables | pin the join with `via: [table.column]` |
   | no join path / tables without a foreign key | write the join with `on: "s.col = o.col"` |
   | path fans out through a shared table | choose a `via` through the bridge table, or `on` |
   | one column refers to several tables by a type column | `polymorphic: {column, type_column, targets}` |
   | not verified: the query did not finish within Ns | saved unverified; re-run `sqlmem graph --check` later |
3. Re-verify everything: `sqlmem graph --kb <kb> --check --db <db>`; aim for 0 dropped and 0 unverified.
4. `sqlmem build --kb <kb>` to refresh docs (`knowledge-graph.md`, `.html`) and the search index.
5. For the eval fixture (`kb/adventureworks2025`), run the `retrieval-evaluation` skill and report the change.

## Acceptance
Report counts (entities, relations, verified, unverified, dropped) before and after, and the eval numbers.
