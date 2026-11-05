"""SQL Server integration test (opt-in).

Run against any SQL Server where you may create a scratch database, e.g. LocalDB:
    $env:SQLMEM_MSSQL_ODBC = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\MSSQLLocalDB;" +
                             "Trusted_Connection=yes;"
    pytest tests/test_mssql.py
"""

import os
import uuid

import pytest

ODBC = os.environ.get("SQLMEM_MSSQL_ODBC", "")
pytestmark = pytest.mark.skipif(not ODBC, reason="set SQLMEM_MSSQL_ODBC to run SQL Server integration tests")

DDL = [
    "CREATE SCHEMA Sales",
    "CREATE SCHEMA HR",
    """CREATE TABLE HR.Employee (EmployeeID int IDENTITY PRIMARY KEY, FullName nvarchar(100) NOT NULL,
         Email nvarchar(200) NULL, IsActive bit NOT NULL DEFAULT 1, OrgNode hierarchyid NULL, HiredOn date NOT NULL,
         Salary money NOT NULL, rowguid uniqueidentifier NOT NULL DEFAULT NEWID(), Notes nvarchar(max) NULL,
         Resume xml NULL, Legacy ntext NULL)""",
    """CREATE TABLE Sales.Customer (CustomerID int IDENTITY PRIMARY KEY, Name nvarchar(100) NOT NULL,
         Country nvarchar(50) NOT NULL, Location geography NULL, Segment char(2) NOT NULL)""",
    """CREATE TABLE Sales.[Order] (OrderID int IDENTITY PRIMARY KEY,
         CustomerID int NOT NULL REFERENCES Sales.Customer(CustomerID), EmployeeID int NULL,
         OrderDate datetime2 NOT NULL, Status tinyint NOT NULL, Total decimal(12,2) NOT NULL, Online bit NOT NULL)""",
    """CREATE VIEW Sales.vOrderTotals AS SELECT c.Country, SUM(o.Total) AS Revenue
         FROM Sales.[Order] o JOIN Sales.Customer c ON c.CustomerID = o.CustomerID GROUP BY c.Country""",
    """CREATE PROCEDURE Sales.uspTopCustomers @n int AS
         SELECT TOP (@n) CustomerID, SUM(Total) AS Total FROM Sales.[Order] GROUP BY CustomerID ORDER BY 2 DESC""",
    "EXEC sp_addextendedproperty 'MS_Description', 'Customer orders', 'SCHEMA', 'Sales', 'TABLE', 'Order'",
    (
        "EXEC sp_addextendedproperty 'MS_Description', '1=Open, 2=Shipped', 'SCHEMA', 'Sales', 'TABLE', 'Order', "
        "'COLUMN', 'Status'"
    ),
    (
        "EXEC sp_addextendedproperty 'MS_Description', 'Returns top customers', 'SCHEMA', 'Sales', 'PROCEDURE', "
        "'uspTopCustomers'"
    ),
    """INSERT HR.Employee (FullName, Email, OrgNode, HiredOn, Salary, Notes, Resume, Legacy) VALUES
         (N'Ann Lee', N'ann@x.com', hierarchyid::Parse('/1/'), '2020-01-05', 5000, N'n', N'<r/>', N'l'),
         (N'Bob Ray', N'bob@x.com', hierarchyid::Parse('/1/1/'), '2021-03-01', 4000, NULL, NULL, NULL)""",
    """INSERT Sales.Customer (Name, Country, Location, Segment) VALUES
         (N'Acme', N'Germany', geography::Point(52.5, 13.4, 4326), 'RT'), (N'Bolt', N'France', NULL, 'WH'),
         (N'Cogs', N'Germany', NULL, 'RT')""",
    """INSERT Sales.[Order] (CustomerID, EmployeeID, OrderDate, Status, Total, Online) VALUES
         (1, 1, '2024-01-02', 1, 10.50, 1), (2, 2, '2024-02-03', 2, 20.00, 0), (3, NULL, '2024-03-04', 2, 30.25, 1),
         (1, 1, '2024-04-05', 2, 40.00, 1)""",
]


