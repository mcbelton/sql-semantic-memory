"""Business knowledge graph (ontology): business entities and named relations mapped onto the schema.

A graph is proposed by an LLM (an API model, GitHub Copilot, or a human) and is only accepted after validation:
every table, column, filter and join must exist in the schema and, when a database connection is available,
filters and joins are executed (with time limits) to record row counts, joined pairs, the cardinality observed in
the data and references that point to no row. Accepted items are merged into <kb>/knowledge_graph.yaml; `sqlmem
build` turns that file into graph nodes, search chunks, Copilot context and docs.

Entities may have composite keys. Relations join through declared or inferred foreign keys, through explicit join
columns ("on") when the schema declares none, or polymorphically: one column that references different tables
depending on a type column, expanded into one conditional relation per target table.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .db import QueryTimeout, check_readonly, run_select

if TYPE_CHECKING:  # pragma: no cover
    from .model import Relationship, SemanticModel, Table

KINDS = ("core", "event", "reference", "role")
DEFAULT_MAX_CHARS = 60_000

SYSTEM_PROMPT = """You are a senior data architect. Build a business knowledge graph (ontology) of a relational \
database: the real-world things and events people ask questions about and the named relationships between them, \
mapped exactly onto the schema you are given.

Rules
- Use ONLY table and column names that appear in the schema, spelled exactly as given. In "filter", "condition" \
and "on" SQL write identifiers exactly as listed, keeping any quotes.
- Entity = one business concept stored in ONE table ("table"). A subtype or role of a concept (e.g. resellers among \
customers) uses the same table plus "filter": a SQL condition on that table's own columns (unqualified column \
names, values exactly as shown), and names its parent in "is_a". A concept kept in its own 1:1 table (e.g. sales \
people extending employees) gets that table and "is_a" the broader entity.
- Do not make entities of technical tables (logs, versions, errors) or of pure link tables; link tables appear in \
the "via" list of relations.
- kind: "core" (master data: customers, products, employees), "event" (transactions: orders, shipments, work \
orders), "reference" (lookups: categories, territories, currencies, statuses), "role" (subtype/role of another \
entity).
- key: list of the column(s) that identify one instance - several columns for a composite key (e.g. \
["ProductID", "LocationID"]). label: column(s) that name an instance for people (e.g. Name), [] if none. \
attributes: the most useful descriptive or measure columns (at most 8).
- Relation = subject --predicate--> object between two entities (by entity name). predicate: short \
lower_snake_case verb phrase read from subject to object (places, contains, supplies, belongs_to, works_in, \
located_in, manages, assigned_to, part_of). For links inside one table phrase it from the referencing row \
(reports_to, part_of).
- via: intermediate tables needed to join subject to object, in order ([] when they join directly). When a join \
could use more than one column - e.g. an order's bill-to vs ship-to address, or a bill of materials whose assembly \
and component columns both point to the product table - add "Table.Column" to via to name the column to use (for a \
link table: its column that points to the SUBJECT).
- on: only when the subject and object tables are linked by columns the schema does NOT declare as a foreign key \
(no "->"): "SubjectTable.column = ObjectTable.column" (several columns joined with AND), with via []. Never link \
two tables through a third table they merely both reference (e.g. two event tables through the product they \
share) - that pairs unrelated rows.
- polymorphic: when one column holds ids of different tables depending on a type column (e.g. ReferenceOrderID is \
a sales, purchase or work order id depending on TransactionType), write ONE relation without "object" and with \
"polymorphic": {"column": "ReferenceOrderID", "type_column": "TransactionType", "targets": [{"type": "S", \
"object": "Sales Order"}, {"type": "P", "object": "Purchase Order"}]} - type values exactly as stored. It becomes \
one relation per target, joined on the target entity's key.
- condition: optional extra SQL condition with table-qualified columns (e.g. History.EndDate IS NULL for current \
assignments), else null.
- cardinality: "1:1", "1:N" (one subject, many objects), "N:1" or "M:N".
- Cover every important business concept and every meaningful relationship, including ones that cross domains.
- Prefer names people would say over table names. Do not invent facts the schema, values and descriptions do not \
support.

