---
name: implement-requirement
description: "Implement a requirement end to end with evidence: requirement row, tests marked with its ID, code, verify.py, docs and an evidence record."
disable-model-invocation: true
argument-hint: "REQ-ID(s) or a short feature description"
---
Implement the requested capability the evidence-driven way:

1. Find or add the requirement row(s) in [docs/requirements.md](../../docs/requirements.md). Quote the final text.
2. Write the tests first, marked `@pytest.mark.req("<ID>")`, and show that they fail.
3. Implement the change following [python instructions](../instructions/python.instructions.md).
4. Run `python scripts/verify.py --fix` until every gate passes. Retrieval changes: also run
   `python -m evals.run_retrieval --embedder kb --ablate-kg` and give before/after numbers.
5. Update `README.md`/`docs/` and `CHANGELOG.md` (Unreleased) for user-visible behavior.
6. Report: files changed, requirement IDs proven, the gate table from `build/evidence/summary.md`, gaps.
