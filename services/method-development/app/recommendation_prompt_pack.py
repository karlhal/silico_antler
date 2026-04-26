from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal, TypeVar

from pydantic import Field, ValidationError, field_validator, model_validator

from .retrieval_schemas import RetrievalBaseModel, coerce_bounded_text

PromptQueryIntent = Literal[
    "exact_title",
    "strict_method",
    "family_expansion",
    "matrix_relaxed",
    "repair",
]
PromptChromatographyMode = Literal["rp_lc", "hilic"] | None
PromptIonizationMode = Literal["ESI", "APCI", "APPI"] | None
PromptPolarity = Literal["positive", "negative", "both"] | None
PromptEntityRole = Literal["target", "impurity", "unknown"]
PromptFieldGroup = Literal[
    "chromatography_system",
    "mobile_phase_gradient",
    "detector_ionization",
    "target_impurity_linkage",
]

T = TypeVar("T", bound=RetrievalBaseModel)


@dataclass(frozen=True)
class RenderedPrompt:
    system_prompt: str
    user_prompt: str


class QueryPlannerQuery(RetrievalBaseModel):
    query: str = Field(min_length=1, max_length=500)
    intent: PromptQueryIntent
    why: str = Field(min_length=1, max_length=300)

    @field_validator("query", mode="before")
    @classmethod
    def _validate_query(cls, value: object) -> str:
        normalized = coerce_bounded_text(value, max_length=500)
        return normalized or ""

    @field_validator("why", mode="before")
    @classmethod
    def _validate_why(cls, value: object) -> str:
        normalized = coerce_bounded_text(value, max_length=300)
        return normalized or ""


class QueryPlannerResponse(RetrievalBaseModel):
    query_count: int = Field(ge=3, le=5)
    queries: list[QueryPlannerQuery] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def _validate_queries(self) -> "QueryPlannerResponse":
        if self.query_count != len(self.queries):
            raise ValueError("query_count must equal the number of queries")
        intents = [item.intent for item in self.queries]
        if len(intents) != len(set(intents)):
            raise ValueError("query intents must be distinct")
        texts = [item.query.casefold() for item in self.queries]
        if len(texts) != len(set(texts)):
            raise ValueError("queries must be distinct")
        return self


class CandidateRerankItem(RetrievalBaseModel):
    paper_id: str = Field(min_length=1, max_length=500)
    shortlist_score: float = Field(ge=0.0, le=1.0)
    final_method_confidence: float = Field(ge=0.0, le=1.0)
    matrix_match_confidence: float = Field(ge=0.0, le=1.0)
    keep: bool
    reason: str = Field(min_length=1, max_length=600)

    @field_validator("reason", mode="before")
    @classmethod
    def _validate_reason(cls, value: object) -> str:
        normalized = coerce_bounded_text(value, max_length=600)
        return normalized or ""


class CandidateRerankResponse(RetrievalBaseModel):
    ranked_candidates: list[CandidateRerankItem] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_unique_papers(self) -> "CandidateRerankResponse":
        paper_ids = [item.paper_id for item in self.ranked_candidates]
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("ranked candidate paper_ids must be unique")
        return self


class MethodEvidenceSniffResponse(RetrievalBaseModel):
    contains_extractable_final_method: bool
    confidence: float = Field(ge=0.0, le=1.0)
    best_evidence_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    reason: str = Field(min_length=1, max_length=600)

    @field_validator("reason", mode="before")
    @classmethod
    def _validate_reason(cls, value: object) -> str:
        normalized = coerce_bounded_text(value, max_length=600)
        return normalized or ""


class PromptMobilePhase(RetrievalBaseModel):
    solvent: str | None = Field(default=None, min_length=1, max_length=500)
    additive: str | None = Field(default=None, min_length=1, max_length=500)
    ph_estimate: float | None = Field(default=None, ge=0.0, le=14.0)

    @field_validator("solvent", "additive", mode="before")
    @classmethod
    def _validate_text(cls, value: object) -> str | None:
        return coerce_bounded_text(value, max_length=500, allow_none=True)


