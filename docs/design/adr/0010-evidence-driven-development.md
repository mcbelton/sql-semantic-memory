# 0010. Evidence-driven development with requirement traceability

- Status: Accepted
- Date: 2026-10-30
- Requirements: QA-LINT, QA-TYPES, QA-TESTS, QA-COVERAGE, QA-ENGINES, QA-TRACE

## Context

Most changes are made by AI agents. Agents are fast and confident, and confident claims ("all tests pass", "works
on all engines") are only as good as the evidence behind them. This repository must stay trustworthy when many
autonomous sessions change it.

## Options

1. **Conventional CI only**: tests run, but nothing ties tests to requirements, and claims in PRs are unchecked.
2. **Evidence-driven development**: requirement IDs, tests marked with them, one verification command that runs
   every gate and writes a machine-readable evidence bundle, committed evidence and review records, and a team of
   agents with separated roles (implementer ≠ reviewer ≠ evidence auditor).

## Decision

We use option 2:

- [docs/requirements.md](../../requirements.md) is the single source of requirement IDs; tests carry
  `@pytest.mark.req`; unknown IDs fail the run.
- `scripts/verify.py` runs ruff, ruff format, mypy (strict), pyright, pytest with coverage (≥ 85%), the retrieval
  eval and the traceability check, and writes `build/evidence/`. CI runs the same script and uploads the bundle.
- Every change ends with an evidence record (`docs/evidence/`) and a review record (`docs/reviews/`).
- Agent roles, skills and instructions live in `.github/` and `AGENTS.md`.

## Consequences

- "Done" is checkable by anyone, including another agent.
- Some overhead per change (records); gates can only be lowered through an ADR.

## Verification

The `trace` gate (every `REQ-*` proven by a passing test), CI on every push and pull request, and the evidence
auditor's check of each evidence record.
