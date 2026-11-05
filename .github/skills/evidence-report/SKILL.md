---
name: evidence-report
description: "Audit the evidence for a change and write the evidence record in docs/evidence."
disable-model-invocation: true
argument-hint: "Slug for the record, e.g. polymorphic-relations"
---
Audit the current change with the [record-evidence](../skills/record-evidence/SKILL.md) skill: run
`python scripts/verify.py` (with `--require-engines` if SQL or dialect code changed and engines are running), check
traceability for the touched requirements, compare every claim in the PR description, CHANGELOG and docs with the
evidence, and write `docs/evidence/<date>-<slug>.md`. Return the audit verdict and any unsupported claims.
