# Review: Mermaid runtime flow syntax

| | |
|---|---|
| Date | 2026-11-01 |
| Verdict | Changes requested: fresh required gate evidence is missing |
| Reviewed tree | Uncommitted changes based on `fbddbded16b31ecd4c81fc44b18ced84c569c32e` |
| Scope | `docs/architecture/flows.md`, `CHANGELOG.md`, `docs/evidence/2026-11-01-mermaid-runtime-flows.md` |
| Evidence | [Mermaid runtime flows](../evidence/2026-11-01-mermaid-runtime-flows.md) |

Author disposition: the full-suite omission is accepted for this Markdown-only correction under the
documentation-only validation rule. Focused before/after Mermaid parsing and browser rendering cover the
changed artifact; Python gates do not parse these diagrams. The reviewer's original verdict is retained above;
no full-gate success or subsequent reviewer approval is claimed.

## Findings and resolutions

| Severity | File:line | Issue | Proposed fix | Resolution |
|---|---|---|---|---|
| Major | `docs/evidence/2026-11-01-mermaid-runtime-flows.md:64` | No fresh `scripts/verify.py` evidence covers this tree. The existing summary is dated 2026-10-30 and identifies `9d65b35c13fa + 26 uncommitted file(s)`, not this snapshot. The checklist's fresh-verification approval prerequisite remains unmet despite the bounded documentation-only scope. | Run `python scripts/verify.py` on the reviewed snapshot and copy its passing gate table and snapshot identification into the evidence record before approval. | Answered by author: omission accepted for a documentation-only change under the documentation-only validation rule; focused Mermaid checks passed, and full gates remain explicitly unverified. |

No high-confidence defect was found in the Mermaid escape or changelog. The verdict concerns missing required
verification, not a demonstrated runtime regression.

## Independent checks

- Read all scoped changed hunks, the complete flows document and evidence record, and surrounding changelog.
  Staged scoped diff was empty; the evidence record was untracked and reviewed in full.
- Followed [the checklist](checklist.md), documentation/evidence instructions and evidence-driven process.
- Reproduced the evidence's local bundled-Mermaid parser check, additionally loading the original document with
  `git show HEAD:docs/architecture/flows.md`. Exit 0: original diagram 1 failed with `Parse error on line 17`,
  `got 'NEWLINE'`; original diagrams 2-6 passed; all six edited diagrams passed.
- `git diff --check -- docs/architecture/flows.md CHANGELOG.md` exited 0. Only line-ending conversion warnings
  were printed; this was not the parent's final repository-wide whitespace check.
- `git rev-parse HEAD` matched the evidence record's base SHA. Read `build/evidence/summary.md`; its date and
  snapshot identity establish the finding above, not current gate success.

## Checklist disposition

- **Correctness and error behavior:** the sole flow-source edit replaces the message's literal semicolon with
  `#59;`. Independent before/after parsing confirms the reported parser failure and correction. No runtime
  behavior or error-message implementation changed.
- **SQL safety, privacy and portability:** no executable SQL, guards, time limits, sensitive-column handling,
  dialect logic or MCP inputs changed. No credentials were found in the scoped changes. Database-engine runs
  are not relevant to the Mermaid syntax correction.
- **Typing, requirements and tests:** no package code, dependencies or runtime requirements changed.
  The focused parser reproduction supplies negative and positive evidence for the documentation defect.
- **Retrieval and knowledge:** unaffected; no retrieval evaluation or derived-knowledge regeneration is needed
  for the escape.
- **Documentation and ADRs:** changelog updated under Unreleased; links and scope are consistent. No significant
  architectural decision requiring an ADR was introduced.
- **Evidence:** snapshot and omitted checks are explicit. Fresh full-gate evidence remains missing.

## Gaps and risks

- Browser rendering and exact DOM label preservation were not independently rerun. The author's evidence
  reports six SVGs, all parse/render flags true and `labelPreserved: true`, using the same installed bundle.
  Its browser harness is described but not included as a rerunnable command.
- The parent reports an intermediate Node-only label assertion failing on Mermaid's internal entity
  placeholders, followed by a successful real-browser assertion. That intermediate check does not establish
  a rendered-label defect; the parser-only reproduction does not itself prove displayed text.
- The original VS Code Markdown preview was not reopened; this limitation is already disclosed in evidence.
- No full Python suites, engine tests, retrieval evaluation or CI were run by this reviewer.
- Final `docs/status.md` linking and final whitespace validation remain with the parent, outside this scope.
