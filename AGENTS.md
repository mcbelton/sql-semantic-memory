# AGENTS.md

`sqlmem` builds semantic knowledge, long-term memory and a data-verified knowledge graph for an entire SQL
database, and serves it to AI agents through a CLI and an MCP server. This repository is developed with
**evidence-driven development**: no change is done until it is proven by tests, measurements and a review, and the
proof is written down. Read [docs/process/evidence-driven-development.md](docs/process/evidence-driven-development.md)
once; this file is the short version.

## Map

| Path | What |
|---|---|
| `sqlmem/` | the package: `scan` (facts) → `model` (+ `semantic.yaml`) → `render`/`store` (docs, chunks, hybrid index) → `kb` (facade) → `cli` / `mcp_server`; `kgraph` (knowledge graph), `llm`, `enrich`, `memory`, `db` (read-only guard, time limits) |
| `tests/` | pytest; every test carries `@pytest.mark.req("REQ-...")` |
| `evals/` | retrieval evaluation on the AdventureWorks example KB, with gates |
| `scripts/verify.py` | **the** verification command; writes evidence to `build/evidence/` |
| `scripts/engines.ps1`, `compose.yaml` | PostgreSQL, MariaDB, SQL Server for cross-engine tests |
| `kb/adventureworks2025/` | example knowledge base (eval fixture); `index.db` is derived and not committed |
| `docs/status.md` | current state, next steps and how to resume: read it first, update it last |
| `docs/requirements.md` | requirement IDs (single source of truth for traceability) |
| `docs/architecture/`, `docs/design/adr/` | architecture views and decision records |
| `docs/evidence/`, `docs/reviews/` | committed evidence records and review records |
| `.github/agents/`, `.github/skills/`, `.github/instructions/`, `.github/prompts/` | agent team, procedures, coding rules, task prompts |

## Commands

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -e ".[local,mcp,llm,duckdb,dev]"   # Linux/macOS: .venv/bin/pip
python scripts/verify.py                  # lint, format, mypy, pyright, tests+coverage, eval, traceability
python scripts/verify.py --fix            # ruff fixes + formatting first
python -m pytest tests/test_kgraph.py -q  # focused tests while iterating
python -m evals.run_retrieval --embedder kb --ablate-kg   # eval with fastembed, as the KB is configured
.\scripts\engines.ps1 start; .\scripts\engines.ps1 env | Invoke-Expression; python scripts/verify.py --require-engines
```

Stop the VS Code MCP server before reinstalling: pip rewrites `sqlmem.exe`, which is locked while it runs.

## Rules

1. **Evidence, not claims.** Every statement that something works, is fixed or is faster cites evidence: a test node
   id, a `build/evidence/summary.md` gate line, an eval number, or a command with its output. Never write "should
   work".
2. **Requirements first.** New or changed behavior gets a row in `docs/requirements.md` and tests marked with its ID.
   Unknown IDs fail the test run; unproven requirements fail `verify.py`.
3. **Red, then green.** For a bug, first add a test that fails for the reason in the report, then fix it.
4. **Gates only go up.** Lint, types (mypy strict + pyright), coverage (≥ 85%) and eval gates must pass. Lowering a
   gate needs an ADR in `docs/design/adr/`.
5. **Retrieval changes are measured.** Anything touching search, ranking or context runs the eval (BM25 and the KB's
   embedder) and reports before/after numbers.
6. **Safety is not negotiable.** All SQL goes through `check_readonly` and `run_select` time limits; never store
   values of sensitive columns; never commit secrets, connection strings with passwords, or `index.db`.
7. **Decisions are recorded.** Architecture-relevant choices get an ADR (template in `docs/design/adr/`).
8. **Independent review.** Changes are reviewed by the `reviewer` agent (fresh context) against
   [docs/reviews/checklist.md](docs/reviews/checklist.md); findings are fixed or answered.
9. **Write the evidence record.** Finish with `docs/evidence/<date>-<slug>.md` (template in the `record-evidence`
   skill).
10. **Leave a handoff.** Start every session by reading [docs/status.md](docs/status.md); before it ends, update it
    (state, next steps, anything unverified) and commit it with the work, so the next session can resume.

## Definition of done

- [ ] `python scripts/verify.py` passes; summary pasted into the evidence record and the PR
- [ ] requirements and tests updated together; traceability shows every `REQ-*` proven
- [ ] eval numbers reported for retrieval-affecting changes; cross-engine run for SQL/dialect changes
- [ ] docs updated (README for users, `docs/` for design); ADR for significant decisions
- [ ] review record with all findings resolved
- [ ] no secrets, no derived files (`index.db`, `build/`) committed

## Code conventions

Python ≥ 3.10, fully typed (`mypy --strict`), ruff-formatted (line length 120). Prefer small pure functions, explicit
errors with actionable messages, and no new dependencies without an ADR. Details: `.github/instructions/`.
