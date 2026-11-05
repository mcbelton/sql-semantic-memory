"""Hybrid search index (SQLite FTS5 BM25 + dense vectors, fused with RRF) in a single SQLite file."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import itertools
import json
import os
import re
import sqlite3
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

_STOPWORD_TEXT = """
a an and are as at be been by can could did do does for from had has have how i if in into is it its me my of on or
our show list give tell find get what whats which who whom whose why when where with would the their them there
these they this those to was we were will you your all any each per vs versus please
"""
STOPWORDS = frozenset(_STOPWORD_TEXT.split())
RRF_K = 60
# Dense vectors only see the head of a chunk (title + description); the full text stays in the BM25 index.
EMBED_MAX_CHARS = 700


@dataclass
class Chunk:
    id: str
    kind: str
    ref: str
    title: str
    text: str
    keywords: str = ""
    tables: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        return hashlib.sha1(f"{self.title}\n{self.text}".encode()).hexdigest()


@dataclass
class Hit:
    id: str
    kind: str
    ref: str
    title: str
    text: str
    tables: list[str]
    payload: dict[str, Any]
    score: float
    lexical_rank: int | None = None
    vector_rank: int | None = None


# ---------------------------------------------------------------------------- embedders
def _normalize(m: NDArray[np.float32]) -> NDArray[np.float32]:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    out: NDArray[np.float32] = (m / n).astype(np.float32)
    return out


class HashEmbedder:
    """Dependency-free feature-hashing embedder (offline fallback / tests). Lexical, not truly semantic."""

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.spec = f"hash:{dim}"

    def _vec(self, text: str) -> NDArray[np.float32]:
        v = np.zeros(self.dim, dtype=np.float32)
        toks = [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]
        for tok in [*toks, *(a + "_" + b for a, b in itertools.pairwise(toks))]:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 64) & 1 else -1.0
        return v

    def embed_docs(self, texts: list[str]) -> NDArray[np.float32]:
        return _normalize(np.stack([self._vec(t) for t in texts])) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        row: NDArray[np.float32] = self.embed_docs([text])[0]
        return row


class FastEmbedEmbedder:
    """Local ONNX embeddings (no API keys). Model is downloaded once from Hugging Face."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        TextEmbedding = importlib.import_module("fastembed").TextEmbedding  # optional extra 'local'

        cache = os.environ.get("SQLMEM_MODEL_CACHE") or str(Path.home() / ".cache" / "sqlmem" / "fastembed")
        with contextlib.redirect_stdout(sys.stderr):  # keep stdout clean for the MCP stdio protocol
            self.model = TextEmbedding(model_name=model, cache_dir=cache)
        self.spec = f"fastembed:{model}"

    def embed_docs(self, texts: list[str]) -> NDArray[np.float32]:
        with contextlib.redirect_stdout(sys.stderr):
            vecs = list(self.model.passage_embed(texts, batch_size=64))
        return _normalize(np.array(vecs, dtype=np.float32))

    def embed_query(self, text: str) -> NDArray[np.float32]:
        with contextlib.redirect_stdout(sys.stderr):
            vec = next(iter(self.model.query_embed(text)))
        row: NDArray[np.float32] = _normalize(np.array([vec], dtype=np.float32))[0]
        return row


class OpenAIEmbedder:
    """Azure OpenAI / OpenAI embeddings (spec 'azure-openai:<deployment>' or 'openai:<model>')."""

    def __init__(self, provider: str, model: str, client: Any = None):
        from .llm import make_client

        self.client = client or make_client(provider)
        self.model = model
        self.spec = f"{provider}:{model}"

    def embed_docs(self, texts: list[str]) -> NDArray[np.float32]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 128):
            resp = self.client.embeddings.create(model=self.model, input=texts[i : i + 128])
            out += [d.embedding for d in resp.data]
        return _normalize(np.array(out, dtype=np.float32))

    def embed_query(self, text: str) -> NDArray[np.float32]:
        row: NDArray[np.float32] = self.embed_docs([text])[0]
        return row


def make_embedder(spec: str | None) -> Any:
    if not spec or spec == "none":
        return None
    provider, _, model = spec.partition(":")
    if provider == "fastembed":
        return FastEmbedEmbedder(model or "BAAI/bge-small-en-v1.5")
    if provider in ("azure-openai", "openai", "ollama"):
        if not model:
            raise ValueError(f"Embedder '{spec}' needs a model/deployment name, e.g. {provider}:text-embedding-3-small")
        return OpenAIEmbedder(provider, model)
    if provider == "hash":
        return HashEmbedder(int(model or 512))
    raise ValueError(
        f"Unknown embedder '{spec}' (use none | fastembed[:model] | azure-openai:<deployment> | "
        "openai:<model> | ollama:<model> | hash[:dim])"
    )


