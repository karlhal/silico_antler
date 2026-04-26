from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DocumentKind = Literal["pdf", "html", "manual", "seeded"]
ExtractionMode = Literal[
    "manual", "seeded", "parsed_text", "parsed_table", "llm_assisted"
]
ChromatographyMode = Literal["rp_lc", "hilic", "unknown"]
ValidationSeverity = Literal["info", "warning", "error"]
ValidationStatus = Literal["unvalidated", "valid", "invalid", "needs_review"]
ReviewRecordState = Literal["seeded", "draft", "approved", "rejected"]
RetrievalMatchType = Literal["exact", "similarity"]
RankingMode = Literal["target_only", "target_plus_impurities"]
CorpusOrigin = Literal["seeded", "review_promoted"]


class RetrievalBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def coerce_bounded_text(
    value: object,
    *,
    max_length: int,
    allow_none: bool = False,
) -> str | None:
    if value is None:
        return None if allow_none else ""

    normalized = re.sub(r"\s+", " ", str(value)).strip()
    if not normalized:
        return None if allow_none else ""
    if len(normalized) <= max_length:
        return normalized
    truncated = normalized[:max_length].rstrip()
    return truncated or normalized[:max_length]


class EvidenceSnippet(RetrievalBaseModel):
    text: str = Field(min_length=1, max_length=4000)
    page_number: int | None = Field(default=None, ge=1)
    section_label: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("text", mode="before")
    @classmethod
    def validate_text_bounds(cls, value: object) -> str:
        return str(coerce_bounded_text(value, max_length=4000))

    @field_validator("section_label", mode="before")
    @classmethod
    def validate_section_label_bounds(cls, value: object) -> str | None:
        return coerce_bounded_text(value, max_length=120, allow_none=True)


class SourceDocumentMetadata(RetrievalBaseModel):
    source_document_id: str = Field(min_length=1, max_length=200)
    source_type: DocumentKind
    title: str | None = Field(default=None, min_length=1, max_length=500)
    doi: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
    published_year: int | None = Field(default=None, ge=1900, le=2100)


class HplcMolecularEntity(RetrievalBaseModel):
    local_identifier: str = Field(min_length=1, max_length=120)
    smiles_string: str = Field(min_length=1, max_length=400)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    observed_retention_time_min: float | None = Field(default=None, ge=0.0, le=240.0)
    notes: str | None = Field(default=None, min_length=1, max_length=500)


class MobilePhase(RetrievalBaseModel):
    solvent: str = Field(min_length=1, max_length=500)
    additive: str | None = Field(default=None, min_length=1, max_length=500)
    ph_estimate: float | None = Field(default=None, ge=0.0, le=14.0)

    @field_validator("solvent", mode="before")
    @classmethod
    def validate_solvent_bounds(cls, value: object) -> str:
        return str(coerce_bounded_text(value, max_length=500))

    @field_validator("additive", mode="before")
    @classmethod
    def validate_additive_bounds(cls, value: object) -> str | None:
        return coerce_bounded_text(value, max_length=500, allow_none=True)


class GradientPoint(RetrievalBaseModel):
    time_min: float = Field(ge=0.0, le=240.0)
    percent_b: float = Field(ge=0.0, le=100.0)


class ChromatographySystem(RetrievalBaseModel):
    mode: ChromatographyMode = "unknown"
    column_manufacturer: str | None = Field(default=None, min_length=1, max_length=120)
    column_name: str | None = Field(default=None, min_length=1, max_length=200)
    stationary_phase_chemistry: str = Field(min_length=1, max_length=80)
    column_length_mm: float = Field(ge=10.0, le=300.0)
    column_inner_diameter_mm: float = Field(ge=1.0, le=4.6)
    particle_size_um: float = Field(ge=1.3, le=10.0)


