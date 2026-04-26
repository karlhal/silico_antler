from __future__ import annotations

from pathlib import Path
import sys
import threading
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from app.gemini_orchestration_client import (
    ROLE_PLANNER,
    ROLE_WORKER,
    OrchestrationClientError,
    _BaseOrchestrationClient,
)
from app.provider_pool import ProviderPool, ProviderSlot
from app.ai_runtime_settings import load_ai_runtime_settings


# ── Stub client ───────────────────────────────────────────────────────────────

class _StubClient(_BaseOrchestrationClient):
    """Minimal stub that records calls and can raise on demand."""

    def __init__(self, *, name: str = "stub", raises: Exception | None = None):
        # Bypass AiRuntimeSettings — stub doesn't need settings
        object.__setattr__(self, "_settings", None)
        object.__setattr__(self, "_max_context_chars", 12000)
        object.__setattr__(self, "_max_vetting_chars", 12000)
        self.name = name
        self.raises = raises
        self.calls: list[dict] = []

    def run_prompt(self, *, prompt, max_output_tokens, response_mime_type, model=None, system_prompt=None):
        self.calls.append({"model": model})
        if self.raises:
            raise self.raises
        return "ok", {}, model or "stub-model"

    def probe_connection(self):
        from app.gemini_orchestration_client import ConnectivityProbe
        if self.raises:
            raise self.raises
        return ConnectivityProbe(ok=True, model="stub-model", response_text="ok")

    def _generate_content(self, **kwargs) -> dict:
        raise NotImplementedError

    def _extract_response_text(self, response_json: dict) -> str:
        raise NotImplementedError


def _make_slot(*, name="stub", raises=None, max_concurrency=5):
    return ProviderSlot(
        client=_StubClient(name=name, raises=raises),
        planner_model=f"{name}-planner",
        worker_model=f"{name}-worker",
        max_concurrency=max_concurrency,
    )


# ── ProviderSlot unit tests ───────────────────────────────────────────────────

def test_slot_load_fraction_zero_when_idle():
    slot = _make_slot(max_concurrency=10)
    assert slot.load_fraction() == 0.0


def test_slot_has_capacity_until_full():
    slot = _make_slot(max_concurrency=2)
    assert slot.has_capacity()
    slot.acquire()
    assert slot.has_capacity()
    slot.acquire()
    assert not slot.has_capacity()


def test_slot_release_clamps_to_zero():
    slot = _make_slot()
    slot.release()  # should not go negative
    assert slot._in_flight == 0


def test_slot_backoff_starts_false():
    slot = _make_slot()
    assert not slot.in_backoff()


def test_slot_backoff_set_and_expires():
    slot = _make_slot()
    slot.set_backoff(0.05)
    assert slot.in_backoff()
    time.sleep(0.06)
    assert not slot.in_backoff()


# ── ProviderPool routing tests ────────────────────────────────────────────────

def test_pool_routes_to_least_loaded_slot():
    slot_a = _make_slot(name="a", max_concurrency=10)
    slot_b = _make_slot(name="b", max_concurrency=10)
    slot_a._in_flight = 8  # heavily loaded
    pool = ProviderPool([slot_a, slot_b])

    pool.run_prompt(prompt="hi", max_output_tokens=10, response_mime_type="text/plain", model=ROLE_WORKER)

    assert slot_b.client.calls, "Expected slot_b (less loaded) to be used"
    assert not slot_a.client.calls, "Expected slot_a (more loaded) to be skipped"


def test_pool_uses_planner_model_for_role_planner():
    slot = _make_slot(name="p")
    pool = ProviderPool([slot])

    text, _, model = pool.run_prompt(
        prompt="plan", max_output_tokens=10, response_mime_type="text/plain", model=ROLE_PLANNER
    )
    assert model == "p-planner"


