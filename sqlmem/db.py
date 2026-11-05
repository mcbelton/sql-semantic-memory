"""Database connection helpers, a read-only SQL guard and per-query time limits."""

from __future__ import annotations

import contextlib
import os
import re
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, quote_plus, unquote_plus

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine, make_url


def resolve_url(db: str | None = None, odbc: str | None = None, readonly: bool = True) -> str:
    """Turn a file path, SQLAlchemy URL or raw ODBC connection string into a SQLAlchemy URL."""
    if odbc:
        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)
    db = db or os.environ.get("SQLMEM_DB")
    if not db:
        raise ValueError("No database given: use --db PATH|URL, --odbc CONNSTR or set SQLMEM_DB")
    if "://" in db:
        return db
    path = Path(db).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Database file not found: {path}")
    posix = quote(path.as_posix(), safe="/:")
    # SQLite URI filename => opened read-only so scanning/querying can never modify the file.
    return f"sqlite:///file:{posix}?mode=ro&uri=true" if readonly else f"sqlite:///{path.as_posix()}"


def make_engine(url: str, query_timeout: int | None = None, readonly: bool = True) -> Engine:
    """Engine for scanning/querying. With readonly=True the database itself rejects writes where it can
    (PostgreSQL/MySQL/MariaDB read-only sessions, DuckDB read-only open; SQLite files are opened mode=ro by
    resolve_url). SQL Server, Oracle and cloud warehouses rely on the login's permissions: use a read-only login."""
    u = make_url(url)
    backend = u.get_backend_name()
    kwargs: dict[str, Any] = {}
    if (
        backend == "sqlite"
        and readonly
        and u.database
        and u.database != ":memory:"
        and not u.database.startswith("file:")
    ):
        posix = quote(Path(u.database).expanduser().resolve().as_posix(), safe="/:")
        u = u.set(database=f"file:{posix}", query={**u.query, "mode": "ro", "uri": "true"})
    if backend == "postgresql":
        options = [str(u.query["options"])] if u.query.get("options") else []
        if readonly:
            options.append("-c default_transaction_read_only=on")
        if query_timeout:
            options.append(f"-c statement_timeout={int(query_timeout * 1000)}")
        if options:
            kwargs["connect_args"] = {"options": " ".join(options)}
    elif backend == "duckdb" and readonly:
        kwargs["connect_args"] = {"read_only": True}
    engine = create_engine(u, **kwargs)
    if backend == "mssql" and query_timeout and u.get_driver_name() == "pyodbc":

        @event.listens_for(engine, "connect")
        def _set_timeout(dbapi_conn: Any, _record: Any) -> None:  # pragma: no cover - needs SQL Server
            dbapi_conn.timeout = int(query_timeout)

    if backend in ("mysql", "mariadb") and (readonly or query_timeout):

        @event.listens_for(engine, "connect")
        def _mysql_session(dbapi_conn: Any, _record: Any) -> None:
            cur = dbapi_conn.cursor()
            try:
                if readonly:
                    cur.execute("SET SESSION TRANSACTION READ ONLY")
                if query_timeout:  # MariaDB names this max_statement_time (s), MySQL max_execution_time (ms)
                    for stmt in (
                        f"SET SESSION max_statement_time = {int(query_timeout)}",
                        f"SET SESSION max_execution_time = {int(query_timeout * 1000)}",
                    ):
                        try:
                            cur.execute(stmt)
                            break
                        except Exception:
                            continue
            finally:
                cur.close()

    return engine