class ChromatographySystemExtractionResponse(RetrievalBaseModel):
    mode: PromptChromatographyMode = None
    column_manufacturer: str | None = Field(default=None, min_length=1, max_length=120)
    column_name: str | None = Field(default=None, min_length=1, max_length=200)
    stationary_phase_chemistry: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
    )
    column_length_mm: float | None = Field(default=None, ge=0.0, le=300.0)
    column_inner_diameter_mm: float | None = Field(default=None, ge=0.0, le=10.0)
    particle_size_um: float | None = Field(default=None, ge=0.0, le=20.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("column_manufacturer", mode="before")
    @classmethod
    def _validate_column_manufacturer(cls, value: object) -> str | None:
        return coerce_bounded_text(value, max_length=120, allow_none=True)

    @field_validator("column_name", mode="before")
    @classmethod
    def _validate_column_name(cls, value: object) -> str | None:
        return coerce_bounded_text(value, max_length=200, allow_none=True)

    @field_validator("stationary_phase_chemistry", mode="before")
    @classmethod
    def _validate_stationary_phase_chemistry(cls, value: object) -> str | None:
        return coerce_bounded_text(value, max_length=80, allow_none=True)


class GradientPointExtractionResponse(RetrievalBaseModel):
    time_min: float = Field(ge=0.0, le=240.0)
    percent_b: float = Field(ge=0.0, le=100.0)


class MobilePhaseGradientExtractionResponse(RetrievalBaseModel):
    mobile_phase_a: PromptMobilePhase | None = None
    mobile_phase_b: PromptMobilePhase | None = None
    flow_rate_ml_min: float | None = Field(default=None, ge=0.0, le=10.0)
    run_time_min: float | None = Field(default=None, ge=0.0, le=240.0)
    column_temperature_c: float | None = Field(default=None, ge=0.0, le=120.0)
    gradient_profile: list[GradientPointExtractionResponse] = Field(default_factory=list)
    isocratic_percent_b: float | None = Field(default=None, ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class DetectorIonizationExtractionResponse(RetrievalBaseModel):
    detector_type: str | None = Field(default=None, min_length=1, max_length=200)
    mass_spectrometry_present: bool
    ionization_mode: PromptIonizationMode = None
    polarity: PromptPolarity = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("detector_type", mode="before")
    @classmethod
    def _validate_detector_type(cls, value: object) -> str | None:
        return coerce_bounded_text(value, max_length=200, allow_none=True)


class LinkedEntityExtractionItem(RetrievalBaseModel):
    local_identifier: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: PromptEntityRole
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_unit_ids: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("local_identifier", "display_name", mode="before")
    @classmethod
    def _validate_text(cls, value: object) -> str | None:
        allow_none = value is None
        return coerce_bounded_text(value, max_length=200, allow_none=allow_none)


class TargetImpurityLinkageExtractionResponse(RetrievalBaseModel):
    linked_entities: list[LinkedEntityExtractionItem] = Field(
        default_factory=list,
        max_length=40,
    )
    warnings: list[str] = Field(default_factory=list, max_length=8)


QUERY_PLANNER_SYSTEM_PROMPT = """You generate high-precision literature search queries for analytical chemistry method discovery.

Your job is to create a small set of search queries for open-access paper discovery.

The user is looking for a final usable chromatographic method, not a broad review, not a composition paper, and not a general chemistry overview.

Priorities:
1. final validated or directly usable analytical methods
2. the correct analyte or analyte family
3. the correct matrix context
4. the correct detector or method mode when specified

Hard rules:
- Return JSON only.
- Do not return more than 5 queries.
- Queries must be concise and high signal.
- At least one query must be strict and method-oriented.
- At least one query may relax matrix or family wording to preserve recall.
- Avoid generic filler like "study", "paper", "analysis" unless it improves precision.
- Prefer "LC-MS/MS", "HPLC", "quantification", "validated", "bioanalytical", and matrix-specific language when appropriate.
- Do not invent analytes that are not plausible expansions of the provided analyte family.
- If the input request already looks like a literature title, preserve one near-exact title-style query."""

QUERY_PLANNER_USER_TEMPLATE = """Generate a query plan for this recommendation request.

Request text:
{request_text}

Analyte name:
{analyte_name}

Target smiles present:
{target_smiles_present}

Impurity smiles count:
{impurity_count}

Matrix hint:
{matrix_hint}

Preferred mode:
{preferred_mode}

Mass spectrometry required:
{require_mass_spectrometry}

Return exactly 3 to 5 queries with distinct retrieval intent."""

CANDIDATE_RERANKER_SYSTEM_PROMPT = """You are screening scientific papers for whether they are likely to contain a final usable chromatographic method.

You are not choosing the final recommendation. You are only deciding which papers are worth fetching and extracting.

Treat these as strong positive signals:
- validated analytical method
- quantification assay
- simultaneous determination with concrete analytes
- explicit LC-MS/MS, HPLC, UHPLC, MRM, triple quadrupole, or column and mobile phase language
- the correct matrix context

Treat these as strong negative signals:
- review articles
- editorials
- corrigenda
- broad chemistry or composition studies
- plant, food, pigment, or extract papers when the request is for a clinical matrix
- papers that mention the analyte family but do not look like final-method literature

Hard rules:
- Return JSON only.
- Score from 0.0 to 1.0.
- `keep` must be false for obvious reviews, editorials, and non-method literature.
- Prefer precision over recall when the request is clinically specific.
- Do not use knowledge outside the provided request and candidate metadata."""

CANDIDATE_RERANKER_USER_TEMPLATE = """Screen and rerank these paper candidates for method discovery.

Request:
{request_text}

Analyte:
{analyte_name}

Matrix:
{matrix_hint}

Preferred mode:
{preferred_mode}

Mass spectrometry required:
{require_mass_spectrometry}

Candidates:
{json_candidates}

Return every candidate in ranked order."""

METHOD_SNIFF_SYSTEM_PROMPT = """You are deciding whether a fetched scientific document is likely to contain enough method detail for full chromatographic extraction.

You are not extracting the full method yet.

Positive evidence:
- explicit column or stationary phase
- mobile phase solvents or additives
- gradient or runtime details
- detector or ionization details
- a validated assay or quantification method in the requested context

Negative evidence:
- composition-only results
- biological findings without analytical method details
- broad review or discussion text
- methods mentioned only generically with no final parameters

Hard rules:
- Return JSON only.
- Base the decision only on the provided evidence units.
- If confidence is below 0.45, set `contains_extractable_final_method` to false.
- Cite the best evidence unit ids instead of quoting long text."""

METHOD_SNIFF_USER_TEMPLATE = """Assess whether this paper contains an extractable final chromatographic method.

Request:
{request_text}

Analyte:
{analyte_name}

Matrix:
{matrix_hint}

Mass spectrometry required:
{require_mass_spectrometry}

Evidence units:
{json_evidence_units}"""

CHROMATOGRAPHY_SYSTEM_SYSTEM_PROMPT = """You extract chromatography system details from evidence units.

Rules:
- Return JSON only.
- Extract only what is directly supported.
- Use null when unsupported.
- Do not infer exact numbers from vague wording.
- Prefer final method parameters over exploratory or discarded conditions."""

CHROMATOGRAPHY_SYSTEM_USER_TEMPLATE = """Extract the chromatography system for the final method only.

Request:
{request_text}

Evidence units:
{json_evidence_units}"""

MOBILE_PHASE_GRADIENT_SYSTEM_PROMPT = """You extract final mobile phase, gradient, and runtime details for a chromatographic method.

Rules:
- Return JSON only.
- Prefer explicit final conditions.
- If both isocratic and gradient language appear, choose the condition best supported as the final analytical method and mention ambiguity in warnings.
- Do not fabricate gradient points.
- Use null or empty arrays when unsupported."""

MOBILE_PHASE_GRADIENT_USER_TEMPLATE = """Extract the final mobile phase, gradient, flow rate, runtime, and temperature details.

Request:
{request_text}

Evidence units:
{json_evidence_units}"""

DETECTOR_IONIZATION_SYSTEM_PROMPT = """You extract detector and ionization details for the final analytical method.

Rules:
- Return JSON only.
- Prefer explicit detector wording over inference.
- If mass spectrometry is not clearly present, set `mass_spectrometry_present` to false.
- Do not infer polarity from analyte chemistry."""

DETECTOR_IONIZATION_USER_TEMPLATE = """Extract detector and ionization details for the final analytical method.

Request:
{request_text}

Evidence units:
{json_evidence_units}"""

TARGET_IMPURITY_LINKAGE_SYSTEM_PROMPT = """You identify which named entities in the paper correspond to the request target and optional impurities.

Rules:
- Return JSON only.
- Use `target`, `impurity`, or `unknown` only.
- Do not overclaim entity linkage when the paper only discusses a broad analyte family.
- If a paper does not clearly link to the requested impurity set, keep the role as `unknown`."""

TARGET_IMPURITY_LINKAGE_USER_TEMPLATE = """Link named analyte entities from the paper to the request target and optional impurities.

Request:
{request_text}

Analyte:
{analyte_name}

Target smiles present:
{target_smiles_present}

Impurity smiles count:
{impurity_count}

Evidence units:
{json_evidence_units}"""

FIELD_EXTRACTION_RESPONSE_MODELS: dict[PromptFieldGroup, type[RetrievalBaseModel]] = {
    "chromatography_system": ChromatographySystemExtractionResponse,
    "mobile_phase_gradient": MobilePhaseGradientExtractionResponse,
    "detector_ionization": DetectorIonizationExtractionResponse,
    "target_impurity_linkage": TargetImpurityLinkageExtractionResponse,
}

RESPONSE_SCHEMAS: dict[str, dict] = {
    "query_planner": QueryPlannerResponse.model_json_schema(),
    "candidate_reranker": CandidateRerankResponse.model_json_schema(),
    "method_evidence_sniff": MethodEvidenceSniffResponse.model_json_schema(),
    "chromatography_system": ChromatographySystemExtractionResponse.model_json_schema(),
    "mobile_phase_gradient": MobilePhaseGradientExtractionResponse.model_json_schema(),
    "detector_ionization": DetectorIonizationExtractionResponse.model_json_schema(),
    "target_impurity_linkage": TargetImpurityLinkageExtractionResponse.model_json_schema(),
}


def build_query_planner_prompt(
    *,
    request_text: str,
    analyte_name: str | None,
    target_smiles_present: bool,
    impurity_count: int,
    matrix_hint: str | None,
    preferred_mode: str | None,
    require_mass_spectrometry: bool,
) -> RenderedPrompt:
    return RenderedPrompt(
        system_prompt=QUERY_PLANNER_SYSTEM_PROMPT,
        user_prompt=QUERY_PLANNER_USER_TEMPLATE.format(
            request_text=request_text.strip(),
            analyte_name=_render_optional_text(analyte_name),
            target_smiles_present=_render_bool(target_smiles_present),
            impurity_count=max(0, impurity_count),
            matrix_hint=_render_optional_text(matrix_hint),
            preferred_mode=_render_optional_text(preferred_mode),
            require_mass_spectrometry=_render_bool(require_mass_spectrometry),
        ),
    )


def build_candidate_reranker_prompt(
    *,
    request_text: str,
    analyte_name: str | None,
    matrix_hint: str | None,
    preferred_mode: str | None,
    require_mass_spectrometry: bool,
    candidates: list[dict[str, object]],
) -> RenderedPrompt:
    return RenderedPrompt(
        system_prompt=CANDIDATE_RERANKER_SYSTEM_PROMPT,
        user_prompt=CANDIDATE_RERANKER_USER_TEMPLATE.format(
            request_text=request_text.strip(),
            analyte_name=_render_optional_text(analyte_name),
            matrix_hint=_render_optional_text(matrix_hint),
            preferred_mode=_render_optional_text(preferred_mode),
            require_mass_spectrometry=_render_bool(require_mass_spectrometry),
            json_candidates=_render_json(candidates),
        ),
    )


def build_method_evidence_sniff_prompt(
    *,
    request_text: str,
    analyte_name: str | None,
    matrix_hint: str | None,
    require_mass_spectrometry: bool,
    evidence_units: list[dict[str, object]],
) -> RenderedPrompt:
    return RenderedPrompt(
        system_prompt=METHOD_SNIFF_SYSTEM_PROMPT,
        user_prompt=METHOD_SNIFF_USER_TEMPLATE.format(
            request_text=request_text.strip(),
            analyte_name=_render_optional_text(analyte_name),
            matrix_hint=_render_optional_text(matrix_hint),
            require_mass_spectrometry=_render_bool(require_mass_spectrometry),
            json_evidence_units=_render_json(evidence_units),
        ),
    )


def build_field_extraction_prompt(
    *,
    field_group: PromptFieldGroup,
    request_text: str,
    evidence_units: list[dict[str, object]],
    analyte_name: str | None = None,
    target_smiles_present: bool = False,
    impurity_count: int = 0,
) -> RenderedPrompt:
    if field_group == "chromatography_system":
        return RenderedPrompt(
            system_prompt=CHROMATOGRAPHY_SYSTEM_SYSTEM_PROMPT,
            user_prompt=CHROMATOGRAPHY_SYSTEM_USER_TEMPLATE.format(
                request_text=request_text.strip(),
                json_evidence_units=_render_json(evidence_units),
            ),
        )
    if field_group == "mobile_phase_gradient":
        return RenderedPrompt(
            system_prompt=MOBILE_PHASE_GRADIENT_SYSTEM_PROMPT,
            user_prompt=MOBILE_PHASE_GRADIENT_USER_TEMPLATE.format(
                request_text=request_text.strip(),
                json_evidence_units=_render_json(evidence_units),
            ),
        )
    if field_group == "detector_ionization":
        return RenderedPrompt(
            system_prompt=DETECTOR_IONIZATION_SYSTEM_PROMPT,
            user_prompt=DETECTOR_IONIZATION_USER_TEMPLATE.format(
                request_text=request_text.strip(),
                json_evidence_units=_render_json(evidence_units),
            ),
        )
    if field_group == "target_impurity_linkage":
        return RenderedPrompt(
            system_prompt=TARGET_IMPURITY_LINKAGE_SYSTEM_PROMPT,
            user_prompt=TARGET_IMPURITY_LINKAGE_USER_TEMPLATE.format(
                request_text=request_text.strip(),
                analyte_name=_render_optional_text(analyte_name),
                target_smiles_present=_render_bool(target_smiles_present),
                impurity_count=max(0, impurity_count),
                json_evidence_units=_render_json(evidence_units),
            ),
        )
    raise ValueError(f"Unsupported field group: {field_group}")


def parse_query_planner_response(response_text: str) -> QueryPlannerResponse | None:
    return _parse_response_model(response_text, QueryPlannerResponse)


def parse_candidate_reranker_response(
    response_text: str,
) -> CandidateRerankResponse | None:
    return _parse_response_model(response_text, CandidateRerankResponse)


def parse_method_evidence_sniff_response(
    response_text: str,
) -> MethodEvidenceSniffResponse | None:
    payload = _parse_response_model(response_text, MethodEvidenceSniffResponse)
    if payload is None:
        return None
    if payload.confidence < 0.45 and payload.contains_extractable_final_method:
        return payload.model_copy(
            update={"contains_extractable_final_method": False}
        )
    return payload


def parse_field_extraction_response(
    field_group: PromptFieldGroup,
    response_text: str,
) -> RetrievalBaseModel | None:
    response_model = FIELD_EXTRACTION_RESPONSE_MODELS[field_group]
    return _parse_response_model(response_text, response_model)


def _parse_response_model(response_text: str, response_model: type[T]) -> T | None:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    try:
        return response_model.model_validate(payload)
    except ValidationError:
        return None


def _render_optional_text(value: str | None) -> str:
    normalized = coerce_bounded_text(value, max_length=500, allow_none=True)
    return normalized if normalized is not None else "null"


def _render_bool(value: bool) -> str:
    return "true" if value else "false"


def _render_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