# ---------------------------------------------------------------------------- index
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS chunks(
    rid INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, ref TEXT, title TEXT, text TEXT,
    keywords TEXT, tables TEXT, payload TEXT, hash TEXT);
CREATE INDEX IF NOT EXISTS chunks_kind ON chunks(kind);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    title, text, keywords, tokenize = 'porter unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS vectors(rid INTEGER PRIMARY KEY, hash TEXT, vec BLOB);
"""


def fts_query(text: str) -> str:
    from .model import split_identifier

    words = re.findall(r"[a-z0-9]+", split_identifier(text) + " " + text.lower())
    toks = list(dict.fromkeys(w for w in words if w not in STOPWORDS and (len(w) > 1 or w.isdigit())))
    return " OR ".join(f'"{t}"' for t in toks[:40])


class Index:
    def __init__(self, path: Path | str, embedder: Any = None):
        self.path = Path(path)
        self.embedder = embedder
        self.con = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30)
        self.con.executescript(SCHEMA)
        self._vec_gen: str | None = None
        self._vec_rids: NDArray[Any] | None = None
        self._vec_mat: NDArray[Any] | None = None

    def close(self) -> None:
        self.con.close()

    def meta(self, key: str, default: str | None = None) -> str | None:
        row = self.con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def _set_meta(self, key: str, value: Any) -> None:
        self.con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, str(value)))

    def _bump(self) -> None:
        self._set_meta("generation", f"{time.time_ns()}")

    def _embed(
        self, chunks: list[Chunk], reuse: dict[str, bytes], log: Callable[[str], None] | None
    ) -> dict[str, bytes]:
        if self.embedder is None:
            return {}
        # Sorting by length keeps batches uniformly sized, which minimizes padding work in the encoder.
        todo = sorted((c for c in chunks if c.hash not in reuse), key=lambda c: len(c.title) + len(c.text))
        out = dict(reuse)
        if todo:
            t0 = time.time()
            for i in range(0, len(todo), 256):
                batch = todo[i : i + 256]
                mat = self.embedder.embed_docs([f"{c.title}\n{c.text}"[:EMBED_MAX_CHARS] for c in batch])
                out.update({c.hash: mat[j].astype(np.float32).tobytes() for j, c in enumerate(batch)})
                if log:
                    log(f"  embedded {min(i + 256, len(todo))}/{len(todo)} chunks")
            if log:
                log(f"  embeddings: {len(todo)} new, {len(chunks) - len(todo)} reused ({time.time() - t0:.1f}s)")
        return out

    def _insert(self, chunks: list[Chunk], vecs: dict[str, bytes]) -> None:
        for c in chunks:
            cur = self.con.execute(
                "INSERT INTO chunks(id, kind, ref, title, text, keywords, tables, payload, hash) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    c.id,
                    c.kind,
                    c.ref,
                    c.title,
                    c.text,
                    c.keywords,
                    json.dumps(c.tables),
                    json.dumps(c.payload, ensure_ascii=False, default=str),
                    c.hash,
                ),
            )
            rid = cur.lastrowid
            self.con.execute(
                "INSERT INTO chunks_fts(rowid, title, text, keywords) VALUES (?,?,?,?)",
                (rid, c.title, c.text, c.keywords),
            )
            if c.hash in vecs:
                self.con.execute("INSERT INTO vectors(rid, hash, vec) VALUES (?,?,?)", (rid, c.hash, vecs[c.hash]))

    def replace_all(
        self,
        chunks: list[Chunk],
        log: Callable[[str], None] | None = None,
        *,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Rebuild the whole index in one transaction (readers keep working; vectors reused by text hash)."""
        spec = self.embedder.spec if self.embedder else "none"
        reuse: dict[str, bytes] = {}
        if self.meta("embedder") == spec and self.meta("embed_chars") == str(EMBED_MAX_CHARS):
            reuse = dict(self.con.execute("SELECT hash, vec FROM vectors").fetchall())
        wanted = {c.hash for c in chunks}
        vecs = self._embed(chunks, {h: v for h, v in reuse.items() if h in wanted}, log)
        with self.con:
            self.con.execute("DELETE FROM chunks")
            self.con.execute("DELETE FROM chunks_fts")
            self.con.execute("DELETE FROM vectors")
            self._insert(chunks, vecs)
            self._set_meta("embedder", spec)
            self._set_meta("embed_chars", EMBED_MAX_CHARS)
            if self.embedder is not None and vecs:
                self._set_meta("dim", len(next(iter(vecs.values()))) // 4)
            self._set_meta("built_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
            for key, value in (metadata or {}).items():
                self._set_meta(key, value)
            self._bump()
        self.con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
        self.con.commit()

    def upsert(self, chunks: list[Chunk]) -> None:
        if self.embedder is not None and self.meta("embedder") not in (None, self.embedder.spec):
            raise RuntimeError("Index was built with a different embedder; run `sqlmem build` first")
        vecs = self._embed(chunks, {}, None)
        with self.con:
            self._delete([c.id for c in chunks])
            self._insert(chunks, vecs)
            self._bump()

    def _delete(self, ids: Iterable[str]) -> int:
        n = 0
        for cid in ids:
            row = self.con.execute("SELECT rid FROM chunks WHERE id = ?", (cid,)).fetchone()
            if row:
                for sql in (
                    "DELETE FROM chunks WHERE rid = ?",
                    "DELETE FROM chunks_fts WHERE rowid = ?",
                    "DELETE FROM vectors WHERE rid = ?",
                ):
                    self.con.execute(sql, (row[0],))
                n += 1
        return n

    def delete(self, ids: Iterable[str]) -> int:
        with self.con:
            n = self._delete(ids)
            self._bump()
        return n

    def count(self) -> dict[str, int]:
        return dict(self.con.execute("SELECT kind, COUNT(*) FROM chunks GROUP BY kind ORDER BY kind").fetchall())

    # ------------------------------------------------------------------ search
    def _kind_filter(self, kinds: list[str] | None) -> tuple[str, list[str]]:
        if not kinds:
            return "", []
        return f" AND c.kind IN ({','.join('?' * len(kinds))})", list(kinds)

    def _lexical(self, query: str, limit: int, kinds: list[str] | None) -> list[int]:
        q = fts_query(query)
        if not q:
            return []
        where, params = self._kind_filter(kinds)
        try:
            rows = self.con.execute(
                "SELECT f.rowid FROM chunks_fts f JOIN chunks c ON c.rid = f.rowid "
                f"WHERE chunks_fts MATCH ?{where} ORDER BY bm25(chunks_fts, 4.0, 1.0, 2.0) LIMIT ?",
                [q, *params, limit],
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [r[0] for r in rows]

    def _load_vectors(self) -> None:
        gen = self.meta("generation")
        if gen == self._vec_gen and self._vec_mat is not None:
            return
        rows = self.con.execute("SELECT rid, vec FROM vectors ORDER BY rid").fetchall()
        self._vec_rids = np.array([r[0] for r in rows], dtype=np.int64)
        self._vec_mat = (
            np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows]) if rows else np.zeros((0, 1), np.float32)
        )
        self._vec_gen = gen

    def _semantic(self, query: str, limit: int, kinds: list[str] | None) -> list[int]:
        if self.embedder is None or self.meta("embedder") != self.embedder.spec:
            return []
        self._load_vectors()
        mat, row_ids = self._vec_mat, self._vec_rids
        if mat is None or row_ids is None or not len(mat):
            return []
        q = self.embedder.embed_query(query)
        sims = mat @ q
        order = np.argsort(-sims)
        rids = [int(row_ids[i]) for i in order[: limit * 4]]
        if kinds:
            allowed = {
                r[0]
                for r in self.con.execute(
                    f"SELECT rid FROM chunks WHERE kind IN ({','.join('?' * len(kinds))})", list(kinds)
                )
            }
            rids = [r for r in rids if r in allowed]
        return rids[:limit]

    def search(self, query: str, k: int = 10, kinds: list[str] | None = None, rrf_k: int = RRF_K) -> list[Hit]:
        pool = max(50, k * 5)
        lex = self._lexical(query, pool, kinds)
        sem = self._semantic(query, pool, kinds)
        scores: dict[int, float] = {}
        for ranks in (lex, sem):
            for i, rid in enumerate(ranks):
                scores[rid] = scores.get(rid, 0.0) + 1.0 / (rrf_k + i + 1)
        top = sorted(scores.items(), key=lambda x: -x[1])[:k]
        lex_rank = {rid: i + 1 for i, rid in enumerate(lex)}
        sem_rank = {rid: i + 1 for i, rid in enumerate(sem)}
        hits = []
        for rid, score in top:
            row = self.con.execute(
                "SELECT id, kind, ref, title, text, tables, payload FROM chunks WHERE rid = ?", (rid,)
            ).fetchone()
            if row:
                hits.append(
                    Hit(
                        row[0],
                        row[1],
                        row[2],
                        row[3],
                        row[4],
                        json.loads(row[5] or "[]"),
                        json.loads(row[6] or "{}"),
                        round(score, 5),
                        lex_rank.get(rid),
                        sem_rank.get(rid),
                    )
                )
        return hits
