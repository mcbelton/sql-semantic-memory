import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.conftest import tool_text

SPEC = {"type": "bar", "mapping": {"x": "category", "y": ["revenue"]}, "options": {"title": "Revenue"}}
COLUMNS = [
    {"name": "category", "kind": "string", "sensitivity": "non_sensitive"},
    {"name": "revenue", "kind": "number", "sensitivity": "non_sensitive"},
]


@pytest.mark.req("REQ-CHART-03", "REQ-MCP-01", "REQ-CHART-05")
def test_chart_tool_rows_without_database_and_write_annotations(kb):
    from mcp.client.client import Client

    from sqlmem.mcp_server import create_server

    async def run():
        async with Client(create_server(kb)) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert "create_chart" in tools
            annotations = tools["create_chart"].annotations
            assert annotations is not None
            assert annotations.read_only_hint is False
            assert annotations.idempotent_hint is False
            with patch("sqlmem.mcp_server.run_select", side_effect=AssertionError("Rows must not query")):
                result = await client.call_tool(
                    "create_chart",
                    {
                        "source": {
                            "kind": "rows",
                            "columns": COLUMNS,
                            "rows": [["Bikes", 42], ["Helmets", 7]],
                            "source_truncated": None,
                        },
                        "spec": SPEC,
                    },
                )
            assert not result.is_error, tool_text(result)
            artifact = json.loads(tool_text(result))
            assert artifact["row_count"] == 2
            assert artifact["source_truncated"] is None
            path = Path(artifact["path"])
            assert path.is_relative_to(kb.root / "build" / "charts")
            assert path.is_file()
            assert "source_truncated" in path.read_text(encoding="utf-8")

    asyncio.run(run())


@pytest.mark.req("REQ-CHART-03", "REQ-SAFE-01", "REQ-SAFE-03", "REQ-CHART-05")
def test_chart_sql_caps_safety_and_sanitized_errors(kb, engine):
    from mcp.client.client import Client

    from sqlmem.db import run_select
    from sqlmem.mcp_server import create_server

    async def run():
        async with Client(create_server(kb, engine, row_cap=2, query_timeout=0.5)) as client:
            query = "SELECT name AS category, price AS revenue FROM products ORDER BY product_id"
            source = {
                "kind": "sql",
                "sql": query,
                "columns": COLUMNS,
                "max_rows": 100,
            }
            with patch("sqlmem.mcp_server.run_select", wraps=run_select) as guarded:
                result = await client.call_tool("create_chart", {"source": source, "spec": SPEC})
            assert not result.is_error, tool_text(result)
            assert guarded.call_args.kwargs["timeout"] == 0.5
            assert guarded.call_args.args[2] == 2
            artifact = json.loads(tool_text(result))
            assert artifact["source_truncated"] is True
            assert artifact["row_count"] == 2
            html = Path(artifact["path"]).read_text(encoding="utf-8")
            assert query not in html
            for sql in (
                "DELETE FROM products",
                "SELECT 'private-secret-value' AS no_such_column FROM missing_table",
                "SELECT email AS category, 1 AS revenue FROM customers",
            ):
                bad = await client.call_tool("create_chart", {"source": {**source, "sql": sql}, "spec": SPEC})
                assert bad.is_error
                assert "private-secret-value" not in tool_text(bad)
                assert sql not in tool_text(bad)

    asyncio.run(run())


@pytest.mark.req("REQ-CHART-03", "REQ-CHART-05")
@pytest.mark.parametrize(
    "source",
    [
        {"kind": "sql", "sql": "SELECT 1", "columns": COLUMNS},
        {"kind": "rows", "columns": COLUMNS, "rows": [], "sql": "SELECT 1", "source_truncated": False},
        {"kind": "rows", "columns": COLUMNS, "rows": []},
        {
            "kind": "rows",
            "columns": [{"name": "email", "kind": "string", "sensitivity": "non_sensitive"}],
            "rows": [],
            "source_truncated": False,
        },
        {"kind": "rows", "columns": COLUMNS, "rows": [], "source_truncated": "false"},
        {"kind": "unknown", "columns": COLUMNS},
    ],
)
def test_invalid_chart_sources_are_actionable(kb, source):
    from mcp.client.client import Client

    from sqlmem.mcp_server import create_server

    async def run():
        async with Client(create_server(kb)) as client:
            result = await client.call_tool("create_chart", {"source": source, "spec": SPEC})
            assert result.is_error
            assert tool_text(result).strip()
            assert not (kb.root / "build" / "charts").exists()

    asyncio.run(run())


@pytest.mark.req("REQ-CHART-04")
def test_vendor_hashes_and_license_inventory():
    root = Path(__file__).parents[1] / "sqlmem" / "assets" / "vendor"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "sqlmem-chart-vendor"
    assert manifest["version"] == 1
    for bundle in manifest["bundles"]:
        assert hashlib.sha256((root / bundle["file"]).read_bytes()).hexdigest() == bundle["sha256"]
        assert bundle["source"].startswith("https://raw.githubusercontent.com/")
        for notice in bundle["notices"]:
            assert (root / notice).stat().st_size > 100


@pytest.mark.req("REQ-CHART-03", "REQ-SAFE-03")
def test_chart_sql_timeout_is_actionable_and_connection_stays_usable(kb, engine):
    from mcp.client.client import Client

    from sqlmem.mcp_server import create_server

    async def run():
        async with Client(create_server(kb, engine, query_timeout=0.01)) as client:
            result = await client.call_tool(
                "create_chart",
                {
                    "source": {
                        "kind": "sql",
                        "sql": (
                            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<2000000000) "
                            "SELECT 'all' AS category, COUNT(*) AS revenue FROM n"
                        ),
                        "columns": COLUMNS,
                    },
                    "spec": SPEC,
                },
            )
            assert result.is_error
            assert "time limit" in tool_text(result)
            usable = await client.call_tool("run_sql", {"sql": "SELECT COUNT(*) FROM products"})
            assert not usable.is_error
            assert "| 6 |" in tool_text(usable)
            assert not (kb.root / "build" / "charts").exists()

    asyncio.run(run())
