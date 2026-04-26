from pathlib import Path
from contextlib import contextmanager
import threading
import time
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.open_access_client import OpenAccessPaperClient
from app.compound_context_schemas import CompoundContext, CompoundSourceIds
from app.hplc_extraction_schemas import MinimalHplcExtractionResponse
from app.recommendation_prompt_pack import (
    CandidateRerankItem,
    CandidateRerankResponse,
    MethodEvidenceSniffResponse,
    QueryPlannerQuery,
    QueryPlannerResponse,
)
from app.recommendation_engine import (
    _OpenAccessScreeningDecision,
    _build_open_access_recommendation_candidate,
    _build_search_query_variants,
    _build_search_queries,
    _screen_open_access_candidates,
    _score_extraction_against_request,
    recommend_methods,
)
from app.recommendation_runtime import RecommendationRuntimeTracker
from app.recommendation_schemas import (
    FetchedSourceArtifact,
    MethodRecommendationRequest,
    OpenAccessPaperCandidate,
    RecommendationQueryVariant,
    RecommendationTrust,
)
from app.retrieval_schemas import (
    ChromatographySystem,
    HplcMolecularEntity,
    MethodParameters,
    MobilePhase,
    RetrievalRecordReviewSummary,
    RetrievalMethodRecord,
    RetrievalProvenance,
    SourceDocumentMetadata,
)
from app.retrieval_store import SeededRetrievalStore


FIXTURES_DIR = Path(__file__).resolve().parent / "paper_example"


def test_recommend_methods_local_files_mode_returns_ranked_candidate() -> None:
    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Extract the final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="local_files",
            local_paths=[
                str(
                    FIXTURES_DIR
                    / "Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html"
                )
            ],
        )
    )

    assert report.recommended_candidate is not None
    assert report.source_mode == "local_files"
    assert "Carotenoids" in report.recommended_candidate.title
    assert report.recommended_candidate.score.total_score > 0.5
    assert report.recommended_candidate.trust.trust_state == "local_file_extracted"
    assert report.recommended_candidate.trust.manual_verification_required is True
    assert report.recommended_candidate.evidence_snippets
    assert len(report.recommended_candidate.evidence_snippets) <= 3
    assert report.runtime is not None
    assert report.runtime.status == "completed"
    assert report.recommended_candidate.ranking_context.ranking_mode == "target_only"
    assert (
        report.recommended_candidate.ranking_context.impurity_handling
        == "not_requested"
    )
    assert (
        report.recommended_candidate.trust.validation_status
        == _validation_for_candidate(report.recommended_candidate)
    )
    assert (
        report.recommended_candidate.trust.issue_counts.model_dump()
        == _expected_issue_counts(report.recommended_candidate)
    )
    assert len(report.recommended_candidate.trust.warning_summary) <= 3
    assert report.recommended_candidate.decision_trace is not None
    score_layers = report.recommended_candidate.decision_trace.score_layers
    assert score_layers is not None
    assert score_layers.retrieval_relevance is None
    assert (
        score_layers.method_viability
        == report.recommended_candidate.decision_trace.viability_score
    )
    assert score_layers.final_fit == report.recommended_candidate.score.total_score


def test_recommend_methods_open_access_mode_uses_client_results() -> None:
    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=2,
        ),
        open_access_client=_FakeOpenAccessPaperClient(),
    )

    assert report.discovered_papers
    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-mdpi"
    assert report.recommended_candidate.trust.trust_state == "open_access_extracted"
    assert report.recommended_candidate.trust.manual_verification_required is True
    assert report.recommended_candidate.evidence_snippets
    assert len(report.recommended_candidate.evidence_snippets) <= 3
    assert report.runtime is not None
    assert report.runtime.status == "completed"
    assert (
        report.recommended_candidate.trust.validation_status
        == _validation_for_candidate(report.recommended_candidate)
    )
    assert (
        report.recommended_candidate.trust.issue_counts.model_dump()
        == _expected_issue_counts(report.recommended_candidate)
    )
    assert len(report.recommended_candidate.trust.warning_summary) <= 3
    assert report.recommended_candidate.decision_trace is not None
    score_layers = report.recommended_candidate.decision_trace.score_layers
    assert score_layers is not None
    assert score_layers.retrieval_relevance is not None
    assert (
        score_layers.retrieval_relevance
        == report.recommended_candidate.decision_trace.retrieval_score
    )
    assert score_layers.final_fit == report.recommended_candidate.score.total_score


def test_recommend_methods_open_access_runtime_exposes_search_plan_and_telemetry() -> None:
    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine in organic solvent",
            analyte_name="caffeine",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=2,
        ),
        open_access_client=_FakeOpenAccessPaperClient(),
    )

    assert report.runtime is not None
    assert report.runtime.budget.search_plan is not None
    assert report.runtime.budget.search_plan.request_specificity == "mixed"
    assert report.runtime.budget.search_plan.query_count >= 2
    assert report.runtime.telemetry is not None
    assert report.runtime.telemetry.evidence_unit_count > 0
    assert report.runtime.telemetry.cache.extraction_misses >= 1
    stage_names = {stage.stage for stage in report.runtime.telemetry.stages}
    assert "query_papers" in stage_names
    assert "extract_methods" in stage_names


def test_recommend_methods_open_access_adds_compound_context_to_report() -> None:
    client = _QueryCapturingOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine in organic solvent",
            analyte_name="caffeine",
            target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
        compound_context_client=_FakeCompoundContextClient(),
    )

    assert report.target_compound_context is not None
    assert report.target_compound_context.resolved_name == "Caffeine"
    assert report.external_evidence_trace is not None
    assert "Caffeine" in report.external_evidence_trace.query_terms_used
    assert client.queries[0].startswith("Caffeine")
    assert "LC-MS/MS" in client.queries[0]


def test_recommend_methods_open_access_uses_llm_query_planner_when_available() -> None:
    client = _PlannerAwareOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
        gemini_client=_PlannerGeminiClient(),
    )

    assert report.recommended_candidate is not None
    assert client.queries == [
        "Validated LC-MS/MS carotenoids human plasma",
        "carotenoids plasma bioanalytical LC-MS/MS",
        "carotenoids quantification LC-MS/MS",
    ]
    assert report.runtime is not None
    assert any(
        "LLM query planner produced" in decision
        for decision in report.runtime.branch_decisions
    )


def test_search_query_planner_can_run_parallel_planners() -> None:
    client = _ParallelPlannerGeminiClient(parallelism=3)

    variants = _build_search_query_variants(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
        ),
        gemini_client=client,
        planner_parallelism=3,
    )

    assert client.calls == 3
    assert client.max_active >= 2
    assert [variant.query_text for variant in variants][:3] == [
        "planner query 1 strict_method",
        "planner query 1 repair",
        "planner query 1 matrix_relaxed",
    ]
    assert len(variants) == 9


def test_recommend_methods_open_access_extracts_candidates_in_parallel(monkeypatch) -> None:
    client = _ParallelExtractionOpenAccessPaperClient()
    monkeypatch.setattr("app.recommendation_engine._DEFAULT_EXTRACTION_CONCURRENCY", 3)
    state = {
        "calls": 0,
        "active": 0,
        "max_active": 0,
    }
    lock = threading.Lock()
    release = threading.Event()

    def _fake_build_open_access_recommendation_candidate(*args, **kwargs):
        del args, kwargs
        with lock:
            state["calls"] += 1
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
            if state["calls"] >= 2:
                release.set()
        release.wait(timeout=1.0)
        time.sleep(0.01)
        with lock:
            state["active"] -= 1
        return None, []

    monkeypatch.setattr(
        "app.recommendation_engine._build_open_access_recommendation_candidate",
        _fake_build_open_access_recommendation_candidate,
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=3,
        ),
        open_access_client=client,
        gemini_client=_PlannerGeminiClient(),
    )

    assert state["calls"] == 3
    assert state["max_active"] >= 2
    assert report.runtime is not None
    assert report.runtime.status == "no_trustworthy_candidates"


