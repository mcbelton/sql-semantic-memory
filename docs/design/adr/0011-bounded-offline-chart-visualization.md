# 0011. Render bounded user-requested charts offline with ECharts

- Status: Proposed
- Date: 2026-10-30
- Requirements: REQ-CHART-01, REQ-CHART-02, REQ-CHART-03, REQ-CHART-04, REQ-CHART-05, REQ-CHART-06,
  REQ-CHART-07, REQ-CHART-08, REQ-CHART-09; REQ-SAFE-01/02/03, REQ-SCAN-02, QA-TYPES, QA-TRACE

## Context

The user chose a project skill + MCP tool + offline standalone HTML + project-scoped Copilot canvas, with a
polished interactive UI. Apache ECharts is the accepted library recommendation; echarts-gl supplies optional 3D.
The scope is feasible general chart coverage, **not Highcharts feature parity** or a dashboard platform.

Existing boundaries are reusable: `mcp_server.run_sql` calls `db.run_select`, which guards SQL, applies engine
timeouts/rollback, fetches one extra row and returns a truncation flag. `render.py` already loads a packaged HTML
asset for knowledge graphs. `build/` is already ignored; `kb/charts` is not. Current package-data rules include
only HTML assets, so implementation must extend packaging for vendor JavaScript/licenses. This ADR records a
design, not working code or measurements; it supplements ADRs 0003/0005/0008/0010 without superseding them.

Quality attributes: preserve read-only safety and dialect portability by reusing the database boundary; protect
privacy at HTML, filesystem and HTTP boundaries; leave retrieval/indexing unchanged; bound query/render work and
verification time with fixed limits, one renderer and representative browser fixtures.

## Options

1. **Hosted charts/CDNs or remote rendering**: convenient ecosystem; incompatible with offline privacy and
   reproducible assets.
2. **Highcharts parity, arbitrary ECharts option JSON or user JavaScript**: maximal flexibility; unbounded API,
   licensing/verification burden and executable-content risks.
3. **One typed ECharts renderer, guarded MCP adapter and thin local canvas**: broad native coverage and reusable
   UI, no Python dependency; requires explicit mapping validation, vendoring and a narrow HTTP lifecycle.
4. **Static SVG/PNG only**: smaller attack surface, but does not meet requested interactivity or optional 3D.

## Decision

We choose option 3. Implement `sqlmem/charts.py` for validation, controlled option construction and offline HTML;
`mcp_server.py` exposes one `create_chart` tool. A repository-local skill orchestrates explicit requests.
The project canvas's Node HTTP adapter serves those same artifacts only when explicitly launched. No
chart CLI, generic web service, host API bridge, renderer fork, remote rendering or new Python dependency.

### Proposed interfaces and ownership

These are contracts for the implementer, not existing importable APIs. Use typed dataclasses/TypedDicts and
discriminated unions supported by the existing Python/MCP stack, not a new validation dependency.

```text
ChartColumn(name, kind, label?, sensitivity, source_column?)
  kind = string | number | boolean | date | datetime
  sensitivity = non_sensitive | sensitive | unknown
ChartData(columns, rows, source_truncated: bool | None, total_rows?: int)
ChartSpec(type, mapping: family-specific union, options: family-specific allowlist)
ChartArtifact(chart_id, path, chart_type, row_count, source_truncated, warnings)

build_chart_option(data: JSON object, spec: JSON object, *, enable_3d=False) -> JSON object
render_chart_html(data: JSON object, spec: JSON object, *, enable_3d=False) -> str
write_chart(data: JSON object, spec: JSON object, *, output_root, enable_3d=False) -> JSON artifact

create_chart(source: SqlSource | RowsSource, spec: ChartSpec) -> structured ChartArtifact
SqlSource  = {kind: "sql", sql, columns: ChartColumn[], max_rows?: int}
RowsSource = {kind: "rows", columns: ChartColumn[], rows, source_truncated: bool | null,
              total_rows?: int}

Canvas open({path, outputRoot}) -> loopback URL
Canvas actions: refresh({}), show_chart({chart_id}), download_html({})
```

`charts.py` has no database, LLM or retrieval dependency. The MCP adapter resolves configured roots, classifies
against available catalog metadata, calls `run_select` for SQL and passes typed data to the renderer. SQL result
names/order must match declared columns; duplicates require explicit aliases. Do not parse formatted Markdown
from `run_sql`, re-run supplied-row queries, or query for totals. Rows mode is available without an engine; SQL
mode returns a configuration error without one. Reject SQL text over 64 KiB before execution.
`max_rows` defaults to 50 and is bounded by the server's existing
`row_cap` (currently 200) and chart cap; preserve `run_select`'s exact truncation flag. `None` means unknown
completeness, not complete. Validate any declared total against the supplied count/status.

