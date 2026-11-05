# 0001. Record architecture decisions

- Status: Accepted
- Date: 2026-10-30
- Requirements: QA-TRACE

## Context

The project is developed largely by AI agents working in short sessions. Without a written record, the reasons
behind earlier choices (read-only layers, verification budgets, retrieval policies) are lost between sessions and
get "simplified away".

## Options

1. **No records**: rely on commit messages. Cheap, but rationale is scattered and not discoverable by agents.
2. **Architecture Decision Records** in `docs/design/adr/`, one Markdown file per decision, linked from an index.

## Decision

We record every significant decision as an ADR (template `0000-template.md`), including how the decision is
verified. Accepted ADRs are immutable except for their status; changes are new ADRs that supersede old ones.

## Consequences

- Agents and humans find the rationale next to the code; `architect` and `reviewer` agents check new changes
  against existing ADRs.
- A small writing cost per significant change.

## Verification

Review checklist item "decision recorded" ([checklist](../../reviews/checklist.md)); the `write-adr` skill.
