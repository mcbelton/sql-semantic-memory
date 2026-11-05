import asyncio
import json
import re
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from sqlmem.cli import main
from sqlmem.db import check_readonly, run_select
from sqlmem.enrich import draft_semantic, suggest_with_llm
from sqlmem.kb import KnowledgeBase
from sqlmem.model import SemanticModel
from sqlmem.render import select_tables
from tests.conftest import SEMANTIC, tool_text


def _obj(catalog, name):
    return next(o for o in catalog["objects"] if o["fqn"] == name)


def _col(obj, name):
    return next(c for c in obj["columns"] if c["name"] == name)


# ---------------------------------------------------------------------------------------------- scan
@pytest.mark.req("REQ-SCAN-01")
def test_scan_catalog_schema_and_profile(catalog):
    assert {o["fqn"] for o in catalog["objects"]} == {
        "customers",
        "products",
        "sales_reps",
        "orders",
        "order_items",
        "v_order_totals",
    }
    assert catalog["errors"] == []
    orders = _obj(catalog, "orders")
    assert orders["row_count"] == 60
    assert orders["row_count_exact"]
    assert orders["primary_key"] == ["order_id"]
    assert orders["foreign_keys"] == [
        {"name": None, "columns": ["customer_id"], "ref_table": "customers", "ref_columns": ["id"]}
    ]
    status = _col(orders, "status")["profile"]
    assert sorted(v for v, _ in status["values"]) == [1, 2, 3]
    assert _col(orders, "order_date")["profile"]["min"].startswith("2024-")
    view = _obj(catalog, "v_order_totals")
    assert view["type"] == "view"
    assert "SUM" in view["definition"]


@pytest.mark.req("REQ-SCAN-02")
def test_scan_never_captures_sensitive_values(catalog):
    email = _col(_obj(catalog, "customers"), "email")
    assert email["sensitive"]
    assert "values" not in email["profile"]
    assert "examples" not in email["profile"]
    assert "min" not in email["profile"]
    assert _col(_obj(catalog, "sales_reps"), "full_name")["sensitive"]
    assert not _col(_obj(catalog, "customers"), "country")["sensitive"]


@pytest.mark.req("REQ-SCAN-03")
def test_scan_respects_include_exclude(engine):
    from sqlmem.scan import ScanOptions, scan_database

    cat = scan_database(engine, ScanOptions(exclude=["order*", "v_*"], profile=False), log=lambda _m: None)
    assert {o["fqn"] for o in cat["objects"]} == {"customers", "products", "sales_reps"}


# ---------------------------------------------------------------------------------------------- model
@pytest.mark.req("REQ-SEM-02", "REQ-RET-04")
def test_model_infers_undeclared_joins_and_housekeeping(catalog):
    m = SemanticModel(catalog, {})
    inferred = {(r.from_table, r.from_columns[0], r.to_table) for r in m.relationships if r.source == "inferred"}
    assert ("order_items", "product_id", "products") in inferred
    assert ("orders", "sales_rep_id", "sales_reps") in inferred
    hk = {c.name for t in m.tables.values() for c in t.columns.values() if c.housekeeping}
    assert hk == {"row_guid", "created_at"}
    path = m.join_path("order_items", "customers")
    assert path is not None
    assert [(r.from_table, r.to_table) for r in path] == [("order_items", "orders"), ("orders", "customers")]


@pytest.mark.req("REQ-SEM-01")
def test_model_overlay_merge_and_warnings(catalog):
    from tests.conftest import SEMANTIC

    m = SemanticModel(catalog, SEMANTIC)
    assert m.tables["orders"].description.startswith("Customer orders")
    assert m.tables["orders"].columns["status"].values == {"1": "Open", "2": "Shipped", "3": "Cancelled"}
    assert m.tables["customers"].description.startswith("People")
    assert any("no_such_table" in w for w in m.warnings)
    assert set(m.examples[0]["tables"]) == {"order_items", "orders", "customers"}
    assert m.resolve("ORDERS") is m.tables["orders"]
    assert m.resolve("nope") is None