def test_pool_uses_worker_model_for_role_worker():
    slot = _make_slot(name="w")
    pool = ProviderPool([slot])

    _, _, model = pool.run_prompt(
        prompt="work", max_output_tokens=10, response_mime_type="text/plain", model=ROLE_WORKER
    )
    assert model == "w-worker"


def test_pool_fails_over_on_error():
    bad = _make_slot(name="bad", raises=OrchestrationClientError("boom"))
    good = _make_slot(name="good")
    pool = ProviderPool([bad, good])

    text, _, _ = pool.run_prompt(
        prompt="hi", max_output_tokens=10, response_mime_type="text/plain", model=ROLE_WORKER
    )
    assert text == "ok"
    assert good.client.calls


def test_pool_sets_backoff_on_429():
    error_429 = OrchestrationClientError("HTTP 429 rate limit exceeded")
    bad = _make_slot(name="bad", raises=error_429)
    good = _make_slot(name="good")
    pool = ProviderPool([bad, good])

    pool.run_prompt(prompt="hi", max_output_tokens=10, response_mime_type="text/plain", model=ROLE_WORKER)

    assert bad.in_backoff(), "Slot should be in backoff after 429"


def test_pool_raises_when_all_providers_fail():
    bad1 = _make_slot(name="b1", raises=OrchestrationClientError("err1"))
    bad2 = _make_slot(name="b2", raises=OrchestrationClientError("err2"))
    pool = ProviderPool([bad1, bad2])

    with pytest.raises(OrchestrationClientError, match="All providers failed"):
        pool.run_prompt(
            prompt="hi", max_output_tokens=10, response_mime_type="text/plain", model=ROLE_WORKER
        )


def test_pool_probe_connection_returns_first_success():
    bad = _make_slot(name="bad", raises=OrchestrationClientError("unreachable"))
    good = _make_slot(name="good")
    pool = ProviderPool([bad, good])

    probe = pool.probe_connection()
    assert probe.ok


def test_pool_probe_connection_raises_when_all_down():
    bad1 = _make_slot(name="b1", raises=OrchestrationClientError("down"))
    bad2 = _make_slot(name="b2", raises=OrchestrationClientError("down"))
    pool = ProviderPool([bad1, bad2])

    with pytest.raises(OrchestrationClientError, match="All providers unreachable"):
        pool.probe_connection()


def test_pool_picks_over_capacity_slot_when_all_full():
    slot_a = _make_slot(name="a", max_concurrency=1)
    slot_b = _make_slot(name="b", max_concurrency=1)
    slot_a._in_flight = 1  # at capacity
    slot_b._in_flight = 1  # at capacity
    pool = ProviderPool([slot_a, slot_b])

    # Should still route (no backoff) — just pick least loaded
    pool.run_prompt(prompt="hi", max_output_tokens=10, response_mime_type="text/plain", model=ROLE_WORKER)
    # Either slot was used — just check no exception
    total_calls = len(slot_a.client.calls) + len(slot_b.client.calls)
    assert total_calls == 1


def test_pool_thread_safety():
    slot = _make_slot(name="shared", max_concurrency=50)
    pool = ProviderPool([slot])
    errors: list[Exception] = []

    def call():
        try:
            pool.run_prompt(
                prompt="x", max_output_tokens=5, response_mime_type="text/plain", model=ROLE_WORKER
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(slot.client.calls) == 20


# ── ai_runtime_settings: provider_pool_enabled ────────────────────────────────

def test_provider_pool_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED", raising=False)
    settings = load_ai_runtime_settings()
    assert settings.provider_pool_enabled is False


def test_provider_pool_enabled_via_env(monkeypatch):
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED", "true")
    settings = load_ai_runtime_settings()
    assert settings.provider_pool_enabled is True


def test_provider_pool_disabled_via_env(monkeypatch):
    monkeypatch.setenv("SILICO_METHOD_DEVELOPMENT_PROVIDER_POOL_ENABLED", "false")
    settings = load_ai_runtime_settings()
    assert settings.provider_pool_enabled is False
