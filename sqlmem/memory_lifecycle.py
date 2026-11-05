"""Authoritative private SQLite lifecycle; the BM25 projection is disposable.

All authoritative writes and their events/lineage share BEGIN IMMEDIATE. Reads also
serialize cache refresh against writers so a stale projection never leaks an old head.
Nothing in this module executes remembered prose or sends it to a model.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import sqlite3
import stat
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from .memory_safety import (
    INSTRUCTIONS,
    PROPOSAL_SCHEMA,
    TYPES,
    WARNINGS,
    array,
    canonical,
    digest,
    fail,
    fields,
    integer,
    messages,
    opaque,
    redactions,
    sanitize,
    text,
)
from .store import Chunk, Index, fts_query

SCHEMA = """
CREATE TABLE sources(
 conversation_id TEXT NOT NULL, revision INTEGER NOT NULL, session_id TEXT NOT NULL,
 messages_json TEXT NOT NULL, content_hash TEXT NOT NULL, sanitizer_version INTEGER NOT NULL,
 redaction_counts_json TEXT NOT NULL, created_seq INTEGER NOT NULL,
 PRIMARY KEY(conversation_id, revision));
CREATE TABLE items(
 memory_id TEXT PRIMARY KEY, type TEXT NOT NULL, key TEXT NOT NULL, session_id TEXT NOT NULL,
 head_revision INTEGER NOT NULL, UNIQUE(type, session_id, key));
CREATE TABLE revisions(
 memory_id TEXT NOT NULL REFERENCES items(memory_id), revision INTEGER NOT NULL,
 text TEXT NOT NULL, steps_json TEXT NOT NULL, tables_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','archived')), origin TEXT NOT NULL,
 previous_revision INTEGER, restored_from INTEGER, created_seq INTEGER NOT NULL,
 PRIMARY KEY(memory_id, revision));
CREATE TABLE lineage(
 memory_id TEXT NOT NULL, revision INTEGER NOT NULL,
 conversation_id TEXT NOT NULL, source_revision INTEGER NOT NULL, message_indices_json TEXT NOT NULL,
 FOREIGN KEY(memory_id,revision) REFERENCES revisions(memory_id,revision),
 FOREIGN KEY(conversation_id,source_revision) REFERENCES sources(conversation_id,revision),
 PRIMARY KEY(memory_id,revision,conversation_id,source_revision));
CREATE TABLE events(seq INTEGER PRIMARY KEY, at TEXT NOT NULL, operation TEXT NOT NULL,
 operation_key TEXT UNIQUE, payload_json TEXT NOT NULL);
CREATE INDEX events_target ON events(operation,json_extract(payload_json,'$.memory_id'),
 json_extract(payload_json,'$.revision'));
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO meta VALUES('schema_version','1'),('sanitizer_version','1'),
 ('source_generation','0'),('private_index_generation','0');
