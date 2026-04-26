from __future__ import annotations

from .source_document_ingestion import ingest_source_document
from .source_document_schemas import (
    RegisteredSourceDocument,
    SourceDocumentRegisterRequest,
)


class DuplicateSourceDocumentError(ValueError):
    pass


class InMemorySourceDocumentRegistry:
    def __init__(self) -> None:
        self._documents: dict[str, RegisteredSourceDocument] = {}

    def register(
        self, payload: SourceDocumentRegisterRequest
    ) -> RegisteredSourceDocument:
        source_document_id = payload.source_document.source_document_id
        if source_document_id in self._documents:
            raise DuplicateSourceDocumentError(
                f"Source document already registered: {source_document_id}"
            )

        document = ingest_source_document(payload)
        self._documents[source_document_id] = document
        return document

    def get(self, source_document_id: str) -> RegisteredSourceDocument | None:
        return self._documents.get(source_document_id)
