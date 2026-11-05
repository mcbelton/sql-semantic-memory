# Independent review: chart visualization

| | |
|---|---|
| Date | 2026-10-30 |
| Reviewer | Independent reviewer; no implementation changes made |
| Baseline | `9d65b35c13fadff15527d8cae6a038a43ef75e00` plus the uncommitted chart change |
| Verdict | changes requested → **approve after fixes and visual follow-up** |
| Checklist | [checklist.md](checklist.md) |
| Evidence record | [Chart visualization evidence](../evidence/2026-10-30-chart-visualization.md), being prepared by the parent at review time |

## Scope and method

Read every tracked diff hunk and the new renderer, HTML/CSS/JavaScript, MCP adapter, project skill and canvas,
vendor build script/manifest, packaging changes, chart tests, added dialect scenario, requirements, ADR 0011 and
related documentation. Excluded user-created SVGs and ignored build artifacts other than verification evidence.
Did not review minified vendor source wholesale: independently checked the public tagged upstream bundle hashes,
read the narrow compiler replacement and relevant remaining dynamic-compilation contexts, and ran its
reconstruction test. No runtime/test files were edited and no full verification suite was rerun.

## Original findings

All three findings below are **resolved**. Their original locations and reproductions are retained for the
audit trail; the surgical fixes and added tests were independently re-reviewed on 2026-10-30.

| Severity | File:line | Issue and evidence | Proposed fix |
|---|---|---|---|
| **blocking** | `.github/extensions/sqlmem-chart/viewer.mjs:54–58` | Windows network/device-path rejection checks only the original backslash spelling. A lexical execution of the actual `absolute()` function rejected `\\untrusted.invalid\share\build\charts`, but accepted `//untrusted.invalid/share/build/charts` as `\\untrusted.invalid\share\build\charts` and accepted `//?/C:/build/charts` as `\\?\C:\build\charts`. `canonicalNoLinks()` then makes filesystem calls on that result. This bypasses the intended local-artifact boundary and can initiate remote-share access before rejection. The probe performed no network/filesystem access. | Normalize separators and validate the resulting Windows root before **any** filesystem operation; reject UNC, device namespaces and alternate streams in every spelling. Add forward-slash and mixed-separator negative tests that also prove filesystem resolution is not attempted. |
| **major** | `sqlmem/charts.py:1155–1158` | Standalone HTML includes only the primary ECharts/GL LICENSE and NOTICE files, not their bundled dependency licenses. In-memory real-asset renders confirmed that the exact `echarts.LICENSE-d3`, `zrender.LICENSE` and `tslib.LICENSE` texts are absent from 2D and 3D HTML, and `claygl.LICENSE` is absent from 3D HTML. Package inclusion does not supply these texts with a standalone artifact. This contradicts REQ-CHART-04 and ADR 0011; the GL notice itself refers to separate files absent from the HTML. | Include and deduplicate every applicable notice/license listed for the embedded bundles in the manifest. Add real-asset tests checking their full text in standalone 2D and enabled-3D HTML, while retaining GL opt-in. |
| **blocking** | `sqlmem/charts.py:863` | Exact binary64 equality rejects valid fractional hierarchy totals. With a root value `0.3` and leaf values `0.1`, `0.2`, `build_chart_option()` raises “Hierarchy parent total conflicts with its leaf-derived sum.” The identical input with a null parent derives `0.30000000000000004`. Ordinary decimal-valued treemaps and sunbursts therefore fail solely because of representation rounding. | Use an explicitly documented, tight rounding-aware comparison, or validate totals with exact source-number arithmetic. Test both hierarchy families with fractional matching totals and genuinely conflicting totals; do not weaken mismatch rejection indiscriminately. |

### Resolutions checked

