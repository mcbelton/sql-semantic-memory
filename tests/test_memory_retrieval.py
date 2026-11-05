"""Acceptance checks for private memory recall without schema-retrieval regressions."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sqlmem.kb import KnowledgeBase


def _learn(
    kb: KnowledgeBase,
    conversation: str,
    texts: list[str],
    *,
    memory_type: str = "semantic",
    session: str = "",
    prefix: str = "fact",
) -> dict[str, Any]:
    kb.submit_conversation(
        conversation,
        [{"role": "user", "content": text} for text in texts],
        session_id=session,
    )
    task = kb.memory_task(conversation)
    return kb.save_memory(
        {
            "task_id": task["task_id"],
            "items": [
                {
                    "type": memory_type,
                    "key": f"{prefix}_{i}",
                    "text": text,
                    "steps": ["Check the approved filters before querying."] if memory_type == "procedural" else [],
                    "tables": ["orders", "products"],
                    "message_indices": [i],
                    "base_revision": 0,
                }
                for i, text in enumerate(texts)
            ],
        }
    )


def _public_documents(kb: KnowledgeBase) -> dict[str, bytes]:
    paths = [*kb.docs_path.rglob("*"), kb.root / "graph.json"]
    return {str(path.relative_to(kb.root)): path.read_bytes() for path in paths if path.is_file()}


@pytest.mark.req("REQ-AMEM-09", "REQ-RET-03", "REQ-RET-05")
def test_saturated_agentic_memory_preserves_schema_hits_tables_and_examples(kb: KnowledgeBase) -> None:
    question = "helmet revenue by country"
    before_context = kb.context(question)
    before_hits = [(hit.id, hit.score) for hit in kb.search(question, k=40)]
    before_counts = kb.index().count()
    before_documents = _public_documents(kb)
    for batch in range(73):
        _learn(
            kb,
            f"saturation_{batch}",
            [
                f"PrivateCanary orders products customers helmet revenue country inference {batch} {i}."
                for i in range(32)
            ],
            prefix=f"batch_{batch}",
        )

    after_context = kb.context(question)
    assert after_context.startswith(before_context)
    assert "PrivateCanary" in after_context
    assert len(after_context.encode()) - len(before_context.encode()) <= 8192
    assert [(hit.id, hit.score) for hit in kb.search(question, k=40)] == before_hits
    assert kb.index().count() == before_counts
    assert all("PrivateCanary" not in hit.text for hit in kb.search("PrivateCanary", k=50))

    kb.build(log=lambda _message: None)
    assert _public_documents(kb) == before_documents
    assert kb.index().count() == before_counts
    assert [(hit.id, hit.score) for hit in kb.search(question, k=40)] == before_hits
    assert not kb.memories.load()


@pytest.mark.req("REQ-AMEM-01", "REQ-AMEM-05", "REQ-AMEM-09")
def test_memory_recall_rebuilds_both_disposable_indexes_without_losing_sources(kb: KnowledgeBase) -> None:
    marker = "ArchiveRecoveryCanary"
    _learn(kb, "recovery", [f"{marker} revenue uses approved order filters."])
    before = kb.recall_memory(marker)["items"]
    assert len(before) == 1
    memory_id = before[0]["memory_id"]
    authoritative = kb.root / "private" / "memory.sqlite3"
    assert authoritative.is_file()
    kb.close()
    kb.index_path.unlink()
    (kb.root / "private" / "memory-index.db").unlink()

    fresh = KnowledgeBase(kb.root, embedder="hash:256")
    try:
        fresh.build(log=lambda _message: None)
        recovered = fresh.recall_memory(marker)["items"]
        assert len(recovered) == 1
        assert recovered[0]["memory_id"] == memory_id
        assert recovered[0]["text"] == before[0]["text"]
        assert recovered[0]["sources"] == before[0]["sources"]
        assert marker in json.dumps(fresh.memory_history(conversation_id="recovery"))
        assert marker in fresh.context("revenue")
        assert marker not in json.dumps(fresh.memories.load())
    finally:
        fresh.close()


@pytest.mark.req("REQ-AMEM-02", "REQ-AMEM-05", "REQ-AMEM-09")
def test_context_keeps_working_state_session_scoped_and_visibly_untrusted(kb: KnowledgeBase) -> None:
    _learn(
        kb,
        "working_source",
        ["SessionOnlyCanary helmet revenue task is waiting for validation."],
        memory_type="working",
        session="session_A",
    )
    plain = kb.context("helmet revenue")
    own = kb.context("helmet revenue", session_id="session_A")
    other = kb.context("helmet revenue", session_id="session_B")
    assert "SessionOnlyCanary" not in plain
    assert "SessionOnlyCanary" not in other
    assert "SessionOnlyCanary" in own
    section = own[len(plain) :].casefold()
    assert "untrusted" in section
    assert "inferred" in section
    assert "not" in section
    assert "verified" in section


@pytest.mark.req("REQ-AMEM-06", "REQ-AMEM-09")
def test_compaction_removes_active_context_not_recoverable_evidence(kb: KnowledgeBase) -> None:
    marker = "CompactEpisodeCanary"
    _learn(kb, "episode_source", [f"{marker} helmet revenue query needs a bridge join."], memory_type="episodic")
    assert marker in kb.context("helmet revenue bridge join")
    original = kb.recall_memory(marker)["items"][0]
    kb.compact_memory(keep=0)
    assert marker not in kb.context("helmet revenue bridge join")
    assert not kb.recall_memory(marker)["items"]
    archived = kb.recall_memory(marker, include_archived=True)["items"]
    assert len(archived) == 1
    assert archived[0]["memory_id"] == original["memory_id"]
    assert archived[0]["status"] == "archived"
    assert marker in json.dumps(kb.memory_history(conversation_id="episode_source"))
    kb.restore_memory(
        original["memory_id"],
        revision=original["revision"],
        expected_revision=archived[0]["revision"],
    )
    assert marker in kb.context("helmet revenue bridge join")


@pytest.mark.req("REQ-AMEM-09")
def test_private_memory_is_excluded_from_public_docs_and_graph(kb: KnowledgeBase) -> None:
    marker = "PrivateProcedureCanary"
    _learn(
        kb,
        "private_workflow",
        [f"{marker} compare revenue totals against approved aggregates."],
        memory_type="procedural",
    )
    kb.build(log=lambda _message: None)
    assert marker in json.dumps(kb.recall_memory(marker))
    for path, content in _public_documents(kb).items():
        assert marker.encode() not in content, path
    assert marker not in json.dumps(kb.memories.load())
    assert all(marker not in hit.text for hit in kb.search(marker, k=50))
    private_ignore = kb.root / "private" / ".gitignore"
    assert private_ignore.is_file()
    assert "*" in private_ignore.read_text(encoding="utf-8").splitlines()


@pytest.mark.req("REQ-AMEM-07", "REQ-AMEM-09")
def test_helpful_feedback_improves_bounded_context_selection_without_schema_changes(kb: KnowledgeBase) -> None:
    question = "helmet revenue"
    schema_hits = [(hit.id, hit.score) for hit in kb.search(question, k=40)]
    _learn(
        kb,
        "feedback_quality",
        ["FeedbackQualityCanary helmet revenue uses the approved business definition."] * 6,
    )
    initial = kb.recall_memory(question, limit=6)["items"]
    assert len(initial) == 6
    target = initial[-1]
    assert target["memory_id"] not in kb.context(question)

    kb.memory_feedback(
        target["memory_id"],
        feedback_id="helpful_vote",
        outcome="helpful",
        expected_revision=target["revision"],
    )

    assert kb.recall_memory(question, limit=6)["items"][0]["memory_id"] == target["memory_id"]
    assert target["memory_id"] in kb.context(question)
    assert [(hit.id, hit.score) for hit in kb.search(question, k=40)] == schema_hits
