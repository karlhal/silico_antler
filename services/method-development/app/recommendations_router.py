import logging
import traceback

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi import FastAPI
from pydantic import BaseModel

_LOGGER = logging.getLogger(__name__)

from .gemini_orchestration_client import OrchestrationClientError
from .hplc_extraction_schemas import MinimalHplcExtractionResponse
from .limiters import limiter
from .open_access_client import OpenAccessClientError
from .recommendation_runtime import RecommendationRuntimeError, RecommendationRuntimeTracker

from .recommendation_schemas import (
    MethodRecommendationRequest,
    MethodRecommendationReport,
    RecommendationCandidate,
    RecommendationJobAccepted,
    RecommendationJobStatus,
    RecommendationResponseDetail,
    RecommendationDiscoverySummary,
    RecommendationPayloadTelemetry,
)
from .recommendation_engine import recommend_methods

router = APIRouter(prefix="/recommendation", tags=["Recommendation"])
RECOMMENDATION_RATE_LIMIT_POLICY = "5/hour"


class ClarifyRequestPayload(BaseModel):
    request_text: str
    analyte_name: str | None = None
    max_run_time_min: float | None = None
    matrix_hint: str | None = None
    detector_types: list[str] = []
    require_mass_spectrometry: bool = False


class ClarifyQuestion(BaseModel):
    id: str
    question: str
    placeholder: str


class ClarifyResponse(BaseModel):
    questions: list[ClarifyQuestion]


def _build_recommendation_kwargs(app: FastAPI) -> dict[str, object]:
    settings = app.state.ai_runtime_settings
    return {
        "retrieval_store": app.state.retrieval_store,
        "open_access_client": app.state.open_access_client,
        "compound_context_client": getattr(app.state, "compound_context_client", None),
        "gemini_client": getattr(app.state, "gemini_client", None),
        "open_access_timeout_sec": settings.open_access_timeout_sec,
        "enable_runtime_debug_metadata": settings.enable_runtime_debug_metadata,
        "query_planner_parallelism": settings.query_planner_parallelism,
        "rate_limit_policy": RECOMMENDATION_RATE_LIMIT_POLICY,
    }


def _runtime_error_status_code(exc: RecommendationRuntimeError) -> int:
    if exc.error_detail.failure_classification == "request_invalid":
        return 422
    if exc.error_detail.failure_classification == "timeout":
        return 504
    return 503


def _fallback_runtime_error(
    app: FastAPI,
    payload: MethodRecommendationRequest,
    *,
    message: str,
) -> RecommendationRuntimeError:
    tracker = RecommendationRuntimeTracker(
        payload,
        open_access_timeout_sec=app.state.ai_runtime_settings.open_access_timeout_sec,
        llm_observer_enabled=getattr(app.state, "gemini_client", None) is not None,
        rate_limit_policy=RECOMMENDATION_RATE_LIMIT_POLICY,
        enable_debug_metadata=app.state.ai_runtime_settings.enable_runtime_debug_metadata,
    )
    return tracker.fail(
        runtime_status="upstream_unavailable",
        failure_classification="retrieval_store_unavailable",
        message=message,
        retryable=True,
        failure_stage="failed",
    )


def _run_recommendation_job(
    job_id: str,
    payload: MethodRecommendationRequest,
    app: FastAPI,
) -> None:
    job_store = app.state.recommendation_job_store

    try:
        report = recommend_methods(
            request=payload,
            **_build_recommendation_kwargs(app),
            progress_callback=lambda stage, message, items_completed, items_total: job_store.update_job(
                job_id,
                state="running",
                stage=stage,
                message=message,
                items_completed=items_completed,
                items_total=items_total,
            ),
        )
    except RecommendationRuntimeError as exc:
        job_store.fail_job(
            job_id,
            error_detail=exc.error_detail,
            runtime=exc.runtime,
        )
        return
    except OpenAccessClientError as exc:
        _LOGGER.error("Recommendation job %s: paper fetch failed: %s", job_id, exc)
        runtime_error = _fallback_runtime_error(app, payload, message=f"Paper fetch failed: {exc}")
        job_store.fail_job(job_id, error_detail=runtime_error.error_detail, runtime=runtime_error.runtime)
        return
    except OrchestrationClientError as exc:
        _LOGGER.error("Recommendation job %s: LLM call failed: %s", job_id, exc)
        runtime_error = _fallback_runtime_error(app, payload, message=f"LLM call failed: {exc}")
        job_store.fail_job(job_id, error_detail=runtime_error.error_detail, runtime=runtime_error.runtime)
        return
    # Other exceptions are bugs — log and re-raise so they appear as errors in logs
    except Exception:
        _LOGGER.error("Recommendation job %s failed with unhandled exception:\n%s", job_id, traceback.format_exc())
        raise

    try:
        job_store.complete_job(job_id, report)
    except Exception:
        _LOGGER.error("Failed to store completed recommendation job %s:\n%s", job_id, traceback.format_exc())
        raise


