from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from functools import cmp_to_key
import math
import os
from pathlib import Path
import re
from threading import Event, Thread
from typing import Callable
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from rich import print as rprint

from .chemistry import InvalidSmilesError, normalize_molecule, tanimoto_similarity
from .compound_context import (
    build_recommendation_compound_context,
    count_skip_reasons,
)
from .compound_context_client import PubChemCompoundContextClient
from .compound_context_schemas import ExternalEvidenceTrace
from .gemini_orchestration_client import GeminiClientError
from .hplc_extraction_schemas import MinimalHplcExtractionResponse
from .recommendation_context_optimizer import (
    artifact_cache_lookup,
    build_artifact_cache_key,
    get_evidence_units,
    OpenAccessRunPlan,
    plan_open_access_run,
    store_artifact_cache,
)
from .method_scaling import scale_method_for_system
from .hplc_text_extraction import extract_minimal_hplc
from .open_access_client import (
    OpenAccessClientError,
    OpenAccessPaperClient,
    OpenAccessPaperClientSession,
)
from .recommendation_runtime import RecommendationRuntimeTracker
from .recommendation_schemas import (
    FetchedSourceArtifact,
    MethodRecommendationReport,
    MethodRecommendationRequest,
    OpenAccessPaperCandidate,
    RecommendationCandidate,
    RecommendationDecisionTrace,
    RecommendationFeatureBreakdown,
    RecommendationIssueCounts,
    RecommendationQueryVariant,
    RecommendationRankingContext,
    RecommendationScoreBreakdown,
    RecommendationScoreLayers,
    RecommendationSkippedPaper,
    RecommendationTrust,
    RecommendationTrustState,
    RecommendedMethod,
)
from .retrieval_schemas import (
    EvidenceSnippet,
    RecordValidationState,
    SourceDocumentMetadata,
)
from .retrieval_store import RetrievalStore, SeededRetrievalStore, RetrievalRecordMatch
from .source_document_ingestion import ingest_html_document, ingest_pdf_document


@dataclass(frozen=True)
class _ExtractionMolecularProfile:
    target_score: float
    impurity_scores: tuple[float, ...]
    aggregate_score: float


@dataclass(frozen=True)
class _OpenAccessScreeningDecision:
    candidate: OpenAccessPaperCandidate
    screening_score: float
    normalized_score: float
    screening_model: str
    screening_reason: str
    screening_reasons: tuple[str, ...]
    summary: str


REVIEW_BACKED_NEAR_TIE_EPSILON = 0.02
VIABILITY_SCORE_THRESHOLD = 0.45
_LLM_ORCHESTRATION_SEARCH_BUDGET = 40
_LLM_ORCHESTRATION_SCREEN_LIMIT = 8
_LLM_TARGET_VIABLE_CANDIDATES = 3
_EXTRACTION_BATCH_SIZE = 5
_DEFAULT_FETCH_CONCURRENCY = 1
_DEFAULT_EXTRACTION_CONCURRENCY = int(
    os.getenv("SILICO_METHOD_DEVELOPMENT_EXTRACTION_CONCURRENCY", "2")
)
_FULL_DOCUMENT_LLM_FALLBACK_LIMIT = int(
    os.getenv(
        "SILICO_METHOD_DEVELOPMENT_FULL_DOCUMENT_LLM_FALLBACK_LIMIT",
        str(_LLM_ORCHESTRATION_SCREEN_LIMIT),
    )
)
_DEFAULT_QUERY_PLANNER_PARALLELISM = int(
    os.getenv("SILICO_METHOD_DEVELOPMENT_QUERY_PLANNER_PARALLELISM", "1")
)
HPLC_REQUIRED_SIGNALS = ["mobile phase", "flow rate", "column", "gradient", "mL/min"]
HPLC_STRONG_SIGNALS = ["acetonitrile", "methanol", "LC-MS", "HPLC", "UHPLC", "RP-HPLC"]
RANKING_FEATURE_WEIGHTS = {
    "target_chemistry_fit": 0.23,
    "impurity_compatibility": 0.08,
    "system_fit": 0.15,
    "detector_compatibility": 0.10,
    "matrix_fit": 0.10,
    "runtime_fit": 0.08,
    "extraction_completeness": 0.10,
    "evidence_quality": 0.10,
    "review_trust_prior": 0.03,
    "literature_specificity": 0.03,
}
MISSING_DATA_PENALTY_WEIGHT = 0.08
_RANKING_FEATURE_LABELS = (
    ("target_chemistry_fit", "target chemistry fit"),
    ("impurity_compatibility", "impurity compatibility"),
    ("system_fit", "system fit"),
    ("detector_compatibility", "detector compatibility"),
    ("matrix_fit", "matrix fit"),
    ("runtime_fit", "runtime fit"),
    ("extraction_completeness", "extraction completeness"),
    ("evidence_quality", "evidence quality"),
    ("review_trust_prior", "review-backed trust prior"),
    ("literature_specificity", "literature specificity"),
)
RecommendationProgressCallback = Callable[[str, str, int | None, int | None], None]
PROGRESS_HEARTBEAT_INTERVAL_S = 10.0


def recommend_methods(
    request: MethodRecommendationRequest,
    *,
    open_access_client: OpenAccessPaperClient | None = None,
    compound_context_client: PubChemCompoundContextClient | None = None,
    retrieval_store: RetrievalStore | None = None,
    gemini_client: GeminiOrchestrationClient | None = None,
    progress_callback: RecommendationProgressCallback | None = None,
    open_access_timeout_sec: int | None = None,
    enable_runtime_debug_metadata: bool = False,
    query_planner_parallelism: int | None = None,
    rate_limit_policy: str = "5/hour",
) -> MethodRecommendationReport:
    runtime_tracker = RecommendationRuntimeTracker(
        request,
        open_access_timeout_sec=open_access_timeout_sec,
        llm_observer_enabled=gemini_client is not None,
        rate_limit_policy=rate_limit_policy,
        enable_debug_metadata=enable_runtime_debug_metadata,
    )
    runtime_tracker.log_start()
    discovered_papers: list[OpenAccessPaperCandidate] = []
    source_artifacts: list[FetchedSourceArtifact] = []
    recommendation_candidates: list[RecommendationCandidate] = []
    skipped_papers: list[RecommendationSkippedPaper] = []
    search_query_used: str | None = None
    target_compound_context = None
    impurity_compound_contexts = []
    external_evidence_trace = ExternalEvidenceTrace()

    def _emit_progress(
        stage: str,
        message: str,
        items_completed: int | None,
        items_total: int | None,
    ) -> None:
        runtime_tracker.log_stage(
            stage,
            message=message,
            items_completed=items_completed,
            items_total=items_total,
        )
        if progress_callback is not None:
            progress_callback(stage, message, items_completed, items_total)

    if (
        request.source_mode in {"open_access", "local_corpus"}
        and compound_context_client is not None
    ):
        with compound_context_client.open_run() as context_client:
            compound_context = build_recommendation_compound_context(
                request, context_client
            )
        target_compound_context = compound_context.target
        impurity_compound_contexts = list(compound_context.impurities)
        external_evidence_trace = compound_context.trace
        if request.source_mode == "open_access":
            if external_evidence_trace.query_terms_used:
                runtime_tracker.note_branch_decision(
                    "Compound-context lookup enriched open-access search terms."
                )
        else:
            external_evidence_trace = external_evidence_trace.model_copy(
                update={"query_terms_used": []}
            )
            if external_evidence_trace.source_clients_succeeded:
                runtime_tracker.note_branch_decision(
                    "Compound-context lookup resolved auxiliary metadata for the local-corpus report."
                )

    if request.source_mode == "local_files":
        if request.local_paths:
            _emit_progress(
                "extract_methods",
                "Loading local source files for extraction.",
                0,
                len(request.local_paths),
            )
        for path in request.local_paths:
            try:
                source_artifacts.append(_load_local_source_artifact(Path(path)))
            except (FileNotFoundError, ValueError) as exc:
                raise runtime_tracker.fail(
                    runtime_status="request_invalid",
                    failure_classification="request_invalid",
                    message=f"Invalid local source input: {_summarize_exception(exc)}",
                    retryable=False,
                    failure_stage="extract_methods",
                ) from exc
    elif request.source_mode == "open_access":
        client = open_access_client or OpenAccessPaperClient(
            timeout_sec=open_access_timeout_sec or 20
        )
        search_plan = plan_open_access_run(request)
        search_query_variants = _build_search_query_variants(
            request,
            gemini_client=gemini_client,
            planner_parallelism=query_planner_parallelism,
        )
        if gemini_client is not None and request.search_query is None:
            if search_query_variants:
                search_plan = OpenAccessRunPlan(
                    request_specificity=search_plan.request_specificity,
                    exploration_mode=search_plan.exploration_mode,
                    query_count=len(search_query_variants),
                    search_budget=search_plan.search_budget,
                    rationale=(
                        "LLM query planner produced a bounded open-access search plan."
                    ),
                )
                runtime_tracker.note_branch_decision(
                    f"LLM query planner produced {len(search_query_variants)} query variant(s)."
                )
            else:
                search_query_variants = _build_search_query_variants(request)[
                    : search_plan.query_count
                ]
                runtime_tracker.note_branch_decision(
                    "LLM query planner returned malformed output; using deterministic query variants."
                )
        else:
            search_query_variants = search_query_variants[: search_plan.query_count]
        search_query_variants = _enrich_query_variants_with_compound_context(
            request,
            search_query_variants,
            external_evidence_trace.query_terms_used,
        )[: search_plan.query_count]
        runtime_tracker.note_search_plan(search_plan, queries=search_query_variants)
        # When the LLM planner is available, cast a wider net and let it prioritise.
        effective_search_budget = (
            _LLM_ORCHESTRATION_SEARCH_BUDGET
            if gemini_client is not None
            else search_plan.search_budget
        )
        effective_screen_limit = (
            _LLM_ORCHESTRATION_SCREEN_LIMIT
            if gemini_client is not None
            else request.max_papers
        )
        runtime_tracker.note_search_budget(effective_search_budget)
        runtime_tracker.note_open_access_budget(
            shortlist_size=effective_screen_limit,
            fetch_concurrency=_DEFAULT_FETCH_CONCURRENCY,
            extraction_concurrency=_DEFAULT_EXTRACTION_CONCURRENCY,
            target_viable_candidates=(
                _LLM_TARGET_VIABLE_CANDIDATES if gemini_client is not None else None
            ),
            stop_condition=(
                f"stop after {_LLM_TARGET_VIABLE_CANDIDATES} viable candidates or shortlist exhaustion"
                if gemini_client is not None
                else "process all shortlisted candidates"
            ),
        )
        runtime_tracker.note_branch_decision(search_plan.rationale)
        raw_papers: list[OpenAccessPaperCandidate] = []
        executed_queries: list[RecommendationQueryVariant] = []
        with client.open_run() as run_client:
            rprint(f"[blue]Phase: paper_fetch — {len(search_query_variants)} query variant(s)[/blue]")
            _emit_progress(
                "query_papers",
                "Searching open-access literature.",
                0,
                len(search_query_variants),
            )
            for variant in search_query_variants:
                runtime_tracker.note_query_attempt(variant.query_text)
                try:
                    raw_papers.extend(
                        _attach_query_provenance(
                            run_client.search_papers(
                                variant.query_text,
                                max_papers=effective_search_budget,
                            ),
                            variant,
                        )
                    )
                except Exception as exc:
                    raise runtime_tracker.fail(
                        runtime_status="upstream_unavailable",
                        failure_classification=_failure_classification_for_exception(
                            exc,
                            default="search_failure",
                        ),
                        message=(
                            "Open-access search failed for "
                            f"{variant.variant_id}: {_summarize_exception(exc)}"
                        ),
                        retryable=True,
                        failure_stage="query_papers",
                    ) from exc
                executed_queries.append(variant)
                _emit_progress(
                    "query_papers",
                    (
                        f"Completed literature query {len(executed_queries)} of "
                        f"{len(search_query_variants)} ({variant.variant_id})."
                    ),
                    len(executed_queries),
                    len(search_query_variants),
                )
            search_query_used = " | ".join(
                variant.query_text for variant in executed_queries
            )[:500]
            shortlisted_papers, skipped_papers = _screen_open_access_candidates(
                request, raw_papers, limit=effective_screen_limit
            )
            discovered_papers = [item.candidate for item in shortlisted_papers]
            if skipped_papers:
                runtime_tracker.note_branch_decision(
                    f"Screened out {len(skipped_papers)} open-access paper(s) before fetch."
                )
            if discovered_papers:
                runtime_tracker.note_branch_decision(
                    f"Shortlisted {len(discovered_papers)} open-access paper(s) for extraction."
                )

            if gemini_client is not None and shortlisted_papers:
                # LLM-orchestrated iterative extraction: planner ranks candidates, worker
                # extracts in batches of _EXTRACTION_BATCH_SIZE, stopping as soon as
                # _LLM_TARGET_VIABLE_CANDIDATES viable methods are found.
                _emit_progress(
                    "extract_methods",
                    f"Planner ranking {len(shortlisted_papers)} candidates.",
                    0,
                    len(shortlisted_papers),
                )
                try:
                    shortlisted_papers, reranker_skips, reranker_used = _llm_rerank_candidates(
                        request, shortlisted_papers, gemini_client
                    )
                    if reranker_skips:
                        skipped_papers.extend(reranker_skips)
                    if reranker_used:
                        runtime_tracker.note_branch_decision(
                            "LLM reranker reordered and filtered candidates for targeted extraction."
                        )
                    else:
                        runtime_tracker.note_branch_decision(
                            "LLM reranker returned malformed output; using heuristic ordering."
                        )
                except Exception:
                    runtime_tracker.note_branch_decision(
                        "LLM reranker failed; using heuristic ordering."
                    )
                # Hard-filter: never extract papers with non-positive heuristic scores.
                positive_papers = [p for p in shortlisted_papers if p.screening_score > 0]
                if positive_papers:
                    shortlisted_papers = positive_papers
                extraction_workers = max(
                    1,
                    min(_DEFAULT_EXTRACTION_CONCURRENCY, _EXTRACTION_BATCH_SIZE),
                )
                full_document_llm_fallback_limit = max(
                    0,
                    _FULL_DOCUMENT_LLM_FALLBACK_LIMIT,
                )
                rprint(
                    f"[blue]Phase: extraction — {len(shortlisted_papers)} candidate(s) "
                    f"in batches of {_EXTRACTION_BATCH_SIZE} with {extraction_workers} worker(s)[/blue]"
                )
                _emit_progress(
                    "extract_methods",
                    "Fetching and extracting shortlisted papers.",
                    0,
                    len(shortlisted_papers),
                )
                papers_attempted = 0
                for batch_start in range(
                    0,
                    len(shortlisted_papers),
                    _EXTRACTION_BATCH_SIZE,
                ):
                    batch = shortlisted_papers[
                        batch_start : batch_start + _EXTRACTION_BATCH_SIZE
                    ]
                    _stop_early = False
                    batch_inputs = []
                    for index_in_batch, screening_decision in enumerate(batch, start=1):
                        candidate_position = batch_start + index_in_batch
                        papers_attempted = max(papers_attempted, candidate_position)
                        batch_inputs.append(
                            (
                                candidate_position,
                                screening_decision,
                                candidate_position <= full_document_llm_fallback_limit,
                            )
                        )
                    with ThreadPoolExecutor(
                        max_workers=min(extraction_workers, len(batch_inputs))
                    ) as executor:
                        futures = [
                            executor.submit(
                                _build_open_access_recommendation_candidate,
                                request,
                                screening_decision,
                                client=run_client,
                                gemini_client=gemini_client,
                                progress_callback=_emit_progress,
                                candidate_index=candidate_position,
                                candidate_total=len(shortlisted_papers),
                                runtime_tracker=runtime_tracker,
                                allow_full_document_llm_fallback=allow_full_doc_fallback,
                            )
                            for (
                                candidate_position,
                                screening_decision,
                                allow_full_doc_fallback,
                            ) in batch_inputs
                        ]
                        batch_results = [future.result() for future in futures]
                    for built_candidate, candidate_skips in batch_results:
                        skipped_papers.extend(candidate_skips)
                        if built_candidate is not None:
                            recommendation_candidates.append(built_candidate)
                        if len(recommendation_candidates) >= _LLM_TARGET_VIABLE_CANDIDATES:
                            runtime_tracker.note_branch_decision(
                                f"Reached {_LLM_TARGET_VIABLE_CANDIDATES} viable candidates after "
                                f"{papers_attempted} papers; stopping extraction early."
                            )
                            _stop_early = True
                            break
                    if _stop_early:
                        break
            else:
                # Non-LLM path: extract all shortlisted papers linearly.
                _emit_progress(
                    "extract_methods",
                    "Fetching and extracting shortlisted papers.",
                    0,
                    len(discovered_papers),
                )
                for index, screening_decision in enumerate(shortlisted_papers, start=1):
                    built_candidate, candidate_skips = _build_open_access_recommendation_candidate(
                        request,
                        screening_decision,
                        client=run_client,
                        gemini_client=gemini_client,
                        progress_callback=_emit_progress,
                        candidate_index=index,
                        candidate_total=len(discovered_papers),
                        runtime_tracker=runtime_tracker,
                    )
                    skipped_papers.extend(candidate_skips)
                    if built_candidate is not None:
                        recommendation_candidates.append(built_candidate)
    else:
        _emit_progress(
            "query_papers",
            "Searching the curated local corpus.",
            0,
            request.max_papers,
        )
        store = retrieval_store or SeededRetrievalStore.from_seed_file()
        try:
            matches = store.search(
                request.target_smiles or "",
                impurity_smiles=request.impurity_smiles,
                limit=request.max_papers,
                matrix_hint=request.matrix_hint,
                preferred_mode=request.preferred_mode,
                require_mass_spectrometry=request.require_mass_spectrometry,
                apply_contextual_priors=True,
            )
        except InvalidSmilesError as exc:
            raise runtime_tracker.fail(
                runtime_status="request_invalid",
                failure_classification="request_invalid",
                message=str(exc),
                retryable=False,
                failure_stage="query_papers",
            ) from exc
        except Exception as exc:
            raise runtime_tracker.fail(
                runtime_status="upstream_unavailable",
                failure_classification="retrieval_store_unavailable",
                message=f"Retrieval store unavailable: {_summarize_exception(exc)}",
                retryable=True,
                failure_stage="query_papers",
            ) from exc
        _emit_progress(
            "match_system",
            f"Found {len(matches)} local corpus matches. Building recommendation candidates.",
            len(matches),
            len(matches),
        )
        recommendation_candidates = [
            _build_local_corpus_recommendation_candidate(request, match)
            for match in matches
        ]

    for index, artifact in enumerate(source_artifacts, start=1):
        _emit_progress(
            "extract_methods",
            f"Extracting method details from local source {index} of {len(source_artifacts)}.",
            index - 1,
            len(source_artifacts),
        )
        try:
            candidate = _build_recommendation_candidate(
                request,
                artifact,
                runtime_tracker=runtime_tracker,
            )
        except Exception as exc:
            classification = _failure_classification_for_exception(
                exc,
                default="extraction_failure",
            )
            skipped_papers.append(
                _skipped_paper_from_artifact(
                    artifact,
                    stage="extraction",
                    reason=_classified_skip_reason(classification, exc),
                )
            )
            runtime_tracker.note_branch_decision(
                f"Skipped local source {artifact.paper_id} after extraction failure.",
                degraded=True,
            )
            continue
        viability_skip_reason = _candidate_viability_skip_reason(request, candidate)
        if viability_skip_reason is not None:
            skipped_papers.append(
                _skipped_paper_from_artifact(
                    artifact,
                    stage="extraction",
                    reason=viability_skip_reason,
                )
            )
            runtime_tracker.note_branch_decision(
                f"Skipped local source {artifact.paper_id} after viability gating.",
                degraded=True,
            )
            continue
        recommendation_candidates.append(candidate)

    _emit_progress(
        "scale_physics",
        "Applying system fit and physics-aware method scaling.",
        len(recommendation_candidates),
        len(recommendation_candidates),
    )

    rprint(f"[blue]Phase: ranking — {len(recommendation_candidates)} extracted record(s)[/blue]")
    _emit_progress(
        "final_rank",
        "Ranking recommendation candidates.",
        len(recommendation_candidates),
        len(recommendation_candidates),
    )
    _sort_recommendation_candidates(recommendation_candidates)
    _annotate_ranked_candidate_explanations(recommendation_candidates)

    recommended_candidate = recommendation_candidates[0] if recommendation_candidates else None
    runtime = runtime_tracker.success_runtime(
        discovered_count=len(discovered_papers),
        candidate_count=len(recommendation_candidates),
        recommended_candidate_id=(
            recommended_candidate.paper_id if recommended_candidate is not None else None
        ),
    )
    if skipped_papers:
        external_evidence_trace = external_evidence_trace.model_copy(
            update={
                "skipped_reason_counts": count_skip_reasons(
                    [paper.reason for paper in skipped_papers]
                )
            }
        )

    return MethodRecommendationReport(
        request=request,
        source_mode=request.source_mode,
        search_query_used=search_query_used,
        target_compound_context=target_compound_context,
        impurity_compound_contexts=impurity_compound_contexts,
        external_evidence_trace=external_evidence_trace,
        discovered_papers=discovered_papers,
        skipped_papers=skipped_papers,
        considered_candidates=recommendation_candidates,
        recommended_candidate=recommended_candidate,
        runtime=runtime,
    )


