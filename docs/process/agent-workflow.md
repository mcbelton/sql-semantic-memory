# Agent workflow

The repository ships an agent team for GitHub Copilot (VS Code agent mode, Copilot CLI and the Copilot coding agent).
The definitions live in `.github/` and are discovered automatically when this repository is the workspace folder
(or one folder of a multi-root workspace).

## Team

| Agent | File | Role | Can edit | Hands off to |
|---|---|---|---|---|
| orchestrator | [orchestrator.agent.md](../../.github/agents/orchestrator.agent.md) | plans, delegates, enforces the definition of done | nothing | architect, implementer |
| architect | [architect.agent.md](../../.github/agents/architect.agent.md) | requirements, ADRs, architecture docs | `docs/` | implementer |
| implementer | [implementer.agent.md](../../.github/agents/implementer.agent.md) | tests first, code, verify | code, tests, docs | reviewer |
| test-engineer | [test-engineer.agent.md](../../.github/agents/test-engineer.agent.md) | test design, cross-engine runs, eval cases | `tests/`, `evals/` | — |
| reviewer | [reviewer.agent.md](../../.github/agents/reviewer.agent.md) | independent review, review record | `docs/reviews/` | implementer, evidence-auditor |
| evidence-auditor | [evidence-auditor.agent.md](../../.github/agents/evidence-auditor.agent.md) | checks every claim, writes the evidence record | `docs/evidence/` | — |
| kb-curator | [kb-curator.agent.md](../../.github/agents/kb-curator.agent.md) | knowledge graph, semantics, memories via MCP | `kb/*/` curated files | — |

## Skills (procedures loaded on demand)

`verify-change`, `record-evidence`, `cross-engine-testing`, `add-database-dialect`, `knowledge-graph-curation`,
`retrieval-evaluation`, `write-adr`, `code-review`, `release` — in `.github/skills/`.

## Prompts (slash commands)

`/implement-requirement`, `/fix-bug`, `/review-changes`, `/evidence-report`, `/new-adr`, `/curate-knowledge` — in
`.github/prompts/`.

## Always-on and file-scoped rules

[AGENTS.md](../../AGENTS.md) (always) and `.github/instructions/*.instructions.md` (Python, tests, docs,
knowledge base, evidence, CI) applied by file pattern.

## Hook

`.github/hooks/format-python.json` (Copilot hook format, also read by VS Code) runs `scripts/hooks/format_edited.py`
after each tool call. For edit tools only, the Python files named in the tool's arguments (or `apply_patch` headers)
are lint-fixed and formatted with ruff; files outside the repository or in excluded folders (`.venv`, `build`, `kb`)
are never touched. Findings ruff cannot fix are returned as `additionalContext`, so the agent sees them next to the
tool output. Behavior is pinned by `tests/test_hooks.py`.

## Typical session

1. Pick the **orchestrator**, describe the issue. It returns a plan with requirement IDs and the evidence expected.
2. Hand off to the **architect** (requirements, ADR) and then the **implementer** (tests first, code,
   `scripts/verify.py`).
3. Hand off to the **reviewer**: review record; findings go back to the implementer.
4. Finish with the **evidence-auditor**: evidence record; open a PR using the template, CI attaches the evidence
   bundle.

## Copilot coding agent (GitHub)

Assign an issue to Copilot: `.github/workflows/copilot-setup-steps.yml` prepares Python and the dev tools, and the
agent follows `AGENTS.md`. Its pull request must contain the gate table and links to the review and evidence
records (PR template).

## Opening the repository in VS Code

Agents, skills, prompts and hooks are discovered in the open workspace folder(s). Open this repository folder
directly, or add it as a folder of a multi-root `.code-workspace` when it lives next to other repositories.
