---
name: review-changes
description: "Independent review of the current changes against the review checklist, with a written review record."
disable-model-invocation: true
argument-hint: "Optional: diff range or branch (default: uncommitted changes)"
---
Review the changes (default: `git diff` plus `git diff --staged`; or the range given) with the
[code-review](../skills/code-review/SKILL.md) skill and [the checklist](../../docs/reviews/checklist.md).
Run `python scripts/verify.py` for the reviewed tree. Write the review record in `docs/reviews/` and return the
verdict with the findings table.
