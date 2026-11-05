"""Public command/tool parity without external processes or models."""

import asyncio
import json
import sqlite3

import pytest

from sqlmem.cli import main
from sqlmem.mcp_server import create_server
from tests.conftest import tool_text
from tests.test_memory_lifecycle import submit


@pytest.mark.req("REQ-AMEM-08")
def test_nested_cli_task_save_history_recall_and_errors(kb, tmp_path, capsys):
    path = tmp_path / "messages.json"
    path.write_text(json.dumps([{"role": "user", "content": "Remember revenue"}]))
    common = ["memory", "--kb", str(kb.root)]
    main([*common, "submit", "--conversation", "cli", "--file", str(path)])
    assert json.loads(capsys.readouterr().out)["revision"] == 1
    main([*common, "task", "--conversation", "cli"])
    task = json.loads(capsys.readouterr().out)
    path.write_text(json.dumps({"task_id": task["task_id"], "items": []}))
    main([*common, "save", "--file", str(path)])
    assert json.loads(capsys.readouterr().out)["accepted"] == 0
    main([*common, "history", "--conversation", "cli"])
    assert json.loads(capsys.readouterr().out)["items"][0]["role"] == "user"
    main([*common, "recall"])
    assert json.loads(capsys.readouterr().out)["items"] == []
    main([*common, "compact", "--keep", "0"])
    assert json.loads(capsys.readouterr().out)["archived"] == 0
    with pytest.raises(SystemExit) as error:
        main([*common, "learn", "--conversation", "cli"])
    assert error.value.code == 2


@pytest.mark.req("REQ-AMEM-08", "REQ-AMEM-02")
def test_all_mcp_tools_annotations_and_keyless_workflow(kb):
    from mcp.client.client import Client

    submit(kb)
    server = create_server(kb)

    async def run():
        async with Client(server) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            writes = {
                "submit_conversation",
                "save_memory",
                "learn_conversation",
                "restore_memory",
                "memory_feedback",
                "compact_memory",
            }
            reads = {"memory_task", "recall_memory", "memory_history"}
            for name in writes | reads:
                assert name in tools
                annotations = tools[name].annotations
                assert annotations is not None
                assert annotations.read_only_hint == (name in reads)
                assert annotations.destructive_hint is False
            annotations = tools["learn_conversation"].annotations
            assert annotations is not None
            assert annotations.open_world_hint is True
            task = await client.call_tool("memory_task", {"conversation_id": "chat"})
            data = json.loads(tool_text(task))
            result = await client.call_tool("save_memory", {"proposal": {"task_id": data["task_id"], "items": []}})
            assert json.loads(tool_text(result))["accepted"] == 0

    asyncio.run(run())


@pytest.mark.req("REQ-AMEM-08")
def test_cli_restore_feedback_and_no_config_learning(kb, tmp_path, capsys, monkeypatch):
    from tests.test_memory_lifecycle import proposal

    submit(kb, session="cli_session")
    path = tmp_path / "reply.json"
    path.write_text(json.dumps(proposal(kb, kind="episodic")), encoding="utf-8")
    common = ["memory", "--kb", str(kb.root)]
    main([*common, "save", "--file", str(path)])
    saved = json.loads(capsys.readouterr().out)
    mid = saved["items"][0]["memory_id"]
    main([*common, "feedback", mid, "--feedback-id", "cli_help", "--outcome", "helpful", "--expected-revision", "1"])
    assert json.loads(capsys.readouterr().out)["operation"] == "feedback"
    main([*common, "compact", "--keep", "0"])
    assert json.loads(capsys.readouterr().out)["archived"] == 1
    main([*common, "restore", mid, "--revision", "1", "--expected-revision", "2"])
    assert json.loads(capsys.readouterr().out)["items"][0]["revision"] == 3
    main(["context", "--kb", str(kb.root), "revenue", "--session", "cli_session"])
    assert "untrusted" in capsys.readouterr().out
    monkeypatch.delenv("SQLMEM_LLM", raising=False)
    with pytest.raises(SystemExit) as error:
        main([*common, "learn", "--conversation", "chat", "--llm"])
    assert error.value.code == 2
    assert "llm_setup" in capsys.readouterr().err


@pytest.mark.req("REQ-AMEM-08", "REQ-AMEM-02")
@pytest.mark.parametrize("body", ["not-json-secret-canary", "x" * 65537], ids=["invalid-json", "oversize-file"])
def test_cli_file_errors_do_not_echo_contents(kb, tmp_path, capsys, body):
    path = tmp_path / "bad.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["memory", "--kb", str(kb.root), "save", "--file", str(path)])
    assert error.value.code == 2
    assert body not in capsys.readouterr().err


