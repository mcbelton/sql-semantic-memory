---
name: retrieval-evaluation
description: 'Measure and debug sqlmem retrieval quality with the AdventureWorks evaluation (evals/run_retrieval.py): full-recall and mean recall of the tables a correct SQL needs, BM25 vs fastembed, knowledge-graph ablation, gates, adding cases, and diagnosing misses with rank_tables, select_tables and value matches. Use for search, ranking, context-pack, chunking, embedding or knowledge-graph changes.'
argument-hint: 'Optional: embedder (none, hash:256, kb)'
---

# Retrieval evaluation

Each case in `evals/retrieval_cases.yaml` is a question plus the tables a correct SQL needs. A case is a *full* hit
when all of them appear under "## Relevant tables" in the context pack.

## Procedure
1. Baseline before changing anything:
   `python -m evals.run_retrieval --ablate-kg` (BM25, CI gate) and
   `python -m evals.run_retrieval --embedder kb --ablate-kg` (fastembed, as the KB is configured).
2. Make the change; run both again. Report full hits, mean recall and average tables (context size) before and
   after, with and without the knowledge graph.
3. A miss is diagnosed, never just re-tuned until it disappears:
   ```python
   from evals.run_retrieval import prepare_kb
   from sqlmem.render import rank_tables, select_tables

   kb = prepare_kb(Path("kb/adventureworks2025"), "none", Path(tempfile.mkdtemp()))
   hits = kb.index().search(question, k=40, rrf_k=10)
   ranked, values, chosen = select_tables(kb.model(), question, hits)
   ```
   Check whether the table is retrieved at all (hits), ranked too low (`rank_tables`), displaced (value matches,
   `max_tables`), or missing from the knowledge (descriptions, synonyms, graph relations).
4. Prefer fixing knowledge (semantic.yaml, graph) for data-specific misses and code for systematic ones; a code
   change must not lower any embedder's result.
5. New capability? Add cases that fail before and pass after. Phrase questions like users do.

## Gates
`gates` in the cases file are per embedder family. Raise them when results improve; lowering one needs an ADR.
The pytest gate (`tests/test_eval_gate.py`) enforces the BM25 gate in every test run.