def test_recommend_methods_full_document_fallback_limit_is_independent_of_viable_target(
    monkeypatch,
) -> None:
    client = _ParallelExtractionOpenAccessPaperClient()
    seen_fallback_flags: list[bool] = []
    monkeypatch.setattr("app.recommendation_engine._DEFAULT_EXTRACTION_CONCURRENCY", 1)
    monkeypatch.setattr("app.recommendation_engine._FULL_DOCUMENT_LLM_FALLBACK_LIMIT", 2)

    def _fake_build_open_access_recommendation_candidate(*args, **kwargs):
        del args
        seen_fallback_flags.append(kwargs["allow_full_document_llm_fallback"])
        return None, []

    monkeypatch.setattr(
        "app.recommendation_engine._build_open_access_recommendation_candidate",
        _fake_build_open_access_recommendation_candidate,
    )

    recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=3,
        ),
        open_access_client=client,
        gemini_client=_PlannerGeminiClient(),
    )

    assert seen_fallback_flags == [True, True, False]


def test_open_access_pdf_artifact_skips_html_only_hplc_signal_gate(monkeypatch) -> None:
    request = MethodRecommendationRequest(
        request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
        analyte_name="carotenoids",
        matrix_hint="human plasma",
        require_mass_spectrometry=True,
        source_mode="open_access",
    )
    client = _PdfOnlyNoAbstractSignalOpenAccessPaperClient()
    runtime_tracker = RecommendationRuntimeTracker(
        request,
        open_access_timeout_sec=None,
        llm_observer_enabled=False,
        rate_limit_policy="none",
        enable_debug_metadata=True,
    )
    called = False

    def _fake_candidate_from_open_access_artifact(*args, **kwargs):
        nonlocal called
        del args, kwargs
        called = True
        return None, "forced test failure", "extraction_failure"

    monkeypatch.setattr(
        "app.recommendation_engine._candidate_from_open_access_artifact",
        _fake_candidate_from_open_access_artifact,
    )

    built_candidate, skips = _build_open_access_recommendation_candidate(
        request,
        _OpenAccessScreeningDecision(
            candidate=client.search_papers("query")[0],
            screening_score=0.9,
            normalized_score=0.9,
            screening_model="test",
            screening_reason="test",
            screening_reasons=("test",),
            summary="test",
        ),
        client=client,
        runtime_tracker=runtime_tracker,
    )

    assert built_candidate is None
    assert called is True
    assert skips[0].reason != "no_hplc_signal"


def test_recommend_methods_accepts_legacy_local_source_mode_as_local_files() -> None:
    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Extract the final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="local",
            local_paths=[
                str(
                    FIXTURES_DIR
                    / "Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html"
                )
            ],
        )
    )

    assert report.source_mode == "local_files"
    assert report.recommended_candidate is not None


def test_recommend_methods_local_corpus_mode_returns_unified_candidate_shape() -> None:
    store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="seed-caffeine-rp18",
                local_identifier="caffeine",
                smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            )
        ]
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine",
            analyte_name="caffeine",
            target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="local_corpus",
            system_specs={
                "column_manufacturer": "Waters",
                "column_name": "XBridge BEH C18",
                "column_chemistry": "C18",
                "column_length_mm": 100,
                "column_inner_diameter_mm": 2.1,
                "particle_size_um": 3.5,
            },
        ),
        retrieval_store=store,
    )

    assert report.source_mode == "local_corpus"
    assert report.discovered_papers == []
    assert report.recommended_candidate is not None
    assert report.runtime is not None
    assert report.runtime.status == "completed"
    assert report.recommended_candidate.paper_id == "seed-caffeine-rp18"
    assert report.recommended_candidate.source_kind == "seeded"
    assert report.recommended_candidate.score.total_score > 0.8
    assert report.recommended_candidate.score.system_match > 0.5
    assert report.recommended_candidate.score.analyte_match == 1.0
    assert report.recommended_candidate.score.practical_fit > 0.8
    assert report.recommended_candidate.score.literature_relevance > 0.7
    assert report.recommended_candidate.evidence_snippets
    assert report.recommended_candidate.evidence_snippets[0].text.startswith(
        "Curated seeded LC-MS/MS record for caffeine"
    )
    assert report.recommended_candidate.trust.trust_state == "seeded_corpus"
    assert report.recommended_candidate.trust.validation_status == "unvalidated"
    assert report.recommended_candidate.trust.retrieval_ready is False
    assert report.recommended_candidate.trust.manual_verification_required is True
    assert (
        report.recommended_candidate.trust.issue_counts.model_dump()
        == {"info": 0, "warning": 0, "error": 0}
    )
    assert report.recommended_candidate.trust.warning_summary == []
    assert report.recommended_candidate.ranking_context.ranking_mode == "target_only"
    assert (
        report.recommended_candidate.ranking_context.impurity_handling
        == "not_requested"
    )
    assert report.recommended_candidate.match_rationale is not None
    assert report.recommended_candidate.review_summary is not None
    assert report.recommended_candidate.recommended_method is not None
    assert report.recommended_candidate.recommended_method.is_scaled is True
    assert "Local corpus exact match" in report.recommended_candidate.rationale
    assert "Review state: seeded" in report.recommended_candidate.rationale
    assert report.recommended_candidate.decision_trace is not None
    score_layers = report.recommended_candidate.decision_trace.score_layers
    assert score_layers is not None
    assert score_layers.retrieval_relevance is not None
    assert (
        score_layers.retrieval_relevance
        == report.recommended_candidate.decision_trace.retrieval_score
    )
    assert (
        score_layers.method_viability
        == report.recommended_candidate.decision_trace.viability_score
    )
    assert score_layers.final_fit == report.recommended_candidate.score.total_score


def test_recommend_methods_local_corpus_adds_compound_context_to_report() -> None:
    store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="seed-caffeine-rp18",
                local_identifier="caffeine",
                smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            )
        ]
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine",
            analyte_name="caffeine",
            target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="local_corpus",
        ),
        retrieval_store=store,
        compound_context_client=_FakeCompoundContextClient(),
    )

    assert report.target_compound_context is not None
    assert report.target_compound_context.resolved_name == "Caffeine"
    assert report.target_compound_context.formula == "C8H10N4O2"
    assert report.external_evidence_trace is not None
    assert report.external_evidence_trace.source_clients_succeeded == ["pubchem"]
    assert report.external_evidence_trace.query_terms_used == []


def test_recommend_methods_local_corpus_uses_recommendation_fit_to_break_exact_match_ties() -> (
    None
):
    store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="zzz-bad-fit",
                local_identifier="caffeine",
                smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                title="Synthetic HPLC method for caffeine",
                column_manufacturer="Generic",
                column_name="Generic C18",
                column_length_mm=150.0,
                column_inner_diameter_mm=4.6,
                particle_size_um=5.0,
                run_time_min=28.0,
                evidence_text=(
                    "Curated seeded HPLC record for caffeine with no mass spectrometry "
                    "and aqueous tablet workflow."
                ),
            ),
            _build_record(
                record_id="aaa-good-fit",
                local_identifier="caffeine",
                smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                title="Synthetic LC-MS/MS method for caffeine in organic solvent",
                column_manufacturer="Waters",
                column_name="XBridge BEH C18",
                column_length_mm=100.0,
                column_inner_diameter_mm=2.1,
                particle_size_um=3.5,
                run_time_min=8.0,
                evidence_text=(
                    "Curated seeded LC-MS/MS record for caffeine in organic solvent "
                    "with triple quadrupole detection."
                ),
            ),
        ]
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine in organic solvent",
            analyte_name="caffeine",
            target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="local_corpus",
            system_specs={
                "column_manufacturer": "Waters",
                "column_name": "XBridge BEH C18",
                "column_chemistry": "C18",
                "column_length_mm": 100,
                "column_inner_diameter_mm": 2.1,
                "particle_size_um": 3.5,
            },
            max_run_time_min=10,
        ),
        retrieval_store=store,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "aaa-good-fit"
    assert report.considered_candidates[0].score.total_score > report.considered_candidates[1].score.total_score
    assert report.considered_candidates[0].score.system_match > report.considered_candidates[1].score.system_match
    assert report.considered_candidates[0].score.practical_fit > report.considered_candidates[1].score.practical_fit


