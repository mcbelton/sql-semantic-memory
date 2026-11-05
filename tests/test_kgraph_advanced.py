"""Composite keys, explicit join columns (on), polymorphic references, fan-out protection and time limits."""

import asyncio
import sqlite3
import time

import pytest

from sqlmem.db import QueryTimeout, make_engine, resolve_url, run_select
from sqlmem.kb import KnowledgeBase
from sqlmem.kgraph import to_yaml_dict
from sqlmem.scan import ScanOptions, scan_database
from tests.conftest import tool_text

HEAVY = "WITH RECURSIVE c(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM c WHERE n < 1000000000) SELECT COUNT(*) FROM c"

ENTITIES = [
    {"name": "Product", "table": "products", "label": ["name"]},
    {"name": "Sale", "kind": "event", "table": "sales"},
    {"name": "Purchase", "kind": "event", "table": "purchases"},
    {"name": "Job", "kind": "event", "table": "jobs"},
    {"name": "Stock Move", "kind": "event", "table": "stock_moves"},
    {"name": "Sale Line", "kind": "event", "table": "sale_lines"},
    {"name": "Inventory", "table": "inventory", "attributes": ["qty"]},
    {"name": "Legacy Note", "table": "legacy_notes"},
]


@pytest.fixture
def shop(tmp_path):
    path = tmp_path / "moves.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE products (product_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, amount NUMERIC);
        CREATE TABLE purchases (purchase_id INTEGER PRIMARY KEY, amount NUMERIC);
        CREATE TABLE jobs (job_id INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE sale_lines (sale_id INTEGER REFERENCES sales(sale_id), line_no INTEGER,
                                 product_id INTEGER REFERENCES products(product_id), qty INTEGER,
                                 PRIMARY KEY (sale_id, line_no));
        CREATE TABLE stock_moves (move_id INTEGER PRIMARY KEY, product_id INTEGER REFERENCES products(product_id),
                                  ref_type TEXT, ref_id INTEGER, qty INTEGER);
        CREATE TABLE inventory (product_id INTEGER REFERENCES products(product_id), bin TEXT, qty INTEGER,
                                PRIMARY KEY (product_id, bin));
        CREATE TABLE legacy_notes (note_id INTEGER PRIMARY KEY, sale_no INTEGER, body TEXT);
        INSERT INTO products VALUES (1, 'Bike'), (2, 'Helmet'), (3, 'Lock');
        INSERT INTO sales VALUES (1, 10), (2, 20), (3, 30);
        INSERT INTO purchases VALUES (1, 5), (2, 6);
        INSERT INTO jobs VALUES (1, 'Assemble');
        INSERT INTO sale_lines VALUES (1, 1, 1, 1), (1, 2, 2, 1), (2, 1, 2, 2), (3, 1, 1, 1), (3, 2, 3, 1);
        INSERT INTO stock_moves VALUES
            (1, 1, 'S', 1, -1), (2, 2, 'S', 1, -1), (3, 2, 'S', 2, -2), (4, 1, 'S', 99, -1),
            (5, 1, 'P', 1, 5), (6, 2, 'P', 2, 6), (7, 3, 'J', 1, 1), (8, 3, 'X', 7, 0);
        INSERT INTO inventory VALUES (1, 'A1', 3), (1, 'B2', 1), (2, 'A1', 7), (3, 'C3', 2);
        INSERT INTO legacy_notes VALUES (1, 1, 'gift'), (2, 3, 'rush'), (3, 42, 'lost'), (4, 1, 'repeat');""")
    con.commit()
    con.close()
    engine = make_engine(resolve_url(str(path)))
    kb = KnowledgeBase(tmp_path / "kb", embedder="hash:64")
    kb.save_catalog(scan_database(engine, ScanOptions(), log=lambda _m: None))
    report = kb.import_kg({"entities": ENTITIES}, engine)
    assert report.entities == len(ENTITIES), report.text()
    return kb, engine


def _rel(kb, subject, predicate):
    return next(r for r in kb.load_kg()["relations"] if r["subject"] == subject and r["predicate"] == predicate)


def _ent(kb, name):
    return next(e for e in kb.load_kg()["entities"] if e["name"] == name)


# ---------------------------------------------------------------------------------------------- composite keys
@pytest.mark.req("REQ-KG-04")
def test_composite_keys_default_to_the_primary_key_and_measure_cardinality(shop):
    kb, engine = shop
    assert _ent(kb, "Inventory")["key"] == ["product_id", "bin"]  # composite: stored as a list
    assert _ent(kb, "Sale Line")["key"] == ["sale_id", "line_no"]
    assert _ent(kb, "Product")["key"] == "product_id"  # single column: stored as a plain name
    report = kb.import_kg(
        {
            "relations": [
                {"subject": "Product", "predicate": "stocked_as", "object": "Inventory"},
                {"subject": "Sale", "predicate": "has_line", "object": "Sale Line", "cardinality": "1:1"},
            ]
        },
        engine,
    )
    assert report.relations == 2, report.text()
    assert _rel(kb, "Product", "stocked_as")["verified"] == {"pairs": 4, "cardinality": "1:N"}
    assert _rel(kb, "Sale", "has_line")["cardinality"] == "1:N"  # corrected from the claimed 1:1
    assert any("corrected to 1:N" in w for w in report.warnings)
    summary = kb.kg_summary("Inventory")
    assert "key product_id, bin" in summary
    kb.build(log=lambda _m: None)
    assert "| product_id, bin |" in (kb.docs_path / "knowledge-graph.md").read_text(encoding="utf-8")


@pytest.mark.req("REQ-KG-04")
def test_explicit_composite_key_and_uniqueness_check(shop):
    kb, engine = shop
    report = kb.import_kg(
        {
            "entities": [
                {"name": "Bin Stock", "table": "inventory", "key": ["product_id", "bin"]},
                {"name": "Stock Level", "table": "inventory", "key": "product_id"},  # not unique per row
                {"name": "Typo Key", "table": "inventory", "key": ["product_id", "bin_code"]},
            ]
        },
        engine,
    )
    assert report.entities == 3
    text = "\n".join(report.warnings)
    assert "entity 'Stock Level': key (product_id) is not unique - 1 values occur more than once" in text
    assert (
        "entity 'Typo Key': key column(s) bin_code not in inventory - using the primary key (product_id, bin)" in text
    )
    assert _ent(kb, "Typo Key")["key"] == ["product_id", "bin"]
    assert not any("Bin Stock" in w for w in report.warnings)


@pytest.mark.req("REQ-KG-04")
def test_yaml_keeps_single_keys_compact():
    out = to_yaml_dict(
        {
            "entities": [{"name": "A", "table": "t", "key": ["id"]}, {"name": "B", "table": "t", "key": ["a", "b"]}],
            "relations": [],
        }
    )
    assert [e["key"] for e in out["entities"]] == ["id", ["a", "b"]]


# ---------------------------------------------------------------------------------------------- explicit "on"
@pytest.mark.req("REQ-KG-05")
def test_on_links_tables_without_a_declared_foreign_key(shop):
    kb, engine = shop
    missing = kb.import_kg({"relations": [{"subject": "Legacy Note", "predicate": "about", "object": "Sale"}]}, engine)
    assert "no join path between legacy_notes and sales - if a column links them" in missing.dropped[0]
    report = kb.import_kg(
        {
            "relations": [
                {
                    "subject": "Legacy Note",
                    "predicate": "about",
                    "object": "Sale",
                    "on": "sales.sale_id = legacy_notes.sale_no",
                }
            ]
        },
        engine,
    )  # either order
    assert report.relations == 1, report.text()
    rel = _rel(kb, "Legacy Note", "about")
    assert rel["on"] == "legacy_notes.sale_no = sales.sale_id"
    assert rel["join"] == "FROM legacy_notes s JOIN sales o ON s.sale_no = o.sale_id"
    assert rel["verified"] == {"pairs": 3, "cardinality": "N:1", "unmatched": 1}
    assert any("1 Legacy Note rows reference a Sale that does not exist" in w for w in report.warnings)
    bad = kb.import_kg(
        {
            "relations": [
                {
                    "subject": "Legacy Note",
                    "predicate": "x",
                    "object": "Sale",
                    "on": "legacy_notes.body = products.name",
                }
            ]
        },
        engine,
    )
    assert "must compare a column of legacy_notes with a column of sales" in bad.dropped[0]


# ---------------------------------------------------------------------------------------------- polymorphic
POLY = {
    "relations": [
        {
            "subject": "Stock Move",
            "predicate": "for_order",
            "description": "Order behind the stock movement.",
            "polymorphic": {
                "column": "ref_id",
                "type_column": "ref_type",
                "targets": [
                    {"type": "S", "object": "Sale", "predicate": "for_sale"},
                    {"type": "P", "object": "Purchase"},
                    {"type": ["J", "Z"], "object": "Job", "predicate": "for_job"},
                ],
            },
        }
    ]
}


@pytest.mark.req("REQ-KG-06")
def test_polymorphic_reference_becomes_one_verified_relation_per_target(shop):
    kb, engine = shop
    report = kb.import_kg(POLY, engine)
    assert (report.relations, report.dropped) == (3, []), report.text()
    warnings = "\n".join(report.warnings)
    assert "ref_type value 'Z' does not occur in the data" in warnings
    assert "ref_type values without a target: 'X' (1 rows)" in warnings
    assert "1 Stock Move rows reference a Sale that does not exist" in warnings
    sale = _rel(kb, "Stock Move", "for_sale")
    assert sale["join"] == "FROM stock_moves s JOIN sales o ON s.ref_id = o.sale_id WHERE s.ref_type = 'S'"
    assert sale["verified"] == {"pairs": 3, "cardinality": "N:1", "unmatched": 1}
    assert sale["polymorphic"] == {"column": "ref_id", "type_column": "ref_type", "type": "S"}
    purchase = _rel(kb, "Stock Move", "for_order")  # no target predicate: the relation's own predicate
    assert purchase["object"] == "Purchase"
    assert purchase["verified"]["pairs"] == 2
    job = _rel(kb, "Stock Move", "for_job")
    assert job["condition"] == "stock_moves.ref_type IN ('J', 'Z')"
    assert job["verified"]["pairs"] == 1
    for r in kb.load_kg()["relations"]:  # every stored join runs and agrees with its verified count
        assert run_select(engine, f"SELECT COUNT(*) {r['join']}")[1][0][0] == r["verified"]["pairs"]


@pytest.mark.req("REQ-KG-06", "REQ-RET-04")
def test_polymorphic_links_reload_and_feed_join_planning(shop):
    kb, engine = shop
    kb.import_kg(POLY, engine)
    kb.build(log=lambda _m: None)
    model = kb.model()
    assert {(r["subject"], r["predicate"]): r["join"] for r in model.kg["relations"]} == {
        (r["subject"], r["predicate"]): r["join"] for r in kb.load_kg()["relations"]
    }  # same after reload
    links = [r for r in model.relationships if r.source == "kg"]
    assert {(r.from_table, r.to_table) for r in links} == {
        ("stock_moves", "sales"),
        ("stock_moves", "purchases"),
        ("stock_moves", "jobs"),
    }
    path = model.join_path("stock_moves", "sales")
    assert len(path) == 1
    assert path[0].condition == "stock_moves.ref_type = 'S'"
    ctx = kb.context("which sales did stock moves belong to")
    assert "Stock Move --for_sale--> Sale (N:1, 3 pairs, 1 unmatched)" in ctx
    assert "stock_moves.ref_id = sales.sale_id AND (stock_moves.ref_type = 'S')  [kg;" in ctx


@pytest.mark.req("REQ-KG-06")
def test_polymorphic_errors_are_actionable(shop):
    kb, engine = shop
    report = kb.import_kg(
        {
            "relations": [
                {
                    "subject": "Stock Move",
                    "predicate": "a",
                    "polymorphic": {"column": "ref_no", "type_column": "ref_type", "targets": {"S": "Sale"}},
                },
                {
                    "subject": "Stock Move",
                    "predicate": "b",
                    "polymorphic": {"column": "ref_id", "type_column": "kind", "targets": {"S": "Sale"}},
                },
                {
                    "subject": "Stock Move",
                    "predicate": "c",
                    "polymorphic": {"column": "ref_id", "type_column": "ref_type", "targets": {"S": "Sale Line"}},
                },
            ]
        },
        engine,
    )
    dropped = "\n".join(report.dropped)
    assert "column(s) ref_no not in stock_moves" in dropped
    assert "type_column kind not in stock_moves" in dropped
    assert "Sale Line is identified by sale_id, line_no, which does not match the reference column(s) ref_id" in dropped


# ---------------------------------------------------------------------------------------------- fan-out protection
@pytest.mark.req("REQ-KG-07")
def test_auto_planned_joins_through_a_shared_table_are_rejected(shop):
    kb, engine = shop
    started = time.monotonic()
    report = kb.import_kg({"relations": [{"subject": "Stock Move", "predicate": "for_sale", "object": "Sale"}]}, engine)
    assert time.monotonic() - started < 5
    assert report.relations == 0
    msg = report.dropped[0]
    assert "only connected through products (stock_moves -> products -> sale_lines -> sales)" in msg
    assert "give the join with on" in msg
    assert "use polymorphic" in msg
    explicit = kb.import_kg(
        {
            "relations": [
                {
                    "subject": "Stock Move",
                    "predicate": "same_product_as",
                    "object": "Sale",
                    "via": ["products", "sale_lines"],
                }
            ]
        },
        engine,
    )
    assert explicit.relations == 1  # spelled out on purpose: accepted, with a warning
    assert any("passes through products from both sides" in w for w in explicit.warnings)


@pytest.mark.req("REQ-KG-07")
def test_ambiguous_direct_links_are_reported(tmp_path):
    path = tmp_path / "addr.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE addresses (address_id INTEGER PRIMARY KEY, city TEXT);
        CREATE TABLE orders (order_id INTEGER PRIMARY KEY, bill_to INTEGER REFERENCES addresses(address_id),
                             ship_to INTEGER REFERENCES addresses(address_id));
        INSERT INTO addresses VALUES (1, 'Oslo'), (2, 'Rome');
        INSERT INTO orders VALUES (1, 1, 2), (2, 2, 2);""")
    con.commit()
    con.close()
    engine = make_engine(resolve_url(str(path)))
    kb = KnowledgeBase(tmp_path / "kb", embedder="hash:64")
    kb.save_catalog(scan_database(engine, ScanOptions(), log=lambda _m: None))
    report = kb.import_kg(
        {
            "entities": [{"name": "Order", "table": "orders"}, {"name": "Address", "table": "addresses"}],
            "relations": [
                {"subject": "Order", "predicate": "ships_to", "object": "Address"},
                {"subject": "Order", "predicate": "billed_to", "object": "Address", "via": ["orders.bill_to"]},
            ],
        },
        engine,
    )
    assert report.relations == 2
    assert any(
        "ships_to Address': orders and addresses are linked by several columns (bill_to, ship_to)" in w
        for w in report.warnings
    )
    assert not any("billed_to" in w for w in report.warnings)
    assert _rel(kb, "Order", "billed_to")["join"] == "FROM orders s JOIN addresses o ON s.bill_to = o.address_id"