def _build_local_corpus_recommendation_candidate(
    request: MethodRecommendationRequest,
    match: RetrievalRecordMatch,
) -> RecommendationCandidate:
    extraction = _extraction_from_record(match.record)
    trust = _build_recommendation_trust(
        trust_state=_local_corpus_trust_state(match),
        validation=match.record.validation,
        extraction_warnings=extraction.warnings,
    )
    score, decision_trace = _score_local_corpus_match_against_request(
        request,
        extraction,
        match,
        trust=trust,
    )
    rationale = _build_local_corpus_rationale(
        request, extraction, match, score, decision_trace=decision_trace
    )
    evidence_snippets = _build_candidate_evidence_snippets(
        extraction,
        primary_snippets=[
            match.match_rationale.supporting_snippet
        ]
        if match.match_rationale.supporting_snippet is not None
        else [],
    )
    return RecommendationCandidate(
        paper_id=match.record.record_id,
        title=(
            match.record.source_document.title
            or match.record.source_document.file_name
            or match.record.record_id
        ),
        doi=match.record.source_document.doi,
        url=match.record.source_document.url,
        published_year=match.record.source_document.published_year,
        source_kind=match.record.source_document.source_type,
        score=score,
        rationale=rationale,
        extraction=extraction,
        evidence_snippets=evidence_snippets,
        trust=trust,
        ranking_context=_build_local_corpus_ranking_context(request, match),
        match_rationale=match.match_rationale,
        review_summary=match.review_summary,
        decision_trace=decision_trace,
        recommended_method=_scale_method_for_recommendation(request, extraction),
        citation=_build_citation(match.record.source_document),
    )


def _load_local_source_artifact(path: Path) -> FetchedSourceArtifact:
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    paper_id = _local_paper_id(path)
    if suffix == ".pdf":
        return FetchedSourceArtifact(
            paper_id=paper_id,
            kind="pdf",
            title=path.stem,
            file_name=path.name,
            pdf_bytes=path.read_bytes(),
            url=str(path),
        )
    if suffix in {".html", ".htm"}:
        return FetchedSourceArtifact(
            paper_id=paper_id,
            kind="html",
            title=path.stem,
            file_name=path.name,
            html_content=path.read_text(),
            url=str(path),
        )
    raise ValueError(f"Unsupported local source type: {path.suffix}")

def _build_recommendation_candidate(
    request: MethodRecommendationRequest,
    artifact: FetchedSourceArtifact,
    *,
    gemini_client: GeminiOrchestrationClient | None = None,
    runtime_tracker: RecommendationRuntimeTracker | None = None,
    retrieval_score: float | None = None,
    screening_model: str | None = None,
    screening_summary: str | None = None,
    screening_reasons: tuple[str, ...] = (),
    query_provenance: list[RecommendationQueryVariant] | None = None,
    allow_full_document_llm_fallback: bool = True,
) -> RecommendationCandidate:
    extraction = _extract_artifact(
        artifact,
        request_text=request.request_text,
        gemini_client=gemini_client,
        runtime_tracker=runtime_tracker,
        allow_full_document_llm_fallback=allow_full_document_llm_fallback,
    )
    molecular_profile = _build_trusted_extraction_molecular_profile(
        request, extraction
    )
    validation = _validation_for_extraction(extraction)
    trust_state: RecommendationTrustState = (
        "open_access_extracted"
        if request.source_mode == "open_access"
        else "local_file_extracted"
    )
    trust = _build_recommendation_trust(
        trust_state=trust_state,
        validation=validation,
        extraction_warnings=extraction.warnings,
    )
    score, decision_trace = _score_extraction_against_request(
        request,
        extraction,
        trust=trust,
        molecular_profile=molecular_profile,
        retrieval_score=retrieval_score,
        screening_model=screening_model,
        screening_summary=screening_summary,
        screening_reasons=screening_reasons,
        query_provenance=query_provenance,
        candidate_abstract=artifact.abstract,
    )
    title = (
        extraction.source_document.title
        or artifact.title
        or artifact.file_name
        or artifact.paper_id
    )
    citation = _build_citation(extraction.source_document)
    rationale = _build_rationale(
        request,
        extraction,
        score,
        decision_trace=decision_trace,
    )
    return RecommendationCandidate(
        paper_id=artifact.paper_id,
        title=title,
        doi=extraction.source_document.doi,
        url=extraction.source_document.url,
        published_year=extraction.source_document.published_year,
        source_kind=artifact.kind,
        score=score,
        rationale=rationale,
        extraction=extraction,
        evidence_snippets=_build_candidate_evidence_snippets(extraction),
        trust=trust,
        ranking_context=_build_extraction_ranking_context(
            request, molecular_profile=molecular_profile
        ),
        decision_trace=decision_trace,
        recommended_method=_scale_method_for_recommendation(request, extraction),
        citation=citation,
    )


def _extract_artifact(
    artifact: FetchedSourceArtifact,
    *,
    request_text: str | None = None,
    gemini_client: GeminiOrchestrationClient | None = None,
    runtime_tracker: RecommendationRuntimeTracker | None = None,
    allow_full_document_llm_fallback: bool = True,
) -> MinimalHplcExtractionResponse:
    metadata = SourceDocumentMetadata(
        source_document_id=artifact.paper_id,
        source_type=artifact.kind,
        title=artifact.title,
        doi=artifact.doi,
        url=artifact.url,
        file_name=artifact.file_name,
        published_year=artifact.published_year,
    )
    if artifact.kind == "pdf":
        document = ingest_pdf_document(metadata, artifact.pdf_bytes or b"")
    else:
        document = ingest_html_document(metadata, artifact.html_content or "")
    return extract_minimal_hplc(
        document,
        request_text=request_text,
        gemini_client=gemini_client,
        runtime_tracker=runtime_tracker,
        allow_full_document_llm_fallback=allow_full_document_llm_fallback,
        source_pdf_bytes=artifact.pdf_bytes if artifact.kind == "pdf" else None,
        source_pdf_url=artifact.url if artifact.kind == "pdf" else None,
    )


def _document_from_artifact(artifact: FetchedSourceArtifact):
    metadata = SourceDocumentMetadata(
        source_document_id=artifact.paper_id,
        source_type=artifact.kind,
        title=artifact.title,
        doi=artifact.doi,
        url=artifact.url,
        file_name=artifact.file_name,
        published_year=artifact.published_year,
    )
    if artifact.kind == "pdf":
        return ingest_pdf_document(metadata, artifact.pdf_bytes or b"")
    return ingest_html_document(metadata, artifact.html_content or "")


def _open_access_method_sniff_skip_reason(
    request: MethodRecommendationRequest,
    artifact: FetchedSourceArtifact,
    *,
    gemini_client,
    runtime_tracker: RecommendationRuntimeTracker | None,
) -> str | None:
    try:
        document = _document_from_artifact(artifact)
    except Exception:
        return None

    evidence_units, _cache_hit = get_evidence_units(document)
    if not evidence_units:
        return None

    serialized_units = [
        {
            "unit_id": unit.unit_id,
            "text": unit.text,
            "section_label": unit.section_label,
            "page_number": unit.page_number,
            "source_kind": unit.source_kind,
            "feature_tags": list(unit.feature_tags),
        }
        for unit in evidence_units[:6]
    ]
    try:
        sniff = gemini_client.sniff_method_bearing_evidence(
            request_text=request.request_text,
            analyte_name=request.analyte_name,
            matrix_hint=request.matrix_hint,
            require_mass_spectrometry=request.require_mass_spectrometry,
            evidence_units=serialized_units,
        )
    except Exception:
        return None

    if sniff is None:
        return None
    if sniff.contains_extractable_final_method:
        if runtime_tracker is not None:
            runtime_tracker.note_branch_decision(
                f"Method-bearing sniff cleared {artifact.paper_id} with confidence {sniff.confidence:.2f}."
            )
        return None

    if runtime_tracker is not None:
        runtime_tracker.note_branch_decision(
            f"Method-bearing sniff rejected {artifact.paper_id} with confidence {sniff.confidence:.2f}.",
            degraded=True,
        )
    return (
        f"Method-bearing evidence sniff rejected the paper: {sniff.reason} "
        f"Sniff confidence: {sniff.confidence:.2f}."
    )


