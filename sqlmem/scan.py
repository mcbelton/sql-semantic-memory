"""Scan a database: schema metadata + data profile of every table/view -> catalog dict (catalog.json)."""

from __future__ import annotations

import contextlib
import datetime as dt
import fnmatch
import math
import re
import sqlite3
import sys
import time
import uuid
import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import Float, case, cast, distinct, func, inspect, select, text
from sqlalchemy import column as sa_column
from sqlalchemy import table as sa_table
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import ObjectKind
from sqlalchemy.exc import SAWarning
from sqlalchemy.sql import sqltypes

from .db import describe_source

CATALOG_VERSION = 1

SYSTEM_SCHEMAS = {
    "mssql": {
        "sys",
        "INFORMATION_SCHEMA",
        "guest",
        "db_owner",
        "db_accessadmin",
        "db_securityadmin",
        "db_ddladmin",
        "db_backupoperator",
        "db_datareader",
        "db_datawriter",
        "db_denydatareader",
        "db_denydatawriter",
    },
    "postgresql": {"information_schema", "pg_catalog", "pg_toast"},
}
# Dialects where one database holds many user schemas that are all scanned by default.
ALL_SCHEMAS_DIALECTS = {"mssql", "postgresql"}

_SENSITIVE = re.compile(
    r"passw|pwd|secret|token$|apikey|^ssn$|socialsecurity|nationalid|taxid|^e?mail(address)?$|emailaddr|phone|"
    r"^mobile|^fax|cardnumber|cvv|iban|birth|^dob$|^firstname$|^lastname$|^middlename$|^fullname$|^surname$|"
    r"^addressline|^street|^login(id|name)?$|^username$|ipaddress|salt$|hash$"
)
_ID_EXCEPTIONS = {"loginid", "nationalid", "taxid"}
_DATE_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?")


def is_sensitive(name: str, extra: re.Pattern[str] | None = None) -> bool:
    if extra is not None and extra.search(name):
        return True
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    if n.endswith("id") and n not in _ID_EXCEPTIONS:
        return False  # surrogate keys are not personal data by themselves
    return bool(_SENSITIVE.search(n))


@dataclass
class ScanOptions:
    schemas: list[str] | None = None
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    views: bool = True
    profile: bool = True
    profile_rows: int = 200_000
    enum_max: int = 30
    lookup_max: int = 250
    examples: int = 3
    capture_values: bool = True
    sample_rows: int = 0
    sensitive: str | None = None
    workers: int = 4
    routines: bool = True
    query_timeout: int | None = 120


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def jsonable(v: Any, width: int = 120) -> Any:
    if v is None or isinstance(v, (bool, int)):
        return v
    if isinstance(v, str):
        return v if len(v) <= width else v[: width - 3] + "..."
    if isinstance(v, float):
        return round(v, 6) if math.isfinite(v) else None
    if isinstance(v, Decimal):
        f = float(v)
        return int(f) if f.is_integer() and abs(f) < 2**53 else round(f, 6)
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(v))} bytes>"
    if isinstance(v, uuid.UUID):
        return str(v)
    return jsonable(str(v), width)


def column_kind(coltype: Any, dialect: str) -> str:
    """Classify a reflected type to decide which statistics are safe/meaningful to compute."""
    if isinstance(coltype, (sqltypes.NullType, sqltypes.LargeBinary, sqltypes._Binary)):
        return "skip"
    if isinstance(coltype, sqltypes.Boolean):
        return "bool"
    if isinstance(coltype, sqltypes.Uuid):
        return "uuid"
    if isinstance(coltype, (sqltypes.Integer, sqltypes.Numeric)) or type(coltype).__name__.upper() in (
        "MONEY",
        "SMALLMONEY",
    ):
        return "number"
    if isinstance(coltype, (sqltypes.Date, sqltypes.DateTime, sqltypes.Time)):
        return "temporal"
    if isinstance(coltype, (sqltypes.JSON, sqltypes.ARRAY)):
        return "lob"
    if isinstance(coltype, sqltypes.String):
        # SQL Server TEXT/NTEXT/XML cannot be compared, grouped or DISTINCTed.
        if dialect == "mssql" and isinstance(coltype, sqltypes.Text):
            return "lob"
        return "text"
    return "other"


