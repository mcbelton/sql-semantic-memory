"""Draft semantic.yaml: a complete skeleton of every table/column, gaps optionally filled by an LLM.

Curated (non-empty) content is never overwritten. LLM-written tables are tagged `source: llm-draft`
so a human can review them (delete the tag once reviewed).
"""

from __future__ import annotations

import copy
import fnmatch
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .model import SemanticModel, Table
from .render import column_facts, column_flags

SYSTEM_PROMPT = (
    "You are a senior data steward documenting a relational database for analysts and AI assistants. "
    "Given one table's schema, relationships and data profile, write precise business descriptions. "
    "Never invent facts that cannot be inferred from the input; if the meaning is unclear say 'Unclear: ...'. "
    "Respond with a single JSON object only."
)


def table_prompt(model: SemanticModel, t: Table, include_values: bool = True) -> str:
    lines = [
        f"Database: {model.name} ({model.dialect}). {model.description}".strip(),
        f"Table: {t.fqn} ({t.type}, domain {t.domain or '-'}, {t.row_count if t.row_count is not None else '?'} rows)",
    ]
    if t.description:
        lines.append(f"Current description: {t.description}")
    lines.append("Columns:")
    for c in t.columns.values():
        facts = column_facts(c, 10) if include_values else ""
        lines.append(
            f"- {c.name} ({', '.join([c.type, *column_flags(c)])})"
            + (f": {c.description}" if c.description else "")
            + (f" | {facts}" if facts else "")
        )
    rels = model.relationships_of(t.fqn)
    if rels:
        lines.append("Relationships: " + "; ".join(r.label() for r in rels[:25]))
    lines.append(
        'Return JSON: {"description": "1-2 sentences: what one row represents and what the table is used for", '
        '"synonyms": ["business words people may use for this table"], '
        '"columns": {"<column name>": "short description; explain codes/flags when the values make it clear"}}'
    )
    return "\n".join(lines)


def suggest_with_llm(
    model: SemanticModel,
    tables: list[Table],
    llm: Any,
    workers: int = 4,
    include_values: bool = True,
    log: Callable[[str], None] | None = None,
) -> dict[str, dict[str, Any]]:
    """`llm` is a sqlmem.llm.LLM (or anything with complete_json(system, user) -> dict)."""

    def one(t: Table) -> tuple[str, dict[str, Any]]:
        try:
            return t.fqn, llm.complete_json(SYSTEM_PROMPT, table_prompt(model, t, include_values))
        except Exception as e:
            if log:
                log(f"  LLM failed for {t.fqn}: {str(e).splitlines()[0][:200]}")
            return t.fqn, {}

    out: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i, (fqn, data) in enumerate(pool.map(one, tables), 1):
            out[fqn] = data
            if log:
                log(f"  [{i}/{len(tables)}] {fqn}: {'ok' if data else 'no suggestion'}")
    return out


def draft_semantic(
    model: SemanticModel,
    existing: dict[str, Any] | None,
    suggestions: dict[str, dict[str, Any]] | None = None,
    only: list[str] | None = None,
) -> dict[str, Any]:
    out = copy.deepcopy(existing or {})
    db = out.setdefault("database", {})
    db.setdefault("name", model.name)
    db.setdefault("description", model.description or "")
    db.setdefault("dialect_notes", model.dialect_notes or [])
    domains = out.setdefault("domains", {})
    for d in sorted({t.domain for t in model.visible_tables() if t.domain}):
        domains.setdefault(d, "")
    tables = out.setdefault("tables", {})
    suggestions = suggestions or {}
    for t in model.tables.values():
        if only and not any(fnmatch.fnmatch(t.fqn.lower(), p.lower()) for p in only):
            continue
        key = next((k for k in tables if model.resolve(str(k)) is t), t.fqn)
        current = tables.get(key)
        entry: dict[str, Any] = {"description": current} if isinstance(current, str) else dict(current or {})
        if entry.get("hidden"):
            tables[key] = entry
            continue
        s = suggestions.get(t.fqn) or {}
        used_llm = False
        if not entry.get("description"):
            entry["description"] = t.description or str(s.get("description") or "").strip()
            used_llm |= bool(not t.description and s.get("description"))
        if not entry.get("synonyms") and s.get("synonyms"):
            entry["synonyms"] = [str(x) for x in s["synonyms"]][:8]
            used_llm = True
        cols = entry.get("columns") or {}
        raw_cols = s.get("columns")
        scols: dict[str, Any] = raw_cols if isinstance(raw_cols, dict) else {}
        merged: dict[str, Any] = {}
        for c in t.columns.values():
            current_col = cols.get(c.name)
            ce: dict[str, Any] = (
                {"description": current_col}
                if isinstance(current_col, str) or current_col is None
                else dict(current_col)
            )
            if not ce.get("description"):
                ce["description"] = c.description or str(scols.get(c.name) or "").strip()
                used_llm |= bool(not c.description and scols.get(c.name))
            merged[c.name] = ce if len(ce) > 1 else (ce.get("description") or "")
        entry["columns"] = merged
        if used_llm:
            entry["source"] = "llm-draft"
        tables[key] = entry
    for section in ("relationships", "glossary", "metrics", "examples"):
        out.setdefault(section, [])
    return out
