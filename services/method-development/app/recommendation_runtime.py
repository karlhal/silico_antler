from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import logging
from threading import Lock
import time
from uuid import uuid4

from .recommendation_schemas import (
    MethodRecommendationRequest,
    RecommendationCacheTelemetry,
    RecommendationErrorDetail,
    RecommendationFailureClassification,
    RecommendationJobStage,
    RecommendationRuntimeBudget,
    RecommendationRuntimeStatus,
    RecommendationRuntimeSummary,
    RecommendationRuntimeTelemetry,
    RecommendationQueryVariant,
    RecommendationSearchPlan,
    RecommendationStageTelemetry,
)

LOGGER = logging.getLogger(__name__)
_FAILURE_COUNTERS: Counter[str] = Counter()
_FAILURE_COUNTERS_LOCK = Lock()


def increment_failure_counter(
    classification: RecommendationFailureClassification,
) -> None:
    with _FAILURE_COUNTERS_LOCK:
        _FAILURE_COUNTERS[classification] += 1


def snapshot_failure_counters() -> dict[str, int]:
    with _FAILURE_COUNTERS_LOCK:
        return dict(sorted(_FAILURE_COUNTERS.items()))


def _log_event(event: str, **payload: object) -> None:
    LOGGER.info("%s %s", event, json.dumps(payload, sort_keys=True, default=str))


class RecommendationRuntimeError(RuntimeError):
    def __init__(
        self,
        *,
        error_detail: RecommendationErrorDetail,
        runtime: RecommendationRuntimeSummary,
    ) -> None:
        super().__init__(error_detail.message)
        self.error_detail = error_detail
        self.runtime = runtime


@dataclass
class _StageAccumulator:
    elapsed_ms: float = 0.0
    llm_calls: int = 0
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    evidence_unit_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    estimated_cost_usd: float = 0.0
    has_known_cost: bool = False