def _type_str(coltype: Any, dialect: Any) -> str:
    if isinstance(coltype, sqltypes.NullType):
        return "UNKNOWN"
    try:
        return str(coltype.compile(dialect=dialect))
    except Exception:
        return type(coltype).__name__.upper()


# Unquoted identifiers are case-insensitive here, so mixed-case names only need quotes when reserved/illegal.
# Elsewhere (PostgreSQL, Oracle, Snowflake, ...) SQLAlchemy's rules apply: mixed-case names must be quoted.
CASE_INSENSITIVE_IDENTIFIERS = {"mssql", "sqlite", "mysql", "mariadb"}


def _ident(preparer: Any, name: str, dialect: str) -> str:
    if dialect in CASE_INSENSITIVE_IDENTIFIERS:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and name.lower() not in preparer.reserved_words:
            return name
        return str(preparer.quote_identifier(name))
    return str(preparer.quote(name))


def _matches(patterns: list[str], *names: str) -> bool:
    return any(fnmatch.fnmatch(n.lower(), p.lower()) for p in patterns for n in names if n)


def _short_error(e: Exception) -> str:
    return (str(e).strip().splitlines() or [type(e).__name__])[0][:300]


# Reflection results are keyed by (schema, table name); schema is None for the default schema.
TableKey = tuple[str | None, str]


def _multi(
    fn: Callable[..., Any], schema: str | None, names: list[str], kind: ObjectKind
) -> tuple[dict[TableKey, Any], str | None]:
    try:
        with warnings.catch_warnings():
            # Types SQLAlchemy doesn't know (hierarchyid, geography, ...) are resolved later via INFORMATION_SCHEMA.
            warnings.filterwarnings("ignore", message="Did not recognize type", category=SAWarning)
            return dict(fn(schema=schema, filter_names=names, kind=kind)), None
    except NotImplementedError:
        return {}, None
    except Exception as e:  # keep scanning even if one reflection call fails
        return {}, _short_error(e)


# ---------------------------------------------------------------------------
# INFORMATION_SCHEMA fallback for drivers whose SQLAlchemy reflection is missing or broken
# ---------------------------------------------------------------------------
_INT_TYPE = re.compile(r"\bu?(tiny|small|medium|big|huge|long)?int(eger)?\d*\b")
_GENERIC_TYPES: list[tuple[str, Any]] = [
    ("interval", sqltypes.Interval),
    ("bool", sqltypes.Boolean),
    ("timestamp", sqltypes.DateTime),
    ("datetime", sqltypes.DateTime),
    ("date", sqltypes.Date),
    ("time", sqltypes.Time),
    ("uuid", sqltypes.Uuid),
    ("uniqueidentifier", sqltypes.Uuid),
    ("json", sqltypes.JSON),
    ("blob", sqltypes.LargeBinary),
    ("binary", sqltypes.LargeBinary),
    ("bytea", sqltypes.LargeBinary),
    ("dec", sqltypes.Numeric),
    ("numeric", sqltypes.Numeric),
    ("number", sqltypes.Numeric),
    ("money", sqltypes.Numeric),
    ("real", sqltypes.Float),
    ("float", sqltypes.Float),
    ("double", sqltypes.Float),
    ("char", sqltypes.String),
    ("text", sqltypes.Text),
    ("string", sqltypes.String),
    ("clob", sqltypes.Text),
]


def _type_from_name(dialect: Any, type_name: str) -> Any:
    base = re.sub(r"\(.*", "", type_name or "").strip().lower()
    known = getattr(dialect, "ischema_names", {}).get(base)
    if known is not None:
        try:
            return known() if isinstance(known, type) else known
        except Exception:
            pass
    if "[]" in base or base.startswith(("struct", "map", "list", "array", "union")):
        return sqltypes.JSON()
    if _INT_TYPE.search(base):
        return sqltypes.Integer()
    for key, typ in _GENERIC_TYPES:
        if key in base:
            return typ()
    return sqltypes.NullType()


def _is_rows(engine: Engine, sql: str, schema: str) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql), {"s": schema}).all()]


