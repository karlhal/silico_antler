from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import ceil
import json
from threading import Lock
import re
from typing import Literal, TypeVar

from .recommendation_schemas import FetchedSourceArtifact, MethodRecommendationRequest
from .source_document_schemas import RegisteredSourceDocument

RequestSpecificity = Literal["specific", "mixed", "broad"]
ExplorationMode = Literal[
    "narrow_confirmation",
    "balanced_validation",
    "broad_exploration",
]
EvidenceFieldGroup = Literal[
    "chromatography_system",
    "mobile_phase_gradient",
    "detector_ionization",
    "target_impurity_linkage",
]

T = TypeVar("T")

EXTRACTION_CACHE_VERSION = "pdf-markdown-reader-fallback-v1"

_ARTIFACT_CACHE: dict[str, FetchedSourceArtifact] = {}
_EVIDENCE_UNIT_CACHE: dict[str, tuple["EvidenceUnit", ...]] = {}
_EXTRACTION_CACHE: dict[str, object] = {}
_VETTED_SNIPPET_CACHE: dict[str, str] = {}
_CACHE_LOCK = Lock()

_PRICING_PER_MILLION_TOKENS_USD: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "google/gemma-4-31b-it:free": (0.0, 0.0),
    "google/gemma-4-26b-a4b-it:free": (0.0, 0.0),
    "google/gemma-3-27b-it": (0.08, 0.16),
    "google/gemma-3-27b-it:free": (0.0, 0.0),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "nvidia/nemotron-3-super-120b-a12b:free": (0.0, 0.0),
    "nvidia/nemotron-3-nano-30b-a3b:free": (0.0, 0.0),
}


@dataclass(frozen=True)
class OpenAccessRunPlan:
    request_specificity: RequestSpecificity
    exploration_mode: ExplorationMode
    query_count: int
    search_budget: int
    rationale: str


@dataclass(frozen=True)
class EvidenceUnit:
    unit_id: str
    text: str
    section_label: str | None
    page_number: int | None
    source_kind: str
    feature_tags: tuple[str, ...]
    priority: float


@dataclass(frozen=True)
class LlmCallUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    raw_usage: dict[str, int]


def plan_open_access_run(request: MethodRecommendationRequest) -> OpenAccessRunPlan:
    analyte_tokens = _tokenize_text(request.analyte_name)
    matrix_tokens = _tokenize_text(request.matrix_hint)
    request_tokens = _tokenize_text(request.request_text)
    specificity_score = 0.0

    if request.target_smiles:
        specificity_score += 2.2
    if analyte_tokens:
        specificity_score += 1.8
    if matrix_tokens and not _is_generic_matrix(request.matrix_hint):
        specificity_score += 1.6
    if request.require_mass_spectrometry:
        specificity_score += 0.8
    if request.max_run_time_min is not None:
        specificity_score += 0.5
    if len(request_tokens) >= 8:
        specificity_score += 0.4
    if _contains_family_language(request.analyte_name):
        specificity_score -= 0.8
    if not request.target_smiles and len(analyte_tokens) <= 1:
        specificity_score -= 0.4

    if specificity_score >= 4.2:
        request_specificity: RequestSpecificity = "specific"
        exploration_mode: ExplorationMode = "narrow_confirmation"
        query_count = 2
        search_budget = min(max(request.max_papers * 2, request.max_papers + 2), 16)
        rationale = (
            "Specific analyte and matrix constraints allow a narrow confirmation search."
        )
    elif specificity_score >= 2.2:
        request_specificity = "mixed"
        exploration_mode = "balanced_validation"
        query_count = 3
        search_budget = min(max(request.max_papers * 3, request.max_papers + 3), 24)
        rationale = (
            "The request has useful anchors, but still benefits from a balanced follow-up sweep."
        )
    else:
        request_specificity = "broad"
        exploration_mode = "broad_exploration"
        query_count = 4
        search_budget = min(max(request.max_papers * 4, request.max_papers + 4), 32)
        rationale = (
            "The request remains broad, so search can explore more variants before screening."
        )

    return OpenAccessRunPlan(
        request_specificity=request_specificity,
        exploration_mode=exploration_mode,
        query_count=query_count,
        search_budget=search_budget,
        rationale=rationale,
    )


