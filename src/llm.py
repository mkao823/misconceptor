"""Thin client for any OpenAI-compatible chat endpoint, with an on-disk cache.

Features: temperature / seed / max_tokens, JSON-mode output, token-usage capture,
and a cache under results/cache/ keyed by a hash of (model, messages, temperature,
seed, max_tokens, json_mode) so re-runs are free and deterministic.

The network layer is a pluggable ``transport``: a callable that takes the request
kwargs (as passed to ``chat.completions.create``) and returns the response as a
plain dict in the OpenAI chat-completion shape. ``OpenAITransport`` wraps the
official SDK; ``MockTransport`` returns canned content for tests and smoke runs.

Context window. Ollama loads a model with a fixed context (4096 tokens unless the
server was started with OLLAMA_CONTEXT_LENGTH) and silently truncates a longer
prompt; the OpenAI-compatible endpoint cannot change it per request.
``LLMClient.loaded_context_length()`` reads the window the model is loaded with so
a run can refuse to start when its prompts would not fit (scripts/run_condition.py).
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.config import RESULTS_DIR, get_api_key, load_config, resolve_model

CACHE_DIR = RESULTS_DIR / "cache"
CACHE_VERSION = 1

Transport = Callable[[dict], dict]


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.prompt_tokens + other.prompt_tokens,
                     self.completion_tokens + other.completion_tokens)

    def to_dict(self) -> dict:
        return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens}


@dataclass
class ChatResponse:
    text: str
    usage: Usage
    model: str
    cached: bool
    cache_key: str
    finish_reason: str | None = None
    reasoning: str | None = None      # gpt-oss / deepseek-r1 expose hidden reasoning here
    raw: dict = field(default_factory=dict)


class LLMError(RuntimeError):
    """Raised when the endpoint cannot be reached or returns no usable completion."""


def make_cache_key(model: str, messages: list[dict], temperature: float, seed: int | None,
                   max_tokens: int, json_mode: bool) -> str:
    payload = {"v": CACHE_VERSION, "model": model, "messages": messages, "temperature": temperature,
               "seed": seed, "max_tokens": max_tokens, "json_mode": bool(json_mode)}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _extract(response: dict, model: str, cached: bool, key: str) -> ChatResponse:
    try:
        choice = response["choices"][0]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"Response has no choices: {response!r}") from e
    message = choice.get("message") or {}
    text = message.get("content")
    if text is None:
        text = ""
    usage = response.get("usage") or {}
    return ChatResponse(
        text=text,
        usage=Usage(int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)),
        model=response.get("model") or model,
        cached=cached,
        cache_key=key,
        finish_reason=choice.get("finish_reason"),
        reasoning=message.get("reasoning") or message.get("reasoning_content"),
        raw=response,
    )


class OpenAITransport:
    """Calls ``chat.completions.create`` on the official SDK and returns a plain dict."""

    def __init__(self, base_url: str | None, api_key: str, timeout: float = 300.0):
        from openai import OpenAI  # imported lazily so tests with MockTransport need no SDK

        self.base_url = base_url
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    def __call__(self, request: dict) -> dict:
        return self._client.chat.completions.create(**request).model_dump()

    def is_reachable(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:  # noqa: BLE001 - any failure means "not reachable"
            return False

    def context_length(self, model: str) -> int | None:
        """Context window (tokens) an Ollama server has ``model`` loaded with, from /api/ps.
        None when the model is not loaded or the server does not answer like Ollama."""
        if not self.base_url:
            return None
        root = self.base_url.rstrip("/")
        root = root[:-3] if root.endswith("/v1") else root
        try:
            with urllib.request.urlopen(f"{root}/api/ps", timeout=5.0) as resp:
                loaded = json.load(resp).get("models") or []
        except Exception:  # noqa: BLE001
            return None
        for m in loaded:
            if model in (m.get("name"), m.get("model")):
                return m.get("context_length")
        return None


class MockTransport:
    """Returns canned content; records every request. ``content`` may be a str or a callable."""

    def __init__(self, content: str | Callable[[dict], str], prompt_tokens: int = 10,
                 completion_tokens: int = 5, model: str = "mock"):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.model = model
        self.calls: list[dict] = []

    def __call__(self, request: dict) -> dict:
        self.calls.append(request)
        text = self.content(request) if callable(self.content) else self.content
        return {
            "id": f"mock-{len(self.calls)}",
            "model": self.model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                      "total_tokens": self.prompt_tokens + self.completion_tokens},
        }

    def is_reachable(self) -> bool:
        return True


class LLMClient:
    """Chat client bound to one (provider, model) with a content-addressed disk cache."""

    def __init__(self, model: str | None = None, *, transport: Transport | None = None,
                 cache_dir: Path | str | None = CACHE_DIR, use_cache: bool = True,
                 max_retries: int = 3, retry_wait: float = 2.0, models_cfg: dict | None = None):
        self.cfg = models_cfg if models_cfg is not None else load_config("models")
        self.provider, self.model = resolve_model(model, self.cfg)
        self.provider_cfg = self.cfg["providers"][self.provider]
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.use_cache = use_cache and self.cache_dir is not None
        self.max_retries = max_retries
        self.retry_wait = retry_wait
        if transport is None:
            transport = OpenAITransport(self.provider_cfg.get("base_url"),
                                        get_api_key(self.provider, self.cfg["providers"]))
        self.transport = transport
        self.usage = Usage()           # tokens for calls that actually hit the endpoint
        self.usage_all = Usage()       # tokens including cache hits (what a cold run would cost)
        self.n_calls = 0
        self.n_cached = 0

    # -- cache -----------------------------------------------------------------
    def _cache_path(self, key: str) -> Path:
        assert self.cache_dir is not None
        return self.cache_dir / key[:2] / f"{key}.json"

    def _cache_read(self, key: str) -> dict | None:
        if not self.use_cache:
            return None
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)["response"]
        except (OSError, ValueError, KeyError):
            return None

    def _cache_write(self, key: str, request: dict, response: dict) -> None:
        if not self.use_cache:
            return
        path = self._cache_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump({"cache_version": CACHE_VERSION, "provider": self.provider,
                       "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "request": request, "response": response}, f, ensure_ascii=False, indent=1)
        tmp.replace(path)

    def is_cached(self, messages: list[dict], *, temperature: float = 0.0, seed: int | None = 0,
                  max_tokens: int = 1024, json_mode: bool = True) -> bool:
        """True when ``chat`` with these arguments would be served from the disk cache."""
        if not self.use_cache:
            return False
        return self._cache_path(make_cache_key(self.model, messages, temperature, seed, max_tokens,
                                               json_mode)).exists()

    def loaded_context_length(self, load: bool = True) -> int | None:
        """Context window the server has this model loaded with (Ollama only), else None.

        With ``load``, a model that is not loaded yet is loaded first with a one-token
        request that bypasses the cache and the usage counters.
        """
        probe = getattr(self.transport, "context_length", None)
        if self.provider != "ollama" or probe is None:
            return None
        ctx = probe(self.model)
        if ctx is None and load:
            try:
                self.transport({"model": self.model, "messages": [{"role": "user", "content": "ping"}],
                                "max_tokens": 1})
            except Exception:  # noqa: BLE001 - the real calls will report the failure
                return None
            ctx = probe(self.model)
        return ctx

    # -- calls -----------------------------------------------------------------
    def chat(self, messages: list[dict], *, temperature: float = 0.0, seed: int | None = 0,
             max_tokens: int = 1024, json_mode: bool = True, use_cache: bool | None = None) -> ChatResponse:
        key = make_cache_key(self.model, messages, temperature, seed, max_tokens, json_mode)
        cache_ok = self.use_cache if use_cache is None else (use_cache and self.cache_dir is not None)
        if cache_ok:
            hit = self._cache_read(key)
            if hit is not None:
                resp = _extract(hit, self.model, cached=True, key=key)
                self.n_cached += 1
                self.usage_all = self.usage_all + resp.usage
                return resp

        request: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature,
                                   "max_tokens": max_tokens}
        if seed is not None:
            request["seed"] = seed
        if json_mode:
            request["response_format"] = {"type": "json_object"}

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                raw = self.transport(request)
                break
            except Exception as e:  # noqa: BLE001 - retry anything transient, then report
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(self.retry_wait * (2 ** attempt))
        else:
            base = self.provider_cfg.get("base_url") or "the API"
            raise LLMError(f"{self.provider}/{self.model}: request failed after {self.max_retries + 1} attempts "
                           f"({type(last_err).__name__}: {last_err}). Is the server at {base} running? "
                           f"For Ollama: `ollama serve` or open the Ollama app.") from last_err

        resp = _extract(raw, self.model, cached=False, key=key)
        self.n_calls += 1
        self.usage = self.usage + resp.usage
        self.usage_all = self.usage_all + resp.usage
        if cache_ok:
            self._cache_write(key, request, raw)
        return resp

    def is_reachable(self) -> bool:
        probe = getattr(self.transport, "is_reachable", None)
        return bool(probe()) if probe else True

    def stats(self) -> dict:
        return {"calls_uncached": self.n_calls, "calls_cached": self.n_cached,
                "tokens_uncached": self.usage.to_dict(), "tokens_total": self.usage_all.to_dict()}
