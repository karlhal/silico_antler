from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .retrieval_schemas import (
    DocumentKind,
    EvidenceSnippet,
    RetrievalMatchRationale,
    RetrievalRecordReviewSummary,
    ValidationStatus,
)
from .hplc_extraction_schemas import MinimalHplcExtractionResponse
from .retrieval_schemas import RetrievalBaseModel, GradientPoint
from .compound_context_schemas import CompoundContext, ExternalEvidenceTrace

SourceMode = Literal["local_files", "local_corpus", "open_access"]
SourceModeInput = Literal["local", "local_files", "local_corpus", "open_access"]
FetchedSourceKind = Literal["pdf", "html"]
RecommendationTrustState = Literal[
    "review_backed",
    "seeded_corpus",
    "open_access_extracted",
    "local_file_extracted",
]
RecommendationRankingMode = Literal["target_only", "target_plus_impurities"]
ImpurityHandlingMode = Literal["not_requested", "active", "requested_but_untrusted"]
OpenAccessSkipStage = Literal["screening", "fetch", "extraction"]
RecommendationJobState = Literal["queued", "running", "completed", "failed"]
RecommendationJobStage = Literal[
    "queued",
    "query_papers",
    "extract_methods",
    "match_system",
    "scale_physics",
    "final_rank",
    "completed",
    "failed",
]
RecommendationRuntimeStatus = Literal[
    "completed",
    "completed_with_degraded_source",
    "completed_with_demo_fallback",
    "no_trustworthy_candidates",
    "upstream_unavailable",
    "request_invalid",
]
RecommendationResponseDetail = Literal["agent", "operator"]
RecommendationFailureClassification = Literal[
    "search_failure",
    "fetch_failure",
    "extraction_failure",
    "retrieval_store_unavailable",
    "llm_observer_unavailable",
    "timeout",
    "request_invalid",
]
RecommendationScreeningModel = Literal["deterministic", "llm_reranker"]
RecommendationQueryIntent = Literal[
    "exact_request",
    "analyte_matrix_anchor",
    "family_expansion",
    "matrix_relaxed_fallback",
    "context_repair",
    "user_supplied",
]


class SystemSpecs(RetrievalBaseModel):
    column_manufacturer: str | None = Field(default=None, min_length=1, max_length=120)
    column_name: str | None = Field(default=None, min_length=1, max_length=200)
    column_chemistry: str | None = Field(default=None, min_length=1, max_length=80)
    column_length_mm: float | None = Field(default=None, ge=10.0, le=300.0)
    column_inner_diameter_mm: float | None = Field(default=None, ge=1.0, le=4.6)
    particle_size_um: float | None = Field(default=None, ge=1.3, le=10.0)
    instrument_modes: list[str] = Field(default_factory=list)
    detector_types: list[str] = Field(default_factory=list)
    available_solvents: list[str] = Field(default_factory=list)
    max_pressure_bar: float | None = Field(default=None, ge=0.0, le=1500.0)


class MethodRecommendationRequest(RetrievalBaseModel):
    request_text: str = Field(min_length=1, max_length=2000)
    analyte_name: str | None = Field(default=None, min_length=1, max_length=200)
    target_smiles: str | None = Field(default=None, min_length=1, max_length=400)
    impurity_smiles: list[str] = Field(default_factory=list)
    matrix_hint: str | None = Field(default=None, min_length=1, max_length=200)
    system_specs: SystemSpecs | None = Field(default=None)
    preferred_mode: Literal["rp_lc", "hilic"] | None = None
    max_run_time_min: float | None = Field(default=None, gt=0.0, le=240.0)
    require_mass_spectrometry: bool = False
    source_mode: SourceMode = "local_files"
    local_paths: list[str] = Field(default_factory=list)
    search_query: str | None = Field(default=None, min_length=1, max_length=500)
    max_papers: int = Field(default=8, ge=1, le=20)

    @field_validator("source_mode", mode="before")
    @classmethod
    def normalize_source_mode(cls, value: str | None) -> SourceMode:
        if value is None:
            return "local_files"
        normalized = str(value).strip()
        if normalized == "local":
            return "local_files"
        if normalized in {"local_files", "local_corpus", "open_access"}:
            return normalized
        raise ValueError(
            "source_mode must be one of 'local', 'local_files', 'local_corpus', or 'open_access'"
        )

    @model_validator(mode="after")
    def validate_mode_specific_requirements(self) -> "MethodRecommendationRequest":
        if self.source_mode == "local_corpus" and not self.target_smiles:
            raise ValueError(
                "target_smiles is required when source_mode is 'local_corpus'"
            )
        return self