def _is_columns(engine: Engine, schema: str, names: dict[str, str]) -> dict[str, Any]:
    rows = _is_rows(
        engine,
        "SELECT table_name, column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_schema = :s "
        "ORDER BY table_name, ordinal_position",
        schema,
    )
    out: dict[str, Any] = {}
    for table, col, dtype, nullable, default in rows:
        if str(table).lower() in names:
            out.setdefault(names[str(table).lower()], []).append(
                {
                    "name": _normalize(engine, col),
                    "type": _type_from_name(engine.dialect, str(dtype)),
                    "nullable": str(nullable).upper() != "NO",
                    "default": default,
                    "comment": None,
                }
            )
    return out


def _is_primary_keys(engine: Engine, schema: str, names: dict[str, str]) -> dict[str, Any]:
    rows = _is_rows(
        engine,
        "SELECT tc.table_name, kcu.column_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu ON kcu.table_schema = tc.table_schema "
        "AND kcu.table_name = tc.table_name AND kcu.constraint_name = tc.constraint_name "
        "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = :s "
        "ORDER BY tc.table_name, kcu.ordinal_position",
        schema,
    )
    out: dict[str, Any] = {}
    for table, col in rows:
        if str(table).lower() in names:
            out.setdefault(names[str(table).lower()], {"constrained_columns": []})["constrained_columns"].append(
                _normalize(engine, col)
            )
    return out


def _is_foreign_keys(engine: Engine, schema: str, names: dict[str, str]) -> dict[str, Any]:
    rows = _is_rows(
        engine,
        "SELECT kcu.table_name, rc.constraint_name, kcu.column_name, ref.table_schema, "
        "ref.table_name, ref.column_name FROM information_schema.referential_constraints rc "
        "JOIN information_schema.key_column_usage kcu ON kcu.constraint_schema = rc.constraint_schema "
        "AND kcu.constraint_name = rc.constraint_name "
        "JOIN information_schema.key_column_usage ref ON ref.constraint_schema = rc.unique_constraint_schema "
        "AND ref.constraint_name = rc.unique_constraint_name "
        "AND ref.ordinal_position = kcu.position_in_unique_constraint "
        "WHERE kcu.table_schema = :s ORDER BY kcu.table_name, rc.constraint_name, kcu.ordinal_position",
        schema,
    )
    groups: dict[tuple[str, Any], list[tuple[Any, ...]]] = {}
    for table, cname, col, rschema, rtable, rcol in rows:
        if str(table).lower() in names:
            groups.setdefault((names[str(table).lower()], cname), []).append((col, rschema, rtable, rcol))
    out: dict[str, Any] = {}
    for (table, cname), parts in groups.items():
        targets = {(p[1], p[2]) for p in parts}
        if len(targets) != 1 or len({p[0] for p in parts}) != len(parts):
            continue  # ambiguous (e.g. engines that name every primary key alike): leave it to inference
        rschema, rtable = targets.pop()
        out.setdefault(table, []).append(
            {
                "name": cname,
                "constrained_columns": [_normalize(engine, p[0]) for p in parts],
                "referred_schema": _normalize(engine, rschema),
                "referred_table": _normalize(engine, rtable),
                "referred_columns": [_normalize(engine, p[3]) for p in parts],
            }
        )
    return out


def _normalize(engine: Engine, name: Any) -> Any:
    if name is not None and getattr(engine.dialect, "requires_name_normalize", False):
        return engine.dialect.normalize_name(name)
    return name


