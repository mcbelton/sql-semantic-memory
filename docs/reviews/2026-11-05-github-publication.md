# Independent review: GitHub.com publication

- Date: 2026-11-05 (UTC)
- Final verdict (scope 2, public MIT publication, after recheck): **approve**. All six findings are resolved
  (see "Scope 2 recheck"); no findings remain. Approval covers the scrubbed tree and the documented
  publication procedure, not the not-yet-executed push/visibility outcomes.
- Initial scope 2 verdict: changes requested (six findings, kept below as history).
- Scope 1 verdict (initial publication and HTTPX dependency declaration): **approve**, preserved below as history.
- Requirements: REQ-AMEM-03, QA-TYPES, QA-TESTS.
- Evidence record: [GitHub publication](../evidence/2026-11-05-github-publication.md).

## Scope 2: public MIT publication

### Scope and baseline

Reviewed only the working-tree changes against HEAD `347502a` (`git diff` plus untracked `LICENSE`),
with surrounding content:

- `LICENSE` (new): MIT, `Copyright (c) 2026 Belton Albert`.
- `pyproject.toml`: build requirement `setuptools>=77`; `license = "MIT"`, `license-files = ["LICENSE"]`.
- `README.md`: public repository/license line, clone instructions without an access caveat, License section.
- `SECURITY.md`, `.github/ISSUE_TEMPLATE/config.yml`: GitHub private vulnerability reporting link.
- `CHANGELOG.md`: license addition and public-repository entry.
- `docs/status.md`: removes previous-hosting URLs, the previous account name, local session identifiers and the
  historical-hosting evidence section.
- `docs/evidence/2026-11-01-mermaid-runtime-flows.md`, `docs/evidence/2026-11-03-duckdb-architecture-documentation.md`:
  an account-specific local path segment replaced with a `<user>` placeholder.
- `docs/evidence/2026-11-05-github-publication.md`: public publication, license metadata and history-action evidence.

Owner-confirmed context (from the task, not independently verifiable): personal project, publication authorized,
MIT selected, no previous-hosting/account content wanted in Git history. Approved history action: delete the
still-private repository (removing commit `347502a` and its Actions runs), recreate it private, create a fresh
orphan root commit from the scrubbed tree, push it, make it public and enable private vulnerability reporting.
This review did not commit, push or change any GitHub setting.

### Findings

| # | Severity | File:line | Issue | Proposed fix |
|---|---|---|---|---|
| 1 | major | local refs `refs/agents/*/checkpoints/turn/{0,1,2}` (`git for-each-ref`) | Three local agent-checkpoint refs exist besides `main`. Their ref names contain a local session identifier; the commits of turns 0 and 1 each contain 3 files with previous-hosting/account content, and turn 2 descends from them. A `git push --mirror` (or any refspec beyond `main`) to the recreated repository would publish exactly the history the owner wants removed. | Push only the orphan branch with an explicit refspec (`git push -u origin main`); never `--mirror`/`refs/*`. Before pushing, assert `git rev-list --count main` is `1` and `git grep -i` over `main` has no previous-hosting/account/session matches. After pushing and before visibility changes, assert `git ls-remote origin` lists only `HEAD` and `refs/heads/main` at the orphan SHA. Optionally delete the local checkpoint refs after publication. |
| 2 | major | `docs/evidence/2026-11-05-github-publication.md:80-84`, `:92-93` | Results of history actions not yet performed are recorded in past tense: deletion/recreation, "only the scrubbed snapshot was pushed", a `gh repo view` result (from the current, to-be-deleted repository) and a scan of "commit metadata" of a clean commit that does not exist yet. At review time the old repository still exists (private, 0 forks, 4 Actions runs) and HEAD is `347502a`. | Delete and recreate first, then run `gh repo view` against the recreated repository and the content/metadata scan against the staged orphan tree/commit, and record those actual outputs before committing. State the remaining steps (push, visibility change, vulnerability-reporting enablement, `ls-remote`) as planned post-commit checks, not results. |
| 3 | major | `docs/evidence/2026-11-05-github-publication.md:99-100`; `docs/status.md:16` | Both say the independent review approved the publication "with no actionable findings"; this review's current verdict is changes requested with the findings listed here. | After fixes, request re-review and quote that record's actual verdict; until then cite scope 1 approval and scope 2 changes requested. |
| 4 | minor | `docs/evidence/2026-11-05-github-publication.md:6` | The Commit row says the checkout had no commits or remotes; the generated summary identifies `347502a28c13 + 10 uncommitted file(s)`, and `347502a` will itself be discarded. | State that verification ran on `347502a` plus 10 uncommitted files, whose resulting tree is the orphan root content (record the orphan SHA in the post-publication handoff). |
| 5 | minor | `SECURITY.md:6`, `.github/ISSUE_TEMPLATE/config.yml:4`; `docs/status.md:72` | The security link only works once private vulnerability reporting is enabled, which happens after the repository becomes public; the handoff's next steps do not include verifying visibility or that setting. | Enable reporting immediately after the visibility change, verify with `gh api repos/mcbelton/sql-semantic-memory/private-vulnerability-reporting` (`enabled: true`) and `gh repo view ... --json visibility`, and add that check to Next steps/post-publication evidence. |
| 6 | minor | `docs/evidence/2026-11-05-github-publication.md:94` | The "70 relative file references" link-validation result predates the new `LICENSE` and vendor-directory links. This review confirmed the new targets exist, but the recorded count was not rerun. | Rerun link validation and update the count, or qualify the sentence as prior to the license links. |