def describe_source(url: str) -> dict[str, Any]:
    """Connection description that is safe to persist (no passwords)."""
    u = make_url(url)
    info: dict[str, Any] = {"dialect": u.get_backend_name(), "driver": u.get_driver_name()}
    odbc = u.query.get("odbc_connect")
    if odbc:
        raw = unquote_plus(odbc if isinstance(odbc, str) else odbc[0])
        parts = {k.strip().lower(): v.strip() for k, _, v in (p.partition("=") for p in raw.split(";") if "=" in p)}
        info["server"] = parts.get("server")
        info["database"] = parts.get("database") or parts.get("initial catalog")
        info["url"] = f"{u.drivername}:///?odbc_connect=<server={info['server']};database={info['database']}>"
        return info
    info["url"] = u.render_as_string(hide_password=True)
    database = u.database or ""
    if info["dialect"] == "sqlite":
        database = database.removeprefix("file:")
        info["path"] = database
        database = Path(database).stem
    info["database"] = database or None
    info["server"] = u.host
    return info


# ---------------------------------------------------------------------------
# Read-only guard (defense in depth: also use read-only logins; see make_engine)
# ---------------------------------------------------------------------------
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|upsert|drop|alter|create|truncate|exec|execute|grant|revoke|deny|"
    r"attach|detach|pragma|vacuum|reindex|copy|call|into|backup|restore|shutdown|kill|dbcc|bulk|install|"
    r"openrowset|opendatasource|openquery|load_extension|set|use|begin|commit|rollback|lock|"
    r"set_config|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_read_\w+|pg_ls_\w+|lo_import|lo_export|"
    r"dblink\w*|load_file|read_(?:text|blob|csv\w*|json\w*|ndjson\w*|parquet|xlsx)|"
    r"xp_\w+|sp_\w+)\b",
    re.IGNORECASE,
)
_CLOSE = {"'": "'", '"': '"', "`": "`", "[": "]"}


def _code_only(sql: str, dialect: str | None = None) -> str:
    """Blank out string literals and quoted identifiers, leaving only code.

    Constructs whose quoting rules differ between engines (comments, backslash-escaped quotes, dollar quoting,
    Oracle q-quotes) are rejected, so what is left is code under every dialect's lexer."""
    if re.search(r"(?<!\\)(?:\\\\)*\\['\"]", sql):
        raise ValueError("Backslash-escaped quotes are not allowed; double the quote instead ('')")
    brackets = dialect in (None, "mssql", "sqlite")  # [identifier] quoting; in PostgreSQL [ ] is array syntax
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "$" and re.match(r"\$(?:[A-Za-z_]\w*)?\$", sql[i:]):
            raise ValueError("Dollar-quoted strings are not allowed")
        if sql.startswith(("--", "/*"), i) or (
            ch == "#" and dialect not in ("postgresql", "duckdb", "mssql", "sqlite")
        ):
            raise ValueError("SQL comments are not allowed in queries run by the agent; remove them")
        if ch in _CLOSE and (ch != "[" or brackets):
            if ch == "'" and re.search(r"(?:^|[^\w$])[nN]?[qQ]$", sql[max(0, i - 3) : i]):
                raise ValueError("Oracle q'...' quoting is not allowed")
            close, j = _CLOSE[ch], i + 1
            while True:
                k = sql.find(close, j)
                if k < 0:
                    raise ValueError("Unterminated quoted string or identifier")
                if k + 1 < n and sql[k + 1] == close:  # doubled quote ('' "" `` ]]) is an escaped quote
                    j = k + 2
                    continue
                break
            out.append(" '' " if ch == "'" else " _q_ ")
            i = k + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def check_readonly(sql: str, dialect: str | None = None) -> None:
    """Raise ValueError unless `sql` is a single SELECT/WITH statement without write/side-effect keywords."""
    body = _code_only(sql, dialect).strip().rstrip(";").strip()
    if not body:
        raise ValueError("Empty SQL")
    if ";" in body:
        raise ValueError("Only a single statement is allowed")
    if not re.match(r"\(*\s*(select|with)\b", body, re.IGNORECASE):
        raise ValueError("Only SELECT / WITH queries are allowed")
    bad = _FORBIDDEN.search(body)
    if bad:
        raise ValueError(f"Keyword not allowed in read-only mode: {bad.group(0).upper()}")
    if re.search(r"\b(from|join)\s+''", body, re.IGNORECASE):
        raise ValueError("Reading files through string literals in FROM/JOIN is not allowed")


