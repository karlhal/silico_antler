import os
from contextlib import contextmanager
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("USE_MILVUS", "false")

from app.main import app
from app.compound_context_schemas import CompoundContext, CompoundSourceIds
from app.recommendation_engine import recommend_methods
from app.recommendation_schemas import (
    MethodRecommendationReport,
    MethodRecommendationRequest,
    RecommendationQueryVariant,
    RecommendationSkippedPaper,
)
from app.recommendation_runtime import RecommendationRuntimeTracker
from app.retrieval_schemas import (
    ChromatographySystem,
    HplcMolecularEntity,
    MethodParameters,
    MobilePhase,
    RetrievalMethodRecord,
    RetrievalProvenance,
    SourceDocumentMetadata,
)
from app.retrieval_store import SeededRetrievalStore

client = TestClient(app)
FIXTURES_DIR = Path(__file__).resolve().parent / "paper_example"


def test_recommendation_api_local_corpus_returns_unified_report_shape() -> None:
    app.state.retrieval_store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="seed-caffeine-rp18",
                local_identifier="caffeine",
                smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            )
        ]
    )

    response = client.post(
        "/recommendation/recommend",
        json={
            "request_text": "Recommend an LC-MS/MS method for caffeine",
            "analyte_name": "caffeine",
            "target_smiles": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            "matrix_hint": "organic solvent",
            "require_mass_spectrometry": True,
            "source_mode": "local_corpus",
            "system_specs": {
                "column_manufacturer": "Waters",
                "column_name": "XBridge BEH C18",
                "column_chemistry": "C18",
                "column_length_mm": 100,
                "column_inner_diameter_mm": 2.1,
                "particle_size_um": 3.5,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["source_mode"] == "local_corpus"
    assert payload["runtime"]["status"] == "completed"
    assert payload["search_query_used"] is None
    assert payload["discovered_papers"] == []
    assert payload["skipped_papers"] == []
    assert payload["recommended_candidate"]["paper_id"] == "seed-caffeine-rp18"
    assert payload["recommended_candidate"]["source_kind"] == "seeded"
    assert payload["recommended_candidate"]["match_rationale"]["match_type"] == "exact"
    assert payload["recommended_candidate"]["review_summary"]["record_state"] == "seeded"
    assert payload["recommended_candidate"]["review_summary"]["corpus_origin"] == "seeded"
    assert payload["recommended_candidate"]["trust"]["trust_state"] == "seeded_corpus"
    assert (
        payload["recommended_candidate"]["trust"]["manual_verification_required"]
        is True
    )
    assert payload["recommended_candidate"]["trust"]["validation_status"] == "unvalidated"
    assert payload["recommended_candidate"]["trust"]["retrieval_ready"] is False
    assert payload["recommended_candidate"]["trust"]["issue_counts"] == {
        "info": 0,
        "warning": 0,
        "error": 0,
    }
    assert payload["recommended_candidate"]["trust"]["warning_summary"] == []
    assert payload["recommended_candidate"]["ranking_context"] == {
        "ranking_mode": "target_only",
        "impurity_handling": "not_requested",
        "impurity_count": 0,
        "summary": "Ranking used the target molecule only.",
    }
    assert payload["recommended_candidate"]["evidence_snippets"]
    assert len(payload["recommended_candidate"]["evidence_snippets"]) <= 3
    assert payload["recommended_candidate"]["score"]["system_match"] > 0.5
    assert payload["recommended_candidate"]["score"]["practical_fit"] > 0.8
    assert payload["recommended_candidate"]["recommended_method"]["is_scaled"] is True
    assert payload["recommended_candidate"]["recommended_method"]["gradient_profile"] == []
    assert (
        "Flow rate adjusted from 0.45 to 0.22 mL/min based on column ID."
        in payload["recommended_candidate"]["recommended_method"]["scaling_notes"]
    )
    assert (
        payload["recommended_candidate"]["recommended_method"]["scaling_warnings"]
        == []
    )
    assert "Local corpus exact match" in payload["recommended_candidate"]["rationale"]


def test_recommendation_api_local_corpus_includes_compound_context_when_available() -> None:
    app.state.retrieval_store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="seed-caffeine-rp18",
                local_identifier="caffeine",
                smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            )
        ]
    )
    original_client = app.state.compound_context_client
    app.state.compound_context_client = _FakeCompoundContextClient()
    try:
        response = client.post(
            "/recommendation/recommend",
            json={
                "request_text": "Recommend an LC-MS/MS method for caffeine",
                "analyte_name": "caffeine",
                "target_smiles": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                "matrix_hint": "organic solvent",
                "require_mass_spectrometry": True,
                "source_mode": "local_corpus",
            },
        )
    finally:
        app.state.compound_context_client = original_client

    assert response.status_code == 200
    payload = response.json()

    assert payload["target_compound_context"]["resolved_name"] == "Caffeine"
    assert payload["target_compound_context"]["formula"] == "C8H10N4O2"
    assert payload["target_compound_context"]["molecular_weight"] == 194.19
    assert payload["external_evidence_trace"]["source_clients_succeeded"] == ["pubchem"]
    assert payload["external_evidence_trace"]["query_terms_used"] == []