def _reflect_schema(
    engine: Engine,
    insp: Any,
    schema: str | None,
    opts: ScanOptions,
    errors: list[dict[str, Any]],
    notes: list[str],
    extra_sensitive: re.Pattern[str] | None,
) -> list[dict[str, Any]]:
    dialect = engine.dialect
    preparer = dialect.identifier_preparer
    qualify = schema is not None  # names are schema-qualified whenever a schema was scanned explicitly
    default_schema = insp.default_schema_name

    names = [(n, "table") for n in insp.get_table_names(schema=schema)]
    if opts.views:
        names += [(n, "view") for n in insp.get_view_names(schema=schema)]
        with contextlib.suppress(Exception):  # optional object type; most dialects don't have it
            names += [(n, "materialized view") for n in insp.get_materialized_view_names(schema=schema)]

    def fqn(sch: str | None, name: str) -> str:
        return f"{sch}.{name}" if qualify and sch else name

    selected = [
        (n, k)
        for n, k in names
        if (not opts.include or _matches(opts.include, fqn(schema, n), n))
        and not _matches(opts.exclude, fqn(schema, n), n)
    ]
    if not selected:
        return []
    filt = [n for n, _ in selected]
    lower_names = {n.lower(): n for n in filt}
    info_schema = schema or default_schema

    def reflect(
        fn: Callable[..., Any], kind: ObjectKind, fallback: Callable[..., Any] | None = None
    ) -> dict[TableKey, Any]:
        result, err = _multi(fn, schema, filt, kind)
        if err is None:
            return result
        stage = fn.__name__.removeprefix("get_multi_")
        if fallback is None or not info_schema:
            notes.append(f"{fqn(schema, '*')}: {stage} not available from the driver ({err})")
            return {}
        try:
            result = {(schema, k): v for k, v in fallback(engine, info_schema, lower_names).items()}
            notes.append(f"{fqn(schema, '*')}: {stage} read from INFORMATION_SCHEMA (driver reflection failed: {err})")
            return result
        except Exception as e:
            errors.append({"stage": stage, "schema": schema, "error": err, "fallback_error": _short_error(e)})
            return {}

    cols = reflect(insp.get_multi_columns, ObjectKind.ANY, _is_columns)
    comments = reflect(insp.get_multi_table_comment, ObjectKind.ANY)
    pks = reflect(insp.get_multi_pk_constraint, ObjectKind.TABLE, _is_primary_keys)
    fks = reflect(insp.get_multi_foreign_keys, ObjectKind.TABLE, _is_foreign_keys)
    idxs = reflect(insp.get_multi_indexes, ObjectKind.TABLE)
    uqs = reflect(insp.get_multi_unique_constraints, ObjectKind.TABLE)

    objects = []
    for name, otype in selected:
        key = (schema, name)
        for d in (cols, comments, pks, fks, idxs, uqs):  # some dialects key the default schema as None
            if key not in d and (None, name) in d:
                d[key] = d[(None, name)]
        obj: dict[str, Any] = {
            "name": name,
            "schema": schema,
            "fqn": fqn(schema, name),
            "sql_name": ".".join(_ident(preparer, p, dialect.name) for p in ([schema] if qualify else []) + [name]),
            "type": otype,
            "comment": (comments.get(key) or {}).get("text"),
            "row_count": None,
            "row_count_exact": False,
            "primary_key": list((pks.get(key) or {}).get("constrained_columns") or []),
            "foreign_keys": [],
            "unique": [list(u.get("column_names") or []) for u in uqs.get(key, [])],
            "indexes": [
                {
                    "name": i.get("name"),
                    "columns": [c for c in i.get("column_names") or [] if c],
                    "unique": bool(i.get("unique")),
                }
                for i in idxs.get(key, [])
            ],
            "columns": [],
        }
        for fk in fks.get(key, []):
            ref_schema = fk.get("referred_schema") or (default_schema if qualify else None)
            obj["foreign_keys"].append(
                {
                    "name": fk.get("name"),
                    "columns": list(fk.get("constrained_columns") or []),
                    "ref_table": fqn(ref_schema, fk["referred_table"]),
                    "ref_columns": list(fk.get("referred_columns") or []),
                }
            )
        for c in cols.get(key, []):
            computed = c.get("computed") or {}
            obj["columns"].append(
                {
                    "name": c["name"],
                    "sql_name": _ident(preparer, c["name"], dialect.name),
                    "type": _type_str(c["type"], dialect),
                    "kind": column_kind(c["type"], dialect.name),
                    "nullable": bool(c.get("nullable", True)),
                    "default": jsonable(c.get("default"), 80),
                    "computed": jsonable(computed.get("sqltext"), 300) if computed else None,
                    "identity": bool(c.get("identity")),
                    "comment": c.get("comment"),
                    "sensitive": is_sensitive(c["name"], extra_sensitive),
                }
            )
        if otype in ("view", "materialized view"):
            try:
                definition = insp.get_view_definition(name, schema=schema)
                obj["definition"] = jsonable(definition, 4000) if definition else None
            except Exception:
                obj["definition"] = None
        objects.append(obj)
    return objects