def test_recommend_methods_local_corpus_prefers_clinical_plasma_over_plant_matrix() -> (
    None
):
    store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="plant-carotenoid",
                local_identifier="carotenoids",
                smiles="CC",
                title="HPLC method for carotenoids in plant tissue",
                evidence_text=(
                    "Curated seeded HPLC record for carotenoids in plant tissue "
                    "and food pigment extracts."
                ),
            ),
            _build_record(
                record_id="clinical-plasma-carotenoid",
                local_identifier="carotenoids",
                smiles="CC",
                title="LC-MS/MS method for carotenoids in human plasma",
                evidence_text=(
                    "Curated seeded LC-MS/MS record for carotenoids in human plasma "
                    "with clinical sample preparation."
                ),
            ),
        ]
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            target_smiles="CC",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="local_corpus",
        ),
        retrieval_store=store,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "clinical-plasma-carotenoid"
    assert (
        report.considered_candidates[0].score.matrix_fit
        > report.considered_candidates[1].score.matrix_fit
    )


def test_score_extraction_complete_method_beats_partial_title_match() -> None:
    request = MethodRecommendationRequest(
        request_text="Recommend an LC-MS/MS method for caffeine in organic solvent",
        analyte_name="caffeine",
        target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        matrix_hint="organic solvent",
        require_mass_spectrometry=True,
    )
    complete_record = _build_record(
        record_id="complete-caffeine",
        local_identifier="caffeine",
        smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        title="LC-MS/MS method for caffeine in organic solvent",
        evidence_text=(
            "Curated seeded LC-MS/MS record for caffeine in organic solvent "
            "with final column, mobile phase, gradient, and runtime evidence."
        ),
    )
    partial_extraction = MinimalHplcExtractionResponse(
        source_document=SourceDocumentMetadata(
            source_document_id="partial-caffeine",
            source_type="manual",
            title="Validated LC-MS/MS method for caffeine in organic solvent",
        ),
        provenance=RetrievalProvenance(
            extraction_mode="parsed_text",
            extraction_confidence=0.35,
            evidence_snippets=[
                {
                    "section_label": "Abstract",
                    "text": (
                        "Caffeine in organic solvent was discussed, but final "
                        "chromatographic conditions were not recovered."
                    ),
                }
            ],
        ),
    )
    trust = RecommendationTrust(
        trust_state="local_file_extracted",
        validation_status="unvalidated",
    )

    complete_score, complete_trace = _score_extraction_against_request(
        request,
        _build_extraction_from_record(complete_record),
        trust=trust,
    )
    partial_score, partial_trace = _score_extraction_against_request(
        request,
        partial_extraction,
        trust=trust,
    )

    assert complete_score.total_score > partial_score.total_score
    assert complete_trace.viability_score > partial_trace.viability_score
    assert (
        complete_score.features.extraction_completeness
        > partial_score.features.extraction_completeness
    )


def test_recommend_methods_local_corpus_reports_mixture_aware_ranking() -> None:
    store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="record-target-only",
                local_identifier="ethanol",
                smiles="CCO",
            ),
            _build_record(
                record_id="record-target-plus-impurity",
                local_identifier="ethanol",
                smiles="CCO",
                extra_entities=[("acetone", "CC(=O)C")],
            ),
        ]
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an HPLC method for ethanol with acetone impurity",
            analyte_name="ethanol",
            target_smiles="CCO",
            impurity_smiles=["CC(=O)C"],
            source_mode="local_corpus",
        ),
        retrieval_store=store,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "record-target-plus-impurity"
    assert (
        report.recommended_candidate.ranking_context.ranking_mode
        == "target_plus_impurities"
    )
    assert (
        report.recommended_candidate.ranking_context.impurity_handling == "active"
    )
    assert report.recommended_candidate.ranking_context.impurity_count == 1
    assert report.recommended_candidate.match_rationale is not None
    assert len(report.recommended_candidate.match_rationale.impurity_matches) == 1
    assert "Mixture-aware ranking is active" in (
        report.recommended_candidate.ranking_context.summary
    )


def test_recommend_methods_open_access_reports_target_only_fallback_for_untrusted_impurity_linkage() -> (
    None
):
    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            target_smiles="CC=C(C)C=CC=C(C)C=CC=C(C)C",
            impurity_smiles=["CC(C)=O"],
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=_FakeOpenAccessPaperClient(),
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.ranking_context.ranking_mode == "target_only"
    assert (
        report.recommended_candidate.ranking_context.impurity_handling
        == "requested_but_untrusted"
    )
    assert report.recommended_candidate.ranking_context.impurity_count == 1
    assert "ranking stayed target-focused" in (
        report.recommended_candidate.ranking_context.summary
    )


def test_recommend_methods_open_access_screens_search_results_before_fetching() -> None:
    client = _ScreeningOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
    )

    assert report.search_query_used is not None
    assert "carotenoids" in report.search_query_used.lower()
    assert "lc-ms/ms" in report.search_query_used.lower()
    assert [candidate.paper_id for candidate in report.discovered_papers] == [
        "paper-relevant"
    ]
    assert client.fetched_ids == ["paper-relevant"]
    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-relevant"
    assert report.discovered_papers[0].query_provenance
    assert report.recommended_candidate.decision_trace is not None
    assert report.recommended_candidate.decision_trace.query_provenance
    assert report.runtime is not None
    assert report.runtime.budget.shortlist_size == 1
    assert report.runtime.budget.search_plan is not None
    assert report.runtime.budget.search_plan.queries
    assert {item.paper_id for item in report.skipped_papers if item.stage == "screening"} == {
        "paper-review",
        "paper-irrelevant",
    }
    assert all(
        item.query_provenance
        for item in report.skipped_papers
        if item.stage == "screening"
    )


def test_recommend_methods_open_access_dedupes_duplicate_results_and_merges_query_provenance() -> (
    None
):
    client = _DuplicateResultOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
    )

    assert report.recommended_candidate is not None
    assert [candidate.paper_id for candidate in report.discovered_papers] == [
        "paper-duplicate-primary"
    ]
    assert client.fetched_ids == ["paper-duplicate-primary"]
    assert report.runtime is not None
    assert report.runtime.budget.search_plan is not None
    assert len(report.runtime.budget.search_plan.queries) >= 2
    assert len(report.discovered_papers[0].query_provenance) >= 2
    assert len(report.recommended_candidate.decision_trace.query_provenance) >= 2
    assert any(
        "mirror.example" in url
        for url in report.discovered_papers[0].alternate_urls
    )


def test_build_search_queries_drop_generic_matrix_terms_and_add_method_anchors() -> None:
    queries = _build_search_queries(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine in organic solvent",
            analyte_name="caffeine",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="open_access",
        )
    )

    assert queries
    assert "caffeine" in queries[0].lower()
    assert "organic solvent" not in queries[0].lower()
    assert "lc-ms/ms" in queries[0].lower()
    assert "quantification" in queries[0].lower()
    assert any("organic solvent" in query.lower() for query in queries[1:])


