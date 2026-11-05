"""Bounded, offline ECharts artifacts. No database or host integration lives here."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import os
import re
import stat
import time
import uuid
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeAlias, cast

Scalar: TypeAlias = bool | int | float | str | None
Json: TypeAlias = Scalar | list["Json"] | dict[str, "Json"]
JsonObject: TypeAlias = dict[str, Json]
MAX_ROWS = 5_000
MAX_COLUMNS = 64
MAX_SERIES = 32
MAX_TEXT_BYTES = 4_096
MAX_DATA_BYTES = 2 * 1024 * 1024
MAX_SPEC_BYTES = 64 * 1024
MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_NODES = 2_000
MAX_DEPTH = 12
JS_SAFE_INTEGER = 2**53 - 1
# Mirror scan.is_sensitive's name patterns without importing its SQL dependencies.
# Charts additionally reject credential/salary/address names and classify qualified source names by component.
_SENSITIVE = re.compile(
    r"passw|pwd|secret|token|apikey|privatekey|credential|ssn|socialsecurity|nationalid|taxid|"
    r"email|^mail(address)?$|phone|mobile|fax|cardnumber|creditcard|cvv|iban|birth|^dob$|salary|address|"
    r"firstname|lastname|middlename|fullname|surname|street|login|username|ipaddress|salt$|hash$"
)
_THREE_D = {"scatter3d", "bar3d", "surface3d"}
_XY = {"bar", "column", "line", "area", "time"}
_LINES = {"line", "area", "time"}
_NAMED = {"pie", "donut", "funnel", "gauge"}
_TREE = {"treemap", "sunburst"}
_EDGES = {"graph", "sankey"}
_MAPPINGS: dict[str, tuple[set[str], set[str]]] = {
    **{kind: ({"x", "y"}, {"series"}) for kind in _XY},
    **{kind: ({"name", "value"}, set()) for kind in _NAMED},
    "scatter": ({"x", "y"}, {"size", "color", "series"}),
    "bubble": ({"x", "y", "size"}, {"color", "series"}),
    "heatmap": ({"x", "y", "value"}, set()),
    **{kind: ({"id", "parent", "name", "value"}, set()) for kind in _TREE},
    "candlestick": ({"x", "open", "close", "low", "high"}, set()),
    "boxplot": ({"x", "low", "q1", "median", "q3", "high"}, set()),
    "radar": ({"name", "values"}, set()),
    **{kind: ({"source", "target"}, {"value"}) for kind in _EDGES},
    **{kind: ({"x", "y", "z"}, set()) for kind in _THREE_D},
}
_PALETTE = ("#5470c6", "#26b99a", "#fac858", "#ee6666", "#73c0de", "#b58bdf", "#e7a26e", "#8acb88")


@dataclass(frozen=True)
class Column:
    name: str
    kind: str
    label: str


@dataclass(frozen=True)
class ChartData:
    columns: tuple[Column, ...]
    rows: tuple[tuple[Scalar, ...], ...]
    display: tuple[tuple[str, ...], ...]
    source_truncated: bool | None
    total_rows: int | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Presentation:
    title: str
    subtitle: str
    theme: str
    colors: tuple[str, ...]
    legend: bool
    tooltip: bool
    zoom: bool
    csv: bool
    renderer: str
    x_label: str
    y_label: str
    z_label: str
    x_unit: str
    y_unit: str
    z_unit: str
    x_scale: str | None
    y_scale: str
    x_min: float | None
    x_max: float | None
    y_min: float | None
    y_max: float | None
    category_order: tuple[str, ...]
    orientation: str
    stacked: bool
    smooth: bool
    step: bool
    area: bool
    radius: tuple[float, float]
    symbol_size: tuple[float, float]
    visual_colors: tuple[str, ...]
    maxima: tuple[float, ...]
    minimum: float | None
    maximum: float | None
    alpha: float
    beta: float
    distance: float
    value_format: str
    currency: str


@dataclass(frozen=True)
class ChartSpec:
    kind: str
    mapping: dict[str, tuple[int, ...]]
    options: Presentation


@dataclass
class Deadline:
    end: float

    def check(self) -> None:
        if time.monotonic() > self.end:
            raise ValueError("Chart construction exceeded five seconds; reduce the input size.")


@dataclass(frozen=True)
class Prepared:
    data: ChartData
    spec: ChartSpec
    option: JsonObject
    warnings: tuple[str, ...]
    enable_3d: bool


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be an object with string keys.")
    return cast("dict[str, object]", value)


def _keys(obj: dict[str, object], required: set[str], optional: set[str], context: str) -> None:
    if not required <= obj.keys():
        raise ValueError(f"{context} is missing required fields: {', '.join(sorted(required - obj.keys()))}.")
    if obj.keys() - required - optional:
        raise ValueError(f"{context} contains unknown fields; use only the documented allowlist.")


def _text(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be text.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        raise ValueError(f"{context} contains invalid Unicode text.") from None
    if size > MAX_TEXT_BYTES:
        raise ValueError(f"{context} text exceeds 4 KiB; shorten it.")
    return value


def _sensitive_name(value: str) -> bool:
    return any(_SENSITIVE.search(re.sub(r"[^a-z0-9]", "", part.lower())) for part in value.split("."))


def _number(value: object, context: str) -> int | float:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be a number, not a boolean.")
    if isinstance(value, int):
        if abs(value) > JS_SAFE_INTEGER:
            raise ValueError(f"{context} exceeds the JavaScript safe integer range.")
        return value
    if not isinstance(value, (float, Decimal)):
        raise ValueError(f"{context} must be a scalar number.")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f"{context} must be a finite binary64 number.") from None
    if not math.isfinite(number):
        raise ValueError(f"{context} must be finite.")
    if number.is_integer() and abs(number) > JS_SAFE_INTEGER:
        raise ValueError(f"{context} exceeds the JavaScript safe integer range.")
    return number


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValueError(
            "Use finite JSON scalars and bounded arrays/objects, not executable or custom values."
        ) from None


def _safe_json(value: object) -> str:
    return _json(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _list(values: Iterable[Json]) -> list[Json]:
    return list(values)


def _normalize_cell(value: object, column: Column, warnings: list[str]) -> tuple[Scalar, str]:
    if value is None:
        return None, ""
    if not isinstance(value, (str, bool, int, float, Decimal, date, datetime)):
        raise ValueError("Rows accept declared scalar values only; nested objects/arrays are not supported.")
    if column.kind == "number":
        number = _number(value, "Numeric cell")
        if isinstance(value, Decimal):
            exact = _text(str(value), "Decimal")
            if Decimal.from_float(float(number)) != value:
                warning = "Decimal precision loss in plotted binary64 values; the table retains exact decimal text."
                if warning not in warnings:
                    warnings.append(warning)
            return number, exact
        return number, str(value)
    if column.kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError("Boolean columns require boolean scalars.")
        return value, str(value).lower()
    if column.kind in {"date", "datetime"}:
        try:
            if column.kind == "date":
                if isinstance(value, datetime) or not isinstance(value, (date, str)):
                    raise ValueError
                normalized = date.fromisoformat(value) if isinstance(value, str) else value
                result = normalized.isoformat()
            else:
                if not isinstance(value, (datetime, str)):
                    raise ValueError
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
                if timestamp.utcoffset() is None:
                    raise ValueError("Datetime values require an explicit timezone offset.")
                result = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except (ValueError, OverflowError):
            raise ValueError("Use ISO dates or ISO datetimes with an explicit timezone offset.") from None
        return result, result
    result = _text(value, "String cell")
    return result, result


def _data(raw: object, deadline: Deadline) -> ChartData:
    obj = _object(raw, "Chart data")
    _keys(obj, {"columns", "rows", "source_truncated"}, {"total_rows"}, "Chart data")
    columns_raw, rows_raw = obj["columns"], obj["rows"]
    if not isinstance(columns_raw, list) or not 1 <= len(columns_raw) <= MAX_COLUMNS:
        raise ValueError("Supply between 1 and 64 columns.")
    if not isinstance(rows_raw, list) or len(rows_raw) > MAX_ROWS:
        raise ValueError("Supply at most 5,000 rows; do not silently sample.")
    columns: list[Column] = []
    names: set[str] = set()
    for raw_column in columns_raw:
        col = _object(raw_column, "Column")
        _keys(col, {"name", "kind", "sensitivity"}, {"label", "source_column"}, "Column")
        name = _text(col["name"], "Column name")
        if not name or name in names:
            raise ValueError("Column names must be nonempty and unique; alias duplicate columns.")
        names.add(name)
        if col["sensitivity"] != "non_sensitive":
            raise ValueError("Every input column must be explicitly classified non_sensitive.")
        source = _text(col.get("source_column", ""), "Source column")
        if _sensitive_name(name) or _sensitive_name(source):
            raise ValueError("A known sensitive column name/source is not allowed in charts.")
        kind = col["kind"]
        if not isinstance(kind, str) or kind not in {"string", "number", "boolean", "date", "datetime"}:
            raise ValueError("Column kind must be string, number, boolean, date or datetime.")
        columns.append(Column(name, kind, _text(col.get("label", name), "Column label")))
    truncated = obj["source_truncated"]
    if truncated is not None and not isinstance(truncated, bool):
        raise ValueError("source_truncated must be true, false or null (unknown).")
    total: int | None = None
    if "total_rows" in obj:
        raw_total = obj["total_rows"]
        if (
            isinstance(raw_total, bool)
            or not isinstance(raw_total, int)
            or raw_total < len(rows_raw)
            or raw_total > JS_SAFE_INTEGER
        ):
            raise ValueError("total_rows must be a safe integer at least as large as the supplied row count.")
        total = raw_total
        if (truncated is False and total != len(rows_raw)) or (truncated is True and total <= len(rows_raw)):
            raise ValueError("total_rows conflicts with source_truncated and the supplied row count.")
    warnings: list[str] = []
    if truncated is True:
        warnings.append("Partial result: source was truncated; only supplied rows are plotted.")
    elif truncated is None:
        warnings.append("Source completeness is unknown; supplied rows may not represent the complete result.")
    rows: list[tuple[Scalar, ...]] = []
    display: list[tuple[str, ...]] = []
    size = len(_json([{"name": col.name, "kind": col.kind, "label": col.label} for col in columns]))
    for raw_row in rows_raw:
        deadline.check()
        if not isinstance(raw_row, list) or len(raw_row) != len(columns):
            raise ValueError("Each row must be an array matching the declared column count.")
        normalized = [_normalize_cell(value, column, warnings) for value, column in zip(raw_row, columns, strict=True)]
        row = tuple(cell[0] for cell in normalized)
        shown = tuple(cell[1] for cell in normalized)
        size += len(_json(row)) + len(_json(shown))
        if size > MAX_DATA_BYTES:
            raise ValueError("Normalized chart data exceeds 2 MiB; reduce rows, columns or text.")
        rows.append(row)
        display.append(shown)
    return ChartData(tuple(columns), tuple(rows), tuple(display), truncated, total, tuple(warnings))


_COMMON_OPTIONS = {"title", "subtitle", "theme", "colors", "legend", "tooltip", "csv", "renderer", "format", "currency"}
_AXIS_OPTIONS = {
    "x_label",
    "y_label",
    "x_unit",
    "y_unit",
    "x_scale",
    "y_scale",
    "x_min",
    "x_max",
    "y_min",
    "y_max",
    "zoom",
}


def _options(raw: object, kind: str) -> Presentation:
    obj = _object(raw, "Chart options")
    allowed = set(_COMMON_OPTIONS)
    if kind in _XY | {"scatter", "bubble", "heatmap", "candlestick", "boxplot"}:
        allowed |= _AXIS_OPTIONS
    if kind in _XY:
        allowed |= {"category_order"}
    if kind in {"bar", "column"}:
        allowed |= {"orientation", "stacked"}
    if kind in _LINES:
        allowed |= {"smooth", "step", "area", "stacked"}
    if kind in {"pie", "donut"}:
        allowed |= {"radius"}
    if kind in {"scatter", "bubble"}:
        allowed |= {"symbol_size_min", "symbol_size_max", "visual_colors"}
    if kind == "heatmap":
        allowed |= {"visual_colors"}
    if kind == "radar":
        allowed |= {"maxima"}
    if kind == "gauge":
        allowed |= {"min", "max"}
    if kind in _THREE_D:
        allowed |= {"x_label", "y_label", "z_label", "x_unit", "y_unit", "z_unit", "alpha", "beta", "distance"}
    _keys(obj, set(), allowed, "Chart options")

    def text(key: str, default: str = "") -> str:
        return _text(obj.get(key, default), f"Option {key}")

    def choice(key: str, default: str, choices: set[str]) -> str:
        value = text(key, default)
        if value not in choices:
            raise ValueError(f"Option {key} must be one of {', '.join(sorted(choices))}.")
        return value

    def boolean(key: str, default: bool) -> bool:
        value = obj.get(key, default)
        if not isinstance(value, bool):
            raise ValueError(f"Option {key} must be boolean.")
        return value

    def numeric(key: str, default: float | None = None) -> float | None:
        value = obj.get(key, default)
        return None if value is None else float(_number(value, f"Option {key}"))

    def bounded(key: str, default: float, lower: float, upper: float) -> float:
        value = numeric(key, default)
        if value is None or not lower <= value <= upper:
            raise ValueError(f"Option {key} is outside its bounded range.")
        return value

    def colors(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = obj.get(key, list(default))
        if not isinstance(value, list) or not 1 <= len(value) <= 32:
            raise ValueError(f"Option {key} requires 1 to 32 hex colors.")
        if any(not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in value):
            raise ValueError(f"Option {key} accepts only six-digit hex colors.")
        return tuple(cast("list[str]", value))

    maxima_raw = obj.get("maxima", [])
    if not isinstance(maxima_raw, list) or len(maxima_raw) > MAX_SERIES:
        raise ValueError("Option maxima must be an array of at most 32 positive numbers.")
    maxima = tuple(float(_number(value, "Option maxima")) for value in maxima_raw)
    if any(value <= 0 for value in maxima):
        raise ValueError("Option maxima must be positive.")
    order_raw = obj.get("category_order", [])
    if not isinstance(order_raw, list) or len(order_raw) > MAX_ROWS:
        raise ValueError("Option category_order must be a bounded text array.")
    order = tuple(_text(value, "Option category_order") for value in order_raw)
    if len(set(order)) != len(order):
        raise ValueError("Option category_order contains duplicate categories.")
    radius_raw = obj.get("radius", [45 if kind == "donut" else 0, 72])
    if not isinstance(radius_raw, list) or len(radius_raw) != 2:
        raise ValueError("Option radius must be [inner_percent, outer_percent].")
    inner, outer = (float(_number(value, "Option radius")) for value in radius_raw)
    if not 0 <= inner < outer <= 90:
        raise ValueError("Option radius must satisfy 0 <= inner < outer <= 90.")
    symbol_size = (bounded("symbol_size_min", 8, 2, 80), bounded("symbol_size_max", 40, 2, 80))
    if symbol_size[0] > symbol_size[1]:
        raise ValueError("Option symbol size minimum must not exceed its maximum.")
    x_scale = choice("x_scale", "auto", {"auto", "category", "linear", "log", "time"})
    y_scale = choice("y_scale", "linear", {"linear", "log"})
    x_min, x_max, y_min, y_max = (numeric(key) for key in ("x_min", "x_max", "y_min", "y_max"))
    for scale, lower, upper in ((x_scale, x_min, x_max), (y_scale, y_min, y_max)):
        if (lower is not None and upper is not None and lower >= upper) or (
            scale == "log" and any(value is not None and value <= 0 for value in (lower, upper))
        ):
            raise ValueError("Axis scale/range options require min < max and positive logarithmic bounds.")
    minimum, maximum = numeric("min"), numeric("max")
    if kind == "gauge" and (minimum is None or maximum is None or minimum < 0 or minimum >= maximum):
        raise ValueError("Gauge options require explicit nonnegative min and larger max.")
    currency = text("currency")
    value_format = choice("format", "number", {"number", "integer", "percent", "date", "currency"})
    if (currency and not re.fullmatch(r"[A-Z]{3}", currency)) or (value_format == "currency" and not currency):
        raise ValueError("Currency format requires a three-letter uppercase currency code.")
    renderer = choice("renderer", "canvas" if kind in _THREE_D else "svg", {"svg", "canvas"})
    if kind in _THREE_D and renderer != "canvas":
        raise ValueError("3D requires the canvas renderer.")
    return Presentation(
        title=text("title", "Data, in perspective"),
        subtitle=text("subtitle"),
        theme=choice("theme", "dark", {"light", "dark"}),
        colors=colors("colors", _PALETTE),
        legend=boolean("legend", True),
        tooltip=boolean("tooltip", True),
        zoom=boolean("zoom", False),
        csv=boolean("csv", False),
        renderer=renderer,
        x_label=text("x_label"),
        y_label=text("y_label"),
        z_label=text("z_label"),
        x_unit=text("x_unit"),
        y_unit=text("y_unit"),
        z_unit=text("z_unit"),
        x_scale=None if x_scale == "auto" else x_scale,
        y_scale=y_scale,
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        category_order=order,
        orientation=choice("orientation", "vertical", {"vertical", "horizontal"}),
        stacked=boolean("stacked", False),
        smooth=boolean("smooth", False),
        step=boolean("step", False),
        area=boolean("area", kind == "area"),
        radius=(inner, outer),
        symbol_size=symbol_size,
        visual_colors=colors("visual_colors", ("#d5e8ff", "#5470c6", "#853d99")),
        maxima=maxima,
        minimum=minimum,
        maximum=maximum,
        alpha=bounded("alpha", 25, -90, 90),
        beta=bounded("beta", 35, -180, 180),
        distance=bounded("distance", 200, 80, 400),
        value_format=value_format,
        currency=currency,
    )


def _spec(raw: object, data: ChartData) -> ChartSpec:
    obj = _object(raw, "Chart spec")
    if len(_json(obj)) > MAX_SPEC_BYTES:
        raise ValueError("Chart spec exceeds 64 KiB.")
    _keys(obj, {"type", "mapping"}, {"options"}, "Chart spec")
    kind_raw = obj["type"]
    if not isinstance(kind_raw, str):
        raise ValueError("Chart type must be a supported name.")
    kind = kind_raw.lower()
    if kind == "surface":
        kind = "surface3d"
    if kind not in _MAPPINGS:
        raise ValueError("Chart has an unsupported type; choose a documented native family (no custom series or maps).")
    mapping_raw = _object(obj["mapping"], "Chart mapping")
    required, optional = _MAPPINGS[kind]
    _keys(mapping_raw, required, optional, "Chart mapping")
    names = {column.name: index for index, column in enumerate(data.columns)}
    mapping: dict[str, tuple[int, ...]] = {}
    for role, value in mapping_raw.items():
        refs = value if isinstance(value, list) else [value]
        if not refs or len(refs) > (MAX_SERIES if role in {"y", "values"} and kind in _XY | {"radar"} else 1):
            raise ValueError("Mapping requires a column name (or at most 32 value columns where supported).")
        if any(not isinstance(ref, str) or ref not in names for ref in refs):
            raise ValueError("Mapping references an unknown column; use declared column names, never expressions.")
        indices = tuple(names[cast("str", ref)] for ref in refs)
        if len(set(indices)) != len(indices):
            raise ValueError("Mapping contains duplicate value columns.")
        mapping[role] = indices
    if "series" in mapping and len(mapping.get("y", ())) > 1:
        raise ValueError("Use multiple y columns OR a series split, not both.")
    numeric = {"value", "size", "z", "open", "close", "low", "high", "q1", "median", "q3", "values"}
    if kind in _XY | {"scatter", "bubble"}:
        numeric.add("y")
    if kind in {"scatter", "bubble", "scatter3d", "surface3d"}:
        numeric |= {"x", "y"}
    for role, indices in mapping.items():
        if role in numeric and any(data.columns[index].kind != "number" for index in indices):
            raise ValueError(f"Mapping {role} requires number columns.")
        if role in {"series", "name", "id", "parent", "source", "target"} and any(
            data.columns[index].kind != "string" for index in indices
        ):
            raise ValueError(f"Mapping {role} requires string columns.")
        if (
            (kind in {"heatmap", "bar3d"} and role in {"x", "y"}) or (kind in {"bar", "column"} and role == "x")
        ) and any(data.columns[index].kind not in {"string", "boolean"} for index in indices):
            raise ValueError(f"Mapping {role} requires categorical string/boolean columns.")
    options = _options(obj.get("options", {}), kind)
    if kind == "time" and data.columns[mapping["x"][0]].kind not in {"date", "datetime"}:
        raise ValueError("Time charts require a date/datetime x column with ordered values.")
    if kind == "radar" and len(options.maxima) != len(mapping["values"]):
        raise ValueError("Radar options require one explicit positive maximum per mapped dimension.")
    return ChartSpec(kind, mapping, options)


class Builder:
    """Controlled JSON output construction after scalar/schema validation."""

    def __init__(self, data: ChartData, spec: ChartSpec, deadline: Deadline) -> None:
        self.data, self.spec, self.deadline = data, spec, deadline
        self.rows, self.mapping, self.options = data.rows, spec.mapping, spec.options

    def cell(self, row: tuple[Scalar, ...], role: str, *, nullable: bool = False) -> Scalar:
        value = row[self.mapping[role][0]]
        if value is None and not nullable:
            raise ValueError(f"Mapping {role} requires non-null values.")
        return value

    def number(self, row: tuple[Scalar, ...], role: str, *, nonnegative: bool = False) -> float:
        value = _number(self.cell(row, role), f"Mapping {role}")
        if nonnegative and value < 0:
            raise ValueError(f"Mapping {role} requires nonnegative values.")
        return float(value)

    def label(self, role: str) -> str:
        return self.data.columns[self.mapping[role][0]].label

    def unique(self, keys: Iterable[tuple[Scalar, ...]]) -> None:
        seen: set[tuple[Scalar, ...]] = set()
        for key in keys:
            self.deadline.check()
            if key in seen:
                raise ValueError(
                    "A duplicate category/series or coordinate cell requires explicit upstream aggregation."
                )
            seen.add(key)

    def axis(self, axis_type: str, name: str, unit: str, categories: list[Json] | None = None) -> JsonObject:
        result: JsonObject = {
            "type": axis_type,
            "name": f"{name} ({unit})" if unit else name,
            "nameLocation": "middle",
            "nameGap": 34,
            "axisLine": {"lineStyle": {"color": "#8796ad"}},
            "axisLabel": {"hideOverlap": True},
            "splitLine": {"lineStyle": {"color": "#8796ad", "opacity": 0.15}},
        }
        if categories is not None:
            result["data"] = categories
        return result

    def axes(self, option: JsonObject, *, financial: bool = False) -> str:
        column = self.data.columns[self.mapping["x"][0]]
        detected = (
            "time" if column.kind in {"date", "datetime"} else ("value" if column.kind == "number" else "category")
        )
        requested = self.options.x_scale
        axis_type = "value" if requested == "linear" else requested or detected
        if axis_type == "time" and detected != "time":
            raise ValueError("Time scale requires a date/datetime column.")
        if axis_type in {"value", "log"} and column.kind != "number":
            raise ValueError("Numeric/log x scale requires a number column.")
        if self.options.category_order and axis_type != "category":
            raise ValueError("Option category_order applies only to a categorical x scale.")
        if financial and axis_type != "category" and column.kind == "number":
            raise ValueError("Financial x requires ordered category/date labels, not a numeric scale.")
        categories = None
        if axis_type == "category" or financial:
            values = list(dict.fromkeys(self.cell(row, "x") for row in self.rows))
            if self.options.category_order:
                if set(self.options.category_order) != set(values):
                    raise ValueError("Option category_order must list exactly the mapped categories.")
                values = list(self.options.category_order)
            categories = _list(values)
            axis_type = "category"
        x_axis = self.axis(axis_type, self.options.x_label or self.label("x"), self.options.x_unit, categories)
        y_axis = self.axis(
            "log" if self.options.y_scale == "log" else "value",
            self.options.y_label or (self.label("y") if "y" in self.mapping else "Value"),
            self.options.y_unit,
        )
        for axis, lower, upper in (
            (x_axis, self.options.x_min, self.options.x_max),
            (y_axis, self.options.y_min, self.options.y_max),
        ):
            if lower is not None:
                axis["min"] = lower
            if upper is not None:
                axis["max"] = upper
        if axis_type == "log" and any(self.number(row, "x") <= 0 for row in self.rows):
            raise ValueError("Log x scale requires positive data.")
        if self.options.y_scale == "log":
            for row in self.rows:
                for index in self.mapping.get("y", ()):
                    if row[index] is not None and _number(row[index], "Log y data") <= 0:
                        raise ValueError("Log y scale requires positive data.")
        option.update(xAxis=x_axis, yAxis=y_axis)
        if self.options.zoom:
            option["dataZoom"] = [{"type": "inside", "filterMode": "none"}, {"type": "slider", "filterMode": "none"}]
        return axis_type

    def ordered(self, *, split: bool = False) -> None:
        previous: dict[Scalar, float | str] = {}
        column_kind = self.data.columns[self.mapping["x"][0]].kind
        for row in self.rows:
            self.deadline.check()
            group = self.cell(row, "series") if split else ""
            raw_value = self.cell(row, "x")
            if column_kind == "datetime":
                timestamp = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
                value: float | str = (timestamp - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
            elif column_kind == "date":
                value = float(date.fromisoformat(str(raw_value)).toordinal())
            elif isinstance(raw_value, (int, float)):
                value = float(raw_value)
            else:
                value = str(raw_value)
            last = previous.get(group)
            if last is not None:
                # Schema validation guarantees one comparable scalar type per column.
                if isinstance(value, (int, float)) and isinstance(last, (int, float)):
                    invalid = value <= last
                else:
                    invalid = str(value) <= str(last)
                if invalid:
                    raise ValueError("Input must already be in strictly ascending x order within each series.")
            previous[group] = value

    def xy(self, option: JsonObject) -> list[Json]:
        kind = self.spec.kind
        axis_type = self.axes(option)
        split = "series" in self.mapping
        self.unique((self.cell(row, "x"), self.cell(row, "series") if split else "") for row in self.rows)
        if kind in _LINES and self.data.columns[self.mapping["x"][0]].kind in {"number", "date", "datetime"}:
            self.ordered(split=split)
        groups = list(dict.fromkeys(self.cell(row, "series") for row in self.rows)) if split else [""]
        if len(groups) * len(self.mapping["y"]) > MAX_SERIES:
            raise ValueError("Chart exceeds 32 rendered series; reduce mapped columns or series groups.")
        series: list[Json] = []
        for group in groups:
            for index in self.mapping["y"]:
                self.deadline.check()
                name = str(group) if split else self.data.columns[index].label
                selected = [row for row in self.rows if not split or self.cell(row, "series") == group]
                if kind in {"bar", "column"} and any(row[index] is None for row in selected):
                    raise ValueError(
                        "Bar/column y values must be non-null; explicit gaps are supported in line charts."
                    )
                points: list[Json]
                if axis_type == "category":
                    lookup = {self.cell(row, "x"): row[index] for row in selected}
                    axis = cast("JsonObject", option["xAxis"])
                    points = [lookup.get(cast("Scalar", category)) for category in cast("list[Json]", axis["data"])]
                else:
                    points = [[self.cell(row, "x"), row[index]] for row in selected]
                item: JsonObject = {
                    "type": "bar" if kind in {"bar", "column"} else "line",
                    "name": name,
                    "data": points,
                    "emphasis": {"focus": "series"},
                    "connectNulls": False,
                }
                if self.options.stacked:
                    item["stack"] = "values"
                if kind in _LINES:
                    item["smooth"] = self.options.smooth
                    item["step"] = "middle" if self.options.step else False
                    item["showSymbol"] = len(selected) < 100
                    if self.options.area:
                        item["areaStyle"] = {"opacity": 0.2}
                else:
                    item["barMaxWidth"] = 48
                    item["itemStyle"] = {"borderRadius": 4}
                series.append(item)
        if self.options.orientation == "horizontal":
            option["xAxis"], option["yAxis"] = option["yAxis"], option["xAxis"]
            category_axis = option["yAxis"]
            if not isinstance(category_axis, dict):
                raise ValueError("Horizontal bars require a categorical axis.")
            category_axis["nameLocation"] = "end"
            category_axis["nameGap"] = 18
            if "dataZoom" in option:
                option["dataZoom"] = [{"type": "inside", "yAxisIndex": 0}, {"type": "slider", "yAxisIndex": 0}]
        return series

    def named(self) -> list[Json]:
        kind = self.spec.kind
        self.unique((self.cell(row, "name"),) for row in self.rows)
        values: list[Json] = [
            {"name": self.cell(row, "name"), "value": self.number(row, "value", nonnegative=True)} for row in self.rows
        ]
        item: JsonObject = {"type": "pie" if kind in {"pie", "donut"} else kind, "data": values}
        if kind in {"pie", "donut"}:
            item["radius"] = [f"{value:g}%" for value in self.options.radius]
            item["avoidLabelOverlap"] = True
            item["label"] = {"overflow": "truncate", "width": 120}
        elif kind == "funnel":
            item.update(sort="none", left="15%", width="70%", gap=4)
        elif kind == "gauge":
            if len(self.rows) != 1 and self.rows:
                raise ValueError("Gauge requires exactly one row.")
            for row in self.rows:
                value = self.number(row, "value")
                if (
                    self.options.minimum is None
                    or self.options.maximum is None
                    or not (self.options.minimum <= value <= self.options.maximum)
                ):
                    raise ValueError("Gauge value must lie within the explicit min/max options.")
            item.update(
                min=self.options.minimum,
                max=self.options.maximum,
                progress={"show": True},
                detail={"fontSize": 28},
                axisLabel={"fontSize": 10},
            )
        return [item]

    def scatter(self, option: JsonObject) -> list[Json]:
        self.axes(option)
        split = "series" in self.mapping
        groups = list(dict.fromkeys(self.cell(row, "series") for row in self.rows)) if split else [""]
        if len(groups) > MAX_SERIES:
            raise ValueError("Chart exceeds 32 rendered series.")
        sizes = [self.number(row, "size", nonnegative=True) for row in self.rows] if "size" in self.mapping else []
        size_min, size_max = (min(sizes), max(sizes)) if sizes else (0.0, 0.0)
        colors: dict[Scalar, str] = {}
        numeric_color = "color" in self.mapping and self.data.columns[self.mapping["color"][0]].kind == "number"
        if "color" in self.mapping and not numeric_color:
            for row in self.rows:
                color = self.cell(row, "color")
                colors.setdefault(color, self.options.colors[len(colors) % len(self.options.colors)])
                if len(colors) > MAX_SERIES:
                    raise ValueError("Categorical color exceeds 32 distinct groups.")
        series: list[Json] = []
        for group in groups:
            points: list[Json] = []
            for row in self.rows:
                self.deadline.check()
                if split and self.cell(row, "series") != group:
                    continue
                point: JsonObject = {"value": [self.cell(row, "x"), self.cell(row, "y")]}
                if "size" in self.mapping:
                    size = self.number(row, "size", nonnegative=True)
                    ratio = (size - size_min) / (size_max - size_min) if size_max != size_min else 0.5
                    point["symbolSize"] = self.options.symbol_size[0] + ratio * (
                        self.options.symbol_size[1] - self.options.symbol_size[0]
                    )
                else:
                    point["symbolSize"] = self.options.symbol_size[0]
                if numeric_color:
                    point["value"] = [self.cell(row, "x"), self.cell(row, "y"), self.cell(row, "color")]
                elif colors:
                    point["itemStyle"] = {"color": colors[self.cell(row, "color")]}
                points.append(point)
            series.append({"type": "scatter", "name": str(group) if split else self.label("y"), "data": points})
        if numeric_color:
            values = [self.number(row, "color") for row in self.rows]
            self.visual(option, values, dimension=2)
        return series

    def visual(self, option: JsonObject, values: list[float], *, dimension: int = 2) -> None:
        option["visualMap"] = {
            "min": min(values, default=0),
            "max": max(values, default=1),
            "calculable": True,
            "dimension": dimension,
            "orient": "horizontal",
            "left": "center",
            "bottom": 0,
            "inRange": {"color": _list(self.options.visual_colors)},
        }

    def heatmap(self, option: JsonObject) -> list[Json]:
        if self.options.x_scale not in {None, "category"} or self.options.y_scale != "linear":
            raise ValueError("Heatmap axes are categorical; numeric/log scale options are not applicable.")
        self.unique((self.cell(row, "x"), self.cell(row, "y")) for row in self.rows)
        xs = list(dict.fromkeys(self.cell(row, "x") for row in self.rows))
        ys = list(dict.fromkeys(self.cell(row, "y") for row in self.rows))
        x_index, y_index = {value: i for i, value in enumerate(xs)}, {value: i for i, value in enumerate(ys)}
        option["xAxis"] = self.axis("category", self.options.x_label or self.label("x"), self.options.x_unit, _list(xs))
        option["yAxis"] = self.axis("category", self.options.y_label or self.label("y"), self.options.y_unit, _list(ys))
        for key, lower, upper in (
            ("xAxis", self.options.x_min, self.options.x_max),
            ("yAxis", self.options.y_min, self.options.y_max),
        ):
            axis = cast("JsonObject", option[key])
            if lower is not None:
                axis["min"] = lower
            if upper is not None:
                axis["max"] = upper
        if self.options.zoom:
            option["dataZoom"] = [
                {"type": "inside", "xAxisIndex": 0, "filterMode": "none"},
                {"type": "slider", "xAxisIndex": 0, "filterMode": "none"},
                {"type": "inside", "yAxisIndex": 0, "filterMode": "none"},
            ]
        self.visual(
            option,
            [self.number(row, "value") for row in self.rows if self.cell(row, "value", nullable=True) is not None],
        )
        points: list[Json] = [
            [x_index[self.cell(row, "x")], y_index[self.cell(row, "y")], self.cell(row, "value", nullable=True)]
            for row in self.rows
        ]
        return [{"type": "heatmap", "data": points, "emphasis": {"itemStyle": {"borderWidth": 2}}}]

    def hierarchy(self) -> list[Json]:
        if len(self.rows) > MAX_NODES:
            raise ValueError("Hierarchy exceeds 2,000 nodes.")
        by_id: dict[str, tuple[Scalar, ...]] = {}
        children: dict[str | None, list[str]] = {}
        for row in self.rows:
            key = str(self.cell(row, "id"))
            if not key or key in by_id:
                raise ValueError("Hierarchy requires unique nonempty IDs; duplicate ID found.")
            by_id[key] = row
            parent_cell = self.cell(row, "parent", nullable=True)
            parent = None if parent_cell is None else str(parent_cell)
            children.setdefault(parent, []).append(key)
        for row in self.rows:
            parent_value = self.cell(row, "parent", nullable=True)
            if parent_value is not None and parent_value not in by_id:
                raise ValueError("Hierarchy parent is missing; supply all referenced parents.")
        built: dict[str, JsonObject] = {}
        totals: dict[str, float] = {}

        def visit(key: str, ancestors: frozenset[str]) -> None:
            self.deadline.check()
            if key in ancestors:
                raise ValueError("Hierarchy contains a parent cycle.")
            if len(ancestors) >= MAX_DEPTH:
                raise ValueError("Hierarchy exceeds maximum depth 12.")
            if key in built:
                return
            row = by_id[key]
            descendants = children.get(key, [])
            for child in descendants:
                visit(child, ancestors | {key})
            supplied = self.cell(row, "value", nullable=True)
            if descendants:
                total = math.fsum(totals[child] for child in descendants)
                if not math.isfinite(total) or abs(total) > JS_SAFE_INTEGER:
                    raise ValueError("Hierarchy derived parent total exceeds the finite/safe number range.")
                if supplied is not None:
                    supplied_number = self.number(row, "value", nonnegative=True)
                    tolerance = max(math.ulp(supplied_number), math.ulp(total)) * 2
                    matches = (
                        supplied_number == total
                        if supplied_number.is_integer() and total.is_integer()
                        else math.isclose(supplied_number, total, rel_tol=0, abs_tol=tolerance)
                    )
                    if not matches:
                        raise ValueError("Hierarchy parent total conflicts with its leaf-derived sum.")
            else:
                total = self.number(row, "value", nonnegative=True)
            totals[key] = total
            node: JsonObject = {"id": key, "name": self.cell(row, "name"), "value": total}
            if descendants:
                node["children"] = [built[child] for child in descendants]
            built[key] = node

        for key in by_id:
            visit(key, frozenset())
        roots: list[Json] = [built[key] for key in children.get(None, [])]
        return [
            {
                "type": self.spec.kind,
                "data": roots,
                "roam": self.spec.kind == "treemap",
                "label": {"overflow": "truncate"},
                "breadcrumb": {"show": True},
                "sort": None,
            }
        ]

    def financial(self, option: JsonObject) -> list[Json]:
        self.unique((self.cell(row, "x"),) for row in self.rows)
        if self.data.columns[self.mapping["x"][0]].kind in {"number", "date", "datetime"}:
            self.ordered()
        self.axes(option, financial=True)
        roles = (
            ("open", "close", "low", "high")
            if self.spec.kind == "candlestick"
            else ("low", "q1", "median", "q3", "high")
        )
        values: list[Json] = []
        for row in self.rows:
            points = [self.number(row, role) for role in roles]
            if self.spec.kind == "candlestick":
                opening, closing, low, high = points
                if not low <= min(opening, closing) <= max(opening, closing) <= high:
                    raise ValueError("Candlestick low/high must enclose both open and close.")
            elif points != sorted(points):
                raise ValueError("Boxplot values must be in low <= q1 <= median <= q3 <= high order.")
            if self.options.y_scale == "log" and any(value <= 0 for value in points):
                raise ValueError("Log y scale requires positive financial data.")
            values.append(_list(points))
        return [
            {
                "type": self.spec.kind,
                "name": "Price" if self.spec.kind == "candlestick" else "Distribution",
                "data": values,
            }
        ]

    def radar(self, option: JsonObject) -> list[Json]:
        self.unique((self.cell(row, "name"),) for row in self.rows)
        if len(self.rows) > MAX_SERIES:
            raise ValueError("Radar exceeds 32 rendered series.")
        option["radar"] = {
            "indicator": [
                {"name": self.data.columns[index].label, "max": maximum}
                for index, maximum in zip(self.mapping["values"], self.options.maxima, strict=True)
            ]
        }
        values: list[Json] = []
        for row in self.rows:
            numbers = [float(_number(row[index], "Radar values")) for index in self.mapping["values"]]
            if any(not 0 <= number <= maximum for number, maximum in zip(numbers, self.options.maxima, strict=True)):
                raise ValueError("Radar values must be nonnegative and not exceed explicit maxima.")
            values.append({"name": self.cell(row, "name"), "value": _list(numbers)})
        return [{"type": "radar", "data": values, "areaStyle": {"opacity": 0.12}}]

    def edges(self) -> list[Json]:
        self.unique((self.cell(row, "source"), self.cell(row, "target")) for row in self.rows)
        nodes: dict[str, None] = {}
        links: list[Json] = []
        adjacency: dict[str, list[str]] = {}
        degrees: dict[str, int] = {}
        for row in self.rows:
            self.deadline.check()
            source, target = str(self.cell(row, "source")), str(self.cell(row, "target"))
            if not source or not target:
                raise ValueError("Edges require nonempty source and target names.")
            nodes[source] = nodes[target] = None
            if len(nodes) > MAX_NODES:
                raise ValueError("Graph exceeds 2,000 derived nodes.")
            value = self.number(row, "value", nonnegative=True) if "value" in self.mapping else 1.0
            # Use generated IDs so labels such as '__proto__' stay data in vendor internals.
            links.append({"source": source, "target": target, "value": value})
            adjacency.setdefault(source, []).append(target)
            degrees.setdefault(source, 0)
            degrees[target] = degrees.get(target, 0) + 1
        if self.spec.kind == "sankey":
            queue = deque(node for node, degree in degrees.items() if degree == 0)
            count = 0
            while queue:
                self.deadline.check()
                node = queue.popleft()
                count += 1
                for target in adjacency.get(node, []):
                    degrees[target] -= 1
                    if degrees[target] == 0:
                        queue.append(target)
            if count != len(nodes):
                raise ValueError("Sankey requires an acyclic directed graph; remove cycles/self edges.")
        ids = {node: f"node-{index}" for index, node in enumerate(nodes)}
        normalized_links: list[Json] = []
        for link in links:
            obj = cast("JsonObject", link)
            normalized_links.append(
                {"source": ids[str(obj["source"])], "target": ids[str(obj["target"])], "value": obj["value"]}
            )
        item: JsonObject = {
            "type": self.spec.kind,
            "data": [
                {"name": ids[node], "id": ids[node], "label": {"show": True}, "displayName": node} for node in nodes
            ],
            "links": normalized_links,
            "emphasis": {"focus": "adjacency"},
        }
        if self.spec.kind == "graph":
            item.update(layout="circular", roam=True, symbolSize=26, label={"show": True}, lineStyle={"opacity": 0.45})
        return [item]

    def three_d(self, option: JsonObject) -> list[Json]:
        kind = self.spec.kind
        points: list[Json] = []
        if kind in {"surface3d", "bar3d"}:
            self.unique((self.cell(row, "x"), self.cell(row, "y")) for row in self.rows)
        for role in ("x", "y", "z"):
            categories = None
            if kind == "bar3d" and role != "z":
                categories = _list(dict.fromkeys(self.cell(row, role) for row in self.rows))
            option[f"{role}Axis3D"] = self.axis(
                "category" if categories is not None else "value",
                getattr(self.options, f"{role}_label") or self.label(role),
                getattr(self.options, f"{role}_unit"),
                categories,
            )
        if kind == "surface3d":
            xs = sorted({self.number(row, "x") for row in self.rows})
            ys = sorted({self.number(row, "y") for row in self.rows})
            if self.rows and (len(xs) < 2 or len(ys) < 2):
                raise ValueError(
                    "Surface requires at least two distinct x and two distinct y coordinates; supply a 2D grid."
                )
            if len(xs) * len(ys) != len(self.rows):
                raise ValueError("Surface requires a complete unique rectangular numeric grid; supply missing cells.")
            lookup = {(self.number(row, "x"), self.number(row, "y")): self.number(row, "z") for row in self.rows}
            points = [[x, y, lookup[x, y]] for y in ys for x in xs]
        else:
            indices: dict[str, dict[Scalar, int]] = {}
            if kind == "bar3d":
                for role in ("x", "y"):
                    indices[role] = {
                        value: i for i, value in enumerate(dict.fromkeys(self.cell(row, role) for row in self.rows))
                    }
            for row in self.rows:
                points.append(
                    [
                        indices["x"][self.cell(row, "x")] if indices else self.cell(row, "x"),
                        indices["y"][self.cell(row, "y")] if indices else self.cell(row, "y"),
                        self.cell(row, "z"),
                    ]
                )
        for row in self.rows:
            for role in ("x", "y", "z"):
                self.cell(row, role)
        option["grid3D"] = {
            "viewControl": {"alpha": self.options.alpha, "beta": self.options.beta, "distance": self.options.distance},
            "environment": "auto",
            "boxWidth": 100,
            "boxDepth": 80,
            "light": {"main": {"intensity": 1.1}},
            "postEffect": {
                "enable": False,
                "bloom": {"enable": False},
                "screenSpaceAmbientOcclusion": {"enable": False},
                "screenSpaceReflection": {"enable": False},
                "FXAA": {"enable": False},
            },
            "temporalSuperSampling": {"enable": False},
        }
        self.visual(option, [self.number(row, "z") for row in self.rows])
        return [
            {
                "type": {"scatter3d": "scatter3D", "bar3d": "bar3D", "surface3d": "surface"}[kind],
                "data": points,
                "shading": "color",
            }
        ]

    def build(self) -> JsonObject:
        option: JsonObject = {
            "animation": False,
            "backgroundColor": "transparent",
            "color": _list(self.options.colors),
            "tooltip": {
                "show": self.options.tooltip,
                "renderMode": "richText",
                "confine": True,
                "trigger": "item",
                "textStyle": {"fontFamily": "sans-serif"},
            },
            "legend": {"show": self.options.legend, "type": "scroll", "top": 0, "padding": 8},
            "grid": {"left": 24, "right": 36, "top": 64, "bottom": 80, "containLabel": True},
            "aria": {"enabled": True, "decal": {"show": False}},
        }
        kind = self.spec.kind
        if kind in _XY:
            series = self.xy(option)
        elif kind in _NAMED:
            series = self.named()
        elif kind in {"scatter", "bubble"}:
            series = self.scatter(option)
        elif kind == "heatmap":
            series = self.heatmap(option)
        elif kind in _TREE:
            series = self.hierarchy()
        elif kind in {"candlestick", "boxplot"}:
            series = self.financial(option)
        elif kind == "radar":
            series = self.radar(option)
        elif kind in _EDGES:
            series = self.edges()
        else:
            series = self.three_d(option)
        option["series"] = series
        self.deadline.check()
        return option


def _prepare(data: object, spec: object, enable_3d: bool, deadline: Deadline) -> Prepared:
    if not isinstance(enable_3d, bool):
        raise ValueError("enable_3d must be a trusted boolean.")
    normalized = _data(data, deadline)
    parsed = _spec(spec, normalized)
    option = Builder(normalized, parsed, deadline).build()
    warnings = list(normalized.warnings)
    if parsed.kind in _THREE_D and not enable_3d:
        warnings.append(
            "3D rendering is disabled; enable the trusted 3D setting to render. The data table is retained."
        )
    return Prepared(normalized, parsed, option, tuple(warnings), enable_3d)


def build_chart_option(data: dict[str, Any], spec: dict[str, Any], *, enable_3d: bool = False) -> dict[str, Any]:
    """Validate scalars, mappings, invariants and options; return controlled ECharts JSON."""
    return _prepare(data, spec, enable_3d, Deadline(time.monotonic() + 5)).option


def _asset(name: str) -> str:
    try:
        return (Path(__file__).parent / "assets" / name).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ValueError(
            "Required offline chart assets are missing or unreadable; reinstall the packaged assets."
        ) from None


def _payload(prepared: Prepared) -> JsonObject:
    data, spec = prepared.data, prepared.spec
    indices = sorted({index for values in spec.mapping.values() for index in values})
    return {
        "format": "sqlmem-chart",
        "version": 1,
        "chart_type": spec.kind,
        "row_count": len(data.rows),
        "source_truncated": data.source_truncated,
        "total_rows": data.total_rows,
        "warnings": _list(prepared.warnings),
        "title": spec.options.title,
        "subtitle": spec.options.subtitle,
        "theme": spec.options.theme,
        "renderer": spec.options.renderer,
        "csv": spec.options.csv,
        "value_format": spec.options.value_format,
        "currency": spec.options.currency,
        "three_d": spec.kind in _THREE_D,
        "three_d_enabled": prepared.enable_3d,
        "columns": [
            {"name": data.columns[index].name, "label": data.columns[index].label, "kind": data.columns[index].kind}
            for index in indices
        ],
        "rows": [_list(row[index] for index in indices) for row in data.rows],
        "display_rows": [_list(row[index] for index in indices) for row in data.display],
        "option": prepared.option,
    }


def _notice_files(three_d: bool) -> list[str]:
    try:
        manifest = json.loads(_asset("vendor/manifest.json"))
    except json.JSONDecodeError:
        raise ValueError("Vendor notice manifest is invalid; reinstall the packaged chart assets.") from None
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "sqlmem-chart-vendor"
        or manifest.get("version") != 1
    ):
        raise ValueError("Vendor notice manifest has an unsupported format; reinstall the packaged chart assets.")
    bundles = manifest.get("bundles")
    if not isinstance(bundles, list) or len(bundles) > 8:
        raise ValueError("Vendor notice manifest must list the pinned chart bundles.")
    required = {"echarts.min.js", *(["echarts-gl.min.js"] if three_d else [])}
    found: set[str] = set()
    notices: list[str] = []
    for bundle in bundles:
        if not isinstance(bundle, dict) or not isinstance(bundle.get("file"), str):
            raise ValueError("Vendor notice manifest must name each pinned bundle.")
        if bundle["file"] not in required:
            continue
        found.add(bundle["file"])
        files = bundle.get("notices")
        if not isinstance(files, list) or not files or len(files) > 32:
            raise ValueError("Vendor notice manifest must list the bundle's license and notice files.")
        for name in files:
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
                raise ValueError("Vendor notice filenames must be local vendor basenames.")
            if name not in notices:
                notices.append(name)
    if found != required:
        raise ValueError("Vendor notice manifest is missing a required chart bundle.")
    return notices


def _render(prepared: Prepared, deadline: Deadline) -> str:
    scripts = [_asset("vendor/echarts.min.js")]
    if prepared.spec.kind in _THREE_D and prepared.enable_3d:
        scripts.append(_asset("vendor/echarts-gl.min.js"))
    notice_files = _notice_files(prepared.spec.kind in _THREE_D and prepared.enable_3d)
    scripts.append(_asset("chart.js"))
    # These are reviewed fixed assets, never caller programs. Reject malformed packaging rather than break out.
    if any(re.search(r"</script", script, re.I) for script in scripts):
        raise ValueError("Offline vendor script contains an unsafe HTML script terminator.")
    hashes = [
        "'sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii") + "'"
        for script in scripts
    ]
    csp = (
        "default-src 'none'; script-src " + " ".join(hashes) + "; "
        "style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; object-src 'none'; "
        "frame-src 'none'; worker-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'"
    )
    notices = "\n\n".join(f"{name}\n{_asset('vendor/' + name)}" for name in notice_files)
    template = _asset("chart.html")
    replacements = {
        "@@CSP@@": html.escape(csp, quote=False),
        "@@STYLE@@": _asset("chart.css"),
        "@@PAYLOAD@@": _safe_json(_payload(prepared)),
        "@@SCRIPTS@@": "\n".join(f"<script>{script}</script>" for script in scripts),
        "@@NOTICES@@": html.escape(notices),
    }
    # A single substitution prevents user text from being interpreted as template placeholders.
    result = re.sub(r"@@[A-Z]+@@", lambda match: replacements[match[0]], template)
    if len(result.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("Final chart HTML exceeds 8 MiB; reduce the plotted data.")
    deadline.check()
    return result


def render_chart_html(data: dict[str, Any], spec: dict[str, Any], *, enable_3d: bool = False) -> str:
    """Return the sole standalone/viewer HTML, with fixed code hashes and mapped data only."""
    deadline = Deadline(time.monotonic() + 5)
    return _render(_prepare(data, spec, enable_3d, deadline), deadline)


def _trusted_root(output_root: Path) -> Path:
    # Inspect before resolve/mkdir: resolving first would hide junction and symlink ancestors.
    if ".." in output_root.parts:
        raise ValueError("Chart output root must not contain parent traversal components.")
    absolute = Path(os.path.abspath(output_root))
    for component in (*reversed(absolute.parents), absolute):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Chart output root must not contain a symlink or reparse point.")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("Chart output root ancestors must be directories.")
    try:
        absolute.mkdir(parents=True, exist_ok=True, mode=0o700)
        canonical = absolute.resolve(strict=True)
    except OSError:
        raise ValueError("Cannot create the trusted private chart output directory.") from None
    if canonical != absolute:
        raise ValueError("Chart output root changed during canonical containment validation.")
    return canonical


def write_chart(
    data: dict[str, Any],
    spec: dict[str, Any],
    *,
    output_root: Path,
    enable_3d: bool = False,
) -> dict[str, Any]:
    """Publish a new private UUID HTML atomically without replacing an existing artifact.

    The root is trusted startup configuration, not a user-selected path. Its ancestors must not
    be concurrently writable by an adversary (the same trust boundary as the local viewer).
    """
    deadline = Deadline(time.monotonic() + 5)
    prepared = _prepare(data, spec, enable_3d, deadline)
    content = _render(prepared, deadline).encode("utf-8")
    root = _trusted_root(output_root)
    chart_id = uuid.uuid4().hex
    path = root / f"{chart_id}.html"
    temporary = root / f".{uuid.uuid4().hex}.tmp"
    if path.parent != root or path.resolve().parent != root:
        raise ValueError("Chart artifact escaped the trusted output root.")
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link publication is atomic and exclusive on Windows and POSIX; rename can overwrite.
        os.link(temporary, path)
    except OSError:
        raise ValueError("Cannot publish a private chart artifact; check permissions and output collisions.") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            temporary.unlink(missing_ok=True)
    return {
        "chart_id": chart_id,
        "path": str(path),
        "chart_type": prepared.spec.kind,
        "row_count": len(prepared.data.rows),
        "source_truncated": prepared.data.source_truncated,
        "warnings": list(prepared.warnings),
    }
