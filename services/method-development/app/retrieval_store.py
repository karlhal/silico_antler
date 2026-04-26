from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .chemistry import NormalizedMolecule, normalize_molecule, tanimoto_similarity
from .retrieval_schemas import (
    RetrievalContextualPriors,
    RetrievalImpurityMatch,
    RetrievalMatchRationale,
    RetrievalMethodRecord,
    RetrievalRecordReviewSummary,
)

SEED_METHODS_PATH = Path(__file__).resolve().parent / "data" / "seed_methods.json"

_RETRIEVAL_CONTEXT_WEIGHTS = {
    "chemistry": 0.72,
    "matrix": 0.10,
    "detector": 0.06,
    "method_family": 0.04,
    "review": 0.05,
    "retrieval_ready": 0.03,
}
_MS_SIGNAL_TERMS = (
    "lc-ms",
    "lc ms",
    "lc-ms/ms",
    "ms/ms",
    "triple quadrupole",
    "mass spectrom",
    "qtrap",
    "mrm",
    "orbitrap",
)
_RP_MODE_TERMS = ("c18", "rp-hplc", "reversed phase", "reverse phase", "rp lc")


@dataclass(frozen=True)
class RetrievalEntityMatch:
    local_identifier: str
    canonical_smiles: str
    display_name: str | None
    observed_retention_time_min: float | None
    score: float


@dataclass(frozen=True)
class RetrievalRecordMatch:
    record: RetrievalMethodRecord
    score: float
    matched_entity: RetrievalEntityMatch
    match_rationale: RetrievalMatchRationale
    review_summary: RetrievalRecordReviewSummary


@dataclass(frozen=True)
class _IndexedEntity:
    local_identifier: str
    normalized: NormalizedMolecule
    display_name: str | None
    observed_retention_time_min: float | None


@dataclass(frozen=True)
class _IndexedRecord:
    record: RetrievalMethodRecord
    entities: tuple[_IndexedEntity, ...]
    review_summary: RetrievalRecordReviewSummary


@dataclass(frozen=True)
class _ImpurityQueryMatch:
    query_canonical_smiles: str
    matched_entity: RetrievalEntityMatch


def load_seed_method_records(
    file_path: Path = SEED_METHODS_PATH,
) -> list[RetrievalMethodRecord]:
    payload = json.loads(file_path.read_text())
    if not isinstance(payload, list):
        raise ValueError("Seed method file must contain a list of retrieval records")
    return [RetrievalMethodRecord(**item) for item in payload]


@runtime_checkable
class RetrievalStore(Protocol):
    def search(
        self,
        query_smiles: str,
        *,
        impurity_smiles: list[str] | tuple[str, ...] | None = None,
        limit: int = 5,
        min_score: float = 0.0,
        matrix_hint: str | None = None,
        preferred_mode: str | None = None,
        require_mass_spectrometry: bool = False,
        apply_contextual_priors: bool = False,
    ) -> list[RetrievalRecordMatch]:
        ...

    def upsert_record(
        self,
        record: RetrievalMethodRecord,
        review_summary: RetrievalRecordReviewSummary,
    ) -> None:
        ...

    def remove_record(self, record_id: str) -> None:
        ...