def test_build_search_queries_tries_cleaned_request_text_first() -> None:
    queries = _build_search_queries(
        MethodRecommendationRequest(
            request_text=(
                "  Development of an Advanced HPLC-MS/MS Method for the Determination "
                "of Carotenoids and Fat-Soluble Vitamins in Human Plasma  "
            ),
            analyte_name="carotenoids and fat-soluble vitamins",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
        )
    )

    assert queries
    assert queries[0] == (
        "Development of an Advanced HPLC-MS/MS Method for the Determination "
        "of Carotenoids and Fat-Soluble Vitamins in Human Plasma"
    )
    assert any("lc-ms/ms" in query.lower() for query in queries[1:])


def test_build_search_queries_expand_family_terms_for_carotenoid_vitamin_demo() -> None:
    queries = _build_search_queries(
        MethodRecommendationRequest(
            request_text=(
                "Validated LC-MS/MS quantification of carotenoids and fat-soluble "
                "vitamins in human plasma"
            ),
            analyte_name="carotenoids and fat-soluble vitamins",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
        )
    )

    assert len(queries) >= 3
    assert any(
        "advanced hplc-ms/ms method" in query.lower()
        and "fat-soluble vitamins in human plasma" in query.lower()
        for query in queries
    )
    assert any("vitamin a" in query.lower() for query in queries)
    assert any("tocopherol" in query.lower() for query in queries)
    assert any("human serum" in query.lower() for query in queries)
    assert any("bioanalytical" in query.lower() for query in queries)
    assert any("validated" in query.lower() for query in queries)


def test_recommend_methods_open_access_tries_secondary_query_variant_when_first_search_is_junk() -> (
    None
):
    client = _FallbackQueryOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
    )

    assert len(client.queries) >= 2
    assert any("human plasma" in query.lower() for query in client.queries)
    assert any("human plasma" not in query.lower() for query in client.queries)
    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-query-fallback"
    assert client.fetched_ids == ["paper-query-fallback"]


def test_recommend_methods_open_access_demotes_broad_coffee_literature_for_caffeine_query() -> (
    None
):
    client = _CaffeineScreeningOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine in organic solvent",
            analyte_name="caffeine",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
    )

    assert [candidate.paper_id for candidate in report.discovered_papers] == [
        "paper-caffeine-method"
    ]
    assert client.fetched_ids == ["paper-caffeine-method"]
    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-caffeine-method"
    assert {
        item.paper_id for item in report.skipped_papers if item.stage == "screening"
    } == {
        "paper-coffee-chemistry",
        "paper-coffee-methods-review",
        "paper-green-coffee-properties",
    }


def test_recommend_methods_open_access_demotes_nonclinical_carotenoid_literature_for_plasma_query() -> (
    None
):
    client = _CarotenoidMatrixScreeningOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
    )

    assert [candidate.paper_id for candidate in report.discovered_papers] == [
        "paper-human-plasma-method"
    ]
    assert client.fetched_ids == ["paper-human-plasma-method"]
    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-human-plasma-method"
    skipped_by_id = {
        item.paper_id: item.reason
        for item in report.skipped_papers
        if item.stage == "screening"
    }
    assert set(skipped_by_id) == {
        "paper-plant-tissues",
        "paper-functional-pigments",
    }
    assert "conflicting matrix context" in skipped_by_id["paper-plant-tissues"].lower()


def test_open_access_screening_prefers_exact_title_provenance_before_year() -> None:
    exact_title = (
        "Development of a RP-HPLC method for determination of glucose in "
        "Shewanella oneidensis cultures utilizing 1-phenyl-3-methyl-5-pyrazolone "
        "derivatization"
    )
    request = MethodRecommendationRequest(
        request_text=(
            "Extract the final RP-HPLC method for glucose in Shewanella oneidensis "
            "cultures utilizing PMP derivatization"
        ),
        analyte_name="glucose",
        matrix_hint="Shewanella oneidensis cultures",
        preferred_mode="rp_lc",
        source_mode="open_access",
        max_papers=1,
    )

    shortlisted, skipped = _screen_open_access_candidates(
        request,
        [
            OpenAccessPaperCandidate(
                paper_id="paper-newer-equal-score",
                title=exact_title,
                url="https://example.test/newer",
                published_year=2025,
                abstract="RP-HPLC determination of glucose in Shewanella cultures after PMP derivatization.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-plos-glucose",
                title=exact_title,
                url="https://example.test/plos",
                published_year=2011,
                abstract="RP-HPLC determination of glucose in Shewanella cultures after PMP derivatization.",
                query_provenance=[
                    RecommendationQueryVariant(
                        variant_id="exact_request",
                        intent="exact_request",
                        query_text=exact_title,
                    )
                ],
            ),
        ],
        limit=1,
    )

    assert [item.candidate.paper_id for item in shortlisted] == ["paper-plos-glucose"]
    assert [item.paper_id for item in skipped] == ["paper-newer-equal-score"]


def test_open_access_screening_keeps_known_method_titles_ahead_of_negative_plasma_literature() -> None:
    request = MethodRecommendationRequest(
        request_text="Find a final LC-MS/MS method for metformin in human plasma",
        analyte_name="metformin",
        matrix_hint="human plasma",
        require_mass_spectrometry=True,
        source_mode="open_access",
        max_papers=2,
    )

    shortlisted, skipped = _screen_open_access_candidates(
        request,
        [
            OpenAccessPaperCandidate(
                paper_id="paper-metformin-plasma",
                title="Validated LC-MS/MS method for determination of metformin in human plasma",
                url="https://example.test/metformin-plasma",
                published_year=2018,
                abstract="Validated LC-MS/MS determination of metformin in human plasma.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-carotenoid-review",
                title="Review of carotenoid nutrition and plasma antioxidant composition",
                url="https://example.test/carotenoid-review",
                published_year=2025,
                abstract="Review of broad nutrition and compositional biomarkers in plasma.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-plant-extract",
                title="HPLC determination of metformin residues in plant extracts and food oils",
                url="https://example.test/plant-extract",
                published_year=2024,
                abstract="HPLC analysis in plant extract, fruit, vegetable, food, oil, and tissue samples.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-validation-guidance",
                title="Generic bioanalytical validation protocol guidance for LC-MS laboratories",
                url="https://example.test/validation-guidance",
                published_year=2023,
                abstract="General protocol and guidance without a named analyte method or plasma assay.",
            ),
        ],
        limit=1,
    )

    assert [item.candidate.paper_id for item in shortlisted] == [
        "paper-metformin-plasma"
    ]
    skipped_by_id = {item.paper_id: item.reason.lower() for item in skipped}
    assert set(skipped_by_id) == {
        "paper-carotenoid-review",
        "paper-plant-extract",
        "paper-validation-guidance",
    }
    assert "missing analyte" in skipped_by_id["paper-carotenoid-review"]
    assert "broad/compositional" in skipped_by_id["paper-carotenoid-review"]
    assert "conflicting matrix context" in skipped_by_id["paper-plant-extract"]
    assert "lacks ms signal" in skipped_by_id["paper-plant-extract"]
    assert "missing analyte" in skipped_by_id["paper-validation-guidance"]
    assert "secondary/review/protocol title" in skipped_by_id[
        "paper-validation-guidance"
    ]


def test_recommend_methods_open_access_llm_reranker_can_drop_shortlisted_candidates() -> None:
    client = _RerankerOpenAccessPaperClient()

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=2,
        ),
        open_access_client=client,
        gemini_client=_RerankerGeminiClient(),
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-plasma"
    assert client.fetched_ids == ["paper-plasma"]
    skipped_by_id = {
        item.paper_id: item.reason
        for item in report.skipped_papers
        if item.stage == "screening"
    }
    assert "paper-serum" in skipped_by_id
    assert "matrix mismatch" in skipped_by_id["paper-serum"].lower()