class RecommendationRuntimeTracker:
    def __init__(
        self,
        request: MethodRecommendationRequest,
        *,
        open_access_timeout_sec: int | None,
        llm_observer_enabled: bool,
        rate_limit_policy: str,
        enable_debug_metadata: bool,
    ) -> None:
        self._request = request
        self._open_access_timeout_sec = open_access_timeout_sec
        self._llm_observer_enabled = llm_observer_enabled
        self._rate_limit_policy = rate_limit_policy
        self._enable_debug_metadata = enable_debug_metadata
        self._lock = Lock()
        self.request_id = f"recommendation-{uuid4().hex[:16]}"
        self._started_at = time.perf_counter()
        self._stage_started_at = self._started_at
        self._branch_decisions: list[str] = []
        self._search_budget_used: int | None = None
        self._shortlist_size: int | None = None
        self._fetch_concurrency: int | None = None
        self._extraction_concurrency: int | None = None
        self._target_viable_candidates: int | None = None
        self._stop_condition: str | None = None
        self._search_plan: RecommendationSearchPlan | None = None
        self._queries_attempted = 0
        self._degraded = False
        self._last_stage: RecommendationJobStage | None = None
        self._stage_accumulators: dict[RecommendationJobStage, _StageAccumulator] = {}
        self._cache_counts = {
            "artifact_hits": 0,
            "artifact_misses": 0,
            "evidence_unit_hits": 0,
            "evidence_unit_misses": 0,
            "extraction_hits": 0,
            "extraction_misses": 0,
            "vetted_snippet_hits": 0,
            "vetted_snippet_misses": 0,
        }
        self._llm_prompt_tokens = 0
        self._llm_completion_tokens = 0
        self._evidence_unit_count = 0
        self._estimated_cost_usd = 0.0
        self._has_known_cost = False

    def log_start(self) -> None:
        _log_event(
            "recommendation_start",
            request_id=self.request_id,
            source_mode=self._request.source_mode,
            max_papers=self._request.max_papers,
            require_mass_spectrometry=self._request.require_mass_spectrometry,
        )

    def log_stage(
        self,
        stage: RecommendationJobStage,
        *,
        message: str | None = None,
        items_completed: int | None = None,
        items_total: int | None = None,
    ) -> None:
        self._transition_stage(stage)
        _log_event(
            "recommendation_stage",
            request_id=self.request_id,
            stage=stage,
            message=message,
            items_completed=items_completed,
            items_total=items_total,
        )

    def note_branch_decision(self, decision: str, *, degraded: bool = False) -> None:
        cleaned = " ".join(decision.split()).strip()
        if not cleaned:
            return
        with self._lock:
            if cleaned not in self._branch_decisions:
                self._branch_decisions.append(cleaned[:240])
            if degraded:
                self._degraded = True
        if degraded:
            _log_event(
                "recommendation_degraded_branch",
                request_id=self.request_id,
                decision=cleaned[:240],
            )

    def note_query_attempt(self, query: str) -> None:
        with self._lock:
            self._queries_attempted += 1
        if self._enable_debug_metadata:
            self.note_branch_decision(f"Executed literature query: {query[:180]}")

    def note_search_budget(self, budget: int) -> None:
        self._search_budget_used = budget

    def note_search_plan(
        self,
        plan: object,
        *,
        queries: list[RecommendationQueryVariant] | None = None,
    ) -> None:
        self._search_plan = RecommendationSearchPlan(
            request_specificity=str(getattr(plan, "request_specificity")),
            exploration_mode=str(getattr(plan, "exploration_mode")),
            query_count=int(getattr(plan, "query_count")),
            search_budget=int(getattr(plan, "search_budget")),
            rationale=str(getattr(plan, "rationale")),
            queries=[query.model_copy(deep=True) for query in (queries or [])],
        )

    def note_open_access_budget(
        self,
        *,
        shortlist_size: int,
        fetch_concurrency: int,
        extraction_concurrency: int,
        target_viable_candidates: int | None,
        stop_condition: str,
    ) -> None:
        self._shortlist_size = shortlist_size
        self._fetch_concurrency = fetch_concurrency
        self._extraction_concurrency = extraction_concurrency
        self._target_viable_candidates = target_viable_candidates
        self._stop_condition = stop_condition.strip()[:200] or None

    def note_evidence_units(
        self, stage: RecommendationJobStage, *, count: int, cache_hit: bool
    ) -> None:
        if count <= 0:
            return
        with self._lock:
            accumulator = self._ensure_stage_accumulator(stage)
            accumulator.evidence_unit_count += count
            self._evidence_unit_count += count
        self.note_cache_event(stage, cache_name="evidence_unit", hit=cache_hit)

    def note_cache_event(
        self,
        stage: RecommendationJobStage,
        *,
        cache_name: str,
        hit: bool,
    ) -> None:
        suffix = "hits" if hit else "misses"
        key = f"{cache_name}_{suffix}"
        with self._lock:
            if key in self._cache_counts:
                self._cache_counts[key] += 1
            accumulator = self._ensure_stage_accumulator(stage)
            if hit:
                accumulator.cache_hits += 1
            else:
                accumulator.cache_misses += 1

    def note_llm_usage(
        self,
        stage: RecommendationJobStage,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float | None,
    ) -> None:
        with self._lock:
            accumulator = self._ensure_stage_accumulator(stage)
            accumulator.llm_calls += 1
            accumulator.llm_prompt_tokens += max(prompt_tokens, 0)
            accumulator.llm_completion_tokens += max(completion_tokens, 0)
            self._llm_prompt_tokens += max(prompt_tokens, 0)
            self._llm_completion_tokens += max(completion_tokens, 0)
            if estimated_cost_usd is not None:
                accumulator.estimated_cost_usd += estimated_cost_usd
                accumulator.has_known_cost = True
                self._estimated_cost_usd += estimated_cost_usd
                self._has_known_cost = True

    def budget(self) -> RecommendationRuntimeBudget:
        return RecommendationRuntimeBudget(
            max_papers_requested=self._request.max_papers,
            search_budget_used=self._search_budget_used,
            queries_attempted=self._queries_attempted,
            shortlist_size=self._shortlist_size,
            fetch_concurrency=self._fetch_concurrency,
            extraction_concurrency=self._extraction_concurrency,
            target_viable_candidates=self._target_viable_candidates,
            stop_condition=self._stop_condition,
            open_access_timeout_sec=(
                self._open_access_timeout_sec
                if self._request.source_mode == "open_access"
                else None
            ),
            llm_observer_enabled=self._llm_observer_enabled,
            rate_limit_policy=self._rate_limit_policy,
            search_plan=self._search_plan,
        )

    def telemetry(self) -> RecommendationRuntimeTelemetry:
        self._finalize_current_stage()
        return RecommendationRuntimeTelemetry(
            llm_prompt_tokens=self._llm_prompt_tokens,
            llm_completion_tokens=self._llm_completion_tokens,
            evidence_unit_count=self._evidence_unit_count,
            estimated_cost_usd=(
                round(self._estimated_cost_usd, 6) if self._has_known_cost else None
            ),
            cache=RecommendationCacheTelemetry(**self._cache_counts),
            stages=[
                RecommendationStageTelemetry(
                    stage=stage,
                    elapsed_ms=round(accumulator.elapsed_ms, 1),
                    llm_calls=accumulator.llm_calls,
                    llm_prompt_tokens=accumulator.llm_prompt_tokens,
                    llm_completion_tokens=accumulator.llm_completion_tokens,
                    evidence_unit_count=accumulator.evidence_unit_count,
                    cache_hits=accumulator.cache_hits,
                    cache_misses=accumulator.cache_misses,
                    estimated_cost_usd=(
                        round(accumulator.estimated_cost_usd, 6)
                        if accumulator.has_known_cost
                        else None
                    ),
                )
                for stage, accumulator in self._stage_accumulators.items()
            ],
        )

    def success_runtime(
        self,
        *,
        discovered_count: int,
        candidate_count: int,
        recommended_candidate_id: str | None,
    ) -> RecommendationRuntimeSummary:
        if candidate_count == 0:
            status: RecommendationRuntimeStatus = "no_trustworthy_candidates"
            if discovered_count == 0:
                summary = "Run completed, but no relevant literature sources were found or matched the query."
            else:
                summary = (
                    f"Run completed. Found {discovered_count} potential source(s), but "
                    "no trustworthy recommendation candidates remained after screening, "
                    "extraction, and safety checks."
                )
        elif self._degraded:
            status = "completed_with_degraded_source"
            summary = (
                f"Built {candidate_count} recommendation candidate(s) with degraded "
                "source handling."
            )
        else:
            status = "completed"
            summary = (
                f"Built {candidate_count} recommendation candidate(s) and selected "
                f"{recommended_candidate_id or 'the highest-ranked result'}."
            )

        runtime = RecommendationRuntimeSummary(
            request_id=self.request_id,
            status=status,
            summary=summary,
            degraded=self._degraded,
            failure_classification=None,
            budget=self.budget(),
            branch_decisions=self._branch_decisions_for_response(),
            telemetry=self.telemetry(),
        )
        self._log_completion(runtime, candidate_count, recommended_candidate_id)
        return runtime

    def failure_runtime(
        self,
        *,
        runtime_status: RecommendationRuntimeStatus,
        failure_classification: RecommendationFailureClassification,
        message: str,
    ) -> RecommendationRuntimeSummary:
        runtime = RecommendationRuntimeSummary(
            request_id=self.request_id,
            status=runtime_status,
            summary=message[:1000],
            degraded=self._degraded,
            failure_classification=failure_classification,
            budget=self.budget(),
            branch_decisions=self._branch_decisions_for_response(),
            telemetry=self.telemetry(),
        )
        self._log_completion(runtime, 0, None)
        return runtime

    def fail(
        self,
        *,
        runtime_status: RecommendationRuntimeStatus,
        failure_classification: RecommendationFailureClassification,
        message: str,
        retryable: bool,
        failure_stage: RecommendationJobStage | None = None,
    ) -> RecommendationRuntimeError:
        increment_failure_counter(failure_classification)
        stage = failure_stage or self._last_stage
        runtime = self.failure_runtime(
            runtime_status=runtime_status,
            failure_classification=failure_classification,
            message=message,
        )
        error_detail = RecommendationErrorDetail(
            request_id=self.request_id,
            runtime_status=runtime_status,
            failure_classification=failure_classification,
            failure_stage=stage,
            message=message[:1000],
            retryable=retryable,
        )
        _log_event(
            "recommendation_failure",
            request_id=self.request_id,
            runtime_status=runtime_status,
            failure_classification=failure_classification,
            failure_stage=stage,
            retryable=retryable,
            message=message[:240],
        )
        return RecommendationRuntimeError(error_detail=error_detail, runtime=runtime)

    def _branch_decisions_for_response(self) -> list[str]:
        if self._enable_debug_metadata:
            return self._branch_decisions[:10]
        important = [
            decision
            for decision in self._branch_decisions
            if "query:" not in decision.lower()
        ]
        return important[:6]

    def _ensure_stage_accumulator(
        self, stage: RecommendationJobStage
    ) -> _StageAccumulator:
        accumulator = self._stage_accumulators.get(stage)
        if accumulator is None:
            accumulator = _StageAccumulator()
            self._stage_accumulators[stage] = accumulator
        return accumulator

    def _transition_stage(self, stage: RecommendationJobStage) -> None:
        if self._last_stage == stage:
            return
        self._finalize_current_stage()
        self._last_stage = stage
        self._stage_started_at = time.perf_counter()
        self._ensure_stage_accumulator(stage)

    def _finalize_current_stage(self) -> None:
        if self._last_stage is None:
            return
        elapsed_ms = (time.perf_counter() - self._stage_started_at) * 1000
        accumulator = self._ensure_stage_accumulator(self._last_stage)
        accumulator.elapsed_ms += elapsed_ms
        self._stage_started_at = time.perf_counter()

    def _log_completion(
        self,
        runtime: RecommendationRuntimeSummary,
        candidate_count: int,
        recommended_candidate_id: str | None,
    ) -> None:
        elapsed_ms = round((time.perf_counter() - self._started_at) * 1000, 1)
        _log_event(
            "recommendation_complete",
            request_id=self.request_id,
            source_mode=self._request.source_mode,
            runtime_status=runtime.status,
            degraded=runtime.degraded,
            candidate_count=candidate_count,
            recommended_candidate_id=recommended_candidate_id,
            failure_classification=runtime.failure_classification,
            elapsed_ms=elapsed_ms,
        )
