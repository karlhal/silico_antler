# Slice 1b — Multi-Provider Pool with Concurrency-Aware Routing

## Goal

Run LLM calls across Z.AI, Groq, and Gemini simultaneously. Route each request to whichever provider has capacity right now. On 429 or timeout, fail over to the next provider instantly rather than waiting for retry delays on the same one.

This is built on top of Slice 1 (the `OpenAICompatibleClient` abstraction). Implement Slice 1 first.

## Effective free capacity

| Provider | Model | Concurrent slots | Role |
|----------|-------|-----------------|------|
| Z.AI | GLM-4-Plus | 20 | Worker |
| Z.AI | GLM-4.6 | 3 | Planner |
| Gemini | gemini-2.5-flash | ~15 (quota-based) | Worker |
| Gemini | gemini-2.5-pro | ~5 (quota-based) | Planner |
| Groq | llama-3.3-70b | ~5 (varies) | Planner |
| Groq | llama-4-scout | ~5 (varies) | Worker |
| OpenRouter | gemini-2.5-flash:free | ~10 (varies by model) | Worker |
| OpenRouter | google/gemini-2.5-pro | pay-per-token, no hard limit | Planner |

Combined free slots: ~40–55 parallel. OpenRouter adds a useful overflow valve — when Z.AI hits capacity it can absorb the excess, and its model catalogue means you can swap worker models without code changes.

## Design

### Core concept: `ProviderPool`

The pool wraps multiple clients and implements the same `_BaseOrchestrationClient` interface, so the rest of the codebase never knows it's talking to multiple providers.

```
ProviderPool
  ├── ProviderSlot(ZaiOrchestrationClient,        planner="glm-4.6",               worker="glm-4-plus",                      max_concurrency=20)
  ├── ProviderSlot(GeminiOrchestrationClient,     planner="gemini-2.5-pro",        worker="gemini-2.5-flash",                max_concurrency=12)
  ├── ProviderSlot(GroqOrchestrationClient,       planner="llama-3.3-70b",         worker="llama-4-scout",                   max_concurrency=5)
  └── ProviderSlot(OpenRouterOrchestrationClient, planner="google/gemini-2.5-pro", worker="google/gemini-2.5-flash:free",    max_concurrency=10)
```

Each slot tracks:
- `in_flight: int` — requests currently executing on this provider
- `backoff_until: float` — epoch time before which this provider should not be used (set after 429)

### Routing algorithm

```
pick_slot(role: "planner" | "worker") -> ProviderSlot:
    candidates = [s for s in slots if not s.in_backoff() and s.has_capacity()]
    if not candidates:
        candidates = [s for s in slots if not s.in_backoff()]  # over capacity but not 429
    if not candidates:
        candidates = slots  # everyone is in backoff — just try them all
    return min(candidates, key=lambda s: s.in_flight / s.max_concurrency)  # least loaded fraction
```

This uses **load fraction** (in_flight / max_concurrency) rather than raw in_flight count, so a provider with 18/20 slots used is preferred over one with 3/5 slots used.

### Backoff on 429

When a provider returns 429, the pool catches it **before** the inner client's retry logic runs, marks the slot as `backoff_until = now + 60s`, and immediately retries the call on the next best provider. The inner retry logic (2s, 4s, 8s) is disabled when running inside a pool — the pool handles failure routing itself.

## New file: `services/method-development/app/provider_pool.py`

```python
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from .gemini_orchestration_client import (
    _BaseOrchestrationClient,
    OrchestrationClientError,
)


@dataclass
class ProviderSlot:
    client: _BaseOrchestrationClient
    planner_model: str
    worker_model: str
    max_concurrency: int
    _in_flight: int = field(default=0, init=False, repr=False)
    _backoff_until: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def in_backoff(self) -> bool:
        return time.monotonic() < self._backoff_until

    def has_capacity(self) -> bool:
        return self._in_flight < self.max_concurrency

    def load_fraction(self) -> float:
        return self._in_flight / max(self.max_concurrency, 1)

    def acquire(self) -> None:
        with self._lock:
            self._in_flight += 1

    def release(self) -> None:
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)

    def set_backoff(self, seconds: float = 60.0) -> None:
        self._backoff_until = time.monotonic() + seconds


class ProviderPool(_BaseOrchestrationClient):
    """Routes LLM calls across multiple provider slots by concurrency availability."""

    def __init__(self, slots: list[ProviderSlot]) -> None:
        # No settings passed to base — each slot has its own client with its own settings.
        # We override run_prompt entirely, so _BaseOrchestrationClient internals are unused.
        self._slots = slots
        self._lock = threading.Lock()

    def run_prompt(
        self,
        *,
        prompt: str,
        max_output_tokens: int,
        response_mime_type: str,
        model: str | None = None,  # "planner" | "worker" | literal model name
        system_prompt: str | None = None,
    ) -> tuple[str, dict, str]:
        role = model if model in ("planner", "worker") else "worker"
        errors: list[str] = []

        for slot in self._pick_order(role):
            slot.acquire()
            try:
                actual_model = slot.planner_model if role == "planner" else slot.worker_model
                return slot.client.run_prompt(
                    prompt=prompt,
                    max_output_tokens=max_output_tokens,
                    response_mime_type=response_mime_type,
                    model=actual_model,
                    system_prompt=system_prompt,
                )
            except OrchestrationClientError as exc:
                msg = str(exc)
                if "429" in msg or "rate limit" in msg.lower():
                    slot.set_backoff(60.0)
                errors.append(f"{slot.client.__class__.__name__}: {msg}")
            finally:
                slot.release()

        raise OrchestrationClientError(
            f"All providers failed: {'; '.join(errors)}"
        )

    def probe_connection(self):
        # Probe all slots; return first success
        for slot in self._slots:
            try:
                return slot.client.probe_connection()
            except OrchestrationClientError:
                continue
        raise OrchestrationClientError("All providers unreachable")

    def _pick_order(self, role: str) -> list[ProviderSlot]:
        with self._lock:
            available = [s for s in self._slots if not s.in_backoff() and s.has_capacity()]
            if not available:
                available = [s for s in self._slots if not s.in_backoff()]
            if not available:
                available = list(self._slots)
            return sorted(available, key=lambda s: s.load_fraction())

    # Pool delegates all high-level methods to run_prompt, so they inherit routing for free.
    # _generate_content and _extract_response_text are not used — they stay as NotImplemented.
    def _generate_content(self, **kwargs) -> dict:
        raise NotImplementedError("ProviderPool does not implement _generate_content directly")

    def _extract_response_text(self, response_json: dict) -> str:
        raise NotImplementedError
```

