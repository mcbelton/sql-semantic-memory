# 0004. Hybrid retrieval: BM25 and vectors fused with RRF

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-RET-01, REQ-RET-05

## Context

Questions use business words ("bike shops", "store contacts"), database words (`SalesOrderHeader`) and literals
("Germany", "helmets"). Pure lexical search misses paraphrases; pure vector search misses exact identifiers and
codes, and needs a model that may not be available offline or in CI.

## Options

1. **BM25 only** (SQLite FTS5): fast, exact, no model; weak on paraphrase.
2. **Vectors only**: good on paraphrase; weak on identifiers; requires a model.
3. **Hybrid**: FTS5 BM25 with identifier splitting and Porter stemming, plus dense vectors, fused with Reciprocal
   Rank Fusion; vectors optional (`--embedder none` = BM25 only).

## Decision

We use option 3, in one SQLite file (`index.db`). Default embedder: local `BAAI/bge-small-en-v1.5` via fastembed
(no data leaves the machine); Azure OpenAI, OpenAI and Ollama embedders are opt-in. Value linking and the knowledge
graph complement search (see [retrieval design](../retrieval.md)).

## Consequences

- Works offline and in CI without a model (BM25 only), better with one.
- Two signals to keep calibrated; RRF keeps fusion parameter-free except `k`.

## Verification

`test_hybrid_search_uses_lexical_and_vectors`; the retrieval eval gates per embedder family in
`evals/retrieval_cases.yaml` (BM25 enforced in every test run by `tests/test_eval_gate.py`).