class MethodParameters(RetrievalBaseModel):
    mobile_phase_a: MobilePhase
    mobile_phase_b: MobilePhase | None = None
    flow_rate_ml_min: float = Field(ge=0.05, le=5.0)
    column_temperature_c: float | None = Field(default=None, ge=15.0, le=90.0)
    run_time_min: float | None = Field(default=None, gt=0.0, le=240.0)
    gradient_profile: list[GradientPoint] = Field(default_factory=list)
    isocratic_percent_b: float | None = Field(default=None, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_gradient_profile(self) -> MethodParameters:
        if self.gradient_profile and len(self.gradient_profile) < 2:
            raise ValueError("gradient_profile must have at least two points if present")

        previous_time: float | None = None
        for point in self.gradient_profile:
            if previous_time is not None and point.time_min < previous_time:
                raise ValueError(
                    "gradient_profile time_min values must be non-decreasing"
                )
            previous_time = point.time_min

        return self


class ValidationIssue(RetrievalBaseModel):
    code: str = Field(min_length=1, max_length=80)
    severity: ValidationSeverity
    message: str = Field(min_length=1, max_length=500)
    field_path: str | None = Field(default=None, min_length=1, max_length=200)


class RecordValidationState(RetrievalBaseModel):
    status: ValidationStatus = "unvalidated"
    retrieval_ready: bool = False
    issues: list[ValidationIssue] = Field(default_factory=list)


class RetrievalProvenance(RetrievalBaseModel):
    extraction_mode: ExtractionMode
    source_pages: list[int] = Field(default_factory=list)
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)


class RetrievalMethodRecord(RetrievalBaseModel):
    record_id: str = Field(min_length=1, max_length=200)
    source_document: SourceDocumentMetadata
    molecular_entities: list[HplcMolecularEntity] = Field(min_length=1)
    chromatography_system: ChromatographySystem
    method_parameters: MethodParameters
    provenance: RetrievalProvenance
    validation: RecordValidationState = Field(default_factory=RecordValidationState)
    notes: str | None = Field(default=None, min_length=1, max_length=1000)


class RetrievalQueryRequest(RetrievalBaseModel):
    target_smiles: str = Field(min_length=1, max_length=400)
    impurity_smiles: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RetrievalMatchedEntity(RetrievalBaseModel):
    local_identifier: str = Field(min_length=1, max_length=120)
    canonical_smiles: str = Field(min_length=1, max_length=400)
    score: float = Field(ge=0.0, le=1.0)


class RetrievalRecordReviewSummary(RetrievalBaseModel):
    record_state: ReviewRecordState
    review_record_id: str | None = Field(default=None, min_length=1, max_length=200)
    validation_status: ValidationStatus
    retrieval_ready: bool = False
    corpus_origin: CorpusOrigin = "seeded"


class RetrievalImpurityMatch(RetrievalBaseModel):
    query_canonical_smiles: str = Field(min_length=1, max_length=400)
    matched_entity_local_identifier: str = Field(min_length=1, max_length=120)
    matched_entity_display_name: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    score: float = Field(ge=0.0, le=1.0)


class RetrievalContextualPriors(RetrievalBaseModel):
    matrix_compatibility: float = Field(ge=0.0, le=1.0)
    detector_compatibility: float = Field(ge=0.0, le=1.0)
    method_family_compatibility: float = Field(ge=0.0, le=1.0)
    review_backed_prior: float = Field(ge=0.0, le=1.0)
    retrieval_ready_prior: float = Field(ge=0.0, le=1.0)


class RetrievalMatchRationale(RetrievalBaseModel):
    match_type: RetrievalMatchType
    matched_entity_local_identifier: str = Field(min_length=1, max_length=120)
    matched_entity_display_name: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    matched_entity_observed_retention_time_min: float | None = Field(
        default=None, ge=0.0, le=240.0
    )
    target_score: float = Field(ge=0.0, le=1.0)
    impurity_matches: list[RetrievalImpurityMatch] = Field(default_factory=list)
    aggregate_score: float = Field(ge=0.0, le=1.0)
    retrieval_score: float | None = Field(default=None, ge=0.0, le=1.0)
    contextual_priors: RetrievalContextualPriors | None = None
    supporting_snippet: EvidenceSnippet | None = None
    summary: str = Field(min_length=1, max_length=400)


class RetrievalQueryResult(RetrievalBaseModel):
    score: float = Field(ge=0.0, le=1.0)
    matched_entity: RetrievalMatchedEntity
    record: RetrievalMethodRecord
    match_rationale: RetrievalMatchRationale
    review_summary: RetrievalRecordReviewSummary | None = None


class RetrievalQueryResponse(RetrievalBaseModel):
    target_smiles: str = Field(min_length=1, max_length=400)
    target_canonical_smiles: str = Field(min_length=1, max_length=400)
    impurity_smiles: list[str] = Field(default_factory=list)
    ranking_mode: RankingMode
    results: list[RetrievalQueryResult] = Field(default_factory=list)
