---
name: release
description: 'Release a new sqlmem version: bump the version in pyproject.toml, finalize CHANGELOG.md, verify on all engines, write the release evidence record, tag and publish a GitHub release with the evidence attached. Use when asked to cut, tag or publish a release.'
argument-hint: 'Version, e.g. 0.3.0'
---

# Release

## Procedure
1. Start from a clean, up-to-date `main`: `git status` shows nothing; CI is green for `HEAD`
   (`gh run list --branch main --limit 1`).
2. Bump `version` in `pyproject.toml` (semantic versioning: breaking change → minor while < 1.0).
3. Move the `Unreleased` entries in `CHANGELOG.md` under the new version with today's date.
4. Verify everything: `.\scripts\engines.ps1 start`, `.\scripts\engines.ps1 env | Invoke-Expression`,
   `python scripts/verify.py --require-engines`, and the fastembed eval
   `python -m evals.run_retrieval --embedder kb --ablate-kg`.
5. Write `docs/evidence/<date>-release-<version>.md` (skill `record-evidence`), commit
   ("release: <version>") and push; wait for CI (`gh run watch`).
6. Tag and publish:
   `git tag -a v<version> -m "sqlmem <version>"`, `git push origin v<version>`,
   `gh release create v<version> --notes-file <changelog section> build/evidence/summary.md`.
7. Stop the engines (`.\scripts\engines.ps1 stop`).
