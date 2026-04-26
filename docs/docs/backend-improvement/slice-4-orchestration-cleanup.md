# Slice 4 — Orchestration Cleanup

## Problem

The orchestration layer has accumulated conflicting rules, misleading names, and hidden coupling:

1. **Default model mismatch**: `ai_runtime_settings.py` defaults planner/worker to `"openai/gpt-oss-20b"` when `llm_provider == "groq"` — that model ID doesn't exist on Groq's API. This causes silent fallback-to-nothing on first boot.
2. **`enable_llm_orchestration` defaults to `False`** in the dataclass but the production `.env` sets it to `True`. Any code that reads the raw dataclass default (not from `load_ai_runtime_settings`) will silently disable LLM orchestration.
3. **`GeminiOrchestrationClient` naming** is used everywhere even when running Groq or DeepSeek. All type hints, import names, and log lines say "Gemini". This is confusing when debugging.
4. **C12 orchestration and recommendation engine have separate step-budget trackers** that don't share state. A C12 run triggered inside a recommendation run can double-count LLM calls.
5. **Router error handling hides extraction failures** — `recommendations_router.py` catches all exceptions and returns a degraded response. Legitimate extraction bugs get buried under "upstream_unavailable".

## Files to change

### `services/method-development/app/ai_runtime_settings.py`

Fix the bad model defaults:
```python
# Before:
default_planner_model = (
    "openai/gpt-oss-20b" if llm_provider == "groq" else "gemini-2.5-pro"
)

# After:
_PROVIDER_DEFAULT_PLANNER = {
    "gemini": "gemini-2.5-pro",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
}
_PROVIDER_DEFAULT_WORKER = {
    "gemini": "gemini-2.5-flash",
    "groq": "meta-llama/llama-4-scout-17b-16e-instruct",
    "deepseek": "deepseek-chat",
}
default_planner_model = _PROVIDER_DEFAULT_PLANNER.get(llm_provider, "deepseek-chat")
default_worker_model = _PROVIDER_DEFAULT_WORKER.get(llm_provider, "deepseek-chat")
```

Also: make `enable_llm_orchestration` default to `True` in the dataclass since disabling it silently cripples the system and there's no good reason to have it off by default in code.

### `services/method-development/app/gemini_orchestration_client.py`

Rename types without breaking external callers:
- Rename `GeminiOrchestrationClient` base interface to `OrchestrationClient` (abstract base)
- Keep `GeminiOrchestrationClient` as the Gemini-specific subclass (no rename needed there — it IS Gemini)
- Rename `GeminiClientError` → `OrchestrationClientError` and keep `GeminiClientError` as an alias for backward compat
- Rename `GeminiConnectivityProbe` → `ConnectivityProbe`
- Rename `GeminiObserverInsight` → `ObserverInsight`
- Update `create_orchestration_client` return type annotation

This is a rename-only change — no logic changes. Search-replace across the codebase.

### `services/method-development/app/c12_orchestration.py`

**Fix the step budget**: currently `_ExecutionBudgetTracker` tracks steps but doesn't integrate with `RecommendationRuntimeTracker`'s LLM call counter. Add a shared call counter parameter:

```python
def orchestrate_review_record_preparation(
    payload,
    gemini_client,
    *,
    shared_llm_call_counter: list[int] | None = None,  # mutable counter shared with caller
    ...
):
```

When `shared_llm_call_counter` is provided, increment it on each LLM call and abort if it exceeds the budget.

### `services/method-development/app/recommendations_router.py`

**Narrow the exception catch**: find the broad `except Exception` that returns `_fallback_runtime_error`. Replace with:
```python
except OpenAccessClientError as exc:
    return _fallback_runtime_error(app, payload, f"Paper fetch failed: {exc}")
except GeminiClientError as exc:  # (will be OrchestrationClientError after rename)
    return _fallback_runtime_error(app, payload, f"LLM call failed: {exc}")
# Let other exceptions propagate — they are bugs, not expected failures
```

This ensures extraction bugs appear as 500s in logs rather than silent degraded responses.

### `services/method-development/app/recommendation_engine.py`

**Log which step is happening**: the engine runs a multi-step pipeline but the logs only show the final result. Add a structured log at each pipeline phase:
```python
rprint(f"[blue]Phase: paper_fetch — {len(candidates)} candidates[/blue]")
rprint(f"[blue]Phase: extraction — batch {i+1}/{n_batches}[/blue]")
rprint(f"[blue]Phase: ranking — {len(extracted)} extracted records[/blue]")
```

This alone will make it much easier to diagnose where the pipeline is stalling.

## Conflicting rules inventory

These are the specific conflicts found in the codebase that should be resolved:

| Location | Conflict | Resolution |
|----------|----------|-----------|
| `ai_runtime_settings.py:65` | Default model `"openai/gpt-oss-20b"` doesn't exist on Groq | Use `"llama-3.3-70b-versatile"` |
| `ai_runtime_settings.py:46` | `enable_llm_orchestration: bool = False` but prod env has it True | Change default to True |
| `gemini_orchestration_client.py:52` | `_max_context_chars = 4500` for Groq; too small for method extraction | Increase to 8000 minimum, 32000 for DeepSeek |
| `recommendation_engine.py:92` | `_DEFAULT_EXTRACTION_CONCURRENCY = 1` — serial extraction on 5-paper batches | Increase to 3 |
| `c12_orchestration.py` | Step budget doesn't share state with recommendation engine | Add shared counter (see above) |
| `recommendations_router.py` | Broad `except Exception` swallows extraction bugs | Narrow to specific error types |

## Acceptance criteria

- `LLM_PROVIDER=groq` boots with a valid default model (no `"openai/gpt-oss-20b"` in logs)
- `enable_llm_orchestration` is on by default; turning it off via env var still works
- Extraction bugs appear as 500 errors in the router, not as silent degraded responses
- All type annotations reference `OrchestrationClient` not `GeminiOrchestrationClient` for the abstract interface
- `uv run pytest -q` passes with no new failures
