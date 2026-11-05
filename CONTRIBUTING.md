# Contributing

Thanks for improving sqlmem. This repository uses **evidence-driven development**: a change is done when it is proven
by tests and measurements, reviewed independently, and recorded. AI agents and people follow the same rules
([AGENTS.md](AGENTS.md), [process](docs/process/evidence-driven-development.md)).

## Set up

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[local,mcp,llm,duckdb,dev]"     # Linux/macOS: .venv/bin/pip
python scripts/verify.py                                          # all gates must pass on a fresh clone
```

Recommended VS Code extensions are listed in `.vscode/extensions.json` (Python, Pylance, Ruff, Mypy). Formatting
and import sorting happen on save; Pylance and the Mypy extension read their settings from `pyproject.toml`.

## Make a change

1. Open or pick an issue. Agree on the requirement rows ([docs/requirements.md](docs/requirements.md)).
2. Write tests first and mark them `@pytest.mark.req("REQ-...")`.
3. Implement; iterate with `python -m pytest <file> -q`.
4. Run `python scripts/verify.py --fix`; for SQL/dialect work also the cross-engine run
   (`.github/skills/cross-engine-testing/SKILL.md`); for retrieval work the eval with `--embedder kb`.
5. Update README/docs/CHANGELOG; write an ADR for significant decisions.
6. Get a review (the `reviewer` agent or a person) and write the evidence record (`docs/evidence/`).
7. Open a pull request with the template filled in. CI must be green.

## Commit messages

Imperative mood, scoped prefix (`scan:`, `kgraph:`, `retrieval:`, `docs:`, `ci:`, `evidence:`), body explaining
*why*. Reference requirement IDs and the evidence record.

## Never commit

Secrets or connection strings with passwords, `kb/**/index.db`, `build/`, local databases, `.venv/`.
