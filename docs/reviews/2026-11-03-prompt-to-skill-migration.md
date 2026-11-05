# Review: VS Code prompt-to-skill migration

## Verdict

**Changes requested.** Reviewed the uncommitted migration on base commit
`f947272df22e3f57ee4c81800603c6c25e97c42a`: six deleted prompt files and their six untracked replacement
skills. No migration fixes were applied during this review.

## Findings

| # | Severity | Location | Issue and impact | Proposed fix | Resolution |
|---|---|---|---|---|---|
| 1 | major | [curate-knowledge, line 8](../../.github/skills/curate-knowledge/SKILL.md), and all five other migrated skills | All nine Markdown references retain paths relative to the old `.github/prompts/` directory. From a skill's new subdirectory they resolve to nonexistent files, preventing linked procedures, requirements and review instructions from loading through those references. All nine targets existed at their old locations. | Rebase sibling skill links to `../<skill>/SKILL.md`, repository documentation links to `../../../docs/...`, and the Python instructions link to `../../instructions/python.instructions.md`. Validate every target from its containing file. | Open |
| 2 | major | [review-changes, lines 2-6](../../.github/skills/review-changes/SKILL.md), and all five other migrated skill headers | Every original prompt selected a custom agent with `agent:`; none of the replacement skills preserves that routing. Invoking a skill supplies instructions to the current agent rather than selecting the former role. In particular, `/review-changes` no longer selects the reviewer with its review-only editing constraints and handoffs; the evidence audit and curation commands likewise lose their role-specific constraints and tool configurations. | Retain agent-routed prompt entry points, or explicitly delegate each skill's execution to its former custom agent. Adding prompt-only `agent:` metadata to a skill is not an equivalent fix. | Open |

### Affected references

| Skill | Lines | Invalid targets |
|---|---|---|
| [curate-knowledge](../../.github/skills/curate-knowledge/SKILL.md) | 8 | `../skills/knowledge-graph-curation/SKILL.md` |
| [evidence-report](../../.github/skills/evidence-report/SKILL.md) | 7 | `../skills/record-evidence/SKILL.md` |
| [fix-bug](../../.github/skills/fix-bug/SKILL.md) | 14 | `../skills/cross-engine-testing/SKILL.md` |
| [implement-requirement](../../.github/skills/implement-requirement/SKILL.md) | 9, 11 | `../../docs/requirements.md`, `../instructions/python.instructions.md` |
| [new-adr](../../.github/skills/new-adr/SKILL.md) | 7, 9 | `../skills/write-adr/SKILL.md`, `../../docs/design/README.md` |
| [review-changes](../../.github/skills/review-changes/SKILL.md) | 8 | `../skills/code-review/SKILL.md`, `../../docs/reviews/checklist.md` |

### Removed agent selections

| Command | Original agent |
|---|---|
| `/curate-knowledge` | `kb-curator` |
| `/evidence-report` | `evidence-auditor` |
| `/fix-bug` | `implementer` |
| `/implement-requirement` | `implementer` |
| `/new-adr` | `architect` |
| `/review-changes` | `reviewer` |

## Evidence

- `git status --short`, `git diff --stat`, `git diff --cached --stat`: six deleted prompts and six untracked
  replacement directories; no staged changes.
- `git diff -- .github\prompts`: inspected all original headers and bodies.
- An inline Python audit using `.\.venv\Scripts\python.exe -` parsed each replacement's YAML with
  `yaml.safe_load`, compared its body with `git show HEAD:.github/prompts/<name>.prompt.md`, checked names,
  descriptions, argument hints and `disable-model-invocation`, and resolved each Markdown target against both
  its new containing directory and its original directory. Exact summary:

  ```text
  SUMMARY: 6/6 valid headers and identical bodies; 9/9 broken links; 6 agent selectors removed
  ```

- `git diff --check`: passed before writing this review record.
- Agent routing impact was checked against the original prompt `agent:` fields, the
  [agent workflow](../process/agent-workflow.md), and the
  [reviewer](../../.github/agents/reviewer.agent.md),
  [evidence auditor](../../.github/agents/evidence-auditor.agent.md) and
  [curator](../../.github/agents/kb-curator.agent.md) definitions.

## Gaps and risks

- No application Python, SQL, retrieval logic or knowledge-base contents changed. Full `scripts/verify.py`,
  engine tests and retrieval evaluations were not run for this customization-only review; no runtime gate
  result is claimed.
- Live VS Code discovery and slash-command execution were not tested. Static metadata validity does not
  establish that the six new skills have been loaded into the running session.
- [The agent workflow](../process/agent-workflow.md) still describes the six commands as prompt files under
  `.github/prompts/`; update that description if the migration is retained.
