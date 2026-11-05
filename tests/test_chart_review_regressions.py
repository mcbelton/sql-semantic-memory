import html
import json
from pathlib import Path

import pytest

import sqlmem.charts as charts
from sqlmem.charts import build_chart_option, render_chart_html
from tests.test_charts import data, spec


@pytest.mark.req("REQ-CHART-01", "REQ-CHART-02")
@pytest.mark.parametrize("kind", ["treemap", "sunburst"])
def test_fractional_hierarchy_totals_allow_only_rounding_error(kind):
    source = data(
        "id parent name value",
        [["r", None, "Root", 0.3], ["a", "r", "A", 0.1], ["b", "r", "B", 0.2]],
        kinds=["string", "string", "string", "number"],
    )
    chart = spec(kind, id="id", parent="parent", name="name", value="value")
    option = build_chart_option(source, chart)
    assert option["series"][0]["data"][0]["value"] == pytest.approx(0.3)
    source["rows"][0][3] = 0.300001
    with pytest.raises(ValueError, match="parent total conflicts"):
        build_chart_option(source, chart)
    source["rows"][0][3] = 0.3
    source["rows"][1][3] = 100000000000000.0
    source["rows"][2][3] = 100000000000000.0
    source["rows"][0][3] = 200000000000001.0
    with pytest.raises(ValueError, match="parent total conflicts"):
        build_chart_option(source, chart)
    source["rows"][1][3] = 4500000000000000
    source["rows"][2][3] = 4500000000000000
    source["rows"][0][3] = 9000000000000001
    with pytest.raises(ValueError, match="parent total conflicts"):
        build_chart_option(source, chart)


@pytest.mark.req("REQ-CHART-04")
@pytest.mark.parametrize("three_d", [False, True])
def test_standalone_includes_every_applicable_manifest_notice(three_d):
    root = Path(__file__).parents[1] / "sqlmem" / "assets" / "vendor"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    source = data("x y z", [[1, 2, 3]], kinds=["number"] * 3)
    chart = spec("scatter3d", x="x", y="y", z="z") if three_d else spec("scatter", x="x", y="y")
    rendered = html.unescape(render_chart_html(source, chart, enable_3d=three_d))
    applicable = [bundle for bundle in manifest["bundles"] if three_d or bundle["file"] == "echarts.min.js"]
    for bundle in applicable:
        for notice in bundle["notices"]:
            text = (root / notice).read_text(encoding="utf-8")
            assert text in rendered, notice
    assert rendered.count("zrender.LICENSE\n") == 1
    if not three_d:
        assert "claygl.LICENSE\n" not in rendered


@pytest.mark.req("REQ-CHART-04", "REQ-CHART-05")
@pytest.mark.parametrize(
    "manifest",
    [
        [],
        {"format": "other", "version": 1},
        {"format": "sqlmem-chart-vendor", "version": 2},
        {"format": "sqlmem-chart-vendor", "version": 1, "bundles": None},
        {"format": "sqlmem-chart-vendor", "version": 1, "bundles": []},
        {"format": "sqlmem-chart-vendor", "version": 1, "bundles": [None]},
        {"format": "sqlmem-chart-vendor", "version": 1, "bundles": [{"file": "echarts.min.js", "notices": []}]},
        {
            "format": "sqlmem-chart-vendor",
            "version": 1,
            "bundles": [{"file": "echarts.min.js", "notices": ["../outside.LICENSE"]}],
        },
    ],
)
def test_corrupt_notice_manifest_fails_closed(monkeypatch, manifest):
    original = charts._asset
    monkeypatch.setattr(
        charts, "_asset", lambda name: json.dumps(manifest) if name == "vendor/manifest.json" else original(name)
    )
    with pytest.raises(ValueError, match="Vendor notice"):
        render_chart_html(data("x y", [["A", 1]]), spec("bar", x="x", y="y"))


@pytest.mark.req("REQ-CHART-06")
def test_horizontal_category_axis_title_does_not_overlay_category_labels():
    chart = {**spec("bar", x="x", y="y"), "options": {"orientation": "horizontal"}}
    option = build_chart_option(data("x y", [["United Kingdom", 42], ["North America", 20]]), chart)
    assert option["yAxis"]["nameLocation"] == "end"
