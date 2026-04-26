from __future__ import annotations

from .ai_runtime_settings import AiRuntimeSettings
from .c12_orchestration_schemas import (
    C12ExecutionBudget,
    C12AiObserverStep,
    C12ApprovalStep,
    C12ExtractionStep,
    C12RegistrationStep,
    C12ReviewRecordOrchestrationRequest,
    C12ReviewRecordOrchestrationResponse,
    C12ReviewRecordOrchestrationSteps,
    C12ReviewRecordStep,
)
from .gemini_orchestration_client import GeminiClientError, GeminiOrchestrationClient
from .hplc_text_extraction import extract_minimal_hplc
from .review_record_materialization import sync_review_record_promotion
from .review_record_schemas import ReviewRecordApprovalUpdate
from .sqlite_review_record_store import SqliteReviewRecordStore
from .review_record_store import ReviewRecordStatusError
from .retrieval_store import RetrievalStore, SeededRetrievalStore
from .source_document_registry import InMemorySourceDocumentRegistry


class _ExecutionBudgetTracker:
    def __init__(self, *, max_step_attempts: int, max_total_steps: int) -> None:
        self.max_step_attempts = max_step_attempts
        self.max_total_steps = max_total_steps
        self.total_steps_attempted = 0
        self.cutoff_reason: str | None = None

    def claim(self, step_name: str) -> bool:
        del step_name
        if self.total_steps_attempted >= self.max_total_steps:
            self.cutoff_reason = f"Reached orchestration cutoff after {self.max_total_steps} step attempts"
            return False
        self.total_steps_attempted += 1
        return True

    def summary(self) -> C12ExecutionBudget:
        return C12ExecutionBudget(
            max_step_attempts=self.max_step_attempts,
            max_total_steps=self.max_total_steps,
            total_steps_attempted=self.total_steps_attempted,
            cutoff_reached=self.cutoff_reason is not None,
            cutoff_reason=self.cutoff_reason,
        )


