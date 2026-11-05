"""Memory-specific LLM transport options, with a deterministic clock and in-process SDK."""

import json
from types import SimpleNamespace

import pytest

from sqlmem.llm import LLM


def response(body='{"ok":true}', finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=body))])


class BadParameter(Exception):
    status_code = 400


def client(create):
    class Response:
        async def __aenter__(self):
            self.value = create(**self.kwargs)
            return self

        async def __aexit__(self, *args):
            return None

        async def iter_bytes(self):
            yield json.dumps(
                {
                    "choices": [
                        {"finish_reason": choice.finish_reason, "message": {"content": choice.message.content}}
                        for choice in self.value.choices
                    ]
                }
            ).encode()

        def __init__(self, kwargs):
            self.kwargs = kwargs

    def streaming_create(**kwargs):
        return Response(kwargs)

    return SimpleNamespace(
        with_streaming_response=SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=streaming_create))
        )
    )


@pytest.mark.req("REQ-AMEM-03")
def test_memory_negotiation_has_three_attempts_and_remaining_deadline():
    times = [100.0]
    seen = []

    def create(**kwargs):
        seen.append(kwargs)
        times[0] += 10
        if len(seen) == 1:
            raise BadParameter("temperature unsupported")
        if len(seen) == 2:
            raise BadParameter("response_format unsupported")
        return response()

    llm = LLM("ollama:stub", client=client(create), memory_mode=True, clock=lambda: times[0])
    assert llm.complete_json("static", "data") == {"ok": True}
    assert [r["timeout"] for r in seen] == [60, 50, 40]
    assert "temperature" not in seen[1]
    assert "response_format" not in seen[2]


@pytest.mark.req("REQ-AMEM-03")
@pytest.mark.parametrize(
    ("body", "finish", "match"),
    [
        ("not json", "stop", "model_json"),
        (json.dumps({"x": "a" * 65536}), "stop", "reply"),
        ('{"ok":true}', "length", "model_finish"),
        ('{"ok":true}', "tool_calls", "model_finish"),
    ],
    ids=["invalid-json", "oversize", "truncated", "tool-calls"],
)
def test_memory_rejects_bad_reply_once(body, finish, match):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return response(body, finish)

    llm = LLM("openai:stub", client=client(create), memory_mode=True)
    with pytest.raises(ValueError, match=match):
        llm.complete_json("static", "data")
    assert len(calls) == 1


@pytest.mark.req("REQ-AMEM-03")
def test_memory_deadline_prevents_apply_or_more_attempts():
    times = [100.0]

    def create(**kwargs):
        times[0] += 61
        raise BadParameter("temperature")

    llm = LLM("azure-openai:stub", client=client(create), clock=lambda: times[0])
    with pytest.raises(ValueError, match="model_deadline"):
        llm.complete_memory_json("static", "data")


@pytest.mark.req("REQ-AMEM-03")
def test_memory_disables_sdk_retries_and_no_provider_fallback():
    options = []

    class SDK:
        with_streaming_response = client(lambda **kwargs: response()).with_streaming_response

        def with_options(self, **kwargs):
            options.append(kwargs)
            return self

    llm = LLM("openai:stub", client=SDK())
    assert llm.complete_memory_json("static", "data") == {"ok": True}
    assert options == [{"max_retries": 0}]


@pytest.mark.req("REQ-AMEM-02", "REQ-AMEM-03")
def test_streaming_sdk_value_errors_are_sanitized():
    def create(**kwargs):
        raise ValueError("api_key=provider-secret user@example.com")

    llm = LLM("openai:stub", client=client(create), memory_mode=True)
    with pytest.raises(ValueError, match="model_failed") as error:
        llm.complete_json("static", "data")
    assert "provider-secret" not in str(error.value)