def test_recommend_methods_open_access_method_sniff_can_skip_before_extraction(
    monkeypatch,
) -> None:
    client = _MethodSniffOpenAccessPaperClient()
    original_extract_artifact = __import__(
        "app.recommendation_engine", fromlist=["_extract_artifact"]
    )._extract_artifact

    def _fake_extract_artifact(artifact: FetchedSourceArtifact, **kwargs) -> MinimalHplcExtractionResponse:
        if artifact.paper_id == "paper-sniff-reject":
            raise AssertionError("sniffed paper should not reach extraction")
        return original_extract_artifact(artifact, **kwargs)

    monkeypatch.setattr("app.recommendation_engine._extract_artifact", _fake_extract_artifact)

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=2,
        ),
        open_access_client=client,
        gemini_client=_MethodSniffGeminiClient(),
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-sniff-accept"
    skipped_by_id = {
        item.paper_id: item.reason
        for item in report.skipped_papers
        if item.stage == "extraction"
    }
    assert "paper-sniff-reject" in skipped_by_id
    assert "method-bearing evidence sniff rejected" in skipped_by_id[
        "paper-sniff-reject"
    ].lower()


def test_recommend_methods_open_access_reports_fetch_and_extraction_skips(
    monkeypatch,
) -> None:
    client = _FailureTrackingOpenAccessPaperClient()
    original_extract_artifact = __import__(
        "app.recommendation_engine", fromlist=["_extract_artifact"]
    )._extract_artifact

    def _fake_extract_artifact(artifact: FetchedSourceArtifact, **kwargs) -> MinimalHplcExtractionResponse:
        if artifact.paper_id == "paper-bad-extract":
            raise ValueError("deterministic extraction failure")
        return original_extract_artifact(artifact, **kwargs)

    monkeypatch.setattr("app.recommendation_engine._extract_artifact", _fake_extract_artifact)

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=3,
        ),
        open_access_client=client,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-good"
    assert set(client.fetched_ids) == {
        "paper-fetch-fail",
        "paper-bad-extract",
        "paper-good",
    }
    assert report.runtime is not None
    assert report.runtime.status == "completed_with_degraded_source"
    skipped_by_id = {(item.paper_id, item.stage): item.reason for item in report.skipped_papers}
    assert ("paper-fetch-fail", "fetch") in skipped_by_id
    assert "publisher blocked the landing page" in skipped_by_id[("paper-fetch-fail", "fetch")]
    assert ("paper-bad-extract", "extraction") in skipped_by_id
    assert "deterministic extraction failure" in skipped_by_id[
        ("paper-bad-extract", "extraction")
    ]


def test_recommend_methods_open_access_bounds_long_skip_reasons() -> None:
    class _LongFetchFailureClient(OpenAccessPaperClient):
        def search_papers(
            self, query: str, *, max_papers: int = 5
        ) -> list[OpenAccessPaperCandidate]:
            del query, max_papers
            return [
                OpenAccessPaperCandidate(
                    paper_id="paper-long-fetch-fail",
                    title="Validated LC-MS/MS method for carotenoids in human plasma",
                    url="https://example.test/long-fetch-fail",
                    abstract="Validated LC-MS/MS determination of carotenoids in plasma.",
                )
            ]

        def fetch_source_artifact(
            self, candidate: OpenAccessPaperCandidate
        ) -> FetchedSourceArtifact:
            del candidate
            raise RuntimeError("publisher failure " + ("x" * 5000))

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=_LongFetchFailureClient(),
    )

    assert report.recommended_candidate is None
    assert report.runtime is not None
    assert report.runtime.status == "no_trustworthy_candidates"
    assert report.skipped_papers
    assert len(report.skipped_papers[0].reason) <= 1200
    assert report.skipped_papers[0].reason.endswith("[truncated]")


def test_open_access_screening_does_not_shortlist_other_drug_plasma_methods() -> None:
    request = MethodRecommendationRequest(
        request_text="Find a final LC-MS/MS method for carotenoids in human plasma",
        analyte_name="carotenoids",
        matrix_hint="human plasma",
        require_mass_spectrometry=True,
        source_mode="open_access",
        max_papers=1,
    )
    shortlisted, skipped = _screen_open_access_candidates(
        request,
        [
            OpenAccessPaperCandidate(
                paper_id="paper-haloperidol",
                title=(
                    "Salt-assisted liquid-liquid microextraction for determination "
                    "of haloperidol in human plasma by LC-MS/MS"
                ),
                abstract="An LC-MS/MS method for haloperidol in human plasma.",
                url="https://example.test/haloperidol",
                published_year=2024,
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-carotenoids",
                title=(
                    "Development of an Advanced HPLC-MS/MS Method for the "
                    "Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma"
                ),
                abstract="Carotenoids and vitamins in plasma were analyzed by HPLC-MS/MS.",
                url="https://example.test/carotenoids",
                published_year=2016,
            ),
        ],
        limit=1,
    )

    assert [item.candidate.paper_id for item in shortlisted] == ["paper-carotenoids"]
    skipped_by_id = {item.paper_id: item.reason for item in skipped}
    assert "paper-haloperidol" in skipped_by_id
    assert "missing analyte match" in skipped_by_id["paper-haloperidol"]


def test_recommend_methods_open_access_falls_back_to_pdf_after_html_extraction_failure(
    monkeypatch,
) -> None:
    client = _HtmlThenPdfOpenAccessPaperClient()
    original_extract_artifact = __import__(
        "app.recommendation_engine", fromlist=["_extract_artifact"]
    )._extract_artifact

    def _fake_extract_artifact(artifact: FetchedSourceArtifact, **kwargs) -> MinimalHplcExtractionResponse:
        if artifact.kind == "html":
            raise ValueError("html extraction failed")
        return original_extract_artifact(artifact, **kwargs)

    monkeypatch.setattr("app.recommendation_engine._extract_artifact", _fake_extract_artifact)

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=1,
        ),
        open_access_client=client,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "paper-html-then-pdf"
    assert report.recommended_candidate.source_kind == "pdf"
    assert report.runtime is not None
    assert report.runtime.status == "completed_with_degraded_source"
    assert client.fetch_kinds == ["html", "pdf"]
    assert not report.skipped_papers


def test_recommend_methods_open_access_reports_no_trustworthy_candidates() -> None:
    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Find a final LC-MS/MS method for carotenoids in plasma",
            analyte_name="carotenoids",
            matrix_hint="human plasma",
            require_mass_spectrometry=True,
            source_mode="open_access",
            max_papers=2,
        ),
        open_access_client=_NoTrustworthyCandidatesOpenAccessPaperClient(),
    )

    assert report.recommended_candidate is None
    assert report.considered_candidates == []
    assert report.runtime is not None
    assert report.runtime.status == "no_trustworthy_candidates"
    assert report.runtime.degraded is True
    skipped_by_id = {
        (item.paper_id, item.stage): item.reason for item in report.skipped_papers
    }
    assert ("paper-fetch-fail", "fetch") in skipped_by_id
    assert "publisher blocked the landing page" in skipped_by_id[
        ("paper-fetch-fail", "fetch")
    ]
    assert ("paper-bad-extract", "extraction") in skipped_by_id
    assert "Extraction did not recover a complete final method" in skipped_by_id[
        ("paper-bad-extract", "extraction")
    ]