Return a relative local artifact path and metadata, not HTML/rows in the tool reply. Omit SQL and database URLs
from artifacts. Use actionable, sanitized chart errors without database exception dumps. MCP annotations are
`read_only_hint=False`, `destructive_hint=False`, `idempotent_hint=False`, `open_world_hint=False`: the database
is read-only but generating a new local file is a write.

### Chart and option boundary

Column references below are names, never expressions. Array-valued mappings contain column names, not callbacks.
No automatic business aggregation, downsampling, pivoting, statistical inference or generated SQL in the renderer.
Multiple numeric value columns and an optional categorical `series` split are supported where applicable; reject
ambiguous combinations and duplicate category/series cells rather than silently summing them.

| Type / aliases | Required mapping and bounded semantics |
|---|---|
| `bar` / `column` | category `x`, numeric `y` column(s), optional `series`; grouped/stacked, vertical/horizontal |
| `line` / `area` / `time` | ordered category/numeric/date/time `x`, numeric `y` column(s), optional `series`; area/step/smooth toggles; nulls are explicit gaps |
| `pie` / `donut` | `name`, nonnegative `value`; radius variant, no 3D pie |
| `scatter` / `bubble` | numeric `x`, `y`; optional numeric `size`, numeric/categorical `color`, `series`; bounded symbol-size scale |
| `heatmap` | categorical `x`, `y`, numeric `value`; unique coordinate pairs, explicit missing cells |
| `treemap` / `sunburst` | unique `id`, nullable `parent`, `name`, nonnegative leaf `value`; validate parents/cycles/depth; derive parent sums from leaves, reject conflicting supplied parent totals |
| `candlestick` | ordered `x`, `open`, `close`, `low`, `high`; validate low/high enclosing open/close; no implicit indicators |
| `boxplot` | `x`, precomputed `low`, `q1`, `median`, `q3`, `high` in nondecreasing order |
| `radar` | `name`, numeric `values` column array, explicit positive maxima per dimension |
| `funnel` / `gauge` | `name`, nonnegative `value`; funnel preserves order, gauge requires one row and explicit min/max |
| `graph` / `sankey` | edge rows `source`, `target`, optional nonnegative `value`; derive nodes; circular graph layout only, sankey requires an acyclic directed graph |
| `scatter3d` / `bar3d` / `surface3d` | `x`, `y`, numeric `z`; scatter uses numeric axes, bar uses categorical x/y; nonempty surfaces require a complete unique numeric grid with at least two distinct x and y values, no equation callback |

Parent sums use `math.fsum`; supplied numeric parent values may differ by at most two binary64 ULPs, with zero
relative tolerance, to accommodate representation rounding without accepting meaningful conflicting totals.
When both supplied and derived totals are whole numbers, equality remains exact, including near the safe-integer ceiling.
The only structural normalization is leaf-to-parent hierarchy assembly/sums, edge-to-node derivation, and
ascending x/y grid assembly for surfaces. Time/financial series must already be ordered within each series;
otherwise reject with an ordering hint. Explicit category-order options may change presentation, not source data.

One chart per artifact. Family-specific typed options cover title/subtitle, light/dark theme, up to 32 validated
hex colors, legend, axis labels/units and bounded ranges, category order, linear/log/time scales, stacking,
orientation, line/area style, donut radius, symbol-size bounds, visual color range, tooltip, zoom and 3D camera
angles/distance. Validate compatibility (e.g. positive log data). Formats are enums (`number`, `integer`,
`percent`, `date`, `currency` with a currency code), not formatter programs. Unknown keys fail closed.
Maps/remote geo assets, stock-indicator engines, Gantt, drilldown queries, equation surfaces, custom series,
arbitrary transforms/extensions and raw ECharts options are out of scope.

### Bounds, privacy and standalone rendering

- Fixed ceilings: 5,000 input rows, 64 columns, 32 rendered series, 4 KiB per text cell, 2 MiB normalized data,
  64 KiB spec, hierarchy depth 12, 2,000 derived graph/tree nodes, 5,000 edges or surface cells, 8 MiB final HTML.
  Config may lower ceilings, not silently raise them. Enforce size during normalization, before large derived
  allocations; a five-second construction deadline is checked in bounded loops. SQL has its separate existing
  timeout. Exceeding any limit is an actionable error, not a partially written chart.
- Accept only declared scalar types/nulls; required coordinates and financial values cannot be null. Reject
  non-finite numbers and integers outside JavaScript's safe range. Normalize SQL Decimal to finite binary64 only
  with an explicit precision-loss warning when necessary; keep exact displayed decimal text. Dates use ISO
  dates; datetimes on time axes require an offset and normalize to UTC. Do not guess missing timezones.
