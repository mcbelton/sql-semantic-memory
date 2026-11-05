"""LLM access for sqlmem: which model to use, how to reach it, and a chat helper that returns parsed JSON.

An LLM is named by a spec "<provider>:<model>":

  azure-openai:<deployment>  Azure OpenAI / Microsoft Foundry (v1 API). Needs AZURE_OPENAI_ENDPOINT
                             (https://<resource>.openai.azure.com). Auth: AZURE_OPENAI_API_KEY, or - when it is not
                             set - Microsoft Entra ID (az login, VS Code / Visual Studio sign-in, managed identity).
  openai:<model>             OpenAI (OPENAI_API_KEY), or any OpenAI-compatible server through a base URL
                             (LM Studio, vLLM, other hosted endpoints).
  ollama:<model>             Local Ollama server (OLLAMA_HOST, default http://localhost:11434); data stays local.

The spec comes from --llm, else $SQLMEM_LLM, else "llm" in <kb>/sqlmem.json (saved by `sqlmem llm --save`).
A base URL override comes from --base-url, else $SQLMEM_LLM_BASE_URL, else "llm_base_url" in sqlmem.json.
Secrets are only ever read from environment variables (or Entra ID), never stored by sqlmem.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
import re
import time
from collections.abc import Callable
from typing import Any

PROVIDERS = ("azure-openai", "openai", "ollama")
AZURE_SCOPE = "https://ai.azure.com/.default"
OPENAI_URL = "https://api.openai.com/v1"


class _MemoryBoundaryError(ValueError):
    """Only application-generated boundary errors can cross the SDK error sanitizer."""


HELP = """No LLM configured. Pick one and save it for this knowledge base, e.g.:
  Azure OpenAI:  $env:AZURE_OPENAI_ENDPOINT = "https://<resource>.openai.azure.com"
                 (optional $env:AZURE_OPENAI_API_KEY; without it Microsoft Entra ID is used - run `az login`)
                 sqlmem llm --kb <kb> --llm azure-openai:<deployment> --save
  OpenAI:        $env:OPENAI_API_KEY = "..."; sqlmem llm --kb <kb> --llm openai:<model> --save
  Local Ollama:  ollama pull <model>; sqlmem llm --kb <kb> --llm ollama:<model> --save