def _build_discovery_summary(
    report: MethodRecommendationReport,
) -> RecommendationDiscoverySummary:
    return RecommendationDiscoverySummary(
        discovered_paper_count=len(report.discovered_papers),
        skipped_paper_count=len(report.skipped_papers),
        skipped_papers_truncated=len(report.skipped_papers) > 5,
        skipped_papers_preview=report.skipped_papers[:5],
        considered_candidate_count=len(report.considered_candidates),
        considered_candidates_truncated=len(report.considered_candidates) > 3,
        repeated_extraction_exception_count=_repeated_extraction_exception_count(report),
    )


def _repeated_extraction_exception_count(
    report: MethodRecommendationReport,
) -> int:
    counts: dict[str, int] = {}
    for skipped_paper in report.skipped_papers:
        if skipped_paper.stage != "extraction":
            continue
        normalized_reason = _normalized_extraction_exception_reason(
            skipped_paper.reason
        )
        if normalized_reason is None:
            continue
        counts[normalized_reason] = counts.get(normalized_reason, 0) + 1
    return max(counts.values(), default=0)


def _normalized_extraction_exception_reason(reason: str) -> str | None:
    normalized = reason.strip()
    if normalized.startswith("HTML: "):
        normalized = normalized[6:]
    elif normalized.startswith("PDF: "):
        normalized = normalized[5:]
    if "Extraction failure:" not in normalized:
        return None
    return normalized


def _compact_extraction_for_agent(
    extraction: MinimalHplcExtractionResponse,
) -> MinimalHplcExtractionResponse:
    compact_provenance = extraction.provenance.model_copy(
        update={"evidence_snippets": extraction.provenance.evidence_snippets[:3]}
    )
    return MinimalHplcExtractionResponse(
        source_document=extraction.source_document,
        chromatography_system=extraction.chromatography_system,
        method_parameters=extraction.method_parameters,
        provenance=compact_provenance,
        warnings=extraction.warnings[:6],
        retrieval_record_ready=extraction.retrieval_record_ready,
    )


def _compact_candidate_for_agent(
    candidate: RecommendationCandidate,
) -> RecommendationCandidate:
    return candidate.model_copy(
        update={
            "extraction": _compact_extraction_for_agent(candidate.extraction),
            "evidence_snippets": candidate.evidence_snippets[:3],
        }
    )


def _attach_payload_telemetry(
    report: MethodRecommendationReport,
    detail: RecommendationResponseDetail,
) -> MethodRecommendationReport:
    if report.runtime is None or report.runtime.telemetry is None:
        return report
    evidence_preview_count = sum(
        len(candidate.evidence_snippets) for candidate in report.considered_candidates
    )
    report.runtime.telemetry.payload = RecommendationPayloadTelemetry(
        response_detail=detail,
        response_bytes=0,
        candidate_count=len(report.considered_candidates),
        evidence_preview_count=evidence_preview_count,
    )
    report.runtime.telemetry.payload = report.runtime.telemetry.payload.model_copy(
        update={
            "response_bytes": len(
                report.model_dump_json(exclude_none=True).encode("utf-8")
            )
        }
    )
    return report


def _transform_report_for_detail_mode(
    report: MethodRecommendationReport, detail: RecommendationResponseDetail
) -> MethodRecommendationReport:
    """Transforms a recommendation report based on the requested detail mode."""
    working_report = report.model_copy(deep=True)
    working_report.discovery_summary = _build_discovery_summary(working_report)
    if detail == "operator":
        return _attach_payload_telemetry(working_report, detail)

    compact_candidates = [
        _compact_candidate_for_agent(candidate)
        for candidate in working_report.considered_candidates[:3]
    ]
    compact_recommended = (
        _compact_candidate_for_agent(working_report.recommended_candidate)
        if working_report.recommended_candidate is not None
        else None
    )
    compact_report = MethodRecommendationReport(
        request=None,  # Omit echoed request
        source_mode=working_report.source_mode,
        search_query_used=working_report.search_query_used,
        target_compound_context=working_report.target_compound_context,
        impurity_compound_contexts=working_report.impurity_compound_contexts,
        external_evidence_trace=working_report.external_evidence_trace,
        discovered_papers=[],  # Omit full paper list
        skipped_papers=[],  # Omit full skip list, summary is in discovery_summary
        discovery_summary=working_report.discovery_summary,
        considered_candidates=compact_candidates,
        recommended_candidate=compact_recommended,
        runtime=working_report.runtime,
    )
    return _attach_payload_telemetry(compact_report, detail)


