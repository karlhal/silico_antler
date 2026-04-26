from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.open_access_client import OpenAccessPaperClient
from app.recommendation_engine import recommend_methods
from app.recommendation_schemas import (
    FetchedSourceArtifact,
    MethodRecommendationRequest,
    OpenAccessPaperCandidate,
    SystemSpecs,
)
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


TESTS_DIR = Path(__file__).resolve().parent
PAPER_FIXTURES_DIR = TESTS_DIR / "paper_example"
GOLDEN_CASES_PATH = TESTS_DIR / "fixtures" / "recommendation_golden_cases.json"

_GOLDEN_CASES = json.loads(GOLDEN_CASES_PATH.read_text())
_RECOMMENDATION_CASES = _GOLDEN_CASES["recommendation_cases"]
_LOCAL_CORPUS_CASES = _GOLDEN_CASES["local_corpus_cases"]

_PAPER_FIXTURE_ALIASES = {
    "carotenoids_plasma_html": (
        PAPER_FIXTURES_DIR
        / "Development of an Advanced HPLC–MS_MS Method for the Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma.html"
    ),
    "plos_glucose_pdf": PAPER_FIXTURES_DIR / "paper_test2.pdf",
}


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
                title=(
                    "Development of an Advanced HPLC-MS/MS Method for the "
                    "Determination of Carotenoids and Fat-Soluble Vitamins in Human Plasma"
                ),
                doi="10.3390/ijms17101719",
                url="https://example.test/mdpi",
                pdf_url=None,
                published_year=2016,
                source_name="International Journal of Molecular Sciences",
                abstract=(
                    "Carotenoids and vitamins in plasma were analyzed by HPLC-MS/MS."
                ),
                open_access=True,
            )
        ]

    def fetch_source_artifact(
        self, candidate: OpenAccessPaperCandidate
    ) -> FetchedSourceArtifact:
        paper_path = _PAPER_FIXTURE_ALIASES["carotenoids_plasma_html"]
        return FetchedSourceArtifact(
            paper_id=candidate.paper_id,
            kind="html",
            title=candidate.title,
            doi=candidate.doi,
            url=candidate.url,
            published_year=candidate.published_year,
            file_name="mdpi.html",
            html_content=paper_path.read_text(),
        )


@pytest.mark.parametrize(
    "case",
    _RECOMMENDATION_CASES,
    ids=[case["case_id"] for case in _RECOMMENDATION_CASES],
)
def test_recommendation_golden_cases(case: dict) -> None:
    request_payload = case["request"]
    request = MethodRecommendationRequest(
        request_text=request_payload["request_text"],
        analyte_name=request_payload["analyte_name"],
        matrix_hint=request_payload.get("matrix_hint"),
        preferred_mode=request_payload.get("preferred_mode"),
        require_mass_spectrometry=request_payload.get(
            "require_mass_spectrometry", False
        ),
        source_mode=case["source_mode"],
        max_papers=request_payload["max_papers"],
        system_specs=SystemSpecs(**request_payload["system_specs"]),
        local_paths=_build_local_paths(case),
    )

    report = recommend_methods(
        request,
        open_access_client=(
            _FakeOpenAccessPaperClient()
            if case["source_mode"] == "open_access"
            else None
        ),
    )

    expected = case["expected"]
    best = report.recommended_candidate

    assert best is not None
    assert report.source_mode == case["source_mode"]
    assert len(report.discovered_papers) == expected["discovered_paper_count"]
    assert best.paper_id == expected["recommended_paper_id"]

    assert best.score.total_score == pytest.approx(expected["total_score"])
    assert best.score.system_match == pytest.approx(expected["system_match"])
    assert best.score.analyte_match == pytest.approx(expected["analyte_match"])
    assert best.score.matrix_fit == pytest.approx(expected["matrix_fit"])
    assert best.score.practical_fit == pytest.approx(expected["practical_fit"])
    assert best.score.extraction_confidence == pytest.approx(
        expected["extraction_confidence"]
    )
    assert best.score.literature_relevance == pytest.approx(
        expected["literature_relevance"]
    )

    assert best.recommended_method is not None
    if "scaled_flow_rate_ml_min" in expected:
        assert best.recommended_method.is_scaled is True
        assert best.recommended_method.flow_rate_ml_min == pytest.approx(
            expected["scaled_flow_rate_ml_min"]
        )
        assert best.recommended_method.injection_volume_ul == pytest.approx(
            expected["scaled_injection_volume_ul"]
        )
        assert best.recommended_method.run_time_min == pytest.approx(
            expected["scaled_run_time_min"]
        )
        assert len(best.recommended_method.gradient_profile) == expected[
            "scaled_gradient_points"
        ]
    else:
        assert best.recommended_method.is_scaled is False
    assert len(best.extraction.provenance.evidence_snippets) >= expected[
        "min_evidence_count"
    ]
    assert best.evidence_snippets
    assert len(best.evidence_snippets) <= 3
    assert best.trust.trust_state == _expected_trust_state(case["source_mode"])
    assert best.trust.manual_verification_required is True
    assert best.trust.validation_status == _validation_for_candidate(best)
    assert best.trust.issue_counts.model_dump() == _expected_issue_counts(best)
    assert len(best.trust.warning_summary) <= 3

    for fragment in expected["required_rationale_fragments"]:
        assert fragment in best.rationale

    for fragment in expected.get("required_scaling_note_fragments", []):
        assert any(
            fragment in note for note in best.recommended_method.scaling_notes
        )


