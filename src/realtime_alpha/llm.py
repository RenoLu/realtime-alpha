"""Lean, provider-agnostic LLM client.

A single ``complete()`` method over the Anthropic Messages API via ``httpx`` (no langchain),
plus a deterministic ``MockClient`` so the LLM strategies are testable and CI runs key-less.
Mirrors content-engine's ModelClient pattern.

Models (see the ``claude-api`` reference): ``claude-haiku-4-5`` for cheap bulk calls
(no ``thinking``/``effort`` params), ``claude-opus-4-8`` for the deep synthesis (set
``thinking=True`` → adaptive thinking).
"""

from __future__ import annotations

import abc
import json
import os
from collections.abc import Callable
from typing import Any

import httpx

ANTHROPIC_API = "https://api.anthropic.com"
HAIKU = "claude-haiku-4-5"
OPUS = "claude-opus-4-8"


class ModelError(RuntimeError):
    pass


def extract_json(text: str) -> dict[str, Any]:
    """Pull the last JSON object out of a model's text response.

    Scans for every position where a balanced object decodes (via ``raw_decode``) and
    returns the *last* one, so braces appearing earlier in prose (a heading, an example)
    don't break parsing when the model is told to END with its JSON verdict.
    """
    decoder = json.JSONDecoder()
    found: dict[str, Any] | None = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            found = obj
    if found is None:
        raise ModelError(f"no JSON object in model output: {text[:120]!r}")
    return found


class ModelClient(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        thinking: bool = False,
    ) -> str:
        """Return the model's text completion for ``system`` + user ``prompt``."""
        raise NotImplementedError


class AnthropicClient(ModelClient):
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = HAIKU,
        base_url: str = ANTHROPIC_API,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ModelError("ANTHROPIC_API_KEY is required for the Anthropic client")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=60.0)

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        thinking: bool = False,
    ) -> str:
        body: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if thinking:
            body["thinking"] = {"type": "adaptive"}
        resp = self._client.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )


class MockClient(ModelClient):
    name = "mock"

    # A valid, neutral verdict so a key-less run exercises the LLM strategies end-to-end
    # (they emit zero-confidence predictions) instead of erroring on an unparseable reply.
    NEUTRAL = '{"stance": "neutral", "yhat": 0.0, "confidence": 0.0}'

    def __init__(
        self,
        *,
        canned: str = NEUTRAL,
        responder: Callable[[str, str], str] | None = None,
    ) -> None:
        self._canned = canned
        self._responder = responder

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        thinking: bool = False,
    ) -> str:
        return self._responder(system, prompt) if self._responder else self._canned


def build_model_client(api_key: str | None = None, *, model: str = HAIKU) -> ModelClient:
    """Anthropic client when a key is present; otherwise a deterministic mock (key-less CI/dev)."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    return AnthropicClient(key, model=model) if key else MockClient()
