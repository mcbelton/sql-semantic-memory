---
name: fix-bug
description: "Fix a bug red-to-green: reproduce it with a failing test, fix it, prove it with verify.py, and record the evidence."
disable-model-invocation: true
argument-hint: "Bug description, error message or issue link"
---
Fix the reported bug with proof:

1. Reproduce: write the smallest test that fails **for the reported reason**; mark it with the requirement it
   violates (`@pytest.mark.req(...)`). Run it and keep the failing output.
2. Find the root cause (not the symptom). Explain it in two sentences with file and line.
3. Fix it with the smallest change; run the new test (green) and the module's tests.
4. Run `python scripts/verify.py --fix`. SQL or dialect bugs: run the
   [cross-engine-testing](../skills/cross-engine-testing/SKILL.md) skill too.
5. Report: root cause, fix, failing-then-passing test node id, gate table, anything not verified.