| Original finding | Resolution and regression evidence | Status |
|---|---|---|
| Windows path bypass | `viewer.mjs:47–62` exports pure `validateLocalPath()`, normalizes Windows separators, requires a drive-absolute prefix and rejects subsequent colons before filesystem operations. `viewer.test.mjs` test “Windows network and device spellings fail lexically before filesystem access” covers forward/backslash and mixed UNC/device spellings plus an alternate stream. This Windows-specific test ran on the review machine, not merely as a skipped case. | **resolved** |
| Missing standalone licenses | `charts.py:1161–1201` reads the pinned manifest, checks required embedded bundles and bounded local notice basenames, and deduplicates applicable notices. `tests/test_chart_review_regressions.py::test_standalone_includes_every_applicable_manifest_notice` checks complete real license texts for both 2D and enabled 3D, ZRender deduplication and GL opt-in. `test_corrupt_notice_manifest_fails_closed` covers malformed inventories and traversal filenames. | **resolved** |
| Fractional hierarchy totals | `charts.py:864–871` permits at most two ULPs of absolute rounding error with zero relative tolerance for fractional totals; two whole-number totals still require exact equality. `tests/test_chart_review_regressions.py::test_fractional_hierarchy_totals_allow_only_rounding_error` accepts `0.3` versus `0.1 + 0.2` for both hierarchy families, rejects `0.300001`, and rejects integer differences of one, including near `9e15`. | **resolved** |

**No open findings after re-review.**

### Horizontal-axis visual follow-up (2026-10-30)

The parent subsequently reported a screenshot showing a horizontal bar category-axis title overlapping category
labels. The two-line visual change in `charts.py:700–701` moves the swapped category y-axis title to its end with
an 18-pixel gap, without changing values, categories, orientation or zoom ownership. Its regression and the
existing horizontal-series test passed independently:

`.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_chart_review_regressions.py::test_horizontal_category_axis_title_does_not_overlay_category_labels tests/test_charts.py::test_multivalue_split_and_order_preservation`
— **2 passed in 0.08s**.

| Severity | File:line | Issue | Proposed fix / status |
|---|---|---|---|
| **blocking** | `sqlmem/charts.py:700–701` (initial follow-up) | The direct indexed assignments targeted a `Json` union rather than a narrowed object. Independent `.venv\Scripts\python.exe -m mypy sqlmem/charts.py` failed with **four errors** (`index` and `call-overload`). | **Resolved:** `charts.py:700–705` now binds `category_axis`, checks `isinstance(category_axis, dict)` and raises a static actionable error if the invariant fails before assigning the title position/gap. This runtime guard safely narrows the object without a cast or suppression. Independent mypy reports no issues; both focused tests pass again (**2 passed in 0.05s**). |

The three original findings remain resolved. The earlier 247-test full gate and the subsequent **20:09:41**
full run (248 tests passing but mypy/pyright failing) were not used to approve this follow-up. Approval was
restored only after independently reading the fresh **20:13:07** full-gate PASS following the guard.
The visual screenshot was supplied by the parent, not independently repeated by this reviewer.
**The visual follow-up and its typing finding are resolved; no open findings remain.**

## Verification checked

- Read `build/evidence/summary.md` and the corresponding summary/traceability records:
  **2026-10-30 19:48:42 -07:00**, baseline above plus **24 uncommitted files**. All seven gates PASS:
  **231 tests, 32 warnings, coverage 89%**, BM25 full **24/24**, mean recall **1.00**, **42/42** requirements;
  SQLite, DuckDB, PostgreSQL, MySQL, SQL Server and SQL Server integration passed.
- The initial gate predates the native-DPR GL-export amendment and review fixes; it is retained only as
  historical evidence, not the approval basis.
- Independently read the fresh final `build/evidence/summary.md` and `summary.json`:
  **2026-10-30 20:03:49 -07:00**, the same baseline plus **26 uncommitted files**. The parent's
  `.venv\Scripts\python.exe scripts\verify.py --require-engines` run has **all seven gates PASS**:
  lint clean; **109 files** formatted; mypy **39 source files** clean; pyright **0 errors/0 warnings**;
  **247 passed, 34 warnings, coverage 89%**; BM25 full **24/24**, mean recall **1.00**; **42/42** requirements;
  SQLite, DuckDB, PostgreSQL, MySQL, SQL Server and SQL Server integration passed. This evidence follows all
  runtime fixes at the first approval; their modification times were checked. The subsequent visual follow-up
  was separately re-reviewed above.
