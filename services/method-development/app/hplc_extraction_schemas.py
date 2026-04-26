from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .retrieval_schemas import (
    ChromatographySystem,
    EvidenceSnippet,
    GradientPoint,
    MethodParameters,
    MobilePhase,
    RecordValidationState,
    RetrievalBaseModel,
    RetrievalProvenance,
    SourceDocumentMetadata,
    coerce_bounded_text,
)

MobilePhaseCandidateKind = Literal["full_system", "replacement_note"]
MobilePhaseDetailTarget = Literal["mobile_phase_a", "mobile_phase_b", "unspecified"]
MobilePhaseDetailCandidateKind = Literal["phase_detail_statement"]
GradientCandidateKind = Literal["text_statement", "table_derived"]
ChromatographySystemCandidateKind = Literal["text_match"]
TimingCandidateKind = Literal["run_time_statement", "gradient_derived"]
AnchoredEntityCandidateKind = Literal["retention_sentence"]
SmilesLinkageStatus = Literal[
    "unresolved_local_identifier",
    "unresolved_named_entity",
    "placeholder_generated",
]
MobilePhaseCandidateRole = Literal[
    "final",
    "comparison",
    "trial",
    "rejected",
    "ambiguous",
]


class ExtractedFieldEvidence(RetrievalBaseModel):
    field_path: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    snippet: EvidenceSnippet


class ExtractedRetentionTimeObservation(RetrievalBaseModel):
    local_identifier: str | None = Field(default=None, min_length=1, max_length=120)
    observed_retention_time_min: float = Field(ge=0.0, le=240.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    candidate_role: MobilePhaseCandidateRole = "ambiguous"
    selected_for_record_draft: bool = False
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)


class ExtractedMobilePhaseCandidate(RetrievalBaseModel):
    candidate_kind: MobilePhaseCandidateKind
    candidate_role: MobilePhaseCandidateRole
    statement_text: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    selected_for_method_parameters: bool = False
    mobile_phase_a: MobilePhase | None = None
    mobile_phase_b: MobilePhase | None = None
    comparison_from_text: str | None = Field(default=None, min_length=1, max_length=200)
    comparison_to_text: str | None = Field(default=None, min_length=1, max_length=200)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)

    @field_validator("statement_text", mode="before")
    @classmethod
    def validate_statement_text_bounds(cls, value: object) -> str:
        return str(coerce_bounded_text(value, max_length=2000))


class ExtractedMobilePhaseDetailCandidate(RetrievalBaseModel):
    candidate_kind: MobilePhaseDetailCandidateKind
    candidate_role: MobilePhaseCandidateRole
    target_phase: MobilePhaseDetailTarget
    statement_text: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    selected_for_method_parameters: bool = False
    additive: str | None = Field(default=None, min_length=1, max_length=120)
    ph_estimate: float | None = Field(default=None, ge=0.0, le=14.0)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)

    @field_validator("statement_text", mode="before")
    @classmethod
    def validate_statement_text_bounds(cls, value: object) -> str:
        return str(coerce_bounded_text(value, max_length=2000))


class ExtractedChromatographySystemCandidate(RetrievalBaseModel):
    candidate_kind: ChromatographySystemCandidateKind
    candidate_role: MobilePhaseCandidateRole
    statement_text: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    selected_for_output: bool = False
    chromatography_system: ChromatographySystem | None = None
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)

    @field_validator("statement_text", mode="before")
    @classmethod
    def validate_statement_text_bounds(cls, value: object) -> str:
        return str(coerce_bounded_text(value, max_length=2000))


class ExtractedGradientCandidate(RetrievalBaseModel):
    candidate_kind: GradientCandidateKind
    candidate_role: MobilePhaseCandidateRole
    statement_text: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)
    selected_for_method_parameters: bool = False
    gradient_profile: list[GradientPoint] = Field(default_factory=list)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)

    @field_validator("statement_text", mode="before")
    @classmethod
    def validate_statement_text_bounds(cls, value: object) -> str:
        return str(coerce_bounded_text(value, max_length=4000))


