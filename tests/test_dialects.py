"""Same end-to-end scenario on every database engine (portable SQLAlchemy DDL).

Always runs on SQLite and, when `duckdb-engine` is installed, DuckDB. Add other engines with SQLMEM_TEST_URLS,
a whitespace-separated list of SQLAlchemy URLs (the login needs CREATE SCHEMA / CREATE DATABASE), e.g.
    $env:SQLMEM_TEST_URLS = "postgresql+psycopg://postgres@127.0.0.1:5432/postgres mysql+pymysql://root@127.0.0.1:3306/mysql"
Each run creates a scratch schema (a database on MySQL/MariaDB) and drops it afterwards.
"""

import asyncio
import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    create_engine,
    func,
    select,
)
from sqlalchemy.exc import DBAPIError

from sqlmem.db import QueryTimeout, make_engine, run_select
from sqlmem.kb import KnowledgeBase
from sqlmem.model import Relationship
from sqlmem.model import Table as ModelTable
from sqlmem.scan import ScanOptions, scan_database
from tests.conftest import tool_text

# "readonly database" (SQLite), "read-only" (DuckDB, PostgreSQL), "READ ONLY transaction" (MySQL/MariaDB)
READ_ONLY_ERROR = r"(?i)read[- ]?only"

_RECURSIVE = (
    "WITH RECURSIVE c(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM c WHERE n < 2000000000) SELECT COUNT(*) FROM c"
)
_IS_CROSS = (
    "SELECT COUNT(*) FROM information_schema.COLUMNS a, information_schema.COLUMNS b, information_schema.COLUMNS c"
)
HEAVY = {  # a query that runs for minutes on each engine (used to test the per-query time limit)
    "sqlite": _RECURSIVE,
    "duckdb": _RECURSIVE,
    "mysql": _IS_CROSS,
    "mariadb": _IS_CROSS,
    "postgresql": "SELECT COUNT(*) FROM generate_series(1, 3000000000) g",
    "mssql": "SELECT COUNT_BIG(*) FROM sys.all_columns a CROSS JOIN sys.all_columns b CROSS JOIN sys.all_columns c",
}


def _targets() -> list[str]:
    targets = ["sqlite"]
    try:
        import duckdb_engine  # noqa: F401

        targets.append("duckdb")
    except ImportError:
        pass
    return targets + os.environ.get("SQLMEM_TEST_URLS", "").split()


def _label(target: str) -> str:
    return target.split("://")[0]


@contextmanager
def scratch(target: str, tmp_path):
    if target == "sqlite":
        url, schema = f"sqlite:///{(tmp_path / 'scratch.db').as_posix()}", None
    elif target == "duckdb":
        url, schema = f"duckdb:///{(tmp_path / 'scratch.duckdb').as_posix()}", "sqlmem_t"
    else:
        url, schema = target, "sqlmem_t_" + uuid.uuid4().hex[:8]
    engine = create_engine(url)
    dialect = engine.dialect.name
    try:
        if schema:
            with engine.begin() as conn:
                conn.exec_driver_sql(f"CREATE {'DATABASE' if dialect in ('mysql', 'mariadb') else 'SCHEMA'} {schema}")
        yield engine, url, schema
    finally:
        if schema and target != "duckdb":
            with engine.begin() as conn:
                if dialect in ("mysql", "mariadb"):
                    conn.exec_driver_sql(f"DROP DATABASE {schema}")
                elif dialect == "postgresql":
                    conn.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
                elif dialect == "mssql":
                    for kind, name in (
                        ("VIEW", "vOrderTotal"),
                        ("TABLE", "Note"),
                        ("TABLE", "OrderLine"),
                        ("TABLE", "Order"),
                        ("TABLE", "Customer"),
                        ("TABLE", "Product"),
                    ):
                        conn.exec_driver_sql(f"DROP {kind} IF EXISTS {schema}.[{name}]")
                    conn.exec_driver_sql(f"DROP SCHEMA {schema}")
        engine.dispose()


