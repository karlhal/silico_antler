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
from app.retrieval_store import SeededRetrievalStore
from app.source_document_registry import InMemorySourceDocumentRegistry

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

client = TestClient(app)


def test_create_review_record_preserves_provenance_and_validation() -> None:
    _reset_state()
    _register_source_document(
        source_document_id="review-source-001",
        fixture_name="sample_hplc_detail_and_anchoring_article.html",
    )

    response = client.post("/source-documents/review-source-001/review-records")

    assert response.status_code == 201
    payload = response.json()
    assert payload["review_record_id"] == "review-0001"
    assert payload["status"] == "draft"
    assert payload["provenance"]["extraction_mode"] == "parsed_text"
    assert payload["provenance"]["evidence_snippets"]
    assert payload["validation"]["status"] == "needs_review"
    assert payload["record_draft"]["validation"]["status"] == "needs_review"


def test_list_and_get_review_records_return_reviewable_summary() -> None:
    _reset_state()
    _register_source_document(
        source_document_id="review-source-002",
        fixture_name="sample_hplc_alias_resolution_article.html",
    )
    create_response = client.post("/source-documents/review-source-002/review-records")
    review_record_id = create_response.json()["review_record_id"]

    list_response = client.get("/review-records")
    detail_response = client.get(f"/review-records/{review_record_id}")

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload[0]["review_record_id"] == review_record_id
    assert list_payload[0]["source_document_id"] == "review-source-002"
    assert list_payload[0]["provenance"]["evidence_snippets"]

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["extraction_snapshot"]["molecular_entity_drafts"]
    assert detail_payload["record_draft"]["molecular_entity_drafts"]


def test_review_record_status_can_be_rejected_but_not_approved_when_not_ready() -> None:
    _reset_state()
    _register_source_document(
        source_document_id="review-source-003",
        fixture_name="sample_hplc_detail_and_anchoring_article.html",
    )
    create_response = client.post("/source-documents/review-source-003/review-records")
    review_record_id = create_response.json()["review_record_id"]

    approve_response = client.post(
        f"/review-records/{review_record_id}/status",
        json={"status": "approved"},
    )
    reject_response = client.post(
        f"/review-records/{review_record_id}/status",
        json={"status": "rejected", "review_notes": "Needs manual molecule linkage"},
    )

    assert approve_response.status_code == 409
    assert (
        approve_response.json()["detail"]
        == "Only retrieval-ready records can be approved"
    )

    assert reject_response.status_code == 200
    reject_payload = reject_response.json()
    assert reject_payload["status"] == "rejected"
    assert reject_payload["review_notes"] == "Needs manual molecule linkage"


def test_review_record_can_be_approved_after_entity_resolution() -> None:
    _reset_state()
    _register_source_document(
        source_document_id="review-source-004",
        fixture_name="sample_hplc_detail_and_anchoring_article.html",
    )
    create_response = client.post("/source-documents/review-source-004/review-records")
    review_record_id = create_response.json()["review_record_id"]

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
    payload = approve_response.json()
    assert payload["status"] == "approved"
    assert payload["validation"]["retrieval_ready"] is True
    assert payload["corpus_promotion"]["status"] == "promoted"
    assert (
        payload["approved_record_snapshot"]["record"]["record_id"]
        == f"approved-{review_record_id}"
    )
    assert (
        payload["corpus_promotion"]["local_corpus_record_id"]
        == f"approved-{review_record_id}"
    )
    assert (
        payload["approved_record_snapshot"]["review_summary"]["record_state"]
        == "approved"
    )
    assert (
        payload["record_draft"]["molecular_entity_drafts"][0][
            "ready_for_retrieval_entity"
        ]
        is True
    )


def test_review_record_can_be_approved_without_immediately_promoting_into_local_corpus() -> (
    None
):
    _reset_state()
    app.state.retrieval_store = SeededRetrievalStore(records=[])
    _register_source_document(
        source_document_id="review-source-005",
        fixture_name="sample_hplc_detail_and_anchoring_article.html",
    )
    create_response = client.post("/source-documents/review-source-005/review-records")
    review_record_id = create_response.json()["review_record_id"]

    approve_response = client.post(
        f"/review-records/{review_record_id}/status",
        json={
            "status": "approved",
            "promote_to_local_corpus": False,
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
    approve_payload = approve_response.json()
    assert approve_payload["status"] == "approved"
    assert approve_payload["corpus_promotion"]["status"] == "not_promoted"

    retrieval_response = client.post(
        "/retrieval/query",
        json={"target_smiles": "c1ccccc1", "limit": 1, "min_score": 0.99},
    )
    assert retrieval_response.status_code == 200
    assert retrieval_response.json()["results"] == []

    promote_response = client.post(
        f"/review-records/{review_record_id}/promotion",
        json={"promote_to_local_corpus": True},
    )

    assert promote_response.status_code == 200
    promote_payload = promote_response.json()
    assert promote_payload["corpus_promotion"]["status"] == "promoted"
    assert (
        promote_payload["corpus_promotion"]["local_corpus_record_id"]
        == f"approved-{review_record_id}"
    )

    retrieval_response = client.post(
        "/retrieval/query",
        json={"target_smiles": "c1ccccc1", "limit": 1, "min_score": 0.99},
    )
    assert retrieval_response.status_code == 200
    assert (
        retrieval_response.json()["results"][0]["record"]["record_id"]
        == f"approved-{review_record_id}"
    )


def test_review_record_promotion_can_be_removed_from_local_corpus() -> None:
    _reset_state()
    app.state.retrieval_store = SeededRetrievalStore(records=[])
    _register_source_document(
        source_document_id="review-source-006",
        fixture_name="sample_hplc_detail_and_anchoring_article.html",
    )
    create_response = client.post("/source-documents/review-source-006/review-records")
    review_record_id = create_response.json()["review_record_id"]

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

    unpromote_response = client.post(
        f"/review-records/{review_record_id}/promotion",
        json={"promote_to_local_corpus": False},
    )

    assert unpromote_response.status_code == 200
    payload = unpromote_response.json()
    assert payload["corpus_promotion"]["status"] == "not_promoted"

    retrieval_response = client.post(
        "/retrieval/query",
        json={"target_smiles": "c1ccccc1", "limit": 1, "min_score": 0.99},
    )
    assert retrieval_response.status_code == 200
    assert retrieval_response.json()["results"] == []


def _reset_state() -> None:
    app.state.source_document_registry = InMemorySourceDocumentRegistry()
    app.state.review_record_store = SqliteReviewRecordStore()
    app.state.retrieval_store = SeededRetrievalStore.from_seed_file()


def _register_source_document(*, source_document_id: str, fixture_name: str) -> None:
    response = client.post(
        "/source-documents/",
        json={
            "source_document": {
                "source_document_id": source_document_id,
                "source_type": "html",
                "url": f"https://example.test/{source_document_id}",
            },
            "html_content": (FIXTURES_DIR / fixture_name).read_text(),
        },
    )

    assert response.status_code == 201