No blocking findings: all gates pass and no code, SQL-safety or privacy defect is introduced by the diff.

### Checklist assessment

- **License and packaging:** `LICENSE` is the standard MIT text with the stated holder. `license = "MIT"` with
  `license-files` is PEP 639 metadata, which needs setuptools 77+; the build requirement was raised accordingly.
  There are no conflicting `License ::` classifiers. README notes that bundled chart assets keep their own
  licenses; eight vendor LICENSE/NOTICE files remain in the wheel.
- **Security reporting:** `SECURITY.md` and the issue-template contact link agree, keep the "not in a public issue"
  instruction and the relevant-scope list. See finding 5 for the enablement ordering.
- **Correctness, SQL safety, typing, dialects:** no executable source, SQL guard, time-limit, sensitive-column or
  dialect code changed. Gates are unchanged and green.
- **Privacy / publishable content:** see "Content scan" below. The scrub edits remove the targeted categories and the
  `<user>` placeholder keeps both reproduction recipes usable with an explicit substitution note.
- **Documentation consistency:** README, CHANGELOG, SECURITY, status and evidence agree on the public MIT target.
  Relative links `LICENSE`, `../LICENSE` (from `docs/status.md`) and `sqlmem/assets/vendor/` resolve.
  Exceptions: findings 2–4 and 6.
- **Commit identity:** repository-local author/committer is the owner's GitHub no-reply address; no
  previous-hosting address in the current commit metadata or message.

### Content scan (tracked and untracked publishable files)

Scanned `git ls-files` plus `git ls-files --others --exclude-standard` (255 files; only `LICENSE` untracked),
case-insensitively, for: the previous-hosting domain, the previous account name (and prefixes), the previous local
session identifiers and session-URI schemes, any UUID outside the generated `kb/` example data, `C:\Users` /
`C:/Users` / `/home/` user paths, `GH_HOST`/`--hostname` usage and generic previous-hosting wording.

- No previous-hosting domain, previous account name or local session identifier remains in any publishable file.
- UUIDs occur only in the generated AdventureWorks KB sample data (row GUIDs).
- The only user-path hits are the two `<user>` placeholders. Remaining `D:\dev\...` paths are generic project
  locations without account names. The only generic previous-hosting wording left in a publishable file was the
  scope 1 text of this review record, neutralized here; other keyword hits were AdventureWorks sample data.
- Remaining vendor references are product names, documentation links, package/image hosts and sample-data XML
  namespaces, not hosting/account details.
- Built wheel and sdist also contain none of these markers.

### Evidence checked (scope 2)

Accepted the existing verification bundle; it was not rerun or overwritten.

- `build/evidence/summary.md`: generated `2026-11-04T19:23:39-08:00`, Windows/Python 3.14.7, commit
  `347502a28c13 + 10 uncommitted file(s)` (the 9 modified files plus `LICENSE`). All seven gates PASS:
  349 passed, 1 skipped (`tests/test_mssql.py`, requires `SQLMEM_MSSQL_ODBC`), 33 warnings, 88% coverage
  (min 85%); BM25 24/24, recall 1.00; 51/51 requirements; engines SQLite and DuckDB passed.
- File timestamps: `LICENSE` and all other scoped edits precede the run, except the publication evidence record
  (documentation-only, written afterwards).
- Exact case-sensitive comparison: all seven gate rows and the REQ-AMEM-03 (22/0/0), QA-TYPES and QA-TESTS rows in
  the evidence record match `summary.md` and `traceability.md`. QA-ENGINES remains partial, as disclosed.