def build_evidence_units(document: RegisteredSourceDocument) -> tuple[EvidenceUnit, ...]:
    cache_key = build_document_cache_key(document)
    with _CACHE_LOCK:
        cached_units = _EVIDENCE_UNIT_CACHE.get(cache_key)
    if cached_units is not None:
        return cached_units

    units: list[EvidenceUnit] = []
    seen_texts: set[tuple[str, str | None, int | None]] = set()

    def _append_unit(
        *,
        text: str,
        section_label: str | None,
        page_number: int | None,
        source_kind: str,
        priority: float,
    ) -> None:
        collapsed = _collapse_whitespace(text)
        if len(collapsed) < 60:
            return
        for chunk in _chunk_text(collapsed):
            key = (chunk, section_label, page_number)
            if key in seen_texts:
                continue
            seen_texts.add(key)
            units.append(
                EvidenceUnit(
                    unit_id=f"evu-{sha256(json.dumps(key).encode('utf-8')).hexdigest()[:12]}",
                    text=chunk,
                    section_label=section_label,
                    page_number=page_number,
                    source_kind=source_kind,
                    feature_tags=tuple(sorted(_feature_tags_for_text(chunk))),
                    priority=priority,
                )
            )

    priority_by_kind = {
        "methods": 1.0,
        "results": 0.92,
        "discussion": 0.82,
        "conclusion": 0.74,
        "abstract": 0.64,
        "introduction": 0.52,
        "other": 0.45,
        "references": 0.1,
    }
    for section in document.sections:
        priority = priority_by_kind.get(section.normalized_label, 0.4)
        source_kind = f"section:{section.normalized_label}"
        _append_unit(
            text=section.text,
            section_label=section.label,
            page_number=section.start_page_number,
            source_kind=source_kind,
            priority=priority,
        )
    for page in document.pages:
        _append_unit(
            text=page.text,
            section_label=None,
            page_number=page.page_number,
            source_kind="page",
            priority=0.36,
        )

    units.sort(key=lambda item: (-item.priority, -len(item.feature_tags), len(item.text)))
    frozen_units = tuple(units)
    with _CACHE_LOCK:
        _EVIDENCE_UNIT_CACHE[cache_key] = frozen_units
    return frozen_units


def get_evidence_units(
    document: RegisteredSourceDocument,
) -> tuple[tuple[EvidenceUnit, ...], bool]:
    cache_key = build_document_cache_key(document)
    with _CACHE_LOCK:
        cached_units = _EVIDENCE_UNIT_CACHE.get(cache_key)
    if cached_units is not None:
        return cached_units, True
    return build_evidence_units(document), False


def select_evidence_units(
    evidence_units: tuple[EvidenceUnit, ...],
    *,
    field_group: EvidenceFieldGroup,
    limit: int = 4,
    allow_broad_follow_up: bool = False,
) -> tuple[EvidenceUnit, ...]:
    required_tags = _FIELD_GROUP_TAGS[field_group]
    scored_units: list[tuple[float, EvidenceUnit]] = []
    for unit in evidence_units:
        matched_tags = len(required_tags & set(unit.feature_tags))
        if matched_tags == 0 and not allow_broad_follow_up:
            continue
        score = unit.priority + matched_tags * 0.45
        if field_group == "mobile_phase_gradient" and "timing" in unit.feature_tags:
            score += 0.2
        if field_group == "detector_ionization" and "ms" in unit.feature_tags:
            score += 0.2
        if allow_broad_follow_up and matched_tags == 0:
            score -= 0.25
        scored_units.append((score, unit))

    scored_units.sort(key=lambda item: (-item[0], len(item[1].text)))
    selected = [unit for _, unit in scored_units[:limit]]
    if selected:
        return tuple(selected)
    return evidence_units[:limit]