class RecommendationQueryVariant(RetrievalBaseModel):
    variant_id: str = Field(min_length=1, max_length=80)
    intent: RecommendationQueryIntent
    query_text: str = Field(min_length=1, max_length=500)


class OpenAccessPaperCandidate(RetrievalBaseModel):
    paper_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=1000)
    doi: str | None = Field(default=None, min_length=1, max_length=300)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    pdf_url: str | None = Field(default=None, min_length=1, max_length=2000)
    alternate_urls: list[str] = Field(default_factory=list)
    alternate_pdf_urls: list[str] = Field(default_factory=list)
    published_year: int | None = Field(default=None, ge=1900, le=2100)
    source_name: str | None = Field(default=None, min_length=1, max_length=300)
    abstract: str | None = Field(default=None, min_length=1, max_length=10000)
    open_access: bool = True
    query_provenance: list[RecommendationQueryVariant] = Field(default_factory=list)

    @field_validator("abstract", mode="before")
    @classmethod
    def validate_abstract_bounds(cls, value: object) -> str | None:
        from .retrieval_schemas import coerce_bounded_text
        return coerce_bounded_text(value, max_length=10000, allow_none=True)


class FetchedSourceArtifact(RetrievalBaseModel):
    paper_id: str = Field(min_length=1, max_length=500)
    kind: FetchedSourceKind
    title: str | None = Field(default=None, min_length=1, max_length=1000)
    abstract: str | None = Field(default=None, min_length=1, max_length=10000)
    doi: str | None = Field(default=None, min_length=1, max_length=300)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    published_year: int | None = Field(default=None, ge=1900, le=2100)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
    html_content: str | None = Field(default=None, min_length=1)
    pdf_bytes: bytes | None = None


class RecommendationScoreBreakdown(RetrievalBaseModel):
    total_score: float = Field(ge=0.0, le=1.0)
    system_match: float = Field(ge=0.0, le=1.0)
    analyte_match: float = Field(ge=0.0, le=1.0)
    matrix_fit: float = Field(ge=0.0, le=1.0)
    practical_fit: float = Field(ge=0.0, le=1.0)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    literature_relevance: float = Field(ge=0.0, le=1.0)
    features: "RecommendationFeatureBreakdown"


class RecommendationFeatureBreakdown(RetrievalBaseModel):
    target_chemistry_fit: float = Field(ge=0.0, le=1.0)
    impurity_compatibility: float = Field(ge=0.0, le=1.0)
    system_fit: float = Field(ge=0.0, le=1.0)
    detector_compatibility: float = Field(ge=0.0, le=1.0)
    matrix_fit: float = Field(ge=0.0, le=1.0)
    runtime_fit: float = Field(ge=0.0, le=1.0)
    extraction_completeness: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    review_trust_prior: float = Field(ge=0.0, le=1.0)
    literature_specificity: float = Field(ge=0.0, le=1.0)
    missing_data_penalty: float = Field(ge=0.0, le=1.0)


class RecommendationScoreLayers(RetrievalBaseModel):
    retrieval_relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    method_viability: float = Field(ge=0.0, le=1.0)
    final_fit: float = Field(ge=0.0, le=1.0)
    retrieval_relevance_summary: str = Field(min_length=1, max_length=300)
    method_viability_summary: str = Field(min_length=1, max_length=300)
    final_fit_summary: str = Field(min_length=1, max_length=300)


class RecommendationDecisionTrace(RetrievalBaseModel):
    retrieval_score: float | None = Field(default=None, ge=0.0, le=1.0)
    viability_score: float = Field(ge=0.0, le=1.0)
    ranking_score: float = Field(ge=0.0, le=1.0)
    score_layers: RecommendationScoreLayers | None = None
    screening_model: RecommendationScreeningModel | None = None
    screening_summary: str | None = Field(default=None, min_length=1, max_length=600)
    screening_reasons: list[str] = Field(default_factory=list)
    query_provenance: list[RecommendationQueryVariant] = Field(default_factory=list)
    dominant_differentiator: str | None = Field(
        default=None, min_length=1, max_length=400
    )
    beat_runner_up_summary: str | None = Field(
        default=None, min_length=1, max_length=600
    )