def test_recommend_methods_use_same_scaling_output_for_equivalent_local_files_and_local_corpus_sources(
    monkeypatch, tmp_path
) -> None:
    request = MethodRecommendationRequest(
        request_text="Recommend an LC-MS/MS method for caffeine in organic solvent",
        analyte_name="caffeine",
        target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        matrix_hint="organic solvent",
        require_mass_spectrometry=True,
        system_specs={
            "column_manufacturer": "Waters",
            "column_name": "XBridge BEH C18",
            "column_chemistry": "C18",
            "column_length_mm": 100,
            "column_inner_diameter_mm": 2.1,
            "particle_size_um": 1.8,
        },
        max_run_time_min=10,
    )

    matching_record = _build_record(
        record_id="seed-caffeine-rp18",
        local_identifier="caffeine",
        smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        column_manufacturer="Agilent",
        column_name="ZORBAX Eclipse Plus C18",
        column_length_mm=150.0,
        column_inner_diameter_mm=3.0,
        particle_size_um=3.5,
        run_time_min=12.0,
    )
    extraction = _build_extraction_from_record(matching_record)

    def _fake_extract_artifact(_artifact: FetchedSourceArtifact, **kwargs) -> MinimalHplcExtractionResponse:
        return extraction

    monkeypatch.setattr("app.recommendation_engine._extract_artifact", _fake_extract_artifact)

    temp_html = tmp_path / "synthetic.html"
    temp_html.write_text("<html><body>synthetic</body></html>")

    local_files_report = recommend_methods(
        request.model_copy(
            update={
                "source_mode": "local_files",
                "local_paths": [str(temp_html)],
            }
        )
    )
    local_corpus_report = recommend_methods(
        request.model_copy(update={"source_mode": "local_corpus"}),
        retrieval_store=SeededRetrievalStore(records=[matching_record]),
    )

    assert local_files_report.recommended_candidate is not None
    assert local_corpus_report.recommended_candidate is not None
    assert (
        local_files_report.recommended_candidate.recommended_method.model_dump()
        == local_corpus_report.recommended_candidate.recommended_method.model_dump()
    )
    assert (
        local_files_report.recommended_candidate.recommended_method.scaling_warnings
        == [
            "Target particle size 1.8 um is smaller than the literature method's 3.5 um particles; backpressure may increase."
        ]
    )


def test_recommend_methods_local_corpus_review_backed_candidate_can_clear_manual_verification() -> (
    None
):
    record = _build_record(
        record_id="approved-caffeine",
        local_identifier="caffeine",
        smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        validation_status="valid",
        retrieval_ready=True,
    )
    store = SeededRetrievalStore(records=[])
    store.upsert_record(
        record,
        RetrievalRecordReviewSummary(
            record_state="approved",
            review_record_id="review-caffeine-1",
            validation_status="valid",
            retrieval_ready=True,
            corpus_origin="review_promoted",
        ),
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine",
            analyte_name="caffeine",
            target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="local_corpus",
        ),
        retrieval_store=store,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.trust.trust_state == "review_backed"
    assert report.recommended_candidate.trust.validation_status == "valid"
    assert report.recommended_candidate.trust.retrieval_ready is True
    assert report.recommended_candidate.trust.manual_verification_required is False
    assert report.recommended_candidate.review_summary is not None
    assert report.recommended_candidate.review_summary.corpus_origin == "review_promoted"
    assert report.recommended_candidate.evidence_snippets
    assert report.recommended_candidate.evidence_snippets[0].text.startswith(
        "Curated seeded LC-MS/MS record for caffeine"
    )


def test_recommend_methods_local_corpus_prefers_review_backed_record_for_near_ties() -> (
    None
):
    seeded_record = _build_record(
        record_id="aaa-seeded-caffeine",
        local_identifier="caffeine",
        smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        title="A seeded LC-MS/MS method for caffeine in organic solvent",
    )
    review_backed_record = _build_record(
        record_id="zzz-review-backed-caffeine",
        local_identifier="caffeine",
        smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        title="Z review-backed LC-MS/MS method for caffeine in organic solvent",
        validation_status="valid",
        retrieval_ready=True,
    )
    store = SeededRetrievalStore(records=[seeded_record])
    store.upsert_record(
        review_backed_record,
        RetrievalRecordReviewSummary(
            record_state="approved",
            review_record_id="review-caffeine-2",
            validation_status="valid",
            retrieval_ready=True,
            corpus_origin="review_promoted",
        ),
    )

    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine",
            analyte_name="caffeine",
            target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="local_corpus",
        ),
        retrieval_store=store,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "zzz-review-backed-caffeine"
    assert (
        abs(
            report.considered_candidates[0].score.total_score
            - report.considered_candidates[1].score.total_score
        )
        <= 0.02
    )
    assert report.considered_candidates[0].trust.trust_state == "review_backed"
    assert (
        "Review-backed promoted corpus"
        in report.considered_candidates[0].rationale
    )


def _build_record(
    *,
    record_id: str,
    local_identifier: str,
    smiles: str,
    extra_entities: list[tuple[str, str]] | None = None,
    title: str | None = None,
    column_manufacturer: str = "Agilent",
    column_name: str = "ZORBAX Eclipse Plus C18",
    column_length_mm: float = 150.0,
    column_inner_diameter_mm: float = 3.0,
    particle_size_um: float = 3.5,
    run_time_min: float = 12.0,
    evidence_text: str | None = None,
    validation_status: str = "unvalidated",
    retrieval_ready: bool = False,
    validation_issues: list[dict[str, str]] | None = None,
) -> RetrievalMethodRecord:
    title = title or f"Synthetic LC-MS/MS method for {local_identifier} in organic solvent"
    evidence_text = evidence_text or (
        f"Curated seeded LC-MS/MS record for {local_identifier} in organic solvent."
    )
    return RetrievalMethodRecord(
        record_id=record_id,
        source_document=SourceDocumentMetadata(
            source_document_id=f"seed:{record_id}",
            source_type="seeded",
            title=title,
        ),
        molecular_entities=[
            HplcMolecularEntity(
                local_identifier=entity_local_identifier,
                display_name=entity_local_identifier,
                smiles_string=entity_smiles,
                observed_retention_time_min=4.82,
            )
            for entity_local_identifier, entity_smiles in [
                (local_identifier, smiles),
                *(extra_entities or []),
            ]
        ],
        chromatography_system=ChromatographySystem(
            mode="rp_lc",
            column_manufacturer=column_manufacturer,
            column_name=column_name,
            stationary_phase_chemistry="C18",
            column_length_mm=column_length_mm,
            column_inner_diameter_mm=column_inner_diameter_mm,
            particle_size_um=particle_size_um,
        ),
        method_parameters=MethodParameters(
            mobile_phase_a=MobilePhase(solvent="water"),
            mobile_phase_b=MobilePhase(solvent="methanol"),
            flow_rate_ml_min=0.45,
            column_temperature_c=30.0,
            run_time_min=run_time_min,
        ),
        provenance=RetrievalProvenance(
            extraction_mode="seeded",
            extraction_confidence=1.0,
            evidence_snippets=[
                {
                    "section_label": "Seeded record",
                    "text": evidence_text,
                }
            ],
        ),
        validation={
            "status": validation_status,
            "retrieval_ready": retrieval_ready,
            "issues": validation_issues or [],
        },
    )


class _FakeOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        pass

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-mdpi",
                title="Development of an Advanced HPLC-MS/MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma",
                doi="10.3390/ijms17101719",
                url="https://example.test/mdpi",
                pdf_url=None,
                published_year=2016,
                source_name="International Journal of Molecular Sciences",
                abstract="Carotenoids and vitamins in plasma were analyzed by HPLC-MS/MS.",
                open_access=True,
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        return FetchedSourceArtifact(
            paper_id=candidate.paper_id,
            kind="html",
            title=candidate.title,
            doi=candidate.doi,
            url=candidate.url,
            published_year=candidate.published_year,
            file_name="mdpi.html",
            html_content=(
                FIXTURES_DIR
                / "Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html"
            ).read_text(),
        )


