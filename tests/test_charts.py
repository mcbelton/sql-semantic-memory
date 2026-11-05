"""Bounded offline chart contracts; browser/vendor provenance is verified separately."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from sqlmem.charts import build_chart_option, render_chart_html, write_chart


def data(names: str, rows: list[list[Any]], *, kinds: list[str] | None = None) -> dict[str, Any]:
    columns = names.split()
    return {
        "columns": [
            {"name": name, "kind": kind, "sensitivity": "non_sensitive"}
            for name, kind in zip(columns, kinds or ["string", *(["number"] * (len(columns) - 1))], strict=True)
        ],
        "rows": rows,
        "source_truncated": False,
    }


def spec(kind: str, **mapping: Any) -> dict[str, Any]:
    return {"type": kind, "mapping": mapping, "options": {}}


@pytest.fixture
def vendor(monkeypatch: pytest.MonkeyPatch) -> None:
    # Core tests use deterministic fixed code, never fetch a dependency. Parent verifies real pinned assets.
    import sqlmem.charts as charts

    original = charts._asset

    def asset(name: str) -> str:
        if name == "vendor/manifest.json":
            return original(name)
        if name.startswith("vendor/"):
            return "/* fixed offline vendor fixture */" if name.endswith(".js") else "Apache license / NOTICE"
        return original(name)

    monkeypatch.setattr(charts, "_asset", asset)


CASES = [
    ("bar", data("x y", [["A", 2], ["B", 3]]), {"x": "x", "y": "y"}, {}),
    ("column", data("x y", [["A", 2]]), {"x": "x", "y": ["y"]}, {}),
    ("line", data("x y", [["A", 2], ["B", None]]), {"x": "x", "y": "y"}, {}),
    ("area", data("x y", [["A", 2]]), {"x": "x", "y": "y"}, {}),
    ("time", data("x y", [["2026-01-01", 2]], kinds=["date", "number"]), {"x": "x", "y": "y"}, {}),
    ("pie", data("x y", [["A", 2]]), {"name": "x", "value": "y"}, {}),
    ("donut", data("x y", [["A", 2]]), {"name": "x", "value": "y"}, {}),
    ("scatter", data("x y", [[1, 2]], kinds=["number"] * 2), {"x": "x", "y": "y"}, {}),
    ("bubble", data("x y z", [[1, 2, 4]], kinds=["number"] * 3), {"x": "x", "y": "y", "size": "z"}, {}),
    (
        "heatmap",
        data("x y z", [["A", "B", 4]], kinds=["string", "string", "number"]),
        {"x": "x", "y": "y", "value": "z"},
        {},
    ),
    (
        "treemap",
        data(
            "id parent name value",
            [["r", None, "Root", 3], ["c", "r", "Child", 3]],
            kinds=["string", "string", "string", "number"],
        ),
        {"id": "id", "parent": "parent", "name": "name", "value": "value"},
        {},
    ),
    (
        "sunburst",
        data("id parent name value", [["r", None, "Root", 3]], kinds=["string", "string", "string", "number"]),
        {"id": "id", "parent": "parent", "name": "name", "value": "value"},
        {},
    ),
    (
        "candlestick",
        data("x o c l h", [["A", 2, 3, 1, 4]]),
        {"x": "x", "open": "o", "close": "c", "low": "l", "high": "h"},
        {},
    ),
    (
        "boxplot",
        data("x l q m r h", [["A", 1, 2, 3, 4, 5]]),
        {"x": "x", "low": "l", "q1": "q", "median": "m", "q3": "r", "high": "h"},
        {},
    ),
    ("radar", data("n a b", [["A", 2, 3]]), {"name": "n", "values": ["a", "b"]}, {"maxima": [5, 6]}),
    ("funnel", data("x y", [["A", 2]]), {"name": "x", "value": "y"}, {}),
    ("gauge", data("x y", [["A", 2]]), {"name": "x", "value": "y"}, {"min": 0, "max": 10}),
    (
        "graph",
        data("s t v", [["A", "B", 2]], kinds=["string", "string", "number"]),
        {"source": "s", "target": "t", "value": "v"},
        {},
    ),
    (
        "sankey",
        data("s t v", [["A", "B", 2]], kinds=["string", "string", "number"]),
        {"source": "s", "target": "t", "value": "v"},
        {},
    ),
    ("scatter3d", data("x y z", [[1, 2, 3]], kinds=["number"] * 3), {"x": "x", "y": "y", "z": "z"}, {}),
    ("bar3d", data("x y z", [["A", "B", 3]], kinds=["string", "string", "number"]), {"x": "x", "y": "y", "z": "z"}, {}),
    (
        "surface3d",
        data("x y z", [[2, 2, 4], [1, 2, 3], [2, 1, 2], [1, 1, 1]], kinds=["number"] * 3),
        {"x": "x", "y": "y", "z": "z"},
        {},
    ),
    ("scatter3D", data("x y z", [[1, 2, 3]], kinds=["number"] * 3), {"x": "x", "y": "y", "z": "z"}, {}),
    ("bar3D", data("x y z", [["A", "B", 3]], kinds=["string", "string", "number"]), {"x": "x", "y": "y", "z": "z"}, {}),
    (
        "surface",
        data("x y z", [[1, 1, 1], [2, 1, 2], [1, 2, 3], [2, 2, 4]], kinds=["number"] * 3),
        {"x": "x", "y": "y", "z": "z"},
        {},
    ),
]


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-02", "REQ-CHART-07")
@pytest.mark.parametrize(("kind", "source", "mapping", "options"), CASES, ids=[c[0] for c in CASES])
def test_family_matrix(kind, source, mapping, options):
    option = build_chart_option(source, {"type": kind, "mapping": mapping, "options": options}, enable_3d=True)
    assert option["series"]
    assert option["tooltip"]["renderMode"] == "richText"
    assert "formatter" not in json.dumps(option)


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-05")
@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["columns"].append(d["columns"][0]), "duplicate"),
        (lambda d: d["rows"].append(["bad"]), "row"),
        (lambda d: d["columns"][0].update(sensitivity="unknown"), "non_sensitive"),
        (lambda d: d["columns"][0].update(sensitivity="sensitive"), "non_sensitive"),
        (lambda d: d["columns"][0].update(source_column="customer.email"), "sensitive"),
        (lambda d: d["columns"][0].update(name="password"), "sensitive"),
        (lambda d: d.update(source_truncated="false"), "source_truncated"),
        (lambda d: d.update(total_rows=10), "total_rows"),
        (lambda d: d.update(total_rows=None), "total_rows"),
        (lambda d: d["rows"][0].__setitem__(1, float("nan")), "finite"),
        (lambda d: d["rows"][0].__setitem__(1, float("inf")), "finite"),
        (lambda d: d["rows"][0].__setitem__(1, 2**53), "safe"),
        (lambda d: d["rows"][0].__setitem__(1, True), "number"),
        (lambda d: d["rows"][0].__setitem__(1, {"value": 4}), "scalar"),
        (lambda d: d["rows"][0].__setitem__(0, "a" * 4097), "text"),
        (lambda d: d.update(rows=[["A", 1]] * 5001), "5,000"),
        (lambda d: d.update(sql="secret query"), "unknown"),
    ],
)
def test_invalid_data(mutate, message):
    source = data("x y", [["A", 2]])
    mutate(source)
    with pytest.raises(ValueError, match=message):
        build_chart_option(source, spec("bar", x="x", y="y"))


@pytest.mark.req("REQ-CHART-02", "REQ-CHART-05")
@pytest.mark.parametrize(
    "bad",
    [
        {"series": []},
        {"formatter": "alert(1)"},
        {"url": "https://example.test"},
        {"animation": True},
        {"smooth": True},
        {"theme": "remote"},
        {"colors": ["red"]},
        {"x_scale": "log", "x_min": -1},
        {"renderer": "webgl"},
        {"maxima": [2]},
        {"title": 4},
    ],
)
def test_options_fail_closed(bad):
    with pytest.raises(ValueError, match=r"[Oo]ption|scale|color|title"):
        build_chart_option(data("x y", [["A", 2]]), {"type": "bar", "mapping": {"x": "x", "y": "y"}, "options": bad})


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-02")
@pytest.mark.parametrize(
    ("source", "chart", "message"),
    [
        (data("x y", [["A", 1], ["A", 2]]), spec("bar", x="x", y="y"), "duplicate"),
        (data("x y", [["A", -1]]), spec("pie", name="x", value="y"), "nonnegative"),
        (data("x y", [["A", 1]]), spec("bar", x="missing", y="y"), "column"),
        (data("x y", [["A", 1]]), spec("bar", x="x", y="x"), "number"),
        (data("x y", [["A", 1]]), spec("bar", x="x", y="y", raw="y"), "mapping"),
        (data("x y", [[2, 1], [1, 2]], kinds=["number"] * 2), spec("line", x="x", y="y"), "order"),
        (
            data("x o c l h", [["A", 4, 3, 1, 2]]),
            spec("candlestick", x="x", open="o", close="c", low="l", high="h"),
            "low",
        ),
        (
            data("x l q m r h", [["A", 1, 3, 2, 4, 5]]),
            spec("boxplot", x="x", low="l", q1="q", median="m", q3="r", high="h"),
            "order",
        ),
        (
            data("s t", [["A", "B"], ["B", "A"]], kinds=["string"] * 2),
            spec("sankey", source="s", target="t"),
            "acyclic",
        ),
        (
            data("x y z", [[1, 1, 2], [2, 2, 3]], kinds=["number"] * 3),
            spec("surface3d", x="x", y="y", z="z"),
            "complete",
        ),
        (
            data("x y z", [[1, 1, 2], [1, 1, 3]], kinds=["number"] * 3),
            spec("surface3d", x="x", y="y", z="z"),
            "duplicate",
        ),
    ],
)
def test_family_invariants(source, chart, message):
    with pytest.raises(ValueError, match=message):
        build_chart_option(source, chart, enable_3d=True)


@pytest.mark.req("REQ-CHART-02")
@pytest.mark.parametrize(
    "rows",
    [
        [["a", "missing", "A", 1]],
        [["a", "b", "A", 1], ["b", "a", "B", 1]],
        [["a", None, "A", 9], ["b", "a", "B", 1]],
        [["a", None, "A", 1], ["a", None, "B", 1]],
    ],
)
def test_hierarchy_invariants(rows):
    source = data("id parent name value", rows, kinds=["string", "string", "string", "number"])
    with pytest.raises(ValueError, match=r"parent|cycle|duplicate"):
        build_chart_option(source, spec("treemap", id="id", parent="parent", name="name", value="value"))


@pytest.mark.req("REQ-CHART-01")
def test_time_decimal_and_gaps(tmp_path: Path, vendor: None):
    source = data("x y", [[datetime(2026, 1, 1, tzinfo=UTC), Decimal("0.1")]], kinds=["datetime", "number"])
    option = build_chart_option(source, spec("time", x="x", y="y"))
    assert option["xAxis"]["type"] == "time"
    result = write_chart(source, spec("time", x="x", y="y"), output_root=tmp_path)
    assert any("precision" in warning for warning in result["warnings"])
    assert "0.1" in Path(result["path"]).read_text(encoding="utf-8")
    source["rows"][0][0] = datetime(2026, 1, 1)
    with pytest.raises(ValueError, match=r"offset|timezone"):
        build_chart_option(source, spec("time", x="x", y="y"))
    source["rows"][0][0] = date(2026, 1, 1)
    source["columns"][0]["kind"] = "date"
    assert build_chart_option(source, spec("time", x="x", y="y"))["series"]


@pytest.mark.req("REQ-CHART-04", "REQ-CHART-05", "REQ-CHART-06")
def test_html_privacy_csp_and_controls(vendor: None):
    attack = "</script><img src=https://example.test onerror=alert(1)>\u2028"
    source = data("x y unused", [[attack, 2, "DO_NOT_PERSIST"]], kinds=["string", "number", "string"])
    chart = spec("bar", x="x", y="y")
    chart["options"] = {"title": attack, "subtitle": "A private chart", "csv": True}
    html = render_chart_html(source, chart)
    assert attack not in html
    assert "DO_NOT_PERSIST" not in html
    assert "\\u003c/script\\u003e" in html
    assert "unsafe-eval" not in html
    assert "connect-src 'none'" in html
    assert "default-src 'none'" in html
    assert "Apache license / NOTICE" in html
    for script in re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, re.S):
        if script.lstrip().startswith("{"):
            continue
        import base64

        digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        assert f"'sha256-{digest}'" in html
    for control in ["theme-toggle", "reset-chart", "download-png", "download-csv", "toggle-table", "data-table"]:
        assert f'id="{control}"' in html
    assert "__sqlmemChartStatus" in html
    assert "__sqlmemChart" in html
    assert "innerHTML" not in html
    assert "richText" in html
    assert "aria-live" in html


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-03", "REQ-CHART-05")
@pytest.mark.parametrize("truncated", [True, False, None])
def test_artifact_metadata_and_private_exclusive_output(tmp_path: Path, vendor: None, truncated):
    source = data("x y", [["A", 2]])
    source["source_truncated"] = truncated
    first = write_chart(source, spec("bar", x="x", y="y"), output_root=tmp_path / "charts")
    second = write_chart(source, spec("bar", x="x", y="y"), output_root=tmp_path / "charts")
    assert set(first) == {"chart_id", "path", "chart_type", "row_count", "source_truncated", "warnings"}
    assert first["row_count"] == 1
    assert first["source_truncated"] is truncated
    assert re.fullmatch(r"[0-9a-f]{32}", first["chart_id"])
    assert first["path"] != second["path"]
    assert Path(first["path"]).is_absolute()
    assert Path(first["path"]).parent == (tmp_path / "charts").resolve()
    assert bool(first["warnings"]) is (truncated is not False)


@pytest.mark.req("REQ-CHART-05")
def test_symlink_output_rejected(tmp_path: Path, vendor: None):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        # Windows junctions do not require Developer Mode or symlink privileges.
        import subprocess

        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    with pytest.raises(ValueError, match=r"symlink|reparse"):
        write_chart(data("x y", [["A", 2]]), spec("bar", x="x", y="y"), output_root=link / "nested")
    assert not list(target.iterdir())


@pytest.mark.req("REQ-CHART-07")
def test_disabled_3d_is_explicit_and_table_retained(vendor: None, tmp_path: Path):
    source = data("x y z", [[1, 2, 3]], kinds=["number"] * 3)
    chart = spec("scatter3d", x="x", y="y", z="z")
    result = write_chart(source, chart, output_root=tmp_path)
    assert any("3D" in warning and "disabled" in warning for warning in result["warnings"])
    html = Path(result["path"]).read_text(encoding="utf-8")
    assert '"three_d_enabled":false' in html
    assert 'id="data-table"' in html
    assert "webgl-unavailable" in html
    assert "webglcontextlost" in html


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-06")
def test_empty_state_and_no_write_on_error(tmp_path: Path, vendor: None):
    source = data("x y", [])
    html = render_chart_html(source, spec("bar", x="x", y="y"))
    assert '"row_count":0' in html
    assert "empty" in html
    with pytest.raises(ValueError, match="unsupported"):
        write_chart(source, spec("custom", x="x", y="y"), output_root=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-02")
def test_multivalue_split_and_order_preservation():
    source = data("x a b", [["B", 2, 4], ["A", 3, 5]])
    chart = spec("bar", x="x", y=["a", "b"])
    chart["options"] = {"orientation": "horizontal", "stacked": True, "category_order": ["A", "B"], "zoom": True}
    option = build_chart_option(source, chart)
    assert option["yAxis"]["data"] == ["A", "B"]
    assert option["series"][0]["data"] == [3, 2]
    assert option["series"][1]["data"] == [5, 4]
    assert all(series["stack"] == "values" for series in option["series"])
    assert source["rows"] == [["B", 2, 4], ["A", 3, 5]]
    source = data("x y group", [["B", 2, "one"], ["A", 3, "two"]], kinds=["string", "number", "string"])
    option = build_chart_option(source, spec("bar", x="x", y="y", series="group"))
    assert option["xAxis"]["data"] == ["B", "A"]
    assert option["series"][0]["data"] == [2, None]
    assert option["series"][1]["data"] == [None, 3]
    with pytest.raises(ValueError, match="OR"):
        build_chart_option(source, spec("bar", x="x", y=["y", "x"], series="group"))


@pytest.mark.req("REQ-CHART-01")
def test_fractional_datetime_order_is_chronological():
    source = data("x y", [["2026-01-01T00:00:00Z", 1], ["2026-01-01T00:00:00.1Z", None]], kinds=["datetime", "number"])
    assert build_chart_option(source, spec("time", x="x", y="y"))["series"][0]["data"][1][1] is None
    source["rows"].reverse()
    with pytest.raises(ValueError, match="order"):
        build_chart_option(source, spec("time", x="x", y="y"))


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-02")
@pytest.mark.parametrize(
    ("source", "chart", "message"),
    [
        (data("x y", [["A", None]]), spec("bar", x="x", y="y"), "non-null"),
        (data("x y", [[None, 1]]), spec("line", x="x", y="y"), "non-null"),
        (data("x y", [[1, None]], kinds=["number"] * 2), spec("scatter", x="x", y="y"), "non-null"),
        (data("x y z", [[1, 2, None]], kinds=["number"] * 3), spec("scatter3d", x="x", y="y", z="z"), "non-null"),
    ],
)
def test_required_coordinates_are_not_null(source, chart, message):
    with pytest.raises(ValueError, match=message):
        build_chart_option(source, chart, enable_3d=True)


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-02")
def test_structural_normalization():
    source = data(
        "id parent name value",
        [["r", None, "Root", None], ["c", "r", "Child", 3]],
        kinds=["string", "string", "string", "number"],
    )
    option = build_chart_option(source, spec("sunburst", id="id", parent="parent", name="name", value="value"))
    assert option["series"][0]["data"][0]["value"] == 3
    source = data("x y z", [[2, 2, 4], [1, 2, 3], [2, 1, 2], [1, 1, 1]], kinds=["number"] * 3)
    option = build_chart_option(source, spec("surface3d", x="x", y="y", z="z"), enable_3d=True)
    assert len(option["series"][0]["data"]) == 4
    assert option["series"][0]["data"] == [[1, 1, 1], [2, 1, 2], [1, 2, 3], [2, 2, 4]]


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-07")
@pytest.mark.parametrize("kind", ["surface3d", "surface3D", "surface"])
@pytest.mark.parametrize("rows", [[[1, 1, 3]], [[1, 1, 3], [2, 1, 4]], [[1, 1, 3], [1, 2, 4]]])
def test_surface_rejects_degenerate_nonempty_grids(kind, rows):
    with pytest.raises(ValueError, match="at least two distinct x and two distinct y"):
        build_chart_option(data("x y z", rows, kinds=["number"] * 3), spec(kind, x="x", y="y", z="z"), enable_3d=True)


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-06", "REQ-CHART-07")
@pytest.mark.parametrize("kind", ["surface3d", "surface3D", "surface"])
def test_empty_surface_remains_an_empty_state(kind, vendor: None):
    source = data("x y z", [], kinds=["number"] * 3)
    chart = spec(kind, x="x", y="y", z="z")
    assert build_chart_option(source, chart, enable_3d=True)["series"][0]["data"] == []
    assert '"row_count":0' in render_chart_html(source, chart, enable_3d=True)


def _browser_probe(scenario: str) -> dict[str, Any]:
    import subprocess

    harness = r"""
