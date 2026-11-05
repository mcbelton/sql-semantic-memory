---
description: "Use when writing evidence records, review records, verification reports or pull request descriptions."
applyTo: ["docs/evidence/**", "docs/reviews/**"]
---
# Evidence and review records

- Evidence records live in `docs/evidence/YYYY-MM-DD-<slug>.md` and follow the template of the `record-evidence`
  skill. Review records live in `docs/reviews/YYYY-MM-DD-<slug>.md`.
- Every claim cites its proof: a gate line from `build/evidence/summary.md`, a test node id, an eval number from
  `eval-retrieval.json`, a commit SHA or a CI run URL. Copy numbers; never round them up or restate from memory.
- State the commit the evidence was produced on. Evidence for an uncommitted tree says so explicitly.
- Record what was *not* verified (engines not run, skipped tests, manual checks) under "Gaps and risks".
- Review findings keep their severity and resolution (fixed in commit X / accepted because Y). Do not delete
  findings.
