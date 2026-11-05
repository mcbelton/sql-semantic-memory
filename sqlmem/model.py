"""Semantic model = raw catalog (facts from the DB) + semantic.yaml (business meaning) + inferred joins."""

from __future__ import annotations

import difflib
import heapq
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

HOUSEKEEPING_MIN_TABLES = 5
HOUSEKEEPING_SHARE = 0.3
_GUID = re.compile(r"^\{?[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\}?$")


@dataclass
class Column:
    name: str
    sql_name: str
    type: str
    kind: str
    nullable: bool
    description: str = ""
    synonyms: list[str] = field(default_factory=list)
    values: dict[str, str] = field(default_factory=dict)  # curated code -> meaning
    profile: dict[str, Any] = field(default_factory=dict)
    sensitive: bool = False
    computed: str | None = None
    pk: bool = False
    fk: str | None = None  # "<table fqn>.<column>"
    housekeeping: bool = False
    curated: bool = False  # described in semantic.yaml


@dataclass
class Table:
    fqn: str
    name: str
    schema: str | None
    sql_name: str
    type: str
    short: str
    domain: str | None = None
    description: str = ""
    synonyms: list[str] = field(default_factory=list)
    grain: str = ""
    notes: list[str] = field(default_factory=list)
    hidden: bool = False
    row_count: int | None = None
    row_count_exact: bool = False
    columns: dict[str, Column] = field(default_factory=dict)
    primary_key: list[str] = field(default_factory=list)
    unique: list[list[str]] = field(default_factory=list)
    indexes: list[dict[str, Any]] = field(default_factory=list)
    definition: str | None = None
    sampled: bool = False
    sample_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Relationship:
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    source: str  # declared | curated | inferred | kg (explicit/polymorphic link from the knowledge graph)
    condition: str = ""
    description: str = ""

    def on_clause(self, model: SemanticModel) -> str:
        a, b = model.tables[self.from_table], model.tables[self.to_table]
        parts = [
            f"{a.sql_name}.{a.columns[x].sql_name if x in a.columns else x} = "
            f"{b.sql_name}.{b.columns[y].sql_name if y in b.columns else y}"
            for x, y in zip(self.from_columns, self.to_columns, strict=True)
        ]
        if self.condition:
            parts.append(f"({self.condition})")
        return " AND ".join(parts)

    def label(self) -> str:
        return f"{self.from_table}.{','.join(self.from_columns)} -> {self.to_table}.{','.join(self.to_columns)}"


def singular(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("sses", "xes", "ches", "shes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# Words that are never evidence for a value match on their own ("n a" is the normalized form of "N/A").
_VALUE_STOPWORD_TEXT = """
other others none unknown all total true false yes no null the and for with from this that what which who
how many much most top best per each by of in on at to is are was were
"""
VALUE_STOPWORDS = frozenset(_VALUE_STOPWORD_TEXT.split()) | {"n a"}


def _value_key(s: str) -> str:
    return " ".join(singular(w) for w in re.findall(r"[a-z0-9]+", s.lower()))


def split_identifier(name: str) -> str:
    """'SalesOrderHeader' / 'sales_order_header' -> 'sales order header'."""
    s = re.sub(r"[_\-.\[\]\"`]+", " ", name)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x) for x in v]


def _as_text_list(v: Any) -> list[str]:
    if not v:
        return []
    return [str(v).strip()] if isinstance(v, str) else [str(x).strip() for x in v]


def _split_ref(ref: str) -> tuple[str, str]:
    table, _, col = ref.rpartition(".")
    return table, col


def _spec_dict(spec: Any) -> dict[str, Any]:
    """semantic.yaml allows a bare description string wherever a mapping of details is accepted."""
    if isinstance(spec, str):
        return {"description": spec}
    return dict(spec or {})