def artifact_cache_lookup(cache_key: str) -> FetchedSourceArtifact | None:
    with _CACHE_LOCK:
        artifact = _ARTIFACT_CACHE.get(cache_key)
    if artifact is None:
        return None
    return artifact.model_copy(deep=True)


def store_artifact_cache(cache_key: str, artifact: FetchedSourceArtifact) -> None:
    with _CACHE_LOCK:
        _ARTIFACT_CACHE[cache_key] = artifact.model_copy(deep=True)


def extraction_cache_lookup(cache_key: str, value_type: type[T]) -> T | None:
    del value_type
    with _CACHE_LOCK:
        cached = _EXTRACTION_CACHE.get(cache_key)
    if cached is None:
        return None
    if hasattr(cached, "model_copy"):
        return cached.model_copy(deep=True)
    return cached


def store_extraction_cache(cache_key: str, value: object) -> None:
    cached_value = value.model_copy(deep=True) if hasattr(value, "model_copy") else value
    with _CACHE_LOCK:
        _EXTRACTION_CACHE[cache_key] = cached_value


def vetted_snippet_cache_lookup(cache_key: str) -> str | None:
    with _CACHE_LOCK:
        cached = _VETTED_SNIPPET_CACHE.get(cache_key)
    return cached


def store_vetted_snippet_cache(cache_key: str, snippet: str) -> None:
    with _CACHE_LOCK:
        _VETTED_SNIPPET_CACHE[cache_key] = snippet


def clear_recommendation_context_caches() -> None:
    with _CACHE_LOCK:
        _ARTIFACT_CACHE.clear()
        _EVIDENCE_UNIT_CACHE.clear()
        _EXTRACTION_CACHE.clear()
        _VETTED_SNIPPET_CACHE.clear()


def build_artifact_cache_key(
    *,
    paper_id: str,
    doi: str | None,
    url: str | None,
    pdf_url: str | None = None,
) -> str:
    payload = {
        "version": EXTRACTION_CACHE_VERSION,
        "paper_id": paper_id.strip().lower(),
        "doi": (doi or "").strip().lower(),
        "url": (url or "").strip().lower(),
        "pdf_url": (pdf_url or "").strip().lower(),
    }
    return (
        "artifact:"
        f"{sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()}"
    )


def build_document_cache_key(document: RegisteredSourceDocument) -> str:
    payload = {
        "version": EXTRACTION_CACHE_VERSION,
        "source_document": document.source_document.model_dump(mode="json"),
        "raw_text": document.raw_text,
    }
    return f"document:{sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()}"


def build_extraction_cache_key(
    document: RegisteredSourceDocument,
    *,
    llm_cache_key: str | None,
) -> str:
    return f"extraction:{build_document_cache_key(document)}:{llm_cache_key or 'heuristic-only'}"


def build_vetted_snippet_cache_key(
    source_hash: str,
    snippets: list[str],
) -> str:
    normalized_snippets = [_collapse_whitespace(snippet) for snippet in snippets if snippet]
    payload = json.dumps(normalized_snippets, sort_keys=True)
    return f"vetted:{source_hash}:{sha256(payload.encode('utf-8')).hexdigest()}"


def normalize_model_pricing_key(model: str) -> str:
    return model.strip().removeprefix("models/").lower()


