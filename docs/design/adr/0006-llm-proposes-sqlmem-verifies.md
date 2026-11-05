# 0006. The LLM proposes, sqlmem verifies the knowledge graph

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-KG-01, REQ-KG-02, REQ-KG-03, REQ-KG-09

## Context

A business knowledge graph (Customer, Reseller, Sales Order, "ships to", ...) greatly improves retrieval for
questions phrased in business terms, but writing it by hand for hundreds of tables is slow. LLMs write plausible
graphs quickly, and plausible is not correct: wrong filters, joins over the wrong key, invented columns.

## Options

1. **Hand-written graph only**: correct but does not scale.
2. **LLM-written graph stored as is**: fast but unverified.
3. **LLM (or Copilot) proposes; sqlmem plans every join from the schema and verifies every filter and join
   against the data** (row counts, key uniqueness, pairs, unmatched rows, cardinality) before storing it.

## Decision

We use option 3. Proposals arrive through `sqlmem graph` (configured LLM) or the MCP tools
`knowledge_graph_task`/`save_knowledge_graph` (Copilot, no API key). Large schemas are split into parts; later parts
see the names already defined. Items that fail planning or verification are dropped with an actionable reason.

## Consequences

- The graph only contains joins that ran on the real data; the report teaches the proposer how to fix the rest.
- Verification costs database time (bounded by ADR 0008).

## Verification

`test_generate_validates_against_schema_and_data`, `test_merge_keeps_existing_unless_replace`,
`test_check_keeps_broken_edits_for_fixing`, `test_mcp_tools_let_copilot_build_the_graph`, and the eval ablation:
on the AdventureWorks eval the knowledge graph raises full hits from 22/24 to 24/24 with fastembed
([evidence](../../evidence/2026-10-30-repository-baseline.md)).