class _PlannerGeminiClient:
    def plan_recommendation_queries(self, **_: object) -> QueryPlannerResponse:
        return QueryPlannerResponse(
            query_count=3,
            queries=[
                QueryPlannerQuery(
                    query="Validated LC-MS/MS carotenoids human plasma",
                    intent="strict_method",
                    why="Strict method-oriented query for the exact clinical matrix.",
                ),
                QueryPlannerQuery(
                    query="carotenoids plasma bioanalytical LC-MS/MS",
                    intent="repair",
                    why="Bioanalytical repair query for clinical literature wording.",
                ),
                QueryPlannerQuery(
                    query="carotenoids quantification LC-MS/MS",
                    intent="matrix_relaxed",
                    why="Matrix-relaxed fallback to preserve recall.",
                ),
            ],
        )

    def rerank_paper_candidates(self, **_: object) -> CandidateRerankResponse | None:
        return None

    def sniff_method_bearing_evidence(self, **_: object) -> MethodEvidenceSniffResponse | None:
        return None

    def extract_targeted_hplc_bundle(self, **_: object) -> tuple[dict | None, dict, str]:
        return None, {}, "test-model"

    def vet_evidence_snippets(self, snippets: list[str]) -> str | None:
        return snippets[0] if snippets else None


class _ParallelPlannerGeminiClient:
    def __init__(self, *, parallelism: int) -> None:
        self._parallelism = parallelism
        self._lock = threading.Lock()
        self._release = threading.Event()
        self.calls = 0
        self._active = 0
        self.max_active = 0

    def plan_recommendation_queries(self, **_: object) -> QueryPlannerResponse:
        with self._lock:
            self.calls += 1
            call_number = self.calls
            self._active += 1
            self.max_active = max(self.max_active, self._active)
            if self.calls >= self._parallelism:
                self._release.set()

        self._release.wait(timeout=1.0)

        with self._lock:
            self._active -= 1

        return QueryPlannerResponse(
            query_count=3,
            queries=[
                QueryPlannerQuery(
                    query=f"planner query {call_number} strict_method",
                    intent="strict_method",
                    why="Parallel planner test query.",
                ),
                QueryPlannerQuery(
                    query=f"planner query {call_number} repair",
                    intent="repair",
                    why="Parallel planner test query.",
                ),
                QueryPlannerQuery(
                    query=f"planner query {call_number} matrix_relaxed",
                    intent="matrix_relaxed",
                    why="Parallel planner test query.",
                ),
            ],
        )


class _ParallelExtractionOpenAccessPaperClient(OpenAccessPaperClient):
    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-parallel-1",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/paper-parallel-1",
                abstract="Validated LC-MS/MS determination of carotenoids in human plasma.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-parallel-2",
                title="Validated LC-MS/MS assay for carotenoids in human plasma",
                url="https://example.test/paper-parallel-2",
                abstract="Validated LC-MS/MS assay for carotenoids in human plasma.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-parallel-3",
                title="Validated LC-MS/MS quantification of carotenoids in human plasma",
                url="https://example.test/paper-parallel-3",
                abstract="Validated LC-MS/MS quantification of carotenoids in human plasma.",
            ),
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _PdfOnlyNoAbstractSignalOpenAccessPaperClient(OpenAccessPaperClient):
    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-pdf-no-abstract-signal",
                title="Relevant bioanalytical plasma method",
                pdf_url="https://example.test/paper.pdf",
                abstract="A relevant bioanalytical plasma study is reported.",
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        return FetchedSourceArtifact(
            paper_id=candidate.paper_id,
            kind="pdf",
            title=candidate.title,
            url=candidate.pdf_url,
            file_name="paper-pdf-no-abstract-signal.pdf",
            pdf_bytes=b"%PDF-1.7\n%%EOF",
        )


class _PlannerAwareOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del max_papers
        self.queries.append(query)
        if "validated" not in query.lower():
            return []
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-planned-query",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/planned-query",
                abstract="Validated LC-MS/MS determination of carotenoids in human plasma.",
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _QueryCapturingOpenAccessPaperClient(_FakeOpenAccessPaperClient):
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        self.queries.append(query)
        return super().search_papers(query, max_papers=max_papers)


class _FakeCompoundContextClient:
    @contextmanager
    def open_run(self):
        yield self

    def resolve_compound(
        self,
        *,
        label: str | None = None,
        smiles: str | None = None,
    ) -> CompoundContext:
        return CompoundContext(
            input_label=label,
            input_smiles=smiles,
            resolved_name="Caffeine",
            canonical_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            source_ids=CompoundSourceIds(pubchem_cid="2519"),
            formula="C8H10N4O2",
            molecular_weight=194.19,
            synonyms=["Caffeine", "1,3,7-trimethylxanthine"],
            lookup_sources=["pubchem"],
            confidence="high",
        )


class _ScreeningOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.fetched_ids: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-review",
                title="Review of carotenoid nutrition in human plasma",
                url="https://example.test/review",
                abstract="Narrative review of plasma carotenoids across diet studies.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-irrelevant",
                title="GC-MS cannabinoid method in serum",
                url="https://example.test/irrelevant",
                abstract="GC-MS method for cannabinoids in serum.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-relevant",
                title="UHPLC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/relevant",
                abstract="Validated UHPLC-MS/MS determination of carotenoids in plasma.",
            ),
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        self.fetched_ids.append(candidate.paper_id)
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _DuplicateResultOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.fetched_ids: list[str] = []
        self.search_calls = 0

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        self.search_calls += 1
        if self.search_calls == 1:
            return [
                OpenAccessPaperCandidate(
                    paper_id="paper-duplicate-primary",
                    title="Validated LC-MS/MS method for carotenoids in human plasma",
                    doi="10.1000/example-duplicate",
                    url="https://publisher.example/article?utm_source=newsletter",
                    abstract="Validated LC-MS/MS determination of carotenoids in human plasma.",
                )
            ]
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-duplicate-mirror",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                doi="https://doi.org/10.1000/example-duplicate",
                url="https://mirror.example/article",
                abstract="Validated LC-MS/MS determination of carotenoids in human plasma.",
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        self.fetched_ids.append(candidate.paper_id)
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _FailureTrackingOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.fetched_ids: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-fetch-fail",
                title="LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/fetch-fail",
                abstract="LC-MS/MS determination of carotenoids in plasma.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-bad-extract",
                title="LC-MS/MS quantification of carotenoids in human plasma",
                url="https://example.test/bad-extract",
                abstract="HPLC-MS/MS quantification of carotenoids in plasma.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-good",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/good",
                abstract="Validated LC-MS/MS determination of carotenoids in plasma.",
            ),
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        self.fetched_ids.append(candidate.paper_id)
        if candidate.paper_id == "paper-fetch-fail":
            raise RuntimeError("publisher blocked the landing page")
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _NoTrustworthyCandidatesOpenAccessPaperClient(OpenAccessPaperClient):
    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-fetch-fail",
                title="LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/fetch-fail",
                abstract="LC-MS/MS determination of carotenoids in plasma.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-bad-extract",
                title="LC-MS/MS quantification of carotenoids in human plasma",
                url="https://example.test/bad-extract",
                abstract="HPLC-MS/MS quantification of carotenoids in plasma.",
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        if candidate.paper_id == "paper-fetch-fail":
            raise RuntimeError("publisher blocked the landing page")
        return FetchedSourceArtifact(
            paper_id=candidate.paper_id,
            kind="html",
            title=candidate.title,
            url=candidate.url,
            html_content="<html><body><p>Instrumentation details only.</p></body></html>",
        )