const vm = require("node:vm");
const source = require("node:fs").readFileSync(process.argv[2], "utf8");
const scenario = process.argv[1];
const exporting = scenario.startsWith("export-");
const svg = scenario.startsWith("export-svg");
const threeD = !exporting || scenario.startsWith("export-gl");
const nativeRatio = scenario === "export-gl-high-dpr" ? 3 : 1.5;
const png = "data:image/png;base64,iVBORw0KGgo=";
const svgUrl = "data:image/svg+xml;charset=UTF-8,%3Csvg%3E";
const observed = {
  download: null, rasterized: false, engineExport: false, svgExport: false,
  enginePixelRatio: null, rasterSize: null
};
const elements = new Map();
const element = () => ({
  hidden: true, textContent: "", listeners: {},
  append() {}, replaceChildren() {}, setAttribute() {},
  addEventListener(type, callback) { this.listeners[type] = callback; },
  querySelector() { return element(); }
});
const get = (id) => {
  if (!elements.has(id)) elements.set(id, element());
  return elements.get(id);
};
get("sqlmem-chart-data").textContent = JSON.stringify({
  title: "Test", subtitle: "", theme: "dark", three_d: threeD, three_d_enabled: true,
  row_count: 1, source_truncated: false, chart_type: "bar3d", warnings: [], csv: false,
  renderer: svg ? "svg" : "canvas", value_format: "number", currency: "",
  columns: [{name: "x", label: "X", kind: "number"}], rows: [[1]], display_rows: [["1"]],
  option: {tooltip: {}, series: []}
});
const sandbox = {
  document: {
    getElementById: get, documentElement: {dataset: {}}, body: {append() {}},
    createElement(tag) {
      const node = element();
      if (tag === "canvas") {
        node.getContext = (kind) => kind === "2d" ?
          {fillRect() {}, drawImage() { observed.rasterized = true; }} :
          scenario === "webgl-missing" ? null : {getExtension() { return null; }};
        node.toDataURL = () => {
          observed.rasterSize = [node.width, node.height];
          return scenario === "export-svg-invalid-png" ? svgUrl : png;
        };
      }
      if (tag === "a") {
        node.click = () => { observed.download = {href: node.href, filename: node.download}; };
        node.remove = () => {};
      }
      return node;
    }
  },
  Blob,
  URL: {createObjectURL() { return "blob:local-svg"; }, revokeObjectURL() {}},
  Image: class {
    async decode() {
      if (scenario === "export-svg-decode-failure") throw new Error("PRIVATE_ROW_MUST_NOT_LEAK");
    }
  },
  setTimeout() { return 1; }, clearTimeout() {}, addEventListener() {},
  echarts: {
    init() {
      if (scenario === "render-failure") throw new Error("PRIVATE_ROW_MUST_NOT_LEAK");
      let finished;
      return {
        on(event, callback) { if (event === "finished") finished = callback; }, resize() {},
        setOption() {
          if (scenario === "context-loss") get("chart").listeners.webglcontextlost({preventDefault() {}});
          else if (finished) finished();
        },
        getDataURL(options) {
          observed.engineExport = true;
          observed.enginePixelRatio = options.pixelRatio;
          return scenario === "export-canvas-svg" ? svgUrl : png;
        },
        getDevicePixelRatio: scenario === "export-gl-no-api" ? undefined : () => nativeRatio,
        renderToSVGString() { observed.svgExport = true; return '<svg xmlns="http://www.w3.org/2000/svg"/>'; },
        getWidth() { return 320; }, getHeight() { return 240; }
      };
    }
  }
};
sandbox.window = sandbox;
(async () => {
  vm.runInNewContext(source, sandbox);
  if (exporting) await get("download-png").listeners.click();
  process.stdout.write(JSON.stringify({
    ...observed, status: sandbox.__sqlmemChartStatus,
    message: get("render-status").textContent,
    tableHidden: get("table-panel").hidden, pngDisabled: get("download-png").disabled
  }));
})().catch(() => { process.exitCode = 1; });
"""
    script = Path(__file__).parents[1] / "sqlmem" / "assets" / "chart.js"
    result = subprocess.run(
        ["node", "-e", harness, scenario, str(script)],
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return dict(json.loads(result.stdout))


@pytest.mark.req("REQ-CHART-05", "REQ-CHART-06", "REQ-CHART-07")
@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("render-failure", "error"),
        ("webgl-missing", "webgl-unavailable"),
        ("context-loss", "webgl-unavailable"),
    ],
)
def test_browser_mount_error_classification_and_privacy(scenario, expected):
    rendered = _browser_probe(scenario)
    assert rendered["status"] == expected
    assert rendered["tableHidden"] is False
    assert rendered["pngDisabled"] is True
    assert "PRIVATE_ROW_MUST_NOT_LEAK" not in rendered["message"]
    assert "data table" in rendered["message"]


@pytest.mark.req("REQ-CHART-05", "REQ-CHART-06")
@pytest.mark.parametrize("scenario", ["export-svg", "export-canvas"])
def test_png_download_has_png_mime_and_signature(scenario):
    import base64

    rendered = _browser_probe(scenario)
    assert rendered["status"] == "ready"
    assert rendered["download"]["filename"] == "sqlmem-chart.png"
    url = rendered["download"]["href"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")
    if scenario == "export-svg":
        assert rendered["svgExport"] is True
        assert rendered["rasterized"] is True
        assert rendered["engineExport"] is False
        assert rendered["rasterSize"] == [640, 480]


@pytest.mark.req("REQ-CHART-06", "REQ-CHART-07")
@pytest.mark.parametrize(
    ("scenario", "expected_ratio"),
    [
        ("export-canvas", 2),
        ("export-gl-native", 1.5),
        ("export-gl-high-dpr", 3),
        ("export-gl-no-api", 1),
    ],
)
def test_png_export_uses_native_gl_ratio_and_keeps_2d_supersampling(scenario, expected_ratio):
    rendered = _browser_probe(scenario)
    assert rendered["status"] == "ready"
    assert rendered["enginePixelRatio"] == expected_ratio
    assert rendered["download"]["href"].startswith("data:image/png;base64,iVBORw0KGgo")
    assert rendered["download"]["filename"] == "sqlmem-chart.png"


@pytest.mark.req("REQ-CHART-05", "REQ-CHART-06")
@pytest.mark.parametrize("scenario", ["export-canvas-svg", "export-svg-invalid-png", "export-svg-decode-failure"])
def test_png_export_failure_never_downloads_mislabeled_svg(scenario):
    rendered = _browser_probe(scenario)
    assert rendered["status"] == "error"
    assert rendered["download"] is None
    assert rendered["tableHidden"] is False
    assert "PNG export failed" in rendered["message"]
    assert "PRIVATE_ROW_MUST_NOT_LEAK" not in rendered["message"]


@pytest.mark.req("REQ-CHART-02")
def test_presentation_options_are_applied_not_ignored():
    source = data("x y z", [["A", "B", 3]], kinds=["string", "string", "number"])
    chart = spec("heatmap", x="x", y="y", value="z")
    chart["options"] = {"zoom": True, "x_min": 0, "x_max": 1, "y_min": 0, "y_max": 1}
    option = build_chart_option(source, chart)
    assert option["dataZoom"]
    assert option["xAxis"]["min"] == 0
    assert option["yAxis"]["max"] == 1
    tree = data("id parent name value", [["r", None, "Root", 4]], kinds=["string", "string", "string", "number"])
    option = build_chart_option(tree, spec("treemap", id="id", parent="parent", name="name", value="value"))
    assert option["series"][0]["sort"] is None
    numeric = data("x y", [[1, 2]], kinds=["number"] * 2)
    chart = spec("line", x="x", y="y")
    chart["options"] = {"category_order": ["1"]}
    with pytest.raises(ValueError, match="category_order"):
        build_chart_option(numeric, chart)


@pytest.mark.req("REQ-CHART-01")
def test_fixed_bounds_and_deadline(monkeypatch: pytest.MonkeyPatch):
    source = data("x y", [["A", 1]])
    chart = spec("bar", x="x", y="y")
    too_wide = data(" ".join(f"c{i}" for i in range(65)), [], kinds=["number"] * 65)
    with pytest.raises(ValueError, match="64 columns"):
        build_chart_option(too_wide, chart)
    many_groups = data(
        "x y group", [[f"A{i}", i, f"group{i}"] for i in range(33)], kinds=["string", "number", "string"]
    )
    with pytest.raises(ValueError, match="32 rendered series"):
        build_chart_option(many_groups, spec("bar", x="x", y="y", series="group"))
    many_nodes = data("s t", [[f"A{i}", f"B{i}"] for i in range(1001)], kinds=["string"] * 2)
    with pytest.raises(ValueError, match="2,000"):
        build_chart_option(many_nodes, spec("graph", source="s", target="t"))
    deep = data(
        "id parent name value",
        [[str(i), str(i - 1) if i else None, "Node", None if i < 12 else 1] for i in range(13)],
        kinds=["string", "string", "string", "number"],
    )
    with pytest.raises(ValueError, match="depth 12"):
        build_chart_option(deep, spec("treemap", id="id", parent="parent", name="name", value="value"))
    enormous = data("x y", [["A" * 4096, 1]] * 300)
    with pytest.raises(ValueError, match="2 MiB"):
        build_chart_option(enormous, chart)
    huge_spec = spec("bar", x="x", y="y")
    huge_spec["options"] = {"title": "A" * 65536}
    with pytest.raises(ValueError, match="64 KiB"):
        build_chart_option(source, huge_spec)
    ticks = iter([0.0, 6.0])
    monkeypatch.setattr("sqlmem.charts.time.monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="five seconds"):
        build_chart_option(source, chart)


@pytest.mark.req("REQ-CHART-05")
@pytest.mark.parametrize("name", ["national_id", "pwd", "CVV", "IBAN", "user_name", "tax_id", "customer.hash"])
def test_sensitive_names_cannot_be_reclassified(name):
    source = data("x y", [["A", 1]])
    source["columns"][0]["source_column"] = name
    with pytest.raises(ValueError, match="sensitive"):
        build_chart_option(source, spec("bar", x="x", y="y"))


@pytest.mark.req("REQ-CHART-05")
def test_collision_and_write_failure_leave_user_files_intact(
    tmp_path: Path, vendor: None, monkeypatch: pytest.MonkeyPatch
):
    import uuid

    identifier = uuid.UUID(int=42)
    monkeypatch.setattr("sqlmem.charts.uuid.uuid4", lambda: identifier)
    existing = tmp_path / f"{identifier.hex}.html"
    existing.write_text("KEEP_USER_FILE", encoding="utf-8")
    with pytest.raises(ValueError, match="collisions"):
        write_chart(data("x y", [["A", 1]]), spec("bar", x="x", y="y"), output_root=tmp_path)
    assert existing.read_text(encoding="utf-8") == "KEEP_USER_FILE"
    assert list(tmp_path.iterdir()) == [existing]
    temporary = tmp_path / f".{identifier.hex}.tmp"
    temporary.write_text("KEEP_OTHER_FILE", encoding="utf-8")
    with pytest.raises(ValueError, match="collisions"):
        write_chart(data("x y", [["A", 1]]), spec("bar", x="x", y="y"), output_root=tmp_path)
    assert temporary.read_text(encoding="utf-8") == "KEEP_OTHER_FILE"


@pytest.mark.req("REQ-CHART-04", "REQ-CHART-07")
def test_real_assets_are_embedded_and_gl_is_opt_in():
    source = data("x y z", [[1, 2, 3]], kinds=["number"] * 3)
    chart = spec("scatter3d", x="x", y="y", z="z")
    plain = render_chart_html(source, chart)
    enabled = render_chart_html(source, chart, enable_3d=True)
    assert "echarts-gl.LICENSE" not in plain
    assert "echarts-gl.LICENSE" in enabled
    assert "echarts.NOTICE" in plain
    assert len(enabled) > len(plain)
    match = re.search(r'<script id="sqlmem-chart-data" type="application/json">(.*?)</script>', enabled)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["format"] == "sqlmem-chart"
    assert payload["version"] == 1
    assert payload["chart_type"] == "scatter3d"
