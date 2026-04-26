from __future__ import annotations

from typing import Literal

from pydantic import Field

from .review_record_schemas import MolecularEntityResolutionInput, ReviewRecord
from .retrieval_schemas import RetrievalBaseModel, ValidationStatus
from .source_document_schemas import SourceDocumentRegisterRequest

RegistrationStepStatus = Literal["created", "reused"]
ExtractionStepStatus = Literal["completed", "reused"]
ReviewRecordStepStatus = Literal["created", "reused"]
ApprovalStepStatus = Literal["approved", "reused", "skipped", "blocked"]
AiObserverStepStatus = Literal["completed", "skipped", "blocked"]
OrchestrationStepState = Literal["completed", "reused", "skipped", "blocked", "cutoff"]


class C12ReviewRecordOrchestrationRequest(SourceDocumentRegisterRequest):
    entity_resolutions: list[MolecularEntityResolutionInput] = Field(
        default_factory=list
    )
    approve_if_ready: bool = False
    retry_existing: bool = True
    max_step_attempts: int = Field(default=1, ge=1, le=3)
    max_total_steps: int = Field(default=5, ge=3, le=8)


class C12ExecutionBudget(RetrievalBaseModel):
    max_step_attempts: int = Field(ge=1, le=3)
    max_total_steps: int = Field(ge=3, le=8)
    total_steps_attempted: int = Field(ge=0, le=8)
    cutoff_reached: bool = False
    cutoff_reason: str | None = Field(default=None, min_length=1, max_length=400)


class C12BaseStep(RetrievalBaseModel):
    state: OrchestrationStepState
    attempts_used: int = Field(ge=0, le=3)
    attempts_allowed: int = Field(ge=1, le=3)
    detail: str | None = Field(default=None, min_length=1, max_length=400)


class C12RegistrationStep(C12BaseStep):
    status: RegistrationStepStatus


class C12ExtractionStep(C12BaseStep):
    status: ExtractionStepStatus
    validation_status: ValidationStatus
    retrieval_record_ready: bool = False


class C12ReviewRecordStep(C12BaseStep):
    status: ReviewRecordStepStatus
    review_record_id: str = Field(min_length=1, max_length=200)


class C12ApprovalStep(C12BaseStep):
    status: ApprovalStepStatus
    reason: str | None = Field(default=None, min_length=1, max_length=400)


class C12AiObserverStep(C12BaseStep):
    status: AiObserverStepStatus
    model: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, min_length=1, max_length=400)
    recommended_next_action: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    concerns: list[str] = Field(default_factory=list)


class C12ReviewRecordOrchestrationSteps(RetrievalBaseModel):
    registration: C12RegistrationStep
    extraction: C12ExtractionStep
    review_record: C12ReviewRecordStep
    approval: C12ApprovalStep
    ai_observer: C12AiObserverStep


class C12ReviewRecordOrchestrationResponse(RetrievalBaseModel):
    source_document_id: str = Field(min_length=1, max_length=200)
    budget: C12ExecutionBudget
    steps: C12ReviewRecordOrchestrationSteps
    review_record: ReviewRecord
