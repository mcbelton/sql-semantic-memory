"""Learning uses explicit, bounded, injected clients; no models or sockets."""

import json
from types import SimpleNamespace

import pytest

from sqlmem.llm import LLM
from tests.test_memory_lifecycle import submit
from tests.test_memory_llm_bounds import client as streaming_client


class Stub:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system, user, **kwargs):
        self.calls += 1
        assert "untrusted" in system.lower()
        task = json.loads(user)
        return {"task_id": task["task_id"], "items": []}


@pytest.mark.req("REQ-AMEM-03", "REQ-AMEM-08")
def test_only_explicit_learning_calls_model(kb):
    stub = Stub()
    submit(kb)
    kb.memory_task("chat")
    kb.recall_memory()
    kb.compact_memory()
    kb.build(log=lambda _: None)
    assert stub.calls == 0
    report = kb.learn_conversation("chat", stub)
    assert report["accepted"] == 0
    assert stub.calls == 1


@pytest.mark.req("REQ-AMEM-03")
@pytest.mark.parametrize("provider", ["ollama", "azure-openai", "openai"])
def test_memory_llm_options_disable_retry_and_bound_reply(kb, provider):
    submit(kb)
    seen = []

    def create(**kwargs):
        seen.append(kwargs)
        task = json.loads(kwargs["messages"][1]["content"])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps({"task_id": task["task_id"], "items": []})),
                )
            ]
        )

    sdk = streaming_client(create)
    client = LLM(f"{provider}:stub", client=sdk, memory_mode=True)
    assert kb.learn_conversation("chat", client)["accepted"] == 0
    assert len(seen) == 1
    assert 0 < seen[0]["timeout"] <= 60


@pytest.mark.req("REQ-AMEM-03", "REQ-AMEM-02")
def test_model_errors_are_safe_and_apply_nothing(kb, capsys):
    submit(kb)

    class Broken:
        def complete_json(self, system, user, **kwargs):
            raise RuntimeError("api_key=provider-secret user@example.com")

    with pytest.raises(ValueError, match="model_failed") as error:
        kb.learn_conversation("chat", Broken())
    assert "provider-secret" not in str(error.value)
    assert "provider-secret" not in str(capsys.readouterr())
    assert kb.recall_memory()["items"] == []


@pytest.mark.req("REQ-AMEM-03", "REQ-AMEM-04")
def test_explicit_model_learning_uses_same_validator_and_all_types(kb):
    submit(kb, session="learning")

    class AllTypes:
        def complete_json(self, system, user):
            task = json.loads(user)
            return {
                "task_id": task["task_id"],
                "items": [
                    {
                        "type": kind,
                        "key": "shared_key",
                        "text": "Revenue workflow",
                        "steps": ["Check approved filters"] if kind == "procedural" else [],
                        "tables": ["orders"],
                        "message_indices": [0],
                        "base_revision": 0,
                    }
                    for kind in ("working", "episodic", "semantic", "procedural")
                ],
            }

    report = kb.learn_conversation("chat", AllTypes())
    assert report["operation"] == "learn"
    assert report["accepted"] == 4
    assert {r["origin"] for r in report["items"]} == {"model"}
    assert {r["type"] for r in kb.recall_memory(session_id="learning")["items"]} == {
        "working",
        "episodic",
        "semantic",
        "procedural",
    }


@pytest.mark.req("REQ-AMEM-03")
def test_injected_client_deadline_rejects_late_reply_without_writes(kb, monkeypatch):
    submit(kb)
    now = [0.0]
    monkeypatch.setattr("sqlmem.kb.time.monotonic", lambda: now[0])

    class Late(Stub):
        def complete_json(self, system, user, **kwargs):
            now[0] = 61
            return super().complete_json(system, user)

    with pytest.raises(ValueError, match="model_deadline"):
        kb.learn_conversation("chat", Late())
    assert kb.recall_memory()["items"] == []
