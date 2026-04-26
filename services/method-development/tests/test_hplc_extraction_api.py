import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("USE_MILVUS", "false")

from app.main import app
from app.source_document_registry import InMemorySourceDocumentRegistry

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

client = TestClient(app)


def test_extract_hplc_endpoint_returns_method_components() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-001",
                "source_type": "html",
                "url": "https://example.test/extract-api-001",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_extraction_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-001/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    assert payload["chromatography_system"]["stationary_phase_chemistry"] == "C18"
    assert payload["method_parameters"]["flow_rate_ml_min"] == 1.0
    assert (
        payload["retention_time_observations"][0]["observed_retention_time_min"] == 16.7
    )


def test_extract_hplc_endpoint_rejects_unknown_document() -> None:
    _reset_registry()

    response = client.post("/source-documents/missing-doc/extract-hplc")

    assert response.status_code == 404
    assert response.json()["detail"] == "Source document not found: missing-doc"


def test_extract_hplc_endpoint_returns_mobile_phase_candidates() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-002",
                "source_type": "html",
                "url": "https://example.test/extract-api-002",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_alternative_solvents_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-002/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    assert payload["method_parameters"]["mobile_phase_b"]["solvent"] == "methanol"
    selected_candidates = [
        candidate
        for candidate in payload["mobile_phase_candidates"]
        if candidate["selected_for_method_parameters"]
    ]
    assert len(selected_candidates) == 1
    assert selected_candidates[0]["candidate_kind"] == "full_system"
    replacement_candidates = [
        candidate
        for candidate in payload["mobile_phase_candidates"]
        if candidate["candidate_kind"] == "replacement_note"
    ]
    assert replacement_candidates[0]["comparison_from_text"] == "acetonitrile"
    assert replacement_candidates[0]["comparison_to_text"] == "phosphate buffer"


def test_extract_hplc_endpoint_returns_gradient_candidates() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-003",
                "source_type": "html",
                "url": "https://example.test/extract-api-003",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_gradient_candidates_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-003/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    assert payload["method_parameters"]["gradient_profile"][0]["percent_b"] == 10.0
    selected_candidates = [
        candidate
        for candidate in payload["gradient_candidates"]
        if candidate["selected_for_method_parameters"]
    ]
    assert len(selected_candidates) == 1
    assert selected_candidates[0]["candidate_kind"] == "text_statement"
    table_candidates = [
        candidate
        for candidate in payload["gradient_candidates"]
        if candidate["candidate_kind"] == "table_derived"
    ]
    assert len(table_candidates) == 1


def test_extract_hplc_endpoint_returns_record_draft_and_system_candidates() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-004",
                "source_type": "html",
                "url": "https://example.test/extract-api-004",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_candidate_selection_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-004/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    assert payload["chromatography_system"]["column_name"] == "YMC-Pack ODS-AQ"
    selected_system_candidates = [
        candidate
        for candidate in payload["chromatography_system_candidates"]
        if candidate["selected_for_output"]
    ]
    assert len(selected_system_candidates) == 1
    assert selected_system_candidates[0]["candidate_role"] == "final"
    selected_observations = [
        observation
        for observation in payload["retention_time_observations"]
        if observation["selected_for_record_draft"]
    ]
    assert len(selected_observations) == 1
    assert selected_observations[0]["local_identifier"] == "PMP-glucose"
    assert payload["record_draft"]["record_id"] == "draft-extract-api-004"


def test_extract_hplc_endpoint_returns_detail_and_anchor_candidates() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-005",
                "source_type": "html",
                "url": "https://example.test/extract-api-005",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-005/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    assert (
        payload["method_parameters"]["mobile_phase_a"]["additive"] == "0.1% formic acid"
    )
    assert payload["method_parameters"]["mobile_phase_a"]["ph_estimate"] == 3.2
    assert payload["method_parameters"]["run_time_min"] == 12.0
    assert len(payload["mobile_phase_detail_candidates"]) >= 1
    assert len(payload["timing_candidates"]) >= 2
    selected_entities = [
        candidate
        for candidate in payload["anchored_entity_candidates"]
        if candidate["selected_for_record_draft"]
    ]
    assert len(selected_entities) == 1
    assert selected_entities[0]["local_identifier"] == "intermediate 2"
    assert (
        payload["record_draft"]["anchored_entities"][0]["local_identifier"]
        == "intermediate 2"
    )


def test_extract_hplc_endpoint_returns_molecular_entity_drafts() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-006",
                "source_type": "html",
                "url": "https://example.test/extract-api-006",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_alias_resolution_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-006/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    drafts = payload["record_draft"]["molecular_entity_drafts"]
    assert len(drafts) == 2
    compound_draft = next(
        draft for draft in drafts if draft["local_identifier"] == "4a"
    )
    assert set(alias.lower() for alias in compound_draft["aliases"]) >= {
        "compound 4a",
        "4a",
        "target compound",
        "desired isomer",
        "main peak",
    }
    assert compound_draft["placeholder_smiles_string"] == "UNRESOLVED::4a"
    assert compound_draft["smiles_linkage_status"] == "unresolved_local_identifier"
    assert set(compound_draft["linkage_lookup_keys"]) >= {"4a", "compound 4a"}


def test_extract_hplc_endpoint_returns_record_validation_state() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-007",
                "source_type": "html",
                "url": "https://example.test/extract-api-007",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_invalid_validation_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-007/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    assert payload["retrieval_record_ready"] is False
    assert payload["record_draft"]["validation"]["status"] == "invalid"
    issue_codes = {
        issue["code"] for issue in payload["record_draft"]["validation"]["issues"]
    }
    assert "flow_rate_high_for_narrow_column" in issue_codes
    assert "ph_outside_stationary_phase_range" in issue_codes


def test_extract_hplc_endpoint_reports_generic_anchor_placeholder() -> None:
    _reset_registry()

    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "extract-api-008",
                "source_type": "html",
                "url": "https://example.test/extract-api-008",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_generic_alias_article.html"
            ).read_text(),
        },
    )

    assert register_response.status_code == 201

    extract_response = client.post("/source-documents/extract-api-008/extract-hplc")

    assert extract_response.status_code == 200
    payload = extract_response.json()
    draft = payload["record_draft"]["molecular_entity_drafts"][0]
    assert draft["local_identifier"] == "main peak"
    assert draft["smiles_linkage_status"] == "placeholder_generated"
    issue_codes = {
        issue["code"] for issue in payload["record_draft"]["validation"]["issues"]
    }
    assert "generic_anchor_unresolved" in issue_codes


def _reset_registry() -> None:
    app.state.source_document_registry = InMemorySourceDocumentRegistry()