class SeededRetrievalStore:
    def __init__(self, records: list[RetrievalMethodRecord]) -> None:
        self._records: dict[str, _IndexedRecord] = {
            record.record_id: _index_record(
                record,
                RetrievalRecordReviewSummary(
                    record_state="seeded",
                    validation_status=record.validation.status,
                    retrieval_ready=record.validation.retrieval_ready,
                ),
            )
            for record in records
        }

    @classmethod
    def from_seed_file(
        cls, file_path: Path = SEED_METHODS_PATH
    ) -> SeededRetrievalStore:
        return cls(load_seed_method_records(file_path))

    def search(
        self,
        query_smiles: str,
        *,
        impurity_smiles: list[str] | tuple[str, ...] | None = None,
        limit: int = 5,
        min_score: float = 0.0,
        matrix_hint: str | None = None,
        preferred_mode: str | None = None,
        require_mass_spectrometry: bool = False,
        apply_contextual_priors: bool = False,
    ) -> list[RetrievalRecordMatch]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0")

        normalized_query = normalize_molecule(query_smiles)
        normalized_impurities = tuple(
            normalize_molecule(smiles) for smiles in (impurity_smiles or [])
        )
        matches: list[RetrievalRecordMatch] = []

        for indexed_record in self._records.values():
            best_match = _best_entity_match(indexed_record, normalized_query)
            if best_match is None:
                continue

            impurity_matches = [
                _build_impurity_query_match(indexed_record, impurity)
                for impurity in normalized_impurities
            ]
            impurity_matches = [
                match for match in impurity_matches if match is not None
            ]
            aggregate_score = _compute_aggregate_score(
                best_match.score, impurity_matches
            )
            contextual_priors = (
                _build_contextual_priors(
                    indexed_record,
                    matrix_hint=matrix_hint,
                    preferred_mode=preferred_mode,
                    require_mass_spectrometry=require_mass_spectrometry,
                )
                if apply_contextual_priors
                else None
            )
            retrieval_score = (
                _compute_retrieval_score(
                    aggregate_score,
                    contextual_priors,
                )
                if contextual_priors is not None
                else aggregate_score
            )
            if retrieval_score < min_score:
                continue

            matches.append(
                RetrievalRecordMatch(
                    record=indexed_record.record,
                    score=retrieval_score,
                    matched_entity=best_match,
                    match_rationale=_build_match_rationale(
                        indexed_record,
                        best_match,
                        normalized_query.canonical_smiles,
                        impurity_matches,
                        aggregate_score,
                        retrieval_score=retrieval_score,
                        contextual_priors=contextual_priors,
                    ),
                    review_summary=indexed_record.review_summary,
                )
            )

        matches.sort(
            key=lambda match: (match.score, match.record.record_id),
            reverse=True,
        )
        return matches[:limit]

    def upsert_record(
        self,
        record: RetrievalMethodRecord,
        review_summary: RetrievalRecordReviewSummary,
    ) -> None:
        self._records[record.record_id] = _index_record(record, review_summary)

    def remove_record(self, record_id: str) -> None:
        self._records.pop(record_id, None)


def _index_record(
    record: RetrievalMethodRecord,
    review_summary: RetrievalRecordReviewSummary,
) -> _IndexedRecord:
    entities = tuple(
        _IndexedEntity(
            local_identifier=entity.local_identifier,
            normalized=normalize_molecule(entity.smiles_string),
            display_name=entity.display_name,
            observed_retention_time_min=entity.observed_retention_time_min,
        )
        for entity in record.molecular_entities
    )
    return _IndexedRecord(
        record=record, entities=entities, review_summary=review_summary
    )


def _best_entity_match(
    indexed_record: _IndexedRecord, normalized_query: NormalizedMolecule
) -> RetrievalEntityMatch | None:
    best_match: RetrievalEntityMatch | None = None
    for entity in indexed_record.entities:
        score = tanimoto_similarity(
            normalized_query.fingerprint,
            entity.normalized.fingerprint,
        )
        if best_match is None or score > best_match.score:
            best_match = RetrievalEntityMatch(
                local_identifier=entity.local_identifier,
                canonical_smiles=entity.normalized.canonical_smiles,
                display_name=entity.display_name,
                observed_retention_time_min=entity.observed_retention_time_min,
                score=score,
            )
    return best_match


def _build_impurity_query_match(
    indexed_record: _IndexedRecord, normalized_query: NormalizedMolecule
) -> _ImpurityQueryMatch | None:
    best_match = _best_entity_match(indexed_record, normalized_query)
    if best_match is None:
        return None
    return _ImpurityQueryMatch(
        query_canonical_smiles=normalized_query.canonical_smiles,
        matched_entity=best_match,
    )


