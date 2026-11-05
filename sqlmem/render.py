"""Render the semantic model as Markdown docs, search chunks, a knowledge graph and prompt-ready context."""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from importlib import resources
from typing import Any

from .kgraph import data_note, key_text
from .model import Column, Relationship, SemanticModel, Table, split_identifier
from .store import Chunk, Hit


def lit(v: Any) -> str:
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def num(n: Any) -> str:
    return f"{n:,}" if isinstance(n, int) else "?"


def cell(s: Any) -> str:
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def doc_filename(fqn: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]', "_", fqn) + ".md"


def column_flags(c: Column) -> list[str]:
    flags = []
    if c.pk:
        flags.append("PK")
    if c.fk:
        flags.append(f"FK -> {c.fk}")
    if not c.nullable:
        flags.append("NOT NULL")
    if c.computed:
        flags.append(f"computed: {c.computed}")
    return flags


def column_facts(c: Column, max_values: int = 12) -> str:
    """Compact facts about a column's data: code meanings, value dictionary, ranges, nulls."""
    p = c.profile or {}
    parts = []
    if c.values:
        parts.append("codes: " + ", ".join(f"{k}={v}" for k, v in c.values.items()))
    if c.sensitive:
        parts.append("sensitive - values not captured")
    else:
        obs = p.get("values") or []
        nn, nd = p.get("non_null") or 0, p.get("distinct")
        lo, hi = p.get("min"), p.get("max")
        has_range = lo is not None and hi is not None
        is_date = c.kind == "temporal" or (c.kind == "text" and has_range)
        idlike = c.pk or c.fk is not None
        unique = isinstance(nd, int) and nd == nn and nd > 3
        if obs and not is_date and not (c.kind == "number" and (idlike or unique)):
            counts = any(n != 1 for _, n in obs)
            if unique and len(obs) > max_values:  # long list of unique names/codes: a few examples suffice
                parts.append("e.g. " + ", ".join(lit(v) for v, _ in obs[:3]) + f" ({num(nd)} distinct)")
            else:
                shown = ", ".join(lit(v) + (f" ({num(n)})" if counts else "") for v, n in obs[:max_values])
                if len(obs) > max_values or (isinstance(nd, int) and nd > len(obs)):
                    shown += f", ... ({num(nd)} distinct)"
                parts.append(f"values: {shown}")
        elif has_range:
            rng = f"range {lo} .. {hi}"
            if c.kind == "number" and not idlike and isinstance(p.get("avg"), (int, float)):
                rng += f", avg {p['avg']:.6g}"
            parts.append(rng)
        elif c.kind == "text" and p.get("examples"):
            parts.append("e.g. " + ", ".join(lit(v) for v in p["examples"]))
        if c.kind == "text" and not is_date and not obs and isinstance(nd, int):
            parts.append(f"{num(nd)} distinct")
    if p.get("null_pct"):
        parts.append(f"{p['null_pct']}% null")
    return "; ".join(parts)


def column_line(c: Column) -> str:
    head = ", ".join([c.type, *column_flags(c)])
    desc = f": {c.description}" if c.description else ""
    facts = column_facts(c)
    return f"- {c.sql_name} ({head}){desc}" + (f" | {facts}" if facts else "")


def table_header(t: Table) -> str:
    bits = [t.type]
    if t.row_count is not None:
        bits.append(f"{'~' if not t.row_count_exact else ''}{num(t.row_count)} rows")
    if t.domain:
        bits.append(f"domain {t.domain}")
    return f"{t.sql_name} ({', '.join(bits)})"


def compact_card(model: SemanticModel, t: Table) -> str:
    lines = [f"### {table_header(t)}"]
    if t.description:
        lines.append(t.description)
    if t.grain:
        lines.append(f"Grain: {t.grain}")
    if t.synonyms:
        lines.append(f"Also called: {', '.join(t.synonyms)}")
    lines += [f"Note: {n}" for n in t.notes]
    main = [c for c in t.columns.values() if not c.housekeeping]
    other = [c.sql_name for c in t.columns.values() if c.housekeeping]
    lines += [column_line(c) for c in main]
    if other:
        lines.append(f"- (also: {', '.join(other)})")
    refs = sorted(
        {
            f"{r.from_table}.{','.join(r.from_columns)}"
            for r in model.relationships
            if r.to_table == t.fqn and r.from_table != t.fqn and not model.tables[r.from_table].hidden
        }
    )
    if refs:
        lines.append(f"Referenced by: {', '.join(refs[:10])}" + (", ..." if len(refs) > 10 else ""))
    return "\n".join(lines)