def build_schema(engine, schema: str | None) -> None:
    md = MetaData(schema=schema)
    customer = Table(
        "Customer",
        md,
        Column("CustomerId", Integer, primary_key=True, autoincrement=False),
        Column("Name", String(100), nullable=False),
        Column("Country", String(50), nullable=False),
        Column("Email", String(200)),
    )
    product = Table(
        "Product",
        md,
        Column("ProductId", Integer, primary_key=True, autoincrement=False),
        Column("Name", String(100), nullable=False),
        Column("Category", String(50), nullable=False),
        Column("ListPrice", Numeric(10, 2), nullable=False),
    )
    order = Table(
        "Order",
        md,  # reserved word
        Column("OrderId", Integer, primary_key=True, autoincrement=False),
        Column("CustomerId", Integer, ForeignKey(customer.c.CustomerId), nullable=False),
        Column("OrderDate", Date, nullable=False),
        Column("Status", SmallInteger, nullable=False),
        Column("IsOnline", Boolean, nullable=False),
        Column("Total", Numeric(12, 2), nullable=False),
    )
    line = Table(
        "OrderLine",
        md,
        Column("OrderId", Integer, ForeignKey(order.c.OrderId), primary_key=True, autoincrement=False),
        Column("LineNo", Integer, primary_key=True, autoincrement=False),  # reserved in T-SQL
        Column("ProductId", Integer, nullable=False),  # deliberately no FK: the join must be inferred
        Column("Qty", Integer, nullable=False),
    )
    note = Table(
        "Note",
        md,  # polymorphic: RefId is a customer or a product id depending on RefType
        Column("NoteId", Integer, primary_key=True, autoincrement=False),
        Column("RefType", String(1), nullable=False),
        Column("RefId", Integer, nullable=False),
        Column("Body", String(200)),
    )
    md.create_all(engine)
    view = (
        select(customer.c.Country, func.sum(order.c.Total).label("Revenue"))
        .select_from(order.join(customer))
        .group_by(customer.c.Country)
    )
    view_name = engine.dialect.identifier_preparer.format_table(Table("vOrderTotal", MetaData(), schema=schema))
    with engine.begin() as conn:
        conn.execute(
            customer.insert(),
            [
                {"CustomerId": 1, "Name": "Acme Bikes", "Country": "Germany", "Email": "a@acme.example"},
                {"CustomerId": 2, "Name": "Bolt Cycles", "Country": "France", "Email": "b@bolt.example"},
                {"CustomerId": 3, "Name": "Cog Works", "Country": "Germany", "Email": None},
                {"CustomerId": 4, "Name": "Dyna Sport", "Country": "United States", "Email": "d@dyna.example"},
            ],
        )
        conn.execute(
            product.insert(),
            [
                {"ProductId": 1, "Name": "Road Bike", "Category": "Bikes", "ListPrice": 1200},
                {"ProductId": 2, "Name": "Sport Helmet", "Category": "Helmets", "ListPrice": 60},
                {"ProductId": 3, "Name": "Kids Helmet", "Category": "Helmets", "ListPrice": 40},
                {"ProductId": 4, "Name": "Water Bottle", "Category": "Accessories", "ListPrice": 8},
            ],
        )
        conn.execute(
            order.insert(),
            [
                {"OrderId": i, "CustomerId": c, "OrderDate": d, "Status": s, "IsOnline": o, "Total": t}
                for i, c, d, s, o, t in [
                    (1, 1, date(2024, 1, 5), 1, True, 1260),
                    (2, 2, date(2024, 2, 9), 2, False, 1200),
                    (3, 3, date(2024, 3, 1), 2, True, 100),
                    (4, 1, date(2024, 4, 2), 2, True, 68),
                    (5, 4, date(2024, 5, 7), 1, False, 2400),
                    (6, 3, date(2024, 6, 30), 2, True, 40),
                ]
            ],
        )
        conn.execute(
            line.insert(),
            [
                {"OrderId": o, "LineNo": n, "ProductId": p, "Qty": q}
                for o, n, p, q in [
                    (1, 1, 1, 1),
                    (1, 2, 2, 1),
                    (2, 1, 1, 1),
                    (3, 1, 2, 1),
                    (3, 2, 3, 1),
                    (4, 1, 2, 1),
                    (4, 2, 4, 1),
                    (5, 1, 1, 2),
                    (6, 1, 3, 1),
                ]
            ],
        )
        conn.execute(
            note.insert(),
            [
                {"NoteId": i, "RefType": t, "RefId": r, "Body": b}
                for i, t, r, b in [
                    (1, "C", 1, "vip"),
                    (2, "C", 3, "late payer"),
                    (3, "P", 2, "recall"),
                    (4, "P", 99, "discontinued"),
                    (5, "X", 5, "misc"),
                    (6, "C", 1, "reorder"),
                ]
            ],
        )
        sql = view.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
        conn.exec_driver_sql(f"CREATE VIEW {view_name} AS {sql}")
        if (
            engine.dialect.name == "postgresql"
        ):  # engine-specific objects: materialized view + type unknown to SQLAlchemy
            conn.exec_driver_sql(
                f'CREATE MATERIALIZED VIEW {schema}."mvCategorySales" AS SELECT p."Category", '
                f'SUM(l."Qty") AS "Units" FROM {schema}."OrderLine" l JOIN {schema}."Product" p '
                f'ON p."ProductId" = l."ProductId" GROUP BY p."Category"'
            )
            conn.exec_driver_sql(f'ALTER TABLE {schema}."Customer" ADD COLUMN "Location" point')


