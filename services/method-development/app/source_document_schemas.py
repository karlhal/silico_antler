from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .retrieval_schemas import SourceDocumentMetadata

SourceDocumentSectionKind = Literal[
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "references",
    "other",
]
DocumentAssetKind = Literal["table", "figure", "supplement"]


class SourceDocumentBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceDocumentPage(SourceDocumentBaseModel):
    page_number: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=50000)


class SourceDocumentSection(SourceDocumentBaseModel):
    section_id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=1000)
    normalized_label: SourceDocumentSectionKind = "other"
    start_page_number: int | None = Field(default=None, ge=1)
    end_page_number: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1, max_length=1000000)

    @model_validator(mode="after")
    def validate_page_bounds(self) -> SourceDocumentSection:
        if (
            self.start_page_number is not None
            and self.end_page_number is not None
            and self.end_page_number < self.start_page_number
        ):
            raise ValueError("end_page_number must be >= start_page_number")
        return self


class SourceDocumentAssetPlaceholder(SourceDocumentBaseModel):
    asset_kind: DocumentAssetKind
    label: str | None = Field(default=None, min_length=1, max_length=1000)
    section_label: str | None = Field(default=None, min_length=1, max_length=1000)
    page_number: int | None = Field(default=None, ge=1)
    caption_hint: str | None = Field(default=None, min_length=1, max_length=2000)


class RegisteredSourceDocument(SourceDocumentBaseModel):
    source_document: SourceDocumentMetadata
    raw_text: str = Field(min_length=1, max_length=500000)
    pages: list[SourceDocumentPage] = Field(default_factory=list)
    sections: list[SourceDocumentSection] = Field(default_factory=list)
    table_placeholders: list[SourceDocumentAssetPlaceholder] = Field(
        default_factory=list
    )
    figure_placeholders: list[SourceDocumentAssetPlaceholder] = Field(
        default_factory=list
    )
    supplement_placeholders: list[SourceDocumentAssetPlaceholder] = Field(
        default_factory=list
    )
    ingestion_warnings: list[str] = Field(default_factory=list)


class SourceDocumentRegisterRequest(SourceDocumentBaseModel):
    source_document: SourceDocumentMetadata
    html_content: str | None = Field(default=None, min_length=1, max_length=1000000)
    pdf_base64: str | None = Field(default=None, min_length=1, max_length=10000000)

    @model_validator(mode="after")
    def validate_content_shape(self) -> SourceDocumentRegisterRequest:
        source_type = self.source_document.source_type
        if source_type not in {"html", "pdf"}:
            raise ValueError(
                "source_document.source_type must be 'html' or 'pdf' for C5 registration"
            )

        if source_type == "html":
            if self.html_content is None:
                raise ValueError("html_content is required when source_type is 'html'")
            if self.pdf_base64 is not None:
                raise ValueError(
                    "pdf_base64 must not be provided when source_type is 'html'"
                )

        if source_type == "pdf":
            if self.pdf_base64 is None:
                raise ValueError("pdf_base64 is required when source_type is 'pdf'")
            if self.html_content is not None:
                raise ValueError(
                    "html_content must not be provided when source_type is 'pdf'"
                )

        return self