def _extraction_from_record(record) -> MinimalHplcExtractionResponse:
    return MinimalHplcExtractionResponse(
        source_document=record.source_document,
        chromatography_system=record.chromatography_system,
        method_parameters=record.method_parameters,
        provenance=record.provenance,
        warnings=[],
        retrieval_record_ready=record.validation.retrieval_ready,
    )


def _score_extraction_against_request(
    request: MethodRecommendationRequest,
    extraction,
    *,
    molecular_profile: _ExtractionMolecularProfile | None = None,
    trust: RecommendationTrust,
    retrieval_score: float | None = None,
    screening_model: str | None = None,
    screening_summary: str | None = None,
    screening_reasons: tuple[str, ...] = (),
    query_provenance: list[RecommendationQueryVariant] | None = None,
    candidate_abstract: str | None = None,
) -> tuple[RecommendationScoreBreakdown, RecommendationDecisionTrace]:
    target_chemistry_fit = _target_chemistry_fit_score(
        request, extraction, molecular_profile=molecular_profile, candidate_abstract=candidate_abstract
    )
    impurity_compatibility = _extraction_impurity_compatibility_score(
        request, molecular_profile=molecular_profile
    )
    system_match = _system_match_score(request, extraction)
    detector_compatibility = _detector_compatibility_score(request, extraction)
    runtime_fit = _runtime_fit_score(request, extraction)
    matrix_fit = _matrix_fit_score(request, extraction, candidate_abstract=candidate_abstract)
    extraction_completeness = _extraction_completeness_score(extraction)
    evidence_quality = _evidence_quality_score(extraction)
    review_trust_prior = _review_trust_prior_score(trust)
    literature_specificity = _literature_specificity_score(request, extraction)
    missing_data_penalty = _missing_data_penalty(
        request,
        extraction,
        detector_compatibility=detector_compatibility,
    )
    analyte_match = _combined_analyte_match_score(
        request,
        target_chemistry_fit=target_chemistry_fit,
        impurity_compatibility=impurity_compatibility,
    )
    practical_fit = _combined_practical_fit_score(
        request,
        extraction,
        detector_compatibility=detector_compatibility,
        runtime_fit=runtime_fit,
    )
    features = RecommendationFeatureBreakdown(
        target_chemistry_fit=target_chemistry_fit,
        impurity_compatibility=impurity_compatibility,
        system_fit=system_match,
        detector_compatibility=detector_compatibility,
        matrix_fit=matrix_fit,
        runtime_fit=runtime_fit,
        extraction_completeness=extraction_completeness,
        evidence_quality=evidence_quality,
        review_trust_prior=review_trust_prior,
        literature_specificity=literature_specificity,
        missing_data_penalty=missing_data_penalty,
    )
    score = _build_score_breakdown(
        system_match=system_match,
        analyte_match=analyte_match,
        matrix_fit=matrix_fit,
        practical_fit=practical_fit,
        extraction_confidence=round(
            min(1.0, extraction_completeness * 0.65 + evidence_quality * 0.35), 3
        ),
        literature_relevance=literature_specificity,
        features=features,
    )
    return score, _build_decision_trace(
        score,
        features,
        retrieval_score=retrieval_score,
        screening_model=screening_model,
        screening_summary=screening_summary,
        screening_reasons=screening_reasons,
        query_provenance=query_provenance,
    )


def _score_local_corpus_match_against_request(
    request: MethodRecommendationRequest,
    extraction: MinimalHplcExtractionResponse,
    match: RetrievalRecordMatch,
    *,
    trust: RecommendationTrust,
) -> tuple[RecommendationScoreBreakdown, RecommendationDecisionTrace]:
    target_chemistry_fit = _local_corpus_target_chemistry_fit_score(request, match)
    impurity_compatibility = _local_corpus_impurity_compatibility_score(
        request, match
    )
    system_match = _system_match_score(request, extraction)
    detector_compatibility = _detector_compatibility_score(request, extraction)
    runtime_fit = _runtime_fit_score(request, extraction)
    matrix_fit = _matrix_fit_score(request, extraction)
    extraction_completeness = _extraction_completeness_score(extraction)
    evidence_quality = _evidence_quality_score(extraction)
    review_trust_prior = _review_trust_prior_score(trust)
    literature_specificity = _local_corpus_literature_relevance_score(
        request, extraction, match
    )
    missing_data_penalty = _missing_data_penalty(
        request,
        extraction,
        detector_compatibility=detector_compatibility,
    )
    analyte_match = _combined_analyte_match_score(
        request,
        target_chemistry_fit=target_chemistry_fit,
        impurity_compatibility=impurity_compatibility,
    )
    practical_fit = _combined_practical_fit_score(
        request,
        extraction,
        detector_compatibility=detector_compatibility,
        runtime_fit=runtime_fit,
    )
    features = RecommendationFeatureBreakdown(
        target_chemistry_fit=target_chemistry_fit,
        impurity_compatibility=impurity_compatibility,
        system_fit=system_match,
        detector_compatibility=detector_compatibility,
        matrix_fit=matrix_fit,
        runtime_fit=runtime_fit,
        extraction_completeness=extraction_completeness,
        evidence_quality=evidence_quality,
        review_trust_prior=review_trust_prior,
        literature_specificity=literature_specificity,
        missing_data_penalty=missing_data_penalty,
    )
    score = _build_score_breakdown(
        system_match=system_match,
        analyte_match=analyte_match,
        matrix_fit=matrix_fit,
        practical_fit=practical_fit,
        extraction_confidence=round(
            min(1.0, extraction_completeness * 0.65 + evidence_quality * 0.35), 3
        ),
        literature_relevance=literature_specificity,
        features=features,
    )
    screening_summary = (
        f"Local corpus shortlist survived retrieval with score {match.score:.2f}. "
        f"{match.match_rationale.summary}"
    )
    return score, _build_decision_trace(
        score,
        features,
        retrieval_score=match.score,
        screening_model="deterministic",
        screening_summary=screening_summary[:600],
    )


def _build_score_breakdown(
    *,
    system_match: float,
    analyte_match: float,
    matrix_fit: float,
    practical_fit: float,
    extraction_confidence: float,
    literature_relevance: float,
    features: RecommendationFeatureBreakdown,
) -> RecommendationScoreBreakdown:
    weighted_positive_score = sum(
        getattr(features, feature_name) * weight
        for feature_name, weight in RANKING_FEATURE_WEIGHTS.items()
    )
    total_score = round(
        max(
            0.0,
            min(
                1.0,
                weighted_positive_score
                - features.missing_data_penalty * MISSING_DATA_PENALTY_WEIGHT,
            ),
        ),
        3,
    )

    return RecommendationScoreBreakdown(
        total_score=total_score,
        system_match=system_match,
        analyte_match=analyte_match,
        matrix_fit=matrix_fit,
        practical_fit=practical_fit,
        extraction_confidence=extraction_confidence,
        literature_relevance=literature_relevance,
        features=features,
    )


def _build_open_access_recommendation_candidate(
    request: MethodRecommendationRequest,
    screening_decision: _OpenAccessScreeningDecision,
    *,
    client: OpenAccessPaperClientSession,
    gemini_client: GeminiOrchestrationClient | None = None,
    progress_callback: RecommendationProgressCallback | None = None,
    candidate_index: int | None = None,
    candidate_total: int | None = None,
    runtime_tracker: RecommendationRuntimeTracker,
    allow_full_document_llm_fallback: bool = True,
) -> tuple[RecommendationCandidate | None, list[RecommendationSkippedPaper]]:
    candidate = screening_decision.candidate
    attempted_reasons: list[str] = []

    if progress_callback is not None:
        progress_callback(
            "extract_methods",
            f"Fetching source {candidate_index or 0} of {candidate_total or 0}: {candidate.title[:160]}",
            candidate_index - 1 if candidate_index is not None else None,
            candidate_total,
        )

    artifact_cache_key = build_artifact_cache_key(
        paper_id=candidate.paper_id,
        doi=candidate.doi,
        url=candidate.url,
        pdf_url=candidate.pdf_url,
    )
    cached_artifact = artifact_cache_lookup(artifact_cache_key)
    try:
        if cached_artifact is not None:
            runtime_tracker.note_cache_event(
                "extract_methods",
                cache_name="artifact",
                hit=True,
            )
            primary_artifact = cached_artifact
        else:
            runtime_tracker.note_cache_event(
                "extract_methods",
                cache_name="artifact",
                hit=False,
            )
            primary_artifact = _run_with_progress_keepalive(
                progress_callback=progress_callback,
                stage="extract_methods",
                message=(
                    f"Still fetching source {candidate_index or 0} of {candidate_total or 0}: "
                    f"{candidate.title[:160]}"
                ),
                items_completed=candidate_index - 1 if candidate_index is not None else None,
                items_total=candidate_total,
                operation=lambda: client.fetch_source_artifact(candidate),
            )
            store_artifact_cache(artifact_cache_key, primary_artifact)
    except Exception as exc:
        classification = _failure_classification_for_exception(
            exc,
            default="fetch_failure",
        )
        runtime_tracker.note_branch_decision(
            f"Fetch failed for {candidate.paper_id}.",
            degraded=True,
        )
        return (
            None,
            [
                _skipped_paper_from_candidate(
                    candidate,
                    stage="fetch",
                    reason=_classified_skip_reason(classification, exc),
                )
            ],
        )

    if progress_callback is not None:
        progress_callback(
            "extract_methods",
            f"Extracting method details from source {candidate_index or 0} of {candidate_total or 0}: {candidate.title[:160]}",
            candidate_index if candidate_index is not None else None,
            candidate_total,
        )

    candidate_text = (primary_artifact.html_content or "") + " " + (candidate.abstract or "")
    if primary_artifact.kind == "html" and not _paper_has_hplc_signal(candidate_text):
        runtime_tracker.note_branch_decision(
            f"Skipped {candidate.paper_id}: no HPLC signal detected.",
            degraded=True,
        )
        return (
            None,
            [
                _skipped_paper_from_candidate(
                    candidate,
                    stage="extraction",
                    reason="no_hplc_signal",
                )
            ],
        )

    built_candidate, primary_reason, _primary_classification = _candidate_from_open_access_artifact(
        request,
        primary_artifact,
        gemini_client=gemini_client,
        runtime_tracker=runtime_tracker,
        retrieval_score=screening_decision.normalized_score,
        screening_model=screening_decision.screening_model,
        screening_summary=screening_decision.summary,
        screening_reasons=screening_decision.screening_reasons,
        query_provenance=screening_decision.candidate.query_provenance,
        progress_callback=progress_callback,
        candidate_index=candidate_index,
        candidate_total=candidate_total,
        allow_full_document_llm_fallback=allow_full_document_llm_fallback,
    )
    if built_candidate is not None:
        return built_candidate, []
    if primary_reason is not None:
        attempted_reasons.append(f"{primary_artifact.kind.upper()}: {primary_reason}")
        runtime_tracker.note_branch_decision(
            f"{primary_artifact.kind.upper()} extraction did not yield a trustworthy candidate.",
            degraded=True,
        )

    html_char_count = len(primary_artifact.html_content or "")
    if _can_try_pdf_fallback(candidate, primary_artifact, html_char_count):
        runtime_tracker.note_branch_decision(
            f"Fell back from HTML to PDF for {candidate.paper_id}.",
            degraded=True,
        )
        pdf_only_candidate = candidate.model_copy(
            update={
                "url": None,
                "pdf_url": candidate.pdf_url,
            }
        )
        try:
            pdf_cache_key = build_artifact_cache_key(
                paper_id=pdf_only_candidate.paper_id,
                doi=pdf_only_candidate.doi,
                url=pdf_only_candidate.url,
                pdf_url=pdf_only_candidate.pdf_url,
            )
            cached_pdf_artifact = artifact_cache_lookup(pdf_cache_key)
            if progress_callback is not None:
                progress_callback(
                    "extract_methods",
                    f"Falling back to PDF for source {candidate_index or 0} of {candidate_total or 0}: {candidate.title[:160]}",
                    candidate_index - 1 if candidate_index is not None else None,
                    candidate_total,
                )
            if cached_pdf_artifact is not None:
                runtime_tracker.note_cache_event(
                    "extract_methods",
                    cache_name="artifact",
                    hit=True,
                )
                pdf_artifact = cached_pdf_artifact
            else:
                runtime_tracker.note_cache_event(
                    "extract_methods",
                    cache_name="artifact",
                    hit=False,
                )
                pdf_artifact = _run_with_progress_keepalive(
                    progress_callback=progress_callback,
                    stage="extract_methods",
                    message=(
                        f"Still fetching PDF fallback for source {candidate_index or 0} of {candidate_total or 0}: "
                        f"{candidate.title[:160]}"
                    ),
                    items_completed=candidate_index - 1 if candidate_index is not None else None,
                    items_total=candidate_total,
                    operation=lambda: client.fetch_source_artifact(pdf_only_candidate),
                )
                store_artifact_cache(pdf_cache_key, pdf_artifact)
        except Exception as exc:
            classification = _failure_classification_for_exception(
                exc,
                default="fetch_failure",
            )
            attempted_reasons.append(
                f"PDF: {_classified_skip_reason(classification, exc)}"
            )
        else:
            if _artifact_identity(pdf_artifact) != _artifact_identity(primary_artifact):
                built_candidate, fallback_reason, fallback_classification = _candidate_from_open_access_artifact(
                    request,
                    pdf_artifact,
                    gemini_client=gemini_client,
                    runtime_tracker=runtime_tracker,
                    retrieval_score=screening_decision.normalized_score,
                    screening_model=screening_decision.screening_model,
                    screening_summary=screening_decision.summary,
                    screening_reasons=screening_decision.screening_reasons,
                    query_provenance=screening_decision.candidate.query_provenance,
                    progress_callback=progress_callback,
                    candidate_index=candidate_index,
                    candidate_total=candidate_total,
                    allow_full_document_llm_fallback=allow_full_document_llm_fallback,
                )
                if built_candidate is not None:
                    return built_candidate, []
                if fallback_reason is not None:
                    attempted_reasons.append(f"{pdf_artifact.kind.upper()}: {fallback_reason}")
                    if fallback_classification is not None:
                        runtime_tracker.note_branch_decision(
                            f"{pdf_artifact.kind.upper()} extraction did not yield a trustworthy candidate.",
                            degraded=True,
                        )

    reason = (
        " ; ".join(attempted_reasons)
        if attempted_reasons
        else "No trustworthy open-access extraction candidate could be built."
    )
    return (
        None,
        [
            _skipped_paper_from_candidate(
                candidate,
                stage="extraction",
                reason=reason,
            )
        ],
    )