def _resolve_foreign_keys(objects: list[dict[str, Any]]) -> None:
    """Point FKs at scanned objects even when the driver reports the target schema differently (or not at all)."""
    exact = {o["fqn"] for o in objects}
    lower = {o["fqn"].lower(): o["fqn"] for o in objects}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for o in objects:
        by_name.setdefault(o["name"].lower(), []).append(o)
    for o in objects:
        for fk in o["foreign_keys"]:
            ref = fk["ref_table"]
            if ref in exact:
                continue
            if ref.lower() in lower:
                fk["ref_table"] = lower[ref.lower()]
                continue
            cands = by_name.get(ref.rpartition(".")[2].lower(), [])
            same_schema = [x for x in cands if x["schema"] == o["schema"]]
            pick = same_schema if len(same_schema) == 1 else cands
            if len(pick) == 1:
                fk["ref_table"] = pick[0]["fqn"]


def _quoted_full(preparer: Any, obj: dict[str, Any]) -> str:
    parts = ([obj["schema"]] if obj["schema"] else []) + [obj["name"]]
    return ".".join(preparer.quote_identifier(p) for p in parts)


def _row_count(conn: Any, dialect: str, preparer: Any, obj: dict[str, Any]) -> tuple[int | None, bool]:
    if obj["type"] == "view":
        return None, False
    try:
        if dialect == "mssql":
            n = conn.execute(
                text(
                    "SELECT SUM(p.rows) FROM sys.partitions p "
                    "WHERE p.object_id = OBJECT_ID(:n) AND p.index_id IN (0, 1)"
                ),
                {"n": _quoted_full(preparer, obj)},
            ).scalar()
            if n is not None:
                return int(n), False
        elif dialect == "postgresql":
            n = conn.execute(
                text("SELECT c.reltuples::bigint FROM pg_class c WHERE c.oid = to_regclass(:n)"),
                {"n": _quoted_full(preparer, obj)},
            ).scalar()
            if n is not None and n >= 0:
                return int(n), False
    except Exception:
        conn.rollback()
    n = conn.execute(select(func.count()).select_from(sa_table(obj["name"], schema=obj["schema"]))).scalar()
    return int(n or 0), True


def _fix_unknown_types(conn: Any, obj: dict[str, Any], dialect: str, default_schema: str | None) -> None:
    """Types SQLAlchemy doesn't know (hierarchyid, geography, PostGIS, ...) -> real names from INFORMATION_SCHEMA."""
    if dialect in ("sqlite", "oracle") or not any(c["type"] == "UNKNOWN" for c in obj["columns"]):
        return
    dtype = (
        "CASE WHEN data_type = 'USER-DEFINED' THEN udt_name ELSE data_type END"
        if dialect == "postgresql"
        else "data_type"
    )
    try:
        rows = conn.execute(
            text(
                f"SELECT column_name, {dtype} FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t"
            ),
            {"s": obj["schema"] or default_schema, "t": obj["name"]},
        ).all()
        types = {r[0]: str(r[1]).upper() for r in rows}
        for c in obj["columns"]:
            if c["type"] == "UNKNOWN" and c["name"] in types:
                c["type"] = types[c["name"]]
    except Exception:
        conn.rollback()