class SemanticModel:
    def __init__(
        self, catalog: dict[str, Any], semantic: dict[str, Any] | None = None, kg: dict[str, Any] | None = None
    ):
        self.catalog = catalog
        self.semantic = semantic or {}
        self.warnings: list[str] = []
        self.dialect: str = catalog.get("source", {}).get("dialect", "")
        db = self.semantic.get("database") or {}
        self.name: str = db.get("name") or catalog.get("source", {}).get("database") or "database"
        self.description: str = (db.get("description") or "").strip()
        self.dialect_notes: list[str] = _as_text_list(db.get("dialect_notes"))
        self.domains: dict[str, str] = {str(k): str(v or "") for k, v in (self.semantic.get("domains") or {}).items()}
        self.separator = self._detect_separator(catalog)
        self.tables: dict[str, Table] = {}
        self.relationships: list[Relationship] = []
        self._composite_fk: set[tuple[str, str]] = set()
        self._load_tables()
        self._apply_overlay()
        self._load_relationships()
        self._mark_housekeeping()
        self.glossary: list[dict[str, Any]] = self._load_items("glossary", "term")
        self.metrics: list[dict[str, Any]] = self._load_items("metrics", "name")
        self.examples: list[dict[str, Any]] = self._load_items("examples", "question")
        self.routines: list[dict[str, Any]] = catalog.get("routines") or []
        self._build_graph()
        self._build_value_index()
        self._load_knowledge_graph(kg)

    def _load_knowledge_graph(self, kg: dict[str, Any] | None) -> None:
        """Business entities/relations from knowledge_graph.yaml, re-checked against the current schema."""
        from .kgraph import validate_graph

        self.kg: dict[str, Any] = {"entities": [], "relations": []}
        if not kg:
            return
        try:
            self.kg, report = validate_graph(self, kg)
        except ValueError as e:
            self.warnings.append(f"knowledge_graph.yaml: {e}")
            return
        self.warnings += [f"knowledge_graph.yaml: {m}" for m in report.dropped + report.warnings]
        self._register_graph_links()

    def _register_graph_links(self) -> None:
        """Explicit and polymorphic links of the knowledge graph become join paths for SQL context and docs."""
        added = False
        for r in self.kg["relations"]:
            link = r.get("_link")
            s, o = self.entity(r["subject"]), self.entity(r["object"])
            if link is None or (s and s.get("filter")) or (o and o.get("filter")):
                continue  # entity filters are not part of a table-level join
            cond = r.get("condition") or ""
            if any(
                x.from_table == link.from_table
                and x.to_table == link.to_table
                and x.condition == cond
                and x.from_columns == link.from_columns
                and x.to_columns == link.to_columns
                for x in self.relationships
            ):
                continue
            self.relationships.append(
                Relationship(
                    link.from_table,
                    list(link.from_columns),
                    link.to_table,
                    list(link.to_columns),
                    "kg",
                    cond,
                    f"{r['subject']} {r['predicate'].replace('_', ' ')} {r['object']}",
                )
            )
            added = True
        if added:
            self._build_graph()

    def entity(self, name: str) -> dict[str, Any] | None:
        low = (name or "").strip().lower()
        return next((e for e in self.kg["entities"] if e["name"].lower() == low), None) or next(
            (e for e in self.kg["entities"] if low in (s.lower() for s in e.get("synonyms") or [])), None
        )

    # ------------------------------------------------------------------ loading
    @staticmethod
    def _detect_separator(catalog: dict[str, Any]) -> str | None:
        names = [o["name"] for o in catalog.get("objects", []) if not o.get("schema")]
        if names and sum("__" in n.strip("_") for n in names) >= 0.5 * len(names):
            return "__"
        return None

    def _load_tables(self) -> None:
        for o in self.catalog.get("objects", []):
            name = o["name"]
            short, domain = name, o.get("schema")
            if self.separator and self.separator in name.strip("_"):
                domain, _, short = name.partition(self.separator)
            t = Table(
                fqn=o["fqn"],
                name=name,
                schema=o.get("schema"),
                sql_name=o.get("sql_name") or o["fqn"],
                type=o.get("type", "table"),
                short=short,
                domain=domain,
                description=(o.get("comment") or "").strip(),
                row_count=o.get("row_count"),
                row_count_exact=bool(o.get("row_count_exact")),
                primary_key=list(o.get("primary_key") or []),
                unique=[list(u) for u in o.get("unique") or [] if u],
                indexes=o.get("indexes") or [],
                definition=o.get("definition"),
                sampled=bool((o.get("profile_meta") or {}).get("sampled")),
                sample_rows=o.get("sample_rows") or [],
            )
            for c in o.get("columns", []):
                t.columns[c["name"]] = Column(
                    name=c["name"],
                    sql_name=c.get("sql_name") or c["name"],
                    type=c.get("type", ""),
                    kind=c.get("kind", "other"),
                    nullable=bool(c.get("nullable", True)),
                    description=(c.get("comment") or "").strip(),
                    profile=c.get("profile") or {},
                    sensitive=bool(c.get("sensitive")),
                    computed=c.get("computed"),
                    pk=c["name"] in t.primary_key,
                )
            self.tables[t.fqn] = t
        for o in self.catalog.get("objects", []):
            for fk in o.get("foreign_keys", []):
                if fk["ref_table"] not in self.tables:
                    continue
                if not fk["columns"] or len(fk["columns"]) != len(fk["ref_columns"]):
                    self.warnings.append(f"catalog.json: ignored malformed foreign key {fk.get('name')} on {o['fqn']}")
                    continue
                rel = Relationship(o["fqn"], fk["columns"], fk["ref_table"], fk["ref_columns"], "declared")
                self.relationships.append(rel)
                cols = self.tables[o["fqn"]].columns
                for col, ref in zip(fk["columns"], fk["ref_columns"], strict=True):
                    if col in cols and (cols[col].fk is None or (o["fqn"], col) in self._composite_fk):
                        cols[col].fk = f"{fk['ref_table']}.{ref}"
                        if len(fk["columns"]) > 1:
                            self._composite_fk.add((o["fqn"], col))
                        else:
                            self._composite_fk.discard((o["fqn"], col))

    def _apply_overlay(self) -> None:
        for key, raw_spec in (self.semantic.get("tables") or {}).items():
            t = self.resolve(str(key))
            if t is None:
                self.warnings.append(f"semantic.yaml: unknown table '{key}'")
                continue
            spec = _spec_dict(raw_spec)
            if spec.get("description"):
                t.description = str(spec["description"]).strip()
            t.synonyms = _as_list(spec.get("synonyms"))
            t.grain = str(spec.get("grain") or "").strip()
            t.notes = _as_text_list(spec.get("notes"))
            t.hidden = bool(spec.get("hidden", False))
            if spec.get("domain"):
                t.domain = str(spec["domain"])
            for cname, raw_cspec in (spec.get("columns") or {}).items():
                col = t.columns.get(str(cname)) or next(
                    (c for c in t.columns.values() if c.name.lower() == str(cname).lower()), None
                )
                if col is None:
                    self.warnings.append(f"semantic.yaml: unknown column '{t.fqn}.{cname}'")
                    continue
                cspec = _spec_dict(raw_cspec)
                if cspec.get("description"):
                    col.description = str(cspec["description"]).strip()
                    col.curated = True
                col.synonyms = _as_list(cspec.get("synonyms"))
                col.values = {str(k): str(v) for k, v in (cspec.get("values") or {}).items()}
                if "sensitive" in cspec:
                    col.sensitive = bool(cspec["sensitive"])

    def _mark_housekeeping(self) -> None:
        """Hide technical columns repeated across many tables (audit timestamps, row GUIDs) from search/context."""
        explicit = (self.semantic.get("database") or {}).get("housekeeping_columns")
        if explicit is not None:
            names = {str(x).lower() for x in explicit}
            for t in self.tables.values():
                for c in t.columns.values():
                    c.housekeeping = c.name.lower() in names and not c.curated
            return
        visible = [t for t in self.tables.values() if not t.hidden]
        counts = Counter(c.name.lower() for t in visible for c in t.columns.values())
        threshold = max(HOUSEKEEPING_MIN_TABLES, HOUSEKEEPING_SHARE * len(visible))
        for t in visible:
            for c in t.columns.values():
                if counts[c.name.lower()] < threshold or c.pk or c.fk or c.values or c.curated:
                    continue
                p = c.profile or {}
                c.housekeeping = (
                    c.kind in ("temporal", "uuid")
                    or "guid" in c.name.lower()
                    or (
                        c.kind == "text"
                        and (
                            p.get("min") is not None  # date-like text
                            or any(_GUID.match(str(x)) for x in p.get("examples") or [])
                        )
                    )
                )

    def _load_relationships(self) -> None:
        for r in self.semantic.get("relationships") or []:
            try:
                ft, fc = _split_ref(str(r["from"]))
                tt, tc = _split_ref(str(r["to"]))
            except Exception:
                self.warnings.append(f"semantic.yaml: bad relationship {r!r}")
                continue
            a, b = self.resolve(ft), self.resolve(tt)
            if a is None or b is None or fc not in a.columns or tc not in b.columns:
                self.warnings.append(
                    f"semantic.yaml: relationship references unknown table/column: {r.get('from')} -> {r.get('to')}"
                )
                continue
            self.relationships.append(
                Relationship(
                    a.fqn,
                    [fc],
                    b.fqn,
                    [tc],
                    "curated",
                    str(r.get("condition") or "").strip(),
                    str(r.get("description") or "").strip(),
                )
            )
        self._infer_relationships()

    def _infer_relationships(self) -> None:
        # Columns that only take part in a composite FK may still get a direct single-column link.
        linked = {(r.from_table, r.from_columns[0]) for r in self.relationships if len(r.from_columns) == 1}
        single_pk = [t for t in self.tables.values() if t.type == "table" and len(t.primary_key) == 1]
        by_pk: dict[str, list[Table]] = {}
        by_name: dict[str, list[Table]] = {}
        for t in single_pk:
            by_pk.setdefault(t.primary_key[0].lower(), []).append(t)
            by_name.setdefault(singular(_norm(t.short)), []).append(t)
        for t in self.tables.values():
            for c in t.columns.values():
                if (t.fqn, c.name) in linked or c.kind not in ("number", "text", "uuid", "other"):
                    continue
                m = re.match(r"^(.+?)_?id$", c.name, re.I)
                if not m or t.primary_key == [c.name]:
                    continue
                base = singular(_norm(m.group(1)))
                cands = [
                    x
                    for x in by_name.get(base, [])
                    if x is not t and x.primary_key[0].lower() in (c.name.lower(), "id")
                ]
                if not cands:
                    cands = [x for x in by_pk.get(c.name.lower(), []) if x is not t]
                if len(cands) == 1:
                    target = cands[0]
                    if any(
                        r.from_table == t.fqn
                        and r.to_table == target.fqn
                        and c.name in r.from_columns
                        and r.to_columns[r.from_columns.index(c.name)] == target.primary_key[0]
                        for r in self.relationships
                    ):
                        continue
                    self.relationships.append(
                        Relationship(t.fqn, [c.name], target.fqn, [target.primary_key[0]], "inferred")
                    )
                    if c.fk is None or (t.fqn, c.name) in self._composite_fk:
                        c.fk = f"{target.fqn}.{target.primary_key[0]}"

    def _load_items(self, section: str, key: str) -> list[dict[str, Any]]:
        items = []
        for raw in self.semantic.get(section) or []:
            if not isinstance(raw, dict) or not raw.get(key):
                self.warnings.append(f"semantic.yaml: {section} item without '{key}': {raw!r}")
                continue
            item = dict(raw)
            item["synonyms"] = _as_list(item.get("synonyms"))
            declared = [self.resolve(x) for x in _as_list(item.get("tables"))]
            for name, t in zip(_as_list(item.get("tables")), declared, strict=True):
                if t is None:
                    self.warnings.append(f"semantic.yaml: {section} '{item[key]}' references unknown table '{name}'")
            found = [t.fqn for t in declared if t] + self.tables_in_sql(str(item.get("sql") or ""))
            item["tables"] = list(dict.fromkeys(found))
            items.append(item)
        return items

    # ------------------------------------------------------------------ lookup
    def visible_tables(self) -> list[Table]:
        return [t for t in self.tables.values() if not t.hidden]

    def resolve(self, name: str) -> Table | None:
        if not name:
            return None
        n = ".".join(p.strip().strip('[]"`') for p in str(name).strip().split("."))
        if n in self.tables:
            return self.tables[n]
        low = n.lower()
        for t in self.tables.values():
            if low in (t.fqn.lower(), re.sub(r'[\[\]"`]', "", t.sql_name).lower()):
                return t
        if self.separator and "." in n:
            joined = n.replace(".", self.separator).lower()
            for t in self.tables.values():
                if t.fqn.lower() == joined:
                    return t
        shorts = [t for t in self.tables.values() if t.short.lower() == low.rpartition(".")[2]]
        return shorts[0] if len(shorts) == 1 else None

    def suggest(self, name: str, n: int = 5) -> list[str]:
        keys = {t.fqn.lower(): t.fqn for t in self.tables.values()}
        keys.update({t.short.lower(): t.fqn for t in self.tables.values()})
        hits = difflib.get_close_matches(name.lower(), list(keys), n=n, cutoff=0.5)
        return list(dict.fromkeys(keys[h] for h in hits))

    def tables_in_sql(self, sql: str) -> list[str]:
        if not sql:
            return []
        s = re.sub(r'[\[\]"`]', "", sql).lower()
        found = []
        for t in self.tables.values():
            aliases = {t.fqn.lower()}
            if not t.schema or (self.dialect == "mssql" and t.schema.lower() == "dbo"):
                aliases.add(t.name.lower())
            if any(re.search(r"(?<![\w.])" + re.escape(a) + r"(?!\w)", s) for a in aliases):
                found.append(t.fqn)
        return found

    # ------------------------------------------------------------------ value linking
    def _build_value_index(self) -> None:
        """Index captured text values so literals in a question ('Helmets', 'Germany') map to table.column."""
        vocab: set[str] = set()
        for t in self.tables.values():
            vocab.update(singular(w) for w in split_identifier(t.short).split())
            for c in t.columns.values():
                vocab.update(singular(w) for w in split_identifier(c.name).split())
        self.value_index: dict[str, list[tuple[str, str, Any]]] = {}
        for t in self.visible_tables():
            for c in t.columns.values():
                if c.sensitive or c.kind != "text":
                    continue
                for v, _n in c.profile.get("values") or []:
                    if not isinstance(v, str):
                        continue
                    key = _value_key(v)
                    if len(key) < 3 or key.replace(" ", "").isdigit():
                        continue
                    if " " not in key and (key in vocab or key in VALUE_STOPWORDS):
                        continue  # single words that are schema vocabulary or generic are not evidence
                    self.value_index.setdefault(key, []).append((t.fqn, c.name, v))
        self._max_value_words = max((k.count(" ") + 1 for k in self.value_index), default=1)

    def match_values(self, text: str, per_value: int = 3) -> list[tuple[str, str, str, Any]]:
        """Longest-first n-gram match of question text against the value index -> (phrase, table, column, value)."""
        words = _value_key(text).split()
        found: list[tuple[str, str, str, Any]] = []
        used: set[int] = set()
        for n in range(min(self._max_value_words, 5), 0, -1):
            for i in range(len(words) - n + 1):
                if used.intersection(range(i, i + n)):
                    continue
                key = " ".join(words[i : i + n])
                if key in self.value_index:
                    found += [(key, t, c, v) for t, c, v in self.value_index[key][:per_value]]
                    used.update(range(i, i + n))
        return found

    # ------------------------------------------------------------------ graph / joins
    def _build_graph(self) -> None:
        self.adj: dict[str, list[tuple[str, float, Relationship]]] = {k: [] for k in self.tables}
        weight = {"declared": 1.0, "curated": 1.0, "kg": 1.0, "inferred": 1.3}
        for r in self.relationships:
            w = weight.get(r.source, 1.5) + (1.5 if r.condition else 0.0)
            self.adj[r.from_table].append((r.to_table, w, r))
            self.adj[r.to_table].append((r.from_table, w, r))

    def relationships_of(self, fqn: str) -> list[Relationship]:
        return [r for r in self.relationships if fqn in (r.from_table, r.to_table)]

    def join_path(
        self, sources: set[str] | str, target: str, max_hops: int = 4, skip_sources: tuple[str, ...] = ()
    ) -> list[Relationship] | None:
        """Cheapest join path from any table in `sources` to `target` (Dijkstra)."""
        srcs = {sources} if isinstance(sources, str) else set(sources)
        if target in srcs:
            return []
        dist = dict.fromkeys(srcs, 0.0)
        prev: dict[str, tuple[str, Relationship]] = {}
        heap = [(0.0, 0, s) for s in srcs]
        heapq.heapify(heap)
        while heap:
            d, hops, node = heapq.heappop(heap)
            if node == target:
                path = []
                while node not in srcs:
                    node, rel = prev[node][0], prev[node][1]
                    path.append(rel)
                return list(reversed(path))
            if d > dist.get(node, float("inf")) or hops >= max_hops:
                continue
            for nxt, w, rel in self.adj.get(node, []):
                if (self.tables[nxt].hidden and nxt != target) or rel.source in skip_sources:
                    continue
                nd = d + w
                if nd < dist.get(nxt, float("inf")):
                    dist[nxt] = nd
                    prev[nxt] = (node, rel)
                    heapq.heappush(heap, (nd, hops + 1, nxt))
        return None

    def connect(self, tables: list[str], max_hops: int = 3, max_extra: int = 3) -> tuple[list[str], list[Relationship]]:
        """Greedy Steiner tree: connect ranked tables, adding bridge tables where needed."""
        if not tables:
            return [], []
        tree: list[str] = [tables[0]]
        rels: list[Relationship] = []
        extra = 0
        for t in tables[1:]:
            if t in tree:
                continue
            path = self.join_path(set(tree), t, max_hops=max_hops)
            if path is None:
                tree.append(t)
                continue
            new: list[str] = []
            for r in path:
                for x in (r.from_table, r.to_table):
                    if x not in tree and x not in new:
                        new.append(x)
            bridges = [x for x in new if x != t and x not in tables]
            if extra + len(bridges) > max_extra:
                tree.append(t)
                continue
            extra += len(bridges)
            tree.extend(new)
            rels.extend(r for r in path if r not in rels)
        return tree, rels