Respond with ONE JSON object only:
{"entities": [{"name": "", "kind": "", "description": "", "synonyms": [], "table": "", "key": [], "label": [], \
"filter": null, "is_a": null, "attributes": []}],
 "relations": [{"subject": "", "predicate": "", "object": "", "cardinality": "", "via": [], "on": null, \
"polymorphic": null, "condition": null, "description": ""}]}"""


# ------------------------------------------------------------------------------------------------- prompts
@dataclass
class Task:
    part: int
    parts: int
    tables: list[str]


def _short(s: Any, n: int) -> str:
    text = re.sub(r"\s+", " ", str(s or "")).strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def _lit(v: Any) -> str:
    if isinstance(v, str):
        short = _short(v, 60)
        return "'" + short.replace("'", "''") + "'"
    return str(v)


def _type_short(t: str | None) -> str:
    return re.sub(r"\(.*", "", t or "?").strip().lower()


def _column_hint(c: Any) -> str:
    p = c.profile or {}
    if c.values:
        return "codes " + ", ".join(f"{k}={v}" for k, v in list(c.values.items())[:12])
    if c.sensitive:
        return ""
    vals, nd = p.get("values") or [], p.get("distinct")
    if vals and isinstance(nd, int) and nd <= 12 and not c.pk and not c.fk:
        return "values " + ", ".join(_lit(v) for v, _ in vals[:12])
    lo, hi = p.get("min"), p.get("max")
    if isinstance(lo, str) and isinstance(hi, str):
        return f"{lo[:10]} .. {hi[:10]}"
    if c.kind == "text" and not c.pk and not c.fk:
        examples = [v for v, _ in vals[:3]] or (p.get("examples") or [])[:3]
        if examples:
            return "e.g. " + ", ".join(_lit(v) for v in examples)
    return ""


def table_digest(model: SemanticModel, t: Table) -> str:
    rows = f"{t.row_count:,} rows" if isinstance(t.row_count, int) else "? rows"
    sql = f", SQL name {t.sql_name}" if t.sql_name != t.fqn else ""
    lines = [f"### {t.fqn} ({t.type}, {rows}{', domain ' + t.domain if t.domain else ''}{sql})"]
    if t.description:
        lines.append(_short(t.description, 300))
    for c in t.columns.values():
        if c.housekeeping:
            continue
        flags = (" PK" if c.pk else "") + (f" -> {c.fk}" if c.fk else "")
        extra = [x for x in (_short(c.description, 100), _column_hint(c)) if x]
        lines.append(f"- {c.sql_name} {_type_short(c.type)}{flags}" + (": " + "; ".join(extra) if extra else ""))
    for r in model.relationships:
        if r.from_table == t.fqn and (r.condition or len(r.from_columns) > 1 or r.source == "curated"):
            lines.append(f"- join: {r.label()}" + (f" when {r.condition}" if r.condition else ""))
    return "\n".join(lines)


def build_tasks(model: SemanticModel, max_chars: int = DEFAULT_MAX_CHARS) -> list[Task]:
    """Split the schema into prompt-sized parts, keeping domains together where possible."""
    tables = sorted(model.visible_tables(), key=lambda t: ((t.domain or "").lower(), t.fqn.lower()))
    size = {t.fqn: len(table_digest(model, t)) + 1 for t in tables}
    groups: dict[str, list[str]] = {}
    for t in tables:
        groups.setdefault(t.domain or "", []).append(t.fqn)
    chunks: list[list[str]] = []
    cur: list[str] = []
    used = 0
    for names in groups.values():
        if cur and used + sum(size[n] for n in names) > max_chars:
            chunks.append(cur)
            cur, used = [], 0
        for n in names:
            if cur and used + size[n] > max_chars:
                chunks.append(cur)
                cur, used = [], 0
            cur.append(n)
            used += size[n]
    if cur:
        chunks.append(cur)
    return [Task(i + 1, len(chunks), c) for i, c in enumerate(chunks)]


def task_prompt(model: SemanticModel, task: Task, known: dict[str, Any] | None = None) -> str:
    out = [f"# Database {model.name} ({model.dialect})"]
    if model.description:
        out.append(_short(model.description, 1500))
    if model.dialect_notes:
        out += ["", "## SQL notes"] + [f"- {n}" for n in model.dialect_notes]
    if model.glossary:
        out += ["", "## Business glossary"]
        out += [f"- {g['term']}: {_short(g.get('definition'), 200)}" for g in model.glossary[:40]]
    known_entities = (known or {}).get("entities") or []
    if known_entities:
        out += ["", "## Entities already defined (reuse these exact names in relations; do not define them again)"]
        out += [
            f"- {e['name']} = {e['table']}" + (f" WHERE {e['filter']}" if e.get("filter") else "")
            for e in known_entities
        ]
    inside = set(task.tables)
    boundary = sorted(
        {
            b
            for r in model.relationships
            for a, b in ((r.from_table, r.to_table), (r.to_table, r.from_table))
            if a in inside and b not in inside and not model.tables[b].hidden
        }
    )
    out += ["", "## Schema" + (f" (part {task.part} of {task.parts})" if task.parts > 1 else "")]
    out += [table_digest(model, model.tables[n]) for n in task.tables]
    if boundary:
        out += ["", "## Related tables described in other parts (usable as relation endpoints or in via)"]
        out += [f"- {b}: {_short(model.tables[b].description, 120)}" for b in boundary]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------- normalize
_CARD = {
    "1:1": "1:1",
    "one-to-one": "1:1",
    "1:n": "1:N",
    "1:m": "1:N",
    "1:*": "1:N",
    "one-to-many": "1:N",
    "n:1": "N:1",
    "m:1": "N:1",
    "*:1": "N:1",
    "many-to-one": "N:1",
    "m:n": "M:N",
    "n:m": "M:N",
    "n:n": "M:N",
    "m:m": "M:N",
    "*:*": "M:N",
    "many-to-many": "M:N",
}


def _s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _opt(v: Any) -> str | None:
    s = _s(v)
    return None if s.lower() in ("", "null", "none") else s


def _list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if x is not None and str(x).strip()]
    return [str(v).strip()]


def _card(v: Any) -> str | None:
    c = _opt(v)
    return _CARD.get(re.sub(r"\s+", "", c).lower()) if c else None


def _predicate(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _s(v).lower()).strip("_") or "related_to"


def _on_text(v: Any) -> str | None:
    if isinstance(v, (list, tuple)):
        return " AND ".join(_s(x) for x in v if _s(x)) or None
    return _opt(v)


def _poly(v: Any) -> dict[str, Any] | None:
    """Polymorphic spec: the input shorthand (with targets) or the metadata of one expanded branch (with type)."""
    if not isinstance(v, dict):
        return None
    targets = v.get("targets")
    if isinstance(targets, dict):  # {"S": "Sales Order", "P": "Purchase Order"}
        targets = [{"type": k, "object": x} for k, x in targets.items()]
    out: dict[str, Any] = {
        "column": _list(v.get("column") or v.get("columns")),
        "type_column": _opt(v.get("type_column") or v.get("discriminator")),
        "targets": [],
        "type": v.get("type"),
    }
    for t in targets if isinstance(targets, list) else []:
        if isinstance(t, dict):
            out["targets"].append(
                {
                    "type": t.get("type", t.get("value")),
                    "object": _s(t.get("object") or t.get("entity")),
                    "predicate": _opt(t.get("predicate")),
                    "cardinality": _card(t.get("cardinality")),
                    "description": _s(t.get("description")),
                }
            )
    return out


def normalize(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("The knowledge graph must be a JSON object with 'entities' and 'relations' lists")
    entities, relations = raw.get("entities") or [], raw.get("relations") or []
    if not isinstance(entities, list) or not isinstance(relations, list):
        raise ValueError("'entities' and 'relations' must be lists")
    out: dict[str, list[dict[str, Any]]] = {"entities": [], "relations": []}
    for e in entities:
        if isinstance(e, dict):
            out["entities"].append(
                {
                    "name": _s(e.get("name")),
                    "kind": _s(e.get("kind")).lower() or None,
                    "description": _s(e.get("description")),
                    "synonyms": _list(e.get("synonyms")),
                    "table": _s(e.get("table")),
                    "key": _list(e.get("key")),
                    "label": _list(e.get("label")),
                    "filter": _opt(e.get("filter")),
                    "is_a": _opt(e.get("is_a")),
                    "attributes": _list(e.get("attributes")),
                    "rows": e["rows"] if isinstance(e.get("rows"), int) else None,
                }
            )
    for r in relations:
        if isinstance(r, dict):
            out["relations"].append(
                {
                    "subject": _s(r.get("subject")),
                    "predicate": _predicate(r.get("predicate")),
                    "object": _s(r.get("object")),
                    "cardinality": _card(r.get("cardinality")),
                    "via": _list(r.get("via")),
                    "on": _on_text(r.get("on")),
                    "polymorphic": _poly(r.get("polymorphic")),
                    "condition": _opt(r.get("condition")),
                    "description": _s(r.get("description")),
                    "verified": r["verified"] if isinstance(r.get("verified"), dict) else None,
                }
            )
    return out


# ------------------------------------------------------------------------------------------------- joins
@dataclass
class JoinStep:
    table: str
    alias: str
    on: str = ""


class PlanError(ValueError):
    """No acceptable join between two tables (the message says how to fix it)."""


def _col(t: Table, name: str | None) -> str | None:
    if not name:
        return None
    name = re.sub(r'[\[\]"`]', "", str(name)).strip()
    if "." in name:
        prefix, _, name = name.rpartition(".")
        if prefix.lower() not in (t.fqn.lower(), t.name.lower(), t.short.lower()):
            return None
    if name in t.columns:
        return name
    return next((c for c in t.columns if c.lower() == name.lower()), None)


def _csql(t: Table, col: str) -> str:
    return t.columns[col].sql_name if col in t.columns else col


def _alias_names(model: SemanticModel, text: str, mapping: dict[str, str]) -> str:
    """Rewrite table-qualified column references (Table.Col) to alias-qualified ones (alias.Col)."""
    names = []
    for fqn, alias in mapping.items():
        t = model.tables[fqn]
        for n in {t.sql_name, t.fqn, t.name}:
            names.append((n, alias))
    for n, alias in sorted(names, key=lambda x: -len(x[0])):
        text = re.sub(r"(?<![\w.\]\"`])" + re.escape(n) + r"\.", alias + ".", text, flags=re.IGNORECASE)
    return text


def _connects(r: Relationship, a: str, b: str) -> bool:
    return r.from_table == r.to_table == a if a == b else {r.from_table, r.to_table} == {a, b}


def _rank(r: Relationship) -> tuple[bool, int, str, str]:
    return (
        bool(r.condition),
        {"declared": 0, "curated": 1, "inferred": 2}.get(r.source, 3),
        ",".join(r.from_columns),
        r.from_table,
    )


def _on(model: SemanticModel, r: Relationship, a_alias: str, a_table: str, b_alias: str) -> str:
    # The referencing (FK) side gets its own alias; for self-references the earlier element is the referencing row.
    f_alias, t_alias = (a_alias, b_alias) if r.from_table == a_table else (b_alias, a_alias)
    ft, tt = model.tables[r.from_table], model.tables[r.to_table]
    parts = [
        f"{f_alias}.{_csql(ft, x)} = {t_alias}.{_csql(tt, y)}"
        for x, y in zip(r.from_columns, r.to_columns, strict=True)
    ]
    if r.condition:
        mapping = (
            {r.from_table: f_alias} if r.from_table == r.to_table else {r.from_table: f_alias, r.to_table: t_alias}
        )
        parts.append("(" + _alias_names(model, r.condition, mapping) + ")")
    return " AND ".join(parts)


def parse_via(model: SemanticModel, item: str) -> tuple[str, str | None] | None:
    """'Table' or 'Table.Column' (Column = link-table column pointing to the previous element)."""
    t = model.resolve(item)
    if t is not None:
        return t.fqn, None
    prefix, _, col = item.rpartition(".")
    t = model.resolve(prefix) if prefix else None
    if t is not None and _col(t, col):
        return t.fqn, _col(t, col)
    return None


def _unique(t: Table, cols: list[str]) -> bool:
    """True if `cols` contain the primary key or a unique constraint/index of `t` (one row per value)."""
    cs = set(cols)
    candidates = [
        t.primary_key,
        *getattr(t, "unique", []),
        *[i.get("columns") or [] for i in t.indexes if i.get("unique")],
    ]
    return any(c and set(c) <= cs for c in candidates)


def hop_kind(model: SemanticModel, r: Relationship, cur: str) -> str:
    """Moving from table `cur` along `r`: '1:1', 'N:1' (to the referenced row) or '1:N' (to referencing rows)."""
    if _unique(model.tables[r.from_table], r.from_columns):
        return "1:1"
    return "N:1" if cur == r.from_table else "1:N"


def _fan_out(model: SemanticModel, hops: list[tuple[str, Relationship]]) -> str | None:
    """Table where a path turns from many-to-one to one-to-many: rows are then paired only through it."""
    seen_up = False
    for cur, r in hops:
        kind = hop_kind(model, r, cur)
        if kind == "N:1":
            seen_up = True
        elif kind == "1:N" and seen_up:
            return cur
    return None


def parse_on(model: SemanticModel, subject: str, obj: str, text: str) -> tuple[Relationship, str]:
    """Explicit join columns 'Subject.col = Object.col [AND ...]' -> (link, normalized text)."""
    from .model import Relationship

    st, ot = model.tables[subject], model.tables[obj]
    fcols: list[str] = []
    tcols: list[str] = []
    for item in [p for p in re.split(r"\s+AND\s+", text, flags=re.IGNORECASE) if p.strip()]:
        m = re.fullmatch(r"\s*\(?\s*([^=()]+?)\s*=\s*([^=()]+?)\s*\)?\s*", item)
        if not m:
            raise ValueError(f"on: '{item.strip()}' is not of the form {subject}.column = {obj}.column")
        left, right = m.group(1), m.group(2)
        a, b = _col(st, left), _col(ot, right)
        if subject != obj and not (a and b) and _col(st, right) and _col(ot, left):
            a, b = _col(st, right), _col(ot, left)
        if not (a and b):
            raise ValueError(f"on: '{item.strip()}' must compare a column of {subject} with a column of {obj}")
        fcols.append(a)
        tcols.append(b)
    if not fcols:
        raise ValueError("on is empty")
    norm = " AND ".join(f"{st.fqn}.{a} = {ot.fqn}.{b}" for a, b in zip(fcols, tcols, strict=True))
    return Relationship(subject, fcols, obj, tcols, "kg"), norm


def plan_relation(
    model: SemanticModel,
    subject: str,
    obj: str,
    via: list[tuple[str, str | None]],
    max_hops: int = 4,
    notes: list[str] | None = None,
    link: Relationship | None = None,
) -> list[JoinStep]:
    """Join steps from the subject table (alias s) through via tables (v1, v2, ...) to the object table (alias o).

    A via item with a column pins which column a link uses: on a link table, the column pointing to the previous
    element; on the subject/object table itself, the column of a direct link (e.g. ShipToAddressID vs BillTo).
    `link` is an explicit subject->object join (from "on"). Tables the planner adds itself must not turn from
    many-to-one to one-to-many (that pairs rows through a shared table). Raises PlanError; advice goes to `notes`."""
    if link is not None:
        return [JoinStep(subject, "s"), JoinStep(obj, "o", _on(model, link, "s", subject, "o"))]
    s_pin = o_pin = None
    middle: list[tuple[str, str | None]] = []
    for table, pin in via:
        if pin and table == subject and s_pin is None and not middle:
            s_pin = pin
        elif pin and table == obj and table != subject and o_pin is None:
            o_pin = pin
        else:
            middle.append((table, pin))
    chain = [(subject, s_pin), *middle, (obj, o_pin)]
    names = ["s", *[f"v{i}" for i in range(1, len(chain) - 1)], "o"]
    steps = [JoinStep(subject, "s")]
    rels = [r for r in model.relationships if r.source != "kg"]  # graph links never justify themselves
    used: set[int] = set()
    hops: list[tuple[str, Relationship]] = []
    extra = 0
    for i in range(1, len(chain)):
        (a, a_pin), (b, b_pin) = chain[i - 1], chain[i]
        a_alias, b_alias = names[i - 1], names[i]
        direct = [r for r in rels if id(r) not in used and _connects(r, a, b)]
        pinned = False
        if a != b:
            for table, pin in ((a, a_pin), (b, b_pin)):
                if pin:
                    hit = [r for r in direct if pin in (r.from_columns if r.from_table == table else r.to_columns)]
                    if hit:
                        direct, pinned = hit, True
        if direct:
            ranked = sorted(direct, key=_rank)
            r = ranked[0]
            options = list(dict.fromkeys(",".join(x.from_columns) for x in ranked if not x.condition))
            if notes is not None and not pinned and len(options) > 1:
                notes.append(
                    f"{a} and {b} are linked by several columns ({', '.join(options)}); used "
                    f'{",".join(r.from_columns)} - to use another one add "{r.from_table}.<column>" to via'
                )
            used.add(id(r))
            hops.append((a, r))
            steps.append(JoinStep(b, b_alias, _on(model, r, a_alias, a, b_alias)))
            continue
        if a == b:
            raise PlanError(f"{a} has no column that references its own rows - give one with on")
        path = model.join_path(a, b, max_hops=max_hops, skip_sources=("kg",))
        if not path:
            raise PlanError(
                f"no join path between {a} and {b} - if a column links them without a declared foreign "
                "key, give it with on"
            )
        auto: list[tuple[str, Relationship]] = []
        cur = a
        for r in path:
            auto.append((cur, r))
            cur = r.to_table if r.from_table == cur else r.from_table
        pivot = _fan_out(model, auto)
        if pivot:
            route = " -> ".join([a] + [r.to_table if r.from_table == c else r.from_table for c, r in auto])
            raise PlanError(
                f"{a} and {b} are only connected through {pivot} ({route}), which pairs rows that merely share the "
                f"same {pivot} row. If {a} references {b} through a column that is not a declared foreign key, give "
                f'the join with on ("{a}.<column> = {b}.<key column>"); if a type column decides which table that '
                "column references, use polymorphic"
            )
        cur_t, cur_a = a, a_alias
        for j, r in enumerate(path):
            nxt_t = r.to_table if r.from_table == cur_t else r.from_table
            if j == len(path) - 1:
                nxt_a = b_alias
            else:
                extra += 1
                nxt_a = f"j{extra}"
            used.add(id(r))
            hops.append((cur_t, r))
            steps.append(JoinStep(nxt_t, nxt_a, _on(model, r, cur_a, cur_t, nxt_a)))
            cur_t, cur_a = nxt_t, nxt_a
    pivot = _fan_out(model, hops)
    if pivot and notes is not None:
        notes.append(
            f"the join passes through {pivot} from both sides (many-to-one, then one-to-many), so rows are "
            f"paired only because they share a {pivot} row - make sure that is intended"
        )
    # Stable aliases whether intermediates were given in via or inserted by the planner: s, v1..vn (join order), o.
    rename = {st.alias: f"v{k}" for k, st in enumerate(steps[1:-1], 1) if st.alias != f"v{k}"}
    if rename:
        pattern = re.compile(r"(?<![\w.])(" + "|".join(map(re.escape, rename)) + r")\.")
        for st in steps:
            st.alias = rename.get(st.alias, st.alias)
            st.on = pattern.sub(lambda m: rename[m.group(1)] + ".", st.on)
    return steps


def _source(model: SemanticModel, table: str, flt: str | None) -> str:
    t = model.tables[table]
    return f"(SELECT * FROM {t.sql_name} WHERE {flt})" if flt else t.sql_name


def from_clause(model: SemanticModel, steps: list[JoinStep], filters: dict[str, str | None]) -> str:
    out = []
    for i, st in enumerate(steps):
        src = _source(model, st.table, filters.get(st.alias))
        out.append(f"FROM {src} {st.alias}" if i == 0 else f"JOIN {src} {st.alias} ON {st.on}")
    return " ".join(out)


# ------------------------------------------------------------------------------------------------- validate
@dataclass
class Report:
    entities: int = 0
    relations: int = 0
    unchanged: int = 0
    dropped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    verified: bool = False
    unverified: int = 0

    def add(self, other: Report) -> None:
        self.entities += other.entities
        self.relations += other.relations
        self.unchanged += other.unchanged
        self.dropped += other.dropped
        self.warnings += other.warnings
        self.verified = self.verified or other.verified
        self.unverified += other.unverified

    def text(self, limit: int = 80) -> str:
        head = f"Accepted {self.entities} entities and {self.relations} relations"
        if self.unchanged:
            head += f"; kept {self.unchanged} existing definitions (use replace to overwrite)"
        head += (
            " - verified against the data."
            if self.verified
            else " - checked against the schema only (connect a database to verify filters and joins)."
        )
        lines = [head]
        if self.unverified:
            lines.append(
                f"{self.unverified} item(s) were accepted without data checks because of the time limit - "
                "verify them later with `sqlmem graph --check --verify-timeout 300`."
            )
        if self.dropped:
            lines += [f"Rejected {len(self.dropped)} (fix and resubmit):"] + [f"- {d}" for d in self.dropped[:limit]]
        if self.warnings:
            lines += [f"Warnings ({len(self.warnings)}):"] + [f"- {w}" for w in self.warnings[:limit]]
        return "\n".join(lines)


class _Checker:
    """Runs verification queries with a per-query time limit and an overall time budget.

    The budget is measured with perf_counter: time.monotonic ticks only every ~16 ms on Windows before Python 3.13.
    """

    def __init__(self, engine: Any, timeout: float | None, budget: float | None):
        self.engine = engine
        self.timeout = timeout
        self.deadline = time.perf_counter() + budget if budget else None

    @property
    def active(self) -> bool:
        return self.engine is not None and (self.deadline is None or time.perf_counter() < self.deadline)

    def scalar(self, sql: str) -> Any:
        limit = self.timeout
        if self.deadline is not None:
            left = self.deadline - time.perf_counter()
            if left <= 0:
                raise QueryTimeout("the time budget for data checks is used up")
            limit = min(limit, left) if limit else left
        rows = run_select(self.engine, sql, 1, timeout=limit)[1]
        return rows[0][0] if rows else None


def _err(e: Exception) -> str:
    text = str(getattr(e, "orig", None) or e).strip()
    return (text.splitlines() or [type(e).__name__])[0][:300]


def _sides(card: str) -> tuple[bool, bool]:
    a, _, b = card.partition(":")
    return a != "1", b != "1"


def _observed(objects_per_subject_many: bool, subjects_per_object_many: bool) -> str:
    return {(False, False): "1:1", (False, True): "1:N", (True, False): "N:1", (True, True): "M:N"}[
        (subjects_per_object_many, objects_per_subject_many)
    ]


def _verify_relation(
    chk: _Checker,
    model: SemanticModel,
    from_sql: str,
    where: str,
    cond: str | None,
    s: dict[str, Any],
    o: dict[str, Any],
    link: Relationship | None,
) -> tuple[dict[str, Any] | None, list[str], bool]:
    """(verified info or None when not verified in time, problems, fatal)."""
    try:
        pairs = int(chk.scalar(f"SELECT COUNT(*) {from_sql}{where}") or 0)
    except QueryTimeout as e:
        return None, [f"not verified: {e}"], False
    except Exception as e:
        return None, [f"the join failed on the database: {_err(e)}"], True
    info: dict[str, Any] = {"pairs": pairs}
    problems: list[str] = []
    if pairs == 0:
        problems.append("the join returns no rows")
    sk, ok = s.get("key") or [], o.get("key") or []
    if pairs and sk and ok:
        st, ot = model.tables[s["table"]], model.tables[o["table"]]
        cols = [f"s.{_csql(st, k)} AS a{i}" for i, k in enumerate(sk)]
        cols += [f"o.{_csql(ot, k)} AS b{i}" for i, k in enumerate(ok)]
        distinct_pairs = f"SELECT DISTINCT {', '.join(cols)} {from_sql}{where}"
        ga = ", ".join(f"a{i}" for i in range(len(sk)))
        gb = ", ".join(f"b{i}" for i in range(len(ok)))
        try:
            per_s = chk.scalar(
                f"SELECT MAX(n) FROM (SELECT {ga}, COUNT(*) AS n FROM ({distinct_pairs}) d GROUP BY {ga}) x"
            )
            per_o = chk.scalar(
                f"SELECT MAX(n) FROM (SELECT {gb}, COUNT(*) AS n FROM ({distinct_pairs}) d GROUP BY {gb}) x"
            )
            info["cardinality"] = _observed(int(per_s or 0) > 1, int(per_o or 0) > 1)
        except QueryTimeout as e:
            problems.append(f"cardinality not measured: {e}")
        except Exception as e:
            problems.append(f"could not measure cardinality: {_err(e)}")
    # References that point to no row: only meaningful for explicit links (no foreign key enforces them) into an
    # unfiltered object, with a condition that only restricts the subject (e.g. the polymorphic type column).
    if link is not None and not o.get("filter") and not (cond and re.search(r"(?<![\w.])(?:o|v\d+)\.", cond)):
        st, ot = model.tables[link.from_table], model.tables[link.to_table]
        match = " AND ".join(
            f"o.{_csql(ot, b)} = s.{_csql(st, a)}" for a, b in zip(link.from_columns, link.to_columns, strict=True)
        )
        present = " AND ".join(f"s.{_csql(st, a)} IS NOT NULL" for a in link.from_columns)
        sql = (
            f"SELECT COUNT(*) FROM {_source(model, s['table'], s.get('filter'))} s WHERE {present}"
            + (f" AND ({cond})" if cond else "")
            + f" AND NOT EXISTS (SELECT 1 FROM {ot.sql_name} o WHERE {match})"
        )
        try:
            info["unmatched"] = int(chk.scalar(sql) or 0)
            if info["unmatched"]:
                problems.append(f"{info['unmatched']:,} {s['name']} rows reference a {o['name']} that does not exist")
        except QueryTimeout as e:
            problems.append(f"references to missing rows not counted: {e}")
        except Exception as e:
            problems.append(f"could not count references to missing rows: {_err(e)}")
    return info, problems, False


def _resolve_key(t: Table, given: list[str], label: str, rep: Report) -> list[str]:
    cols = [_col(t, k) for k in given]
    bad = [k for k, c in zip(given, cols, strict=True) if not c]
    if bad:
        pk = ", ".join(t.primary_key) or "none"
        rep.warnings.append(f"{label}: key column(s) {', '.join(bad)} not in {t.fqn} - using the primary key ({pk})")
        return list(t.primary_key)
    return list(dict.fromkeys(c for c in cols if c)) or list(t.primary_key)


def _match_value(v: Any, values: list[Any]) -> Any:
    for x in values:
        if x == v:
            return x
    return next((x for x in values if str(x).strip() == str(v).strip()), None)


def _sql_literal(col: Any, v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    if col.kind == "number" and re.fullmatch(r"-?\d+(\.\d+)?", str(v).strip()):
        return str(v).strip()
    return "'" + str(v).replace("'", "''") + "'"


def _expand_polymorphic(model: SemanticModel, r: dict[str, Any], find: Any, rep: Report) -> list[dict[str, Any]]:
    """One relation per target: subject.column = target key, restricted to the target's type value(s)."""
    poly = r["polymorphic"]
    label = f"polymorphic relation '{r['subject']} {r['predicate']}'"
    s = find(r["subject"])
    if s is None:
        rep.dropped.append(f"{label}: unknown entity '{r['subject']}'")
        return []
    st = model.tables[s["table"]]
    cols = [_col(st, c) for c in poly["column"]]
    if not cols or not all(cols):
        rep.dropped.append(f"{label}: column(s) {', '.join(poly['column']) or '(none)'} not in {st.fqn}")
        return []
    tcol = _col(st, poly["type_column"])
    if tcol is None:
        rep.dropped.append(f"{label}: type_column {poly['type_column'] or '(none)'} not in {st.fqn}")
        return []
    tc = st.columns[tcol]
    observed = [] if tc.sensitive else list(tc.profile.get("values") or [])
    values = [v for v, _ in observed]
    groups: dict[str, dict[str, Any]] = {}
    for tgt in poly["targets"]:
        if not tgt["object"] or tgt["type"] in (None, "", []):
            rep.dropped.append(f"{label}: every target needs a type value and an object")
            continue
        g = groups.setdefault(tgt["object"].lower(), {**tgt, "types": []})
        for v in tgt["type"] if isinstance(tgt["type"], list) else [tgt["type"]]:
            hit = _match_value(v, values)
            if values and hit is None:
                rep.warnings.append(
                    f"{label}: {tcol} value {v!r} does not occur in the data "
                    f"(values: {', '.join(repr(x) for x in values[:12])})"
                )
            g["types"].append(v if hit is None else hit)
    out = []
    for g in groups.values():
        lits = [_sql_literal(tc, v) for v in g["types"]]
        cond = f"{st.sql_name}.{tc.sql_name} " + (f"= {lits[0]}" if len(lits) == 1 else f"IN ({', '.join(lits)})")
        out.append(
            {
                "subject": r["subject"],
                "predicate": _predicate(g["predicate"]) if g["predicate"] else r["predicate"],
                "object": g["object"],
                "cardinality": g["cardinality"] or r["cardinality"],
                "via": [],
                "on": None,
                "condition": f"({r['condition']}) AND {cond}" if r["condition"] else cond,
                "description": g["description"] or r["description"],
                "verified": None,
                "polymorphic": {
                    "column": cols,
                    "type_column": tcol,
                    "targets": [],
                    "type": g["types"][0] if len(g["types"]) == 1 else g["types"],
                },
            }
        )
    mapped = {str(v).strip() for g in groups.values() for v in g["types"]}
    missing = [(v, n) for v, n in observed if str(v).strip() not in mapped]
    if out and missing:
        rep.warnings.append(
            f"{label}: {tcol} values without a target: " + ", ".join(f"{v!r} ({n:,} rows)" for v, n in missing[:12])
        )
    return out


