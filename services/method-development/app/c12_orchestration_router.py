from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from .ai_runtime_settings import AiRuntimeSettings
from .c12_orchestration import orchestrate_review_record_preparation
from .c12_orchestration_schemas import (
    C12ReviewRecordOrchestrationRequest,
    C12ReviewRecordOrchestrationResponse,
)
from .gemini_orchestration_client import GeminiOrchestrationClient
from .sqlite_review_record_store import SqliteReviewRecordStore
from .retrieval_store import RetrievalStore, SeededRetrievalStore
from .source_document_ingestion import SourceDocumentIngestionError
from .source_document_registry import (
    DuplicateSourceDocumentError,
    InMemorySourceDocumentRegistry,
)

router = APIRouter(prefix="/c12", tags=["c12-orchestration"])


def get_source_document_registry(request: Request) -> InMemorySourceDocumentRegistry:
    return request.app.state.source_document_registry


def get_review_record_store(request: Request) -> SqliteReviewRecordStore:
    return request.app.state.review_record_store


def get_retrieval_store(request: Request) -> RetrievalStore:
    return request.app.state.retrieval_store


def get_ai_runtime_settings(request: Request) -> AiRuntimeSettings:
    return request.app.state.ai_runtime_settings


def get_gemini_client(request: Request) -> GeminiOrchestrationClient | None:
    return request.app.state.gemini_client


SourceDocumentRegistryDep = Annotated[
    InMemorySourceDocumentRegistry, Depends(get_source_document_registry)
]
ReviewRecordStoreDep = Annotated[
    SqliteReviewRecordStore, Depends(get_review_record_store)
]
RetrievalStoreDep = Annotated[RetrievalStore, Depends(get_retrieval_store)]
AiRuntimeSettingsDep = Annotated[AiRuntimeSettings, Depends(get_ai_runtime_settings)]
GeminiClientDep = Annotated[
    GeminiOrchestrationClient | None, Depends(get_gemini_client)
]


@router.post("/review-records/prepare", operation_id="prepare_review_record")
def prepare_review_record_canonical(
    payload: C12ReviewRecordOrchestrationRequest,
    registry: SourceDocumentRegistryDep,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
    ai_runtime_settings: AiRuntimeSettingsDep,
    gemini_client: GeminiClientDep,
) -> C12ReviewRecordOrchestrationResponse:
    """
    High-level orchestration for preparing a review record.
    Handles source document registration, ingestion, and initial extraction.
    Use this instead of lower-level review-record creation when starting from a raw source.
    """
    try:
        return orchestrate_review_record_preparation(
            payload,
            registry=registry,
            review_store=review_store,
            retrieval_store=retrieval_store,
            ai_runtime_settings=ai_runtime_settings,
            gemini_client=gemini_client,
        )
    except DuplicateSourceDocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceDocumentIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/review-records/orchestrate",
    deprecated=True,
    summary="Legacy orchestration endpoint",
)
def orchestrate_review_record(
    payload: C12ReviewRecordOrchestrationRequest,
    registry: SourceDocumentRegistryDep,
    review_store: ReviewRecordStoreDep,
    retrieval_store: RetrievalStoreDep,
    ai_runtime_settings: AiRuntimeSettingsDep,
    gemini_client: GeminiClientDep,
) -> C12ReviewRecordOrchestrationResponse:
    try:
        return orchestrate_review_record_preparation(
            payload,
            registry=registry,
            review_store=review_store,
            retrieval_store=retrieval_store,
            ai_runtime_settings=ai_runtime_settings,
            gemini_client=gemini_client,
        )
    except DuplicateSourceDocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceDocumentIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