class ExtractedTimingCandidate(RetrievalBaseModel):
    candidate_kind: TimingCandidateKind
    candidate_role: MobilePhaseCandidateRole
    statement_text: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    selected_for_method_parameters: bool = False
    run_time_min: float | None = Field(default=None, gt=0.0, le=240.0)
    reequilibration_time_min: float | None = Field(default=None, gt=0.0, le=120.0)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)

    @field_validator("statement_text", mode="before")
    @classmethod
    def validate_statement_text_bounds(cls, value: object) -> str:
        return str(coerce_bounded_text(value, max_length=2000))


class RetrievalRecordDraft(RetrievalBaseModel):
    record_id: str = Field(min_length=1, max_length=200)
    source_document: SourceDocumentMetadata
    chromatography_system: ChromatographySystem
    method_parameters: MethodParameters
    provenance: RetrievalProvenance
    validation: RecordValidationState = Field(default_factory=RecordValidationState)
    anchored_entities: list["AnchoredEntityCandidate"] = Field(default_factory=list)
    molecular_entity_drafts: list["HplcMolecularEntityDraft"] = Field(
        default_factory=list
    )
    selected_retention_time_observations: list[ExtractedRetentionTimeObservation] = (
        Field(default_factory=list)
    )
    unresolved_requirements: list[str] = Field(default_factory=list)
    ready_for_record_assembly: bool = False


class AnchoredEntityCandidate(RetrievalBaseModel):
    candidate_kind: AnchoredEntityCandidateKind
    candidate_role: MobilePhaseCandidateRole
    alias_group_key: str = Field(min_length=1, max_length=120)
    local_identifier: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    observed_retention_time_min: float | None = Field(default=None, ge=0.0, le=240.0)
    confidence: float = Field(ge=0.0, le=1.0)
    selected_for_record_draft: bool = False
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)


class HplcMolecularEntityDraft(RetrievalBaseModel):
    local_identifier: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    linkage_lookup_keys: list[str] = Field(default_factory=list)
    linkage_notes: list[str] = Field(default_factory=list)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    observed_retention_time_min: float | None = Field(default=None, ge=0.0, le=240.0)
    smiles_string: str | None = Field(default=None, min_length=1, max_length=400)
    placeholder_smiles_string: str | None = Field(
        default=None, min_length=1, max_length=400
    )
    smiles_linkage_status: SmilesLinkageStatus
    confidence: float = Field(ge=0.0, le=1.0)
    selected_for_record_draft: bool = False
    ready_for_retrieval_entity: bool = False
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)


class MinimalHplcExtractionResponse(RetrievalBaseModel):
    source_document: SourceDocumentMetadata
    chromatography_system: ChromatographySystem | None = None
    method_parameters: MethodParameters | None = None
    chromatography_system_candidates: list[ExtractedChromatographySystemCandidate] = (
        Field(default_factory=list)
    )
    mobile_phase_candidates: list[ExtractedMobilePhaseCandidate] = Field(
        default_factory=list
    )
    mobile_phase_detail_candidates: list[ExtractedMobilePhaseDetailCandidate] = Field(
        default_factory=list
    )
    gradient_candidates: list[ExtractedGradientCandidate] = Field(default_factory=list)
    timing_candidates: list[ExtractedTimingCandidate] = Field(default_factory=list)
    retention_time_observations: list[ExtractedRetentionTimeObservation] = Field(
        default_factory=list
    )
    anchored_entity_candidates: list[AnchoredEntityCandidate] = Field(
        default_factory=list
    )
    molecular_entity_drafts: list[HplcMolecularEntityDraft] = Field(
        default_factory=list
    )
    provenance: RetrievalProvenance
    field_evidence: list[ExtractedFieldEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    record_draft: RetrievalRecordDraft | None = None
    retrieval_record_ready: bool = False