def _compute_aggregate_score(
    target_score: float, impurity_matches: list[_ImpurityQueryMatch]
) -> float:
    if not impurity_matches:
        return target_score
    impurity_average = sum(
        match.matched_entity.score for match in impurity_matches
    ) / len(impurity_matches)
    return round(target_score * 0.7 + impurity_average * 0.3, 3)


def _compute_retrieval_score(
    chemistry_score: float,
    contextual_priors: RetrievalContextualPriors | None,
) -> float:
    if contextual_priors is None:
        return chemistry_score

    weighted_components = [
        (chemistry_score, _RETRIEVAL_CONTEXT_WEIGHTS["chemistry"]),
        (
            contextual_priors.matrix_compatibility,
            _RETRIEVAL_CONTEXT_WEIGHTS["matrix"],
        ),
        (
            contextual_priors.detector_compatibility,
            _RETRIEVAL_CONTEXT_WEIGHTS["detector"],
        ),
        (
            contextual_priors.method_family_compatibility,
            _RETRIEVAL_CONTEXT_WEIGHTS["method_family"],
        ),
        (
            contextual_priors.review_backed_prior,
            _RETRIEVAL_CONTEXT_WEIGHTS["review"],
        ),
        (
            contextual_priors.retrieval_ready_prior,
            _RETRIEVAL_CONTEXT_WEIGHTS["retrieval_ready"],
        ),
    ]
    total_weight = sum(weight for _, weight in weighted_components)
    if total_weight <= 0:
        return chemistry_score
    return round(
        sum(score * weight for score, weight in weighted_components) / total_weight,
        3,
    )


def _build_contextual_priors(
    indexed_record: _IndexedRecord,
    *,
    matrix_hint: str | None,
    preferred_mode: str | None,
    require_mass_spectrometry: bool,
) -> RetrievalContextualPriors:
    return RetrievalContextualPriors(
        matrix_compatibility=_matrix_compatibility_prior(
            indexed_record, matrix_hint=matrix_hint
        ),
        detector_compatibility=_detector_compatibility_prior(
            indexed_record, require_mass_spectrometry=require_mass_spectrometry
        ),
        method_family_compatibility=_method_family_compatibility_prior(
            indexed_record, preferred_mode=preferred_mode
        ),
        review_backed_prior=_review_backed_prior(indexed_record.review_summary),
        retrieval_ready_prior=(
            1.0 if indexed_record.review_summary.retrieval_ready else 0.45
        ),
    )


def _matrix_compatibility_prior(
    indexed_record: _IndexedRecord, *, matrix_hint: str | None
) -> float:
    if not matrix_hint:
        return 0.5
    descriptor_text = _record_descriptor_text(indexed_record)
    normalized_hint = " ".join(matrix_hint.lower().split())
    hint_tokens = _tokenize(normalized_hint)
    if not hint_tokens:
        return 0.5
    if normalized_hint in descriptor_text:
        return 1.0
    overlap = len(hint_tokens & _tokenize(descriptor_text)) / len(hint_tokens)
    if overlap <= 0:
        return 0.15
    return round(min(1.0, 0.35 + overlap * 0.65), 3)


def _detector_compatibility_prior(
    indexed_record: _IndexedRecord, *, require_mass_spectrometry: bool
) -> float:
    if not require_mass_spectrometry:
        return 0.6
    descriptor_text = _record_descriptor_text(indexed_record)
    return 1.0 if any(term in descriptor_text for term in _MS_SIGNAL_TERMS) else 0.2


def _method_family_compatibility_prior(
    indexed_record: _IndexedRecord, *, preferred_mode: str | None
) -> float:
    if not preferred_mode:
        return 0.55
    if indexed_record.record.chromatography_system.mode == preferred_mode:
        return 1.0

    descriptor_text = _record_descriptor_text(indexed_record)
    if preferred_mode == "hilic":
        return 0.85 if "hilic" in descriptor_text else 0.2
    if preferred_mode == "rp_lc":
        return 0.85 if any(term in descriptor_text for term in _RP_MODE_TERMS) else 0.25
    return 0.5


