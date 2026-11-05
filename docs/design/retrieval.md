# Retrieval design

Goal: for a natural-language question, hand the agent a compact **context pack** that contains every table, column,
value, join and rule needed to write correct SQL — and little else.

## Chunks

`render.build_chunks` turns the semantic model into ~1 chunk per table, column, metric, glossary term, verified
example, routine, knowledge-graph entity and relation, and memory. Each chunk has a `kind`, a title, text,
identifier-split keywords (`OrderDate` → `order date`), the tables it touches, and a payload used for rendering.

## Search (ADR 0004)

`Index.search(question, k=40, rrf_k=10)`:

1. **BM25** over FTS5 (`porter unicode61 remove_diacritics 2`), query built by `fts_query` (stopwords removed,
   identifiers split).
2. **Vectors**: cosine similarity between the question embedding and chunk embeddings (skipped with
   `embedder: none`).
3. **Reciprocal Rank Fusion**: score = Σ 1 / (k + rank). The context uses a small `k` (10) so rank differences count
   more when choosing tables.

## Table selection (`render.select_tables`, ADR 0009)

1. `rank_tables`: every hit contributes `score × KIND_WEIGHT[kind]` to each table it touches; per table the best
   four contributions are combined with decaying weights (1, ½, ¼, ⅛).
2. Keep tables scoring at least `TABLE_SCORE_RATIO` (0.5) of the best, at most `max_tables` (default 6).
3. **Value linking** (`SemanticModel.match_values`): longest-first n-grams of the question are matched against the
   captured value dictionaries; tables holding such a literal are added after the ranked tables (at most 3), so a
   literal never pushes out a retrieved table.
4. `SemanticModel.connect`: a greedy Steiner tree adds bridge tables and returns the join conditions (declared,
   curated, inferred and conditional joins; at most 3 hops, at most 3 extra tables).

## Context pack (`render.render_context`)

Sections, in order: dialect rules (`dialect_notes`), values found in the data (exact literals), business concepts
and relations from the knowledge graph (table/filter mappings and verified joins), learned memories, business
definitions (metrics, glossary), verified example queries, compact table cards (purpose, key columns, codes, ranges,
nulls, foreign keys), join paths, and other possibly relevant tables.

## Measuring

`evals/run_retrieval.py` checks that the "Relevant tables" section contains all tables needed for each of the
24 AdventureWorks questions; gates per embedder family live in `evals/retrieval_cases.yaml`. Use
`--ablate-kg` to measure the knowledge graph's contribution. Current numbers: see the latest
[evidence record](../evidence/README.md).