def _profile(conn: Any, obj: dict[str, Any], opts: ScanOptions) -> None:
    cols = [c for c in obj["columns"] if c["kind"] != "skip"]
    if not cols:
        return
    t = sa_table(obj["name"], *[sa_column(c["name"]) for c in cols], schema=obj["schema"])
    src = select(*[t.c[c["name"]] for c in cols])
    rc = obj.get("row_count")
    limited = rc is None or rc > opts.profile_rows
    if limited:
        src = src.limit(opts.profile_rows)
    s = src.subquery("s")

    specs: list[tuple[dict[str, Any], str, Any]] = []
    for c in cols:
        sc, k, sens = s.c[c["name"]], c["kind"], c["sensitive"]
        # COUNT(col) is invalid for legacy LOBs (SQL Server text/ntext/image); IS NOT NULL works everywhere.
        specs.append((c, "non_null", func.count(case((sc.is_not(None), 1))) if k == "lob" else func.count(sc)))
        if k in ("bool", "number", "temporal", "text"):
            specs.append((c, "distinct", func.count(distinct(sc))))
        if not sens and k in ("number", "temporal", "text"):
            specs.append((c, "min", func.min(sc)))
            specs.append((c, "max", func.max(sc)))
        if not sens and k == "number":
            specs.append((c, "avg", func.avg(cast(sc, Float))))

    results: dict[int, Any] = {}
    try:
        row = conn.execute(select(func.count(), *[e for _, _, e in specs]).select_from(s)).one()
        total = int(row[0])
        results = {i: row[i + 1] for i in range(len(specs))}
    except Exception:
        conn.rollback()
        total = int(conn.execute(select(func.count()).select_from(s)).scalar() or 0)
        for c in cols:  # one query per column so a single exotic type cannot break the whole table
            ids = [i for i, sp in enumerate(specs) if sp[0] is c]
            try:
                row = conn.execute(select(*[specs[i][2] for i in ids]).select_from(s)).one()
                results.update({i: row[j] for j, i in enumerate(ids)})
            except Exception as e:
                conn.rollback()
                c["profile_error"] = str(e).splitlines()[0][:200]

    for i, (c, stat, _) in enumerate(specs):
        if i in results:
            c.setdefault("profile", {})[stat] = jsonable(results[i], 60)
    for c in cols:
        p = c.setdefault("profile", {})
        nn = p.get("non_null")
        if nn is not None and total:
            p["null_pct"] = round(100.0 * (total - nn) / total, 2)
        if c["kind"] == "text":  # lexicographic min/max is only meaningful for date/number-like text
            lo, hi = p.get("min"), p.get("max")
            if not (isinstance(lo, str) and isinstance(hi, str) and _DATE_LIKE.match(lo) and _DATE_LIKE.match(hi)):
                p.pop("min", None)
                p.pop("max", None)

    obj["profile_meta"] = {"rows_profiled": total, "sampled": bool(limited and total >= opts.profile_rows)}

    if not opts.capture_values:
        return
    for c in cols:
        p = c.get("profile") or {}
        nd, nn = p.get("distinct"), p.get("non_null")
        if c["sensitive"] or not nn or "profile_error" in c:
            continue
        sc = s.c[c["name"]]
        # Codes (any type) up to enum_max; text value dictionaries (names in lookup tables) up to lookup_max.
        limit = max(opts.enum_max, opts.lookup_max) if c["kind"] == "text" else opts.enum_max
        try:
            if nd is not None and nd <= limit:
                q = (
                    select(sc, func.count())
                    .where(sc.is_not(None))
                    .group_by(sc)
                    .order_by(func.count().desc())
                    .limit(limit)
                )
                p["values"] = [[jsonable(v, 120), int(n)] for v, n in conn.execute(q).all()]
            elif c["kind"] == "text" and opts.examples:
                q = select(sc).where(sc.is_not(None)).distinct().limit(opts.examples)
                p["examples"] = [jsonable(r[0], 120) for r in conn.execute(q).all()]
        except Exception as e:
            conn.rollback()
            c["profile_error"] = str(e).splitlines()[0][:200]


def _sample_rows(conn: Any, obj: dict[str, Any], n: int) -> list[dict[str, Any]]:
    cols = [c for c in obj["columns"] if c["kind"] not in ("skip", "lob")]
    if not cols or n <= 0:
        return []
    t = sa_table(obj["name"], *[sa_column(c["name"]) for c in cols], schema=obj["schema"])
    rows = conn.execute(select(*[t.c[c["name"]] for c in cols]).limit(n)).all()
    return [
        {c["name"]: ("***" if c["sensitive"] else jsonable(v, 60)) for c, v in zip(cols, r, strict=True)} for r in rows
    ]


def _process(engine: Engine, obj: dict[str, Any], opts: ScanOptions, default_schema: str | None) -> None:
    started = time.time()
    dialect = engine.dialect.name
    with engine.connect() as conn:
        try:
            _fix_unknown_types(conn, obj, dialect, default_schema)
            obj["row_count"], obj["row_count_exact"] = _row_count(
                conn, dialect, engine.dialect.identifier_preparer, obj
            )
            if opts.profile:
                _profile(conn, obj, opts)
            if opts.sample_rows:
                obj["sample_rows"] = _sample_rows(conn, obj, opts.sample_rows)
        except Exception as e:
            conn.rollback()
            obj["error"] = str(e).splitlines()[0][:300]
    obj.setdefault("profile_meta", {})["seconds"] = round(time.time() - started, 2)


