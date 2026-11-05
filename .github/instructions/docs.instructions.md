---
description: "Use when writing or updating documentation: README, architecture, design docs, ADRs, process docs, diagrams."
applyTo: ["docs/**/*.md", "README.md", "CONTRIBUTING.md"]
---
# Documentation

- README is for users (install, use, configure, supported databases). Design rationale goes to `docs/design/`,
  structure and flows to `docs/architecture/`, how we work to `docs/process/`.
- Diagrams are Mermaid in Markdown so they are reviewable in diffs; keep each diagram under ~25 nodes.
- Use relative links between docs and link to code by path (`sqlmem/kgraph.py`) rather than copying code.
- Numbers in docs (eval results, test counts, engine versions) must come from an evidence record or
  `build/evidence/` output of the same change; cite the record.
- A significant decision gets an ADR: copy `docs/design/adr/0000-template.md`, take the next number, and link it
  from `docs/design/README.md`. Never rewrite an accepted ADR; supersede it with a new one.
- Update `CHANGELOG.md` (Unreleased section) for user-visible changes.
