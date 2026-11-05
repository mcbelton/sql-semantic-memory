## What and why

<!-- Two to five sentences. Link the issue and the ADR if there is one. -->

## Requirements

<!-- IDs from docs/requirements.md this change adds, changes or proves, e.g. REQ-KG-06. -->

## Evidence

<!-- Paste the gate table from build/evidence/summary.md (python scripts/verify.py). -->

| Gate | Verdict | Summary |
|---|---|---|
| | | |

- Evidence record: `docs/evidence/...`
- Review record: `docs/reviews/...`
- Retrieval eval before → after (if search, ranking, context or knowledge changed):
- Engines run (if SQL, dialect, scan or guard changed):

## Definition of done

- [ ] `python scripts/verify.py` passes on this commit (CI green)
- [ ] every new/changed behavior has a requirement row and tests marked with its ID
- [ ] eval numbers reported / cross-engine run done where required (or N/A)
- [ ] README / docs / CHANGELOG updated; ADR for significant decisions
- [ ] independent review done, findings resolved
- [ ] no secrets, no derived files (`index.db`, `build/`) committed

## Gaps and risks

<!-- What was not verified, and why. -->
