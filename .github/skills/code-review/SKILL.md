---
name: code-review
description: 'Review a sqlmem change for correctness, SQL safety (read-only guard, time limits), privacy (sensitive columns, secrets), dialect portability, typing, error-message quality, tests mapped to requirements, docs and evidence; classify findings and write the review record in docs/reviews. Use before merging, for pull requests, or when asked to review code.'
argument-hint: 'Diff range, branch or files'
---

# Code review

## Procedure
1. Collect the diff: `git diff --stat` and `git diff` (or `git diff main...HEAD` for a branch). Read each hunk in
   context; open callers of changed functions (`grep`, Pylance references).
2. Walk the [review checklist](../../../docs/reviews/checklist.md). The high-risk areas in this codebase:
   - `sqlmem/db.py` (`check_readonly`, `make_engine`, `time_limit`, `run_select`): any change here needs negative
     tests (blocked statements) and a cross-engine run.
   - `sqlmem/scan.py`: never store values of sensitive columns; sampling must stay bounded.
   - `sqlmem/kgraph.py`: generated SQL must pass the guard and the verification budget.
   - `sqlmem/render.py` (`select_tables`, `render_context`): retrieval changes need eval numbers.
   - `sqlmem/mcp_server.py`: inputs from agents are untrusted; errors must be actionable, not stack traces.
3. Confirm the evidence: fresh `build/evidence/summary.md` for the reviewed commit, traceability for the touched
   requirements, eval and engine results where required.
4. Classify every finding: **blocking**, **major**, **minor**. Give file:line, why it matters, and a concrete fix.
5. Write `docs/reviews/<YYYY-MM-DD>-<slug>.md` with the verdict, the findings table and their resolutions.

## Output
Verdict, findings table, link to the review record. No praise padding; no style nits that ruff enforces.
