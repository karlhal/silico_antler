from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .hplc_extraction_schemas import MinimalHplcExtractionResponse, RetrievalRecordDraft
from .retrieval_schemas import (
    RecordValidationState,
    RetrievalBaseModel,
    RetrievalMethodRecord,
    RetrievalProvenance,
    RetrievalRecordReviewSummary,
)

ReviewRecordStatus = Literal["draft", "approved", "rejected"]
ReviewRecordPromotionStatus = Literal["not_promoted", "promoted"]


class ReviewRecordCorpusPromotion(RetrievalBaseModel):
    status: ReviewRecordPromotionStatus = "not_promoted"
    local_corpus_record_id: str | None = Field(
        default=None, min_length=1, max_length=200
    )


class ReviewRecordSummary(RetrievalBaseModel):
    review_record_id: str = Field(min_length=1, max_length=200)
    source_document_id: str = Field(min_length=1, max_length=200)
    status: ReviewRecordStatus = "draft"
    validation: RecordValidationState
    provenance: RetrievalProvenance
    corpus_promotion: ReviewRecordCorpusPromotion = Field(
        default_factory=ReviewRecordCorpusPromotion
    )


class ApprovedRetrievalRecordSnapshot(RetrievalBaseModel):
    record: RetrievalMethodRecord
    review_summary: RetrievalRecordReviewSummary


class ReviewRecord(RetrievalBaseModel):
    review_record_id: str = Field(min_length=1, max_length=200)
    status: ReviewRecordStatus = "draft"
    review_notes: str | None = Field(default=None, min_length=1, max_length=1000)
    provenance: RetrievalProvenance
    validation: RecordValidationState
    record_draft: RetrievalRecordDraft | None = None
    extraction_snapshot: MinimalHplcExtractionResponse
    approved_record_snapshot: ApprovedRetrievalRecordSnapshot | None = None
    corpus_promotion: ReviewRecordCorpusPromotion = Field(
        default_factory=ReviewRecordCorpusPromotion
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_corpus_promotion(cls, value):
        if not isinstance(value, dict) or "corpus_promotion" in value:
            return value
        approved_record_snapshot = value.get("approved_record_snapshot")
        if value.get("status") != "approved" or not isinstance(
            approved_record_snapshot, dict
        ):
            return value
        record = approved_record_snapshot.get("record")
        local_corpus_record_id = (
            record.get("record_id")
            if isinstance(record, dict)
            else f"approved-{value.get('review_record_id', '')}".rstrip("-")
        )
        return {
            **value,
            "corpus_promotion": {
                "status": "promoted",
                "local_corpus_record_id": local_corpus_record_id or None,
            },
        }


class ReviewRecordStatusUpdate(RetrievalBaseModel):
    status: ReviewRecordStatus
    review_notes: str | None = Field(default=None, min_length=1, max_length=1000)


class MolecularEntityResolutionInput(RetrievalBaseModel):
    local_identifier: str = Field(min_length=1, max_length=120)
    smiles_string: str = Field(min_length=1, max_length=400)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)


class ReviewRecordApprovalUpdate(ReviewRecordStatusUpdate):
    entity_resolutions: list[MolecularEntityResolutionInput] = Field(
        default_factory=list
    )
    promote_to_local_corpus: bool = True


class ReviewRecordPromotionUpdate(RetrievalBaseModel):
    promote_to_local_corpus: bool = True


class ReviewRecordApproveRequest(RetrievalBaseModel):
    review_notes: str | None = Field(default=None, min_length=1, max_length=1000)
    entity_resolutions: list[MolecularEntityResolutionInput] = Field(
        default_factory=list
    )
    promote_to_local_corpus: bool = True


class ReviewRecordRejectRequest(RetrievalBaseModel):
    review_notes: str = Field(min_length=1, max_length=1000)