@router.post("/clarify", response_model=ClarifyResponse, operation_id="clarify_request")
def clarify_request(
    payload: ClarifyRequestPayload,
    request: Request,
) -> ClarifyResponse:
    """
    Analyse a discovery request and return up to 2 clarifying questions for
    important parameters that are missing and would materially change results.
    Returns an empty list when LLM orchestration is disabled or if the request
    is already sufficiently detailed.
    """
    gemini_client = getattr(request.app.state, "gemini_client", None)
    if gemini_client is None:
        return ClarifyResponse(questions=[])

    raw = gemini_client.clarify_request(
        request_text=payload.request_text,
        analyte_name=payload.analyte_name,
        max_run_time_min=payload.max_run_time_min,
        matrix_hint=payload.matrix_hint,
        detector_types=payload.detector_types,
        require_mass_spectrometry=payload.require_mass_spectrometry,
    )
    return ClarifyResponse(
        questions=[ClarifyQuestion(**q) for q in raw]
    )


@router.post("/run", response_model=MethodRecommendationReport, operation_id="run_recommendation_sync")
@limiter.limit(RECOMMENDATION_RATE_LIMIT_POLICY)
def run_recommendation_canonical(
    payload: MethodRecommendationRequest,
    request: Request,
    response_detail: RecommendationResponseDetail = "agent",
) -> MethodRecommendationReport:
    """
    Executes a synchronous recommendation run.
    Recommended for agentic use cases where immediate feedback is required.
    """
    try:
        report = recommend_methods(
            request=payload,
            **_build_recommendation_kwargs(request.app),
        )
        return _transform_report_for_detail_mode(report, response_detail)
    except RecommendationRuntimeError as exc:
        raise HTTPException(
            status_code=_runtime_error_status_code(exc),
            detail=exc.error_detail.model_dump(),
        ) from exc


@router.post(
    "/recommend",
    response_model=MethodRecommendationReport,
    deprecated=True,
    summary="Legacy recommendation endpoint",
)
@limiter.limit(RECOMMENDATION_RATE_LIMIT_POLICY)
def run_recommendation(
    payload: MethodRecommendationRequest,
    request: Request,
    response_detail: RecommendationResponseDetail = "operator",
) -> MethodRecommendationReport:
    try:
        report = recommend_methods(
            request=payload,
            **_build_recommendation_kwargs(request.app),
        )
        return _transform_report_for_detail_mode(report, response_detail)
    except RecommendationRuntimeError as exc:
        raise HTTPException(
            status_code=_runtime_error_status_code(exc),
            detail=exc.error_detail.model_dump(),
        ) from exc


@router.post("/runs", response_model=RecommendationJobAccepted, operation_id="create_recommendation_run")
@limiter.limit(RECOMMENDATION_RATE_LIMIT_POLICY)
def create_recommendation_run_canonical(
    payload: MethodRecommendationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RecommendationJobAccepted:
    """
    Creates an asynchronous recommendation run.
    Returns a job ID that can be polled via /recommendation/runs/{job_id}.
    """
    job = request.app.state.recommendation_job_store.create_job(payload)
    background_tasks.add_task(_run_recommendation_job, job.job_id, payload, request.app)
    return RecommendationJobAccepted(
        job_id=job.job_id,
        state=job.state,
        stage=job.stage,
        status_url=f"/recommendation/runs/{job.job_id}",
    )


@router.post(
    "/jobs",
    response_model=RecommendationJobAccepted,
    deprecated=True,
    summary="Legacy job creation endpoint",
)
@limiter.limit(RECOMMENDATION_RATE_LIMIT_POLICY)
def create_recommendation_job(
    payload: MethodRecommendationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RecommendationJobAccepted:
    job = request.app.state.recommendation_job_store.create_job(payload)
    background_tasks.add_task(_run_recommendation_job, job.job_id, payload, request.app)
    return RecommendationJobAccepted(
        job_id=job.job_id,
        state=job.state,
        stage=job.stage,
        status_url=f"/recommendation/jobs/{job.job_id}",
    )


@router.get("/runs/{job_id}", response_model=RecommendationJobStatus, operation_id="get_recommendation_run_status")
@limiter.limit("240/minute")
def get_recommendation_run_canonical(
    job_id: str, request: Request, response_detail: RecommendationResponseDetail = "agent"
) -> RecommendationJobStatus:
    """
    Retrieves the status and result of a recommendation run.
    """
    job = request.app.state.recommendation_job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Recommendation run not found.")

    if job.report:
        job.report = _transform_report_for_detail_mode(job.report, response_detail)

    return job


@router.get(
    "/jobs/{job_id}",
    response_model=RecommendationJobStatus,
    deprecated=True,
    summary="Legacy job status endpoint",
)
@limiter.limit("240/minute")
def get_recommendation_job(
    job_id: str, request: Request, response_detail: RecommendationResponseDetail = "operator"
) -> RecommendationJobStatus:
    job = request.app.state.recommendation_job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Recommendation job not found.")

    if job.report:
        job.report = _transform_report_for_detail_mode(job.report, response_detail)

    return job