# ---------------------------------------------------------------------------------------------- time limits
@pytest.mark.req("REQ-SAFE-03")
def test_run_select_time_limit_keeps_the_connection_usable(shop):
    _, engine = shop
    started = time.monotonic()
    with pytest.raises(QueryTimeout, match=r"did not finish within 0\.5s"):
        run_select(engine, HEAVY, timeout=0.5)
    assert time.monotonic() - started < 5
    assert run_select(engine, "SELECT 41 + 1", timeout=0.5)[1] == [(42,)]


@pytest.mark.req("REQ-KG-08")
def test_verification_budget_saves_items_unverified(shop):
    kb, engine = shop
    report = kb.import_kg(POLY, engine, budget=1e-9)
    assert report.relations == 3
    assert report.unverified == 3
    assert "3 item(s) were accepted without data checks" in report.text()
    assert all("verified" not in r for r in kb.load_kg()["relations"])
    later = kb.check_kg(engine)  # verified later without a budget
    assert later.unverified == 0
    assert all(r.get("verified") for r in kb.load_kg()["relations"])


@pytest.mark.req("REQ-KG-08")
def test_slow_join_is_saved_unverified_not_dropped(shop, monkeypatch):
    import sqlmem.kgraph as kgraph

    kb, engine = shop
    real = run_select

    def slow(eng, sql, *args, **kwargs):
        if "JOIN purchases" in sql:
            raise QueryTimeout("the query did not finish within 30s")
        return real(eng, sql, *args, **kwargs)

    monkeypatch.setattr(kgraph, "run_select", slow)
    report = kb.import_kg(POLY, engine)
    assert report.relations == 3
    assert report.unverified == 1
    assert report.dropped == []
    assert any("for_order Purchase': not verified: the query did not finish within 30s" in w for w in report.warnings)
    assert "verified" not in _rel(kb, "Stock Move", "for_order")


@pytest.mark.req("REQ-SAFE-03", "REQ-MCP-01")
def test_mcp_tools_are_time_limited(shop):
    from mcp.client.client import Client

    from sqlmem.mcp_server import create_server

    kb, engine = shop

    async def run():
        async with Client(create_server(kb, engine, query_timeout=0.5, save_budget=30)) as c:
            started = time.monotonic()
            slow = await c.call_tool("run_sql", {"sql": HEAVY})
            assert slow.is_error
            assert "did not finish within 0.5s" in tool_text(slow)
            assert time.monotonic() - started < 10
            saved = await c.call_tool("save_knowledge_graph", {"relations": POLY["relations"]})
            text = tool_text(saved)
            assert not saved.is_error, text
            assert text.startswith("Accepted 0 entities and 3 relations"), text
            graph = tool_text(await c.call_tool("get_knowledge_graph", {"entity": "Stock Move"}))
            assert "Stock Move --for_sale--> Sale (N:1, 3 pairs, 1 unmatched)" in graph

    asyncio.run(run())
