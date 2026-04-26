from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from .hplc_extraction_schemas import MinimalHplcExtractionResponse
from .hplc_text_extraction import extract_minimal_hplc
from .source_document_registry import InMemorySourceDocumentRegistry

router = APIRouter(prefix="/source-documents", tags=["hplc-extraction"])


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


@router.post("/{source_document_id}/extract-hplc")
def extract_hplc_from_source_document(
    source_document_id: SourceDocumentId,
    registry: SourceDocumentRegistryDep,
    request: Request,
) -> MinimalHplcExtractionResponse:
    document = registry.get(source_document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source document not found: {source_document_id}",
        )
    return extract_minimal_hplc(
        document, gemini_client=getattr(request.app.state, "gemini_client", None)
    )