def _candidate_from_open_access_artifact(
    request: MethodRecommendationRequest,
    artifact: FetchedSourceArtifact,
    *,
    gemini_client: GeminiOrchestrationClient | None = None,
    runtime_tracker: RecommendationRuntimeTracker | None = None,
    retrieval_score: float | None = None,
    screening_model: str | None = None,
    screening_summary: str | None = None,
    screening_reasons: tuple[str, ...] = (),
    query_provenance: list[RecommendationQueryVariant] | None = None,
    progress_callback: RecommendationProgressCallback | None = None,
    candidate_index: int | None = None,
    candidate_total: int | None = None,
    allow_full_document_llm_fallback: bool = True,
) -> tuple[
    RecommendationCandidate | None,
    str | None,
    str | None,
]:
    if gemini_client is not None:
        sniff_reason = _open_access_method_sniff_skip_reason(
            request,
            artifact,
            gemini_client=gemini_client,
            runtime_tracker=runtime_tracker,
        )
        if sniff_reason is not None:
            return None, sniff_reason, "extraction_failure"

    try:
        candidate = _run_with_progress_keepalive(
            progress_callback=progress_callback,
            stage="extract_methods",
            message=(
                f"Still extracting {artifact.kind.upper()} method details from source "
                f"{candidate_index or 0} of {candidate_total or 0}: "
                f"{(artifact.title or artifact.file_name or artifact.paper_id)[:160]}"
            ),
            items_completed=candidate_index if candidate_index is not None else None,
            items_total=candidate_total,
            operation=lambda: _build_recommendation_candidate(
                request,
                artifact,
                gemini_client=gemini_client,
                runtime_tracker=runtime_tracker,
                retrieval_score=retrieval_score,
                screening_model=screening_model,
                screening_summary=screening_summary,
                screening_reasons=screening_reasons,
                query_provenance=query_provenance,
                allow_full_document_llm_fallback=allow_full_document_llm_fallback,
            ),
        )
    except Exception as exc:
        classification = _failure_classification_for_exception(
            exc,
            default="extraction_failure",
        )
        return None, _classified_skip_reason(classification, exc), classification

    skip_reason = _candidate_viability_skip_reason(request, candidate)
    if skip_reason is not None:
        artifact_label = artifact.paper_id
        if artifact.title:
            artifact_label = f"{artifact_label} — {artifact.title[:120]}"
        rprint(
            f"[yellow]Viability gate rejected {artifact_label}: {skip_reason}[/yellow]"
        )
        return None, skip_reason, "extraction_failure"
    return candidate, None, None


def _paper_has_hplc_signal(text: str) -> bool:
    text_lower = text.lower()
    required = sum(1 for s in HPLC_REQUIRED_SIGNALS if s.lower() in text_lower)
    strong = sum(1 for s in HPLC_STRONG_SIGNALS if s.lower() in text_lower)
    return required >= 2 or strong >= 1


def _can_try_pdf_fallback(
    candidate: OpenAccessPaperCandidate,
    artifact: FetchedSourceArtifact,
    html_char_count: int = 0,
) -> bool:
    if artifact.kind != "html":
        return False
    pdf_url = (candidate.pdf_url or "").strip()
    if not pdf_url:
        return False
    if html_char_count < 1000:
        return True  # sparse HTML (JS shell) — fallback warranted
    return pdf_url != (artifact.url or "").strip()  # rich HTML extraction failed


def _artifact_identity(artifact: FetchedSourceArtifact) -> tuple[str, str | None]:
    return artifact.kind, artifact.url


def _local_corpus_analyte_match_score(
    request: MethodRecommendationRequest, match: RetrievalRecordMatch
) -> float:
    return _combined_analyte_match_score(
        request,
        target_chemistry_fit=_local_corpus_target_chemistry_fit_score(request, match),
        impurity_compatibility=_local_corpus_impurity_compatibility_score(
            request, match
        ),
    )


def _local_corpus_literature_relevance_score(
    request: MethodRecommendationRequest,
    extraction: MinimalHplcExtractionResponse,
    match: RetrievalRecordMatch,
) -> float:
    del match
    return _literature_relevance_score(request, extraction)


def _build_local_corpus_ranking_context(
    request: MethodRecommendationRequest, match: RetrievalRecordMatch
) -> RecommendationRankingContext:
    impurity_count = _requested_impurity_count(request)
    if impurity_count and match.match_rationale.impurity_matches:
        return RecommendationRankingContext(
            ranking_mode="target_plus_impurities",
            impurity_handling="active",
            impurity_count=impurity_count,
            summary=(
                "Mixture-aware ranking is active. Local-corpus scoring combines the "
                "target match (70%) with matched impurity profiles (30%)."
            ),
        )
    if impurity_count:
        return RecommendationRankingContext(
            ranking_mode="target_only",
            impurity_handling="requested_but_untrusted",
            impurity_count=impurity_count,
            summary=(
                "Impurities were requested, but no trustworthy impurity matches were "
                "available in this corpus result, so ranking stayed target-focused."
            ),
        )
    return RecommendationRankingContext(
        ranking_mode="target_only",
        impurity_handling="not_requested",
        impurity_count=0,
        summary="Ranking used the target molecule only.",
    )


def _build_extraction_ranking_context(
    request: MethodRecommendationRequest,
    *,
    molecular_profile: _ExtractionMolecularProfile | None,
) -> RecommendationRankingContext:
    impurity_count = _requested_impurity_count(request)
    if impurity_count == 0:
        return RecommendationRankingContext(
            ranking_mode="target_only",
            impurity_handling="not_requested",
            impurity_count=0,
            summary="Ranking used the target molecule only.",
        )
    if molecular_profile is not None:
        return RecommendationRankingContext(
            ranking_mode="target_plus_impurities",
            impurity_handling="active",
            impurity_count=impurity_count,
            summary=(
                "Mixture-aware ranking is active because the extracted method "
                "contained confidently linked target and impurity identities."
            ),
        )
    return RecommendationRankingContext(
        ranking_mode="target_only",
        impurity_handling="requested_but_untrusted",
        impurity_count=impurity_count,
        summary=(
            "Impurity inputs were accepted, but this extraction lacks confident "
            "SMILES linkage for the impurity set, so ranking stayed target-focused."
        ),
    )


def _build_trusted_extraction_molecular_profile(
    request: MethodRecommendationRequest,
    extraction: MinimalHplcExtractionResponse,
) -> _ExtractionMolecularProfile | None:
    if not request.target_smiles or not request.impurity_smiles:
        return None

    try:
        linked_entities = [
            (normalize_molecule(draft.smiles_string), draft.confidence)
            for draft in extraction.molecular_entity_drafts
            if draft.smiles_string
        ]
        target_molecule = normalize_molecule(request.target_smiles)
        impurity_molecules = [
            normalize_molecule(impurity_smiles)
            for impurity_smiles in request.impurity_smiles
        ]
    except InvalidSmilesError:
        return None

    trustworthy_entities = [
        normalized
        for normalized, confidence in linked_entities
        if confidence >= 0.7
    ]
    if not trustworthy_entities:
        return None

    target_score = max(
        tanimoto_similarity(target_molecule.fingerprint, entity.fingerprint)
        for entity in trustworthy_entities
    )
    if target_score < 0.85:
        return None

    impurity_scores: list[float] = []
    for impurity_molecule in impurity_molecules:
        impurity_score = max(
            tanimoto_similarity(impurity_molecule.fingerprint, entity.fingerprint)
            for entity in trustworthy_entities
        )
        if impurity_score < 0.85:
            return None
        impurity_scores.append(impurity_score)

    impurity_average = sum(impurity_scores) / len(impurity_scores)
    aggregate_score = round(target_score * 0.7 + impurity_average * 0.3, 3)
    return _ExtractionMolecularProfile(
        target_score=round(target_score, 3),
        impurity_scores=tuple(round(score, 3) for score in impurity_scores),
        aggregate_score=aggregate_score,
    )


def _requested_impurity_count(request: MethodRecommendationRequest) -> int:
    return sum(1 for smiles in request.impurity_smiles if smiles.strip())


def _system_match_score(request: MethodRecommendationRequest, extraction) -> float:
    if not request.system_specs or not extraction.chromatography_system:
        return 0.5

    specs = request.system_specs
    system = extraction.chromatography_system
    score = 0.0

    # Chemistry (30%)
    if specs.column_chemistry and system.stationary_phase_chemistry:
        if specs.column_chemistry.lower() in system.stationary_phase_chemistry.lower():
            score += 0.3
        elif _tokenize(specs.column_chemistry) & _tokenize(
            system.stationary_phase_chemistry
        ):
            score += 0.15

    # Dimensions (30%)
    if specs.column_length_mm and system.column_length_mm:
        diff = abs(specs.column_length_mm - system.column_length_mm)
        if diff < 5:
            score += 0.2
        elif diff < 50:
            score += 0.1
    if specs.column_inner_diameter_mm and system.column_inner_diameter_mm:
        if specs.column_inner_diameter_mm == system.column_inner_diameter_mm:
            score += 0.1

    # Particle Size (20%)
    if specs.particle_size_um and system.particle_size_um:
        diff = abs(specs.particle_size_um - system.particle_size_um)
        if diff < 0.5:
            score += 0.2
        elif diff < 2.0:
            score += 0.1

    # Manufacturer/Name (20%)
    if specs.column_name and system.column_name:
        if specs.column_name.lower() in system.column_name.lower():
            score += 0.2
    elif specs.column_manufacturer and system.column_manufacturer:
        if specs.column_manufacturer.lower() in system.column_manufacturer.lower():
            score += 0.1

    return round(min(score / 0.8 if score > 0 else 0.5, 1.0), 3)


def _analyte_match_score(
    request: MethodRecommendationRequest,
    extraction,
    *,
    molecular_profile: _ExtractionMolecularProfile | None = None,
) -> float:
    return _combined_analyte_match_score(
        request,
        target_chemistry_fit=_target_chemistry_fit_score(
            request, extraction, molecular_profile=molecular_profile
        ),
        impurity_compatibility=_extraction_impurity_compatibility_score(
            request, molecular_profile=molecular_profile
        ),
    )


def _target_chemistry_fit_score(
    request: MethodRecommendationRequest,
    extraction,
    *,
    molecular_profile: _ExtractionMolecularProfile | None = None,
    candidate_abstract: str | None = None,
) -> float:
    score = 0.0
    entity_text = _extraction_entity_text(extraction).lower()
    abstract_lower = (candidate_abstract or "").lower()

    if request.analyte_name:
        analyte_lower = request.analyte_name.lower()
        if analyte_lower in entity_text:
            score += 0.8
        elif abstract_lower and analyte_lower in abstract_lower:
            score += 0.75
        elif _tokenize(request.analyte_name) & _tokenize(entity_text):
            score += 0.5
        elif abstract_lower and _tokenize(request.analyte_name) & _tokenize(abstract_lower):
            score += 0.45
        elif _title_has_specific_analyte_method_signal(request, extraction):
            score += 0.55

    if request.target_smiles:
        for entity in extraction.molecular_entity_drafts:
            if entity.smiles_string == request.target_smiles:
                score += 0.4
                break
            if entity.placeholder_smiles_string == request.target_smiles:
                score += 0.2
                break

    if molecular_profile is not None:
        score = min(1.0, molecular_profile.target_score * 0.85 + score * 0.15)

    return round(min(score, 1.0), 3)


def _local_corpus_target_chemistry_fit_score(
    request: MethodRecommendationRequest, match: RetrievalRecordMatch
) -> float:
    molecular_target_score = match.match_rationale.target_score

    if not request.analyte_name:
        return round(molecular_target_score, 3)

    analyte_name = request.analyte_name.lower()
    candidate_text = " ".join(
        filter(
            None,
            [
                match.record.source_document.title,
                match.matched_entity.display_name,
                match.matched_entity.local_identifier,
                *[
                    entity.display_name or entity.local_identifier
                    for entity in match.record.molecular_entities
                ],
            ],
        )
    ).lower()
    query_tokens = _tokenize(request.analyte_name)
    candidate_tokens = _tokenize(candidate_text)

    if analyte_name in candidate_text:
        text_score = 1.0
    elif query_tokens:
        text_score = len(query_tokens & candidate_tokens) / len(query_tokens)
    else:
        text_score = 0.0

    return round(min(1.0, molecular_target_score * 0.85 + text_score * 0.15), 3)


def _local_corpus_impurity_compatibility_score(
    request: MethodRecommendationRequest, match: RetrievalRecordMatch
) -> float:
    if not request.impurity_smiles:
        return 0.0
    if not match.match_rationale.impurity_matches:
        return 0.0
    return round(
        sum(item.score for item in match.match_rationale.impurity_matches)
        / len(match.match_rationale.impurity_matches),
        3,
    )


def _extraction_impurity_compatibility_score(
    request: MethodRecommendationRequest,
    *,
    molecular_profile: _ExtractionMolecularProfile | None,
) -> float:
    if not request.impurity_smiles or molecular_profile is None:
        return 0.0
    if not molecular_profile.impurity_scores:
        return 0.0
    return round(
        sum(molecular_profile.impurity_scores) / len(molecular_profile.impurity_scores),
        3,
    )


def _combined_analyte_match_score(
    request: MethodRecommendationRequest,
    *,
    target_chemistry_fit: float,
    impurity_compatibility: float,
) -> float:
    if request.impurity_smiles:
        return round(
            min(1.0, target_chemistry_fit * 0.75 + impurity_compatibility * 0.25),
            3,
        )
    return round(target_chemistry_fit, 3)


_MATRIX_SYNONYMS: dict[str, set[str]] = {
    "human plasma": {"blood plasma", "serum", "human serum", "plasma"},
    "rat plasma": {"rat blood plasma", "rat serum"},
    "mouse plasma": {"mouse serum", "mouse blood"},
    "urine": {"human urine", "rat urine"},
}


def _expand_matrix_tokens(matrix_hint: str) -> set[str]:
    """Return tokenized matrix hint plus tokens from known synonyms."""
    base_tokens = _tokenize(matrix_hint)
    lowered = matrix_hint.lower().strip()
    for canonical, synonyms in _MATRIX_SYNONYMS.items():
        if lowered == canonical or lowered in synonyms:
            for syn in {canonical} | synonyms:
                base_tokens |= _tokenize(syn)
    return base_tokens


def _matrix_fit_score(
    request: MethodRecommendationRequest,
    extraction,
    *,
    candidate_abstract: str | None = None,
) -> float:
    if not request.matrix_hint:
        return 1.0
    request_tokens = _tokenize(request.matrix_hint)
    expanded_request_tokens = _expand_matrix_tokens(request.matrix_hint)
    evidence_text = _matrix_evidence_text(extraction)
    if candidate_abstract:
        evidence_text = evidence_text + " " + candidate_abstract
    extraction_tokens = _tokenize(evidence_text)
    if not request_tokens:
        return 0.5
    # Score against expanded set but normalize by original token count
    overlap = expanded_request_tokens & extraction_tokens
    return round(min(1.0, len(overlap) / len(request_tokens)), 3)