@pytest.mark.req("REQ-RET-02")
def test_value_linking(catalog):
    m = SemanticModel(catalog, {})
    found = {(t, c, v) for _p, t, c, v in m.match_values("helmet sales in Germany")}
    assert ("products", "category", "Helmets") in found
    assert ("customers", "country", "Germany") in found
    assert m.match_values("orders by product name") == []  # schema words are not value evidence


# ---------------------------------------------------------------------------------------------- build/search
@pytest.mark.req("REQ-SEM-04")
def test_build_writes_docs_graph_and_index(kb):
    assert (kb.docs_path / "README.md").exists()
    assert (kb.docs_path / "tables" / "orders.md").read_text(encoding="utf-8").startswith("# orders")
    graph = json.loads((kb.root / "graph.json").read_text(encoding="utf-8"))
    assert any(e["type"] == "references" and e["via"] == "inferred" for e in graph["edges"])
    counts = kb.index().count()
    assert counts["table"] == 6
    assert counts["example"] == 1
    assert counts["metric"] == 1
    assert "row_guid" not in json.dumps([h.title for h in kb.search("row guid created", k=50)])


@pytest.mark.req("REQ-RET-01")
def test_hybrid_search_uses_lexical_and_vectors(kb):
    hits = kb.search("which sales rep handled the order", k=5)
    assert hits
    assert any(h.lexical_rank for h in hits)
    assert any(h.vector_rank for h in hits)
    assert "sales_reps" in {t for h in hits for t in h.tables}


@pytest.mark.req("REQ-RET-03")
def test_context_pack_contains_tables_values_joins_and_rules(kb):
    ctx = kb.context("helmet revenue by country")
    assert "\"helmet\" -> products.category = 'Helmets'" in ctx
    assert "### order_items" in ctx
    assert "### products" in ctx
    assert "order_items.product_id = products.product_id" in ctx
    assert "Dates are ISO TEXT" in ctx
    assert "codes: 1=Open" in kb.context("open orders by status")


@pytest.mark.req("REQ-RET-03")
def test_value_matches_add_tables_without_displacing_retrieved_ones(kb):
    question = "helmet revenue by country"  # 'country' ranks customers first, the literal 'helmet' is in products
    hits = kb.index().search(question, k=40, rrf_k=10)
    ranked, values, chosen = select_tables(kb.model(), question, hits, max_tables=1)
    assert ("helmet", "products") in [(phrase, table) for phrase, table, _c, _v in values]
    assert ranked[0][1] != "products"
    assert chosen == [ranked[0][1], "products"]


@pytest.mark.req("REQ-RET-04")
def test_join_path_and_describe(kb):
    assert "orders.customer_id = customers.id" in kb.join_path("order_items", "customers")
    assert "Order status." in kb.describe("orders")
    with pytest.raises(ValueError, match="Did you mean"):
        kb.describe("orderz")


# ---------------------------------------------------------------------------------------------- memory
@pytest.mark.req("REQ-MEM-01")
def test_memory_roundtrip_is_persistent_and_searchable(kb):
    sql = "SELECT c.segment, COUNT(*) FROM orders o JOIN customers c ON c.id = o.customer_id GROUP BY 1"
    res = kb.remember("Orders per customer segment", kind="query", question="How many orders per segment?", sql=sql)
    assert res["created"]
    assert set(res["memory"]["tables"]) == {"orders", "customers"}
    assert not kb.remember(
        "Orders per customer segment", kind="query", question="How many orders per segment?", sql=sql
    )["created"]
    mid = res["memory"]["id"]
    fresh = KnowledgeBase(kb.root)  # new process view: reloads from disk
    assert any(h.kind == "memory" for h in fresh.search("orders per segment", k=5))
    assert "Orders per customer segment" in fresh.context("number of orders by segment")
    kb.build(log=lambda _m: None)  # memories survive a full rebuild
    assert kb.index().count().get("memory") == 1
    assert kb.forget(mid)
    assert not kb.forget(mid)
    assert kb.index().count().get("memory") is None
    assert kb.memories.load() == []


