# Evidence: offline chart visualization

| | |
|---|---|
| Date | 2026-10-30 |
| Commit | Uncommitted working tree based on `9d65b35c13fadff15527d8cae6a038a43ef75e00`; evidence/review/handoff documentation finalized after the code checks |
| Requirements | REQ-CHART-01..09; existing REQ-SAFE-01/02/03 and REQ-MCP-01 retained |
| Review | [Independent chart review](../reviews/2026-10-30-chart-visualization.md) |
| CI run | Not run for this change |

## Change

The project chart skill and `create_chart` MCP tool generate private standalone ECharts HTML from classified
retrieved rows or guarded SQL. One renderer supplies both offline files and the project-scoped Copilot canvas.
Native 2D, financial, hierarchy/flow and optional 3D mappings use controlled typed options, not arbitrary
JavaScript; local artifacts remain outside knowledge indexing and Git. The canvas is a bounded loopback viewer,
not a query service or host bridge. [ADR 0011](../design/adr/0011-bounded-offline-chart-visualization.md) records
the library pins, privacy/caps, narrow CSP-compatible GL build and architecture.

## Verification

Command: `.\.venv\Scripts\python.exe scripts\verify.py --require-engines`, after
`.\scripts\engines.ps1 start` and `.\scripts\engines.ps1 env | Invoke-Expression`.
The servers were stopped in `finally`; the final status check showed all three stopped.

Copied from `build/evidence/summary.md`, **2026-10-30T20:13:07-07:00**:

| Gate | Verdict | Time | Summary |
|---|---|---|---|
| lint | PASS | 0.4s | All checks passed! |
| format | PASS | 0.3s | 109 files already formatted |
| mypy | PASS | 1.4s | Success: no issues found in 39 source files |
| pyright | PASS | 31.3s | 0 errors, 0 warnings, 0 informations |
| tests | PASS | 80.7s | 248 passed, 34 warnings in 77.71s (0:01:17); coverage 89% (min 85%) |
| eval | PASS | 1.7s | Retrieval eval [none]: full 24/24, mean recall 1.00, avg tables 4.9, concepts shown 24, 0.1s; Gate: full >= 24, mean recall >= 1.0 -> PASS |
| trace | PASS | 0.0s | 42/42 requirements proven by passing tests; engines: duckdb=passed, mssql=passed, mssql-integration=passed, mysql=passed, postgresql=passed, sqlite=passed |

Environment: Python 3.13.15 (CPython, ARM64), Windows-11-10.0.26300-SP0; ruff 0.17.3, mypy 2.4.1,
pyright 1.1.414, pytest 9.1.1, SQLAlchemy 2.1.6. No Python runtime dependency was added.

### Requirement traceability

Status/count columns copied from the final `build/evidence/traceability.md`. Test lists below identify the
principal reproducible nodes; the complete generated matrix remains in the evidence bundle.

| ID | Status | Passed | Failed | Skipped | Principal evidence |
|---|---|---|---|---|---|
| REQ-CHART-01 | proven | 80 | 0 | 0 | `test_charts.py::test_family_matrix`, `test_fixed_bounds_and_deadline`, `test_invalid_data`; fractional hierarchy review regressions |
| REQ-CHART-02 | proven | 60 | 0 | 0 | `test_charts.py::test_family_matrix`, `test_family_invariants`, `test_options_fail_closed`, `test_presentation_options_are_applied_not_ignored` |
| REQ-CHART-03 | proven | 17 | 0 | 0 | `test_chart_mcp.py`; `test_dialects.py::test_end_to_end_on_engine` on five engines |
| REQ-CHART-04 | proven | 14 | 0 | 0 | Vendor hashes/CSP reconstruction; standalone notice inclusion and invalid manifest regressions |
| REQ-CHART-05 | proven | 65 | 0 | 0 | Privacy, script breakout, mapped-only data, symlink/reparse, exclusive publication and sanitized MCP errors |
| REQ-CHART-06 | proven | 18 | 0 | 0 | HTML/JS controls, PNG MIME/signature/failure/native-DPR tests and horizontal category-title regression |
| REQ-CHART-07 | proven | 47 | 0 | 0 | Three 3D families, disabled/failed WebGL, nonempty 2x2 surface invariants, CSP build and PNG DPR regressions |
| REQ-CHART-08 | proven | 1 | 0 | 0 | `test_chart_canvas.py::test_chart_canvas` invokes the Node viewer/path/HTTP/action/lifecycle suite |
| REQ-CHART-09 | proven | 1 | 0 | 0 | `test_chart_skill.py::test_chart_skill_discovery_and_explicit_request_contract` |

### Red, then green

- MCP acceptance initially failed because `create_chart` was absent; the renderer's initial import test failed
  with `ModuleNotFoundError: No module named 'sqlmem.charts'`.
- Initial GL browser mounts hit two `script-src`/`eval` CSP violations despite disabled post-effects.
  The exact upstream expression compiler was replaced by a static switch over 22 distinct fixed expressions.
  Reconstruction/hash tests and initial browser mounts passed without weakening CSP.
- SVG `getDataURL(type='png')` returned SVG. The final exporter rasterizes SVG and verifies the PNG MIME/signature.
- GL export at forced 2x produced a valid PNG without its plotted layer: a sampled central 210x140 area had
  **0** plotted pixels versus **4,405** at native resolution. The corrected export uses the renderer's native
  DPR; final browser sampling found **7,088** non-background plotted pixels.
