from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from .hplc_text_extraction import extract_minimal_hplc
from .review_record_materialization import (
    ReviewRecordMaterializationError,
    sync_review_record_promotion,
)
from .review_record_schemas import (
    ReviewRecordApprovalUpdate,
    ReviewRecordPromotionUpdate,
    ReviewRecord,
    ReviewRecordSummary,
    ReviewRecordApproveRequest,
    ReviewRecordRejectRequest,
)
from .sqlite_review_record_store import SqliteReviewRecordStore
from .review_record_store import ReviewRecordNotFoundError, ReviewRecordStatusError
from .retrieval_store import RetrievalStore, SeededRetrievalStore
from .source_document_registry import InMemorySourceDocumentRegistry

router = APIRouter(tags=["review-records"])


def get_source_document_registry(request: Request) -> InMemorySourceDocumentRegistry:
    return request.app.state.source_document_registry


def get_review_record_store(request: Request) -> SqliteReviewRecordStore:
    return request.app.state.review_record_store


def get_retrieval_store(request: Request) -> RetrievalStore:
    return request.app.state.retrieval_store


SourceDocumentRegistryDep = Annotated[
    InMemorySourceDocumentRegistry, Depends(get_source_document_registry)
]
ReviewRecordStoreDep = Annotated[
    SqliteReviewRecordStore, Depends(get_review_record_store)
]
RetrievalStoreDep = Annotated[RetrievalStore, Depends(get_retrieval_store)]
SourceDocumentId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=200,
        description="Registered source document identifier",
    ),
]
ReviewRecordId = Annotated[
    str,
    Path(min_length=1, max_length=200, description="Review record identifier"),
]


@router.post(
    "/review-records/from-source-documents/{source_document_id}",
    status_code=201,
    operation_id="create_review_record_from_source",
)
def create_review_record_canonical(
    source_document_id: SourceDocumentId,
    registry: SourceDocumentRegistryDep,
    review_store: ReviewRecordStoreDep,
    request: Request,
) -> ReviewRecord:
    """
    Creates a review record from a registered source document.
    """
    document = registry.get(source_document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source document not found: {source_document_id}",
        )
    extraction_snapshot = extract_minimal_hplc(
        document, gemini_client=getattr(request.app.state, "gemini_client", None)
    )
    return review_store.create_from_extraction(extraction_snapshot)


@router.post(
    "/source-documents/{source_document_id}/review-records",
    status_code=201,
    deprecated=True,
    summary="Legacy review record creation endpoint",
)
def create_review_record(
    source_document_id: SourceDocumentId,
    registry: SourceDocumentRegistryDep,
    review_store: ReviewRecordStoreDep,
    request: Request,
) -> ReviewRecord:
    document = registry.get(source_document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source document not found: {source_document_id}",
        )
    extraction_snapshot = extract_minimal_hplc(
        document, gemini_client=getattr(request.app.state, "gemini_client", None)
    )
    return review_store.create_from_extraction(extraction_snapshot)


@router.get("/review-records")
def list_review_records(
    review_store: ReviewRecordStoreDep,
) -> list[ReviewRecordSummary]:
    return review_store.list()


@router.get("/review-records/{review_record_id}")
def get_review_record(
    review_record_id: ReviewRecordId,
    review_store: ReviewRecordStoreDep,
) -> ReviewRecord:
    try:
        return review_store.get(review_record_id)
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Review record not found: {review_record_id}",
        ) from exc


@router.post("/review-records/{review_record_id}/approve", operation_id="approve_review_record")
def approve_review_record(
    review_record_id: ReviewRecordId,
    payload: ReviewRecordApproveRequest,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
) -> ReviewRecord:
    """
    Approves a review record, finalizing its extraction and optionally promoting it to the local corpus.
    """
    try:
        approval_payload = ReviewRecordApprovalUpdate(
            status="approved",
            review_notes=payload.review_notes,
            entity_resolutions=payload.entity_resolutions,
            promote_to_local_corpus=payload.promote_to_local_corpus,
        )
        updated_record = review_store.update_status(review_record_id, approval_payload)
        sync_review_record_promotion(updated_record, retrieval_store)
        return updated_record
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Review record not found: {review_record_id}",
        ) from exc
    except ReviewRecordStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReviewRecordMaterializationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/review-records/{review_record_id}/reject", operation_id="reject_review_record")
def reject_review_record(
    review_record_id: ReviewRecordId,
    payload: ReviewRecordRejectRequest,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
) -> ReviewRecord:
    """
    Rejects a review record.
    """
    try:
        rejection_payload = ReviewRecordApprovalUpdate(
            status="rejected",
            review_notes=payload.review_notes,
            promote_to_local_corpus=False,
        )
        updated_record = review_store.update_status(review_record_id, rejection_payload)
        sync_review_record_promotion(updated_record, retrieval_store)
        return updated_record
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Review record not found: {review_record_id}",
        ) from exc
    except ReviewRecordStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReviewRecordMaterializationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/review-records/{review_record_id}/promote", operation_id="promote_review_record")
def promote_review_record(
    review_record_id: ReviewRecordId,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
) -> ReviewRecord:
    """
    Promotes an approved review record to the local corpus.
    """
    try:
        updated_record = review_store.update_promotion(
            review_record_id,
            promote_to_local_corpus=True,
        )
        sync_review_record_promotion(updated_record, retrieval_store)
        return updated_record
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Review record not found: {review_record_id}",
        ) from exc
    except ReviewRecordStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/review-records/{review_record_id}/demote", operation_id="demote_review_record")
def demote_review_record(
    review_record_id: ReviewRecordId,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
) -> ReviewRecord:
    """
    Removes a review record from the local corpus.
    """
    try:
        updated_record = review_store.update_promotion(
            review_record_id,
            promote_to_local_corpus=False,
        )
        sync_review_record_promotion(updated_record, retrieval_store)
        return updated_record
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Review record not found: {review_record_id}",
        ) from exc
    except ReviewRecordStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/review-records/{review_record_id}/status",
    deprecated=True,
    summary="Legacy status update endpoint",
)
def update_review_record_status(
    review_record_id: ReviewRecordId,
    payload: ReviewRecordApprovalUpdate,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
) -> ReviewRecord:
    try:
        updated_record = review_store.update_status(review_record_id, payload)
        sync_review_record_promotion(updated_record, retrieval_store)
        return updated_record
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Review record not found: {review_record_id}",
        ) from exc
    except ReviewRecordStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReviewRecordMaterializationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/review-records/{review_record_id}/promotion",
    deprecated=True,
    summary="Legacy promotion update endpoint",
)
def update_review_record_promotion(
    review_record_id: ReviewRecordId,
    payload: ReviewRecordPromotionUpdate,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
) -> ReviewRecord:
    try:
        updated_record = review_store.update_promotion(
            review_record_id,
            promote_to_local_corpus=payload.promote_to_local_corpus,
        )
        sync_review_record_promotion(updated_record, retrieval_store)
        return updated_record
    except ReviewRecordNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Review record not found: {review_record_id}",
        ) from exc
    except ReviewRecordStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