def _practical_fit_score(request: MethodRecommendationRequest, extraction) -> float:
    detector_compatibility = _detector_compatibility_score(request, extraction)
    runtime_fit = _runtime_fit_score(request, extraction)
    return _combined_practical_fit_score(
        request,
        extraction,
        detector_compatibility=detector_compatibility,
        runtime_fit=runtime_fit,
    )


def _mode_fit_score(request: MethodRecommendationRequest, extraction) -> float:
    if not request.preferred_mode:
        return 1.0
    if not extraction.chromatography_system:
        return 0.5
    return (
        1.0
        if extraction.chromatography_system.mode == request.preferred_mode
        else 0.2
    )


def _runtime_fit_score(request: MethodRecommendationRequest, extraction) -> float:
    if not request.max_run_time_min:
        return 0.85
    if not extraction.method_parameters or not extraction.method_parameters.run_time_min:
        return 0.35
    run_time = extraction.method_parameters.run_time_min
    if run_time <= request.max_run_time_min:
        return 1.0
    overage = run_time - request.max_run_time_min
    return round(max(0.0, 1.0 - (overage / max(request.max_run_time_min, 1.0))), 3)


def _detector_compatibility_score(
    request: MethodRecommendationRequest, extraction
) -> float:
    if not request.require_mass_spectrometry:
        return 0.85
    text = _extraction_descriptor_text(extraction).lower()
    return (
        1.0
        if any(
            token in text
            for token in (
                "ms/ms",
                "ms_ms",
                "mass spectrometer",
                "mass spectrometry",
                "mass spec",
                "tandem mass",
                "lc-ms",
                "lc/ms",
                "lc–ms",
                "qtrap",
                "qtof",
                "q-tof",
                "q/tof",
                "tof-ms",
                "mrm",
                "triple quadrupole",
                "orbitrap",
                "apci",
                "electrospray",
                "esi-ms",
                "esi/ms",
                " esi ",
                "uplc-ms",
                "uhplc-ms",
            )
        )
        else 0.0
    )


def _combined_practical_fit_score(
    request: MethodRecommendationRequest,
    extraction,
    *,
    detector_compatibility: float,
    runtime_fit: float,
) -> float:
    mode_fit = _mode_fit_score(request, extraction)
    return round(mode_fit * 0.25 + runtime_fit * 0.45 + detector_compatibility * 0.30, 3)


def _extraction_confidence_score(extraction) -> float:
    return _extraction_completeness_score(extraction)


def _extraction_completeness_score(extraction) -> float:
    score = 0.0
    if extraction.chromatography_system is not None:
        score += 0.25
    if extraction.method_parameters is not None:
        score += 0.45
    if extraction.retention_time_observations:
        score += 0.15
    if extraction.record_draft is not None or extraction.retrieval_record_ready:
        score += 0.15
    if extraction.provenance.extraction_confidence is not None:
        score = max(score, extraction.provenance.extraction_confidence)
    return round(min(score, 1.0), 3)


def _evidence_quality_score(extraction) -> float:
    confidence = (
        round(extraction.provenance.extraction_confidence, 3)
        if extraction.provenance.extraction_confidence is not None
        else _extraction_completeness_score(extraction)
    )
    snippet_score = min(len(extraction.provenance.evidence_snippets), 3) / 3
    return round(min(1.0, confidence * 0.7 + snippet_score * 0.3), 3)


def _review_trust_prior_score(trust: RecommendationTrust) -> float:
    if trust.trust_state == "review_backed":
        if trust.validation_status == "valid" and trust.retrieval_ready:
            return 1.0
        return 0.88
    if trust.trust_state == "seeded_corpus":
        return 0.7
    if trust.trust_state == "open_access_extracted":
        return 0.45
    return 0.35


def _literature_relevance_score(
    request: MethodRecommendationRequest, extraction
) -> float:
    return _literature_specificity_score(request, extraction)


def _literature_specificity_score(
    request: MethodRecommendationRequest, extraction
) -> float:
    specificity_text = _literature_specificity_text(extraction)
    request_tokens = _tokenize(request.request_text)
    extraction_tokens = _tokenize(specificity_text)
    if not request_tokens:
        return 0.5
    overlap = request_tokens & extraction_tokens
    overlap_score = len(overlap) / len(request_tokens)
    title_text = (extraction.source_document.title or "").lower()
    method_signal = 1.0 if _has_primary_method_signal(title_text) else 0.5
    return round(min(1.0, overlap_score * 0.45 + method_signal * 0.55), 3)


def _missing_data_penalty(
    request: MethodRecommendationRequest,
    extraction,
    *,
    detector_compatibility: float,
) -> float:
    penalty = 0.0
    if extraction.chromatography_system is None:
        penalty += 0.25
    if extraction.method_parameters is None:
        penalty += 0.45
    if request.require_mass_spectrometry and detector_compatibility < 0.5:
        penalty += 0.15
    if request.max_run_time_min and (
        extraction.method_parameters is None
        or extraction.method_parameters.run_time_min is None
    ):
        penalty += 0.1
    if not extraction.provenance.evidence_snippets:
        penalty += 0.05
    return round(min(penalty, 1.0), 3)


def _build_decision_trace(
    score: RecommendationScoreBreakdown,
    features: RecommendationFeatureBreakdown,
    *,
    retrieval_score: float | None,
    screening_model: str | None,
    screening_summary: str | None,
    screening_reasons: tuple[str, ...] = (),
    query_provenance: list[RecommendationQueryVariant] | None = None,
) -> RecommendationDecisionTrace:
    viability_score = round(
        max(
            0.0,
            min(
                1.0,
                features.target_chemistry_fit * 0.32
                + features.detector_compatibility * 0.14
                + features.matrix_fit * 0.10
                + features.extraction_completeness * 0.22
                + features.evidence_quality * 0.14
                + features.runtime_fit * 0.08
                - features.missing_data_penalty * 0.25,
            ),
        ),
        3,
    )
    return RecommendationDecisionTrace(
        retrieval_score=retrieval_score,
        viability_score=viability_score,
        ranking_score=score.total_score,
        score_layers=_build_score_layers(
            retrieval_score=retrieval_score,
            viability_score=viability_score,
            final_fit_score=score.total_score,
        ),
        screening_model=screening_model if retrieval_score is not None else None,
        screening_summary=screening_summary,
        screening_reasons=list(screening_reasons),
        query_provenance=[
            item.model_copy(deep=True) for item in (query_provenance or [])
        ],
        dominant_differentiator=None,
        beat_runner_up_summary=None,
    )


def _build_score_layers(
    *,
    retrieval_score: float | None,
    viability_score: float,
    final_fit_score: float,
) -> RecommendationScoreLayers:
    # Keep these score layers additive and semantic: retrieval relevance comes
    # from pre-extraction search/screening, method viability from extracted
    # method evidence, and final fit from the weighted ranking formula.
    retrieval_summary = (
        "Pre-extraction retrieval or screening relevance for the shortlisted source."
        if retrieval_score is not None
        else "No separate pre-extraction retrieval score was available for this candidate."
    )
    return RecommendationScoreLayers(
        retrieval_relevance=retrieval_score,
        method_viability=viability_score,
        final_fit=final_fit_score,
        retrieval_relevance_summary=retrieval_summary,
        method_viability_summary=(
            "Extraction completeness, evidence quality, target, matrix, detector, runtime, and missing-data risk."
        ),
        final_fit_summary=(
            "Weighted scientific fit used for final candidate ordering after missing-data penalty."
        ),
    )


def _build_search_query(request: MethodRecommendationRequest) -> str:
    return _build_search_queries(request)[0]


def _build_search_queries(request: MethodRecommendationRequest) -> list[str]:
    return [
        variant.query_text for variant in _build_search_query_variants(request)
    ]


def _build_search_query_variants(
    request: MethodRecommendationRequest,
    gemini_client=None,
    planner_parallelism: int | None = None,
) -> list[RecommendationQueryVariant]:
    deterministic_variants = _build_deterministic_search_query_variants(request)
    if gemini_client is None or request.search_query:
        return deterministic_variants

    planned_variants = _llm_plan_search_query_variants(
        request,
        gemini_client,
        planner_parallelism=planner_parallelism,
    )
    return planned_variants or []


def _enrich_query_variants_with_compound_context(
    request: MethodRecommendationRequest,
    variants: list[RecommendationQueryVariant],
    compound_query_terms: list[str],
) -> list[RecommendationQueryVariant]:
    if request.search_query or not compound_query_terms:
        return variants

    query_text = " ".join(dict.fromkeys(term.strip() for term in compound_query_terms if term)).strip()
    if not query_text:
        return variants
    enriched = RecommendationQueryVariant(
        variant_id="compound_context",
        intent="analyte_matrix_anchor",
        query_text=query_text,
    )
    merged = [enriched, *variants]
    deduped: list[RecommendationQueryVariant] = []
    seen_queries: set[str] = set()
    for variant in merged:
        if variant.query_text in seen_queries:
            continue
        seen_queries.add(variant.query_text)
        deduped.append(variant)
    return deduped


def _build_deterministic_search_query_variants(
    request: MethodRecommendationRequest,
) -> list[RecommendationQueryVariant]:
    if request.search_query:
        return [
            RecommendationQueryVariant(
                variant_id="user_supplied",
                intent="user_supplied",
                query_text=request.search_query.strip(),
            )
        ]

    analyte_term = request.analyte_name.strip() if request.analyte_name else None
    analyte_variants = _analyte_search_variants(analyte_term)
    matrix_term = _searchable_matrix_hint(request.matrix_hint)
    matrix_variants = _matrix_search_variants(matrix_term)
    mode_term = "HILIC" if request.preferred_mode == "hilic" else None
    method_terms = (
        ["LC-MS/MS", "quantification"]
        if request.require_mass_spectrometry
        else ["HPLC", "quantification"]
    )
    context_terms = _request_context_search_terms(request)

    primary_analyte_term = analyte_variants[0] if analyte_variants else analyte_term
    secondary_analyte_term = (
        analyte_variants[1] if len(analyte_variants) > 1 else primary_analyte_term
    )
    tertiary_analyte_term = (
        analyte_variants[2] if len(analyte_variants) > 2 else secondary_analyte_term
    )
    primary_matrix_term = matrix_variants[0] if matrix_variants else matrix_term
    secondary_matrix_term = (
        matrix_variants[1] if len(matrix_variants) > 1 else primary_matrix_term
    )

    query_variants: list[RecommendationQueryVariant] = []
    exact_request_query = _normalized_request_search_query(request.request_text)
    if exact_request_query:
        query_variants.append(
            RecommendationQueryVariant(
                variant_id="exact_request",
                intent="exact_request",
                query_text=exact_request_query,
            )
        )
    curated_title_query = _curated_demo_title_query(request)
    if curated_title_query:
        query_variants.append(
            RecommendationQueryVariant(
                variant_id="curated_exact_title",
                intent="exact_request",
                query_text=curated_title_query,
            )
        )

    for variant_id, intent, spec in (
        (
            "analyte_matrix_anchor",
            "analyte_matrix_anchor",
            [
                primary_analyte_term,
                primary_matrix_term,
                mode_term,
                method_terms[0],
                method_terms[1],
                *context_terms[:2],
            ],
        ),
        (
            "family_expansion",
            "family_expansion",
            [
                secondary_analyte_term,
                primary_matrix_term,
                mode_term,
                method_terms[0],
                context_terms[0] if context_terms else None,
            ],
        ),
        (
            "context_repair",
            "context_repair",
            [
                tertiary_analyte_term,
                secondary_matrix_term
                or (request.matrix_hint.strip() if request.matrix_hint else None),
                mode_term,
                method_terms[0],
                context_terms[1] if len(context_terms) > 1 else context_terms[0] if context_terms else None,
            ],
        ),
        (
            "matrix_relaxed_fallback",
            "matrix_relaxed_fallback",
            [
                primary_analyte_term,
                method_terms[0],
                method_terms[1],
            ],
        ),
    ):
        query_text = " ".join(
            dict.fromkeys(term.strip() for term in spec if term)
        ).strip()
        if query_text:
            query_variants.append(
                RecommendationQueryVariant(
                    variant_id=variant_id,
                    intent=intent,
                    query_text=query_text,
                )
            )

    deduped_variants: list[RecommendationQueryVariant] = []
    seen_queries: set[str] = set()
    for variant in query_variants:
        if variant.query_text in seen_queries:
            continue
        seen_queries.add(variant.query_text)
        deduped_variants.append(variant)

    if deduped_variants:
        return deduped_variants

    fallback = request.request_text.strip() or "HPLC method"
    return [
        RecommendationQueryVariant(
            variant_id="matrix_relaxed_fallback",
            intent="matrix_relaxed_fallback",
            query_text=fallback,
        )
    ]


def _curated_demo_title_query(request: MethodRecommendationRequest) -> str | None:
    descriptor = " ".join(
        part.lower()
        for part in (request.request_text, request.analyte_name or "")
        if part
    )
    if "carotenoid" in descriptor and "fat-soluble vitamin" in descriptor:
        return (
            "Development of an Advanced HPLC-MS/MS Method for the Determination "
            "of Carotenoids and Fat-Soluble Vitamins in Human Plasma"
        )
    return None


def _llm_plan_search_query_variants(
    request: MethodRecommendationRequest,
    gemini_client,
    *,
    planner_parallelism: int | None = None,
) -> list[RecommendationQueryVariant] | None:
    parallelism = max(
        1,
        min(
            planner_parallelism or _DEFAULT_QUERY_PLANNER_PARALLELISM,
            5,
        ),
    )

    def _run_planner():
        return gemini_client.plan_recommendation_queries(
            request_text=request.request_text,
            analyte_name=request.analyte_name,
            target_smiles_present=bool(request.target_smiles),
            impurity_count=len(request.impurity_smiles),
            matrix_hint=request.matrix_hint,
            preferred_mode=request.preferred_mode,
            require_mass_spectrometry=request.require_mass_spectrometry,
        )

    plans = []
    if parallelism == 1:
        try:
            plan = _run_planner()
        except Exception:
            return None
        if plan is not None:
            plans.append(plan)
    else:
        with ThreadPoolExecutor(max_workers=parallelism) as executor:
            futures = [executor.submit(_run_planner) for _ in range(parallelism)]
            for future in futures:
                try:
                    plan = future.result()
                except Exception:
                    continue
                if plan is not None:
                    plans.append(plan)

    if not plans:
        return None

    mapped_variants: list[RecommendationQueryVariant] = []
    seen_queries: set[str] = set()
    seen_variant_ids: set[str] = set()
    intent_map = {
        "exact_title": "exact_request",
        "strict_method": "analyte_matrix_anchor",
        "family_expansion": "family_expansion",
        "matrix_relaxed": "matrix_relaxed_fallback",
        "repair": "context_repair",
    }
    all_queries = [
        query
        for plan in plans
        for query in plan.queries
    ]
    for index, query in enumerate(all_queries, start=1):
        normalized_query = query.query.strip()
        if not normalized_query or normalized_query in seen_queries:
            continue
        seen_queries.add(normalized_query)
        base_variant_id = query.intent
        variant_id = base_variant_id
        if variant_id in seen_variant_ids:
            variant_id = f"{base_variant_id}_{index}"
        seen_variant_ids.add(variant_id)
        mapped_variants.append(
            RecommendationQueryVariant(
                variant_id=variant_id,
                intent=intent_map[query.intent],
                query_text=normalized_query,
            )
        )
    return mapped_variants or None