def test_recommendation_run_agent_detail_compacts_candidates_and_records_payload_size(
    monkeypatch,
) -> None:
    report = recommend_methods(
        MethodRecommendationRequest(
            request_text="Recommend an LC-MS/MS method for caffeine",
            analyte_name="caffeine",
            target_smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            matrix_hint="organic solvent",
            require_mass_spectrometry=True,
            source_mode="local_corpus",
        ),
        retrieval_store=SeededRetrievalStore(
            records=[
                _build_record(
                    record_id="seed-caffeine-rp18-a",
                    local_identifier="caffeine",
                    smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                ),
                _build_record(
                    record_id="seed-caffeine-rp18-b",
                    local_identifier="caffeine",
                    smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                ),
                _build_record(
                    record_id="seed-caffeine-rp18-c",
                    local_identifier="caffeine",
                    smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                ),
                _build_record(
                    record_id="seed-caffeine-rp18-d",
                    local_identifier="caffeine",
                    smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                ),
            ]
        ),
    )
    assert len(report.considered_candidates) >= 4
    monkeypatch.setattr(
        "app.recommendations_router.recommend_methods",
        lambda *args, **kwargs: report,
    )

    response = client.post(
        "/recommendation/run?response_detail=agent",
        json={
            "request_text": "Recommend an LC-MS/MS method for caffeine",
            "analyte_name": "caffeine",
            "target_smiles": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            "matrix_hint": "organic solvent",
            "require_mass_spectrometry": True,
            "source_mode": "local_corpus",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("request") is None
    assert len(payload["considered_candidates"]) == 3
    assert payload["discovery_summary"]["considered_candidate_count"] == len(
        report.considered_candidates
    )
    assert payload["discovery_summary"]["considered_candidates_truncated"] is True
    assert payload["runtime"]["telemetry"]["payload"]["response_detail"] == "agent"
    assert payload["runtime"]["telemetry"]["payload"]["candidate_count"] == 3
    assert payload["runtime"]["telemetry"]["payload"]["response_bytes"] > 0


def test_recommendation_run_agent_detail_preserves_trust_diagnostics(
    monkeypatch,
) -> None:
    query_variant = RecommendationQueryVariant(
        variant_id="exact_request",
        intent="exact_request",
        query_text="carotenoids human plasma LC-MS/MS",
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
        retrieval_store=SeededRetrievalStore(
            records=[
                _build_record(
                    record_id="seed-caffeine-rp18",
                    local_identifier="caffeine",
                    smiles="Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                )
            ]
        ),
    )
    assert report.recommended_candidate is not None
    assert report.recommended_candidate.decision_trace is not None
    recommended_candidate = report.recommended_candidate.model_copy(
        update={
            "decision_trace": report.recommended_candidate.decision_trace.model_copy(
                update={"query_provenance": [query_variant]}
            )
        },
        deep=True,
    )
    report = report.model_copy(
        update={
            "source_mode": "open_access",
            "search_query_used": "carotenoids human plasma LC-MS/MS",
            "recommended_candidate": recommended_candidate,
            "considered_candidates": [recommended_candidate],
            "skipped_papers": [
                RecommendationSkippedPaper(
                    paper_id=f"skip-{index}",
                    title=f"Skipped paper {index}",
                    stage="screening" if index < 3 else "fetch",
                    reason="Did not pass compact diagnostic gate.",
                    url=f"https://example.test/{index}",
                    query_provenance=[query_variant],
                )
                for index in range(6)
            ],
        },
        deep=True,
    )
    monkeypatch.setattr(
        "app.recommendations_router.recommend_methods",
        lambda *args, **kwargs: report,
    )

    response = client.post(
        "/recommendation/run?response_detail=agent",
        json={
            "request_text": "Recommend an LC-MS/MS method for caffeine",
            "analyte_name": "caffeine",
            "target_smiles": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
            "matrix_hint": "organic solvent",
            "require_mass_spectrometry": True,
            "source_mode": "local_corpus",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["discovered_papers"] == []
    assert payload["skipped_papers"] == []
    assert payload["search_query_used"] == "carotenoids human plasma LC-MS/MS"
    assert payload["discovery_summary"]["skipped_paper_count"] == 6
    assert payload["discovery_summary"]["skipped_papers_truncated"] is True
    assert len(payload["discovery_summary"]["skipped_papers_preview"]) == 5
    skipped_preview = payload["discovery_summary"]["skipped_papers_preview"][0]
    assert skipped_preview["stage"] == "screening"
    assert skipped_preview["reason"] == "Did not pass compact diagnostic gate."
    assert skipped_preview["query_provenance"][0]["intent"] == "exact_request"
    candidate = payload["recommended_candidate"]
    assert candidate["decision_trace"]["query_provenance"][0]["query_text"] == (
        "carotenoids human plasma LC-MS/MS"
    )
    assert candidate["score"]["features"]["target_chemistry_fit"] >= 0
    assert candidate["trust"]["trust_state"] == "seeded_corpus"
    assert len(candidate["evidence_snippets"]) <= 3


def test_recommendation_run_agent_detail_reports_repeated_extraction_exception_count(
    monkeypatch,
) -> None:
    tracker = RecommendationRuntimeTracker(
        MethodRecommendationRequest(
            request_text="Recommend an HPLC method for metformin in plasma",
            analyte_name="metformin",
            source_mode="open_access",
        ),
        open_access_timeout_sec=20,
        llm_observer_enabled=False,
        rate_limit_policy="5/hour",
        enable_debug_metadata=False,
    )
    report = MethodRecommendationReport(
        source_mode="open_access",
        discovered_papers=[],
        skipped_papers=[
            RecommendationSkippedPaper(
                paper_id="paper-a",
                title="Paper A",
                stage="extraction",
                reason="HTML: Extraction failure: repeated schema mismatch",
            ),
            RecommendationSkippedPaper(
                paper_id="paper-b",
                title="Paper B",
                stage="extraction",
                reason="PDF: Extraction failure: repeated schema mismatch",
            ),
            RecommendationSkippedPaper(
                paper_id="paper-c",
                title="Paper C",
                stage="extraction",
                reason="HTML: Extraction failure: repeated schema mismatch",
            ),
            RecommendationSkippedPaper(
                paper_id="paper-d",
                title="Paper D",
                stage="fetch",
                reason="HTTP 404",
            ),
            RecommendationSkippedPaper(
                paper_id="paper-e",
                title="Paper E",
                stage="extraction",
                reason="HTML: Extraction failure: different exception",
            ),
        ],
        considered_candidates=[],
        recommended_candidate=None,
        runtime=tracker.success_runtime(
            candidate_count=0,
            discovered_count=0,
            recommended_candidate_id=None,
        ),
    )
    monkeypatch.setattr(
        "app.recommendations_router.recommend_methods",
        lambda *args, **kwargs: report,
    )

    response = client.post(
        "/recommendation/run?response_detail=agent",
        json={
            "request_text": "Recommend an HPLC method for metformin in plasma",
            "analyte_name": "metformin",
            "source_mode": "open_access",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["discovery_summary"]["repeated_extraction_exception_count"] == 3


def test_recommendation_api_accepts_legacy_local_source_mode_as_local_files() -> None:
    response = client.post(
        "/recommendation/recommend",
        json={
            "request_text": "Extract the final LC-MS/MS method for carotenoids in plasma",
            "analyte_name": "carotenoids",
            "matrix_hint": "human plasma",
            "require_mass_spectrometry": True,
            "source_mode": "local",
            "local_paths": [
                str(
                    FIXTURES_DIR
                    / "Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html"
                )
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "local_files"
    assert payload["search_query_used"] is None
    assert payload["skipped_papers"] == []
    assert payload["recommended_candidate"] is not None


def test_recommendation_api_requires_target_smiles_for_local_corpus() -> None:
    response = client.post(
        "/recommendation/recommend",
        json={
            "request_text": "Recommend an LC-MS/MS method for caffeine",
            "analyte_name": "caffeine",
            "source_mode": "local_corpus",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"]["failure_classification"] == "request_invalid"
    assert payload["detail"]["runtime_status"] == "request_invalid"
    assert "target_smiles is required when source_mode is 'local_corpus'" in payload["detail"]["message"]


def test_recommendation_job_api_reports_progress_and_final_report(monkeypatch) -> None:
    def _fake_recommend_methods(*args, progress_callback=None, **kwargs) -> MethodRecommendationReport:
        tracker = RecommendationRuntimeTracker(
            kwargs["request"],
            open_access_timeout_sec=20,
            llm_observer_enabled=False,
            rate_limit_policy="5/hour",
            enable_debug_metadata=False,
        )
        if progress_callback is not None:
            progress_callback("query_papers", "Searching literature.", 1, 3)
            progress_callback("extract_methods", "Extracting shortlisted papers.", 2, 3)
            progress_callback("final_rank", "Ranking final candidates.", 3, 3)

        return MethodRecommendationReport(
            request=kwargs["request"],
            source_mode="open_access",
            search_query_used="metformin plasma hplc",
            discovered_papers=[],
            skipped_papers=[],
            considered_candidates=[],
            recommended_candidate=None,
            runtime=tracker.success_runtime(
                candidate_count=0,
                discovered_count=0,
                recommended_candidate_id=None,
            ),
        )

    monkeypatch.setattr("app.recommendations_router.recommend_methods", _fake_recommend_methods)

    response = client.post(
        "/recommendation/jobs",
        json={
            "request_text": "Recommend an HPLC method for metformin in plasma",
            "analyte_name": "metformin",
            "matrix_hint": "human plasma",
            "source_mode": "open_access",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]
    assert payload["status_url"] == f"/recommendation/jobs/{payload['job_id']}"

    status_response = client.get(payload["status_url"])
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["state"] == "completed"
    assert status_payload["stage"] == "completed"
    assert status_payload["items_completed"] == 3
    assert status_payload["items_total"] == 3
    assert status_payload["report"]["source_mode"] == "open_access"
    assert status_payload["report"]["search_query_used"] == "metformin plasma hplc"
    assert status_payload["runtime"]["status"] == "no_trustworthy_candidates"


def test_recommendation_job_api_returns_404_for_missing_job() -> None:
    response = client.get("/recommendation/jobs/recommendation-job-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Recommendation job not found."


def test_recommendation_api_returns_structured_upstream_error(monkeypatch) -> None:
    def _fake_recommend_methods(*args, **kwargs) -> MethodRecommendationReport:
        tracker = RecommendationRuntimeTracker(
            kwargs["request"],
            open_access_timeout_sec=20,
            llm_observer_enabled=False,
            rate_limit_policy="5/hour",
            enable_debug_metadata=False,
        )
        raise tracker.fail(
            runtime_status="upstream_unavailable",
            failure_classification="search_failure",
            message="Open-access search failed: upstream offline",
            retryable=True,
            failure_stage="query_papers",
        )

    monkeypatch.setattr("app.recommendations_router.recommend_methods", _fake_recommend_methods)

    response = client.post(
        "/recommendation/recommend",
        json={
            "request_text": "Recommend an HPLC method for metformin in plasma",
            "analyte_name": "metformin",
            "matrix_hint": "human plasma",
            "source_mode": "open_access",
        },
    )

    assert response.status_code == 503
    payload = response.json()["detail"]
    assert payload["runtime_status"] == "upstream_unavailable"
    assert payload["failure_classification"] == "search_failure"
    assert payload["failure_stage"] == "query_papers"
    assert payload["retryable"] is True


def test_recommendation_api_returns_structured_timeout_error(monkeypatch) -> None:
    def _fake_recommend_methods(*args, **kwargs) -> MethodRecommendationReport:
        tracker = RecommendationRuntimeTracker(
            kwargs["request"],
            open_access_timeout_sec=20,
            llm_observer_enabled=False,
            rate_limit_policy="5/hour",
            enable_debug_metadata=False,
        )
        raise tracker.fail(
            runtime_status="upstream_unavailable",
            failure_classification="timeout",
            message="Open-access fetch timed out",
            retryable=True,
            failure_stage="extract_methods",
        )

    monkeypatch.setattr("app.recommendations_router.recommend_methods", _fake_recommend_methods)

    response = client.post(
        "/recommendation/recommend",
        json={
            "request_text": "Recommend an HPLC method for metformin in plasma",
            "analyte_name": "metformin",
            "matrix_hint": "human plasma",
            "source_mode": "open_access",
        },
    )

    assert response.status_code == 504
    payload = response.json()["detail"]
    assert payload["failure_classification"] == "timeout"
    assert payload["failure_stage"] == "extract_methods"


def test_recommendation_job_api_persists_structured_failure(monkeypatch) -> None:
    def _fake_recommend_methods(*args, **kwargs) -> MethodRecommendationReport:
        tracker = RecommendationRuntimeTracker(
            kwargs["request"],
            open_access_timeout_sec=20,
            llm_observer_enabled=False,
            rate_limit_policy="5/hour",
            enable_debug_metadata=False,
        )
        raise tracker.fail(
            runtime_status="upstream_unavailable",
            failure_classification="fetch_failure",
            message="Fetch failure: publisher blocked the landing page",
            retryable=True,
            failure_stage="extract_methods",
        )

    monkeypatch.setattr("app.recommendations_router.recommend_methods", _fake_recommend_methods)

    response = client.post(
        "/recommendation/jobs",
        json={
            "request_text": "Recommend an HPLC method for metformin in plasma",
            "analyte_name": "metformin",
            "matrix_hint": "human plasma",
            "source_mode": "open_access",
        },
    )

    assert response.status_code == 200
    status_response = client.get(response.json()["status_url"])
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] == "failed"
    assert payload["runtime"]["status"] == "upstream_unavailable"
    assert payload["error_detail"]["failure_classification"] == "fetch_failure"
    assert payload["error_detail"]["failure_stage"] == "extract_methods"
    assert payload["error_message"] == "Fetch failure: publisher blocked the landing page"


def _build_record(
    *, record_id: str, local_identifier: str, smiles: str
) -> RetrievalMethodRecord:
    return RetrievalMethodRecord(
        record_id=record_id,
        source_document=SourceDocumentMetadata(
            source_document_id=f"seed:{record_id}",
            source_type="seeded",
            title=f"Synthetic LC-MS/MS method for {local_identifier} in organic solvent",
        ),
        molecular_entities=[
            HplcMolecularEntity(
                local_identifier=local_identifier,
                display_name=local_identifier,
                smiles_string=smiles,
                observed_retention_time_min=4.82,
            )
        ],
        chromatography_system=ChromatographySystem(
            mode="rp_lc",
            column_manufacturer="Agilent",
            column_name="ZORBAX Eclipse Plus C18",
            stationary_phase_chemistry="C18",
            column_length_mm=150.0,
            column_inner_diameter_mm=3.0,
            particle_size_um=3.5,
        ),
        method_parameters=MethodParameters(
            mobile_phase_a=MobilePhase(solvent="water"),
            mobile_phase_b=MobilePhase(solvent="methanol"),
            flow_rate_ml_min=0.45,
            column_temperature_c=30.0,
            run_time_min=12.0,
        ),
        provenance=RetrievalProvenance(
            extraction_mode="seeded",
            extraction_confidence=1.0,
            evidence_snippets=[
                {
                    "section_label": "Seeded record",
                    "text": f"Curated seeded LC-MS/MS record for {local_identifier} in organic solvent.",
                }
            ],
        ),
    )


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
