# Slice 1 — OpenAI-Compatible Provider Abstraction (Z.AI + OpenRouter)

## Goal

Replace the fragile Gemini/Groq split with a single `OpenAICompatibleClient` that works with Z.AI (ZhipuAI), OpenRouter, Groq, Ollama, and any other OpenAI-chat-compatible endpoint. Keep `GeminiOrchestrationClient` for Gemini-native calls (different wire format).

The immediate target providers are **Z.AI** (generous free tier, high concurrency) and **OpenRouter** (aggregates 200+ models, free tier on many).

## Provider comparison

| Provider | Model | Concurrency / pricing | Context | Best for |
|----------|-------|----------------------|---------|----------|
| Groq | llama-3.3-70b | Rate-limited free tier | 32k | Current — replace |
| Gemini | 2.5-flash | Free quota hits fast | 1M | Keep as pool fallback |
| **Z.AI** | **GLM-4-Plus** | **20 concurrent — free** | 128k | **Worker (high throughput)** |
| **Z.AI** | **GLM-4.5** | **10 concurrent — free** | 128k | **Worker alternative** |
| **Z.AI** | GLM-4.6 | 3 concurrent — free | 128k | Planner tasks |
| **OpenRouter** | gemini-2.5-flash:free | Varies, many free models | 1M | Flexible fallback |
| **OpenRouter** | google/gemini-2.5-pro | Pay-per-token | 1M | High-quality planner |

**Default recommendation**: Z.AI `GLM-4-Plus` as worker (20 concurrent, free), Z.AI `GLM-4.6` as planner. Add OpenRouter as a pool member for extra capacity and model flexibility.

## Z.AI API details

- **Base URL**: `https://api.z.ai/api/paas/v4`
- **Auth**: `Authorization: Bearer <api_key>` (standard Bearer)
- **Endpoint**: `POST /chat/completions`
- **OpenAI-compatible**: yes — same request/response shape as OpenAI
- **JSON mode**: `response_format: {"type": "json_object"}` supported
- **Context window**: 128k for GLM-4-Plus, GLM-4.5, GLM-4.6
- **Concurrency note**: GLM-4-Plus allows 20 parallel requests — ideal for batch extraction

## Files to change

### `services/method-development/app/ai_runtime_settings.py`

1. Add new API key fields:
   ```python
   zai_api_key: str | None = None           # Z.AI / ZhipuAI
   openrouter_api_key: str | None = None    # OpenRouter
   ```
2. Extend `_parse_llm_provider` to accept `"zai"`, `"openrouter"`, and `"openai_compatible"`:
   ```python
   if normalized in {"gemini", "groq", "zai", "openrouter", "openai_compatible"}:
       return normalized
   ```