def _rel_line(model: SemanticModel, r: Relationship) -> str:
    tag = r.source + (f"; {r.description}" if r.description else "")
    return f"- {r.on_clause(model)}  [{tag}]"


# ----------------------------------------------------------------------------- full docs
def table_doc(model: SemanticModel, t: Table) -> str:
    out = [f"# {t.fqn}", ""]
    out.append(
        f"**Type:** {t.type} | **Domain:** {t.domain or '-'} | **Rows:** "
        f"{('~' if not t.row_count_exact else '') + num(t.row_count) if t.row_count is not None else '-'}"
        f" | **SQL name:** `{t.sql_name}`"
    )
    out.append("")
    out.append(t.description or "_No description yet - add one in semantic.yaml._")
    if t.grain:
        out += ["", f"**Grain:** {t.grain}"]
    if t.synonyms:
        out += ["", f"**Synonyms:** {', '.join(t.synonyms)}"]
    if t.notes:
        out += ["", "**Notes:**"] + [f"- {n}" for n in t.notes]
    if t.primary_key:
        out += ["", f"**Primary key:** {', '.join(t.primary_key)}"]
    out += [
        "",
        "## Columns",
        "",
        "| Column | Type | Keys / flags | Description | Data profile |",
        "|---|---|---|---|---|",
    ]
    for c in t.columns.values():
        flags = [f for f in column_flags(c) if not f.startswith("computed")]
        desc = c.description + (f" (computed: {c.computed})" if c.computed else "")
        out.append(
            f"| {cell(c.name)} | {cell(c.type)} | {cell(', '.join(flags))} | {cell(desc)} | "
            f"{cell(column_facts(c, 20))} |"
        )
    rels = model.relationships_of(t.fqn)
    if rels:
        out += ["", "## Relationships", ""]
        for r in rels:
            out.append(_rel_line(model, r))
    uniq = [i for i in t.indexes if i.get("unique")]
    if uniq:
        out += ["", "**Unique indexes:** " + "; ".join(f"{i['name']} ({', '.join(i['columns'])})" for i in uniq)]
    related = [m for m in model.metrics if t.fqn in m["tables"]] + [g for g in model.glossary if t.fqn in g["tables"]]
    if related:
        out += ["", "## Business definitions", ""]
        out += [f"- **{x.get('name') or x.get('term')}**: {x.get('definition', '').strip()}" for x in related]
    ex = [e for e in model.examples if t.fqn in e["tables"]]
    if ex:
        out += ["", "## Example queries", ""]
        for e in ex:
            out += [f"**{e['question']}**", "", "```sql", str(e.get("sql", "")).strip(), "```", ""]
    if t.definition:
        out += ["", "## View definition", "", "```sql", t.definition, "```"]
    if t.sample_rows:
        cols = list(t.sample_rows[0].keys())
        out += ["", "## Sample rows", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        out += ["| " + " | ".join(cell(r.get(k)) for k in cols) + " |" for r in t.sample_rows]
    if t.sampled:
        out += ["", "_Profile computed on a sample of rows._"]
    return "\n".join(out) + "\n"


def _ent(fqn: str) -> str:
    return re.sub(r"\W", "_", fqn)


def mermaid(model: SemanticModel, tables: list[Table]) -> str:
    names = {t.fqn for t in tables}
    lines = ["erDiagram"]
    for t in tables:
        keys = [c for c in t.columns.values() if c.pk or c.fk]
        if keys:
            lines.append(f"    {_ent(t.fqn)} {{")
            for c in keys:
                ctype = re.sub(r"\W", "", c.type.split("(")[0].split()[0]) if c.type else "col"
                lines.append(f"        {ctype or 'col'} {_ent(c.name)} {'PK' if c.pk else 'FK'}")
            lines.append("    }")
    for r in model.relationships:
        if (
            (r.from_table in names or r.to_table in names)
            and not model.tables[r.from_table].hidden
            and not model.tables[r.to_table].hidden
        ):
            lines.append(f'    {_ent(r.to_table)} ||--o{{ {_ent(r.from_table)} : "{",".join(r.from_columns)}"')
    return "\n".join(lines)


def by_domain(model: SemanticModel) -> dict[str, list[Table]]:
    groups: dict[str, list[Table]] = defaultdict(list)
    for t in model.visible_tables():
        groups[t.domain or "(no domain)"].append(t)
    return dict(sorted(groups.items()))


def overview_doc(model: SemanticModel, stats: dict[str, Any]) -> str:
    tables = model.visible_tables()
    ncols = sum(len(t.columns) for t in tables)
    described = sum(1 for t in tables if t.description)
    cdesc = sum(1 for t in tables for c in t.columns.values() if c.description)
    src = model.catalog.get("source", {})
    out = [f"# {model.name} - semantic knowledge base", ""]
    if model.description:
        out += [model.description, ""]
    out += [
        (
            f"- **Source:** {src.get('dialect')} `{src.get('database') or ''}` "
            f"(server {src.get('server_version') or '?'}), scanned {model.catalog.get('generated_at', '?')}"
        ),
        (
            f"- **Objects:** {len(tables)} tables/views, {ncols} columns, {len(model.relationships)} relationships "
            f"({sum(r.source == 'declared' for r in model.relationships)} declared, "
            f"{sum(r.source == 'inferred' for r in model.relationships)} inferred, "
            f"{sum(r.source == 'curated' for r in model.relationships)} curated, "
            f"{sum(r.source == 'kg' for r in model.relationships)} from the knowledge graph)"
        ),
        (
            f"- **Semantic coverage:** {described}/{len(tables)} tables and {cdesc}/{ncols} columns described; "
            f"{len(model.glossary)} glossary terms, {len(model.metrics)} metrics, "
            f"{len(model.examples)} example queries, {stats.get('memories', 0)} memories"
        ),
        f"- **Index:** {stats.get('chunks', 0)} chunks, embedder `{stats.get('embedder', 'none')}`",
    ]
    if model.kg["entities"]:
        out.append(
            f"- **Knowledge graph:** {len(model.kg['entities'])} business entities, "
            f"{len(model.kg['relations'])} relations - [knowledge-graph.md](knowledge-graph.md), "
            "[interactive view](knowledge-graph.html)"
        )
    out += [
        "",
    ]
    if model.dialect_notes:
        out += ["## SQL notes for this database", ""] + [f"- {n}" for n in model.dialect_notes] + [""]
    for domain, items in by_domain(model).items():
        out += [f"## {domain}", ""]
        if model.domains.get(domain):
            out += [model.domains[domain], ""]
        out += ["| Table | Rows | Description |", "|---|---|---|"]
        for t in sorted(items, key=lambda x: x.fqn.lower()):
            first = (t.description.split(". ")[0] if t.description else "")[:160]
            out.append(f"| [{t.fqn}](tables/{doc_filename(t.fqn)}) | {num(t.row_count)} | {cell(first)} |")
        if len(items) <= 60:
            out += ["", "```mermaid", mermaid(model, items), "```"]
        out.append("")
    if model.metrics:
        out += (
            ["## Metrics", ""]
            + [
                f"- **{m['name']}**: {m.get('definition', '').strip()} `{str(m.get('sql', '')).strip()}`"
                for m in model.metrics
            ]
            + [""]
        )
    if model.glossary:
        out += (
            ["## Glossary", ""]
            + [f"- **{g['term']}**: {g.get('definition', '').strip()}" for g in model.glossary]
            + [""]
        )
    if model.examples:
        out += ["## Example questions", ""] + [f"- {e['question']}" for e in model.examples] + [""]
    if model.warnings:
        out += ["## Warnings", ""] + [f"- {w}" for w in model.warnings] + [""]
    return "\n".join(out)


def graph_json(model: SemanticModel) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for t in model.visible_tables():
        nodes.append(
            {"id": t.fqn, "type": t.type, "domain": t.domain, "rows": t.row_count, "description": t.description}
        )
        if t.domain:
            edges.append({"source": t.fqn, "target": f"domain:{t.domain}", "type": "in_domain"})
    for d in sorted({t.domain for t in model.visible_tables() if t.domain}):
        nodes.append({"id": f"domain:{d}", "type": "domain", "description": model.domains.get(d, "")})
    for r in model.relationships:
        edges.append(
            {
                "source": r.from_table,
                "target": r.to_table,
                "type": "references",
                "via": r.source,
                "from_columns": r.from_columns,
                "to_columns": r.to_columns,
                "condition": r.condition or None,
            }
        )
    for kind, items, key in (("metric", model.metrics, "name"), ("term", model.glossary, "term")):
        for it in items:
            nodes.append({"id": f"{kind}:{it[key]}", "type": kind, "description": it.get("definition", "")})
            edges += [{"source": f"{kind}:{it[key]}", "target": t, "type": "uses"} for t in it["tables"]]
    for e in model.kg["entities"]:
        nid = f"entity:{e['name']}"
        nodes.append(
            {
                "id": nid,
                "type": "entity",
                "kind": e["kind"],
                "description": e.get("description", ""),
                "synonyms": e.get("synonyms") or [],
                "table": e["table"],
                "filter": e.get("filter"),
                "key": e.get("key"),
                "label": e.get("label") or [],
                "rows": e.get("rows"),
            }
        )
        edges.append({"source": nid, "target": e["table"], "type": "stored_in"})
        if e.get("is_a"):
            edges.append({"source": nid, "target": f"entity:{e['is_a']}", "type": "is_a"})
    for r in model.kg["relations"]:
        edges.append(
            {
                "source": f"entity:{r['subject']}",
                "target": f"entity:{r['object']}",
                "type": "relation",
                "predicate": r["predicate"],
                "cardinality": r.get("cardinality"),
                "via": r.get("via") or [],
                "on": r.get("on"),
                "polymorphic": _poly_meta(r),
                "join": r.get("join"),
                "verified": r.get("verified"),
                "description": r.get("description", ""),
            }
        )
    return {"nodes": nodes, "edges": edges}


def _poly_meta(r: dict[str, Any]) -> dict[str, Any] | None:
    p = r.get("polymorphic")
    return {"column": p.get("column"), "type_column": p.get("type_column"), "type": p.get("type")} if p else None


# ----------------------------------------------------------------------------- knowledge graph docs
def _kg_domain(model: SemanticModel, e: dict[str, Any]) -> str:
    return model.tables[e["table"]].domain or "-"


def _md(s: Any) -> str:
    return str(s or "").replace('"', "#quot;").replace("\n", " ")


def kg_mermaid(model: SemanticModel) -> str:
    ents = model.kg["entities"]
    ids = {e["name"]: f"e{i}" for i, e in enumerate(ents)}
    lines = ["flowchart LR"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in ents:
        groups[_kg_domain(model, e)].append(e)
    for gi, (domain, items) in enumerate(sorted(groups.items())):
        lines.append(f'    subgraph d{gi}["{_md(domain)}"]')
        lines += [f'        {ids[e["name"]]}["{_md(e["name"])}"]' for e in items]
        lines.append("    end")
    for e in ents:
        if e.get("is_a") in ids:
            lines.append(f"    {ids[e['name']]} -.->|is a| {ids[e['is_a']]}")
    for r in model.kg["relations"]:
        if r["subject"] in ids and r["object"] in ids:
            label = r["predicate"].replace("_", " ") + (f" {r['cardinality']}" if r.get("cardinality") else "")
            lines.append(f"    {ids[r['subject']]} -->|{_md(label)}| {ids[r['object']]}")
    return "\n".join(lines)


def kg_doc(model: SemanticModel) -> str:
    ents, rels = model.kg["entities"], model.kg["relations"]
    out = [
        f"# {model.name} - knowledge graph",
        "",
        (
            f"{len(ents)} business entities and {len(rels)} relations mapped onto the database. "
            "Edit [knowledge_graph.yaml](../knowledge_graph.yaml) to change it; "
            "explore it in the [interactive view](knowledge-graph.html)."
        ),
        "",
        "```mermaid",
        kg_mermaid(model),
        "```",
        "",
        "## Entities",
        "",
        "| Entity | Kind | Stored in | Key | Rows | Description |",
        "|---|---|---|---|---|---|",
    ]
    for e in sorted(ents, key=lambda x: (_kg_domain(model, x), x["name"].lower())):
        where = f" WHERE {e['filter']}" if e.get("filter") else ""
        isa = f" (is a {e['is_a']})" if e.get("is_a") else ""
        out.append(
            f"| **{cell(e['name'])}**{cell(isa)} | {e['kind']} | `{cell(e['table'] + where)}` | "
            f"{cell(key_text(e)) or '-'} | {num(e.get('rows'))} | {cell(e.get('description'))} |"
        )
    out += ["", "## Relations", "", "| Relation | Cardinality | In the data | Join |", "|---|---|---|---|"]
    for r in rels:
        out.append(
            f"| {cell(r['subject'])} **{cell(r['predicate'].replace('_', ' '))}** {cell(r['object'])} | "
            f"{r.get('cardinality') or '?'} | {cell(data_note(r)) or '-'} | `{cell(r.get('join'))}` |"
        )
    return "\n".join(out) + "\n"


def _kg_template() -> str:
    """HTML page of the interactive knowledge graph view (vis-network); __TITLE__ and __DATA__ are filled in."""
    return resources.files("sqlmem").joinpath("assets/knowledge-graph.html").read_text(encoding="utf-8")


def kg_html(model: SemanticModel) -> str:
    data = {
        "name": model.name,
        "dialect": model.dialect,
        "entities": [
            {
                "name": e["name"],
                "kind": e["kind"],
                "description": e.get("description", ""),
                "synonyms": e.get("synonyms") or [],
                "domain": _kg_domain(model, e),
                "table": e["table"],
                "filter": e.get("filter"),
                "key": key_text(e),
                "label": e.get("label") or [],
                "attributes": e.get("attributes") or [],
                "is_a": e.get("is_a"),
                "rows": e.get("rows"),
            }
            for e in model.kg["entities"]
        ],
        "relations": [
            {
                "subject": r["subject"],
                "predicate": r["predicate"],
                "object": r["object"],
                "cardinality": r.get("cardinality"),
                "description": r.get("description", ""),
                "join": r.get("join"),
                "facts": data_note(r),
            }
            for r in model.kg["relations"]
        ],
        "tables": sorted({e["table"] for e in model.kg["entities"]}),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(model.name)
    return _kg_template().replace("__TITLE__", title).replace("__DATA__", payload)


# ----------------------------------------------------------------------------- search chunks
def _short(s: str, n: int = 90) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 3] + "..."


def memory_chunk(model: SemanticModel, m: dict[str, Any]) -> Chunk:
    tables = [t for t in m.get("tables") or [] if t in model.tables] or model.tables_in_sql(m.get("sql") or "")
    text = m["text"]
    if m.get("question") and m["question"] != m["text"]:
        text += f"\nQuestion: {m['question']}"
    if m.get("sql"):
        text += f"\nSQL:\n{m['sql']}"
    return Chunk(
        id=f"memory:{m['id']}",
        kind="memory",
        ref=m["id"],
        title=f"Memory ({m['kind']}): {_short(m['text'], 80)}",
        text=text,
        keywords=" ".join(split_identifier(t) for t in tables),
        tables=tables,
        payload={k: m.get(k) for k in ("id", "kind", "text", "question", "sql", "created_at")},
    )


def build_chunks(model: SemanticModel, memories: list[dict[str, Any]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    groups = by_domain(model)
    chunks.append(
        Chunk(
            id="database",
            kind="database",
            ref=model.name,
            title=f"Database {model.name}",
            text="\n".join([model.description, *model.dialect_notes, f"Domains: {', '.join(groups)}"]),
            keywords="database overview",
        )
    )
    for domain, items in groups.items():
        chunks.append(
            Chunk(
                id=f"domain:{domain}",
                kind="domain",
                ref=domain,
                title=f"Domain {domain}",
                text=(
                    model.domains.get(domain, "")
                    + "\nTables: "
                    + "; ".join(f"{t.fqn} - {_short(t.description, 70)}" for t in items)
                ).strip(),
                keywords=split_identifier(domain),
                tables=[t.fqn for t in items],
            )
        )
    for t in model.visible_tables():
        joins = sorted({r.to_table if r.from_table == t.fqn else r.from_table for r in model.relationships_of(t.fqn)})
        cols = "; ".join(
            c.name + (f" ({_short(c.description, 60)})" if c.description else "")
            for c in t.columns.values()
            if not c.housekeeping
        )
        text = "\n".join(
            x
            for x in [
                f"{t.fqn} ({t.type}{', domain ' + t.domain if t.domain else ''}): {t.description}",
                f"Also called: {', '.join(t.synonyms)}" if t.synonyms else "",
                f"Grain: {t.grain}" if t.grain else "",
                " ".join(t.notes),
                f"Columns: {cols}",
                f"Joins to: {', '.join(joins)}" if joins else "",
            ]
            if x
        )
        keywords = " ".join(
            [split_identifier(t.short), t.domain or "", " ".join(t.synonyms)]
            + [split_identifier(c.name) for c in t.columns.values() if not c.housekeeping]
        )
        chunks.append(
            Chunk(
                id=f"table:{t.fqn}",
                kind="table",
                ref=t.fqn,
                title=f"Table {t.fqn}",
                text=text,
                keywords=keywords,
                tables=[t.fqn],
            )
        )
        for c in t.columns.values():
            if c.housekeeping:
                continue
            ctext = "\n".join(
                x
                for x in [
                    f"Column {c.name} of {t.fqn} ({_short(t.description, 100)})",
                    f"{c.type}{', ' + ', '.join(column_flags(c)) if column_flags(c) else ''}",
                    c.description,
                    f"Also called: {', '.join(c.synonyms)}" if c.synonyms else "",
                    column_facts(c, 250),
                ]
                if x
            )
            chunks.append(
                Chunk(
                    id=f"column:{t.fqn}.{c.name}",
                    kind="column",
                    ref=f"{t.fqn}.{c.name}",
                    title=f"Column {t.fqn}.{c.name}",
                    text=ctext,
                    keywords=" ".join([split_identifier(c.name), " ".join(c.synonyms), split_identifier(t.short)]),
                    tables=[t.fqn],
                )
            )
    for i, r in enumerate(r for r in model.relationships if r.source == "curated"):
        chunks.append(
            Chunk(
                id=f"relationship:{i}",
                kind="relationship",
                ref=r.label(),
                title=f"Relationship {r.label()}",
                text=f"{r.description}\nJoin: {r.on_clause(model)}",
                tables=[r.from_table, r.to_table],
            )
        )
    for g in model.glossary:
        chunks.append(
            Chunk(
                id=f"glossary:{g['term']}",
                kind="glossary",
                ref=g["term"],
                title=f"Glossary: {g['term']}",
                text="\n".join(
                    x
                    for x in [
                        str(g.get("definition", "")).strip(),
                        f"Also called: {', '.join(g['synonyms'])}" if g["synonyms"] else "",
                        f"SQL: {str(g.get('sql') or '').strip()}" if g.get("sql") else "",
                    ]
                    if x
                ),
                keywords=" ".join(g["synonyms"]),
                tables=g["tables"],
                payload=_payload(g),
            )
        )
    for m in model.metrics:
        chunks.append(
            Chunk(
                id=f"metric:{m['name']}",
                kind="metric",
                ref=m["name"],
                title=f"Metric: {m['name']}",
                text="\n".join(
                    x
                    for x in [
                        str(m.get("definition", "")).strip(),
                        f"Also called: {', '.join(m['synonyms'])}" if m["synonyms"] else "",
                        f"SQL: {str(m.get('sql') or '').strip()}",
                    ]
                    if x
                ),
                keywords=" ".join(m["synonyms"]),
                tables=m["tables"],
                payload=_payload(m),
            )
        )
    for i, e in enumerate(model.examples):
        chunks.append(
            Chunk(
                id=f"example:{i}",
                kind="example",
                ref=e["question"],
                title=f"Example: {e['question']}",
                text=f"{e['question']}\n{str(e.get('notes') or '').strip()}\nSQL:\n{str(e.get('sql') or '').strip()}",
                keywords=" ".join(split_identifier(t) for t in e["tables"]),
                tables=e["tables"],
                payload=_payload(e),
            )
        )
    for routine in model.routines:
        chunks.append(
            Chunk(
                id=f"routine:{routine['fqn']}",
                kind="routine",
                ref=routine["fqn"],
                title=f"{routine['type']} {routine['fqn']}",
                text=f"{routine.get('comment') or ''}\n{(routine.get('definition') or '')[:1500]}",
                keywords=split_identifier(routine["name"]),
                tables=model.tables_in_sql(routine.get("definition") or ""),
            )
        )
    chunks += kg_chunks(model)
    chunks += [memory_chunk(model, m) for m in memories]
    return chunks


def kg_chunks(model: SemanticModel) -> list[Chunk]:
    out = []
    ents = {e["name"]: e for e in model.kg["entities"]}
    children: dict[str, list[str]] = defaultdict(list)
    for e in ents.values():
        if e.get("is_a"):
            children[e["is_a"]].append(e["name"])

    def family(name: str) -> list[str]:
        """The entity and all its subtypes: a parent's relations also hold for its subtypes."""
        seen, stack = [], [name]
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.append(n)
                stack += children.get(n, [])
        return seen

    def words(names: list[str]) -> str:
        return " ".join(f"{n} {' '.join(ents[n].get('synonyms') or [])}" for n in names if n in ents)

    rels_of: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in model.kg["relations"]:
        rels_of[r["subject"]].append(r)
        rels_of[r["object"]].append(r)
    for e in model.kg["entities"]:
        t = model.tables[e["table"]]
        where = f" WHERE {e['filter']}" if e.get("filter") else ""
        isa = f", is a {e['is_a']}" if e.get("is_a") else ""
        rel_text = "; ".join(
            f"{r['subject']} {r['predicate'].replace('_', ' ')} {r['object']}" for r in rels_of[e["name"]]
        )
        text = "\n".join(
            x
            for x in [
                f"{e['name']} ({e['kind']}{isa}): {e.get('description', '')}",
                f"Also called: {', '.join(e['synonyms'])}" if e.get("synonyms") else "",
                f"Stored in {e['table']}{where}"
                + (f"; key {key_text(e)}" if e.get("key") else "")
                + (f"; label {', '.join(e['label'])}" if e.get("label") else ""),
                f"Attributes: {', '.join(e['attributes'])}" if e.get("attributes") else "",
                f"Relations: {rel_text}" if rel_text else "",
            ]
            if x
        )
        payload = {k: e.get(k) for k in ("name", "kind", "description", "table", "filter", "label", "is_a", "rows")}
        payload["key"] = key_text(e)
        out.append(
            Chunk(
                id=f"entity:{e['name']}",
                kind="entity",
                ref=e["name"],
                title=f"Entity {e['name']}",
                text=text,
                keywords=" ".join([e["name"], " ".join(e.get("synonyms") or []), split_identifier(t.short)]),
                tables=[e["table"]],
                payload=payload,
            )
        )
    for r in model.kg["relations"]:
        words_ = r["predicate"].replace("_", " ")
        subs, objs = family(r["subject"]), family(r["object"])
        also = [*subs[1:], *objs[1:]]
        poly = _poly_meta(r)
        poly_text = (
            f"Polymorphic reference: {', '.join(poly['column'])} points to {r['object']} when "
            f"{poly['type_column']} = {poly['type']!r}"
            if poly
            else ""
        )
        payload = {k: r.get(k) for k in ("subject", "predicate", "object", "cardinality", "join")}
        payload["facts"] = data_note(r)
        out.append(
            Chunk(
                id=f"relation:{r['subject']}|{r['predicate']}|{r['object']}",
                kind="relation",
                ref=f"{r['subject']} {r['predicate']} {r['object']}",
                title=f"Relation: {r['subject']} {words_} {r['object']}",
                text="\n".join(
                    x
                    for x in [
                        r.get("description", ""),
                        poly_text,
                        f"Also applies to: {', '.join(also)}" if also else "",
                        f"Cardinality: {r['cardinality']}" if r.get("cardinality") else "",
                        f"Join: {r.get('join')}",
                    ]
                    if x
                ),
                keywords=" ".join([words_, words(subs), words(objs)]),
                tables=r.get("_tables") or [],
                payload=payload,
            )
        )
    return out


def _payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v for k, v in item.items() if k in ("name", "term", "question", "definition", "sql", "notes", "synonyms")
    }


# ----------------------------------------------------------------------------- context pack
KIND_WEIGHT = {
    "table": 1.0,
    "column": 0.8,
    "memory": 1.0,
    "example": 0.9,
    "metric": 0.8,
    "glossary": 0.7,
    "entity": 1.0,
    "relation": 0.9,
    "relationship": 0.6,
    "domain": 0.25,
    "routine": 0.3,
    "database": 0.0,
}
# Tables scoring below this fraction of the best table are left out of the context (listed as "other").
TABLE_SCORE_RATIO = 0.5


def rank_tables(model: SemanticModel, hits: list[Hit]) -> list[tuple[float, str]]:
    contrib: dict[str, list[float]] = defaultdict(list)
    for h in hits:
        w = KIND_WEIGHT.get(h.kind, 0.5)
        for t in h.tables:
            if t in model.tables and not model.tables[t].hidden:
                contrib[t].append(h.score * w)
    scored = [(sum(x * 0.5**i for i, x in enumerate(sorted(v, reverse=True)[:4])), t) for t, v in contrib.items()]
    return sorted(scored, reverse=True)


ValueMatch = tuple[str, str, str, Any]
# Tables holding a literal from the question are added on top of the retrieval budget (at most this many).
MAX_VALUE_TABLES = 3


def select_tables(
    model: SemanticModel, question: str, hits: list[Hit], max_tables: int = 6
) -> tuple[list[tuple[float, str]], list[ValueMatch], list[str]]:
    """Rank tables for a question; returns (ranked tables, value matches, tables chosen for the context).

    Retrieval ranking and value matches are separate evidence: a literal found in a column's value dictionary
    (e.g. 'Canada') adds that table, but never pushes a retrieved table (e.g. a bridge table named by the
    knowledge graph) out of the context.
    """
    ranked = rank_tables(model, hits)
    values = model.match_values(question)
    chosen: list[str] = []
    if ranked:
        top = ranked[0][0]
        chosen = [t for s, t in ranked if s >= TABLE_SCORE_RATIO * top][:max_tables]
    score = {t: s for s, t in ranked}
    extra = sorted({t for _p, t, _c, _v in values if t not in chosen}, key=lambda t: (-score.get(t, 0.0), t))
    return ranked, values, chosen + extra[:MAX_VALUE_TABLES]


def render_context(model: SemanticModel, question: str, hits: list[Hit], max_tables: int = 6) -> str:
    ranked, values, chosen = select_tables(model, question, hits, max_tables)
    tree, rels = model.connect(chosen, max_hops=3, max_extra=3)

    out = [f"# SQL context for: {question}", ""]
    src = model.catalog.get("source", {})
    out.append(f"Database: {model.name} | dialect: {src.get('dialect')} {src.get('server_version') or ''}".rstrip())
    if model.dialect_notes:
        out += ["", "## Rules for writing SQL against this database"] + [f"- {n}" for n in model.dialect_notes]
    if values:
        out += ["", "## Values from the question found in the data"]
        out += [f'- "{phrase}" -> {t}.{model.tables[t].columns[c].sql_name} = {lit(v)}' for phrase, t, c, v in values]

    concepts = [h for h in hits if h.kind == "entity"][:5]
    links = [h for h in hits if h.kind == "relation"][:6]
    if concepts or links:
        out += ["", "## Business concepts (knowledge graph)"]
        for h in concepts:
            p = h.payload
            isa = f", is a {p['is_a']}" if p.get("is_a") else ""
            rows = f", {num(p['rows'])} rows" if isinstance(p.get("rows"), int) else ""
            where = f" WHERE {p['filter']}" if p.get("filter") else ""
            key = f"; key {p['key']}" if p.get("key") else ""
            label = f"; name column {', '.join(p['label'])}" if p.get("label") else ""
            out.append(
                f"- **{p['name']}** ({p.get('kind')}{isa}{rows}) = `{p['table']}{where}`{key}{label}"
                + (f": {_short(p.get('description') or '', 140)}" if p.get("description") else "")
            )
        for h in links:
            p = h.payload
            facts = ", ".join(x for x in (p.get("cardinality") or "?", p.get("facts") or "") if x)
            out.append(f"- {p['subject']} --{p['predicate']}--> {p['object']} ({facts}): `{p.get('join')}`")

    mems = [h for h in hits if h.kind == "memory"][:5]
    if mems:
        out += ["", "## Learned memories (most relevant first)"]
        for h in mems:
            p = h.payload
            line = f"- [{p.get('kind')}] {p.get('text')}"
            if p.get("sql"):
                line += f"\n  ```sql\n  {p['sql'].strip().replace(chr(10), chr(10) + '  ')}\n  ```"
            out.append(line)
    defs = [h for h in hits if h.kind in ("metric", "glossary")][:5]
    if defs:
        out += ["", "## Business definitions"]
        for h in defs:
            p = h.payload
            name = p.get("name") or p.get("term")
            sql = f" SQL: `{str(p['sql']).strip()}`" if p.get("sql") else ""
            out.append(f"- **{name}** ({h.kind}): {str(p.get('definition', '')).strip()}{sql}")
    exs = [h for h in hits if h.kind == "example"][:3]
    if exs:
        out += ["", "## Verified example queries (adapt, do not copy blindly)"]
        for h in exs:
            out += [f"Q: {h.payload.get('question')}", "```sql", str(h.payload.get("sql", "")).strip(), "```"]

    if tree:
        out += ["", "## Relevant tables"]
        for fqn in tree:
            table = model.tables[fqn]
            tag = "" if fqn in chosen else "  _(bridge table for joins)_"
            out += ["", compact_card(model, table) + tag]
        if rels:
            out += ["", "## Join paths"] + [_rel_line(model, r) for r in rels]
    else:
        out += ["", "_No matching tables found - try different wording or call list_tables._"]
    more = [(s, t) for s, t in ranked if t not in tree][:6]
    if more:
        out += ["", "## Other possibly relevant tables (use describe_table for details)"]
        out += [f"- {t}: {_short(model.tables[t].description, 100) or '(no description)'}" for _, t in more]
    return "\n".join(out) + "\n"