def validate_graph(
    model: SemanticModel,
    raw: Any,
    engine: Any = None,
    known: dict[str, Any] | None = None,
    replace: bool = False,
    timeout: float | None = None,
    budget: float | None = None,
) -> tuple[dict[str, Any], Report]:
    """Check a proposed graph against the schema (and data when `engine` is given).

    `known` is an already accepted graph whose entities relations may reference; its items are not re-checked and
    are only overridden when `replace` is set. Data checks stop each query after `timeout` seconds and stop
    checking altogether after `budget` seconds (items are then accepted unverified). Returns the accepted new
    items and a report."""
    data = normalize(raw)
    rep = Report(verified=engine is not None)
    chk = _Checker(engine, timeout, budget)
    known = known or {"entities": [], "relations": []}
    by_name: dict[str, dict[str, Any]] = {e["name"].lower(): e for e in known.get("entities") or []}
    known_rel = {(r["subject"].lower(), r["predicate"], r["object"].lower()) for r in known.get("relations") or []}
    entities: list[dict[str, Any]] = []

    for e in data["entities"]:
        label = f"entity '{e['name'] or '?'}'"
        if not e["name"]:
            rep.dropped.append("an entity without a name")
            continue
        low = e["name"].lower()
        if any(x["name"].lower() == low for x in entities):
            rep.dropped.append(f"{label}: defined twice")
            continue
        if low in by_name and not replace:
            rep.unchanged += 1
            continue
        t = model.resolve(e["table"]) if e["table"] else None
        if t is None:
            hint = model.suggest(e["table"]) if e["table"] else []
            rep.dropped.append(
                f"{label}: unknown table '{e['table']}'" + (f" (did you mean {', '.join(hint[:3])}?)" if hint else "")
            )
            continue
        e["table"] = t.fqn
        e["key"] = _resolve_key(t, e["key"], label, rep)
        for fld in ("label", "attributes"):
            bad = [c for c in e[fld] if not _col(t, c)]
            if bad:
                rep.warnings.append(f"{label}: ignored {fld} column(s) not in {t.fqn}: {', '.join(bad)}")
            e[fld] = list(dict.fromkeys(_col(t, c) for c in e[fld] if _col(t, c)))
        if e["kind"] not in KINDS:
            e["kind"] = "role" if (e["filter"] or e["is_a"]) else "core"
        if e["filter"]:
            try:
                check_readonly(f"SELECT 1 FROM {t.sql_name} WHERE {e['filter']}", model.dialect)
            except ValueError as ex:
                rep.dropped.append(f"{label}: filter rejected ({ex})")
                continue
        if engine is not None and not chk.active:
            rep.unverified += 1
        elif engine is not None:
            if e["filter"]:
                try:
                    e["rows"] = int(chk.scalar(f"SELECT COUNT(*) FROM {t.sql_name} WHERE {e['filter']}") or 0)
                except QueryTimeout as ex:
                    rep.warnings.append(f"{label}: rows not counted: {ex}")
                    rep.unverified += 1
                except Exception as ex:
                    rep.dropped.append(f"{label}: the filter failed on the database: {_err(ex)}")
                    continue
                else:
                    if e["rows"] == 0:
                        rep.warnings.append(f"{label}: no rows match the filter")
            if e["key"] and not _unique(t, e["key"]):
                cols = ", ".join(_csql(t, k) for k in e["key"])
                try:
                    dups = int(
                        chk.scalar(
                            f"SELECT COUNT(*) FROM (SELECT {cols} FROM "
                            f"{_source(model, t.fqn, e['filter'])} k GROUP BY {cols} "
                            "HAVING COUNT(*) > 1) d"
                        )
                        or 0
                    )
                    if dups:
                        rep.warnings.append(
                            f"{label}: key ({cols}) is not unique - {dups:,} values occur more than "
                            "once; choose the column(s) that identify one row"
                        )
                except QueryTimeout as ex:
                    rep.warnings.append(f"{label}: key uniqueness not checked: {ex}")
                except Exception as ex:
                    rep.warnings.append(f"{label}: could not check that the key is unique: {_err(ex)}")
        if not e["filter"]:
            e["rows"] = t.row_count
        entities.append(e)
        by_name[low] = e

    for e in entities:
        if not e["is_a"]:
            continue
        parent = by_name.get(e["is_a"].lower())
        if parent is None or parent is e:
            rep.warnings.append(f"entity '{e['name']}': is_a '{e['is_a']}' is not a known entity - removed")
            e["is_a"] = None
            continue
        if parent["table"] != e["table"]:
            try:
                plan_relation(model, e["table"], parent["table"], [])
            except PlanError:
                rep.warnings.append(
                    f"entity '{e['name']}': no join between {e['table']} and {parent['table']} - is_a removed"
                )
                e["is_a"] = None
                continue
        e["is_a"] = parent["name"]

    def find(name: str) -> dict[str, Any] | None:
        if not name:
            return None
        low = name.lower()
        hit = by_name.get(low) or next(
            (x for x in by_name.values() if low in (s.lower() for s in x.get("synonyms") or [])), None
        )
        if hit:
            return hit
        t = model.resolve(name)
        cands = [x for x in by_name.values() if t is not None and x["table"] == t.fqn and not x.get("filter")]
        return cands[0] if len(cands) == 1 else None

    pending: list[dict[str, Any]] = []
    for r in data["relations"]:
        poly = r.get("polymorphic")
        pending += _expand_polymorphic(model, r, find, rep) if poly and poly["targets"] else [r]

    relations: list[dict[str, Any]] = []
    for r in pending:
        label = f"relation '{r['subject']} {r['predicate']} {r['object']}'"
        s, o = find(r["subject"]), find(r["object"])
        if s is None or o is None:
            missing = [repr(n) for n, x in ((r["subject"], s), (r["object"], o)) if x is None]
            rep.dropped.append(f"{label}: unknown entity {' and '.join(missing)}")
            continue
        r["subject"], r["object"] = s["name"], o["name"]
        rkey = (s["name"].lower(), r["predicate"], o["name"].lower())
        if any((x["subject"].lower(), x["predicate"], x["object"].lower()) == rkey for x in relations):
            rep.dropped.append(f"{label}: defined twice")
            continue
        if rkey in known_rel and not replace:
            rep.unchanged += 1
            continue
        poly = r.get("polymorphic")
        if poly and not r["on"]:  # expanded polymorphic branch: join the reference column(s) to the target's key
            st, ot = model.tables[s["table"]], model.tables[o["table"]]
            ref_cols = [_col(st, c) for c in poly["column"]]
            okey = o.get("key") or []
            if not ref_cols or not all(ref_cols) or len(okey) != len(ref_cols):
                rep.dropped.append(
                    f"{label}: {o['name']} is identified by {', '.join(okey) or 'no key'}, which does "
                    f"not match the reference column(s) {', '.join(poly['column'])} - give the "
                    f"target's key, or write the join with on"
                )
                continue
            r["on"] = " AND ".join(f"{st.fqn}.{c} = {ot.fqn}.{k}" for c, k in zip(ref_cols, okey, strict=True))
        link = None
        if r["on"]:
            if r["via"]:
                rep.warnings.append(f"{label}: via ignored - on already gives the join columns")
                r["via"] = []
            try:
                link, r["on"] = parse_on(model, s["table"], o["table"], r["on"])
            except ValueError as ex:
                rep.dropped.append(f"{label}: {ex}")
                continue
        via, bad = [], []
        for v in r["via"]:
            parsed = parse_via(model, v)
            if parsed:
                via.append(parsed)
            else:
                bad.append(v)
        if bad:
            rep.warnings.append(f"{label}: ignored unknown via table(s) {', '.join(bad)}")
        notes: list[str] = []
        try:
            steps = plan_relation(model, s["table"], o["table"], via, notes=notes, link=link)
        except PlanError as ex:
            if not via:
                rep.dropped.append(f"{label}: {ex}")
                continue
            try:
                steps = plan_relation(model, s["table"], o["table"], [], notes=notes)
            except PlanError as ex2:
                rep.dropped.append(f"{label}: {ex2}")
                continue
            rep.warnings.append(f"{label}: the via tables do not connect ({ex}) - used the shortest join path instead")
            via = []
        rep.warnings += [f"{label}: {n}" for n in notes]
        pins = {t: p for t, p in via if p}
        s_pin = next((p for t, p in via if p and t == s["table"]), None)
        o_pin = next((p for t, p in via if p and t == o["table"] and t != s["table"]), None)
        r["via"] = (
            ([f"{s['table']}.{s_pin}"] if s_pin else [])
            + [
                st.table
                + (f".{pins[st.table]}" if st.table in pins and st.table not in (s["table"], o["table"]) else "")
                for st in steps[1:-1]
            ]
            + ([f"{o['table']}.{o_pin}"] if o_pin else [])
        )
        if r["condition"]:
            try:
                check_readonly(f"SELECT 1 FROM x WHERE {r['condition']}", model.dialect)
            except ValueError as ex:
                rep.dropped.append(f"{label}: condition rejected ({ex})")
                continue
        first: dict[str, str] = {}
        for step in steps:
            first.setdefault(step.table, step.alias)
        cond = _alias_names(model, r["condition"], first) if r["condition"] else None
        from_sql = from_clause(model, steps, {"s": s.get("filter"), "o": o.get("filter")})
        where = f" WHERE {cond}" if cond else ""
        r["join"] = from_sql + where
        if engine is not None and not chk.active:
            rep.unverified += 1
        elif engine is not None:
            info, problems, fatal = _verify_relation(chk, model, from_sql, where, cond, s, o, link)
            if fatal:
                rep.dropped += [f"{label}: {p}" for p in problems]
                continue
            rep.warnings += [f"{label}: {p}" for p in problems]
            if info is None:
                rep.unverified += 1
            else:
                r["verified"] = info
                seen = info.get("cardinality")
                if seen and (
                    r["cardinality"] is None
                    or any(x and not y for x, y in zip(_sides(seen), _sides(r["cardinality"]), strict=True))
                ):
                    if r["cardinality"]:
                        rep.warnings.append(
                            f"{label}: cardinality {r['cardinality']} corrected to {seen} (observed in data)"
                        )
                    r["cardinality"] = seen
        r["_tables"] = list(dict.fromkeys(st.table for st in steps))
        r["_link"] = link
        relations.append(r)

    rep.entities, rep.relations = len(entities), len(relations)
    return {"entities": entities, "relations": relations}, rep


