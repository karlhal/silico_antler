import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("USE_MILVUS", "false")

from app.main import app
from app.ai_runtime_settings import AiRuntimeSettings
from app.gemini_orchestration_client import GeminiObserverInsight
from app.sqlite_review_record_store import SqliteReviewRecordStore
from app.retrieval_store import SeededRetrievalStore
from app.source_document_registry import InMemorySourceDocumentRegistry

client = TestClient(app)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_c12_orchestration_creates_review_record_and_blocks_unready_approval() -> None:
    _reset_state()

    response = client.post(
        "/c12/review-records/orchestrate",
        json={
            "source_document": {
                "source_document_id": "c12-orch-001",
                "source_type": "html",
                "url": "https://example.test/c12-orch-001",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
            ).read_text(),
            "approve_if_ready": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["budget"]["max_total_steps"] == 5
    assert payload["budget"]["total_steps_attempted"] == 4
    assert payload["steps"]["registration"]["state"] == "completed"
    assert payload["steps"]["registration"]["status"] == "created"
    assert payload["steps"]["extraction"]["status"] == "completed"
    assert payload["steps"]["review_record"]["status"] == "created"
    assert payload["steps"]["approval"]["state"] == "blocked"
    assert payload["steps"]["approval"]["status"] == "blocked"
    assert payload["steps"]["ai_observer"]["status"] == "skipped"
    assert payload["review_record"]["status"] == "draft"


def test_c12_orchestration_reuses_existing_review_record_on_retry() -> None:
    _reset_state()
    request_payload = {
        "source_document": {
            "source_document_id": "c12-orch-002",
            "source_type": "html",
            "url": "https://example.test/c12-orch-002",
        },
        "html_content": (
            FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
        ).read_text(),
        "retry_existing": True,
    }

    first_response = client.post(
        "/c12/review-records/orchestrate", json=request_payload
    )
    second_response = client.post(
        "/c12/review-records/orchestrate",
        json=request_payload,
    )
    list_response = client.get("/review-records")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["budget"]["total_steps_attempted"] == 3
    assert second_response.json()["steps"]["registration"]["status"] == "reused"
    assert second_response.json()["steps"]["registration"]["state"] == "reused"
    assert second_response.json()["steps"]["extraction"]["status"] == "reused"
    assert second_response.json()["steps"]["review_record"]["status"] == "reused"
    assert second_response.json()["steps"]["ai_observer"]["status"] == "skipped"
    assert (
        first_response.json()["review_record"]["review_record_id"]
        == second_response.json()["review_record"]["review_record_id"]
    )
    assert len(list_response.json()) == 1


def test_c12_orchestration_can_approve_and_materialize_review_record() -> None:
    _reset_state()

    response = client.post(
        "/c12/review-records/orchestrate",
        json={
            "source_document": {
                "source_document_id": "c12-orch-003",
                "source_type": "html",
                "url": "https://example.test/c12-orch-003",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
            ).read_text(),
            "approve_if_ready": True,
            "entity_resolutions": [
                {
                    "local_identifier": "intermediate 2",
                    "smiles_string": "c1ccccc1",
                    "display_name": "Intermediate 2",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["budget"]["total_steps_attempted"] == 4
    assert payload["steps"]["approval"]["status"] == "approved"
    assert payload["steps"]["approval"]["state"] == "completed"
    assert payload["steps"]["ai_observer"]["status"] == "skipped"
    assert payload["review_record"]["status"] == "approved"
    assert payload["review_record"]["validation"]["retrieval_ready"] is True

    retrieval_response = client.post(
        "/retrieval/query",
        json={"target_smiles": "c1ccccc1", "limit": 1, "min_score": 0.99},
    )
    assert retrieval_response.status_code == 200
    assert (
        retrieval_response.json()["results"][0]["review_summary"]["record_state"]
        == "approved"
    )


def test_c12_orchestration_rejects_duplicate_registration_when_retry_disabled() -> None:
    _reset_state()
    request_payload = {
        "source_document": {
            "source_document_id": "c12-orch-004",
            "source_type": "html",
            "url": "https://example.test/c12-orch-004",
        },
        "html_content": (
            FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
        ).read_text(),
        "retry_existing": True,
    }
    client.post("/c12/review-records/orchestrate", json=request_payload)

    duplicate_response = client.post(
        "/c12/review-records/orchestrate",
        json={**request_payload, "retry_existing": False},
    )

    assert duplicate_response.status_code == 409
    assert "already registered" in duplicate_response.json()["detail"]


def test_c12_orchestration_stops_at_explicit_budget_cutoff_before_approval() -> None:
    _reset_state()

    response = client.post(
        "/c12/review-records/orchestrate",
        json={
            "source_document": {
                "source_document_id": "c12-orch-005",
                "source_type": "html",
                "url": "https://example.test/c12-orch-005",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
            ).read_text(),
            "approve_if_ready": True,
            "entity_resolutions": [
                {
                    "local_identifier": "intermediate 2",
                    "smiles_string": "c1ccccc1",
                    "display_name": "Intermediate 2",
                }
            ],
            "max_total_steps": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["budget"]["cutoff_reached"] is True
    assert payload["budget"]["total_steps_attempted"] == 3
    assert payload["steps"]["approval"]["state"] == "cutoff"
    assert payload["steps"]["approval"]["status"] == "skipped"
    assert "cutoff" in payload["steps"]["approval"]["reason"].lower()
    assert payload["review_record"]["status"] == "draft"


def test_c12_orchestration_applies_server_side_budget_caps() -> None:
    _reset_state(
        ai_runtime_settings=AiRuntimeSettings(
            google_api_key=None,
            enable_llm_orchestration=False,
            planner_model="gemini-2.5-pro",
            worker_model="gemini-2.5-flash",
            llm_timeout_sec=20,
            llm_max_calls_per_run=6,
            max_step_attempts_per_run=1,
            max_total_steps_per_run=3,
        )
    )

    response = client.post(
        "/c12/review-records/orchestrate",
        json={
            "source_document": {
                "source_document_id": "c12-orch-006",
                "source_type": "html",
                "url": "https://example.test/c12-orch-006",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
            ).read_text(),
            "approve_if_ready": True,
            "max_total_steps": 8,
            "max_step_attempts": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["budget"]["max_total_steps"] == 3
    assert payload["budget"]["max_step_attempts"] == 1
    assert payload["budget"]["cutoff_reached"] is True
    assert payload["steps"]["approval"]["state"] == "cutoff"


def test_c12_orchestration_can_attach_gemini_observer_summary() -> None:
    _reset_state(
        ai_runtime_settings=AiRuntimeSettings(
            google_api_key="demo-key",
            enable_llm_orchestration=True,
            planner_model="gemini-2.5-pro",
            worker_model="gemini-2.5-flash",
            llm_timeout_sec=20,
            llm_max_calls_per_run=6,
            max_step_attempts_per_run=1,
            max_total_steps_per_run=5,
        ),
        gemini_client=_FakeGeminiClient(),
    )

    response = client.post(
        "/c12/review-records/orchestrate",
        json={
            "source_document": {
                "source_document_id": "c12-orch-007",
                "source_type": "html",
                "url": "https://example.test/c12-orch-007",
            },
            "html_content": (
                FIXTURES_DIR / "sample_hplc_detail_and_anchoring_article.html"
            ).read_text(),
            "approve_if_ready": True,
            "entity_resolutions": [
                {
                    "local_identifier": "intermediate 2",
                    "smiles_string": "c1ccccc1",
                    "display_name": "Intermediate 2",
                }
            ],
            "max_total_steps": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["budget"]["total_steps_attempted"] == 5
    assert payload["steps"]["ai_observer"]["status"] == "completed"
    assert payload["steps"]["ai_observer"]["state"] == "completed"
    assert payload["steps"]["ai_observer"]["model"] == "gemini-2.5-pro"
    assert (
        payload["steps"]["ai_observer"]["recommended_next_action"] == "proceed_to_demo"
    )


def _reset_state(
    ai_runtime_settings: AiRuntimeSettings | None = None,
    gemini_client: object | None = None,
) -> None:
    app.state.source_document_registry = InMemorySourceDocumentRegistry()
    app.state.review_record_store = SqliteReviewRecordStore()
    app.state.retrieval_store = SeededRetrievalStore.from_seed_file()
    app.state.ai_runtime_settings = ai_runtime_settings or AiRuntimeSettings(
        google_api_key=None,
        enable_llm_orchestration=False,
        planner_model="gemini-2.5-pro",
        worker_model="gemini-2.5-flash",
        llm_timeout_sec=20,
        llm_max_calls_per_run=6,
        max_step_attempts_per_run=1,
        max_total_steps_per_run=5,
    )
    app.state.gemini_client = gemini_client


class _FakeGeminiClient:
    def summarize_c12_outcome(self, **_: object) -> GeminiObserverInsight:
        return GeminiObserverInsight(
            model="gemini-2.5-pro",
            summary="Review record is approved and demo-ready.",
            recommended_next_action="proceed_to_demo",
            concerns=(),
        )