- Independent packaging check: built a copy of the publishable file set in a temporary directory with
  `python -m build` (isolated); wheel and sdist were produced. Metadata 2.4 carries `License-Expression: MIT` and
  `License-File: LICENSE` in both the wheel `METADATA` and sdist `PKG-INFO`; the wheel has
  `dist-info/licenses/LICENSE` and the sdist has `sqlmem-0.2.0/LICENSE`. The temporary directory was removed.
- Read-only GitHub/Git state: `origin` targets the canonical GitHub.com URL; `gh repo view` reports private,
  0 forks; the Actions runs API reports 4 runs (removed by the planned deletion). No stashes; refs as in finding 1.

## Scope 2 recheck (final)

Bounded recheck of findings 1–6 only, against the revised `docs/evidence/2026-11-05-github-publication.md`
and `docs/status.md`, plus read-only repository state. Implementation, verification bundle and other files were
not re-reviewed; no other file was edited, and nothing was committed, pushed or changed on GitHub.

| # | Status | Resolution checked |
|---|---|---|
| 1 | resolved | Evidence `:96-102` now plans: one orphan root commit with `git rev-list --count main` = `1`; push only `main`, never `--mirror` or local agent checkpoint refs; confirm the remote holds only `HEAD` and `refs/heads/main` at that root. The three local checkpoint refs still exist (expected); the documented main-only refspec excludes them. |
| 2 | resolved | Evidence `:80-85` records only completed facts, independently confirmed read-only: `gh repo view` reports private, `isEmpty: true`, 0 forks; Actions runs total `0`; `git ls-remote origin` returns no refs. The content/metadata scan (`:91-92`) and push/visibility/reporting steps (`:96-102`) are now stated as required or planned, not as results. |
| 3 | resolved | Evidence `:104-109` and `docs/status.md:15` no longer claim a clean approval; they cite the scope 1 approval and defer to this record for the final verdict. |
| 4 | resolved | Evidence `:6` describes the uncommitted scrubbed tree for the new orphan root that replaces the discarded initial commit. Remaining tree changes since the verification run are documentation only. |
| 5 | resolved | `docs/status.md:71-73` Next step 1 verifies public visibility and `private-vulnerability-reporting` `enabled: true`; evidence `:101` plans enabling and API verification right after the visibility change. |
| 6 | resolved | Evidence `:93-94` reports a rerun: 77 references across eight documents, PASS. An independent check of the eight scoped Markdown files (README, CHANGELOG, SECURITY, status, three evidence records, this record), using a different counting method that ignores fenced code blocks and anchors-only links, found 62 relative file links and 0 broken. The count difference comes from method and file selection, not from any defect. |

Additional read-only checks:

- Recreated repository's Actions permissions API: `enabled: true`, `allowed_actions: all`, so the planned first
  push can trigger CI as the evidence states.
- Rescan of all tracked non-KB files plus `LICENSE` for the previous-hosting domain, previous account name,
  local session identifiers/URI schemes, UUIDs and generic previous-hosting wording: 0 files.

Approval boundaries for the remaining steps: the orphan commit, its staged-tree/metadata scan, `rev-list` count,
main-only push, `ls-remote` result, public visibility, vulnerability-reporting enablement and the first CI run are
future actions. They are not verified here and must be recorded with actual outputs in the follow-up handoff commit.
If any pre-push check fails, do not push or change visibility.

## Scope 1: initial publication and HTTPX declaration (history, approved)

The record below is the original scope 1 review, kept as history. Its wording was neutralized for public release;
its verdict and evidence are unchanged.

### Scope and baseline (scope 1)

Reviewed only the task-declared changes, with their surrounding current content:

- `pyproject.toml`: add `httpx>=0.27,<1` to the optional `llm` extra.
- `sqlmem/llm_transport.py`: dependency-description docstring only.
- `README.md`: canonical repository link and clone/install block.
- `CHANGELOG.md`: repository move and dependency fix.
- `docs/design/README.md`: link ADR 0013.
- `docs/design/adr/0013-declare-httpx-transport-dependency.md`: dependency decision.
- `docs/status.md`: publication/current environment and provenance notes.
- `docs/evidence/2026-11-05-github-publication.md`: publication evidence and limitations.

`git status`, `git log`, scoped `git diff` and `git diff --staged` confirmed an unborn `main`
with project files untracked and no usable historical diff. That review therefore assessed the
declared bounded edits in context, not the inherited snapshot as newly authored work.
It could not independently reconstruct a before/after source diff.

### Findings (scope 1)