class RecommendedMethod(RetrievalBaseModel):
    is_scaled: bool = False
    flow_rate_ml_min: float | None = None
    injection_volume_ul: float | None = None
    gradient_profile: list[GradientPoint] = Field(default_factory=list)
    run_time_min: float | None = None
    scaling_notes: list[str] = Field(default_factory=list)
    scaling_warnings: list[str] = Field(default_factory=list)


class RecommendationIssueCounts(RetrievalBaseModel):
    info: int = Field(default=0, ge=0)
    warning: int = Field(default=0, ge=0)
    error: int = Field(default=0, ge=0)


class RecommendationTrust(RetrievalBaseModel):
    trust_state: RecommendationTrustState
    validation_status: ValidationStatus
    retrieval_ready: bool = False
    manual_verification_required: bool = True
    issue_counts: RecommendationIssueCounts = Field(
        default_factory=RecommendationIssueCounts
    )
    warning_summary: list[str] = Field(default_factory=list)


class RecommendationRankingContext(RetrievalBaseModel):
    ranking_mode: RecommendationRankingMode
    impurity_handling: ImpurityHandlingMode
    impurity_count: int = Field(default=0, ge=0)
    summary: str = Field(min_length=1, max_length=600)


class RecommendationSkippedPaper(RetrievalBaseModel):
    paper_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=1000)
    stage: OpenAccessSkipStage
    reason: str = Field(min_length=1, max_length=1200)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    query_provenance: list[RecommendationQueryVariant] = Field(default_factory=list)


class RecommendationCandidate(RetrievalBaseModel):
    paper_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=1000)
    doi: str | None = Field(default=None, min_length=1, max_length=300)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    published_year: int | None = Field(default=None, ge=1900, le=2100)
    source_kind: DocumentKind
    score: RecommendationScoreBreakdown
    rationale: str = Field(min_length=1, max_length=1500)
    extraction: MinimalHplcExtractionResponse
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)
    trust: RecommendationTrust
    ranking_context: RecommendationRankingContext
    match_rationale: RetrievalMatchRationale | None = None
    review_summary: RetrievalRecordReviewSummary | None = None
    decision_trace: RecommendationDecisionTrace | None = None
    recommended_method: RecommendedMethod | None = None
    citation: str = Field(min_length=1, max_length=2000)


class RecommendationSearchPlan(RetrievalBaseModel):
    request_specificity: Literal["specific", "mixed", "broad"]
    exploration_mode: Literal[
        "narrow_confirmation", "balanced_validation", "broad_exploration"
    ]
    query_count: int = Field(ge=1, le=10)
    search_budget: int = Field(ge=1, le=40)
    rationale: str = Field(min_length=1, max_length=400)
    queries: list[RecommendationQueryVariant] = Field(default_factory=list)


class RecommendationRuntimeBudget(RetrievalBaseModel):
    max_papers_requested: int = Field(ge=1, le=200)
    search_budget_used: int | None = Field(default=None, ge=1, le=200)
    queries_attempted: int = Field(default=0, ge=0, le=10)
    shortlist_size: int | None = Field(default=None, ge=1, le=200)
    fetch_concurrency: int | None = Field(default=None, ge=1, le=32)
    extraction_concurrency: int | None = Field(default=None, ge=1, le=32)
    target_viable_candidates: int | None = Field(default=None, ge=1, le=50)
    stop_condition: str | None = Field(default=None, min_length=1, max_length=200)
    open_access_timeout_sec: int | None = Field(default=None, ge=1, le=120)
    llm_observer_enabled: bool = False
    rate_limit_policy: str = Field(min_length=1, max_length=60)
    search_plan: RecommendationSearchPlan | None = None


class RecommendationStageTelemetry(RetrievalBaseModel):
    stage: RecommendationJobStage
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    llm_calls: int = Field(default=0, ge=0)
    llm_prompt_tokens: int = Field(default=0, ge=0)
    llm_completion_tokens: int = Field(default=0, ge=0)
    evidence_unit_count: int = Field(default=0, ge=0)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)


