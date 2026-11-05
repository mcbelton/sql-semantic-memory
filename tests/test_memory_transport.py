"""Absolute transport deadlines without sockets, endpoint calls or background workers."""

import asyncio
import json
import time
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI, OpenAI

from sqlmem.llm import LLM

BODY = json.dumps(
    {
        "id": "test",
        "object": "chat.completion",
        "created": 0,
        "model": "stub",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"ok":true}'}}],
    }
).encode()


@pytest.mark.req("REQ-AMEM-03")
def test_absolute_deadline_stops_slow_drip_before_consuming_whole_body(monkeypatch):
    now = [0.0]
    reads = []
    closed = []

    class SyncBody(httpx.SyncByteStream):
        def __iter__(self):
            for part in (BODY[:30], BODY[30:60], BODY[60:90], BODY[90:]):
                now[0] += 20
                reads.append(now[0])
                yield part

        def close(self):
            closed.append("body")

    class AsyncBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            for part in (BODY[:30], BODY[30:60], BODY[60:90], BODY[90:]):
                await asyncio.sleep(0)
                now[0] += 20
                reads.append(now[0])
                yield part

        async def aclose(self):
            closed.append("body")

    class SyncTransport(httpx.BaseTransport):
        def handle_request(self, request):
            now[0] += 20
            return httpx.Response(200, stream=SyncBody(), headers={"content-type": "application/json"})

    class AsyncTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            now[0] += 20
            return httpx.Response(200, stream=AsyncBody(), headers={"content-type": "application/json"})

    clients: list[OpenAI | AsyncOpenAI] = []

    def factory(provider, base_url=None, timeout=600, max_retries=4, *, asynchronous=False):
        # The installed SDK supports both HTTPX generations at runtime; its annotations
        # only name the newer one. Keep transport injection at this SDK boundary.
        options: dict[str, Any] = {"api_key": "stub", "base_url": "https://invalid.test/v1", "max_retries": max_retries}
        result: OpenAI | AsyncOpenAI
        if asynchronous:
            options["http_client"] = httpx.AsyncClient(transport=AsyncTransport())
            result = AsyncOpenAI(**options)
        else:
            options["http_client"] = httpx.Client(transport=SyncTransport())
            result = OpenAI(**options)
        clients.append(result)
        return result

    monkeypatch.setattr("sqlmem.llm.make_client", factory)
    llm = LLM("openai:stub", memory_mode=True, clock=lambda: now[0])
    try:
        with pytest.raises(ValueError, match="model_deadline"):
            llm.complete_memory_json("static", "data")
        assert now[0] <= 60
        assert len(reads) <= 2
        assert closed == ["body"]
    finally:
        for sdk in clients:
            if isinstance(sdk, AsyncOpenAI):
                asyncio.run(sdk.close())
            else:
                sdk.close()


@pytest.mark.req("REQ-AMEM-03")
def test_absolute_deadline_cancels_and_closes_in_flight_read(monkeypatch):
    cancelled = []
    closed = []

    class BlockedBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            try:
                yield b'{"'
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                raise

        async def aclose(self):
            closed.append(True)

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, stream=BlockedBody(), headers={"content-type": "application/json"})

    def factory(*args, **kwargs):
        options: dict[str, Any] = {
            "api_key": "stub",
            "base_url": "https://invalid.test/v1",
            "http_client": httpx.AsyncClient(transport=Transport()),
            "max_retries": 0,
        }
        return AsyncOpenAI(**options)

    monkeypatch.setattr("sqlmem.llm.make_client", factory)
    llm = LLM("openai:stub", memory_mode=True)
    started = time.monotonic()
    with pytest.raises(ValueError, match="model_deadline"):
        llm.complete_memory_json("static", "data", deadline=started + 0.1)
    assert time.monotonic() - started < 1
    assert cancelled == [True]
    assert closed == [True]


@pytest.mark.req("REQ-AMEM-03")
def test_async_azure_identity_uses_and_closes_cancellable_httpx_transport(monkeypatch):
    from azure.core.credentials import AccessToken

    credentials = []
    tokens = []
    real_sdk = AsyncOpenAI

    class Credential:
        def __init__(self, **kwargs):
            self.transport = kwargs["transport"]
            self.closed = False
            credentials.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            await self.transport.close()
            self.closed = True

        async def get_token(self, *scopes, **kwargs):
            tokens.append(scopes)
            return AccessToken("stub", int(time.time()) + 3600)

    async def handle(request):
        assert request.headers["authorization"] == "Bearer stub"
        return httpx.Response(200, content=BODY, headers={"content-type": "application/json"})

    def sdk_factory(**kwargs):
        kwargs["http_client"] = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        return real_sdk(**kwargs)

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://invalid.test")
    monkeypatch.setattr("azure.identity.aio.DefaultAzureCredential", Credential)
    monkeypatch.setattr("openai.AsyncOpenAI", sdk_factory)
    assert LLM("azure-openai:stub", memory_mode=True).complete_memory_json("static", "data") == {"ok": True}
    assert tokens
    assert credentials[0].closed
    assert credentials[0].transport.client.is_closed


@pytest.mark.req("REQ-AMEM-03")
def test_identity_httpx_bridge_reads_form_response_and_closes():
    from azure.core.pipeline.transport import HttpRequest

    from sqlmem.llm_transport import IdentityTransport

    async def run():
        seen = []

        async def handle(request):
            seen.append(await request.aread())
            return httpx.Response(200, json={"access_token": "stub"})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        async with IdentityTransport(time.monotonic() + 60, time.monotonic, http) as transport:
            await transport.open()
            response = await transport.send(HttpRequest("POST", "https://invalid.test", data={"grant": "client"}))
            assert json.loads(response.text()) == {"access_token": "stub"}
            assert response.status_code == 200
            assert seen == [b"grant=client"]
        assert http.is_closed

    asyncio.run(run())
