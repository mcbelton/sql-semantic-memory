---
name: write-adr
description: 'Write an Architecture Decision Record (ADR) for sqlmem in docs/design/adr: context, options, decision, consequences and how the decision is verified. Use for new dependencies, storage or format changes, retrieval or ranking policy, security or safety boundaries, supported engines, lowering a quality gate, or superseding an earlier decision.'
argument-hint: 'Decision title'
---

# Write an ADR

## Procedure
1. List existing ADRs in `docs/design/adr/` and take the next number (four digits).
2. Copy `docs/design/adr/0000-template.md` to `docs/design/adr/<NNNN>-<kebab-title>.md`.
3. Fill every section:
   - **Context**: the forces (requirements, quality attributes, constraints), with links to requirement IDs.
   - **Options**: at least two real alternatives with pros and cons.
   - **Decision**: one paragraph, active voice ("We ...").
   - **Consequences**: what gets easier, what gets harder, what is now forbidden.
   - **Verification**: the tests, eval gates, measurements or reviews that prove the decision holds. An ADR without
     verification is an opinion.
4. Status starts as `Proposed`; it becomes `Accepted` when the change merges. To change an accepted decision,
   write a new ADR with `Supersedes: NNNN` and set the old one to `Superseded by NNNN` (the only edit allowed).
5. Add the ADR to the index in `docs/design/README.md`.
