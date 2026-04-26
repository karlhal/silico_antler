from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from .recommendation_schemas import (
    RecommendationErrorDetail,
    MethodRecommendationReport,
    MethodRecommendationRequest,
    RecommendationJobStage,
    RecommendationJobState,
    RecommendationJobStatus,
    RecommendationRuntimeSummary,
)


class RecommendationJobStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, RecommendationJobStatus] = {}

    def create_job(self, request: MethodRecommendationRequest) -> RecommendationJobStatus:
        now = datetime.now(UTC)
        job = RecommendationJobStatus(
            job_id=f"recommendation-job-{uuid4().hex}",
            state="queued",
            stage="queued",
            message="Recommendation job queued.",
            created_at=now,
            updated_at=now,
            source_mode=request.source_mode,
            items_completed=0,
            items_total=None,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job.model_copy(deep=True)

    def get_job(self, job_id: str) -> RecommendationJobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job is not None else None

    def update_job(
        self,
        job_id: str,
        *,
        state: RecommendationJobState | None = None,
        stage: RecommendationJobStage | None = None,
        message: str | None = None,
        items_completed: int | None = None,
        items_total: int | None = None,
    ) -> RecommendationJobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            updated_job = job.model_copy(
                update={
                    "state": state or job.state,
                    "stage": stage or job.stage,
                    "message": (message or job.message)[:1000],
                    "items_completed": items_completed
                    if items_completed is not None
                    else job.items_completed,
                    "items_total": items_total if items_total is not None else job.items_total,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._jobs[job_id] = updated_job
            return updated_job.model_copy(deep=True)

    def complete_job(
        self, job_id: str, report: MethodRecommendationReport
    ) -> RecommendationJobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            completed_total = job.items_total
            if completed_total is None and report.source_mode == "open_access":
                completed_total = len(report.discovered_papers)
            if completed_total is None:
                completed_total = len(report.considered_candidates)

            updated_job = job.model_copy(
                update={
                    "state": "completed",
                    "stage": "completed",
                    "message": "Recommendation job completed.",
                    "items_completed": completed_total,
                    "items_total": completed_total,
                    "report": deepcopy(report),
                    "runtime": deepcopy(report.runtime),
                    "error_detail": None,
                    "error_message": None,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._jobs[job_id] = updated_job
            return updated_job.model_copy(deep=True)

    def fail_job(
        self,
        job_id: str,
        *,
        error_detail: RecommendationErrorDetail,
        runtime: RecommendationRuntimeSummary,
    ) -> RecommendationJobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            updated_job = job.model_copy(
                update={
                    "state": "failed",
                    "stage": "failed",
                    "message": "Recommendation job failed.",
                    "runtime": deepcopy(runtime),
                    "error_detail": deepcopy(error_detail),
                    "error_message": error_detail.message[:1000],
                    "updated_at": datetime.now(UTC),
                }
            )
            self._jobs[job_id] = updated_job
            return updated_job.model_copy(deep=True)
