"""Knowledge graph: generation with an LLM, validation against schema + data, merge, build, MCP and CLI."""

import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest
import yaml

from sqlmem.cli import main
from sqlmem.db import make_engine, resolve_url, run_select
from sqlmem.kb import KnowledgeBase
from sqlmem.kgraph import build_tasks, task_prompt
from sqlmem.llm import LLM
from sqlmem.scan import ScanOptions, scan_database
from tests.conftest import tool_text

GRAPH = {
    "entities": [
        {
            "name": "Customer",
            "kind": "core",
            "description": "People and companies who buy from the shop.",
            "synonyms": ["client", "buyer"],
            "table": "customers",
            "key": "id",
            "label": ["name"],
            "attributes": ["country", "segment", "no_such_col"],
        },
        {
            "name": "Wholesale Customer",
            "kind": "role",
            "description": "Customers buying wholesale.",
            "table": "customers",
            "filter": "segment = 'Wholesale'",
            "is_a": "Customer",
        },
        {
            "name": "Product",
            "kind": "core",
            "table": "products",
            "key": "product_id",
            "label": ["name"],
            "attributes": ["category", "price"],
        },
        {
            "name": "Order",
            "kind": "event",
            "description": "A customer order.",
            "table": "orders",
            "key": "order_id",
            "attributes": ["order_date", "status"],
        },
        {"name": "Sales Rep", "kind": "core", "table": "sales_reps", "label": ["full_name"]},
        {"name": "Invoice", "kind": "event", "table": "invoices"},
        {"name": "Bad Filter", "table": "customers", "filter": "segment = 'Retail'; DROP TABLE customers"},
    ],
    "relations": [
        {
            "subject": "Customer",
            "predicate": "places",
            "object": "Order",
            "cardinality": "1:1",
            "via": [],
            "description": "Customers place orders.",
        },
        {
            "subject": "Order",
            "predicate": "contains",
            "object": "Product",
            "cardinality": "many-to-many",
            "via": ["order_items"],
        },
        {"subject": "sales_reps", "predicate": "Handles", "object": "Order", "cardinality": "1:N"},
        {"subject": "Wholesale Customer", "predicate": "places", "object": "Order", "cardinality": "1:N"},
        {"subject": "Customer", "predicate": "pays", "object": "Invoice"},
    ],
}


class ScriptedClient:
    """Stands in for an OpenAI client: replies with GRAPH and records the prompts it was sent."""

    def __init__(self, reply=GRAPH):
        self.calls = []
        self.reply = reply
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        content = json.dumps(self.reply)
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))]
        )


def _count(engine, sql):
    return run_select(engine, sql)[1][0][0]


def _rel(kb, subject, predicate):
    return next(r for r in kb.load_kg()["relations"] if r["subject"] == subject and r["predicate"] == predicate)


@pytest.fixture
def generated(kb, engine):
    client = ScriptedClient()
    report = kb.generate_kg(LLM("openai:scripted", client=client), engine=engine, log=lambda _m: None)
    return kb, report, client