## Wiring: `ai_runtime_settings.py` + `main.py`

Add a new config option: `SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED=true`

When enabled, `create_orchestration_client` builds a pool instead of a single client:

```python
# In main.py or wherever the client is instantiated:

def build_llm_client(settings: AiRuntimeSettings) -> _BaseOrchestrationClient:
    if not settings.provider_pool_enabled:
        return create_orchestration_client(settings)  # existing single-provider path

    slots = []
    if settings.zai_api_key:
        zai_client = ZaiOrchestrationClient(settings)
        slots.append(ProviderSlot(
            client=zai_client,
            planner_model="glm-4.6",
            worker_model="glm-4-plus",
            max_concurrency=20,
        ))
    if settings.google_api_key:
        gemini_client = GeminiOrchestrationClient(settings)
        slots.append(ProviderSlot(
            client=gemini_client,
            planner_model="gemini-2.5-pro",
            worker_model="gemini-2.5-flash",
            max_concurrency=12,
        ))
    if settings.groq_api_key:
        groq_client = GroqOrchestrationClient(settings)
        slots.append(ProviderSlot(
            client=groq_client,
            planner_model="llama-3.3-70b-versatile",
            worker_model="meta-llama/llama-4-scout-17b-16e-instruct",
            max_concurrency=5,
        ))
    if settings.openrouter_api_key:
        openrouter_client = OpenRouterOrchestrationClient(settings)
        slots.append(ProviderSlot(
            client=openrouter_client,
            planner_model="google/gemini-2.5-pro",
            worker_model="google/gemini-2.5-flash-preview:free",
            max_concurrency=10,
        ))
    if not slots:
        raise OrchestrationClientError("No API keys configured for provider pool")

    from rich import print as rprint
    rprint(f"[green]Provider pool: {len(slots)} providers, "
           f"{sum(s.max_concurrency for s in slots)} total concurrent slots[/green]")
    return ProviderPool(slots)
```

## Callers: how `run_prompt` is called with roles

The pool needs callers to pass `model="worker"` or `model="planner"` rather than a literal model name, so the pool can pick the right model per provider.

The existing callers in `_BaseOrchestrationClient` pass `self._settings.worker_model` or `self._settings.planner_model` as the `model` parameter. When running inside a pool, those strings become meaningless (the pool doesn't have a single settings object).

**Fix**: In `_BaseOrchestrationClient`, add constants:
```python
ROLE_WORKER = "__worker__"
ROLE_PLANNER = "__planner__"
```

And update every caller in the base class that passes `self._settings.worker_model` to pass `ROLE_WORKER` instead (and similarly for planner). The individual provider clients intercept these sentinels in `run_prompt` and resolve them to `self._settings.worker_model` / `self._settings.planner_model`. The pool resolves them to the per-slot model names.

This is a mechanical find-replace across `gemini_orchestration_client.py` — all callers are within the same file.

## Model translation table

The pool assigns these models per provider per role:

| Provider | Planner | Worker | Rationale |
|----------|---------|--------|-----------|
| Z.AI | glm-4.6 (3 concurrent) | glm-4-plus (20 concurrent) | Most free throughput |
| Gemini | gemini-2.5-pro | gemini-2.5-flash | Best quality fallback |
| Groq | llama-3.3-70b-versatile | llama-4-scout-17b | Low latency tertiary |

## New env vars

```bash
SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED=true
SILICO_METHOD_DEVELOPMENT_ZAI_API_KEY=<key>
SILICO_METHOD_DEVELOPMENT_GOOGLE_API_KEY=<key>       # already exists
SILICO_METHOD_DEVELOPMENT_GROQ_API_KEY=<key>         # already exists
SILICO_METHOD_DEVELOPMENT_OPENROUTER_API_KEY=<key>   # new
# SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER is ignored when pool is enabled
```

## Acceptance criteria

- Pool starts with 3 keys configured → log shows "3 providers, 37 total concurrent slots"
- Pool starts with only Z.AI key → falls back to single-provider mode with Z.AI
- When Z.AI is at capacity (in_flight == 20), next call routes to Gemini
- When a provider returns 429, it enters 60s backoff and next call goes to a different provider
- `probe_connection()` on the pool returns ok if any provider responds
- Single-provider path (`PROVIDER_POOL_ENABLED=false`) unchanged — no regression

## What this does NOT do

- No per-model cost tracking (future work)
- No geographic routing
- No persistent backoff state across restarts — backoff resets on server restart
- No queue/wait when all providers are at capacity — it just picks the least-loaded one and lets the provider's own rate limit handling run
