"""LLM configuration + client tests against a local OpenAI-compatible stub server (real `openai` SDK)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

pytest.importorskip("openai")

from sqlmem.cli import main
from sqlmem.llm import LLM, endpoint_info, extract_json, parse_spec, resolve_spec

LLM_ENV = (
    "SQLMEM_LLM",
    "SQLMEM_LLM_BASE_URL",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OLLAMA_HOST",
    "SQLMEM_AZURE_SCOPE",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in LLM_ENV:
        monkeypatch.delenv(name, raising=False)


class Stub:
    """Minimal /chat/completions server: records requests, can reject parameters like some real models do."""

    def __init__(self, replies, reject=()):
        self.replies, self.reject = list(replies), set(reject)
        self.requests: list[dict[str, Any]] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.requests.append(
                    {"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body}
                )
                for param in stub.reject:
                    if param in body:
                        msg = (
                            f"Unsupported value: '{param}' does not support 0.1 with this model."
                            if param == "temperature"
                            else f"Invalid parameter: '{param}' is not supported with this model."
                        )
                        self._send(
                            400,
                            {"error": {"message": msg, "type": "invalid_request_error", "param": param, "code": None}},
                        )
                        return
                content = stub.replies.pop(0) if len(stub.replies) > 1 else stub.replies[0]
                self._send(
                    200,
                    {
                        "id": "c1",
                        "object": "chat.completion",
                        "created": 0,
                        "model": body["model"],
                        "choices": [
                            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    },
                )

            def _send(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub_factory():
    stubs = []

    def make(replies=('{"ok": true}',), reject=()):
        s = Stub(replies, reject)
        stubs.append(s)
        return s

    yield make
    for s in stubs:
        s.close()


@pytest.mark.req("REQ-LLM-01")
def test_spec_resolution_order(monkeypatch):
    assert resolve_spec(None, {}) is None
    assert resolve_spec(None, {"llm": "ollama:a"}) == "ollama:a"
    monkeypatch.setenv("SQLMEM_LLM", "openai:b")
    assert resolve_spec(None, {"llm": "ollama:a"}) == "openai:b"
    assert resolve_spec("azure-openai:c", {"llm": "ollama:a"}) == "azure-openai:c"
    assert parse_spec("Azure-OpenAI: gpt-4o ") == ("azure-openai", "gpt-4o")
    for bad in ("gpt-4o", "azure-openai:", "github:openai/gpt-4o", ""):
        with pytest.raises(ValueError, match="Invalid LLM"):
            parse_spec(bad)


@pytest.mark.req("REQ-LLM-01")
def test_endpoint_info(monkeypatch):
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        endpoint_info("azure-openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://res.openai.azure.com/")
    info = endpoint_info("azure-openai")
    assert info["base_url"] == "https://res.openai.azure.com/openai/v1/"
    assert "Entra ID" in info["auth"]
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    assert "AZURE_OPENAI_API_KEY" in endpoint_info("azure-openai")["auth"]
    assert (
        endpoint_info("azure-openai", "https://x.services.ai.azure.com/openai/v1")["base_url"]
        == "https://x.services.ai.azure.com/openai/v1/"
    )
    assert endpoint_info("ollama")["base_url"] == "http://localhost:11434/v1/"
    assert endpoint_info("ollama", "gpu-box:11434")["base_url"] == "http://gpu-box:11434/v1/"
    assert endpoint_info("openai")["base_url"] == "https://api.openai.com/v1/"


@pytest.mark.req("REQ-LLM-02")
def test_extract_json():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Sure! Here it is:\n```json\n{"a": [1, 2,],}\n```\nDone.') == {"a": [1, 2]}
    for bad in ("no json here", "[1, 2]", '{"a": }'):
        with pytest.raises(ValueError, match="JSON"):
            extract_json(bad)


@pytest.mark.req("REQ-LLM-01", "REQ-LLM-02")
def test_openai_compatible_server_and_fallbacks(stub_factory, monkeypatch):
    stub = stub_factory(
        replies=["not json at all", '```json\n{"answer": 42}\n```'], reject=("response_format", "temperature")
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm = LLM("openai:my-model", base_url=stub.url + "/v1")
    assert llm.complete_json("system", "question") == {"answer": 42}
    paths = {r["path"] for r in stub.requests}
    assert paths == {"/v1/chat/completions"}
    assert all(r["headers"]["authorization"] == "Bearer sk-test" for r in stub.requests)
    final = stub.requests[-1]["body"]
    assert final["model"] == "my-model"
    assert "response_format" not in final
    assert "temperature" not in final
    assert "not valid JSON" in final["messages"][-1]["content"]  # repair round-trip after the bad reply


@pytest.mark.req("REQ-LLM-01")
def test_openai_requires_key_only_for_api_openai_com(stub_factory):
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        LLM("openai:gpt-4o")
    stub = stub_factory()
    LLM("openai:local-model", base_url=stub.url + "/v1").complete_json("s", "u")  # e.g. LM Studio, no key
    assert stub.requests[0]["body"]["response_format"] == {"type": "json_object"}


@pytest.mark.req("REQ-LLM-01")
def test_azure_openai_with_api_key(stub_factory, monkeypatch):
    stub = stub_factory()
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", stub.url)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
    assert LLM("azure-openai:gpt-4o-mini").complete_json("s", "u") == {"ok": True}
    req = stub.requests[0]
    assert req["path"] == "/openai/v1/chat/completions"
    assert req["body"]["model"] == "gpt-4o-mini"
    assert req["headers"]["authorization"] == "Bearer azure-key"


@pytest.mark.req("REQ-LLM-01")
def test_azure_openai_with_entra_id(stub_factory, monkeypatch):
    import azure.identity

    scopes = []

    class FakeCredential:
        pass

    def fake_provider(credential, scope):
        assert isinstance(credential, FakeCredential)
        scopes.append(scope)
        return lambda: "entra-token"

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(azure.identity, "get_bearer_token_provider", fake_provider)
    stub = stub_factory()
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", stub.url)
    LLM("azure-openai:gpt-4o").complete_json("s", "u")
    assert scopes == ["https://ai.azure.com/.default"]
    assert stub.requests[0]["headers"]["authorization"] == "Bearer entra-token"


@pytest.mark.req("REQ-LLM-01")
def test_ollama(stub_factory, monkeypatch):
    stub = stub_factory()
    monkeypatch.setenv("OLLAMA_HOST", stub.url)
    LLM("ollama:llama3.1").complete_json("s", "u")
    assert stub.requests[0]["path"] == "/v1/chat/completions"
    assert stub.requests[0]["headers"]["authorization"] == "Bearer ollama"


@pytest.mark.req("REQ-LLM-03")
def test_llm_command_saves_and_tests(stub_factory, monkeypatch, tmp_path, capsys):
    stub = stub_factory(replies=['{"ok": true, "model": "stub"}'])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    kb = str(tmp_path / "kb")
    main(["llm", "--kb", kb, "--llm", "openai:stub-model", "--base-url", stub.url + "/v1", "--save"])
    out = capsys.readouterr().out
    assert "Saved in" in out
    assert "Test:      OK" in out
    assert "openai:stub-model" in out
    saved = json.loads((tmp_path / "kb" / "sqlmem.json").read_text())
    assert saved == {"llm": "openai:stub-model", "llm_base_url": stub.url + "/v1"}  # no secrets stored
    main(["llm", "--kb", kb])  # uses the saved setting
    assert f"(from {tmp_path / 'kb' / 'sqlmem.json'})" in capsys.readouterr().out
    assert len(stub.requests) == 2


@pytest.mark.req("REQ-LLM-03")
def test_llm_command_without_configuration(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["llm", "--kb", str(tmp_path / "kb")])
    assert exc.value.code == 1
    assert "No LLM configured" in capsys.readouterr().out