def usage_from_response(
    *,
    response_json: dict,
    prompt_text: str,
    response_text: str,
    model: str,
) -> LlmCallUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    usage_metadata = response_json.get("usageMetadata")
    if isinstance(usage_metadata, dict):
        prompt_tokens = _safe_int(usage_metadata.get("promptTokenCount"))
        completion_tokens = _safe_int(usage_metadata.get("candidatesTokenCount"))
        total_tokens = _safe_int(usage_metadata.get("totalTokenCount"))

    usage = response_json.get("usage")
    if isinstance(usage, dict):
        prompt_tokens = prompt_tokens or _safe_int(usage.get("prompt_tokens"))
        completion_tokens = completion_tokens or _safe_int(usage.get("completion_tokens"))
        total_tokens = total_tokens or _safe_int(usage.get("total_tokens"))

    if prompt_tokens is None:
        prompt_tokens = estimate_token_count(prompt_text)
    if completion_tokens is None:
        completion_tokens = estimate_token_count(response_text)
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens

    estimated_cost_usd = estimate_token_cost_usd(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return LlmCallUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        raw_usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    )


def estimate_token_count(text: str) -> int:
    cleaned = _collapse_whitespace(text)
    if not cleaned:
        return 0
    return max(1, ceil(len(cleaned) / 4))


def estimate_token_cost_usd(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float | None:
    pricing = _PRICING_PER_MILLION_TOKENS_USD.get(normalize_model_pricing_key(model))
    if pricing is None:
        return None
    input_cost, output_cost = pricing
    return round(
        (prompt_tokens / 1_000_000) * input_cost
        + (completion_tokens / 1_000_000) * output_cost,
        6,
    )


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_text(text: str, *, max_chars: int = 900) -> list[str]:
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n+", text) if segment.strip()]
    if not paragraphs:
        paragraphs = [text]
    chunks: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue
        sentence_parts = re.split(r"(?<=[.!?])\s+", paragraph)
        current: list[str] = []
        current_len = 0
        for sentence in sentence_parts:
            sentence = sentence.strip()
            if not sentence:
                continue
            projected = current_len + len(sentence) + (1 if current else 0)
            if current and projected > max_chars:
                chunks.append(" ".join(current))
                current = [sentence]
                current_len = len(sentence)
            else:
                current.append(sentence)
                current_len = projected
        if current:
            chunks.append(" ".join(current))
    return chunks


def _feature_tags_for_text(text: str) -> set[str]:
    lowered = text.lower()
    tags: set[str] = set()
    if re.search(r"\b(column|c18|hilic|ods|stationary phase|uhplc|hplc|lc-ms)\b", lowered):
        tags.add("column")
    if re.search(r"\b(mobile phase|eluent|solvent|buffer|methanol|acetonitrile|water|mtbe)\b", lowered):
        tags.add("mobile_phase")
    if re.search(r"\b(gradient|isocratic|%b|%a)\b", lowered):
        tags.add("gradient")
    if re.search(r"\b(run time|runtime|flow rate|temperature|injection)\b", lowered):
        tags.add("timing")
    if re.search(r"\b(ms/ms|mass spectrometry|apci|esi|mrm|detector|qtrap|triple quadrupole)\b", lowered):
        tags.add("ms")
    if re.search(r"\b(retention time|analyte|compound|standard|plasma|serum|urine)\b", lowered):
        tags.add("entity")
    return tags


def _contains_family_language(analyte_name: str | None) -> bool:
    if not analyte_name:
        return False
    lowered = analyte_name.lower()
    return any(
        term in lowered
        for term in ("carotenoids", "vitamins", "metabolites", "compounds", "analytes")
    )


def _is_generic_matrix(matrix_hint: str | None) -> bool:
    if not matrix_hint:
        return True
    lowered = _collapse_whitespace(matrix_hint.lower())
    return lowered in {
        "organic solvent",
        "solvent",
        "sample",
        "samples",
        "aqueous",
        "unknown",
    }


def _tokenize_text(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2
    }


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


_FIELD_GROUP_TAGS: dict[EvidenceFieldGroup, set[str]] = {
    "chromatography_system": {"column"},
    "mobile_phase_gradient": {"mobile_phase", "gradient", "timing"},
    "detector_ionization": {"ms"},
    "target_impurity_linkage": {"entity"},
}
