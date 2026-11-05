# 0008. Time-bounded verification and queries

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-SAFE-03, REQ-KG-08

## Context

Verifying a knowledge graph runs dozens of measuring queries; on large tables one join can take minutes, and an
MCP tool call that does not return blocks the agent. Earlier, a validation of archived-transaction links timed out
and the whole save failed.

## Options

1. **No limits**: correct results eventually; unusable for agents.
2. **Global client-side timeout**: the database keeps working after the client gives up.
3. **Per-query limits enforced by the engine** (PostgreSQL `statement_timeout`, MySQL `max_execution_time`, MariaDB
   `max_statement_time`, SQL Server driver timeout, SQLite/DuckDB `interrupt()`) plus an **overall budget**; items
   that cannot be checked in time are saved **unverified** (not dropped) and can be re-checked later.

## Decision

We use option 3: `db.time_limit` per statement, `kgraph._Checker` for the overall budget, and MCP defaults of 30 s
per query and 90 s per `save_knowledge_graph` call.

## Consequences

- Agents always get an answer; slow checks surface as "not verified: ..." warnings with a way to finish them
  (`sqlmem graph --check`).
- Each engine's cancellation path must be tested (connection must stay usable after a timeout).

## Verification

`test_run_select_time_limit_keeps_the_connection_usable`, `test_verification_budget_saves_items_unverified`,
`test_slow_join_is_saved_unverified_not_dropped`, `test_mcp_tools_are_time_limited`, and the `HEAVY` query per
engine in the cross-engine scenario.