@pytest.mark.req("REQ-AMEM-08")
def test_mcp_submit_feedback_compact_restore_history_and_errors(kb, monkeypatch):
    from mcp.client.client import Client

    from sqlmem.mcp_server import INSTRUCTIONS

    monkeypatch.delenv("SQLMEM_LLM", raising=False)
    assert "MCP cannot see host chat" in INSTRUCTIONS
    assert "automatically accepted" in INSTRUCTIONS

    async def run():
        async with Client(create_server(kb)) as client:

            async def call(name, args):
                result = await client.call_tool(name, args)
                assert not result.is_error, tool_text(result)
                return json.loads(tool_text(result))

            source = await call(
                "submit_conversation",
                {
                    "conversation_id": "mcp",
                    "messages": [{"role": "user", "content": "Revenue episode"}],
                },
            )
            assert source["revision"] == 1
            task = await call("memory_task", {"conversation_id": "mcp"})
            reply = {
                "task_id": task["task_id"],
                "items": [
                    {
                        "type": "episodic",
                        "key": "mcp",
                        "text": "Revenue episode",
                        "steps": [],
                        "tables": [],
                        "message_indices": [0],
                        "base_revision": 0,
                    }
                ],
            }
            report = await call("save_memory", {"proposal": reply})
            mid = report["items"][0]["memory_id"]
            await call(
                "memory_feedback",
                {
                    "memory_id": mid,
                    "feedback_id": "mcp_feedback",
                    "outcome": "helpful",
                    "expected_revision": 1,
                },
            )
            await call("compact_memory", {"keep": 0})
            assert (await call("recall_memory", {}))["items"] == []
            await call("restore_memory", {"memory_id": mid, "revision": 1, "expected_revision": 2})
            assert len((await call("memory_history", {"memory_id": mid}))["items"]) == 3
            bad = await client.call_tool("recall_memory", {"limit": 0})
            assert bad.is_error
            assert "limit" in tool_text(bad)
            no_config = await client.call_tool("learn_conversation", {"conversation_id": "mcp"})
            assert no_config.is_error
            assert "llm_setup" in tool_text(no_config)

    asyncio.run(run())


@pytest.mark.req("REQ-AMEM-01", "REQ-AMEM-08", "REQ-AMEM-09")
@pytest.mark.parametrize("fail_refresh", [False, True], ids=["success", "refresh-error"])
def test_cli_build_closes_private_connections_it_opens(kb, capsys, monkeypatch, fail_refresh):
    """CLI build owns no persistent private store, even when refresh raises."""
    import sqlmem.cli
    from sqlmem.kb import KnowledgeBase
    from sqlmem.memory_lifecycle import LifecycleStore

    submit(kb)
    kb.close()
    opened: list[sqlite3.Connection] = []
    facades: list[KnowledgeBase] = []
    connect = sqlite3.connect
    refresh = LifecycleStore.refresh_index

    def tracked_connect(path, *args, **kwargs):
        connection = connect(path, *args, **kwargs)
        if str(path).startswith(str(kb.root / "private")):
            opened.append(connection)
        return connection

    def tracked_facade(*args, **kwargs):
        facade = KnowledgeBase(*args, **kwargs)
        facades.append(facade)
        return facade

    def refresh_then_fail(store):
        refresh(store)
        raise ValueError("private refresh failed")

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)
    monkeypatch.setattr(sqlmem.cli, "KnowledgeBase", tracked_facade)
    if fail_refresh:
        monkeypatch.setattr(LifecycleStore, "refresh_index", refresh_then_fail)
    try:
        args = ["build", "--kb", str(kb.root), "--embedder", "hash:256"]
        if fail_refresh:
            with pytest.raises(SystemExit) as error:
                main(args)
            assert error.value.code == 2
        else:
            main(args)
        capsys.readouterr()
        assert opened
        for connection in opened:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                connection.execute("SELECT 1")
    finally:
        # Legacy public-index ownership is outside this regression; don't leak its test facade.
        for facade in facades:
            facade.close()


@pytest.mark.req("REQ-AMEM-03", "REQ-AMEM-08")
def test_mcp_explicit_learning_awaits_cancellable_transport(kb, monkeypatch):
    from mcp.client.client import Client

    from sqlmem.llm import LLM
    from tests.test_memory_llm_bounds import client as streaming_client
    from tests.test_memory_llm_bounds import response

    submit(kb)
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        task = json.loads(kwargs["messages"][1]["content"])
        return response(json.dumps({"task_id": task["task_id"], "items": []}))

    llm = LLM("openai:stub", client=streaming_client(create), memory_mode=True)
    monkeypatch.setattr("sqlmem.llm.memory_client", lambda *args: llm)

    async def run():
        async with Client(create_server(kb)) as client:
            result = await client.call_tool("learn_conversation", {"conversation_id": "chat"})
            assert not result.is_error, tool_text(result)
            assert json.loads(tool_text(result))["operation"] == "learn"

    asyncio.run(run())
    assert len(calls) == 1