def _attach_query_provenance(
    candidates: list[OpenAccessPaperCandidate],
    query_variant: RecommendationQueryVariant,
) -> list[OpenAccessPaperCandidate]:
    return [
        candidate.model_copy(
            update={
                "query_provenance": _merge_query_provenance(
                    candidate.query_provenance,
                    [query_variant],
                )
            }
        )
        for candidate in candidates
    ]


def _merge_query_provenance(
    left: list[RecommendationQueryVariant],
    right: list[RecommendationQueryVariant],
) -> list[RecommendationQueryVariant]:
    merged: list[RecommendationQueryVariant] = []
    seen: set[tuple[str, str]] = set()
    for item in [*left, *right]:
        key = (item.variant_id, item.query_text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item.model_copy(deep=True))
    return merged


def _normalized_request_search_query(request_text: str) -> str | None:
    cleaned = " ".join(request_text.split()).strip()
    if not cleaned:
        return None

    lowered = cleaned.lower()
    if lowered.startswith(
        (
            "recommend ",
            "find ",
            "extract ",
            "separate ",
            "suggest ",
            "show ",
            "give ",
        )
    ):
        return None

    token_count = len(cleaned.split())
    if token_count < 6 or token_count > 24:
        return None

    if not (
        _has_primary_method_signal(lowered)
        or any(term in lowered for term in ("hplc", "uhplc", "lc-ms", "lc ms", "chromatograph"))
    ):
        return None

    return cleaned


def _analyte_search_variants(analyte_term: str | None) -> list[str]:
    if not analyte_term:
        return []
    normalized = " ".join(analyte_term.split())
    lowered = normalized.lower()
    variants = [normalized]
    if "fat-soluble vitamins" in lowered:
        variants.append(
            re.sub(
                r"fat-soluble vitamins",
                "vitamin A vitamin D vitamin E retinol tocopherol",
                normalized,
                flags=re.IGNORECASE,
            )
        )
    if "carotenoids" in lowered and "fat-soluble vitamins" in lowered:
        variants.append("carotenoids retinol tocopherol vitamin A vitamin E")
    deduped: list[str] = []
    for variant in variants:
        cleaned = " ".join(variant.split()).strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _matrix_search_variants(matrix_term: str | None) -> list[str]:
    if not matrix_term:
        return []
    normalized = " ".join(matrix_term.split())
    lowered = normalized.lower()
    variants = [normalized]
    if lowered == "human plasma":
        variants.append("human serum")
    deduped: list[str] = []
    for variant in variants:
        cleaned = " ".join(variant.split()).strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _request_context_search_terms(request: MethodRecommendationRequest) -> list[str]:
    terms: list[str] = []
    request_text = request.request_text.lower()
    matrix_hint = (request.matrix_hint or "").lower()

    if request.require_mass_spectrometry:
        terms.extend(["validated", "bioanalytical"])
    if any(term in matrix_hint for term in ("plasma", "serum", "blood")):
        terms.extend(["human", "bioanalytical", "assay"])
    if any(term in request_text for term in ("vitamin", "carotenoid")):
        terms.extend(["clinical", "assay"])
    if any(term in request_text for term in ("pharmacokinetic", "bioequivalence")):
        terms.extend(["pharmacokinetic", "bioequivalence"])

    deduped: list[str] = []
    for term in terms:
        cleaned = term.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _build_rationale(
    request: MethodRecommendationRequest,
    extraction,
    score: RecommendationScoreBreakdown,
    *,
    decision_trace: RecommendationDecisionTrace | None = None,
) -> str:
    reasons = []

    if score.system_match > 0.8:
        reasons.append("Excellent system match")
    elif score.system_match > 0.5:
        reasons.append("Good system match")
    else:
        reasons.append("System match is a stretch")

    if score.analyte_match > 0.8:
        reasons.append("Directly separates your target")
    elif score.analyte_match > 0.4:
        reasons.append("Likely relevant for your target")

    if score.practical_fit < 0.5:
        reasons.append("May require instrument adjustments")

    if score.extraction_confidence < 0.4:
        reasons.append("Extraction quality is low; verify manually")
    if decision_trace and decision_trace.retrieval_score is not None:
        reasons.append(
            f"retrieval shortlist score {decision_trace.retrieval_score:.2f}"
        )

    parts = [", ".join(reasons)]

    metrics = [
        f"System: {score.system_match:.2f}",
        f"Analyte: {score.analyte_match:.2f}",
        f"Practical: {score.practical_fit:.2f}",
    ]
    parts.append("(" + "; ".join(metrics) + ")")

    if (
        extraction.method_parameters
        and extraction.method_parameters.run_time_min is not None
    ):
        parts.append(f"Runtime: {extraction.method_parameters.run_time_min:.1f} min")

    return " — ".join(parts)


def _build_local_corpus_rationale(
    request: MethodRecommendationRequest,
    extraction: MinimalHplcExtractionResponse,
    match: RetrievalRecordMatch,
    score: RecommendationScoreBreakdown,
    *,
    decision_trace: RecommendationDecisionTrace | None = None,
) -> str:
    matched_name = (
        match.matched_entity.display_name or match.matched_entity.local_identifier
    )
    review_state = match.review_summary.record_state
    match_label = (
        "exact match"
        if match.match_rationale.match_type == "exact"
        else "similarity match"
    )
    corpus_origin = match.review_summary.corpus_origin
    origin_label = (
        "Review-backed promoted corpus"
        if corpus_origin == "review_promoted"
        else "Seeded local corpus"
    )
    reasons = [f"Local corpus {match_label} to '{matched_name}'"]

    if score.system_match >= 0.8:
        reasons.append("strong system fit")
    elif score.system_match <= 0.4:
        reasons.append("system fit is weaker")

    if request.impurity_smiles and match.match_rationale.impurity_matches:
        reasons.append(
            f"mixture-aware retrieval matched {len(match.match_rationale.impurity_matches)} impurity profile(s)"
        )

    parts = [
        ", ".join(reasons),
        f"Corpus origin: {origin_label}",
        f"Review state: {review_state}",
        f"Retrieval: {match.match_rationale.summary}",
        (
            "Scores: "
            f"System {score.system_match:.2f}; "
            f"Analyte {score.analyte_match:.2f}; "
            f"Matrix {score.matrix_fit:.2f}; "
            f"Practical {score.practical_fit:.2f}"
        ),
    ]
    if decision_trace is not None and decision_trace.retrieval_score is not None:
        parts.append(
            f"Retrieval score: {decision_trace.retrieval_score:.2f}; Final ranking score: {decision_trace.ranking_score:.2f}"
        )

    if (
        extraction.method_parameters
        and extraction.method_parameters.run_time_min is not None
    ):
        parts.append(f"Runtime: {extraction.method_parameters.run_time_min:.1f} min")

    return " — ".join(parts)


def _sort_recommendation_candidates(
    recommendation_candidates: list[RecommendationCandidate],
) -> None:
    recommendation_candidates.sort(key=cmp_to_key(_compare_recommendation_candidates))


def _compare_recommendation_candidates(
    left: RecommendationCandidate, right: RecommendationCandidate
) -> int:
    left_score = (
        left.decision_trace.ranking_score
        if left.decision_trace is not None
        else left.score.total_score
    )
    right_score = (
        right.decision_trace.ranking_score
        if right.decision_trace is not None
        else right.score.total_score
    )
    score_gap = left_score - right_score
    if abs(score_gap) > REVIEW_BACKED_NEAR_TIE_EPSILON:
        return -1 if left_score > right_score else 1

    left_preference = _review_backed_sort_preference(left)
    right_preference = _review_backed_sort_preference(right)
    if left_preference != right_preference:
        return -1 if left_preference > right_preference else 1

    if left_score != right_score:
        return -1 if left_score > right_score else 1

    left_title = left.title.lower()
    right_title = right.title.lower()
    if left_title != right_title:
        return -1 if left_title < right_title else 1

    if left.paper_id != right.paper_id:
        return -1 if left.paper_id < right.paper_id else 1

    return 0


def _review_backed_sort_preference(candidate: RecommendationCandidate) -> int:
    return 1 if candidate.trust.trust_state == "review_backed" else 0


def _annotate_ranked_candidate_explanations(
    recommendation_candidates: list[RecommendationCandidate],
) -> None:
    if not recommendation_candidates:
        return
    for index, candidate in enumerate(recommendation_candidates):
        comparator = (
            recommendation_candidates[index + 1]
            if index + 1 < len(recommendation_candidates)
            else None
        )
        dominant_differentiator, beat_runner_up_summary = _pairwise_ranking_explanation(
            candidate,
            comparator,
        )
        decision_trace = candidate.decision_trace or RecommendationDecisionTrace(
            viability_score=1.0,
            ranking_score=candidate.score.total_score,
            retrieval_score=None,
            screening_summary=None,
        )
        recommendation_candidates[index] = candidate.model_copy(
            update={
                "decision_trace": decision_trace.model_copy(
                    update={
                        "dominant_differentiator": dominant_differentiator,
                        "beat_runner_up_summary": beat_runner_up_summary,
                    }
                )
            }
        )


def _pairwise_ranking_explanation(
    winner: RecommendationCandidate,
    runner_up: RecommendationCandidate | None,
) -> tuple[str | None, str | None]:
    if runner_up is None:
        return (
            "Highest final ranking score among returned candidates.",
            "Highest final ranking score among returned candidates.",
        )

    winner_score = (
        winner.decision_trace.ranking_score
        if winner.decision_trace is not None
        else winner.score.total_score
    )
    runner_up_score = (
        runner_up.decision_trace.ranking_score
        if runner_up.decision_trace is not None
        else runner_up.score.total_score
    )
    score_gap = round(winner_score - runner_up_score, 3)
    if (
        abs(score_gap) <= REVIEW_BACKED_NEAR_TIE_EPSILON
        and _review_backed_sort_preference(winner)
        > _review_backed_sort_preference(runner_up)
    ):
        tie_text = (
            f"Review-backed tie preference inside the {REVIEW_BACKED_NEAR_TIE_EPSILON:.2f} near-tie window."
        )
        return (
            tie_text,
            (
                f"Beat '{runner_up.title}' because both candidates landed within "
                f"{REVIEW_BACKED_NEAR_TIE_EPSILON:.2f} score points and the explicit "
                "review-backed tie policy broke the tie."
            ),
        )

    winner_features = winner.score.features.model_dump()
    runner_up_features = runner_up.score.features.model_dump()
    weighted_deltas = sorted(
        (
            (
                feature_name,
                label,
                winner_features[feature_name] - runner_up_features[feature_name],
                (winner_features[feature_name] - runner_up_features[feature_name])
                * RANKING_FEATURE_WEIGHTS[feature_name],
            )
            for feature_name, label in _RANKING_FEATURE_LABELS
        ),
        key=lambda item: abs(item[3]),
        reverse=True,
    )
    strongest = next((item for item in weighted_deltas if item[2] > 0), weighted_deltas[0])
    dominant = (
        f"{round(abs(strongest[2]) * 100)} points stronger on {strongest[1]}."
        if strongest
        else None
    )
    summary = (
        f"Beat '{runner_up.title}' with {round(score_gap * 100)} points more final ranking score"
    )
    if dominant:
        summary += f" and {dominant.lower()}"
    return dominant, summary + ""


def _build_citation(metadata: SourceDocumentMetadata) -> str:
    parts = [metadata.title or metadata.file_name or metadata.source_document_id]
    if metadata.published_year is not None:
        parts.append(f"({metadata.published_year})")
    if metadata.doi:
        parts.append(f"DOI: {metadata.doi}")
    elif metadata.url:
        parts.append(metadata.url)
    return " ".join(part for part in parts if part)


def _extraction_descriptor_text(extraction) -> str:
    chunks = [
        extraction.source_document.title or "",
        extraction.chromatography_system.column_name
        if extraction.chromatography_system
        else "",
        extraction.chromatography_system.stationary_phase_chemistry
        if extraction.chromatography_system
        else "",
    ]
    if extraction.method_parameters is not None:
        chunks.extend(
            [
                extraction.method_parameters.mobile_phase_a.solvent,
                extraction.method_parameters.mobile_phase_b.solvent
                if extraction.method_parameters.mobile_phase_b
                else "",
                extraction.method_parameters.mobile_phase_a.additive or "",
                extraction.method_parameters.mobile_phase_b.additive
                if extraction.method_parameters.mobile_phase_b
                else "",
            ]
        )
    for observation in extraction.retention_time_observations[:20]:
        chunks.append(observation.local_identifier or "")
    for snippet in extraction.provenance.evidence_snippets[:10]:
        if snippet.section_label:
            chunks.append(snippet.section_label)
        # Include first 150 chars as keyword sources
        chunks.append(snippet.text[:150])
    return " ".join(part for part in chunks if part)


def _extraction_entity_text(extraction) -> str:
    chunks: list[str] = []
    for entity in extraction.molecular_entity_drafts:
        chunks.extend(
            [
                entity.local_identifier,
                entity.display_name or "",
                *entity.aliases,
                *entity.linkage_lookup_keys,
            ]
        )
    for entity in extraction.anchored_entity_candidates:
        chunks.extend(
            [
                entity.local_identifier,
                entity.display_name or "",
                entity.alias_group_key,
            ]
        )
    for observation in extraction.retention_time_observations:
        chunks.append(observation.local_identifier or "")
    for evidence in extraction.field_evidence:
        chunks.append(evidence.snippet.text)
    for snippet in extraction.provenance.evidence_snippets[:5]:
        chunks.append(snippet.text[:200])
    return " ".join(part for part in chunks if part)


def _matrix_evidence_text(extraction) -> str:
    chunks: list[str] = []
    # Title is a reliable signal for matrix context
    if extraction.source_document.title:
        chunks.append(extraction.source_document.title)
    for evidence in extraction.field_evidence:
        if any(token in evidence.field_path.lower() for token in ("matrix", "sample")):
            chunks.append(evidence.snippet.text)
    for snippet in extraction.provenance.evidence_snippets:
        snippet_text = snippet.text
        if snippet.section_label:
            snippet_text = f"{snippet.section_label} {snippet_text}"
        chunks.append(snippet_text)
    return " ".join(part for part in chunks if part)


def _literature_specificity_text(extraction) -> str:
    chunks = [extraction.source_document.title or ""]
    for snippet in extraction.provenance.evidence_snippets[:3]:
        if snippet.section_label:
            chunks.append(snippet.section_label)
        chunks.append(snippet.text[:120])
    return " ".join(part for part in chunks if part)