def _review_backed_prior(review_summary: RetrievalRecordReviewSummary) -> float:
    if review_summary.record_state == "approved":
        return 1.0
    if review_summary.record_state == "seeded":
        return 0.55
    if review_summary.record_state == "draft":
        return 0.4
    return 0.2


def _record_descriptor_text(indexed_record: _IndexedRecord) -> str:
    parts = [
        indexed_record.record.source_document.title or "",
        indexed_record.record.chromatography_system.mode,
        indexed_record.record.chromatography_system.column_name or "",
        indexed_record.record.chromatography_system.stationary_phase_chemistry,
        indexed_record.record.method_parameters.mobile_phase_a.solvent,
        (
            indexed_record.record.method_parameters.mobile_phase_b.solvent
            if indexed_record.record.method_parameters.mobile_phase_b
            else ""
        ),
        *[
            snippet.text[:200]
            for snippet in indexed_record.record.provenance.evidence_snippets[:5]
        ],
    ]
    return " ".join(part.lower() for part in parts if part)


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and not token.isdigit()
    }


def _build_match_rationale(
    indexed_record: _IndexedRecord,
    matched_entity: RetrievalEntityMatch,
    query_canonical_smiles: str,
    impurity_matches: list[_ImpurityQueryMatch],
    aggregate_score: float,
    *,
    retrieval_score: float,
    contextual_priors: RetrievalContextualPriors | None,
) -> RetrievalMatchRationale:
    match_type = (
        "exact"
        if matched_entity.canonical_smiles == query_canonical_smiles
        else "similarity"
    )
    matched_name = matched_entity.display_name or matched_entity.local_identifier
    if impurity_matches:
        impurity_average = sum(
            match.matched_entity.score for match in impurity_matches
        ) / len(impurity_matches)
        chemistry_summary = (
            f"Mixture-aware score {aggregate_score:.2f}: target '{matched_name}' "
            f"contributes {matched_entity.score:.2f} and impurities average "
            f"{impurity_average:.2f}."
        )
    else:
        chemistry_summary = (
            f"Exact molecular match to '{matched_name}'."
            if match_type == "exact"
            else f"Top similarity match to '{matched_name}' with score {matched_entity.score:.2f}."
        )

    summary = chemistry_summary
    if contextual_priors is not None:
        contextual_boosts = _contextual_boost_labels(contextual_priors)
        boost_suffix = (
            f" Context priors: {', '.join(contextual_boosts[:3])}."
            if contextual_boosts
            else ""
        )
        summary = f"Retrieval score {retrieval_score:.2f}. {chemistry_summary}{boost_suffix}"

    supporting_snippet = next(
        iter(indexed_record.record.provenance.evidence_snippets), None
    )
    return RetrievalMatchRationale(
        match_type=match_type,
        matched_entity_local_identifier=matched_entity.local_identifier,
        matched_entity_display_name=matched_entity.display_name,
        matched_entity_observed_retention_time_min=matched_entity.observed_retention_time_min,
        target_score=matched_entity.score,
        impurity_matches=[
            RetrievalImpurityMatch(
                query_canonical_smiles=match.query_canonical_smiles,
                matched_entity_local_identifier=match.matched_entity.local_identifier,
                matched_entity_display_name=match.matched_entity.display_name,
                score=match.matched_entity.score,
            )
            for match in impurity_matches
        ],
        aggregate_score=aggregate_score,
        retrieval_score=retrieval_score,
        contextual_priors=contextual_priors,
        supporting_snippet=supporting_snippet,
        summary=summary[:400],
    )


def _contextual_boost_labels(
    contextual_priors: RetrievalContextualPriors,
) -> list[str]:
    labels: list[tuple[float, str]] = [
        (contextual_priors.matrix_compatibility, "matrix-compatible evidence"),
        (contextual_priors.detector_compatibility, "detector-compatible evidence"),
        (
            contextual_priors.method_family_compatibility,
            "method-family compatibility",
        ),
        (contextual_priors.review_backed_prior, "review-backed prior"),
        (contextual_priors.retrieval_ready_prior, "retrieval-ready prior"),
    ]
    return [label for score, label in labels if score >= 0.75]