@pytest.mark.req("REQ-MEM-02")
def test_memory_validation(kb):
    with pytest.raises(ValueError, match="kind must be one of"):
        kb.remember("x", kind="bogus")
    with pytest.raises(ValueError, match="requires the verified SQL"):
        kb.remember("needs sql", kind="query")
    with pytest.raises(ValueError, match="Unknown table"):
        kb.remember("fact", tables=["nope"])


# ---------------------------------------------------------------------------------------------- safety
@pytest.mark.req("REQ-SAFE-01")
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "with x as (select 1) select * from x",
        "SELECT 'drop table x; delete' AS s",
        "SELECT REPLACE(name, 'a', 'b') FROM customers",
        "select 1;",
        "SELECT 'O''Brien' AS n",
        'SELECT "set", [use], `lock` FROM t',
        "(SELECT 1) UNION (SELECT 2)",
        "SELECT 'C:\\\\Temp\\\\' AS p",
        "SELECT name FROM products WHERE name LIKE '%Lock%'",
    ],
)
def test_readonly_guard_allows(sql):
    check_readonly(sql)


ONLY_SELECT = "Only SELECT / WITH queries are allowed"
NO_COMMENTS = "SQL comments are not allowed"
NO_BACKSLASH = "Backslash-escaped quotes are not allowed"


@pytest.mark.req("REQ-SAFE-01")
@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("DELETE FROM orders", ONLY_SELECT),
        ("SELECT 1; DROP TABLE orders", "Only a single statement is allowed"),
        ("SELECT * INTO x FROM orders", "Keyword not allowed in read-only mode: INTO"),
        ("PRAGMA table_info(x)", ONLY_SELECT),
        ("WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d", "Keyword not allowed in read-only mode: DELETE"),
        ("/* hi */ UPDATE orders SET status = 1", NO_COMMENTS),
        ("EXEC sp_who", ONLY_SELECT),
        ("", "Empty SQL"),
        ("ATTACH DATABASE 'x' AS y", ONLY_SELECT),
        ("SELECT REPLACE(name, 'a', 'b') FROM customers -- delete", NO_COMMENTS),  # comments are rejected outright
        ("SELECT 1 /*! INTO OUTFILE '/tmp/x' */", NO_COMMENTS),  # MySQL executable comment
        ("SELECT 'a\\'' INTO OUTFILE '/tmp/x' -- '", NO_BACKSLASH),  # MySQL escape hiding INTO from naive parsers
        ("SELECT E'a\\'' AS x INTO t FROM y", NO_BACKSLASH),  # PostgreSQL E-string variant
        ("SELECT $$it's$$ AS a INTO t FROM y WHERE 'x' = 'x'", "Dollar-quoted strings are not allowed"),
        ("SELECT q'[it's]' AS a, 1 INTO t FROM dual", "Oracle q'...' quoting is not allowed"),
        ("SELECT 1 # it's\n INTO OUTFILE '/tmp/x'", NO_COMMENTS),  # MySQL hash comment
        ("SELECT set_config('default_transaction_read_only', 'off', false)", "read-only mode: SET_CONFIG"),
        ("SELECT pg_read_file('/etc/passwd')", "read-only mode: PG_READ_FILE"),
        ("SELECT * FROM read_csv('C:/secret.csv')", "read-only mode: READ_CSV"),
        ("SELECT * FROM 'C:/secret.csv'", "Reading files through string literals"),
        ("SELECT 'unterminated", "Unterminated quoted string"),
    ],
)
def test_readonly_guard_blocks(sql, reason):
    with pytest.raises(ValueError, match=re.escape(reason)):
        check_readonly(sql)


@pytest.mark.req("REQ-SAFE-01")
def test_readonly_guard_is_dialect_aware():
    check_readonly("SELECT data #>> '{a,b}' FROM t", "postgresql")  # JSON operator, not a comment
    check_readonly("SELECT arr[1] FROM t", "postgresql")
    with pytest.raises(ValueError, match=NO_COMMENTS):
        check_readonly("SELECT 1 # comment", "mysql")
    with pytest.raises(ValueError, match="SET_CONFIG"):  # in PostgreSQL [ ] is array syntax: its contents are code
        check_readonly("SELECT ARRAY[set_config('a', 'b', false)]", "postgresql")