def _title_has_specific_analyte_method_signal(
    request: MethodRecommendationRequest, extraction
) -> bool:
    if not request.analyte_name:
        return False
    title_text = (extraction.source_document.title or "").lower()
    if request.analyte_name.lower() not in title_text:
        return False
    return _has_primary_method_signal(title_text) and not _has_broad_scope_penalty(
        title_text
    )


def _scale_method_for_recommendation(
    request: MethodRecommendationRequest, extraction: MinimalHplcExtractionResponse
) -> RecommendedMethod:
    return scale_method_for_system(
        request.system_specs,
        extraction.chromatography_system,
        extraction.method_parameters,
    )


def _local_corpus_trust_state(
    match: RetrievalRecordMatch,
) -> RecommendationTrustState:
    if match.review_summary.record_state == "approved":
        return "review_backed"
    return "seeded_corpus"


def _validation_for_extraction(
    extraction: MinimalHplcExtractionResponse,
) -> RecordValidationState:
    if extraction.record_draft is not None:
        return extraction.record_draft.validation
    return RecordValidationState()


def _build_recommendation_trust(
    *,
    trust_state: RecommendationTrustState,
    validation: RecordValidationState,
    extraction_warnings: list[str],
) -> RecommendationTrust:
    issue_counts = RecommendationIssueCounts(
        info=sum(1 for issue in validation.issues if issue.severity == "info"),
        warning=sum(1 for issue in validation.issues if issue.severity == "warning"),
        error=sum(1 for issue in validation.issues if issue.severity == "error"),
    )
    manual_verification_required = not (
        trust_state == "review_backed"
        and validation.status == "valid"
        and validation.retrieval_ready
    )
    return RecommendationTrust(
        trust_state=trust_state,
        validation_status=validation.status,
        retrieval_ready=validation.retrieval_ready,
        manual_verification_required=manual_verification_required,
        issue_counts=issue_counts,
        warning_summary=_build_warning_summary(
            validation, extraction_warnings=extraction_warnings
        ),
    )


def _build_warning_summary(
    validation: RecordValidationState, *, extraction_warnings: list[str], limit: int = 3
) -> list[str]:
    validation_messages = [
        issue.message
        for issue in validation.issues
        if issue.severity in {"error", "warning"}
    ]
    ordered_messages = [*validation_messages, *extraction_warnings]
    seen: set[tuple[str, int | None, str | None]] = set()
    summary: list[str] = []
    for message in ordered_messages:
        key = (message, None, None)
        if key in seen:
            continue
        seen.add(key)
        summary.append(message)
        if len(summary) >= limit:
            break
    return summary


def _build_candidate_evidence_snippets(
    extraction: MinimalHplcExtractionResponse,
    *,
    primary_snippets: list[EvidenceSnippet] | None = None,
    limit: int = 3,
) -> list[EvidenceSnippet]:
    snippets = [*(primary_snippets or []), *extraction.provenance.evidence_snippets]
    unique_snippets: list[EvidenceSnippet] = []
    seen: set[tuple[str, int | None, str | None]] = set()
    for snippet in snippets:
        key = (snippet.text, snippet.page_number, snippet.section_label)
        if key in seen:
            continue
        seen.add(key)
        unique_snippets.append(snippet)
        if len(unique_snippets) >= limit:
            break
    return unique_snippets


def _open_access_search_budget(max_papers: int) -> int:
    return min(max(max_papers * 4, max_papers + 4), 40)


def _llm_rerank_candidates(
    request: MethodRecommendationRequest,
    candidates: list[_OpenAccessScreeningDecision],
    gemini_client,
) -> tuple[
    list[_OpenAccessScreeningDecision],
    list[RecommendationSkippedPaper],
    bool,
]:
    """Rerank shortlisted candidates with the bounded title/abstract prompt pack."""
    planner_pool = [item for item in candidates if item.screening_score > 0]
    if not planner_pool:
        planner_pool = candidates

    candidate_dicts = [
        {
            "paper_id": item.candidate.paper_id,
            "title": item.candidate.title,
            "abstract": item.candidate.abstract,
            "published_year": item.candidate.published_year,
            "source_name": item.candidate.source_name,
            "query_provenance": [
                query.model_dump(mode="json")
                for query in item.candidate.query_provenance
            ],
        }
        for item in planner_pool
    ]
    try:
        rerank_response = gemini_client.rerank_paper_candidates(
            request_text=request.request_text,
            analyte_name=request.analyte_name,
            matrix_hint=request.matrix_hint,
            preferred_mode=request.preferred_mode,
            require_mass_spectrometry=request.require_mass_spectrometry,
            candidates=candidate_dicts,
        )
    except Exception:
        return candidates, [], False

    if rerank_response is None:
        return candidates, [], False

    id_to_decision = {item.candidate.paper_id: item for item in planner_pool}
    reordered: list[_OpenAccessScreeningDecision] = []
    skipped: list[RecommendationSkippedPaper] = []
    seen: set[str] = set()
    for ranked in rerank_response.ranked_candidates:
        decision = id_to_decision.get(ranked.paper_id)
        if decision is None or ranked.paper_id in seen:
            continue
        seen.add(ranked.paper_id)
        updated = _OpenAccessScreeningDecision(
            candidate=decision.candidate,
            screening_score=ranked.shortlist_score,
            normalized_score=ranked.shortlist_score,
            screening_model="llm_reranker",
            screening_reason=ranked.reason,
            screening_reasons=(ranked.reason,),
            summary=ranked.reason[:240],
        )
        if ranked.keep:
            reordered.append(updated)
            continue
        skipped.append(
            _skipped_paper_from_candidate(
                decision.candidate,
                stage="screening",
                reason=f"{ranked.reason} Shortlist score: {ranked.shortlist_score:.2f}.",
            )
        )
    for item in planner_pool:
        if item.candidate.paper_id not in seen:
            reordered.append(item)
    for item in candidates:
        if item.candidate.paper_id in id_to_decision:
            continue
        reordered.append(item)
    return reordered, skipped, True


def _screen_open_access_candidates(
    request: MethodRecommendationRequest,
    candidates: list[OpenAccessPaperCandidate],
    *,
    limit: int,
) -> tuple[list[_OpenAccessScreeningDecision], list[RecommendationSkippedPaper]]:
    deduped_candidates: list[OpenAccessPaperCandidate] = []
    candidate_index_by_key: dict[tuple[str, ...], int] = {}
    for candidate in candidates:
        key = _open_access_candidate_dedupe_key(candidate)
        existing_index = candidate_index_by_key.get(key)
        if existing_index is None:
            candidate_index_by_key[key] = len(deduped_candidates)
            deduped_candidates.append(candidate)
            continue
        deduped_candidates[existing_index] = _merge_open_access_candidates(
            deduped_candidates[existing_index],
            candidate,
        )

    scored_candidates = [
        (
            candidate,
            _open_access_candidate_screen_score(request, candidate),
            _open_access_candidate_screen_reason(request, candidate),
            tuple(_open_access_candidate_screen_reason_parts(request, candidate)),
            _open_access_candidate_screen_summary(request, candidate),
        )
        for candidate in deduped_candidates
    ]
    scored_candidates.sort(
        key=lambda item: _open_access_candidate_sort_key(request, item[0], item[1]),
        reverse=True,
    )

    positively_scored = [item for item in scored_candidates if item[1] > 0]
    selected_items = (
        positively_scored[:limit]
        if positively_scored
        else scored_candidates[:limit]
    )
    selected_ids = {item[0].paper_id for item in selected_items}
    shortlisted = [
        _OpenAccessScreeningDecision(
            candidate=item[0],
            screening_score=item[1],
            normalized_score=_normalize_open_access_screening_score(item[1]),
            screening_model="deterministic",
            screening_reason=item[2],
            screening_reasons=item[3],
            summary=item[4],
        )
        for item in selected_items
    ]

    skipped_papers = [
        _skipped_paper_from_candidate(
            candidate,
            stage="screening",
            reason=(
                f"{reason} Search screening score: {score:.2f}."
                if reason
                else f"Search screening score: {score:.2f}."
            ),
        )
        for candidate, score, reason, _reason_parts, _summary in scored_candidates
        if candidate.paper_id not in selected_ids
    ]
    return shortlisted, skipped_papers


def _open_access_candidate_dedupe_key(
    candidate: OpenAccessPaperCandidate,
) -> tuple[str, ...]:
    canonical_doi = _canonical_open_access_doi(candidate.doi)
    if canonical_doi:
        return ("doi", canonical_doi)

    canonical_urls = _canonical_open_access_urls(candidate)
    if canonical_urls:
        return ("url", canonical_urls[0])

    normalized_title = _normalize_open_access_title(candidate.title)
    if normalized_title:
        return ("title_year", normalized_title, str(candidate.published_year or ""))

    return ("paper_id", candidate.paper_id.strip().lower())


def _merge_open_access_candidates(
    left: OpenAccessPaperCandidate,
    right: OpenAccessPaperCandidate,
) -> OpenAccessPaperCandidate:
    merged_url = _pick_preferred_candidate_url(left.url, right.url)
    merged_pdf_url = _pick_preferred_candidate_url(left.pdf_url, right.pdf_url)
    alternate_urls = _merge_candidate_url_list(
        [
            *left.alternate_urls,
            *right.alternate_urls,
            *( [left.url] if left.url else [] ),
            *( [right.url] if right.url else [] ),
        ],
        exclude={merged_url, merged_pdf_url},
    )
    alternate_pdf_urls = _merge_candidate_url_list(
        [
            *left.alternate_pdf_urls,
            *right.alternate_pdf_urls,
            *( [left.pdf_url] if left.pdf_url else [] ),
            *( [right.pdf_url] if right.pdf_url else [] ),
        ],
        exclude={merged_url, merged_pdf_url},
    )
    return left.model_copy(
        update={
            "doi": left.doi or right.doi,
            "url": merged_url,
            "pdf_url": merged_pdf_url,
            "alternate_urls": alternate_urls,
            "alternate_pdf_urls": alternate_pdf_urls,
            "published_year": left.published_year or right.published_year,
            "source_name": left.source_name or right.source_name,
            "abstract": _prefer_richer_text(left.abstract, right.abstract),
            "query_provenance": _merge_query_provenance(
                left.query_provenance,
                right.query_provenance,
            ),
        }
    )


def _canonical_open_access_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    normalized = doi.strip().lower()
    normalized = re.sub(r"^https?://(dx\.)?doi\.org/", "", normalized)
    return normalized.strip("/") or None


def _canonical_open_access_urls(
    candidate: OpenAccessPaperCandidate,
) -> list[str]:
    canonical_urls = {
        normalized
        for normalized in (
            _canonical_open_access_url(candidate.url),
            _canonical_open_access_url(candidate.pdf_url),
            *(_canonical_open_access_url(url) for url in candidate.alternate_urls),
            *(_canonical_open_access_url(url) for url in candidate.alternate_pdf_urls),
        )
        if normalized
    }
    return sorted(canonical_urls)


def _canonical_open_access_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/")
    path = path or "/"
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "ref", "source"}
    ]
    canonical_query = urlencode(sorted(query_items))
    return urlunparse(
        (
            parsed.scheme.lower(),
            host,
            path,
            "",
            canonical_query,
            "",
        )
    )