def orchestrate_review_record_preparation(
    payload: C12ReviewRecordOrchestrationRequest,
    *,
    registry: InMemorySourceDocumentRegistry,
    review_store: SqliteReviewRecordStore,
    retrieval_store: RetrievalStore,
    ai_runtime_settings: AiRuntimeSettings,
    gemini_client: GeminiOrchestrationClient | None,
    shared_llm_call_counter: list[int] | None = None,
) -> C12ReviewRecordOrchestrationResponse:
    source_document_id = payload.source_document.source_document_id
    effective_max_step_attempts = min(
        payload.max_step_attempts, ai_runtime_settings.max_step_attempts_per_run
    )
    effective_max_total_steps = min(
        payload.max_total_steps, ai_runtime_settings.max_total_steps_per_run
    )
    budget = _ExecutionBudgetTracker(
        max_step_attempts=effective_max_step_attempts,
        max_total_steps=effective_max_total_steps,
    )

    if not budget.claim("registration"):
        raise RuntimeError(
            "registration cannot be cutoff in current orchestration flow"
        )
    existing_document = registry.get(source_document_id)
    if existing_document is not None and payload.retry_existing:
        document = existing_document
        registration_step = C12RegistrationStep(
            status="reused",
            state="reused",
            attempts_used=1,
            attempts_allowed=effective_max_step_attempts,
            detail="Reused previously registered source document",
        )
    else:
        document = registry.register(payload)
        registration_step = C12RegistrationStep(
            status="created",
            state="completed",
            attempts_used=1,
            attempts_allowed=effective_max_step_attempts,
            detail="Registered source document from request payload",
        )

    if not budget.claim("extraction"):
        raise RuntimeError("extraction cannot be cutoff in current orchestration flow")
    review_record = (
        review_store.latest_for_source_document(source_document_id)
        if payload.retry_existing
        else None
    )
    if not budget.claim("review_record"):
        raise RuntimeError("review-record step cannot be cutoff in current flow")
    if review_record is None:
        extraction_snapshot = extract_minimal_hplc(document, gemini_client=gemini_client)
        review_record = review_store.create_from_extraction(extraction_snapshot)
        extraction_step = C12ExtractionStep(
            status="completed",
            state="completed",
            attempts_used=1,
            attempts_allowed=effective_max_step_attempts,
            detail="Computed extraction snapshot and validation state",
            validation_status=review_record.validation.status,
            retrieval_record_ready=review_record.validation.retrieval_ready,
        )
        review_record_step = C12ReviewRecordStep(
            status="created",
            state="completed",
            attempts_used=1,
            attempts_allowed=effective_max_step_attempts,
            detail="Created new review record from extraction snapshot",
            review_record_id=review_record.review_record_id,
        )
    else:
        extraction_step = C12ExtractionStep(
            status="reused",
            state="reused",
            attempts_used=1,
            attempts_allowed=effective_max_step_attempts,
            detail="Reused existing review record snapshot instead of re-extracting",
            validation_status=review_record.validation.status,
            retrieval_record_ready=review_record.validation.retrieval_ready,
        )
        review_record_step = C12ReviewRecordStep(
            status="reused",
            state="reused",
            attempts_used=1,
            attempts_allowed=effective_max_step_attempts,
            detail="Reused latest review record for source document",
            review_record_id=review_record.review_record_id,
        )

    if payload.entity_resolutions and review_record.status != "approved":
        review_record = review_store.update_status(
            review_record.review_record_id,
            ReviewRecordApprovalUpdate(
                status=review_record.status,
                review_notes=review_record.review_notes,
                entity_resolutions=payload.entity_resolutions,
            ),
        )
        extraction_step = extraction_step.model_copy(
            update={
                "validation_status": review_record.validation.status,
                "retrieval_record_ready": review_record.validation.retrieval_ready,
            }
        )
        review_record_step = review_record_step.model_copy(
            update={"detail": "Applied entity resolutions to existing review record"}
        )

    if not payload.approve_if_ready:
        approval_step = C12ApprovalStep(
            status="skipped",
            state="skipped",
            attempts_used=0,
            attempts_allowed=effective_max_step_attempts,
            detail="Approval step disabled for this request",
            reason="approve_if_ready is false",
        )
    elif not budget.claim("approval"):
        approval_step = C12ApprovalStep(
            status="skipped",
            state="cutoff",
            attempts_used=0,
            attempts_allowed=effective_max_step_attempts,
            detail=budget.cutoff_reason,
            reason=budget.cutoff_reason,
        )
    elif review_record.status == "approved":
        if review_record.corpus_promotion.status != "promoted":
            review_record = review_store.update_promotion(
                review_record.review_record_id,
                promote_to_local_corpus=True,
            )
        sync_review_record_promotion(review_record, retrieval_store)
        approval_step = C12ApprovalStep(
            status="reused",
            state="reused",
            attempts_used=1,
            attempts_allowed=effective_max_step_attempts,
            detail="Review record was already approved and promoted into the local corpus",
            reason="review record already approved",
        )
    else:
        try:
            review_record = review_store.update_status(
                review_record.review_record_id,
                ReviewRecordApprovalUpdate(
                    status="approved",
                    entity_resolutions=payload.entity_resolutions,
                ),
            )
            sync_review_record_promotion(review_record, retrieval_store)
            approval_step = C12ApprovalStep(
                status="approved",
                state="completed",
                attempts_used=1,
                attempts_allowed=effective_max_step_attempts,
                detail="Approved review record and promoted it into the local corpus",
            )
            extraction_step = extraction_step.model_copy(
                update={
                    "validation_status": review_record.validation.status,
                    "retrieval_record_ready": review_record.validation.retrieval_ready,
                }
            )
        except ReviewRecordStatusError as exc:
            approval_step = C12ApprovalStep(
                status="blocked",
                state="blocked",
                attempts_used=1,
                attempts_allowed=effective_max_step_attempts,
                detail="Approval attempted but validation gate blocked materialization",
                reason=str(exc),
            )

    if not ai_runtime_settings.enable_llm_orchestration:
        ai_observer_step = C12AiObserverStep(
            status="skipped",
            state="skipped",
            attempts_used=0,
            attempts_allowed=1,
            detail="LLM orchestration is disabled by server configuration",
        )
    elif ai_runtime_settings.llm_max_calls_per_run < 1:
        ai_observer_step = C12AiObserverStep(
            status="blocked",
            state="blocked",
            attempts_used=0,
            attempts_allowed=1,
            detail="Server-side LLM call budget is set to zero",
        )
    elif not budget.claim("ai_observer"):
        ai_observer_step = C12AiObserverStep(
            status="skipped",
            state="cutoff",
            attempts_used=0,
            attempts_allowed=1,
            detail=budget.cutoff_reason,
        )
    elif gemini_client is None:
        ai_observer_step = C12AiObserverStep(
            status="blocked",
            state="blocked",
            attempts_used=1,
            attempts_allowed=1,
            detail="LLM orchestration is enabled but no LLM client is configured",
        )
    elif shared_llm_call_counter is not None and shared_llm_call_counter[0] >= ai_runtime_settings.llm_max_calls_per_run:
        ai_observer_step = C12AiObserverStep(
            status="blocked",
            state="blocked",
            attempts_used=0,
            attempts_allowed=1,
            detail=f"Shared LLM call budget exhausted ({shared_llm_call_counter[0]}/{ai_runtime_settings.llm_max_calls_per_run})",
        )
    else:
        try:
            if shared_llm_call_counter is not None:
                shared_llm_call_counter[0] += 1
            insight = gemini_client.summarize_c12_outcome(
                source_document_id=source_document_id,
                review_record_id=review_record.review_record_id,
                review_record_status=review_record.status,
                validation_status=review_record.validation.status,
                retrieval_ready=review_record.validation.retrieval_ready,
                approval_status=approval_step.status,
                approval_reason=approval_step.reason,
            )
            ai_observer_step = C12AiObserverStep(
                status="completed",
                state="completed",
                attempts_used=1,
                attempts_allowed=1,
                detail="LLM observer summarized orchestration outcome",
                model=insight.model,
                summary=insight.summary,
                recommended_next_action=insight.recommended_next_action,
                concerns=list(insight.concerns),
            )
        except GeminiClientError as exc:
            ai_observer_step = C12AiObserverStep(
                status="blocked",
                state="blocked",
                attempts_used=1,
                attempts_allowed=1,
                detail=f"LLM observer call failed: {exc}",
            )

    return C12ReviewRecordOrchestrationResponse(
        source_document_id=source_document_id,
        budget=budget.summary(),
        steps=C12ReviewRecordOrchestrationSteps(
            registration=registration_step,
            extraction=extraction_step,
            review_record=review_record_step,
            approval=approval_step,
            ai_observer=ai_observer_step,
        ),
        review_record=review_record,
    )