@pytest.mark.req("REQ-SCAN-01", "REQ-SCAN-02", "REQ-SCAN-04", "REQ-SAFE-02", "REQ-RET-03", "REQ-KG-01", "REQ-CHART-03")
@pytest.mark.parametrize("target", _targets(), ids=_label)
def test_end_to_end_on_engine(target, tmp_path):
    with scratch(target, tmp_path) as (engine, url, schema):
        build_schema(engine, schema)
        dialect = engine.dialect.name
        engine.dispose()  # from here on only the read-only engine sqlmem itself uses
        ro = make_engine(url, query_timeout=60)
        try:
            q = lambda n: f"{schema}.{n}" if schema else n  # noqa: E731
            cat = scan_database(ro, ScanOptions(schemas=[schema] if schema else None, workers=2), log=lambda _m: None)
            assert cat["errors"] == []
            assert not [(o["fqn"], o["error"]) for o in cat["objects"] if o.get("error")]
            assert not [
                (o["fqn"], c["name"], c["profile_error"])
                for o in cat["objects"]
                for c in o["columns"]
                if c.get("profile_error")
            ]
            expected = ["Customer", "Product", "Order", "OrderLine", "Note", "vOrderTotal"]
            expected += ["mvCategorySales"] if dialect == "postgresql" else []
            assert {o["fqn"].lower() for o in cat["objects"]} == {q(n).lower() for n in expected}

            kb = KnowledgeBase(tmp_path / "kb", embedder="hash:128")
            kb.save_catalog(cat)
            kb.build(log=lambda _m: None)
            m = kb.model()

            def table(name: str) -> ModelTable:
                found = m.resolve(q(name))
                assert found is not None, f"{name} was not found"
                return found

            c, p, o, li = (table(n) for n in ("Customer", "Product", "Order", "OrderLine"))

            def col(tab, name):
                return next(x for x in tab.columns.values() if x.name.lower() == name.lower())

            def rel(a: ModelTable, b: ModelTable) -> Relationship | None:
                return next((r for r in m.relationships if r.from_table == a.fqn and r.to_table == b.fqn), None)

            assert o.row_count == 6
            assert sorted(v for v, _ in col(o, "Status").profile["values"]) == [1, 2]
            assert col(c, "Email").sensitive
            assert "values" not in col(c, "Email").profile
            assert rel(o, c) is not None
            assert rel(li, o) is not None
            line_product = rel(li, p)
            assert line_product is not None
            assert line_product.source == "inferred"
            ctx = kb.context("helmet sales to customers in Germany")
            assert "= 'Helmets'" in ctx
            assert "= 'Germany'" in ctx
            if dialect == "postgresql":
                mv = table("mvCategorySales")
                assert mv.type == "materialized view"
                assert mv.row_count is not None
                assert col(c, "Location").type == "POINT"

            # SQL assembled only from the knowledge (quoted names + join conditions) must run unchanged.
            path = m.join_path(li.fqn, c.fqn)
            assert path is not None
            sql = (
                f"SELECT {p.sql_name}.{col(p, 'Category').sql_name}, SUM({li.sql_name}.{col(li, 'Qty').sql_name}) "
                f"FROM {li.sql_name} JOIN {o.sql_name} ON {path[0].on_clause(m)} "
                f"JOIN {c.sql_name} ON {path[1].on_clause(m)} JOIN {p.sql_name} ON {line_product.on_clause(m)} "
                f"WHERE {c.sql_name}.{col(c, 'Country').sql_name} = 'Germany' "
                f"GROUP BY {p.sql_name}.{col(p, 'Category').sql_name} ORDER BY 1"
            )
            _, rows, _ = run_select(ro, sql)
            assert [(r[0], int(r[1])) for r in rows] == [("Accessories", 1), ("Bikes", 1), ("Helmets", 5)]

            chart_sql = (
                f"SELECT {col(p, 'Category').sql_name} AS chartcategory, "
                f"SUM({col(p, 'ListPrice').sql_name}) AS chartvalue FROM {p.sql_name} "
                f"GROUP BY {col(p, 'Category').sql_name} ORDER BY 1"
            )

            async def check_chart():
                from mcp.client.client import Client

                from sqlmem.mcp_server import create_server

                async with Client(create_server(kb, ro, row_cap=2)) as client:
                    result = await client.call_tool(
                        "create_chart",
                        {
                            "source": {
                                "kind": "sql",
                                "sql": chart_sql,
                                "columns": [
                                    {"name": "chartcategory", "kind": "string", "sensitivity": "non_sensitive"},
                                    {"name": "chartvalue", "kind": "number", "sensitivity": "non_sensitive"},
                                ],
                            },
                            "spec": {"type": "bar", "mapping": {"x": "chartcategory", "y": ["chartvalue"]}},
                        },
                    )
                    assert not result.is_error, tool_text(result)
                    artifact = json.loads(tool_text(result))
                    assert artifact["row_count"] == 2
                    assert artifact["source_truncated"] is True
                    assert artifact["chart_type"] == "bar"

            asyncio.run(check_chart())

            if dialect in ("postgresql", "mysql", "mariadb", "duckdb", "sqlite"):  # the engine itself blocks writes
                with ro.connect() as conn, pytest.raises(DBAPIError, match=READ_ONLY_ERROR):
                    conn.exec_driver_sql(f"UPDATE {o.sql_name} SET {col(o, 'Status').sql_name} = 3")

            # Knowledge graph: filters and joins are generated, executed and measured on this engine.
            graph = {
                "entities": [
                    {"name": "Customer", "table": q("Customer"), "label": ["Name"]},
                    {
                        "name": "German Customer",
                        "table": q("Customer"),
                        "is_a": "Customer",
                        "filter": f"{col(c, 'Country').sql_name} = 'Germany'",
                    },
                    {"name": "Order", "table": q("Order")},
                    {"name": "Product", "table": q("Product")},
                ],
                "relations": [
                    {"subject": "Customer", "predicate": "places", "object": "Order"},
                    {"subject": "German Customer", "predicate": "places", "object": "Order"},
                    {"subject": "Order", "predicate": "contains", "object": "Product", "via": [q("OrderLine")]},
                ],
            }
            report = kb.import_kg(graph, ro)
            assert (report.entities, report.relations, report.dropped) == (4, 3, []), report.text()
            saved = kb.load_kg()
            assert next(e for e in saved["entities"] if e["name"] == "German Customer")["rows"] == 2
            rels = {f"{r['subject']} {r['predicate']}": r for r in saved["relations"]}
            assert rels["Customer places"]["verified"] == {"pairs": 6, "cardinality": "1:N"}
            assert rels["German Customer places"]["verified"] == {"pairs": 4, "cardinality": "1:N"}
            assert rels["Order contains"]["verified"] == {"pairs": 9, "cardinality": "M:N"}
            assert run_select(ro, f"SELECT COUNT(*) {rels['Order contains']['join']}")[1][0][0] == 9

            # Composite keys, explicit join columns and a polymorphic reference on this engine.
            more = {
                "entities": [{"name": "Order Line", "table": q("OrderLine")}, {"name": "Note", "table": q("Note")}],
                "relations": [
                    {"subject": "Order", "predicate": "has_line", "object": "Order Line"},
                    {
                        "subject": "Order Line",
                        "predicate": "for_product",
                        "object": "Product",
                        "on": f"{q('OrderLine')}.ProductId = {q('Product')}.ProductId",
                    },
                    {
                        "subject": "Note",
                        "predicate": "about",
                        "polymorphic": {
                            "column": "RefId",
                            "type_column": "RefType",
                            "targets": [{"type": "C", "object": "Customer"}, {"type": "P", "object": "Product"}],
                        },
                    },
                ],
            }
            report = kb.import_kg(more, ro)
            assert (report.entities, report.relations, report.dropped) == (2, 4, []), report.text()
            assert any("RefType values without a target: 'X' (1 rows)" in w for w in report.warnings), report.text()
            saved = kb.load_kg()
            line_key = next(e for e in saved["entities"] if e["name"] == "Order Line")["key"]
            assert [k.lower() for k in line_key] == ["orderid", "lineno"]
            rels = {f"{r['subject']} {r['predicate']} {r['object']}": r for r in saved["relations"]}
            assert rels["Order has_line Order Line"]["verified"] == {"pairs": 9, "cardinality": "1:N"}
            assert rels["Order Line for_product Product"]["verified"] == {
                "pairs": 9,
                "cardinality": "N:1",
                "unmatched": 0,
            }
            assert rels["Note about Customer"]["verified"] == {"pairs": 3, "cardinality": "N:1", "unmatched": 0}
            assert rels["Note about Product"]["verified"] == {"pairs": 1, "cardinality": "1:1", "unmatched": 1}
            for r in saved["relations"]:
                assert run_select(ro, f"SELECT COUNT(*) {r['join']}")[1][0][0] == r["verified"]["pairs"], r["join"]
            assert any(r.source == "kg" for r in kb.model().relationships)

            # Per-query time limit: a long query is cancelled and the engine stays usable.
            started = time.monotonic()
            with pytest.raises(QueryTimeout):
                run_select(ro, HEAVY[dialect], timeout=1)
            assert time.monotonic() - started < 30
            assert run_select(ro, "SELECT 1", timeout=1)[1][0][0] == 1
        finally:
            ro.dispose()
