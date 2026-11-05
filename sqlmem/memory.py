"""Long-term memory: learned facts, rules, preferences, corrections and verified question->SQL pairs.

Stored as JSON Lines (one memory per line) so it is human-reviewable and diff-friendly in git;
the search index is derived from it and can always be rebuilt.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

KINDS = ("fact", "rule", "preference", "correction", "query")


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class MemoryStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        items = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in items), encoding="utf-8")
        tmp.replace(self.path)

    def add(
        self,
        text: str,
        kind: str = "fact",
        question: str | None = None,
        sql: str | None = None,
        tables: list[str] | None = None,
        tags: list[str] | None = None,
        source: str = "cli",
    ) -> tuple[dict[str, Any], bool]:
        """Add a memory. Returns (memory, created); identical memories are not duplicated."""
        kind = (kind or "fact").lower()
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        text = (text or "").strip() or (question or "").strip()
        if not text:
            raise ValueError("Memory text (or question) is required")
        if kind == "query" and not (sql or "").strip():
            raise ValueError("kind='query' requires the verified SQL")
        key = "|".join((kind, _norm(text), _norm(question), _norm(sql)))
        mid = "m_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        items = self.load()
        for m in items:
            if m.get("id") == mid:
                return m, False
        mem: dict[str, Any] = {"id": mid, "kind": kind, "text": text}
        if question:
            mem["question"] = question.strip()
        if sql:
            mem["sql"] = sql.strip()
        mem["tables"] = list(dict.fromkeys(tables or []))
        if tags:
            mem["tags"] = list(dict.fromkeys(tags))
        mem["created_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        mem["source"] = source
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(mem, ensure_ascii=False) + "\n")
        return mem, True

    def remove(self, mid: str) -> bool:
        items = self.load()
        kept = [m for m in items if m.get("id") != mid]
        if len(kept) == len(items):
            return False
        self._write(kept)
        return True
