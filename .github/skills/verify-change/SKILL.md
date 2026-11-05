---
name: verify-change
description: 'Run all quality gates for sqlmem with scripts/verify.py and fix failures: ruff lint and format, mypy strict, pyright (Pylance), pytest with coverage, retrieval eval and requirement traceability. Use when finishing a change, before committing, when CI fails, or when asked to prove that the code works.'
argument-hint: 'Optional: gates to skip, e.g. --skip eval'
---

# Verify a change

`scripts/verify.py` is the single source of truth for "done". It runs the same gates locally and in CI and writes
the evidence bundle to `build/evidence/`.

## Procedure
1. Run `python scripts/verify.py --fix` (applies ruff fixes and formatting first, then runs every gate).
2. Read the gate table it prints (also in `build/evidence/summary.md`). For each `FAIL`, open its log in
   `build/evidence/logs/<gate>.log` and fix the cause:

   | Gate | Typical cause | Fix |
   |---|---|---|
   | lint | ruff rule (bugbear, simplify, pytest style) | fix the code; `# noqa` only with a reason |
   | format | unformatted file | `python -m ruff format .` |
   | mypy | missing annotation, `Optional` not narrowed, `Any` returned | annotate or narrow; never `# type: ignore` |
   | pyright | same engine as Pylance: unknown attribute, union access | narrow with `isinstance` or `assert x is not None` |
   | tests | failing test or coverage below the minimum | fix the code (or the test if the requirement changed) |
   | eval | retrieval gate missed | skill `retrieval-evaluation` |
   | trace | a requirement without a passing test, or an unknown id | add the test or the requirement row |
3. Re-run until the verdict is `PASS`. Iterate faster with focused commands, e.g.
   `python -m pytest tests/test_kgraph.py -q`, `python -m mypy`, `python -m pyright --pythonpath <venv python>`.
4. SQL or dialect changes: also run the `cross-engine-testing` skill (`--require-engines`).
5. Quote the final gate table in your report or evidence record. Name skipped gates and why they were skipped.

## Notes
- The coverage minimum and the engine list live at the top of `scripts/verify.py`; the eval gates in
  `evals/retrieval_cases.yaml`. Raising them is welcome; lowering needs an ADR.
- `build/` is ignored by git; commit the summary through an evidence record, not the folder.