@pytest.mark.req("REQ-KG-01")
def test_generate_validates_against_schema_and_data(generated, engine):
    kb, report, client = generated
    assert len(client.calls) == 1
    prompt = client.calls[0]["messages"][1]["content"]
    assert "### orders" in prompt
    assert "segment" in prompt
    assert "Bike shop sales." in prompt
    assert "business knowledge graph" in client.calls[0]["messages"][0]["content"]

    assert (report.entities, report.relations) == (5, 4)
    assert report.verified
    dropped = "\n".join(report.dropped)
    assert "entity 'Invoice': unknown table 'invoices'" in dropped
    assert "entity 'Bad Filter': filter rejected" in dropped
    assert "relation 'Customer pays Invoice': unknown entity 'Invoice'" in dropped
    warnings = "\n".join(report.warnings)
    assert "no_such_col" in warnings
    assert "cardinality 1:1 corrected to 1:N" in warnings

    saved = kb.load_kg()
    ents = {e["name"]: e for e in saved["entities"]}
    assert ents["Customer"]["attributes"] == ["country", "segment"]
    assert (
        ents["Wholesale Customer"]["rows"]
        == _count(engine, "SELECT COUNT(*) FROM customers WHERE segment = 'Wholesale'")
        == 10
    )
    assert ents["Wholesale Customer"]["is_a"] == "Customer"
    assert ents["Wholesale Customer"]["key"] == "id"
    assert saved["generated"][0]["by"] == "openai:scripted"
    assert saved["generated"][0]["verified"] is True

    places = _rel(kb, "Customer", "places")
    assert places["cardinality"] == "1:N"
    assert places["verified"]["pairs"] == 60
    assert places["join"] == "FROM customers s JOIN orders o ON o.customer_id = s.id"
    contains = _rel(kb, "Order", "contains")
    assert contains["via"] == ["order_items"]
    assert contains["cardinality"] == "M:N"
    assert contains["join"] == (
        "FROM orders s JOIN order_items v1 ON v1.order_id = s.order_id JOIN products o ON v1.product_id = o.product_id"
    )
    assert contains["verified"]["pairs"] == _count(engine, "SELECT COUNT(*) FROM order_items")
    handles = _rel(kb, "Sales Rep", "handles")  # endpoint given as a table name, predicate normalized
    assert handles["verified"]["pairs"] == _count(engine, "SELECT COUNT(*) FROM orders WHERE sales_rep_id IS NOT NULL")
    wholesale = _rel(kb, "Wholesale Customer", "places")
    assert wholesale["join"].startswith("FROM (SELECT * FROM customers WHERE segment = 'Wholesale') s JOIN orders o")
    assert wholesale["verified"]["pairs"] == _count(
        engine, "SELECT COUNT(*) FROM orders o JOIN customers c ON c.id = o.customer_id WHERE c.segment = 'Wholesale'"
    )
    for r in saved["relations"]:  # every stored join actually runs
        assert _count(engine, f"SELECT COUNT(*) {r['join']}") == r["verified"]["pairs"]


@pytest.mark.req("REQ-KG-09", "REQ-SEM-04")
def test_build_uses_the_graph_everywhere(generated):
    kb, _, _ = generated
    stats = kb.build(log=lambda _m: None)
    assert (stats["entities"], stats["relations"]) == (5, 4)
    assert kb.index().count()["entity"] == 5
    assert kb.index().count()["relation"] == 4
    graph = json.loads((kb.root / "graph.json").read_text(encoding="utf-8"))
    assert {"id": "entity:Customer", "type": "entity"}.items() <= next(
        n for n in graph["nodes"] if n["id"] == "entity:Customer"
    ).items()
    assert any(e["type"] == "relation" and e["predicate"] == "contains" for e in graph["edges"])
    assert any(e["type"] == "is_a" and e["source"] == "entity:Wholesale Customer" for e in graph["edges"])
    ctx = kb.context("orders placed by wholesale customers")
    assert "## Business concepts (knowledge graph)" in ctx
    assert "**Wholesale Customer** (role, is a Customer, 10 rows) = `customers WHERE segment = 'Wholesale'`" in ctx
    assert "Wholesale Customer --places--> Order" in ctx
    md = (kb.docs_path / "knowledge-graph.md").read_text(encoding="utf-8")
    assert "```mermaid" in md
    assert "-->|places 1:N|" in md
    assert "-.->|is a|" in md
    page = (kb.docs_path / "knowledge-graph.html").read_text(encoding="utf-8")
    assert "vis-network" in page
    assert '"name": "Wholesale Customer"' in page
    assert "__DATA__" not in page
    assert "knowledge-graph.html" in (kb.docs_path / "README.md").read_text(encoding="utf-8")
    assert "Customer" in kb.kg_summary()
    assert "Order --contains--> Product" in kb.kg_summary("order")


@pytest.mark.req("REQ-KG-02")
def test_merge_keeps_existing_unless_replace(generated, engine):
    kb, _, _ = generated
    buys = kb.import_kg({"relations": [{"subject": "Customer", "predicate": "buys", "object": "Product"}]}, engine)
    assert buys.relations == 1, buys.text()  # no via given: the planner inserts orders + order_items
    saved = _rel(kb, "Customer", "buys")
    assert saved["via"] == ["orders", "order_items"]
    assert saved["join"] == (
        "FROM customers s JOIN orders v1 ON v1.customer_id = s.id JOIN order_items v2 "
        "ON v2.order_id = v1.order_id JOIN products o ON v2.product_id = o.product_id"
    )
    assert {r["join"] for r in kb.model().kg["relations"]} == {r["join"] for r in kb.load_kg()["relations"]}
    change = {"entities": [{"name": "customer", "table": "customers", "description": "CHANGED"}]}
    report = kb.import_kg(change, engine)
    assert report.unchanged == 1
    assert report.entities == 0
    assert next(e for e in kb.load_kg()["entities"] if e["name"] == "Customer")["description"].startswith("People")
    report = kb.import_kg(change, engine, replace=True)
    assert report.entities == 1
    assert any(e["description"] == "CHANGED" for e in kb.load_kg()["entities"])
    assert len(kb.load_kg()["entities"]) == 5