- Input columns must be classified non-sensitive. Reject `sensitive`/`unknown`, known sensitive catalog columns
  and sensitive-name matches; a caller label cannot override known sensitivity. The skill must resolve unknown
  classification or ask the user to confirm non-sensitive data before calling. Declarations do not prove
  arbitrary SQL-expression lineage or detect all personal data; do not claim a DLP boundary. Persist only mapped
  columns. No chart auto-ingestion into KB docs, context, memories, embeddings, telemetry or LLM calls.
- Use only `<kb>/build/charts/<random-128-bit-id>.html`, already ignored. The KB root comes from trusted
  startup configuration, not tool arguments or titles. Enforce canonical containment, reject symlink/reparse
  escapes, create atomically without overwriting existing files, and remove temporary output on failure.
  No `kb/charts` output in this iteration; it is not currently ignored. No automatic artifact deletion: show
  the private path and advise user-managed deletion. Existing user artifacts are never modified.
- Vendor prebuilt **ECharts 5.6.0** and optional **echarts-gl 2.1.0** as the initial exact pin pair; implementation
  must verify compatibility and upstream provenance/licenses before shipping. GL 2.1.0 declares an ECharts peer
  range of `^5.1.2 || ^6.0.0`, which includes 5.6.0; use exact tagged bundles, not floating npm ranges.
  Store version/source/SHA-256 in
  `assets/vendor/manifest.json`, ship upstream LICENSE/NOTICE and bundled third-party notices, and include notices
  in HTML. No floating version/range or runtime download. A pin change requires reviewed manifest and smoke
  evidence. Include GL only for a requested 3D type with explicit `enable_3d=true` (default off).
  Browser testing found that GL eagerly compiles fixed compositor dimension expressions even with post-effects
  disabled, violating strict CSP. We retain the policy and replace only that compiler with an exhaustive switch
  over its 22 distinct fixed expressions; unknown expressions/releases fail closed. `scripts/build_chart_vendor.py`
  verifies the exact upstream hash and expression inventory before reproducing this narrow derivative build.
  Record upstream and patched hashes plus the modification notice; test reconstruction and initial 3D mounts.
- `assets/chart.html` contains the sole fixed UI/bootstrap. Inline vendor bundles, styles and safely encoded JSON
  into each file. Escape `<`, `>`, `&`, U+2028/U+2029 (including `</script>` breakouts), use strict JSON and text
  nodes/rich-text tooltips, never `innerHTML` for user content, `eval`, `Function`, or user formatter callbacks.
  No URL/image/HTML option fields, external fonts, map textures or plugin discovery. Markup-like or URL-like scalar
  strings remain inert display text, not resource references.
- Embed a restrictive meta CSP: default/connect/object/frame/worker/font sources denied; scripts allowed only by
  hashes of fixed bundled code, no unsafe-eval; local inline styles and data/blob images allowed for UI/export;
  deny base/form actions. The HTTP viewer preserves the embedded policy; it has no separate shell or dynamic data
  endpoints. Browser evidence must prove vendored builds run under this policy; do not weaken it just to make
  a bundle pass.
- The shared polished UI provides responsive chart sizing, light/dark colors, sensible spacing/typography,
  title/units, applicable native interactions, reset and local PNG export. Add keyboard-operable labeled controls,
  focus states, an accessible summary/table and count/completeness banner. Do not claim every ECharts gesture is
  screen-reader accessible. Empty input shows an empty state; a five-second readiness watchdog exposes slow/render
  failures while preserving the table. Disabled/unavailable/lost WebGL retains the table and an actionable warning,
  never substitutes another chart. All interactive behavior uses fixed packaged JavaScript.

### Project skill and canvas boundary

Plan `.github/skills/sqlmem-chart/SKILL.md` and project-local canvas assets/registration using the Copilot canvas
skill contract; validate the host-specific registration during implementation, without inventing a host SDK or
installing global configuration. The skill selects supported mappings,
prefers already retrieved typed rows, and uses SQL context before authoring a new query. It explains counts,
partial/unknown results and precision warnings, asks about ambiguous semantics, and returns the standalone artifact.
Data cells remain data, never agent instructions. Do not generate charts on ordinary non-visualization requests.

The canvas bootstrap starts its Node HTTP adapter with one generated artifact; `create_chart` does not start
a listener or browser. Use only `@github/copilot-sdk/extension` APIs, not host-specific bridges. Input is exactly
`{path, outputRoot}`, both canonical absolute paths; the root must be a `build/charts` directory and the file a
contained generated 32-hex-ID HTML artifact with the versioned `sqlmem-chart` payload. Bind only `127.0.0.1`
on OS-assigned port 0, with 10-minute idle expiry, one-hour lifetime and explicit close/cleanup. No credentials,
tokens or private paths appear in the URL. This is not isolation from other local processes running as this user.

