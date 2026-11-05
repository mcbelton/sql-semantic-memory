"""Shared fixtures, plus the requirement-traceability plugin (see docs/requirements.md).

`@pytest.mark.req("REQ-...")` links a test to requirements (or to a quality gate such as "QA-LINT"): unknown or
retired ids stop the run, and `pytest --evidence-json PATH` writes every test's outcome with its requirement ids for
scripts/verify.py, which parses docs/requirements.md with the same function.
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from scripts.verify import REQUIREMENTS, requirement_rows
from sqlmem.db import make_engine, resolve_url
from sqlmem.kb import KnowledgeBase
from sqlmem.scan import ScanOptions, scan_database

if TYPE_CHECKING:
    from mcp.types import CallToolResult
    from sqlalchemy.engine import Engine


def known_requirements(path: Path = REQUIREMENTS) -> set[str]:
    """Active requirement and quality-gate ids that tests may reference (retired ids excluded)."""
    if not path.exists():  # e.g. tests run from an sdist without docs
        return set()
    return {rid for rid, _text, _proof in requirement_rows(path)}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--evidence-json", metavar="PATH", help="write each test's outcome and requirement ids to PATH (JSON)"
    )


def pytest_configure(config: pytest.Config) -> None:
    path = config.getoption("--evidence-json")
    if path:
        config.pluginmanager.register(EvidenceRecorder(Path(path)), "sqlmem-evidence")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    known = known_requirements()
    unknown: list[str] = []
    for item in items:
        for mark in item.iter_markers(name="req"):
            for rid in mark.args:
                if known and rid not in known:
                    unknown.append(f"{item.nodeid}: {rid}")
                item.user_properties.append(("req", rid))
    if unknown:
        raise pytest.UsageError(
            "unknown requirement id(s), add them to docs/requirements.md:\n  " + "\n  ".join(unknown)
        )


class EvidenceRecorder:
    """Collects one entry per test: node id, requirement ids, outcome (passed/failed/skipped) and duration."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tests: dict[str, dict[str, Any]] = {}

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        entry = self.tests.setdefault(
            report.nodeid, {"nodeid": report.nodeid, "reqs": [], "outcome": "passed", "duration": 0.0}
        )
        entry["reqs"] = sorted({str(v) for k, v in report.user_properties if k == "req"})
        entry["duration"] = round(entry["duration"] + report.duration, 3)
        if report.failed:
            entry["outcome"] = "failed"
        elif report.skipped and entry["outcome"] != "failed":
            entry["outcome"] = "skipped"

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"exitstatus": int(exitstatus), "tests": sorted(self.tests.values(), key=lambda t: t["nodeid"])}
        self.path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def _make_db(path: Path) -> None:
    rnd = random.Random(0)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT, country TEXT,
                                segment TEXT, row_guid TEXT, created_at TEXT);
        CREATE TABLE products (product_id INTEGER PRIMARY KEY, name TEXT, category TEXT, price NUMERIC,
                               active INTEGER, row_guid TEXT, created_at TEXT);
        CREATE TABLE sales_reps (sales_rep_id INTEGER PRIMARY KEY, full_name TEXT, region TEXT,
                                 row_guid TEXT, created_at TEXT);
        CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
                             order_date TEXT, status INTEGER, sales_rep_id INTEGER, row_guid TEXT, created_at TEXT);
        CREATE TABLE order_items (order_id INTEGER REFERENCES orders(order_id), line_no INTEGER, product_id INTEGER,
                                  qty INTEGER, unit_price NUMERIC, row_guid TEXT, created_at TEXT,
                                  PRIMARY KEY (order_id, line_no));
        CREATE VIEW v_order_totals AS
            SELECT o.order_id, SUM(i.qty * i.unit_price) AS total
            FROM orders o JOIN order_items i ON i.order_id = o.order_id GROUP BY o.order_id;
    """)
    g = lambda: str(uuid.UUID(int=rnd.getrandbits(128)))  # noqa: E731
    ts = "2024-01-01T00:00:00"
    countries = ["Germany", "France", "United States"]
    for i in range(1, 21):
        con.execute(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
            (i, f"Customer {i}", f"c{i}@example.com", countries[i % 3], ["Retail", "Wholesale"][i % 2], g(), ts),
        )
    products = [
        ("Road Bike", "Bikes", 1200),
        ("Mountain Bike", "Bikes", 1500),
        ("Sport Helmet", "Helmets", 60),
        ("Kids Helmet", "Helmets", 40),
        ("Water Bottle", "Accessories", 8),
        ("Bike Lock", "Accessories", 25),
    ]
    for i, (n, c, p) in enumerate(products, 1):
        con.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?)", (i, n, c, p, 1, g(), ts))
    for i, (n, r) in enumerate([("Ann Lee", "North"), ("Bob Ray", "South"), ("Cid Fox", "West")], 1):
        con.execute("INSERT INTO sales_reps VALUES (?,?,?,?,?)", (i, n, r, g(), ts))
    line = 0
    for o in range(1, 61):
        con.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?)",
            (
                o,
                rnd.randint(1, 20),
                f"2024-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}T00:00:00",
                rnd.choice([1, 2, 3]),
                rnd.choice([1, 2, 3, None]),
                g(),
                ts,
            ),
        )
        for line_no in range(1, rnd.randint(2, 4)):
            line += 1
            pid = rnd.randint(1, 6)
            con.execute(
                "INSERT INTO order_items VALUES (?,?,?,?,?,?,?)",
                (o, line_no, pid, rnd.randint(1, 5), products[pid - 1][2], g(), ts),
            )
    con.commit()
    con.close()


def tool_text(result: CallToolResult) -> str:
    """Text of an MCP tool result; sqlmem tools always answer with one text block."""
    from mcp.types import TextContent

    assert result.content, result
    item = result.content[0]
    assert isinstance(item, TextContent), item
    return item.text


SEMANTIC: dict[str, Any] = {
    "database": {
        "name": "ShopDB",
        "description": "Bike shop sales.",
        "dialect_notes": ["Dates are ISO TEXT; use substr(order_date,1,4) for the year."],
    },
    "tables": {
        "orders": {
            "description": "Customer orders, one row per order.",
            "synonyms": ["sales", "purchases"],
            "columns": {
                "status": {"description": "Order status.", "values": {1: "Open", 2: "Shipped", 3: "Cancelled"}}
            },
        },
        "customers": "People and companies who buy from the shop.",
        "no_such_table": "typo on purpose",
    },
    "metrics": [
        {
            "name": "Revenue",
            "synonyms": ["sales amount"],
            "definition": "Sum of qty * unit price.",
            "sql": "SUM(order_items.qty * order_items.unit_price)",
        }
    ],
    "glossary": [
        {"term": "Wholesale customer", "definition": "customers.segment = 'Wholesale'", "tables": ["customers"]}
    ],
    "examples": [
        {
            "question": "Revenue by country",
            "sql": "SELECT c.country, SUM(i.qty * i.unit_price) FROM order_items i "
            "JOIN orders o ON o.order_id = i.order_id JOIN customers c ON c.id = o.customer_id "
            "GROUP BY c.country",
        }
    ],
}


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("db") / "shop.db"
    _make_db(path)
    return path


@pytest.fixture(scope="session")
def engine(db_path: Path) -> Iterator[Engine]:
    engine = make_engine(resolve_url(str(db_path)))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def catalog(engine):
    return scan_database(engine, ScanOptions(), log=lambda _m: None)


@pytest.fixture
def kb(tmp_path, catalog) -> Iterator[KnowledgeBase]:
    import yaml

    kb = KnowledgeBase(tmp_path / "kb", embedder="hash:256")
    kb.save_catalog(catalog)
    kb.semantic_path.write_text(yaml.safe_dump(SEMANTIC, sort_keys=False), encoding="utf-8")
    kb.build(log=lambda _m: None)
    yield kb
    kb.close()