def key_text(e: dict[str, Any]) -> str:
    key = e.get("key") or []
    return ", ".join(key) if isinstance(key, list) else str(key)


def data_note(r: dict[str, Any]) -> str:
    """Short data facts of a relation, e.g. '46,742 pairs, 12 unmatched'."""
    v = r.get("verified") or {}
    parts = [f"{v['pairs']:,} pairs" if isinstance(v.get("pairs"), int) else ""]
    if v.get("unmatched"):
        parts.append(f"{v['unmatched']:,} unmatched")
    return ", ".join(p for p in parts if p)


def merge_graphs(known: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Add or replace items of `known` with the (already validated) items of `new`."""
    entities = {e["name"].lower(): e for e in known.get("entities") or []}
    for e in new.get("entities") or []:
        entities[e["name"].lower()] = e
    relations = {(r["subject"].lower(), r["predicate"], r["object"].lower()): r for r in known.get("relations") or []}
    for r in new.get("relations") or []:
        relations[(r["subject"].lower(), r["predicate"], r["object"].lower())] = r
    return {"entities": list(entities.values()), "relations": list(relations.values())}


ENTITY_FIELDS = (
    "name",
    "kind",
    "description",
    "synonyms",
    "table",
    "key",
    "label",
    "filter",
    "is_a",
    "attributes",
    "rows",
)
RELATION_FIELDS = (
    "subject",
    "predicate",
    "object",
    "cardinality",
    "via",
    "on",
    "condition",
    "polymorphic",
    "description",
    "join",
    "verified",
)


def _compact(v: Any) -> Any:
    return v[0] if isinstance(v, list) and len(v) == 1 else v


def to_yaml_dict(graph: dict[str, Any]) -> dict[str, Any]:
    """Drop derived/empty fields and order keys for a readable knowledge_graph.yaml."""

    def clean(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        return {k: item[k] for k in fields if item.get(k) not in (None, "", [], {})}

    entities = []
    for e in graph.get("entities") or []:
        d = clean(e, ENTITY_FIELDS)
        if "key" in d:
            d["key"] = _compact(d["key"])  # one column: plain name; composite key: list
        entities.append(d)
    relations = []
    for r in graph.get("relations") or []:
        d = clean(r, RELATION_FIELDS)
        p = d.get("polymorphic")
        if isinstance(p, dict):
            p = {
                "column": _compact(p.get("column") or []),
                "type_column": p.get("type_column"),
                "type": p.get("type"),
                "targets": p.get("targets"),
            }
            d["polymorphic"] = {k: v for k, v in p.items() if v not in (None, "", [], {})}
        relations.append(d)
    return {"entities": entities, "relations": relations}
