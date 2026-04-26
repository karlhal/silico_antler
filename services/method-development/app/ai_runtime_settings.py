from __future__ import annotations

import os
from dataclasses import dataclass

_PROVIDER_DEFAULT_PLANNER = {
    "gemini": "gemini-2.5-pro",
    "groq": "llama-3.3-70b-versatile",
    "zai": "glm-4.6",
    "openrouter": "google/gemma-4-31b-it:free",
    "openai_compatible": "gpt-4o-mini",
}
_PROVIDER_DEFAULT_WORKER = {
    "gemini": "gemini-2.5-flash",
    "groq": "meta-llama/llama-4-scout-17b-16e-instruct",
    "zai": "glm-4-plus",
    "openrouter": "google/gemma-4-31b-it:free",
    "openai_compatible": "gpt-4o-mini",
}


def _parse_bool(raw_value: str | None, *, default: bool) -> bool:
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean environment value: {raw_value}")


def _parse_int(
    raw_value: str | None, *, default: int, min_value: int, max_value: int
) -> int:
    if raw_value is None:
        return default
    parsed = int(raw_value)
    if parsed < min_value or parsed > max_value:
        raise ValueError(
            f"Environment value {parsed} must be between {min_value} and {max_value}"
        )
    return parsed


def _parse_llm_provider(raw_value: str | None, *, default: str) -> str:
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"gemini", "groq", "zai", "openrouter", "openai_compatible"}:
        return normalized
    raise ValueError(f"Invalid LLM provider: {raw_value}")


def _parse_optional_string(raw_value: str | None, *, default: str | None = None) -> str | None:
    if raw_value is None:
        return default
    normalized = raw_value.strip()
    if not normalized:
        return default
    return normalized


@dataclass(frozen=True)
class AiRuntimeSettings:
    llm_provider: str = "gemini"
    google_api_key: str | None = None
    groq_api_key: str | None = None
    zai_api_key: str | None = None
    openrouter_api_key: str | None = None
    llm_base_url: str | None = None
    enable_llm_orchestration: bool = True
    provider_pool_enabled: bool = False
    planner_model: str = "gemini-2.5-pro"
    worker_model: str = "gemini-2.5-flash"
    open_access_timeout_sec: int = 20
    enable_runtime_debug_metadata: bool = False
    llm_timeout_sec: int = 20
    llm_max_calls_per_run: int = 6
    query_planner_parallelism: int = 1
    max_step_attempts_per_run: int = 1
    max_total_steps_per_run: int = 5


def load_ai_runtime_settings() -> AiRuntimeSettings:
    llm_provider = _parse_llm_provider(
        os.getenv("SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER"),
        default="gemini",
    )
    google_api_key = _parse_optional_string(
        os.getenv("SILICO_METHOD_DEVELOPMENT_GOOGLE_API_KEY")
    )
    groq_api_key = _parse_optional_string(
        os.getenv("SILICO_METHOD_DEVELOPMENT_GROQ_API_KEY")
    )
    zai_api_key = _parse_optional_string(
        os.getenv("SILICO_METHOD_DEVELOPMENT_ZAI_API_KEY")
    )
    openrouter_api_key = _parse_optional_string(
        os.getenv("SILICO_METHOD_DEVELOPMENT_OPENROUTER_API_KEY")
    )
    default_planner_model = _PROVIDER_DEFAULT_PLANNER.get(llm_provider, "gemini-2.5-pro")
    default_worker_model = _PROVIDER_DEFAULT_WORKER.get(llm_provider, "gemini-2.5-flash")
    return AiRuntimeSettings(
        llm_provider=llm_provider,
        google_api_key=google_api_key,
        groq_api_key=groq_api_key,
        zai_api_key=zai_api_key,
        openrouter_api_key=openrouter_api_key,
        llm_base_url=_parse_optional_string(
            os.getenv("SILICO_METHOD_DEVELOPMENT_LLM_BASE_URL")
        ),
        enable_llm_orchestration=_parse_bool(
            os.getenv("SILICO_METHOD_DEVELOPMENT_ENABLE_LLM_ORCHESTRATION"),
            default=True,
        ),
        provider_pool_enabled=_parse_bool(
            os.getenv("SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED"),
            default=False,
        ),
        planner_model=_parse_optional_string(
            os.getenv("SILICO_METHOD_DEVELOPMENT_PLANNER_MODEL"),
            default=default_planner_model,
        )
        or default_planner_model,
        worker_model=_parse_optional_string(
            os.getenv("SILICO_METHOD_DEVELOPMENT_WORKER_MODEL"),
            default=default_worker_model,
        )
        or default_worker_model,
        open_access_timeout_sec=_parse_int(
            os.getenv("SILICO_METHOD_DEVELOPMENT_OPEN_ACCESS_TIMEOUT_SEC"),
            default=20,
            min_value=5,
            max_value=120,
        ),
        enable_runtime_debug_metadata=_parse_bool(
            os.getenv("SILICO_METHOD_DEVELOPMENT_ENABLE_RUNTIME_DEBUG_METADATA"),
            default=False,
        ),
        llm_timeout_sec=_parse_int(
            os.getenv("SILICO_METHOD_DEVELOPMENT_LLM_TIMEOUT_SEC"),
            default=20,
            min_value=5,
            max_value=120,
        ),
        llm_max_calls_per_run=_parse_int(
            os.getenv("SILICO_METHOD_DEVELOPMENT_LLM_MAX_CALLS_PER_RUN"),
            default=6,
            min_value=1,
            max_value=20,
        ),
        query_planner_parallelism=_parse_int(
            os.getenv("SILICO_METHOD_DEVELOPMENT_QUERY_PLANNER_PARALLELISM"),
            default=1,
            min_value=1,
            max_value=5,
        ),
        max_step_attempts_per_run=_parse_int(
            os.getenv("SILICO_METHOD_DEVELOPMENT_MAX_STEP_ATTEMPTS_PER_RUN"),
            default=1,
            min_value=1,
            max_value=3,
        ),
        max_total_steps_per_run=_parse_int(
            os.getenv("SILICO_METHOD_DEVELOPMENT_MAX_TOTAL_STEPS_PER_RUN"),
            default=5,
            min_value=3,
            max_value=8,
        ),
    )