def _routines(engine: Engine, schemas: list[str | None]) -> list[dict[str, Any]]:
    if engine.dialect.name != "mssql":
        return []
    sql = text("""
        SELECT s.name, o.name, o.type_desc, CAST(OBJECT_DEFINITION(o.object_id) AS nvarchar(max)),
               CAST(ep.value AS nvarchar(4000))
        FROM sys.objects o
        JOIN sys.schemas s ON s.schema_id = o.schema_id
        LEFT JOIN sys.extended_properties ep
               ON ep.class = 1 AND ep.major_id = o.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
        WHERE o.type IN ('P', 'FN', 'IF', 'TF') AND o.is_ms_shipped = 0
        ORDER BY s.name, o.name""")
    with engine.connect() as conn:
        rows = conn.execute(sql).all()
    wanted = {s for s in schemas if s}
    return [
        {
            "schema": r[0],
            "name": r[1],
            "fqn": f"{r[0]}.{r[1]}",
            "type": r[2].lower().replace("sql_", ""),
            "definition": jsonable(r[3], 4000),
            "comment": r[4],
        }
        for r in rows
        if not wanted or r[0] in wanted
    ]


def _server_version(engine: Engine) -> str | None:
    if engine.dialect.name == "sqlite":
        return sqlite3.sqlite_version
    info = getattr(engine.dialect, "server_version_info", None)
    return ".".join(str(x) for x in info) if info else None


def scan_database(engine: Engine, opts: ScanOptions, log: Callable[[str], None] = _log) -> dict[str, Any]:
    started = time.time()
    dialect = engine.dialect.name
    extra = re.compile(opts.sensitive, re.I) if opts.sensitive else None
    errors: list[dict[str, Any]] = []
    notes: list[str] = []
    with engine.connect():
        pass  # fail fast on bad connection details; also populates server_version_info
    insp = inspect(engine)
    if opts.schemas:
        schemas: list[str | None] = list(opts.schemas)
    elif dialect in ALL_SCHEMAS_DIALECTS:
        system = SYSTEM_SCHEMAS.get(dialect, set())
        schemas = [s for s in insp.get_schema_names() if s not in system and not s.startswith("pg_")]
    elif dialect == "oracle":
        schemas = [insp.default_schema_name]  # every Oracle user is a schema: scan your own unless told otherwise
    else:
        schemas = [None]  # the database/schema named in the connection URL

    objects: list[dict[str, Any]] = []
    for schema in schemas:
        objects += _reflect_schema(engine, insp, schema, opts, errors, notes, extra)
    _resolve_foreign_keys(objects)
    log(f"Reflected {len(objects)} objects from {len(schemas)} schema(s) in {time.time() - started:.1f}s")
    for note in notes:
        log(f"NOTE {note}")

    workers = 1 if dialect == "sqlite" else max(1, opts.workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process, engine, obj, opts, insp.default_schema_name): obj for obj in objects}
        for i, fut in enumerate(as_completed(futures), 1):
            obj = futures[fut]
            fut.result()
            rows = obj.get("row_count")
            log(
                f"[{i}/{len(objects)}] {obj['fqn']}: {rows if rows is not None else '?'} rows, "
                f"{len(obj['columns'])} cols ({obj['profile_meta']['seconds']}s)"
                + (f" ERROR: {obj['error']}" if obj.get("error") else "")
            )

    routines: list[dict[str, Any]] = []
    if opts.routines:
        try:
            routines = _routines(engine, schemas)
        except Exception as e:
            errors.append({"stage": "routines", "error": str(e).splitlines()[0][:300]})

    source = describe_source(engine.url.render_as_string(hide_password=True))
    source["server_version"] = _server_version(engine)
    objects.sort(key=lambda o: o["fqn"].lower())
    return {
        "version": CATALOG_VERSION,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "source": source,
        "options": asdict(opts),
        "objects": objects,
        "routines": routines,
        "errors": errors,
        "notes": notes,
        "duration_s": round(time.time() - started, 1),
    }