@pytest.fixture(scope="module")
def mssql_odbc():
    pyodbc = pytest.importorskip("pyodbc")  # optional extra 'mssql'

    name = "sqlmem_test_" + uuid.uuid4().hex[:8]
    base = ODBC if ODBC.rstrip().endswith(";") else ODBC + ";"
    master = pyodbc.connect(base, autocommit=True)
    master.execute(f"CREATE DATABASE [{name}]")
    try:
        con = pyodbc.connect(base + f"Database={name};", autocommit=True)
        for stmt in DDL:
            con.execute(stmt)
        con.close()
        yield base + f"Database={name};"
    finally:
        master.execute(f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        master.execute(f"DROP DATABASE [{name}]")
        master.close()


@pytest.mark.req("REQ-SCAN-04", "REQ-SAFE-01")
def test_mssql_scan_model_and_query(mssql_odbc, tmp_path):
    from sqlmem.db import check_readonly, make_engine, resolve_url, run_select
    from sqlmem.kb import KnowledgeBase
    from sqlmem.scan import ScanOptions, scan_database

    engine = make_engine(resolve_url(odbc=mssql_odbc), query_timeout=60)
    try:
        cat = scan_database(engine, ScanOptions(), log=lambda _m: None)
        objs = {o["fqn"]: o for o in cat["objects"]}
        assert set(objs) == {"HR.Employee", "Sales.Customer", "Sales.Order", "Sales.vOrderTotals"}
        assert cat["source"]["dialect"] == "mssql"
        assert "PWD" not in cat["source"]["url"].upper()
        order = objs["Sales.Order"]
        assert order["sql_name"] == "Sales.[Order]"
        assert order["comment"] == "Customer orders"
        assert order["row_count"] == 4
        assert order["foreign_keys"][0]["ref_table"] == "Sales.Customer"
        cols = {c["name"]: c for c in order["columns"]}
        assert cols["Status"]["comment"] == "1=Open, 2=Shipped"
        assert sorted(v for v, _ in cols["Status"]["profile"]["values"]) == [1, 2]
        assert cols["Online"]["kind"] == "bool"

        emp = {c["name"]: c for c in objs["HR.Employee"]["columns"]}
        assert emp["OrgNode"]["type"] == "HIERARCHYID"
        assert emp["OrgNode"]["kind"] == "skip"
        assert emp["rowguid"]["kind"] == "uuid"
        assert emp["Salary"]["kind"] == "number"
        assert emp["Resume"]["kind"] == "lob"
        assert emp["Legacy"]["kind"] == "lob"
        assert emp["Notes"]["kind"] == "text"
        assert emp["Email"]["sensitive"]
        assert "values" not in emp["Email"]["profile"]
        assert emp["HiredOn"]["profile"]["min"].startswith("2020-01-05")
        cust = {c["name"]: c for c in objs["Sales.Customer"]["columns"]}
        assert cust["Location"]["type"] == "GEOGRAPHY"
        assert not [
            (o["fqn"], c["name"], c["profile_error"])
            for o in cat["objects"]
            for c in o["columns"]
            if c.get("profile_error")
        ]
        assert objs["Sales.vOrderTotals"]["type"] == "view"
        assert any(
            r["fqn"] == "Sales.uspTopCustomers" and r["comment"] == "Returns top customers" for r in cat["routines"]
        )

        kb = KnowledgeBase(tmp_path / "kb", embedder="hash:128")
        kb.save_catalog(cat)
        kb.build(log=lambda _m: None)
        model = kb.model()
        assert any(
            r.from_table == "Sales.Order"
            and r.from_columns == ["EmployeeID"]
            and r.to_table == "HR.Employee"
            and r.source == "inferred"
            for r in model.relationships
        )
        assert model.resolve("[Sales].[Order]") is model.tables["Sales.Order"]
        ctx = kb.context("order revenue by customer country in Germany")
        assert "Sales.[Order]" in ctx
        assert "Sales.Customer" in ctx
        assert "= 'Germany'" in ctx
        assert "Sales.[Order].CustomerID = Sales.Customer.CustomerID" in ctx

        _, rows, _ = run_select(
            engine, "SELECT TOP 2 Country, COUNT(*) AS n FROM Sales.Customer GROUP BY Country ORDER BY n DESC"
        )
        assert rows[0] == ("Germany", 2)
        with pytest.raises(ValueError, match="Only SELECT"):
            check_readonly("EXEC Sales.uspTopCustomers 1")
    finally:
        engine.dispose()