@pytest.mark.req("REQ-SAFE-02")
def test_run_select_is_read_only_and_capped(engine):
    cols, rows, truncated = run_select(engine, "SELECT order_id FROM orders ORDER BY order_id", max_rows=5)
    assert cols == ["order_id"]
    assert [r[0] for r in rows] == [1, 2, 3, 4, 5]
    assert truncated
    # the SQLite file itself is opened with mode=ro, so even unguarded SQL cannot write
    with engine.connect() as conn, pytest.raises(OperationalError, match="readonly database"):
        conn.exec_driver_sql("DELETE FROM orders")


# ---------------------------------------------------------------------------------------------- draft / LLM
class FakeLLM:
    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        assert kw["response_format"] == {"type": "json_object"}
        user = kw["messages"][1]["content"]
        table = user.split("Table: ")[1].split(" ")[0]
        content = json.dumps(
            {
                "description": f"LLM: {table}",
                "synonyms": ["thing"],
                "columns": {"segment": "Customer segment (Retail or Wholesale)"},
            }
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.req("REQ-SEM-03")
def test_draft_preserves_curated_and_fills_gaps(kb):
    from sqlmem.llm import LLM

    model = kb.model()
    llm = FakeLLM()
    sugg = suggest_with_llm(
        model, [model.tables["customers"], model.tables["products"]], LLM("openai:gpt", client=llm), workers=2
    )
    assert llm.calls == 2
    draft = draft_semantic(model, kb.load_semantic(), sugg)
    assert draft["tables"]["customers"]["description"].startswith("People")  # curated wins
    assert draft["tables"]["customers"]["columns"]["segment"] == "Customer segment (Retail or Wholesale)"
    assert draft["tables"]["customers"]["source"] == "llm-draft"
    assert draft["tables"]["products"]["description"] == "LLM: products"
    assert draft["tables"]["orders"]["columns"]["status"]["values"] == {1: "Open", 2: "Shipped", 3: "Cancelled"}
    assert "source" not in draft["tables"]["orders"]
    assert set(draft["tables"]["sales_reps"]["columns"]) == {
        "sales_rep_id",
        "full_name",
        "region",
        "row_guid",
        "created_at",
    }


# ---------------------------------------------------------------------------------------------- MCP + CLI
@pytest.mark.req("REQ-MCP-01")
def test_mcp_server_tools(kb, engine):
    from mcp.client.client import Client

    from sqlmem.mcp_server import create_server

    srv = create_server(kb, engine)

    async def run():
        async with Client(srv) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            assert {
                "get_sql_context",
                "search_knowledge",
                "describe_table",
                "list_tables",
                "find_join_path",
                "remember",
                "forget",
                "list_memories",
                "run_sql",
            } <= names
            ctx = await c.call_tool("get_sql_context", {"question": "helmet revenue by country"})
            assert not ctx.is_error
            assert "products.category = 'Helmets'" in tool_text(ctx)
            rows = await c.call_tool("run_sql", {"sql": "SELECT COUNT(*) AS n FROM orders"})
            assert "| 60 |" in tool_text(rows)
            bad = await c.call_tool("run_sql", {"sql": "DELETE FROM orders"})
            assert bad.is_error
            assert "Only SELECT" in tool_text(bad)
            typo = await c.call_tool("run_sql", {"sql": "SELECT no_such_col FROM orders"})
            assert typo.is_error
            assert "no such column" in tool_text(typo)
            unknown = await c.call_tool("describe_table", {"table": "orderz"})
            assert unknown.is_error
            assert "Did you mean" in tool_text(unknown)
            saved = await c.call_tool(
                "remember",
                {"text": "Revenue excludes cancelled orders (status 3)", "kind": "rule", "tables": ["orders"]},
            )
            assert tool_text(saved).startswith("Saved")
            mems = await c.call_tool("list_memories", {})
            assert "Revenue excludes cancelled orders" in tool_text(mems)

    asyncio.run(run())


@pytest.mark.req("REQ-CLI-01")
def test_cli_end_to_end(tmp_path, db_path, capsys):
    kbdir = str(tmp_path / "clikb")
    main(["scan", "--kb", kbdir, "--db", str(db_path), "--embedder", "hash:128"])
    main(["context", "--kb", kbdir, "orders per sales rep"])
    out = capsys.readouterr().out
    assert "### orders" in out
    assert "### sales_reps" in out
    main(["query", "--kb", kbdir, "--db", str(db_path), "SELECT COUNT(*) AS n FROM customers"])
    assert "| 20 |" in capsys.readouterr().out
    main(["draft", "--kb", kbdir])
    assert (tmp_path / "clikb" / "semantic.draft.yaml").exists()
    with pytest.raises(SystemExit):
        main(["query", "--kb", kbdir, "--db", str(db_path), "DROP TABLE customers"])


@pytest.mark.req("REQ-CLI-01", "REQ-MEM-01")
def test_cli_explore_memory_validate_and_stats_commands(tmp_path, db_path, capsys):
    import yaml

    kbdir, root = str(tmp_path / "clikb"), tmp_path / "clikb"
    broken = {"question": "Broken example", "sql": "SELECT no_such_column FROM customers"}
    semantic = {**SEMANTIC, "examples": [*SEMANTIC["examples"], broken]}
    main(["scan", "--kb", kbdir, "--db", str(db_path), "--embedder", "hash:128", "--no-build"])
    (root / "semantic.yaml").write_text(yaml.safe_dump(semantic, sort_keys=False), encoding="utf-8")
    main(["build", "--kb", kbdir, "--embedder", "hash:128"])
    capsys.readouterr()

    main(["search", "--kb", kbdir, "helmet revenue", "-k", "3", "-v"])
    assert "(lex=" in capsys.readouterr().out
    main(["search", "--kb", kbdir, "anything", "--kind", "routine"])  # SQLite has no routines
    assert capsys.readouterr().out.strip() == "No matches."
    main(["table", "--kb", kbdir, "orders"])
    assert "Order status." in capsys.readouterr().out
    main(["table", "--kb", kbdir, "orders", "--compact"])
    assert "orders" in capsys.readouterr().out
    main(["path", "--kb", kbdir, "order_items", "customers"])
    assert "orders.customer_id = customers.id" in capsys.readouterr().out
    main(["tables", "--kb", kbdir, "--contains", "order"])
    listed = capsys.readouterr().out
    assert "order_items" in listed
    assert "sales_reps" not in listed

    main(["remember", "--kb", kbdir, "Revenue excludes cancelled orders", "--kind", "rule", "--table", "orders"])
    saved = re.search(r"^Saved: (\S+) \[rule\] tables=\['orders'\]", capsys.readouterr().out, re.M)
    assert saved, "remember prints the new memory id"
    main(["memories", "--kb", kbdir])
    assert f"{saved.group(1)} [rule] Revenue excludes cancelled orders" in capsys.readouterr().out
    main(["memories", "--kb", kbdir, "--kind", "query"])
    assert capsys.readouterr().out.strip() == "No memories."
    main(["forget", "--kb", kbdir, saved.group(1)])
    assert capsys.readouterr().out.strip() == "Deleted."
    with pytest.raises(SystemExit) as gone:
        main(["forget", "--kb", kbdir, saved.group(1)])
    assert gone.value.code == 1

    with pytest.raises(SystemExit) as failed:  # one example query is broken on purpose
        main(["validate", "--kb", kbdir, "--db", str(db_path)])
    assert failed.value.code == 1
    report = capsys.readouterr().out
    assert "OK    Revenue by country" in report
    assert "FAIL  Broken example" in report
    assert "1/2 example queries OK" in report

    main(["stats", "--kb", kbdir])
    stats = json.loads(capsys.readouterr().out)
    assert (stats["examples"], stats["memories"], stats["embedder"]) == (2, 0, "hash:128")
    assert stats["relationships"]["declared"] >= 2

    main(["draft", "--kb", kbdir, "--in-place"])  # keeps a backup of the curated file
    assert list(root.glob("semantic.*.bak.yaml"))
    assert "Broken example" in (root / "semantic.yaml").read_text(encoding="utf-8")