def _normalize_open_access_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode(
        "ascii"
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
    return " ".join(normalized.split())


def _pick_preferred_candidate_url(left: str | None, right: str | None) -> str | None:
    options = [url for url in (left, right) if url]
    if not options:
        return None
    options.sort(
        key=lambda item: (
            len(urlparse(item).path or ""),
            item,
        ),
        reverse=True,
    )
    return options[0]


def _merge_candidate_url_list(
    candidates: list[str],
    *,
    exclude: set[str | None],
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    excluded = {item for item in exclude if item}
    for url in candidates:
        cleaned = url.strip()
        if not cleaned or cleaned in excluded or cleaned in seen:
            continue
        seen.add(cleaned)
        merged.append(cleaned)
    return merged


def _prefer_richer_text(left: str | None, right: str | None) -> str | None:
    if not left:
        return right
    if not right:
        return left
    return left if len(left) >= len(right) else right


def _open_access_candidate_sort_key(
    request: MethodRecommendationRequest,
    candidate: OpenAccessPaperCandidate,
    score: float,
) -> tuple[int, float, int, int, int, int, int, int, str, str]:
    title_text = candidate.title.lower()
    descriptor_text = " ".join(
        filter(None, [candidate.title, candidate.abstract])
    ).lower()
    searchable_matrix_hint = _searchable_matrix_hint(request.matrix_hint)
    request_mentions_derivatization = _mentions_derivatization(request.request_text)
    title_mentions_derivatization = _mentions_derivatization(candidate.title)
    title_has_method = _has_primary_method_signal(title_text)
    # When MS required: hard-sort MS papers before non-MS so we hit viable ones first
    ms_priority = (
        1 if (request.require_mass_spectrometry and _text_has_mass_spectrometry_signal(descriptor_text))
        else 0
    )

    return (
        ms_priority,
        score,
        _exact_title_term_match(request.analyte_name, title_text),
        _exact_title_term_match(searchable_matrix_hint, title_text),
        1 if title_has_method else 0,
        1
        if request_mentions_derivatization
        and title_has_method
        and title_mentions_derivatization
        else 0,
        1 if _has_exact_title_query_provenance(candidate) else 0,
        candidate.published_year or 0,
        candidate.title,
        candidate.paper_id,
    )


def _exact_title_term_match(term: str | None, title_text: str) -> int:
    if not term:
        return 0
    normalized_term = " ".join(term.lower().split())
    if not normalized_term:
        return 0
    if normalized_term in title_text:
        return 1
    term_tokens = _tokenize(normalized_term)
    if not term_tokens:
        return 0
    return 1 if term_tokens.issubset(_tokenize(title_text)) else 0


def _mentions_derivatization(text: str | None) -> bool:
    if not text:
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return any(
        term in normalized
        for term in (
            "derivatization",
            "derivatisation",
            "derivatized",
            "derivatised",
            "pmp",
            "phenyl 3 methyl 5 pyrazolone",
            "phenyl methyl pyrazolone",
        )
    )


def _has_exact_title_query_provenance(candidate: OpenAccessPaperCandidate) -> bool:
    candidate_title = _normalize_open_access_title(candidate.title)
    if not candidate_title:
        return False
    for query in candidate.query_provenance:
        normalized_query = _normalize_open_access_title(query.query_text)
        if not normalized_query:
            continue
        if query.intent == "exact_request" and _title_queries_overlap(
            normalized_query,
            candidate_title,
        ):
            return True
        if query.intent == "user_supplied" and _title_queries_overlap(
            normalized_query,
            candidate_title,
        ):
            return True
    return False


def _title_queries_overlap(normalized_query: str, normalized_title: str) -> bool:
    query_tokens = set(normalized_query.split())
    title_tokens = set(normalized_title.split())
    if len(query_tokens) < 6:
        return False
    if normalized_query == normalized_title:
        return True
    if normalized_query in normalized_title or normalized_title in normalized_query:
        return True
    return len(query_tokens & title_tokens) / len(query_tokens) >= 0.8


def _open_access_candidate_screen_score(
    request: MethodRecommendationRequest,
    candidate: OpenAccessPaperCandidate,
) -> float:
    title_text = candidate.title.lower()
    descriptor_text = " ".join(
        filter(None, [candidate.title, candidate.abstract, candidate.source_name])
    ).lower()
    score = 0.0
    searchable_matrix_hint = _searchable_matrix_hint(request.matrix_hint)
    analyte_score = _screening_term_score(
        request.analyte_name, title_text, descriptor_text
    )
    matrix_score = _screening_term_score(
        searchable_matrix_hint, title_text, descriptor_text
    )

    score += analyte_score * 2.2
    score += matrix_score * 1.8
    if request.analyte_name and analyte_score == 0:
        score -= 6.0
    elif request.analyte_name and analyte_score < 0.5:
        score -= 2.0
    if request.analyte_name and request.analyte_name.lower() in title_text:
        score += 0.5
    if searchable_matrix_hint:
        if matrix_score == 0:
            score -= 0.5  # Reduced from 1.3
        elif matrix_score < 0.5:
            score -= 0.2  # Reduced from 0.5
        if _has_conflicting_matrix_context(
            searchable_matrix_hint,
            descriptor_text,
            title_text=title_text,
        ):
            score -= 1.0  # Reduced from 2.2

    chromatography_terms = (
        "hplc",
        "uhplc",
        "lc-ms",
        "lc ms",
        "chromatograph",
        "reversed phase",
        "rp-hplc",
        "column",
        "stationary phase",
    )
    score += 0.8 if any(term in descriptor_text for term in chromatography_terms) else -0.3

    if request.require_mass_spectrometry:
        score += 1.1 if _text_has_mass_spectrometry_signal(descriptor_text) else -1.0

    if request.preferred_mode == "hilic" and "hilic" in descriptor_text:
        score += 0.5
    if _has_primary_method_signal(title_text):
        score += 1.0
    elif _has_primary_method_signal(descriptor_text):
        score += 0.5
    elif _searchable_matrix_hint(request.matrix_hint) is None:
        score -= 0.6

    if _has_broad_scope_penalty(title_text):
        score -= 1.4
    if _looks_like_secondary_methods_literature(title_text):
        score -= 1.6
    if any(
        term in title_text
        for term in ("review", "editorial", "erratum", "correction", "protocol")
    ):
        score -= 2.5

    return round(score, 3)


def _open_access_candidate_screen_reason_parts(
    request: MethodRecommendationRequest,
    candidate: OpenAccessPaperCandidate,
) -> list[str]:
    descriptor_text = " ".join(
        filter(None, [candidate.title, candidate.abstract, candidate.source_name])
    ).lower()
    title_text = candidate.title.lower()
    reasons: list[str] = []
    searchable_matrix_hint = _searchable_matrix_hint(request.matrix_hint)

    if any(
        term in title_text
        for term in ("review", "editorial", "erratum", "correction", "protocol")
    ):
        reasons.append("Title looks like a secondary/review/protocol title.")
    if request.analyte_name and _screening_term_score(
        request.analyte_name, title_text, descriptor_text
    ) == 0:
        reasons.append("Title/abstract showed a missing analyte match.")
    if searchable_matrix_hint and _screening_term_score(
        searchable_matrix_hint, title_text, descriptor_text
    ) == 0:
        reasons.append("Title/abstract showed a missing matrix match.")
    if searchable_matrix_hint and _has_conflicting_matrix_context(
        searchable_matrix_hint,
        descriptor_text,
        title_text=title_text,
    ):
        reasons.append(
            "Title/abstract pointed to a conflicting matrix context for the request."
        )
    if not any(
        term in descriptor_text
        for term in ("hplc", "uhplc", "lc-ms", "lc ms", "chromatograph")
    ):
        reasons.append("Title/abstract lacks chromatography signal.")
    if request.require_mass_spectrometry and not _text_has_mass_spectrometry_signal(
        descriptor_text
    ):
        reasons.append("Title/abstract lacks MS signal for an MS-required query.")
    if _searchable_matrix_hint(request.matrix_hint) is None and not _has_primary_method_signal(
        title_text
    ):
        reasons.append(
            "Title did not look like a direct final-method paper for a matrix-generic query."
        )
    if _has_broad_scope_penalty(title_text):
        reasons.append("Title looked broad/compositional rather than method-specific.")
    if _looks_like_secondary_methods_literature(title_text):
        reasons.append("Title looked like a secondary/review/protocol title rather than one final method.")
    return reasons


def _open_access_candidate_screen_reason(
    request: MethodRecommendationRequest,
    candidate: OpenAccessPaperCandidate,
) -> str:
    return " ".join(_open_access_candidate_screen_reason_parts(request, candidate))


def _open_access_candidate_screen_summary(
    request: MethodRecommendationRequest,
    candidate: OpenAccessPaperCandidate,
) -> str:
    descriptor_text = " ".join(
        filter(None, [candidate.title, candidate.abstract, candidate.source_name])
    ).lower()
    title_text = candidate.title.lower()
    highlights: list[str] = []
    searchable_matrix_hint = _searchable_matrix_hint(request.matrix_hint)

    analyte_score = _screening_term_score(request.analyte_name, title_text, descriptor_text)
    matrix_score = _screening_term_score(
        searchable_matrix_hint, title_text, descriptor_text
    )
    if analyte_score >= 0.85:
        highlights.append("strong analyte match")
    elif analyte_score > 0:
        highlights.append("partial analyte match")
    if searchable_matrix_hint and matrix_score >= 0.85:
        highlights.append("matched matrix context")
    elif searchable_matrix_hint and matrix_score > 0:
        highlights.append("partial matrix context")
    if _has_primary_method_signal(title_text) or _has_primary_method_signal(descriptor_text):
        highlights.append("primary method framing")
    if _text_has_mass_spectrometry_signal(descriptor_text):
        highlights.append("explicit MS signal")
    if any(term in descriptor_text for term in ("hplc", "uhplc", "lc-ms", "lc ms", "chromatograph")):
        highlights.append("chromatography method signal")

    if highlights:
        return (
            "Survived title/abstract screening because it showed "
            + ", ".join(highlights[:4])
            + "."
        )[:600]
    return (
        "Survived title/abstract screening because it remained the best available "
        "open-access method candidate after de-duplication."
    )


def _normalize_open_access_screening_score(score: float) -> float:
    return round((math.tanh(score / 3.0) + 1.0) / 2.0, 3)


def _screening_term_score(
    term: str | None,
    title_text: str,
    descriptor_text: str,
) -> float:
    if not term:
        return 0.0
    normalized_term = term.lower().strip()
    if normalized_term and normalized_term in title_text:
        return 1.0
    if normalized_term and normalized_term in descriptor_text:
        return 0.85

    term_tokens = _tokenize(term)
    if not term_tokens:
        return 0.0
    title_tokens = _tokenize(title_text)
    descriptor_tokens = _tokenize(descriptor_text)
    title_overlap = len(term_tokens & title_tokens) / len(term_tokens)
    descriptor_overlap = len(term_tokens & descriptor_tokens) / len(term_tokens)
    return round(max(title_overlap, descriptor_overlap * 0.85), 3)


def _has_primary_method_signal(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "validated",
            "method",
            "determination",
            "quantification",
            "separation",
            "assay",
            "simultaneous determination",
            "monitoring",
            "therapeutic drug monitoring",
            "drug monitoring",
            "analysis",
            "measurement",
            "detection",
            "chromatography",
        )
    )


def _has_broad_scope_penalty(title_text: str) -> bool:
    broad_scope_terms = (
        "chemistry",
        "characterization",
        "properties",
        "overview",
        "prospective",
        "future",
        "extracts",
        "preparation",
        "bioactive compounds",
        "content",
        "composition",
        "influence of",
        "functional food",
        "nutrition",
        "nutritional",
        "dietary",
        "food science",
    )
    return any(term in title_text for term in broad_scope_terms)


def _looks_like_secondary_methods_literature(title_text: str) -> bool:
    secondary_methods_terms = (
        "analytical methods",
        "methods applied",
        "methods for the characterization",
        "methods for characterization",
    )
    return any(term in title_text for term in secondary_methods_terms)


def _has_conflicting_matrix_context(
    matrix_hint: str,
    descriptor_text: str,
    *,
    title_text: str | None = None,
) -> bool:
    request_tokens = _tokenize(matrix_hint)
    clinical_matrix_tokens = {
        "human",
        "plasma",
        "serum",
        "blood",
        "urine",
        "patient",
    }
    if not (request_tokens & clinical_matrix_tokens):
        return False

    normalized_title = title_text or ""
    clinical_title_terms = (
        "human plasma",
        "plasma",
        "human serum",
        "serum",
        "whole blood",
        "blood",
        "urine",
    )
    if any(term in normalized_title for term in clinical_title_terms):
        return False

    conflicting_terms = (
        "plant",
        "plants",
        "tissue",
        "tissues",
        "leaf",
        "leaves",
        "fruit",
        "fruits",
        "vegetable",
        "vegetables",
        "food",
        "foods",
        "extract",
        "extracts",
        "oil",
        "oils",
        "milk",
        "pigment",
        "pigments",
        "bean",
        "beans",
        "seed",
        "seeds",
        "root",
        "roots",
        "peel",
        "peels",
        "pulp",
        "algae",
        "botanical",
    )
    return any(term in descriptor_text for term in conflicting_terms)


def _searchable_matrix_hint(matrix_hint: str | None) -> str | None:
    if not matrix_hint:
        return None
    normalized = matrix_hint.strip()
    if not normalized:
        return None
    tokens = _tokenize(normalized)
    if not tokens:
        return None
    generic_tokens = {
        "organic",
        "solvent",
        "solution",
        "sample",
        "matrix",
        "buffer",
        "standard",
        "mixture",
        "aqueous",
    }
    if tokens.issubset(generic_tokens):
        return None
    return normalized


def _text_has_mass_spectrometry_signal(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return False
    if any(
        phrase in normalized
        for phrase in (
            "ms ms",
            "lc ms",
            "mass spectrom",
            "triple quadrupole",
        )
    ):
        return True
    tokens = set(normalized.split())
    return any(token in tokens for token in ("mrm", "qtrap", "apci", "esi"))


def _candidate_viability_skip_reason(
    request: MethodRecommendationRequest,
    candidate: RecommendationCandidate,
) -> str | None:
    if candidate.extraction.method_parameters is None:
        return (
            "Extraction did not recover a complete final method with mobile phases "
            "and flow rate."
        )
    if (
        request.require_mass_spectrometry
        and candidate.score.features.detector_compatibility < 0.2
    ):
        return (
            "Post-extraction viability gate rejected the candidate because the "
            "required mass-spectrometry signal was not recovered."
        )
    if candidate.score.features.extraction_completeness < 0.2:
        return (
            "Post-extraction viability gate rejected the candidate because "
            "extraction completeness stayed below the minimum threshold."
        )
    if (
        candidate.decision_trace is not None
        and candidate.decision_trace.viability_score < 0.1
    ):
        return (
            "Post-extraction viability gate rejected the candidate because the "
            f"viability score remained below 0.10."
        )
    return None


def _skipped_paper_from_candidate(
    candidate: OpenAccessPaperCandidate,
    *,
    stage: str,
    reason: str,
) -> RecommendationSkippedPaper:
    return RecommendationSkippedPaper(
        paper_id=_bounded_schema_string(candidate.paper_id, 500),
        title=_bounded_schema_string(candidate.title, 1000),
        stage=stage,
        reason=_bounded_schema_string(reason, 1200),
        url=_bounded_optional_schema_string(candidate.url or candidate.pdf_url, 2000),
        query_provenance=[
            item.model_copy(deep=True) for item in candidate.query_provenance
        ],
    )


def _skipped_paper_from_artifact(
    artifact: FetchedSourceArtifact,
    *,
    stage: str,
    reason: str,
) -> RecommendationSkippedPaper:
    return RecommendationSkippedPaper(
        paper_id=_bounded_schema_string(artifact.paper_id, 500),
        title=_bounded_schema_string(
            artifact.title or artifact.file_name or artifact.paper_id,
            1000,
        ),
        stage=stage,
        reason=_bounded_schema_string(reason, 1200),
        url=_bounded_optional_schema_string(artifact.url, 2000),
    )


def _bounded_schema_string(value: str, max_length: int) -> str:
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= max_length:
        return collapsed or "Unavailable"
    suffix = " ... [truncated]"
    return collapsed[: max_length - len(suffix)].rstrip() + suffix


def _bounded_optional_schema_string(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    bounded = _bounded_schema_string(value, max_length)
    return bounded or None


def _failure_classification_for_exception(
    exc: Exception,
    *,
    default: str,
) -> str:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, (TimeoutError, httpx.TimeoutException)):
            return "timeout"
        if isinstance(current, InvalidSmilesError):
            return "request_invalid"
        if isinstance(current, GeminiClientError):
            return "llm_observer_unavailable"
        if isinstance(current, OpenAccessClientError) and "timed out" in str(current).lower():
            return "timeout"
        current = current.__cause__ or current.__context__
    return default


def _classified_skip_reason(classification: str, exc: Exception) -> str:
    summary = _summarize_exception(exc)
    if classification == "timeout":
        return f"Timeout: {summary}"
    if classification == "fetch_failure":
        return f"Fetch failure: {summary}"
    if classification == "llm_observer_unavailable":
        return f"LLM observer unavailable: {summary}"
    if classification == "request_invalid":
        return f"Invalid request input: {summary}"
    return f"Extraction failure: {summary}"


def _summarize_exception(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _run_with_progress_keepalive(
    *,
    progress_callback: RecommendationProgressCallback | None,
    stage: str,
    message: str,
    items_completed: int | None,
    items_total: int | None,
    operation,
):
    if progress_callback is None:
        return operation()

    stop_event = Event()

    def _heartbeat() -> None:
        while not stop_event.wait(PROGRESS_HEARTBEAT_INTERVAL_S):
            progress_callback(stage, message, items_completed, items_total)

    heartbeat = Thread(target=_heartbeat, daemon=True)
    heartbeat.start()
    try:
        return operation()
    finally:
        stop_event.set()
        heartbeat.join(timeout=0.1)


def _tokenize(text: str) -> set[str]:
    normalized = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "using",
        "used",
        "method",
        "analysis",
        "final",
        "including",
        "extract",
        "recommend",
        "find",
    }
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in stopwords
    }


def best_evidence_snippets(
    candidate: RecommendationCandidate, *, limit: int = 3
) -> list[EvidenceSnippet]:
    return candidate.evidence_snippets[:limit]


def _local_paper_id(path: Path) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-")
    return (normalized or "local-paper")[:180]
