# 0009. Value matches add tables; they never displace retrieved tables

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-RET-03, REQ-RET-05

## Context

The context pack shows at most `max_tables` (default 6) ranked tables. Literals from the question that appear in a
column's value dictionary ("Canada", "reseller") used to boost their tables to 0.8 × the top score. When the
committed retrieval eval was introduced, it showed that the knowledge-graph update (composite keys, polymorphic
relations) had dropped one case: for "Which store contacts work for resellers in Canada?" three value-matched tables
(`Sales__SpecialOffer` for "reseller", `Person__CountryRegion` and `Sales__SalesTerritory` for "Canada") pushed the
bridge table `Person__BusinessEntityContact` (ranked 5th by retrieval, named by the graph relation
*Store has_contact Store Contact*) out of the context: 23/24 full hits for BM25 and fastembed.

## Options

| Option | BM25 full / avg tables | fastembed full / avg tables |
|---|---|---|
| Boost value tables into the ranking (before) | 23/24, 4.67 | 23/24, 4.38 |
| Boost only the best table per phrase | 23/24, 4.67 | 23/24, 4.33 |
| Raise `max_tables` to 8 | 24/24, 4.96 | 24/24, 4.50 |
| **Add value tables after the ranked tables (at most 3)** | **24/24, 4.88** | **24/24, 4.50** |

## Decision

`render.select_tables` keeps the top `max_tables` tables from retrieval and then adds tables that hold a literal
from the question, ordered by retrieval score, at most `MAX_VALUE_TABLES = 3`. Retrieval ranking and value matches
are separate evidence; neither displaces the other.

## Consequences

- Restores 24/24 with a small context-size cost (+0.2 tables on average for BM25, +0.1 for fastembed).
- Questions with many literals get up to three extra tables.
- The deterministic `hash` test embedder stays at 23/24; its gate is set accordingly.

## Verification

`test_value_matches_add_tables_without_displacing_retrieved_ones` (fails under the old policy), the BM25 eval gate
(24/24, mean recall 1.0) in every test run, and the fastembed gate (24/24) in local runs
([evidence](../../evidence/2026-10-30-repository-baseline.md)).
