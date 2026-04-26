from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from .source_document_ingestion import SourceDocumentIngestionError
from .source_document_registry import (
    DuplicateSourceDocumentError,
    InMemorySourceDocumentRegistry,
)
from .source_document_schemas import (
    RegisteredSourceDocument,
    SourceDocumentRegisterRequest,
)

router = APIRouter(prefix="/source-documents", tags=["source-documents"])


def get_source_document_registry(request: Request) -> InMemorySourceDocumentRegistry:
    return request.app.state.source_document_registry


SourceDocumentRegistryDep = Annotated[
    InMemorySourceDocumentRegistry, Depends(get_source_document_registry)
]
SourceDocumentId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=200,
        description="Registered source document identifier",
    ),
]


@router.post("/", status_code=status.HTTP_201_CREATED)
def register_source_document(
    payload: SourceDocumentRegisterRequest,
    registry: SourceDocumentRegistryDep,
) -> RegisteredSourceDocument:
    try:
        return registry.register(payload)
    except DuplicateSourceDocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceDocumentIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{source_document_id}")
def get_source_document(
    source_document_id: SourceDocumentId,
    registry: SourceDocumentRegistryDep,
) -> RegisteredSourceDocument:
    document = registry.get(source_document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source document not found: {source_document_id}",
        )
    return document
