# Review records

One file per reviewed change: `YYYY-MM-DD-<slug>.md` with the verdict, the findings table (severity, location,
issue, resolution) and the evidence the review was based on. Written by the `reviewer` agent (skill `code-review`)
against the [checklist](checklist.md). Findings are never deleted; they are resolved (fixed in a commit) or
accepted with a reason.

| Date | Change | Verdict |
|---|---|---|
| 2026-10-30 | [Repository hardening: typing, gates, traceability, retrieval fix](2026-10-30-repository-hardening.md) | approved after fixes |