def _fmt(v: Any, width: int = 80) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(v))} bytes>"
    s = str(v).replace("\n", " ").replace("|", "\\|")
    return s if len(s) <= width else s[: width - 3] + "..."


class QueryTimeout(Exception):
    """A query was cancelled because it ran longer than its time limit."""


_TIMEOUT_MARKERS = (
    "interrupted",
    "statement timeout",
    "canceling statement",
    "max_execution_time",
    "max_statement_time",
    "query timeout expired",
    "[hyt00]",
)


@contextmanager
def time_limit(conn: Connection, seconds: float | None) -> Generator[None, None, None]:
    """Cancel statements on `conn` that run longer than `seconds` (raises QueryTimeout).

    SQLite/DuckDB: interrupt() from a timer; PostgreSQL: SET LOCAL statement_timeout; MySQL/MariaDB:
    max_execution_time / max_statement_time for the session; SQL Server (pyodbc): the connection's query timeout.
    Other engines run without a per-query limit (use a login/resource-governor limit there)."""
    if not seconds or seconds <= 0:
        yield
        return
    dialect = conn.dialect.name
    raw: Any = conn.connection.dbapi_connection  # driver-specific: timeout (pyodbc), interrupt() (sqlite3, duckdb)
    fired = threading.Event()
    timer: threading.Timer | None = None
    undo: Callable[[], None] | None = None
    if dialect == "postgresql":
        conn.exec_driver_sql(f"SET LOCAL statement_timeout = {max(1, int(seconds * 1000))}")
    elif dialect in ("mysql", "mariadb"):
        mariadb = bool(getattr(conn.dialect, "is_mariadb", False))
        var = "max_statement_time" if mariadb else "max_execution_time"
        value = f"{seconds:g}" if mariadb else str(max(1, int(seconds * 1000)))
        old = conn.exec_driver_sql(f"SELECT @@SESSION.{var}").scalar()
        conn.exec_driver_sql(f"SET SESSION {var} = {value}")

        def reset_session() -> None:
            conn.exec_driver_sql(f"SET SESSION {var} = {old}")

        undo = reset_session
    elif dialect == "mssql" and hasattr(raw, "timeout"):
        old_timeout = raw.timeout
        raw.timeout = max(1, round(seconds))

        def reset_timeout() -> None:
            raw.timeout = old_timeout

        undo = reset_timeout
    elif hasattr(raw, "interrupt"):  # sqlite3 and duckdb connections can be interrupted from another thread

        def stop() -> None:
            fired.set()
            raw.interrupt()

        timer = threading.Timer(seconds, stop)
        timer.daemon = True
        timer.start()
    try:
        yield
    except Exception as e:
        if fired.is_set() or any(m in str(e).lower() for m in _TIMEOUT_MARKERS):
            raise QueryTimeout(f"the query did not finish within {seconds:g}s") from e
        raise
    finally:
        if timer is not None:
            timer.cancel()
        if undo is not None:
            with contextlib.suppress(Exception):
                undo()


def run_select(
    engine: Engine, sql: str, max_rows: int = 50, timeout: float | None = None
) -> tuple[list[str], list[tuple[Any, ...]], bool]:
    check_readonly(sql, engine.dialect.name)
    with engine.connect() as conn:
        with time_limit(conn, timeout):
            result = conn.execution_options(no_parameters=True).exec_driver_sql(sql.strip().rstrip(";"))
            cols = list(result.keys())
            rows = [tuple(r) for r in result.fetchmany(max_rows + 1)]
        conn.rollback()
    return cols, rows[:max_rows], len(rows) > max_rows


def format_rows(cols: list[str], rows: list[tuple[Any, ...]], truncated: bool = False) -> str:
    if not cols:
        return "(no result set)"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(_fmt(v) for v in r) + " |" for r in rows]
    out.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''}{', truncated' if truncated else ''})")
    return "\n".join(out)
