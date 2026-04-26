from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai_runtime_settings import load_ai_runtime_settings


def test_load_ai_runtime_settings_uses_safe_defaults(monkeypatch) -> None:
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv(
        "SILICO_METHOD_DEVELOPMENT_ENABLE_LLM_ORCHESTRATION", raising=False
    )
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_WORKER_MODEL", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_LLM_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_LLM_MAX_CALLS_PER_RUN", raising=False)
    monkeypatch.delenv(
        "SILICO_METHOD_DEVELOPMENT_QUERY_PLANNER_PARALLELISM", raising=False
    )
    monkeypatch.delenv(
        "SILICO_METHOD_DEVELOPMENT_MAX_STEP_ATTEMPTS_PER_RUN", raising=False
    )
    monkeypatch.delenv(
        "SILICO_METHOD_DEVELOPMENT_MAX_TOTAL_STEPS_PER_RUN", raising=False
    )
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED", raising=False)

    settings = load_ai_runtime_settings()

    assert settings.llm_provider == "gemini"
    assert settings.google_api_key is None
    assert settings.groq_api_key is None
    assert settings.llm_base_url is None
    assert settings.enable_llm_orchestration is True
    assert settings.planner_model == "gemini-2.5-pro"
    assert settings.worker_model == "gemini-2.5-flash"
    assert settings.llm_timeout_sec == 20
    assert settings.llm_max_calls_per_run == 6
    assert settings.query_planner_parallelism == 1
    assert settings.max_step_attempts_per_run == 1
    assert settings.max_total_steps_per_run == 5
    assert settings.provider_pool_enabled is False


def test_load_ai_runtime_settings_reads_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_GOOGLE_API_KEY", "demo-key")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_ENABLE_LLM_ORCHESTRATION", "true")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_PLANNER_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_WORKER_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_LLM_TIMEOUT_SEC", "25")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_LLM_MAX_CALLS_PER_RUN", "5")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_QUERY_PLANNER_PARALLELISM", "3")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_MAX_STEP_ATTEMPTS_PER_RUN", "1")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_MAX_TOTAL_STEPS_PER_RUN", "3")

    settings = load_ai_runtime_settings()

    assert settings.llm_provider == "gemini"
    assert settings.google_api_key == "demo-key"
    assert settings.enable_llm_orchestration is True
    assert settings.llm_timeout_sec == 25
    assert settings.llm_max_calls_per_run == 5
    assert settings.query_planner_parallelism == 3
    assert settings.max_total_steps_per_run == 3


def test_load_ai_runtime_settings_uses_groq_defaults(monkeypatch) -> None:
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER", "groq")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_GROQ_API_KEY", "groq-demo-key")
    monkeypatch.setenv(
        "SILICO_METHOD_DEVELOPMENT_LLM_BASE_URL", "https://api.groq.com/openai/v1"
    )
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_WORKER_MODEL", raising=False)

    settings = load_ai_runtime_settings()

    assert settings.llm_provider == "groq"
    assert settings.groq_api_key == "groq-demo-key"
    assert settings.llm_base_url == "https://api.groq.com/openai/v1"
    assert settings.planner_model == "llama-3.3-70b-versatile"
    assert settings.worker_model == "meta-llama/llama-4-scout-17b-16e-instruct"


def test_load_ai_runtime_settings_uses_openrouter_gemma_defaults(monkeypatch) -> None:
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_OPENROUTER_API_KEY", "or-demo-key")
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_PLANNER_MODEL", raising=False)
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_WORKER_MODEL", raising=False)

    settings = load_ai_runtime_settings()

    assert settings.llm_provider == "openrouter"
    assert settings.openrouter_api_key == "or-demo-key"
    assert settings.planner_model == "google/gemma-4-31b-it:free"
    assert settings.worker_model == "google/gemma-4-31b-it:free"


def test_load_ai_runtime_settings_ignores_blank_model_overrides(monkeypatch) -> None:
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_OPENROUTER_API_KEY", "or-demo-key")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_PLANNER_MODEL", "   ")
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_WORKER_MODEL", "")

    settings = load_ai_runtime_settings()

    assert settings.planner_model == "google/gemma-4-31b-it:free"
    assert settings.worker_model == "google/gemma-4-31b-it:free"
