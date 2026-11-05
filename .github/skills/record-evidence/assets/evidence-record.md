# Evidence: <title>

| | |
|---|---|
| Date | YYYY-MM-DD |
| Commit | `<sha>` (or "uncommitted working tree based on `<sha>`") |
| Requirements | REQ-..., REQ-... |
| Review | [docs/reviews/YYYY-MM-DD-slug.md](../reviews/YYYY-MM-DD-slug.md) |
| CI run | <url or "not run"> |

## Change

What changed and why, in three to five sentences. Link the ADR when there is one.

## Verification

Command: `python scripts/verify.py [--require-engines]`

<paste the gate table from build/evidence/summary.md>

### Requirements

<paste the rows of build/evidence/traceability.md for the requirement IDs above>

### Retrieval evaluation (when retrieval is affected)

| Embedder | Before | After | Without knowledge graph |
|---|---|---|---|
| none (BM25) | full x/24, recall y | | |
| fastembed (`--embedder kb`) | | | |

### Cross-engine (when SQL or dialect code is affected)

| Engine | Version | Outcome |
|---|---|---|
| SQLite | | |
| DuckDB | | |
| PostgreSQL | | |
| MariaDB | | |
| SQL Server | | |

## Gaps and risks

- What was not verified and why; known limitations; follow-ups (with issue links).