Or skip API setup and let GitHub Copilot be the LLM: ask Copilot to build the knowledge graph with the
knowledge_graph_task / save_knowledge_graph MCP tools, or use `sqlmem graph --export-prompt` / `--import`."""


def resolve_spec(flag: str | None, config: dict[str, Any] | None = None) -> str | None:
    return flag or os.environ.get("SQLMEM_LLM") or (config or {}).get("llm") or None


def resolve_base_url(flag: str | None, config: dict[str, Any] | None = None) -> str | None:
    return flag or os.environ.get("SQLMEM_LLM_BASE_URL") or (config or {}).get("llm_base_url") or None


def memory_client(spec: str | None, base_url: str | None, config: dict[str, Any]) -> LLM:
    """Explicit learning only; configuration never initiates a request."""
    resolved = resolve_spec(spec, config)
    if not resolved:
        raise ValueError(
            "llm_setup: No LLM configured. Set SQLMEM_LLM or save with sqlmem llm --llm provider:model --save; "
            "or use keyless memory_task/save_memory."
        )
    try:
        return LLM(resolved, resolve_base_url(base_url, config), memory_mode=True)
    except Exception:
        raise ValueError(
            "llm_setup: check the LLM extra, provider:model, endpoint and environment credentials; "
            "or use keyless memory_task/save_memory."
        ) from None


def parse_spec(spec: str) -> tuple[str, str]:
    provider, sep, model = (spec or "").partition(":")
    provider, model = provider.strip().lower(), model.strip()
    if provider not in PROVIDERS or not sep or not model:
        raise ValueError(f"Invalid LLM '{spec}': use azure-openai:<deployment>, openai:<model> or ollama:<model>")
    return provider, model


def endpoint_info(provider: str, base_url: str | None = None) -> dict[str, str]:
    """Where requests go and how they authenticate (never contains secrets)."""
    if provider == "azure-openai":
        endpoint = base_url or os.environ.get("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise RuntimeError(
                "Set AZURE_OPENAI_ENDPOINT to your resource URL, e.g. "
                "https://<resource>.openai.azure.com (or pass --base-url)"
            )
        url = endpoint.rstrip("/")
        if not url.endswith("/openai/v1"):
            url += "/openai/v1"
        auth = (
            "API key from $AZURE_OPENAI_API_KEY"
            if os.environ.get("AZURE_OPENAI_API_KEY")
            else "Microsoft Entra ID (az login / VS Code sign-in / managed identity)"
        )
        return {"base_url": url + "/", "auth": auth}
    if provider == "ollama":
        host = base_url or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
        url = (host if "://" in host else "http://" + host).rstrip("/")
        if not url.endswith("/v1"):
            url += "/v1"
        return {"base_url": url + "/", "auth": "none (local server)"}
    url = (base_url or os.environ.get("OPENAI_BASE_URL") or OPENAI_URL).rstrip("/")
    auth = "API key from $OPENAI_API_KEY" if os.environ.get("OPENAI_API_KEY") else "no API key"
    return {"base_url": url + "/", "auth": auth}


def _entra_api_key(openai_mod: Any, credential: Any = None) -> Any:
    if credential is not None:
        from azure.identity.aio import get_bearer_token_provider as async_provider

        return async_provider(credential, os.environ.get("SQLMEM_AZURE_SCOPE", AZURE_SCOPE))
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError as e:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Keyless Azure OpenAI needs 'azure-identity' (pip install azure-identity), or set AZURE_OPENAI_API_KEY"
        ) from e
    token = get_bearer_token_provider(DefaultAzureCredential(), os.environ.get("SQLMEM_AZURE_SCOPE", AZURE_SCOPE))
    annotation = str(inspect.signature(openai_mod.OpenAI.__init__).parameters["api_key"].annotation)
    # Recent SDKs accept a token provider and refresh it; older ones get a static token (valid about an hour).
    return token if "Callable" in annotation else token()


def make_client(
    provider: str,
    base_url: str | None = None,
    timeout: float = 600.0,
    max_retries: int = 4,
    *,
    asynchronous: bool = False,
    credential: Any = None,
) -> Any:
    try:
        import openai
    except ImportError as e:  # pragma: no cover - optional dependency
        raise RuntimeError("LLM features need the 'openai' package: pip install openai azure-identity") from e
    url = endpoint_info(provider, base_url)["base_url"]
    if provider == "azure-openai":
        api_key = os.environ.get("AZURE_OPENAI_API_KEY") or _entra_api_key(openai, credential)
    elif provider == "ollama":
        api_key = "ollama"
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            if url.rstrip("/") == OPENAI_URL:
                raise RuntimeError("Set OPENAI_API_KEY (or pass --base-url for another OpenAI-compatible server)")
            api_key = "not-needed"
    cls = openai.AsyncOpenAI if asynchronous else openai.OpenAI
    return cls(base_url=url, api_key=api_key, timeout=timeout, max_retries=max_retries)


def extract_json(text: str) -> dict[str, Any]:
    """Parse the JSON object in a model reply (tolerates code fences, prose around it and trailing commas)."""
    s = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if fence:
        s = fence.group(1).strip()
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found in the reply")
    body = s[start : end + 1]
    error = "not a JSON object"
    for candidate in (body, re.sub(r",\s*([}\]])", r"\1", body)):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as e:
            error = str(e)
            continue
        if isinstance(data, dict):
            return data
    raise ValueError(f"invalid JSON in the reply: {error}")


def _rejects(e: Exception, word: str) -> bool:
    status = getattr(e, "status_code", None)
    return (status == 400 or type(e).__name__ == "BadRequestError") and word in str(e).lower()


class LLM:
    """Chat-completions client that returns parsed JSON and adapts to what the model supports."""

    def __init__(
        self,
        spec: str,
        base_url: str | None = None,
        client: Any = None,
        timeout: float = 600.0,
        *,
        memory_mode: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.provider, self.model = parse_spec(spec)
        self.spec = f"{self.provider}:{self.model}"
        self.base_url = base_url
        self._owns_client = client is None
        # Memory transports are created/closed inside their cancellable operation, not
        # bound to an event loop at construction. Legacy synchronous clients stay unchanged.
        self.client: Any = (
            client if client is not None or memory_mode else make_client(self.provider, base_url, timeout)
        )
        self.memory_mode = memory_mode
        self._clock = clock
        self._json_mode = True  # turned off for servers that reject response_format
        self._temperature = True  # turned off for models that only allow the default (e.g. reasoning models)

    def close(self) -> None:
        if self._owns_client and self.client is not None:
            self.client.close()

    def describe(self) -> dict[str, str]:
        return {"llm": self.spec, **endpoint_info(self.provider, self.base_url)}

    def chat(self, messages: list[dict[str, Any]], temperature: float | None = 0.1) -> str:
        if self.client is None:
            raise ValueError("model_client: memory mode uses complete_json with its cancellable transport")
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if self._temperature and temperature is not None:
            kwargs["temperature"] = temperature
        if self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            if self._temperature and "temperature" in kwargs and _rejects(e, "temperature"):
                self._temperature = False
                return self.chat(messages, temperature)
            if self._json_mode and _rejects(e, "response_format"):
                self._json_mode = False
                return self.chat(messages, temperature)
            raise
        choice = resp.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise RuntimeError(
                "The model's reply was cut off at its output limit. Use a model with a larger output "
                "limit or split the work into smaller parts (e.g. --max-chars 20000)."
            )
        return choice.message.content or ""

    def complete_json(
        self, system: str, user: str, temperature: float | None = 0.1, retries: int = 1
    ) -> dict[str, Any]:
        if self.memory_mode:
            return self.complete_memory_json(system, user)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(retries + 1):
            text = self.chat(messages, temperature)
            try:
                return extract_json(text)
            except ValueError as e:
                if attempt >= retries:
                    raise ValueError(f"{self.spec} did not return valid JSON: {e}") from e
                messages = [
                    *messages,
                    {"role": "assistant", "content": text[:30000]},
                    {
                        "role": "user",
                        "content": f"That reply was not valid JSON ({e}). Return the corrected JSON "
                        "object only, nothing else.",
                    },
                ]
        raise AssertionError("unreachable")

    def complete_memory_json(self, system: str, user: str, deadline: float | None = None) -> dict[str, Any]:
        """Synchronous entry to the cancellable memory transport; never starts worker threads."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.acomplete_memory_json(system, user, deadline))
        raise ValueError("model_async: await acomplete_memory_json from an active async event loop")

    async def acomplete_memory_json(self, system: str, user: str, deadline: float | None = None) -> dict[str, Any]:
        """Absolute timeout includes connection, headers, body reads, negotiation and cleanup."""
        from .memory_safety import text

        text(system + user, "task", 65536)
        end = min(deadline, self._clock() + 60) if deadline is not None else self._clock() + 60
        remaining = end - self._clock()
        if remaining <= 0:
            raise ValueError("model_deadline: learning exceeded 60 seconds")

        async def operation() -> dict[str, Any]:
            async with contextlib.AsyncExitStack() as stack:
                if self._owns_client:
                    options: dict[str, Any] = {"asynchronous": True}
                    if self.provider == "azure-openai" and not os.environ.get("AZURE_OPENAI_API_KEY"):
                        from azure.identity.aio import DefaultAzureCredential

                        from .llm_transport import IdentityTransport

                        credential = await stack.enter_async_context(
                            DefaultAzureCredential(transport=IdentityTransport(end, self._clock), retry_total=0)
                        )
                        options["credential"] = credential
                    client = make_client(self.provider, self.base_url, remaining, 0, **options)
                    await stack.enter_async_context(client)
                else:
                    client = self.client
                client = client.with_options(max_retries=0) if hasattr(client, "with_options") else client
                if not hasattr(client, "with_streaming_response"):
                    raise ValueError("model_client: inject a cancellable async streaming SDK, or a complete_json stub")
                if hasattr(client, "close") and not inspect.iscoroutinefunction(client.close):
                    raise ValueError("model_client: memory learning requires an AsyncOpenAI SDK, not a sync transport")
                return await self._memory_reply(client, system, user, end)

        try:
            return await asyncio.wait_for(operation(), timeout=remaining)
        except TimeoutError:
            raise ValueError("model_deadline: learning exceeded 60 seconds") from None

    async def _memory_reply(self, client: Any, system: str, user: str, end: float) -> dict[str, Any]:
        from .memory_safety import text

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        for attempt in range(3):
            remaining = end - self._clock()
            if remaining <= 0:
                raise _MemoryBoundaryError("model_deadline: learning exceeded 60 seconds")
            try:
                async with client.with_streaming_response.chat.completions.create(
                    **kwargs, timeout=remaining
                ) as response:
                    parts = bytearray()
                    if self._clock() >= end:
                        raise _MemoryBoundaryError("model_deadline: learning exceeded 60 seconds")
                    async for part in response.iter_bytes():
                        if self._clock() >= end:
                            raise _MemoryBoundaryError("model_deadline: learning exceeded 60 seconds")
                        if len(parts) + len(part) > 262144:
                            raise _MemoryBoundaryError(
                                "size_limit: reply envelope exceeds 256 KiB; no proposals applied"
                            )
                        parts.extend(part)
            except Exception as error:
                if isinstance(error, _MemoryBoundaryError):
                    raise
                if attempt < 2:
                    if "temperature" in kwargs and _rejects(error, "temperature"):
                        del kwargs["temperature"]
                        continue
                    if "response_format" in kwargs and _rejects(error, "response_format"):
                        del kwargs["response_format"]
                        continue
                raise ValueError("model_failed: check endpoint configuration; no proposals applied") from None
            if self._clock() >= end:
                raise ValueError("model_deadline: learning exceeded 60 seconds")
            try:
                envelope = json.loads(parts)
                choices = envelope["choices"]
                if len(choices) != 1 or choices[0]["finish_reason"] != "stop":
                    raise ValueError("model_finish: need one complete JSON reply; no proposals applied")
                body = choices[0]["message"]["content"]
            except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, RecursionError):
                raise ValueError("model_json: invalid completion envelope; no proposals applied") from None
            text(body, "reply", 65536, 1)
            try:
                return extract_json(body)
            except ValueError:
                raise ValueError("model_json: reply must contain a JSON object; request a fresh task") from None
        raise AssertionError("unreachable")
