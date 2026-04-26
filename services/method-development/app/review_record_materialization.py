from __future__ import annotations

from typing import cast

from .review_record_schemas import (
    ApprovedRetrievalRecordSnapshot,
    ReviewRecord,
    ReviewRecordCorpusPromotion,
)
from .retrieval_schemas import (
    HplcMolecularEntity,
    RetrievalMethodRecord,
    RetrievalRecordReviewSummary,
)
from .retrieval_store import RetrievalStore, SeededRetrievalStore


class ReviewRecordMaterializationError(ValueError):
    pass


def build_materialized_record_id(review_record: ReviewRecord) -> str:
    return f"approved-{review_record.review_record_id}"


def materialize_review_record(review_record: ReviewRecord) -> RetrievalMethodRecord:
    record_draft = review_record.record_draft
    if record_draft is None:
        raise ReviewRecordMaterializationError("Review record has no record_draft")

    entity_drafts = [
        draft
        for draft in record_draft.molecular_entity_drafts
        if draft.selected_for_record_draft
        and draft.ready_for_retrieval_entity
        and draft.smiles_string is not None
    ]
    if not entity_drafts:
        raise ReviewRecordMaterializationError(
            "Review record has no retrieval-ready molecular entities"
        )

    return RetrievalMethodRecord(
        record_id=build_materialized_record_id(review_record),
        source_document=record_draft.source_document,
        molecular_entities=[
            HplcMolecularEntity(
                local_identifier=draft.local_identifier,
                smiles_string=cast(str, draft.smiles_string),
                display_name=draft.display_name,
                observed_retention_time_min=draft.observed_retention_time_min,
                notes=("; ".join(draft.linkage_notes) if draft.linkage_notes else None),
            )
            for draft in entity_drafts
        ],
        chromatography_system=record_draft.chromatography_system,
        method_parameters=record_draft.method_parameters,
        provenance=review_record.provenance,
        validation=review_record.validation,
        notes=review_record.review_notes,
    )


def build_review_summary(review_record: ReviewRecord) -> RetrievalRecordReviewSummary:
    return RetrievalRecordReviewSummary(
        record_state="approved",
        review_record_id=review_record.review_record_id,
        validation_status=review_record.validation.status,
        retrieval_ready=review_record.validation.retrieval_ready,
        corpus_origin="review_promoted",
    )


def build_approved_record_snapshot(
    review_record: ReviewRecord,
) -> ApprovedRetrievalRecordSnapshot:
    return ApprovedRetrievalRecordSnapshot(
        record=materialize_review_record(review_record),
        review_summary=build_review_summary(review_record),
    )


def get_approved_record_snapshot(
    review_record: ReviewRecord,
) -> ApprovedRetrievalRecordSnapshot:
    if review_record.approved_record_snapshot is not None:
        return review_record.approved_record_snapshot
    return build_approved_record_snapshot(review_record)


def build_corpus_promotion(
    review_record: ReviewRecord, *, promote_to_local_corpus: bool
) -> ReviewRecordCorpusPromotion:
    if not promote_to_local_corpus:
        return ReviewRecordCorpusPromotion()
    return ReviewRecordCorpusPromotion(
        status="promoted",
        local_corpus_record_id=build_materialized_record_id(review_record),
    )


def sync_review_record_promotion(
    review_record: ReviewRecord, retrieval_store: RetrievalStore
) -> None:
    materialized_record_id = build_materialized_record_id(review_record)
    if (
        review_record.status != "approved"
        or review_record.corpus_promotion.status != "promoted"
    ):
        retrieval_store.remove_record(materialized_record_id)
        return
    try:
        approved_snapshot = get_approved_record_snapshot(review_record)
    except ReviewRecordMaterializationError:
        retrieval_store.remove_record(materialized_record_id)
        return
    retrieval_store.upsert_record(
        approved_snapshot.record,
        approved_snapshot.review_summary,
    )


def sync_promoted_review_records(
    review_records: list[ReviewRecord], retrieval_store: RetrievalStore
) -> None:
    for review_record in review_records:
        sync_review_record_promotion(review_record, retrieval_store)


def sync_approved_review_records(
    review_records: list[ReviewRecord], retrieval_store: RetrievalStore
) -> None:
    sync_promoted_review_records(review_records, retrieval_store)
