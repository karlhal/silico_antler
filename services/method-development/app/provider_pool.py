from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from .gemini_orchestration_client import (
    ROLE_PLANNER,
    _BaseOrchestrationClient,
    ConnectivityProbe,
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
        # _settings is intentionally not set — the pool overrides run_prompt entirely
        # and uses role sentinels (ROLE_WORKER / ROLE_PLANNER) rather than settings models.
        self._slots = slots
        self._lock = threading.Lock()
        # Set shared attributes so inherited high-level methods can truncate context safely.
        # Uses the minimum across all slot clients to guarantee no slot is overloaded.
        self._max_context_chars = min(
            (getattr(s.client, "_max_context_chars", 12000) for s in slots),
            default=12000,
        )
        self._max_vetting_chars = min(
            (getattr(s.client, "_max_vetting_chars", 12000) for s in slots),
            default=12000,
        )

    def run_prompt(
        self,
        *,
        prompt: str,
        max_output_tokens: int,
        response_mime_type: str,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> tuple[str, dict, str]:
        role = "planner" if model == ROLE_PLANNER else "worker"
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

    def probe_connection(self) -> ConnectivityProbe:
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

    def _generate_content(self, **kwargs) -> dict:
        raise NotImplementedError("ProviderPool does not implement _generate_content directly")

    def _extract_response_text(self, response_json: dict) -> str:
        raise NotImplementedError