@pytest.mark.req("REQ-KG-02")
def test_check_keeps_broken_edits_for_fixing(generated, engine):
    kb, _, _ = generated
    data = yaml.safe_load(kb.kg_path.read_text(encoding="utf-8"))
    next(e for e in data["entities"] if e["name"] == "Product")["table"] = "prodcts"  # typo while editing
    kb.kg_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    report = kb.check_kg(engine)
    assert any("unknown table 'prodcts'" in d for d in report.dropped)
    assert any("unknown entity 'Product'" in d for d in report.dropped)
    saved = kb.load_kg()
    assert any(e["name"] == "Product" and e["table"] == "prodcts" for e in saved["entities"])  # not deleted
    assert any("prodcts" in w for w in kb.model().warnings)


@pytest.mark.req("REQ-KG-05")
def test_link_table_with_two_keys_to_the_same_table(tmp_path):
    path = tmp_path / "bom.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE parts (part_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE bom (bom_id INTEGER PRIMARY KEY, assembly_id INTEGER REFERENCES parts(part_id),
                          component_id INTEGER REFERENCES parts(part_id), qty INTEGER);
        CREATE TABLE kits (kit_id INTEGER PRIMARY KEY, main_part_id INTEGER REFERENCES parts(part_id),
                           spare_part_id INTEGER REFERENCES parts(part_id));
        INSERT INTO parts VALUES (1, 'Bike'), (2, 'Wheel'), (3, 'Frame'), (4, 'Trike'), (5, 'Seat');
        INSERT INTO bom VALUES (1, 1, 2, 2), (2, 1, 3, 1), (3, 4, 2, 3), (4, 4, 5, 1);
        INSERT INTO kits VALUES (1, 1, 2), (2, 4, 5);""")
    con.commit()
    con.close()
    engine = make_engine(resolve_url(str(path)))
    kb = KnowledgeBase(tmp_path / "kb", embedder="hash:64")
    kb.save_catalog(scan_database(engine, ScanOptions(), log=lambda _m: None))
    graph = {
        "entities": [{"name": "Part", "table": "parts", "label": ["name"]}, {"name": "Kit", "table": "kits"}],
        "relations": [
            {"subject": "Part", "predicate": "has_component", "object": "Part", "via": ["bom.assembly_id"]},
            {"subject": "Part", "predicate": "used_in", "object": "Part", "via": ["bom.component_id"]},
            {"subject": "Kit", "predicate": "spare_part", "object": "Part", "via": ["kits.spare_part_id"]},
            {"subject": "Kit", "predicate": "main_part", "object": "Part", "via": ["kits.main_part_id"]},
        ],
    }
    report = kb.import_kg(graph, engine)
    assert report.relations == 4, report.text()
    has = _rel(kb, "Part", "has_component")
    assert has["join"] == (
        "FROM parts s JOIN bom v1 ON v1.assembly_id = s.part_id JOIN parts o ON v1.component_id = o.part_id"
    )
    assert has["via"] == ["bom.assembly_id"]
    assert has["cardinality"] == "M:N"
    assert has["verified"]["pairs"] == 4
    rows = run_select(engine, f"SELECT s.name, o.name {has['join']} ORDER BY 1, 2")[1]
    assert rows == [("Bike", "Frame"), ("Bike", "Wheel"), ("Trike", "Seat"), ("Trike", "Wheel")]
    assert _rel(kb, "Part", "used_in")["join"].startswith("FROM parts s JOIN bom v1 ON v1.component_id = s.part_id")
    spare = _rel(kb, "Kit", "spare_part")  # two direct links between the same tables: the pinned column wins
    assert spare["join"] == "FROM kits s JOIN parts o ON s.spare_part_id = o.part_id"
    assert spare["via"] == ["kits.spare_part_id"]
    assert _rel(kb, "Kit", "main_part")["join"] == "FROM kits s JOIN parts o ON s.main_part_id = o.part_id"
    assert run_select(engine, f"SELECT o.name {spare['join']} ORDER BY 1")[1] == [("Seat",), ("Wheel",)]
    kb.build(log=lambda _m: None)  # re-planning from the saved via reproduces the same joins
    assert {r["join"] for r in kb.model().kg["relations"]} == {r["join"] for r in kb.load_kg()["relations"]}


@pytest.mark.req("REQ-KG-03")
def test_large_schemas_are_split_and_later_parts_reuse_names(generated):
    kb, _, _ = generated
    model = kb.model()
    tasks = build_tasks(model, max_chars=700)
    assert len(tasks) > 1
    assert sorted(t for task in tasks for t in task.tables) == sorted(t.fqn for t in model.visible_tables())
    prompt = task_prompt(model, tasks[-1], model.kg)
    assert "Entities already defined" in prompt
    assert "- Wholesale Customer = customers WHERE segment = 'Wholesale'" in prompt
    assert f"(part {len(tasks)} of {len(tasks)})" in prompt


@pytest.mark.req("REQ-MCP-01", "REQ-KG-01")
def test_mcp_tools_let_copilot_build_the_graph(kb, engine):
    from mcp.client.client import Client

    from sqlmem.mcp_server import create_server

    async def run():
        async with Client(create_server(kb, engine)) as c:
            empty = await c.call_tool("get_knowledge_graph", {})
            assert "empty" in tool_text(empty)
            task = tool_text(await c.call_tool("knowledge_graph_task", {"part": 1}))
            assert task.startswith("KNOWLEDGE GRAPH TASK - part 1 of 1")
            assert "### order_items" in task
            saved = await c.call_tool(
                "save_knowledge_graph", {"entities": GRAPH["entities"], "relations": GRAPH["relations"]}
            )
            text = tool_text(saved)
            assert not saved.is_error
            assert text.startswith("Accepted 5 entities and 4 relations")
            assert "unknown table 'invoices'" in text
            assert "now has 5 entities and 4 relations" in text
            detail = tool_text(await c.call_tool("get_knowledge_graph", {"entity": "client"}))
            assert detail.startswith("Customer (core)")
            assert "Customer --places--> Order" in detail
            ctx = tool_text(await c.call_tool("get_sql_context", {"question": "orders of wholesale customers"}))
            assert "Business concepts (knowledge graph)" in ctx
            bad = await c.call_tool("get_knowledge_graph", {"entity": "Unicorn"})
            assert bad.is_error
            assert "Known entities" in tool_text(bad)

    asyncio.run(run())


@pytest.mark.req("REQ-KG-10", "REQ-CLI-01")
def test_cli_export_import_check(tmp_path, db_path, capsys, monkeypatch):
    monkeypatch.delenv("SQLMEM_LLM", raising=False)
    kbdir = str(tmp_path / "kb")
    main(["scan", "--kb", kbdir, "--db", str(db_path), "--embedder", "hash:64"])
    capsys.readouterr()
    prompt = tmp_path / "prompt.md"
    main(["graph", "--kb", kbdir, "--export-prompt", str(prompt)])
    text = prompt.read_text(encoding="utf-8")
    assert "# SYSTEM" in text
    assert "# USER" in text
    assert "### order_items" in text
    reply = tmp_path / "reply.md"  # e.g. a chat answer pasted with prose and a code fence
    reply.write_text("Here is the graph:\n```json\n" + json.dumps(GRAPH) + "\n```\n", encoding="utf-8")
    main(["graph", "--kb", kbdir, "--import", str(reply), "--db", str(db_path)])
    out = capsys.readouterr().out
    assert "Accepted 5 entities and 4 relations - verified against the data." in out
    assert "knowledge graph=5 entities/4 relations" in out
    main(["graph", "--kb", kbdir, "--check", "--no-verify", "--no-build"])
    assert "checked against the schema only" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        main(["graph", "--kb", kbdir])  # no LLM configured anywhere
    assert exc.value.code == 2
    assert "No LLM configured" in capsys.readouterr().err