@pytest.mark.parametrize(
    "case",
    _LOCAL_CORPUS_CASES,
    ids=[case["case_id"] for case in _LOCAL_CORPUS_CASES],
)
def test_local_corpus_golden_cases(case: dict) -> None:
    query = case["query"]
    expected = case["expected"]

    if case["case_id"] == "local_corpus_target_plus_impurity_prefers_multi_analyte":
        store = SeededRetrievalStore(
            records=[
                _build_record(
                    record_id="record-target-only",
                    entities=[("ethanol", "CCO")],
                ),
                _build_record(
                    record_id="record-multi-analyte",
                    entities=[("ethanol", "CCO"), ("acetone", "CC(=O)C")],
                ),
            ]
        )
    else:
        store = SeededRetrievalStore.from_seed_file()

    matches = store.search(
        query["target_smiles"],
        impurity_smiles=query.get("impurity_smiles", []),
        limit=query["limit"],
        matrix_hint=query.get("matrix_hint"),
        preferred_mode=query.get("preferred_mode"),
        require_mass_spectrometry=query.get("require_mass_spectrometry", False),
        apply_contextual_priors=query.get("apply_contextual_priors", False),
    )

    assert matches
    top = matches[0]

    assert top.record.record_id == expected["top_record_id"]
    assert top.score == pytest.approx(expected["top_score"])
    assert expected["required_summary_fragment"] in top.match_rationale.summary

    if "top_matched_entity" in expected:
        assert top.matched_entity.local_identifier == expected["top_matched_entity"]
        assert top.match_rationale.match_type == expected["match_type"]
        assert top.review_summary.record_state == expected["review_state"]
        assert top.match_rationale.supporting_snippet is not None
        assert expected["required_snippet_fragment"] in top.match_rationale.supporting_snippet.text
        if "corpus_origin" in expected:
            assert top.review_summary.corpus_origin == expected["corpus_origin"]
        if "mode" in expected:
            assert top.record.chromatography_system.mode == expected["mode"]

    if "impurity_match_count" in expected:
        assert len(top.match_rationale.impurity_matches) == expected[
            "impurity_match_count"
        ]
        assert (
            top.match_rationale.impurity_matches[0].matched_entity_local_identifier
            == expected["top_impurity_identifier"]
        )


def test_local_corpus_recommendation_golden_case_prefers_better_fit() -> None:
    store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="zzz-bad-fit",
                entities=[("caffeine", "Cn1c(=O)c2c(ncn2C)n(C)c1=O")],
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
                entities=[("caffeine", "Cn1c(=O)c2c(ncn2C)n(C)c1=O")],
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
            system_specs=SystemSpecs(
                column_manufacturer="Waters",
                column_name="XBridge BEH C18",
                column_chemistry="C18",
                column_length_mm=100,
                column_inner_diameter_mm=2.1,
                particle_size_um=3.5,
            ),
            max_run_time_min=10,
        ),
        retrieval_store=store,
    )

    assert report.recommended_candidate is not None
    assert report.recommended_candidate.paper_id == "aaa-good-fit"
    assert (
        report.considered_candidates[0].score.total_score
        > report.considered_candidates[1].score.total_score
    )
    assert (
        report.considered_candidates[0].score.system_match
        > report.considered_candidates[1].score.system_match
    )
    assert (
        report.considered_candidates[0].score.practical_fit
        > report.considered_candidates[1].score.practical_fit
    )
    assert report.considered_candidates[0].match_rationale is not None
    assert report.considered_candidates[0].review_summary is not None


def test_golden_case_manifest_preserves_current_source_mode_distinctions() -> None:
    recommendation_modes = {case["source_mode"] for case in _RECOMMENDATION_CASES}
    local_corpus_case_ids = {case["case_id"] for case in _LOCAL_CORPUS_CASES}

    assert recommendation_modes == {"local_files", "open_access"}
    assert any(case_id.startswith("local_corpus_") for case_id in local_corpus_case_ids)
    assert "local_files_carotenoids_plasma_msms" in {
        case["case_id"] for case in _RECOMMENDATION_CASES
    }
    assert "local_files_plos_glucose_pmp_rplc" in {
        case["case_id"] for case in _RECOMMENDATION_CASES
    }
    assert "local_corpus_metformin_hilic_seeded" in local_corpus_case_ids
    assert "open_access_carotenoids_plasma_msms" in {
        case["case_id"] for case in _RECOMMENDATION_CASES
    }


def _build_local_paths(case: dict) -> list[str]:
    if case["source_mode"] != "local_files":
        return []
    return [str(_PAPER_FIXTURE_ALIASES[case["paper_fixture"]])]


def _build_record(
    *,
    record_id: str,
    entities: list[tuple[str, str]],
    title: str | None = None,
    column_manufacturer: str = "Waters",
    column_name: str = "Acquity BEH C18",
    column_length_mm: float = 100.0,
    column_inner_diameter_mm: float = 2.1,
    particle_size_um: float = 1.7,
    run_time_min: float = 12.0,
    evidence_text: str | None = None,
) -> RetrievalMethodRecord:
    title = title or f"Synthetic LC-MS/MS method for {record_id} in organic solvent"
    evidence_text = evidence_text or (
        f"Synthetic LC-MS/MS record {record_id} used for local-corpus recommendation acceptance ranking in organic solvent."
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
                local_identifier=local_identifier,
                display_name=local_identifier,
                smiles_string=smiles,
            )
            for local_identifier, smiles in entities
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
            mobile_phase_b=MobilePhase(solvent="acetonitrile"),
            flow_rate_ml_min=0.35,
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
    )


def _expected_trust_state(source_mode: str) -> str:
    if source_mode == "open_access":
        return "open_access_extracted"
    return "local_file_extracted"


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