class RecommendationCacheTelemetry(RetrievalBaseModel):
    artifact_hits: int = Field(default=0, ge=0)
    artifact_misses: int = Field(default=0, ge=0)
    evidence_unit_hits: int = Field(default=0, ge=0)
    evidence_unit_misses: int = Field(default=0, ge=0)
    extraction_hits: int = Field(default=0, ge=0)
    extraction_misses: int = Field(default=0, ge=0)
    vetted_snippet_hits: int = Field(default=0, ge=0)
    vetted_snippet_misses: int = Field(default=0, ge=0)


class RecommendationPayloadTelemetry(RetrievalBaseModel):
    response_detail: RecommendationResponseDetail
    response_bytes: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    evidence_preview_count: int = Field(ge=0)


class RecommendationRuntimeTelemetry(RetrievalBaseModel):
    llm_prompt_tokens: int = Field(default=0, ge=0)
    llm_completion_tokens: int = Field(default=0, ge=0)
    evidence_unit_count: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    cache: RecommendationCacheTelemetry = Field(
        default_factory=RecommendationCacheTelemetry
    )
    stages: list[RecommendationStageTelemetry] = Field(default_factory=list)
    payload: RecommendationPayloadTelemetry | None = None


class RecommendationRuntimeSummary(RetrievalBaseModel):
    request_id: str = Field(min_length=1, max_length=120)
    status: RecommendationRuntimeStatus
    summary: str = Field(min_length=1, max_length=1000)
    degraded: bool = False
    failure_classification: RecommendationFailureClassification | None = None
    budget: RecommendationRuntimeBudget
    branch_decisions: list[str] = Field(default_factory=list)
    telemetry: RecommendationRuntimeTelemetry | None = None


class RecommendationErrorDetail(RetrievalBaseModel):
    request_id: str = Field(min_length=1, max_length=120)
    runtime_status: RecommendationRuntimeStatus
    failure_classification: RecommendationFailureClassification
    failure_stage: RecommendationJobStage | None = None
    message: str = Field(min_length=1, max_length=1000)
    retryable: bool = False


class RecommendationDiscoverySummary(RetrievalBaseModel):
    discovered_paper_count: int = Field(default=0, ge=0)
    skipped_paper_count: int = Field(default=0, ge=0)
    skipped_papers_truncated: bool = False
    skipped_papers_preview: list[RecommendationSkippedPaper] = Field(
        default_factory=list
    )
    considered_candidate_count: int = Field(default=0, ge=0)
    considered_candidates_truncated: bool = False
    repeated_extraction_exception_count: int = Field(default=0, ge=0)


class MethodRecommendationReport(RetrievalBaseModel):
    request: MethodRecommendationRequest | None = None
    source_mode: SourceMode
    search_query_used: str | None = Field(default=None, min_length=1, max_length=500)
    target_compound_context: CompoundContext | None = None
    impurity_compound_contexts: list[CompoundContext] = Field(default_factory=list)
    external_evidence_trace: ExternalEvidenceTrace | None = None
    discovered_papers: list[OpenAccessPaperCandidate] = Field(default_factory=list)
    skipped_papers: list[RecommendationSkippedPaper] = Field(default_factory=list)
    discovery_summary: RecommendationDiscoverySummary | None = None
    considered_candidates: list[RecommendationCandidate] = Field(default_factory=list)
    recommended_candidate: RecommendationCandidate | None = None
    runtime: RecommendationRuntimeSummary | None = None


class RecommendationJobAccepted(RetrievalBaseModel):
    job_id: str = Field(min_length=1, max_length=120)
    state: RecommendationJobState = "queued"
    stage: RecommendationJobStage = "queued"
    status_url: str = Field(min_length=1, max_length=500)


class RecommendationJobStatus(RetrievalBaseModel):
    job_id: str = Field(min_length=1, max_length=120)
    state: RecommendationJobState
    stage: RecommendationJobStage
    message: str = Field(min_length=1, max_length=1000)
    created_at: datetime
    updated_at: datetime
    source_mode: SourceMode
    items_completed: int = Field(default=0, ge=0)
    items_total: int | None = Field(default=None, ge=0)
    report: MethodRecommendationReport | None = None
    runtime: RecommendationRuntimeSummary | None = None
    error_detail: RecommendationErrorDetail | None = None
    error_message: str | None = Field(default=None, min_length=1, max_length=1000)


RecommendedMethod.model_rebuild()
RecommendationCandidate.model_rebuild()
MethodRecommendationReport.model_rebuild()
RecommendationJobStatus.model_rebuild()