3. Fix the bad default model logic (current `"openai/gpt-oss-20b"` doesn't exist on Groq):
   ```python
   _PROVIDER_DEFAULT_PLANNER = {
       "gemini": "gemini-2.5-pro",
       "groq": "llama-3.3-70b-versatile",
       "zai": "glm-4.6",
       "openrouter": "google/gemini-2.5-pro",
       "openai_compatible": "gpt-4o-mini",  # user must override via env
   }
   _PROVIDER_DEFAULT_WORKER = {
       "gemini": "gemini-2.5-flash",
       "groq": "meta-llama/llama-4-scout-17b-16e-instruct",
       "zai": "glm-4-plus",
       "openrouter": "google/gemini-2.5-flash-preview:free",
       "openai_compatible": "gpt-4o-mini",
   }
   ```
4. New env vars:
   - `SILICO_METHOD_DEVELOPMENT_ZAI_API_KEY`
   - `SILICO_METHOD_DEVELOPMENT_OPENROUTER_API_KEY`
   - `SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER=zai` (or `openrouter`)
   - `SILICO_METHOD_DEVELOPMENT_LLM_BASE_URL` — kept for fully custom endpoints

### `services/method-development/app/gemini_orchestration_client.py`

#### 1. Extract `OpenAICompatibleClient`

Pull the shared logic out of `GroqOrchestrationClient` into a new base:

```python
class OpenAICompatibleClient(_BaseOrchestrationClient):
    """Generic OpenAI-chat-compatible client. Subclass and set _DEFAULT_BASE_URL + api_key."""

    _DEFAULT_BASE_URL: str  # subclasses must set
    _DEFAULT_MAX_CONTEXT_CHARS: int = 8000
    _DEFAULT_MAX_VETTING_CHARS: int = 6000

    def __init__(self, settings: AiRuntimeSettings, *, api_key: str, base_url: str | None = None) -> None:
        super().__init__(settings)
        self._api_key = api_key
        self._base_url = (base_url or self._DEFAULT_BASE_URL).rstrip("/")
        self._max_context_chars = self._DEFAULT_MAX_CONTEXT_CHARS
        self._max_vetting_chars = self._DEFAULT_MAX_VETTING_CHARS

    def _generate_content(self, *, model, prompt, max_output_tokens, response_mime_type, system_prompt=None) -> dict:
        # identical to current GroqOrchestrationClient._generate_content
        # uses self._api_key and self._base_url
        ...

    def _extract_response_text(self, response_json: dict) -> str:
        # identical to current GroqOrchestrationClient._extract_response_text
        ...
```

#### 2. Slim down `GroqOrchestrationClient`

```python
class GroqOrchestrationClient(OpenAICompatibleClient):
    _DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    _DEFAULT_MAX_CONTEXT_CHARS = 4500  # Groq models have smaller practical context
    _DEFAULT_MAX_VETTING_CHARS = 3500

    def __init__(self, settings: AiRuntimeSettings) -> None:
        if not settings.groq_api_key:
            raise OrchestrationClientError("Groq API key required")
        super().__init__(settings, api_key=settings.groq_api_key)
```

#### 3. Add `ZaiOrchestrationClient`

```python
class ZaiOrchestrationClient(OpenAICompatibleClient):
    _DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
    _DEFAULT_MAX_CONTEXT_CHARS = 32000  # 128k context, use a practical chunk size
    _DEFAULT_MAX_VETTING_CHARS = 16000

    def __init__(self, settings: AiRuntimeSettings) -> None:
        if not settings.zai_api_key:
            raise OrchestrationClientError("Z.AI API key required")
        super().__init__(settings, api_key=settings.zai_api_key)
```

#### 4. Add `OpenRouterOrchestrationClient`

```python
class OpenRouterOrchestrationClient(OpenAICompatibleClient):
    _DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    _DEFAULT_MAX_CONTEXT_CHARS = 32000
    _DEFAULT_MAX_VETTING_CHARS = 16000

    def __init__(self, settings: AiRuntimeSettings) -> None:
        if not settings.openrouter_api_key:
            raise OrchestrationClientError("OpenRouter API key required")
        super().__init__(settings, api_key=settings.openrouter_api_key)

    def _generate_content(self, *, model, prompt, max_output_tokens, response_mime_type, system_prompt=None) -> dict:
        # OpenRouter recommends passing HTTP-Referer and X-Title for attribution/routing.
        # These are injected as extra headers in the httpx call.
        # Override _generate_content to add them to the request headers.
        # Otherwise identical to OpenAICompatibleClient._generate_content.
        ...
```

Extra headers to add inside `_generate_content` before the httpx POST:
```python
"HTTP-Referer": "https://silico.bio",
"X-Title": "Silico HPLC Method Discovery",
```

OpenRouter uses these to attribute usage and can affect model routing on free tiers.

#### 5. Rename error/probe types

- `GeminiClientError` → `OrchestrationClientError` (keep `GeminiClientError` as alias)
- `GeminiConnectivityProbe` → `ConnectivityProbe`
- `GeminiObserverInsight` → `ObserverInsight`

#### 6. Update factory

```python
def create_orchestration_client(settings: AiRuntimeSettings) -> _BaseOrchestrationClient:
    match settings.llm_provider:
        case "gemini":
            return GeminiOrchestrationClient(settings)
        case "groq":
            return GroqOrchestrationClient(settings)
        case "zai":
            return ZaiOrchestrationClient(settings)
        case "openrouter":
            return OpenRouterOrchestrationClient(settings)
        case "openai_compatible":
            if not settings.llm_base_url:
                raise OrchestrationClientError(
                    "openai_compatible provider requires LLM_BASE_URL"
                )
            # Reuse whichever key is set as the generic bearer token
            api_key = settings.zai_api_key or settings.groq_api_key or settings.openrouter_api_key or ""
            return OpenAICompatibleClient(settings, api_key=api_key, base_url=settings.llm_base_url)
        case _:
            raise OrchestrationClientError(f"Unsupported LLM provider: {settings.llm_provider}")
```

### `services/method-development/app/main.py`

Add startup log:
```python
rprint(f"[green]LLM provider: {settings.llm_provider} | planner={settings.planner_model} | worker={settings.worker_model}[/green]")
```

## Concurrency strategy for Z.AI

With GLM-4-Plus at 20 concurrent requests, we can safely increase extraction parallelism:

- Set `SILICO_METHOD_DEVELOPMENT_EXTRACTION_CONCURRENCY=8` when using Z.AI (vs the current serial=1)
- The batch extraction loop in `recommendation_engine.py` should read this env var
- GLM-4.6 at 3 concurrent is fine for the planner (1 plan per recommendation run)

## Validation

```bash
# Z.AI smoke test
SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER=zai \
SILICO_METHOD_DEVELOPMENT_ZAI_API_KEY=<key> \
uv run python -c "
from app.ai_runtime_settings import load_ai_runtime_settings
from app.gemini_orchestration_client import create_orchestration_client
s = load_ai_runtime_settings()
c = create_orchestration_client(s)
print(c.probe_connection())
print('worker model:', s.worker_model)
"
```

Expected output: `ConnectivityProbe(ok=True, model='glm-4-plus', ...)`

## Acceptance criteria

- `LLM_PROVIDER=zai` boots and `probe_connection()` returns ok
- `LLM_PROVIDER=deepseek` boots and `probe_connection()` returns ok
- Existing `groq` and `gemini` paths pass (no regression)
- No hardcoded `"groq_api_key"` references inside `OpenAICompatibleClient`
- `GeminiClientError` still importable (alias preserved for backward compat)
- Startup log prints active provider + models

## Notes

- Z.AI `glm-4-plus` supports `response_format: {"type": "json_object"}` — confirmed OpenAI-compatible
- Context limit for Z.AI calls: set `_max_context_chars = 32000` (practical limit; full 128k not needed)
- DeepSeek `deepseek-reasoner` (R1): no `response_format` support — handle in `DeepSeekOrchestrationClient._generate_content`
- Do NOT add LangChain — the `httpx` client is 50 lines per provider and does exactly what's needed