PRAGMA user_version=1;
"""
HEADS = """SELECT i.*, r.text, r.steps_json, r.tables_json, r.status, r.origin,
 r.previous_revision, r.restored_from, r.created_seq, r.revision
 FROM items i JOIN revisions r ON i.memory_id=r.memory_id AND i.head_revision=r.revision"""


def _safe_path(path: Path) -> None:
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            fail("unsafe_path", "private", "Remove symlinks/reparse points; use a private local directory.")


def _private_file(path: Path) -> None:
    """Create with private permissions before SQLite writes any source or projection content."""
    _safe_path(path)
    if not path.exists():
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # Another process may initialize the same new KB before BEGIN IMMEDIATE.
            _safe_path(path)
        else:
            os.close(fd)
    if os.name != "nt":
        path.chmod(0o600)


class LifecycleStore:
    def __init__(self, root: Path | str):
        self.root = Path(root) / "private"
        self.path = self.root / "memory.sqlite3"
        self.index_path = self.root / "memory-index.db"
        self._con: sqlite3.Connection | None = None
        self._index: Index | None = None
        self._lock = threading.RLock()

    def close(self) -> None:
        with self._lock:
            if self._index is not None:
                self._index.close()
                self._index = None
            if self._con is not None:
                self._con.close()
                self._con = None

    def _paths(self) -> None:
        # A symlinked KB ancestor also relocates the private root.
        for path in (self.root, *self.root.absolute().parents):
            _safe_path(path)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in self.root.iterdir():
            _safe_path(path)
        ignore = self.root / ".gitignore"
        if not ignore.exists() or ignore.read_text(encoding="utf-8") != "*\n":
            ignore.write_text("*\n", encoding="utf-8")
        if os.name != "nt":
            self.root.chmod(0o700)
            for path in self.root.iterdir():
                if path.is_file():
                    path.chmod(0o600)

    def _connection(self) -> sqlite3.Connection:
        self._paths()
        if self._con is None:
            _private_file(self.path)
            con = sqlite3.connect(self.path, isolation_level=None, timeout=5, check_same_thread=False)
            con.row_factory = sqlite3.Row
            try:
                con.execute("PRAGMA foreign_keys=ON")
                con.execute("PRAGMA busy_timeout=5000")
                con.execute("BEGIN IMMEDIATE")
                version = con.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1):
                    fail("unsupported_schema", "schema", "Use a compatible sqlmem version; back up the store.")
                if version == 0:
                    # executescript would implicitly commit: execute each static DDL statement instead.
                    if con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]:
                        fail("unsupported_schema", "schema", "Use a new private directory or restore a backup.")
                    for statement in SCHEMA.split(";"):
                        if statement.strip():
                            con.execute(statement)
                page_size = con.execute("PRAGMA page_size").fetchone()[0]
                con.execute(f"PRAGMA max_page_count={1073741824 // page_size}")
                con.commit()
            except BaseException:
                con.rollback()
                con.close()
                raise
            self._con = con
            self._paths()
        return self._con

    @contextlib.contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            con: sqlite3.Connection | None = None
            try:
                con = self._connection()
                con.execute("BEGIN IMMEDIATE")
                if con.execute("PRAGMA user_version").fetchone()[0] != 1:
                    fail("unsupported_schema", "schema", "Use a compatible sqlmem version; back up the store.")
                yield con
                con.commit()
            except sqlite3.Error as error:
                if con is not None:
                    con.rollback()
                code = getattr(error, "sqlite_errorcode", None)
                if code is not None:
                    code &= 0xFF
                elif str(error) == "database or disk is full":
                    code = sqlite3.SQLITE_FULL
                elif str(error) in ("database is locked", "database table is locked"):
                    code = sqlite3.SQLITE_BUSY
                if code == sqlite3.SQLITE_FULL:
                    fail(
                        "store_full",
                        "private",
                        "Back up with SQLite backup API and relocate; originals are not deleted.",
                    )
                if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                    fail("store_busy", "private", "Another writer held the store for 5 seconds; retry.")
                fail(
                    "store_failed", "private", "Check storage permissions/integrity and restore a backup if necessary."
                )
            except OSError:
                if con is not None:
                    con.rollback()
                fail("storage_failed", "private", "Check local directory permissions and free space.")
            except BaseException:
                if con is not None:
                    con.rollback()
                raise

    @staticmethod
    def _seq(con: sqlite3.Connection) -> int:
        return int(con.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0])

    def _event(
        self, con: sqlite3.Connection, operation: str, key: str | None = None, payload: dict[str, Any] | None = None
    ) -> int:
        cursor = con.execute(
            "INSERT INTO events(at,operation,operation_key,payload_json) VALUES(?,?,?,?)",
            (dt.datetime.now(dt.UTC).isoformat(), operation, key, canonical(payload or {})),
        )
        seq = cursor.lastrowid
        assert seq is not None
        con.execute("UPDATE meta SET value=? WHERE key='source_generation'", (str(seq),))
        return seq

    @staticmethod
    def _report(operation: str, **values: Any) -> dict[str, Any]:
        return {
            "operation": operation,
            "items": [],
            "accepted": 0,
            "unchanged": 0,
            "archived": 0,
            "sources": [],
            "inferred": True,
            "index_pending": False,
            "warnings": list(WARNINGS),
            "next_cursor": "",
            **values,
        }

    @staticmethod
    def _replay(
        con: sqlite3.Connection, key: str, request_hash: str | None = None, field: str = "replay"
    ) -> dict[str, Any] | None:
        row = con.execute("SELECT payload_json FROM events WHERE operation_key=?", (key,)).fetchone()
        if row:
            payload = json.loads(row[0])
            if request_hash is not None and payload.get("request_hash") != request_hash:
                fail("conflicting_replay", field, "Use a fresh task or feedback ID.")
            report: dict[str, Any] = payload["report"]
            return report
        return None

    def _finish(
        self, con: sqlite3.Connection, seq: int, report: dict[str, Any], metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # Persist a recoverable report BEFORE publishing any projection. A crash here leaves
        # a committed event and a stale cache, never a cache stamped with rolled-back history.
        report["index_pending"] = True
        con.execute(
            "UPDATE events SET payload_json=? WHERE seq=?", (canonical({**(metadata or {}), "report": report}), seq)
        )
        con.commit()
        try:
            # Serialize refreshers with authoritative writers. Sequence + heads come from
            # this same committed snapshot, even if a different writer committed in between.
            con.execute("BEGIN IMMEDIATE")
            self._refresh(con)
            report["index_pending"] = False
            con.execute(
                "UPDATE events SET payload_json=? WHERE seq=?", (canonical({**(metadata or {}), "report": report}), seq)
            )
            con.commit()
        except (sqlite3.Error, OSError, ValueError):
            # The source commit is irrevocable. Cache/report-status failure is advisory.
            con.rollback()
            report["index_pending"] = True
            if self._index is not None:
                self._index.close()
                self._index = None
        return report

    def _source(self, con: sqlite3.Connection, cid: str, revision: int = 0) -> sqlite3.Row:
        row = con.execute(
            "SELECT * FROM sources WHERE conversation_id=? "
            + ("AND revision=?" if revision else "ORDER BY revision DESC LIMIT 1"),
            (cid, revision) if revision else (cid,),
        ).fetchone()
        if row is None:
            fail("missing_source", "source", "Submit the conversation or select an existing revision.")
        return cast(sqlite3.Row, row)

    def submit_conversation(
        self,
        conversation_id: str,
        messages_data: list[dict[str, Any]],
        session_id: str = "",
        expected_revision: int = 0,
        redact: list[str] | None = None,
    ) -> dict[str, Any]:
        opaque(conversation_id, "conversation_id")
        if conversation_id.startswith("__feedback_"):
            fail("reserved_id", "conversation_id")
        opaque(session_id, "session_id", True)
        integer(expected_revision, "expected_revision")
        clean, counts = messages(messages_data, redactions(redact))
        content_hash = digest({"messages": clean, "session_id": session_id})
        with self._transaction() as con:
            latest = con.execute(
                "SELECT * FROM sources WHERE conversation_id=? ORDER BY revision DESC LIMIT 1", (conversation_id,)
            ).fetchone()
            if latest and latest["content_hash"] == content_hash:
                report = self._replay(con, f"submit:{conversation_id}:{latest['revision']}")
                assert report is not None
                return report
            current = latest["revision"] if latest else 0
            if expected_revision != current:
                fail("stale_revision", "expected_revision", "Read the latest source and retry with its revision.")
            revision = current + 1
            seq = self._event(con, "submit", f"submit:{conversation_id}:{revision}")
            self._insert_source(con, conversation_id, revision, session_id, clean, counts, seq)
            report = self._report(
                "submit",
                conversation_id=conversation_id,
                revision=revision,
                redaction_counts=counts,
                sources=[{"conversation_id": conversation_id, "revision": revision}],
            )
            return self._finish(con, seq, report)

    @staticmethod
    def _insert_source(
        con: sqlite3.Connection,
        cid: str,
        revision: int,
        session: str,
        clean: list[dict[str, str]],
        counts: dict[str, int],
        seq: int,
    ) -> None:
        con.execute(
            "INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)",
            (
                cid,
                revision,
                session,
                canonical(clean),
                digest({"messages": clean, "session_id": session}),
                1,
                canonical(counts),
                seq,
            ),
        )

    @staticmethod
    def _task_id(cid: str, revision: int, seq: int) -> str:
        return f"{cid}:{revision}:{seq}:{digest([cid, revision, seq, 1])}"

    def memory_task(self, conversation_id: str, revision: int = 0, tables: list[str] | None = None) -> dict[str, Any]:
        opaque(conversation_id, "conversation_id")
        integer(revision, "revision")
        with self._transaction() as con:
            source = self._source(con, conversation_id, revision)
            seq = self._seq(con)
            task_id = self._task_id(conversation_id, source["revision"], seq)
            words = set(re.findall(r"\w+", source["messages_json"].lower()))
            ordered_tables = sorted(
                set(tables or []), key=lambda name: (-len(words & set(re.findall(r"\w+", name.lower()))), name)
            )
            hints: list[str] = []
            used = 2  # canonical JSON array brackets
            for name in ordered_tables:
                size = len(canonical(name).encode("utf-8")) + int(bool(hints))
                if used + size <= 8192:
                    hints.append(name)
                    used += size
            omitted = len(ordered_tables) - len(hints)
            heads = con.execute(
                HEADS + " WHERE i.type!='working' OR i.session_id=?", (source["session_id"],)
            ).fetchall()
            heads.sort(key=lambda r: (-len(words & set(re.findall(r"\w+", r["text"].lower()))), r["memory_id"]))
            excerpts: list[dict[str, Any]] = []
            for row in heads:
                candidate = {
                    k: row[k] for k in ("memory_id", "type", "key", "session_id", "revision", "text", "status")
                }
                candidate["untrusted"] = True
                if len(excerpts) == 50:
                    break
                if len(canonical([*excerpts, candidate]).encode("utf-8")) <= 16384:
                    excerpts.append(candidate)
            data = {
                "task_id": task_id,
                "source": {
                    "conversation_id": conversation_id,
                    "revision": source["revision"],
                    "session_id": source["session_id"],
                    "messages": json.loads(source["messages_json"]),
                    "untrusted": True,
                },
                "existing_memory_excerpts": excerpts,
                "table_hints": hints,
                "table_hints_omitted": omitted,
                "proposal_schema": PROPOSAL_SCHEMA,
            }
            user = canonical(data)
            text(INSTRUCTIONS + user, "task", 65536)
            return self._report(
                "task",
                task_id=task_id,
                instructions=INSTRUCTIONS,
                system=INSTRUCTIONS,
                user=user,
                proposal_schema=PROPOSAL_SCHEMA,
                revision=source["revision"],
                conversation_id=conversation_id,
                event_seq=seq,
                table_hints_omitted=omitted,
                warnings=[
                    *WARNINGS,
                    *(
                        [
                            (
                                f"{omitted} table hints omitted to fit the 8 KiB hint budget; "
                                "all canonical catalog tables remain valid in proposals."
                            )
                        ]
                        if omitted
                        else []
                    ),
                ],
            )

    def _parse_task(self, con: sqlite3.Connection, token: Any) -> sqlite3.Row:
        text(token, "task_id", 256, 1)
        parts = token.split(":")
        if len(parts) != 4:
            fail("invalid_task", "task_id", "Request a fresh memory_task.")
        cid, rev, seq, _hash = parts
        opaque(cid, "task_id")
        if not rev.isascii() or not rev.isdigit() or not seq.isascii() or not seq.isdigit():
            fail("invalid_task", "task_id")
        revision, event_seq = integer(int(rev), "task_id", 1), integer(int(seq), "task_id")
        if token != self._task_id(cid, revision, event_seq):
            fail("invalid_task", "task_id", "Request a fresh memory_task.")
        if self._seq(con) != event_seq:
            fail("stale_task", "task_id", "Request a fresh memory_task and retry.")
        return self._source(con, cid, revision)

    def save_memory(
        self, proposal: dict[str, Any], tables: list[str] | None = None, origin: str = "caller"
    ) -> dict[str, Any]:
        if origin not in ("caller", "model"):
            fail("invalid_origin", "origin")
        fields(proposal, {"task_id", "items"}, "proposal")
        text(canonical(proposal), "proposal", 65536, 1)
        text(proposal["task_id"], "task_id", 256, 1)
        array(proposal["items"], "items", 32)
        # Sanitize BEFORE hashing: no raw proposal values or hashes of secrets are persisted.
        clean = json.loads(canonical(proposal))
        for entry in clean["items"]:
            fields(entry, {"type", "key", "text", "steps", "tables", "message_indices", "base_revision"}, "items")
            entry["text"] = sanitize(text(entry["text"], "text", 2048, 1))[0]
            text(entry["text"], "text", 2048, 1)
            entry["steps"] = [sanitize(text(s, "steps", 512, 1))[0] for s in array(entry["steps"], "steps", 16)]
            for step in entry["steps"]:
                text(step, "steps", 512, 1)
        text(canonical(clean), "proposal", 65536, 1)
        request_hash = digest(clean)
        with self._transaction() as con:
            replay = self._replay(con, f"save:{clean['task_id']}", request_hash)
            if replay is not None:
                return replay
            source = self._parse_task(con, clean["task_id"])
            validated: list[tuple[dict[str, Any], sqlite3.Row | None, str]] = []
            seen: set[tuple[str, str, str]] = set()
            for entry in clean["items"]:
                kind = entry["type"]
                if not isinstance(kind, str) or kind not in TYPES:
                    fail("invalid_type", "type")
                key = opaque(entry["key"], "key")
                session = source["session_id"] if kind == "working" else ""
                if kind == "working" and not session:
                    fail("missing_session", "session_id", "Working memory requires a source session.")
                scoped_key = (kind, session, key)
                if scoped_key in seen:
                    fail("duplicate_key", "items")
                seen.add(scoped_key)
                if bool(entry["steps"]) != (kind == "procedural"):
                    fail("invalid_steps", "steps", "Only procedural items require 1..16 steps.")
                names = array(entry["tables"], "tables", 16)
                if any(not isinstance(t, str) or t not in (tables or []) for t in names):
                    fail("unknown_table", "tables", "Use canonical existing table names from the task.")
                indices = array(entry["message_indices"], "message_indices", 100, 1)
                for index in indices:
                    integer(index, "message_indices", 0, len(json.loads(source["messages_json"])) - 1)
                entry["message_indices"] = sorted(set(indices))
                base = integer(entry["base_revision"], "base_revision")
                head = con.execute(HEADS + " WHERE i.type=? AND i.session_id=? AND i.key=?", scoped_key).fetchone()
                if base != (head["revision"] if head else 0):
                    fail("stale_revision", "base_revision", "Request a fresh task and use the current head revision.")
                validated.append((entry, head, session))
            operation = "learn" if origin == "model" else "save"
            seq = self._event(con, operation, f"save:{clean['task_id']}")
            records, accepted, unchanged = [], 0, 0
            for entry, head, session in validated:
                link = {
                    "conversation_id": source["conversation_id"],
                    "revision": source["revision"],
                    "message_indices": entry["message_indices"],
                }
                identical = head is not None and self._same(head, entry)
                if identical:
                    assert head is not None
                    mid, revision = head["memory_id"], head["revision"]
                    unchanged += 1
                    # Support links are append-only events, not changes to an accepted revision.
                    self._event(con, "support", payload={"memory_id": mid, "revision": revision, "source": link})
                else:
                    mid = head["memory_id"] if head else "am_" + uuid.uuid4().hex
                    revision = head["revision"] + 1 if head else 1
                    if head is None:
                        con.execute(
                            "INSERT INTO items VALUES(?,?,?,?,?)", (mid, entry["type"], entry["key"], session, revision)
                        )
                    self._append(
                        con,
                        mid,
                        revision,
                        entry["text"],
                        entry["steps"],
                        entry["tables"],
                        "active",
                        origin,
                        seq,
                        [link],
                    )
                    accepted += 1
                records.append({"memory_id": mid, "revision": revision})
            manifest = self._caps(con)
            report = self._report(
                operation,
                items=[self._record(con, r["memory_id"]) for r in records],
                accepted=accepted,
                unchanged=unchanged,
                archived=len(manifest),
                manifest=manifest,
                sources=[{"conversation_id": source["conversation_id"], "revision": source["revision"]}],
            )
            return self._finish(
                con,
                seq,
                report,
                {
                    "request_hash": request_hash,
                    "origin": origin,
                    "supersedes": [
                        {"memory_id": h["memory_id"], "revision": h["revision"]}
                        for _, h, _ in validated
                        if h is not None
                    ],
                },
            )

    @staticmethod
    def _same(head: sqlite3.Row, entry: dict[str, Any]) -> bool:
        return bool(
            head["text"] == entry["text"]
            and json.loads(head["steps_json"]) == entry["steps"]
            and json.loads(head["tables_json"]) == entry["tables"]
        )

    def _links(self, con: sqlite3.Connection, mid: str, revision: int) -> list[dict[str, Any]]:
        links = [
            {
                "conversation_id": r["conversation_id"],
                "revision": r["source_revision"],
                "message_indices": json.loads(r["message_indices_json"]),
            }
            for r in con.execute(
                "SELECT * FROM lineage WHERE memory_id=? AND revision=? ORDER BY conversation_id,source_revision",
                (mid, revision),
            )
        ]
        for row in con.execute(
            "SELECT payload_json FROM events WHERE operation='support' "
            "AND json_extract(payload_json,'$.memory_id')=? "
            "AND json_extract(payload_json,'$.revision')=? ORDER BY seq",
            (mid, revision),
        ):
            links.append(json.loads(row[0])["source"])
        merged: dict[tuple[str, int], set[int]] = {}
        for link in links:
            merged.setdefault((link["conversation_id"], link["revision"]), set()).update(link["message_indices"])
        return [
            {"conversation_id": cid, "revision": rev, "message_indices": sorted(indices)}
            for (cid, rev), indices in sorted(merged.items())
        ]

    def _append(
        self,
        con: sqlite3.Connection,
        mid: str,
        revision: int,
        body: str,
        steps: list[str],
        tables: list[str],
        status: str,
        origin: str,
        seq: int,
        links: list[dict[str, Any]],
        restored_from: int | None = None,
    ) -> None:
        con.execute(
            "INSERT INTO revisions VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                mid,
                revision,
                body,
                canonical(steps),
                canonical(tables),
                status,
                origin,
                revision - 1 or None,
                restored_from,
                seq,
            ),
        )
        for link in links:
            con.execute(
                "INSERT INTO lineage VALUES(?,?,?,?,?)",
                (mid, revision, link["conversation_id"], link["revision"], canonical(link["message_indices"])),
            )
        con.execute("UPDATE items SET head_revision=? WHERE memory_id=?", (revision, mid))

    @staticmethod
    def _usefulness(con: sqlite3.Connection, mid: str) -> int:
        return int(
            max(
                -3,
                min(
                    3,
                    con.execute(
                        "SELECT COALESCE(SUM(json_extract(payload_json,'$.delta')),0) FROM events "
                        "WHERE operation='feedback' AND json_extract(payload_json,'$.memory_id')=?",
                        (mid,),
                    ).fetchone()[0],
                ),
            )
        )

    def _head(self, con: sqlite3.Connection, mid: str) -> sqlite3.Row:
        text(mid, "memory_id", 64, 1)
        row = con.execute(HEADS + " WHERE i.memory_id=?", (mid,)).fetchone()
        if row is None:
            fail("missing_memory", "memory_id", "Use an agentic am_ ID from recall/history.")
        return cast(sqlite3.Row, row)

    def _record(self, con: sqlite3.Connection, mid: str, row: sqlite3.Row | None = None) -> dict[str, Any]:
        row = row if row is not None else self._head(con, mid)
        return {
            **{
                k: row[k]
                for k in (
                    "memory_id",
                    "type",
                    "key",
                    "session_id",
                    "revision",
                    "text",
                    "status",
                    "origin",
                    "previous_revision",
                    "restored_from",
                    "created_seq",
                )
            },
            "steps": json.loads(row["steps_json"]),
            "tables": json.loads(row["tables_json"]),
            "inferred": True,
            "verified": False,
            "trust": "untrusted, inferred, not database-verified",
            "sources": self._links(con, mid, row["revision"]),
            "usefulness": self._usefulness(con, mid),
        }

    def _archive(self, con: sqlite3.Connection, rows: list[sqlite3.Row], reason: str) -> list[dict[str, Any]]:
        if not rows:
            return []
        seq = self._event(con, "archive")
        manifest = []
        for row in rows:
            self._append(
                con,
                row["memory_id"],
                row["revision"] + 1,
                row["text"],
                json.loads(row["steps_json"]),
                json.loads(row["tables_json"]),
                "archived",
                row["origin"],
                seq,
                self._links(con, row["memory_id"], row["revision"]),
            )
            manifest.append(
                {
                    "memory_id": row["memory_id"],
                    "old_revision": row["revision"],
                    "archive_revision": row["revision"] + 1,
                }
            )
        con.execute(
            "UPDATE events SET payload_json=? WHERE seq=?", (canonical({"manifest": manifest, "reason": reason}), seq)
        )
        return manifest

    def _priority(self, con: sqlite3.Connection, row: sqlite3.Row) -> tuple[int, int, str]:
        return self._usefulness(con, row["memory_id"]), row["created_seq"], row["memory_id"]

    def _caps(self, con: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = list(con.execute(HEADS + " WHERE r.status='active'"))
        selected: dict[str, sqlite3.Row] = {}
        for session in sorted({r["session_id"] for r in rows if r["type"] == "working"}):
            group = sorted(
                (r for r in rows if r["type"] == "working" and r["session_id"] == session),
                key=lambda r: self._priority(con, r),
            )
            selected.update((r["memory_id"], r) for r in group[: max(0, len(group) - 32)])
        for kind, cap in (("working", 128), ("episodic", 128), ("semantic", 256), ("procedural", 128)):
            group = sorted(
                (r for r in rows if r["type"] == kind and r["memory_id"] not in selected),
                key=lambda r: self._priority(con, r),
            )
            selected.update((r["memory_id"], r) for r in group[: max(0, len(group) - cap)])
        if len(selected) > 32:
            fail("archive_limit", "items", "Repair active caps using explicit bounded compaction.")
        return self._archive(con, list(selected.values()), "active_caps")

    @staticmethod
    def _kind(row: sqlite3.Row) -> str:
        return f"agentic:{row['type']}:{row['session_id']}:{row['status']}"

    def _refresh(self, con: sqlite3.Connection, force: bool = False) -> None:
        if not self.index_path.exists() and self._index is not None:
            self._index.close()
            self._index = None
        if self._index is None:
            _private_file(self.index_path)
            # Only the disposable index may be discarded, never the authoritative store.
            try:
                with contextlib.closing(sqlite3.connect(self.index_path, timeout=5)) as check:
                    valid = check.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            except sqlite3.DatabaseError as error:
                if getattr(error, "sqlite_errorcode", None) not in (11, 26):  # CORRUPT, NOTADB
                    raise
                valid = False
            if not valid:
                _safe_path(self.index_path)
                self.index_path.unlink()
                _private_file(self.index_path)
            self._index = Index(self.index_path, embedder=None)
        generation = str(self._seq(con))
        if not force and self._index.meta("lifecycle_generation") == generation:
            return
        chunks = []
        for row in con.execute(HEADS):
            # Only head content and references enter the derived projection, never transcripts.
            payload = {
                "memory_id": row["memory_id"],
                "revision": row["revision"],
                "sources": self._links(con, row["memory_id"], row["revision"]),
            }
            chunks.append(
                Chunk(
                    "agentic:" + row["memory_id"],
                    self._kind(row),
                    row["memory_id"],
                    row["type"] + " " + row["key"],
                    row["text"] + "\n" + "\n".join(json.loads(row["steps_json"])),
                    keywords=" ".join(json.loads(row["tables_json"])),
                    tables=json.loads(row["tables_json"]),
                    payload=payload,
                )
            )
        self._index.replace_all(chunks, metadata={"lifecycle_generation": generation})
        con.execute("UPDATE meta SET value=? WHERE key='private_index_generation'", (generation,))
        self._paths()

    def refresh_index(self) -> None:
        with self._transaction() as con:
            self._refresh(con, force=True)

    def _page(self, con: sqlite3.Connection, cursor: str, limit: int, total: int) -> tuple[int, int]:
        integer(limit, "limit", 1, 50)
        text(cursor, "cursor", 128)
        seq = self._seq(con)
        offset = 0
        if cursor:
            if re.fullmatch(r"[0-9]{1,19}:[0-9]{1,19}", cursor) is None:
                fail("invalid_cursor", "cursor", "Restart with an empty cursor.")
            snapshot, offset = (int(v) for v in cursor.split(":"))
            if snapshot != seq or offset > total:
                fail("stale_cursor", "cursor", "Restart with an empty cursor.")
        return seq, offset

    def recall_memory(
        self, query: str = "", session_id: str = "", include_archived: bool = False, limit: int = 10, cursor: str = ""
    ) -> dict[str, Any]:
        text(query, "query", 2048)
        opaque(session_id, "session_id", True)
        if type(include_archived) is not bool:
            fail("invalid_boolean", "include_archived")
        with self._transaction() as con:
            self._refresh(con)
            rows = list(
                con.execute(
                    HEADS
                    + " WHERE (i.type!='working' OR (i.session_id=? AND i.session_id!=''))"
                    + ("" if include_archived else " AND r.status='active'"),
                    (session_id,),
                )
            )
            scores: dict[str, float] = {}
            if query:
                q = fts_query(query)
                kinds = sorted({self._kind(r) for r in rows})
                if q and kinds:
                    assert self._index is not None
                    scores = dict(
                        self._index.con.execute(
                            "SELECT c.ref,bm25(chunks_fts,4.0,1.0,2.0) FROM chunks_fts "
                            "JOIN chunks c ON c.rid=chunks_fts.rowid WHERE chunks_fts MATCH ? "
                            f"AND c.kind IN ({','.join('?' for _ in kinds)})",
                            (q, *kinds),
                        )
                    )
                rows = [r for r in rows if r["memory_id"] in scores]
                rows.sort(
                    key=lambda r: (scores[r["memory_id"]], -self._usefulness(con, r["memory_id"]), r["memory_id"])
                )
            else:
                rows.sort(key=lambda r: (-self._usefulness(con, r["memory_id"]), r["created_seq"], r["memory_id"]))
            seq, offset = self._page(con, cursor, limit, len(rows))
            selected = rows[offset : offset + limit]
            return self._report(
                "recall",
                items=[self._record(con, r["memory_id"], r) for r in selected],
                snapshot=seq,
                next_cursor=f"{seq}:{offset + limit}" if offset + limit < len(rows) else "",
            )

    def memory_history(
        self, memory_id: str = "", conversation_id: str = "", revision: int = 0, limit: int = 10, cursor: str = ""
    ) -> dict[str, Any]:
        text(memory_id, "memory_id", 64)
        text(conversation_id, "conversation_id", 64)
        integer(revision, "revision")
        integer(limit, "limit", 1, 50)
        if bool(memory_id) == bool(conversation_id):
            fail("invalid_selector", "history", "Supply exactly one memory_id or conversation_id.")
        with self._transaction() as con:
            if conversation_id:
                opaque(conversation_id, "conversation_id")
                source = self._source(con, conversation_id, revision)
                latest = self._source(con, conversation_id)["revision"]
                entries = json.loads(source["messages_json"])
                seq, offset = self._page(con, cursor, limit, len(entries))
                page_size = min(limit, 10)
                return self._report(
                    "history",
                    conversation_id=conversation_id,
                    revision=source["revision"],
                    latest_revision=latest,
                    snapshot=seq,
                    items=[
                        {"message_index": i, **entries[i], "trust": "untrusted source data"}
                        for i in range(offset, min(offset + page_size, len(entries)))
                    ],
                    next_cursor=f"{seq}:{offset + page_size}" if offset + page_size < len(entries) else "",
                )
            head = self._head(con, memory_id)
            rows = list(
                con.execute(
                    "SELECT i.type,i.key,i.session_id,r.* FROM revisions r JOIN items i ON i.memory_id=r.memory_id "
                    "WHERE r.memory_id=?" + (" AND r.revision=?" if revision else "") + " ORDER BY r.revision",
                    (memory_id, revision) if revision else (memory_id,),
                )
            )
            if revision and not rows:
                fail("missing_revision", "revision")
            seq, offset = self._page(con, cursor, limit, len(rows))
            selected = rows[offset : offset + limit]
            revisions = {r["revision"] for r in selected}
            events = []
            for event in con.execute(
                "SELECT * FROM events WHERE json_extract(payload_json,'$.memory_id')=? "
                "OR EXISTS(SELECT 1 FROM json_each(payload_json,'$.manifest') "
                "WHERE json_extract(value,'$.memory_id')=?) "
                "OR EXISTS(SELECT 1 FROM json_each(payload_json,'$.report.items') "
                "WHERE json_extract(value,'$.memory_id')=?) ORDER BY seq",
                (memory_id, memory_id, memory_id),
            ):
                payload = json.loads(event["payload_json"])
                affected = {payload.get("revision")} if payload.get("memory_id") == memory_id else set()
                affected.update(
                    m["archive_revision"] for m in payload.get("manifest", []) if m["memory_id"] == memory_id
                )
                affected.update(
                    r["revision"] for r in payload.get("report", {}).get("items", []) if r.get("memory_id") == memory_id
                )
                if revisions & affected:
                    events.append(
                        {
                            "seq": event["seq"],
                            "operation": event["operation"],
                            "metadata": {k: v for k, v in payload.items() if k != "report"},
                        }
                    )
            return self._report(
                "history",
                memory_id=memory_id,
                latest_revision=head["revision"],
                snapshot=seq,
                items=[self._record(con, memory_id, r) for r in selected],
                events=events,
                next_cursor=f"{seq}:{offset + limit}" if offset + limit < len(rows) else "",
            )

    def restore_memory(self, memory_id: str, revision: int, expected_revision: int) -> dict[str, Any]:
        integer(revision, "revision", 1)
        integer(expected_revision, "expected_revision", 1)
        text(memory_id, "memory_id", 64, 1)
        key = f"restore:{memory_id}:{revision}:{expected_revision}"
        with self._transaction() as con:
            replay = self._replay(con, key)
            if replay is not None:
                return replay
            head = self._head(con, memory_id)
            if head["revision"] != expected_revision:
                fail("stale_revision", "expected_revision", "Read the current head and retry.")
            old = con.execute(
                "SELECT * FROM revisions WHERE memory_id=? AND revision=?", (memory_id, revision)
            ).fetchone()
            if old is None:
                fail("missing_revision", "revision")
            seq = self._event(con, "restore", key)
            identical = head["status"] == "active" and all(
                head[k] == old[k] for k in ("text", "steps_json", "tables_json")
            )
            if not identical:
                self._append(
                    con,
                    memory_id,
                    head["revision"] + 1,
                    old["text"],
                    json.loads(old["steps_json"]),
                    json.loads(old["tables_json"]),
                    "active",
                    old["origin"],
                    seq,
                    self._links(con, memory_id, revision),
                    restored_from=revision,
                )
            manifest = self._caps(con)
            report = self._report(
                "restore",
                items=[self._record(con, memory_id)],
                accepted=int(not identical),
                unchanged=int(identical),
                archived=len(manifest),
                manifest=manifest,
            )
            return self._finish(
                con,
                seq,
                report,
                {"memory_id": memory_id, "revision": head["revision"] + int(not identical), "restored_from": revision},
            )

    def memory_feedback(
        self, memory_id: str, feedback_id: str, outcome: str, expected_revision: int, note: str = ""
    ) -> dict[str, Any]:
        text(memory_id, "memory_id", 64, 1)
        opaque(feedback_id, "feedback_id")
        integer(expected_revision, "expected_revision", 1)
        if outcome not in ("helpful", "unhelpful", "correction"):
            fail("invalid_outcome", "outcome")
        text(note, "note", 2048, int(outcome == "correction"))
        note, counts = sanitize(note)
        text(note, "note", 2048, int(outcome == "correction"))
        request_hash = digest([memory_id, feedback_id, outcome, expected_revision, note])
        with self._transaction() as con:
            replay = self._replay(con, f"feedback:{feedback_id}", request_hash, "feedback_id")
            if replay is not None:
                return replay
            head = self._head(con, memory_id)
            if head["revision"] != expected_revision:
                fail("stale_revision", "expected_revision", "Read the current head and retry.")
            seq = self._event(con, "feedback", f"feedback:{feedback_id}")
            cid = "__feedback_" + uuid.uuid4().hex
            self._insert_source(
                con, cid, 1, head["session_id"], [{"role": "user", "content": note or outcome}], counts, seq
            )
            link = {"conversation_id": cid, "revision": 1, "message_indices": [0]}
            delta = 1 if outcome == "helpful" else -1 if outcome == "unhelpful" else 0
            if outcome == "correction":
                self._append(
                    con,
                    memory_id,
                    expected_revision + 1,
                    note,
                    json.loads(head["steps_json"]),
                    json.loads(head["tables_json"]),
                    "active",
                    "caller",
                    seq,
                    [*self._links(con, memory_id, expected_revision), link],
                )
            manifest = self._caps(con) if outcome == "correction" else []
            # Usefulness must be visible to recall immediately, and is derived only from unique events.
            metadata = {
                "request_hash": request_hash,
                "memory_id": memory_id,
                "revision": expected_revision + int(outcome == "correction"),
                "outcome": outcome,
                "delta": delta,
                "source": link,
            }
            con.execute("UPDATE events SET payload_json=? WHERE seq=?", (canonical(metadata), seq))
            report = self._report(
                "feedback",
                items=[self._record(con, memory_id)],
                accepted=int(outcome == "correction"),
                archived=len(manifest),
                manifest=manifest,
                sources=[link],
                redaction_counts=counts,
            )
            return self._finish(con, seq, report, metadata)

    def compact_memory(self, keep: int = 100, session_id: str = "") -> dict[str, Any]:
        integer(keep, "keep", 0, 256)
        opaque(session_id, "session_id", True)
        with self._transaction() as con:
            rows = list(
                con.execute(
                    HEADS
                    + " WHERE r.status='active' AND i.type IN ('working','episodic')"
                    + (" AND i.session_id=?" if session_id else ""),
                    (session_id,) if session_id else (),
                )
            )
            rows.sort(key=lambda r: self._priority(con, r))
            excess = max(0, len(rows) - keep)
            seq = self._event(con, "compact")
            manifest = self._archive(con, rows[: min(excess, 100)], "explicit_compaction")
            return self._finish(
                con,
                seq,
                self._report(
                    "compact",
                    archived=len(manifest),
                    manifest=manifest,
                    remaining=excess - len(manifest),
                    active_remaining=len(rows) - len(manifest),
                ),
            )

    def backup(self, destination: Path | str) -> None:
        """SQLite's consistent backup, never a copy of an open authoritative database."""
        target = Path(destination)
        for path in (target, *target.absolute().parents):
            _safe_path(path)
        if target.resolve() == self.path.resolve() or target.exists():
            fail("invalid_backup", "destination", "Use a new local file in an access-controlled directory.")
        with self._lock:
            try:
                # The destination is caller-selected; source always remains in the private root.
                _private_file(target)
                with contextlib.closing(sqlite3.connect(target)) as out:
                    self._connection().backup(out)
                if os.name != "nt":
                    target.chmod(0o600)
            except (OSError, sqlite3.Error):
                fail("backup_failed", "destination", "Use a new local file with free space and owner-only access.")