- Degenerate nonempty surface grids were rejected after regression tests; a final 2x2 surface rendered four points.
- Independent review reproduced Windows UNC/device spelling bypasses, missing standalone dependency licenses
  and rejected parent `0.3` with leaves `0.1`, `0.2`. New review regressions failed before the fixes; the final
  gate proves them. Windows path tests are lexical and perform no remote filesystem operations.
- Final visual inspection found the horizontal axis title over category labels; its test first reported
  `nameLocation='middle'` instead of `'end'`. Type-checking caught unguarded recursive-JSON assignments, which
  were corrected with dictionary narrowing before the final passing bundle.

### Browser and canvas evidence

Integrated browser/Playwright checks opened standalone `file://` artifacts generated from
`tests.test_charts.CASES`. All **25 families/aliases** initially reached `ready`, with **zero external requests,
zero page errors and zero CSP violations** while HTTP/HTTPS resource requests were blocked.
Final follow-ups verified the corrected 2x2 surface and PNG exporter, rather than relying on readiness alone.

| Check | Observed result |
|---|---|
| Real AdventureWorks chart | Guarded MCP demo and final renderer examples: 10 territory rows, complete result; no warnings |
| SVG PNG export | `data:image/png;base64,`, signature `iVBORw0KGgoA`; intercepted download length 38,474 characters |
| Corrected GL surface export | PNG signature, 7,088 plotted central pixels; `ready`, zero CSP violations |
| Keyboard/table/theme | Enter toggled table with `aria-expanded=true`; theme changed to light; table had header + expected data rows |
| Legend/zoom/reset | Legend selection false and zoom start 20; Reset restored selection true and start 0 |
| Mobile resize | 390 px viewport, body scroll width 375 px, chart width = client width = 338 px after ResizeObserver |
| No WebGL | Explicit `webgl-unavailable`, visible table, disabled PNG; hardware-acceleration guidance |
| Context loss | `WEBGL_lose_context` triggered explicit warning; table remained visible |
| Empty/partial/unknown | Distinct empty state, partial-result banner and completeness-unknown banner |
| Script-like data | Script/img-looking label stayed text; no external images or CSP violations |
| Canvas runtime | `extensions_reload`, capability discovery, open, refresh/show/download actions and same-instance reopen succeeded |

The final canvas ID is `sqlmem-chart`, input `{path, outputRoot}`; actions are `refresh({})`,
`show_chart({chart_id})`, `download_html({})`. Reopening the same artifact reused its live server and preserved
artifact identity. The same licensed HTML reached `ready` in both real-data canvas previews.

### Bounds and packaging

On the environment above, final reviewed renderer calls measured:

| Type | Rows | Construction | HTML bytes |
|---|---|---|---|
| line | 5,000 | 0.1044 s | 1,272,906 |
| scatter3d | 5,000 | 0.1007 s | 1,969,407 |

Representative earlier 5,000-row browser loads reached `ready` in **2,764 ms** (line) and **3,091 ms**
(scatter3d), with no CSP violations. These are single-run measurements, not cross-machine performance guarantees.
`test_fixed_bounds_and_deadline` and negative mapping/data tests cover enforcement, not silent sampling.

- `setuptools.build_meta.build_wheel` and `build_sdist` produced the final wheel/sdist under ignored
  `build/chart-packaging`. **15** module/asset/license files were verified byte-for-byte against source;
  `scripts/build_chart_vendor.py` was present in the sdist.
- An isolated process importing an extracted wheel rendered 3D HTML and verified every applicable manifest-listed
  license's full text in the standalone artifact. The namespace-package packaging warnings were removed by
  explicit package-data configuration.
- Setuptools, already declared as a build dependency, was restored only after packaging failed with
  `ModuleNotFoundError`. The existing SQL MCP executable was not reinstalled.
- Upstream and patched bundle hashes, pinned versions, license inventories and the narrow GL modification notice
  are in `sqlmem/assets/vendor/manifest.json`. Reproducible patch test:
  `.\.venv\Scripts\python.exe -m pytest tests\test_chart_vendor_build.py -q`.

## Gaps and risks

- Restart the existing VS Code MCP server to expose `create_chart`; fresh client/server instances were verified,
  not hot replacement of another session's running server. The project canvas is loaded in this session.
- HTML contains its plotted data. Local files and Git-ignore are not encryption or isolation from other software
  running as the same user. Classification is a caller contract, not comprehensive DLP or arbitrary SQL lineage.
- Browser download-manager events were unavailable in the integrated browser. PNG links were intercepted before
  navigation and checked for valid MIME/signature and actual GL plot pixels; saving through every browser's
  download UI was not verified.
- Other browsers/GPUs, Linux/macOS and Python 3.10-3.12 were not rerun for this change. Every pointer gesture and
  every possible chart/option combination was not exhaustively visually tested.
- Skill tests validate discovery/workflow text; they do not prove that every model follows the instructions for
  every ambiguous/no-request/adversarial conversation.
- CI remains unverified; no retrieval algorithm changed, so no additional fastembed comparison was claimed.
- The suite reported 34 warnings, including existing SQLite resource warnings; they were not silently suppressed.
- Canvas viewers expire after idle/lifetime bounds; reopening the preserved artifact restarts a viewer.
  Test database servers and temporary browser fixtures were cleaned up; real-data example HTML remains local
  and ignored, not committed.
