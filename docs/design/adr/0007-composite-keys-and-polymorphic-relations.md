# 0007. Composite keys, explicit joins and polymorphic relations

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-KG-04, REQ-KG-05, REQ-KG-06, REQ-KG-07

## Context

Real schemas do not always have one-column keys and declared foreign keys. In AdventureWorks, product inventory is
identified by (ProductID, LocationID), archived transactions point to either a sales order or a purchase order
through `ReferenceOrderID` + `TransactionType`, and some joins have no declared foreign key. The first graph could
not represent these, and one validation timed out.

## Options

1. **Ignore** such relations: the graph stays incomplete exactly where users need help.
2. **Free-form SQL joins** written by the LLM: expressive but unplannable and easy to get wrong.
3. **Structured extensions** that sqlmem can still plan and verify: `key: [a, b]` (composite, uniqueness checked),
   `via: [table.column]` (pin which key path to use), `on:` (explicit join for tables without a foreign key), and
   `polymorphic: {column, type_column, targets}` (expanded into one verified relation per target). Auto-planned
   paths that fan out through a shared table are rejected; ambiguous direct links are reported.

## Decision

We use option 3; free-form SQL is only accepted through `on`, which still passes the guard and verification.

## Consequences

- The AdventureWorks graph covers 62 entities and 89 relations, all verified.
- The YAML stays compact: single keys are written as scalars.

## Verification

`tests/test_kgraph_advanced.py` (composite keys, `on`, polymorphic expansion, reload and join planning, actionable
errors, fan-out rejection, ambiguous links) and `test_link_table_with_two_keys_to_the_same_table`.
