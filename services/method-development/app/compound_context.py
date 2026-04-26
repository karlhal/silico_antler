from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .compound_context_client import (
    CompoundContextClientError,
    CompoundContextClientSession,
)
from .compound_context_schemas import CompoundContext, ExternalEvidenceTrace
from .recommendation_schemas import MethodRecommendationRequest

_QUERY_TERM_LIMIT = 8
_SYNONYM_QUERY_LIMIT = 3


@dataclass(frozen=True)
class RecommendationCompoundContext:
    target: CompoundContext | None
    impurities: tuple[CompoundContext, ...]
    trace: ExternalEvidenceTrace


def build_recommendation_compound_context(
    request: MethodRecommendationRequest,
    client: CompoundContextClientSession | None,
) -> RecommendationCompoundContext:
    trace = ExternalEvidenceTrace()
    if client is None:
        return RecommendationCompoundContext(target=None, impurities=(), trace=trace)

    target_context = _resolve_context(
        client,
        label=request.analyte_name,
        smiles=request.target_smiles,
        trace=trace,
    )
    impurity_contexts = tuple(
        context
        for context in (
            _resolve_context(client, label=None, smiles=smiles, trace=trace)
            for smiles in request.impurity_smiles
        )
        if context is not None
    )
    query_terms, truncation_warnings = build_compound_query_terms(
        request,
        target_context=target_context,
        impurity_contexts=impurity_contexts,
    )
    return RecommendationCompoundContext(
        target=target_context,
        impurities=impurity_contexts,
        trace=trace.model_copy(
            update={
                "query_terms_used": query_terms,
                "truncation_warnings": [
                    *trace.truncation_warnings,
                    *truncation_warnings,
                ],
            }
        ),
    )


def build_compound_query_terms(
    request: MethodRecommendationRequest,
    *,
    target_context: CompoundContext | None,
    impurity_contexts: tuple[CompoundContext, ...] = (),
) -> tuple[list[str], list[str]]:
    del impurity_contexts
    terms: list[str] = []
    warnings: list[str] = []

    if target_context is not None:
        _append_unique(terms, target_context.resolved_name)
        for synonym in target_context.synonyms[:_SYNONYM_QUERY_LIMIT]:
            _append_unique(terms, synonym)
        if len(target_context.synonyms) > _SYNONYM_QUERY_LIMIT:
            warnings.append(
                f"Compound-context query synonyms truncated to {_SYNONYM_QUERY_LIMIT} terms."
            )
    _append_unique(terms, request.analyte_name)
    if request.matrix_hint:
        _append_unique(terms, request.matrix_hint)
    if request.require_mass_spectrometry:
        _append_unique(terms, "LC-MS/MS")
    else:
        _append_unique(terms, "HPLC")
    _append_unique(terms, "quantification")

    if len(terms) > _QUERY_TERM_LIMIT:
        warnings.append(f"Compound-context query terms truncated to {_QUERY_TERM_LIMIT}.")
        terms = terms[:_QUERY_TERM_LIMIT]

    return terms, warnings


def count_skip_reasons(skipped_reasons: list[str]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for reason in skipped_reasons:
        counter[_skip_reason_bucket(reason)] += 1
    return dict(counter)


def _resolve_context(
    client: CompoundContextClientSession,
    *,
    label: str | None,
    smiles: str | None,
    trace: ExternalEvidenceTrace,
) -> CompoundContext | None:
    if not (label and label.strip()) and not (smiles and smiles.strip()):
        return None

    trace.source_clients_attempted = _append_value(
        trace.source_clients_attempted, "pubchem"
    )
    try:
        context = client.resolve_compound(label=label, smiles=smiles)
    except CompoundContextClientError as exc:
        trace.source_clients_failed = _append_value(
            trace.source_clients_failed, f"pubchem: {exc}"
        )
        return CompoundContext(
            input_label=label,
            input_smiles=smiles,
            lookup_sources=["pubchem"],
            warnings=[str(exc)],
            confidence="unresolved",
        )
    except Exception as exc:
        trace.source_clients_failed = _append_value(
            trace.source_clients_failed, f"pubchem: {exc}"
        )
        return CompoundContext(
            input_label=label,
            input_smiles=smiles,
            lookup_sources=["pubchem"],
            warnings=[f"Compound lookup failed: {exc}"],
            confidence="unresolved",
        )

    if context.confidence == "unresolved":
        trace.source_clients_failed = _append_value(
            trace.source_clients_failed, "pubchem: unresolved"
        )
    else:
        trace.source_clients_succeeded = _append_value(
            trace.source_clients_succeeded, "pubchem"
        )
    trace.truncation_warnings = [
        *trace.truncation_warnings,
        *(warning for warning in context.warnings if "truncated" in warning.lower()),
    ]
    return context


def _append_unique(values: list[str], value: str | None) -> None:
    if not value:
        return
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return
    seen = {item.lower() for item in values}
    if normalized.lower() not in seen:
        values.append(normalized)


def _append_value(values: list[str], value: str) -> list[str]:
    return values if value in values else [*values, value]


def _skip_reason_bucket(reason: str) -> str:
    lowered = reason.lower()
    if "fetch" in lowered:
        return "fetch"
    if "extraction" in lowered or "extract" in lowered:
        return "extraction"
    if "screen" in lowered or "score" in lowered:
        return "screening"
    if "viability" in lowered:
        return "viability"
    return "other"