class _CaffeineScreeningOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.fetched_ids: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-coffee-chemistry",
                title="A Detail Chemistry of Coffee and Its Analysis",
                url="https://example.test/coffee-chemistry",
                abstract="HPLC and LC-MS analysis of coffee constituents including caffeine and chlorogenic acids.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-coffee-methods-review",
                title="Analytical methods applied for the characterization and the determination of bioactive compounds in coffee",
                url="https://example.test/coffee-methods-review",
                abstract="Overview of analytical methods applied to coffee bioactive compounds including caffeine.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-green-coffee-properties",
                title="Chlorogenic acids, caffeine content and antioxidant properties of green coffee extracts: influence of green coffee bean preparation",
                url="https://example.test/green-coffee-properties",
                abstract="LC-MS analysis of caffeine content and antioxidant properties in coffee extracts.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-caffeine-method",
                title="Validated LC-MS/MS method for caffeine quantification",
                url="https://example.test/caffeine-method",
                abstract="Validated LC-MS/MS quantification of caffeine with final chromatographic conditions and flow rate.",
            ),
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        self.fetched_ids.append(candidate.paper_id)
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _CarotenoidMatrixScreeningOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.fetched_ids: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-plant-tissues",
                title="A rapid and sensitive method for determination of carotenoids in plant tissues by high performance liquid chromatography",
                url="https://example.test/plant-tissues",
                abstract="HPLC determination of carotenoids in plant tissues.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-functional-pigments",
                title="Carotenoids as natural functional pigments",
                url="https://example.test/functional-pigments",
                abstract="Broad discussion of carotenoid pigments and food applications.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-human-plasma-method",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/human-plasma-method",
                abstract="Validated LC-MS/MS determination of carotenoids in human plasma.",
            ),
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        self.fetched_ids.append(candidate.paper_id)
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _RerankerGeminiClient(_PlannerGeminiClient):
    def rerank_paper_candidates(self, **_: object) -> CandidateRerankResponse:
        return CandidateRerankResponse(
            ranked_candidates=[
                CandidateRerankItem(
                    paper_id="paper-plasma",
                    shortlist_score=0.96,
                    final_method_confidence=0.94,
                    matrix_match_confidence=0.97,
                    keep=True,
                    reason="Exact matrix match with strong final-method language.",
                ),
                CandidateRerankItem(
                    paper_id="paper-serum",
                    shortlist_score=0.31,
                    final_method_confidence=0.52,
                    matrix_match_confidence=0.22,
                    keep=False,
                    reason="Matrix mismatch for a plasma-specific request.",
                ),
            ]
        )


class _RerankerOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.fetched_ids: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-serum",
                title="Validated LC-MS/MS method for carotenoids in human serum",
                url="https://example.test/serum",
                abstract="Validated LC-MS/MS determination of carotenoids in human serum.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-plasma",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/plasma",
                abstract="Validated LC-MS/MS determination of carotenoids in human plasma.",
            ),
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        self.fetched_ids.append(candidate.paper_id)
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _FallbackQueryOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.fetched_ids: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del max_papers
        self.queries.append(query)
        if "human plasma" in query.lower():
            return [
                OpenAccessPaperCandidate(
                    paper_id="paper-junk",
                    title="Molecularly imprinted polymers in analytical chemistry",
                    url="https://example.test/junk",
                    abstract="Perspective article on polymer design and future analytical applications.",
                )
            ]
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-query-fallback",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/query-fallback",
                abstract="Validated LC-MS/MS determination of carotenoids in plasma.",
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        self.fetched_ids.append(candidate.paper_id)
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


class _HtmlThenPdfOpenAccessPaperClient(OpenAccessPaperClient):
    def __init__(self) -> None:
        self.fetch_kinds: list[str] = []

    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-html-then-pdf",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/html",
                pdf_url="https://example.test/pdf",
                abstract="Validated LC-MS/MS determination of carotenoids in plasma.",
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        if candidate.url:
            self.fetch_kinds.append("html")
            return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)

        self.fetch_kinds.append("pdf")
        return FetchedSourceArtifact(
            paper_id=candidate.paper_id,
            kind="pdf",
            title=candidate.title,
            url=candidate.pdf_url,
            file_name=f"{candidate.paper_id}.pdf",
            pdf_bytes=(FIXTURES_DIR / "ijms-17-01719.pdf").read_bytes(),
        )


class _MethodSniffGeminiClient(_PlannerGeminiClient):
    def sniff_method_bearing_evidence(
        self,
        *,
        evidence_units: list[dict[str, object]],
        **_: object,
    ) -> MethodEvidenceSniffResponse:
        evidence_text = "\n".join(str(unit.get("text") or "") for unit in evidence_units)
        if "instrumentation details only" in evidence_text.lower():
            return MethodEvidenceSniffResponse(
                contains_extractable_final_method=False,
                confidence=0.18,
                best_evidence_unit_ids=["junk-1"],
                reason="Only generic instrumentation details were present.",
            )
        return MethodEvidenceSniffResponse(
            contains_extractable_final_method=True,
            confidence=0.83,
            best_evidence_unit_ids=["good-1"],
            reason="Evidence units include final-method signals.",
        )


class _MethodSniffOpenAccessPaperClient(OpenAccessPaperClient):
    def search_papers(
        self, query: str, *, max_papers: int = 5
    ) -> list[OpenAccessPaperCandidate]:
        del query, max_papers
        return [
            OpenAccessPaperCandidate(
                paper_id="paper-sniff-reject",
                title="Validated LC-MS/MS method note for carotenoids",
                url="https://example.test/sniff-reject",
                abstract="Validated LC-MS/MS determination of carotenoids with brief instrument summary.",
            ),
            OpenAccessPaperCandidate(
                paper_id="paper-sniff-accept",
                title="Validated LC-MS/MS method for carotenoids in human plasma",
                url="https://example.test/sniff-accept",
                abstract="Validated LC-MS/MS determination of carotenoids in human plasma.",
            ),
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        if candidate.paper_id == "paper-sniff-reject":
            return FetchedSourceArtifact(
                paper_id=candidate.paper_id,
                kind="html",
                title=candidate.title,
                url=candidate.url,
                file_name=f"{candidate.paper_id}.html",
                html_content=(
                    "<html><body><p>Instrumentation details only were reported in this "
                    "brief note, with generic platform language and no final column, "
                    "mobile phase, gradient, or runtime parameters.</p></body></html>"
                ),
            )
        return _fixture_html_artifact(candidate.paper_id, candidate.title, candidate.url)


def _fixture_html_artifact(
    paper_id: str, title: str, url: str | None
) -> FetchedSourceArtifact:
    return FetchedSourceArtifact(
        paper_id=paper_id,
        kind="html",
        title=title,
        url=url,
        file_name=f"{paper_id}.html",
        html_content=(
            FIXTURES_DIR
            / "Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html"
        ).read_text(),
    )


def _build_extraction_from_record(
    record: RetrievalMethodRecord,
) -> MinimalHplcExtractionResponse:
    return MinimalHplcExtractionResponse(
        source_document=record.source_document,
        chromatography_system=record.chromatography_system,
        method_parameters=record.method_parameters,
        provenance=record.provenance,
        warnings=[],
        retrieval_record_ready=record.validation.retrieval_ready,
    )


def _validation_for_candidate(candidate) -> str:
    if candidate.extraction.record_draft is not None:
        return candidate.extraction.record_draft.validation.status
    return "unvalidated"


def _expected_issue_counts(candidate) -> dict[str, int]:
    validation = (
        candidate.extraction.record_draft.validation
        if candidate.extraction.record_draft is not None
        else None
    )
    issues = validation.issues if validation is not None else []
    return {
        "info": sum(1 for issue in issues if issue.severity == "info"),
        "warning": sum(1 for issue in issues if issue.severity == "warning"),
        "error": sum(1 for issue in issues if issue.severity == "error"),
    }
