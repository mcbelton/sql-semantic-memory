---
name: record-evidence
description: 'Write the evidence record for a change in docs/evidence: commit, gate table from scripts/verify.py, requirement traceability, eval and cross-engine results, review outcome, gaps and risks. Use when a change is complete, for pull request descriptions, release notes, or when asked to document proof.'
argument-hint: 'Slug for the record, e.g. composite-keys'
---

# Record evidence

An evidence record is the durable, reviewable proof that a change meets its requirements. It is committed with
(or right after) the change it proves.

## Procedure
1. Make sure the evidence is fresh and belongs to the commit being documented:
   `git rev-parse HEAD`, then `python scripts/verify.py` (and `--require-engines` for SQL or dialect changes).
2. Create `docs/evidence/<YYYY-MM-DD>-<slug>.md` from [the template](./assets/evidence-record.md).
3. Fill it **by copying**, not paraphrasing:
   - the gate table from `build/evidence/summary.md`;
   - the rows of `build/evidence/traceability.md` for the requirement IDs this change touches;
   - eval numbers from `build/evidence/eval-retrieval.json` (and the `--embedder kb` run when retrieval changed);
   - engines and outcomes from the `trace` gate line;
   - the CI run URL when available (`gh run list --limit 1`).
4. Link the review record (`docs/reviews/...`) and summarize findings and their resolution.
5. Under **Gaps and risks**, list everything not verified: engines not run, skipped tests, manual-only checks,
   known limitations.
6. Link the record from the PR description and, for releases, from `CHANGELOG.md`.

## Quality bar
- A reader can re-run every command in the record and get the same verdict.
- No number without a source; no "should", "probably" or "works on my machine".