| Severity | File:line | Issue | Proposed fix |
|---|---|---|---|
| — | — | No actionable findings in the scoped changes. | None. |

### Checklist assessment (scope 1)

- **Correctness and dependencies:** the direct HTTPX import now has an explicit optional dependency.
  The base dependencies are unchanged; `dev` includes `llm`. ADR 0013 explains alternatives,
  coexistence with HTTPX2 and the intentionally unchanged transport behavior.
- **SQL safety, privacy and errors:** no scoped executable change affects `check_readonly`,
  `run_select`, time limits, sensitive-column handling, MCP input bounds or error messages.
  Scoped publication documentation contains no credentials or credential-bearing URLs.
  This is not a comprehensive secret audit of the inherited snapshot.
- **Portability and typing:** no SQL/dialect or typing logic changes. Local SQLite/DuckDB
  evidence is green; absent external-engine and OS/Python-matrix coverage is explicitly disclosed.
- **Tests and requirements:** existing transport tests import HTTPX directly and exercise the bridge,
  SDK injection, closure and cancellation. They provide a regression signal without a new runtime
  feature or requirement. The three cited requirement rows match generated traceability exactly.
- **Documentation:** README, changelog, ADR/index and handoff agreed on the GitHub.com publication
  target (initially private, before scope 2) and explicit dependency. Prior-hosting references were
  labeled provenance rather than represented as this checkout's history; scope 2 removes them.

### Evidence checked (scope 1)

Accepted the fresh existing verification bundle rather than rerunning or overwriting it:

- `build/evidence/summary.md` and `summary.json`: generated
  `2026-11-04T19:14:26-08:00` (`2026-11-05T03:14:26Z`), Windows/Python 3.14.7,
  explicitly identifying an uncommitted tree with no commits.
  The manifest and transport docstring predate the run; the later status/evidence edits are documentation.
- All seven gates PASS; all seven copied gate rows match the generated summary exactly.
  Gate logs confirm successful lint, format, mypy, pyright, tests and eval commands.
- `tests.json`, `junit.xml`, `coverage.xml` and the test log corroborate 349 passed,
  1 skipped, 33 reported warnings and 88% combined coverage against the 85% threshold.
  The skipped test is `tests/test_mssql.py::test_mssql_scan_model_and_query`, requiring
  `SQLMEM_MSSQL_ODBC`. All four `tests/test_memory_transport.py` cases passed.
- `traceability.md`/`.json`: 51/51 requirements proven; REQ-AMEM-03 has 22 passing
  cases and none failed/skipped. QA-TYPES and QA-TESTS rows match the evidence record.
  SQLite and DuckDB passed; QA-ENGINES remains partial, as disclosed.
- `eval-retrieval.json` and eval log: BM25 24/24, recall 1.0; without the knowledge
  graph 23/24. No retrieval change or fastembed result is claimed.

Independent read-only publication/environment checks:

- `.venv\Scripts\python.exe -m pip check`: `No broken requirements found.`
- Installed metadata: sqlmem 0.2.0 declares `httpx<1,>=0.27` for `llm`;
  HTTPX 0.28.1 and HTTPX2 2.16.0 coexist. OpenAI 3.46.0 requires HTTPX2
  `>=2.12.0,<3`; MCP 2.3.0 requires HTTPX2 `>=2.10.0`.
  This supports the dependency-failure explanation. The original red-run counts are
  author-reported; the preserved verification bundle is the green run.
- `git remote -v`: fetch/push target the canonical GitHub.com repository.
- `gh repo view ... --json nameWithOwner,url,isPrivate`: correct owner/URL,
  `isPrivate: true` (the pre-publication state at that time).
- Actions permissions API: `enabled: true`, `allowed_actions: all`.

## Approval boundaries

Scope 2 was initially withheld until findings 1–4 were resolved; the recheck above confirms 1–6 are resolved.
The owner's authorization, license choice and copyright holder are taken as stated, not independently verified.
This review cannot verify the post-publication state (orphan SHA, remote refs, public visibility,
vulnerability-reporting setting, first CI run); those must be recorded after publication.

Approval is not certification of the inherited snapshot, hosted CI or the configured Python
3.10–3.13 matrix. PostgreSQL, MariaDB, SQL Server and fastembed were not run here.
The documented prompt-to-skill findings remain changes-requested and out of scope.
The earlier cancellation failure did not recur; no flake/root-cause fix is inferred.
The first hosted CI run remains a publication follow-up, not a result claimed by this review.

Only this review record was written; implementation and generated evidence were left unchanged.