- Final approval basis after the visual follow-up: independently read the parent's refreshed
  `build/evidence/summary.md`, **2026-10-30 20:13:07 -07:00**, same baseline plus **26 uncommitted files**.
  **All seven gates PASS**: lint/format clean (**109 files**), mypy **39 source files** clean, pyright
  **0 errors/0 warnings**, **248 tests passed, 34 warnings, coverage 89%**, BM25 full **24/24** and mean recall
  **1.00**, **42/42** requirements, and all five engines plus SQL Server integration passed.
  The final runtime guard predates this run. No full suite was rerun by the reviewer.
- Independently ran:
  - `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_chart_vendor_build.py tests/test_chart_canvas.py`
    — **2 passed in 2.26s**.
  - `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_charts.py`
    after the native-DPR amendment — **118 passed in 6.36s**.
  These initial tests passed despite the original gaps.
  - After the surgical fixes:
    `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_charts.py tests/test_chart_review_regressions.py tests/test_chart_canvas.py tests/test_chart_vendor_build.py`
    — **132 passed in 8.30s**. This focused re-review did not rerun the full suite.
- Independently fetched only the public pinned upstream bundles into memory and verified:
  - ECharts 5.6.0: **1,034,102 bytes**, SHA-256
    `bf4a223524e40b77c304bec67e1222cf551f14880cf42c69dc046558e11c07b1`.
  - ECharts GL 2.1.0 upstream: **639,846 bytes**, SHA-256
    `d6d60f2165ce3eb1ea360ef62e8490835e0ae2c1e0c1788a772fff918e350842`.
  Both match the manifest; the reconstruction test verifies the exact narrow derivative patch.

## Checklist assessment and evidence boundaries

- SQL creation reuses `run_select`, hence `check_readonly`, existing engine timeouts, rollback and cap-plus-one
  truncation. No SQL generation/interpolation was introduced. The added cross-engine scenario exercises the
  chart adapter. Expected SQL/database failures are sanitized rather than returned with SQL/data.
- Typed scalar normalization, allowlisted mappings/options, mapped-only persistence, escaped JSON/text,
  hash-authorized scripts, explicit completeness and exclusive atomic publication were inspected. Catalog/name
  sensitivity checks are conservative caller-contract enforcement, **not** SQL lineage or DLP proof.
- The final GL exporter uses the native device-pixel ratio; 2D canvas export retains 2× and SVG export rasterizes
  before PNG signature validation. The parent reported final real-browser surface export with a PNG signature,
  **7,088 non-background central-plot pixels** (previously zero), ready state and zero CSP violations.
  No outstanding export-branch finding is asserted from that supplied evidence and the focused regressions.
- Parent-supplied browser evidence also reports initial offline mounts of all **25 families/aliases** without
  external requests/CSP violations, a final **2×2 surface with four vertices**, working keyboard/theme/table
  controls, responsive mobile sizing, and real SDK canvas registration/open, show/refresh/download and
  same-instance reopen. These browser actions were **not independently repeated by this reviewer**.
- Wheel/sdist byte-exact checks for **15 asset/license files**, source build-script inclusion and extracted-wheel
  3D generation were reported by the parent. After the final guarded visual follow-up, the parent confirmed
  refreshed wheel/sdist checks with all **15 assets byte-exact**. Packaging command outputs belong in the linked
  evidence record; this reviewer did not rebuild distributions.
- Real-browser WebGL-unavailable/context-loss paths, exhaustive per-family gestures, maximum-cap browser
  performance, other browser/GPU combinations and Linux/macOS coverage were not independently demonstrated
  here. The failure-path JavaScript probes use mocks, not a real GPU. Skill tests inspect its contract, not live
  acceptance of every no-request/ambiguous/adversarial-input scenario. Do not equate traceability's “proven”
  status with exhaustive acceptance coverage.

No retrieval algorithm changes or new Python runtime dependencies were found. **Approved after the original
three fixes, the horizontal-axis visual follow-up, its guarded typing correction and the final passing full
verification.** Retain the stated browser/platform evidence boundaries and complete the linked durable evidence
record as the parent handoff.