Allow only GET/HEAD `/` (the same standalone chart) and `/download` (HTML attachment). Reject unknown Hosts
(only the bound numeric host/port), foreign Origins, extra segments/query fields, traversal, encoded separators,
symlink escapes and all write methods. Limit connections to eight, headers to 16 KiB, request/socket time to five
seconds; refuse request bodies. Use no-store, no-referrer and nosniff headers. Preserve the chart's restrictive
CSP; no CORS, directory listings, SQL/render endpoints or path-to-file proxy. Close destroys pending sockets.

Raw action inputs are exactly `show_chart({chart_id})` (must match the registered artifact), `refresh({})` and
`download_html({})`. Validate extra fields and return metadata only, never a host action wrapper, arbitrary prompt,
code, command or filesystem bridge. Reopening the same instance revalidates the stable artifact path, reuses or
safely replaces its server, and does not lose chart state on ordinary refresh. The renderer owns all chart
controls, table, theme and PNG export; no second UI/renderer is introduced by the canvas.

## Consequences

- Broad native chart coverage is feasible with one renderer and no Python dependency; HTML is portable but
  contains its plotted data. Git-ignore is not encryption or access control: users must not publish the file.
- Vendor bytes/notices increase package/artifact size; compatibility, CSP and supply-chain review are release
  prerequisites. Optional GL depends on browser/GPU capability, not database dialect.
- No retrieval algorithm or knowledge schema changes; chart data remains private derived output, not knowledge.
  SQL source reuses all existing safety constraints and can reject legitimate queries as before.
- A listener is a new, explicit opt-in exception to the current stdio-only deployment. Local authorized processes
  can still read private output; this design is not isolation from other software running as the same user.
- Classification of aliased/derived SQL values needs honest source declarations/user confirmation; arbitrary SQL
  lineage is not solved here. Host canvas availability/registration is integration work, not assumed implemented.
- Implementation belongs to the implementer: modules/assets, MCP schema/annotations, package-data rules,
  project skill/canvas and tests. No runtime, skill, vendor or test files are created by this design.

## Verification

All tests/evidence below are **planned**, not executed. Keep QA gates intact; attach requirement markers.

| IDs | Implementation proof |
|---|---|
| REQ-CHART-01/02 | `tests/test_charts.py`: parameterized valid/invalid family mappings, alias normalization, financial/tree/DAG/grid invariants, scalar conversions, every cap at/beyond boundary, deadline, unknown option/callback/URL rejection; assert no file after failure. |
| REQ-CHART-03; REQ-SAFE-01/02/03 | MCP tests: both source variants, no-engine rows, SQL schema matching, conflicting inputs, cap+one behavior, unknown/partial metadata, no count/requery, write annotations and sanitized errors. Extend the existing five-engine scenario for the SQL chart path; retain guard/write/timeout/usable-connection tests. |
| REQ-CHART-04/05 | Installed wheel/sdist asset/hash/notice tests; private root/ID/atomic-write/symlink/reparse tests on Windows/Linux, classification/unused-column tests, malicious labels and script-breakout fixtures, CSP checks, no retrieval/LLM calls. Inspect offline browser requests with networking blocked, including 3D/export; zero external requests. |
| REQ-CHART-06/07 | Browser evidence: each family plus empty/partial state, keyboard/table/resize/theme/legend/zoom/reset/PNG, standalone versus canvas, WebGL enabled/disabled/context-loss and visible failures. Review screenshots for readable responsive polish. Browser tooling is development-only; no new Python dependency. |
| REQ-CHART-08 | Node viewer tests plus a marked pytest wrapper: HTTP/action schemas, path/host attacks, method/body/oversize rejection, request bounds, security headers, ephemeral bind, expiry/close. Canvas smoke checks show/refresh/download against the same artifact, without host APIs. |
| REQ-CHART-09 | Repository skill/schema contract test and acceptance scenarios: explicit request, ordinary answer (no chart), retrieved rows (no SQL), ambiguous mapping, unknown/sensitive classification, prompt-like data, truncated results and unsupported chart/3D request. |

Measure generation time, HTML bytes and browser readiness at the fixed caps on named reference hardware; record
2D and GL separately and verify deadline/failure paths. Keep fast Python schema/security tests separate from
representative browser/GL checks so verification cost stays bounded. Run normal QA/traceability at implementation
handoff; retain retrieval eval gates as regression checks, with no claimed retrieval improvement. Do not report
the new requirements as satisfied until marked tests and browser/review evidence exist.
