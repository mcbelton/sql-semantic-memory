"""Cancellable HTTPX bridge for Azure's public async identity transport API.

Azure identity's default async transport requires aiohttp, which is not an sqlmem
dependency. HTTPX is declared in sqlmem's LLM extra. This keeps credential HTTP
inside the same absolute memory deadline without executor threads or new extras.
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any

import httpx
from azure.core.pipeline.transport import AsyncHttpResponse, AsyncHttpTransport, HttpRequest


class IdentityResponse(AsyncHttpResponse):
    def __init__(self, request: HttpRequest, response: httpx.Response, body: bytes):
        super().__init__(request, response)
        self.status_code = response.status_code
        self.headers = response.headers
        self.reason = response.reason_phrase
        self.content_type = response.headers.get("content-type")
        self._body = body

    def body(self) -> bytes:
        return self._body


class IdentityTransport(AsyncHttpTransport[HttpRequest, IdentityResponse]):
    def __init__(self, deadline: float, clock: Callable[[], float], client: httpx.AsyncClient | None = None):
        self.deadline = deadline
        self.clock = clock
        self.client = client if client is not None else httpx.AsyncClient()

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> IdentityTransport:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        await self.close()

    async def send(self, request: HttpRequest, **kwargs: Any) -> IdentityResponse:
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise ValueError("model_deadline: credential request exceeded learning deadline")
        async with self.client.stream(
            request.method,
            request.url,
            headers=dict(request.headers),
            content=request.body if not isinstance(request.body, dict) else None,
            data=request.body if isinstance(request.body, dict) else None,
            timeout=remaining,
        ) as response:
            body = bytearray()
            async for part in response.aiter_bytes():
                if self.clock() >= self.deadline:
                    raise ValueError("model_deadline: credential request exceeded learning deadline")
                if len(body) + len(part) > 65536:
                    raise ValueError("size_limit: credential response exceeds 64 KiB")
                body.extend(part)
            return IdentityResponse(request, response, bytes(body))
