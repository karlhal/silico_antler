import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("USE_MILVUS", "false")

from app.main import app
from app.sqlite_review_record_store import SqliteReviewRecordStore
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
from app.source_document_registry import InMemorySourceDocumentRegistry

client = TestClient(app)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_retrieval_query_returns_ranked_matches() -> None:
    _reset_state()
    response = client.post(
        "/retrieval/query",
        json={
            "target_smiles": "CCO",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_smiles"] == "CCO"
    assert payload["target_canonical_smiles"] == "CCO"
    assert payload["ranking_mode"] == "target_only"
    assert len(payload["results"]) == 3
    assert payload["results"][0]["record"]["record_id"] == "seed-ethanol-rp18"
    assert payload["results"][0]["matched_entity"]["local_identifier"] == "ethanol"
    assert payload["results"][0]["score"] == 1.0
    assert payload["results"][0]["match_rationale"]["match_type"] == "exact"
    assert (
        payload["results"][0]["match_rationale"]["matched_entity_display_name"]
        == "ethanol"
    )
    assert (
        "Exact molecular match" in payload["results"][0]["match_rationale"]["summary"]
    )


def test_retrieval_query_accepts_optional_impurity_smiles() -> None:
    _reset_state()
    response = client.post(
        "/retrieval/query",
        json={
            "target_smiles": "CC(C)O",
            "impurity_smiles": ["CCO", "CC(=O)C"],
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["impurity_smiles"] == ["CCO", "CC(=O)C"]
    assert payload["ranking_mode"] == "target_plus_impurities"
    assert payload["results"][0]["record"]["record_id"] == "seed-isopropanol-rp18"


def test_retrieval_query_can_change_ranking_for_mixture_queries() -> None:
    app.state.source_document_registry = InMemorySourceDocumentRegistry()
    app.state.review_record_store = SqliteReviewRecordStore()
    app.state.retrieval_store = SeededRetrievalStore(
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

    response = client.post(
        "/retrieval/query",
        json={
            "target_smiles": "CCO",
            "impurity_smiles": ["CC(=O)C"],
            "limit": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_mode"] == "target_plus_impurities"
    assert payload["results"][0]["record"]["record_id"] == "record-multi-analyte"
    assert payload["results"][0]["match_rationale"]["target_score"] == 1.0
    assert payload["results"][0]["match_rationale"]["aggregate_score"] == 1.0
    assert (
        payload["results"][0]["match_rationale"]["impurity_matches"][0][
            "matched_entity_local_identifier"
        ]
        == "acetone"
    )
    assert "Mixture-aware score" in payload["results"][0]["match_rationale"]["summary"]


def test_retrieval_query_rejects_invalid_smiles() -> None:
    _reset_state()
    response = client.post(
        "/retrieval/query",
        json={
            "target_smiles": "not-a-smiles",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid SMILES: not-a-smiles"


def test_retrieval_query_can_return_empty_results() -> None:
    _reset_state()
    response = client.post(
        "/retrieval/query",
        json={
            "target_smiles": "c1ccccc1",
            "min_score": 0.99,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"] == []


def test_retrieval_query_can_return_approved_review_record_with_review_summary() -> (
    None
):
    _reset_state()
    register_response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": "retrieval-review-001",
                "source_type": "html",
                "url": "https://example.test/retrieval-review-001",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
            ).read_text(),
        },
    )
    assert register_response.status_code == 201

    review_response = client.post(
        "/source-documents/retrieval-review-001/review-records"
    )
    review_record_id = review_response.json()["review_record_id"]

    approve_response = client.post(
        f"/review-records/{review_record_id}/status",
        json={
            "status": "approved",
            "entity_resolutions": [
                {
                    "local_identifier": "intermediate 2",
                    "smiles_string": "c1ccccc1",
                    "display_name": "Intermediate 2",
                }
            ],
        },
    )
    assert approve_response.status_code == 200

    query_response = client.post(
        "/retrieval/query",
        json={"target_smiles": "c1ccccc1", "limit": 1, "min_score": 0.99},
    )

    assert query_response.status_code == 200
    payload = query_response.json()
    assert (
        payload["results"][0]["record"]["record_id"] == f"approved-{review_record_id}"
    )
    assert payload["results"][0]["match_rationale"]["match_type"] == "exact"
    assert payload["results"][0]["review_summary"]["record_state"] == "approved"
    assert (
        payload["results"][0]["review_summary"]["review_record_id"] == review_record_id
    )
    assert payload["results"][0]["review_summary"]["retrieval_ready"] is True
    assert (
        payload["results"][0]["review_summary"]["corpus_origin"]
        == "review_promoted"
    )


def _reset_state() -> None:
    app.state.source_document_registry = InMemorySourceDocumentRegistry()
    app.state.review_record_store = SqliteReviewRecordStore()
    app.state.retrieval_store = SeededRetrievalStore.from_seed_file()


def _build_record(
    *, record_id: str, entities: list[tuple[str, str]]
) -> RetrievalMethodRecord:
    return RetrievalMethodRecord(
        record_id=record_id,
        source_document=SourceDocumentMetadata(
            source_document_id=f"seed:{record_id}",
            source_type="seeded",
            title=f"Synthetic record {record_id}",
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
            column_name="Acquity BEH C18",
            stationary_phase_chemistry="C18",
            column_length_mm=100.0,
            column_inner_diameter_mm=2.1,
            particle_size_um=1.7,
        ),
        method_parameters=MethodParameters(
            mobile_phase_a=MobilePhase(solvent="water"),
            mobile_phase_b=MobilePhase(solvent="acetonitrile"),
            flow_rate_ml_min=0.35,
        ),
        provenance=RetrievalProvenance(
            extraction_mode="seeded",
            extraction_confidence=1.0,
        ),
    )
