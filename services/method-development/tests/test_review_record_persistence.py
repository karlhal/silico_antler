import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.hplc_text_extraction import extract_minimal_hplc
from app.review_record_materialization import sync_promoted_review_records
from app.review_record_schemas import (
    MolecularEntityResolutionInput,
    ReviewRecordApprovalUpdate,
)
from app.sqlite_review_record_store import SqliteReviewRecordStore
from app.retrieval_schemas import SourceDocumentMetadata
from app.retrieval_store import SeededRetrievalStore
from app.source_document_ingestion import ingest_html_document

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_review_record_store_persists_and_reloads_records(tmp_path: Path) -> None:
    persistence_path = tmp_path / "review_records.json"
    store = SqliteReviewRecordStore(persistence_path=persistence_path)
    extraction = _build_extraction("sample_hplc_detail_and_anchoring_article.html")

    created_record = store.create_from_extraction(extraction)
    reloaded_store = SqliteReviewRecordStore.from_persistence_path(persistence_path)

    assert persistence_path.exists()
    reloaded_record = reloaded_store.get(created_record.review_record_id)
    assert reloaded_record.review_record_id == created_record.review_record_id
    assert reloaded_record.provenance.evidence_snippets
    assert reloaded_store.list()[0].review_record_id == created_record.review_record_id


def test_persisted_approved_review_records_rehydrate_into_retrieval_store(
    tmp_path: Path,
) -> None:
    persistence_path = tmp_path / "review_records.json"
    store = SqliteReviewRecordStore(persistence_path=persistence_path)
    extraction = _build_extraction("sample_hplc_detail_and_anchoring_article.html")
    review_record = store.create_from_extraction(extraction)

    approved_record = store.update_status(
        review_record.review_record_id,
        ReviewRecordApprovalUpdate(
            status="approved",
            entity_resolutions=[
                MolecularEntityResolutionInput(
                    local_identifier="intermediate 2",
                    smiles_string="c1ccccc1",
                    display_name="Intermediate 2",
                )
            ],
        ),
    )

    reloaded_store = SqliteReviewRecordStore.from_persistence_path(persistence_path)
    reloaded_record = reloaded_store.get(review_record.review_record_id)
    retrieval_store = SeededRetrievalStore.from_seed_file()
    sync_promoted_review_records(reloaded_store.all_records(), retrieval_store)
    matches = retrieval_store.search("c1ccccc1", limit=3, min_score=0.99)

    assert approved_record.status == "approved"
    assert reloaded_record.approved_record_snapshot is not None
    assert reloaded_record.corpus_promotion.status == "promoted"
    assert (
        reloaded_record.approved_record_snapshot.record.record_id
        == f"approved-{review_record.review_record_id}"
    )
    assert any(
        match.record.record_id == f"approved-{review_record.review_record_id}"
        for match in matches
    )
    approved_match = next(
        match
        for match in matches
        if match.record.record_id == f"approved-{review_record.review_record_id}"
    )
    assert approved_match.review_summary.record_state == "approved"
    assert (
        approved_match.review_summary.review_record_id == review_record.review_record_id
    )


def test_sync_uses_frozen_approved_record_snapshot_instead_of_recomputing(
    tmp_path: Path,
) -> None:
    persistence_path = tmp_path / "review_records.json"
    store = SqliteReviewRecordStore(persistence_path=persistence_path)
    extraction = _build_extraction("sample_hplc_detail_and_anchoring_article.html")
    review_record = store.create_from_extraction(extraction)
    store.update_status(
        review_record.review_record_id,
        ReviewRecordApprovalUpdate(
            status="approved",
            entity_resolutions=[
                MolecularEntityResolutionInput(
                    local_identifier="intermediate 2",
                    smiles_string="c1ccccc1",
                    display_name="Intermediate 2",
                )
            ],
        ),
    )

    reloaded_store = SqliteReviewRecordStore.from_persistence_path(persistence_path)
    reloaded_record = reloaded_store.get(review_record.review_record_id)
    assert reloaded_record.record_draft is not None

    tampered_drafts = [
        draft.model_copy(
            update={"smiles_string": "CCO", "ready_for_retrieval_entity": True}
        )
        if draft.local_identifier == "intermediate 2"
        else draft
        for draft in reloaded_record.record_draft.molecular_entity_drafts
    ]
    tampered_record = reloaded_record.model_copy(
        update={
            "record_draft": reloaded_record.record_draft.model_copy(
                update={"molecular_entity_drafts": tampered_drafts}
            )
        }
    )

    retrieval_store = SeededRetrievalStore.from_seed_file()
    sync_promoted_review_records([tampered_record], retrieval_store)

    benzene_matches = retrieval_store.search("c1ccccc1", limit=3, min_score=0.99)
    ethanol_matches = retrieval_store.search("CCO", limit=10, min_score=0.99)

    assert any(
        match.record.record_id == f"approved-{review_record.review_record_id}"
        for match in benzene_matches
    )
    assert not any(
        match.record.record_id == f"approved-{review_record.review_record_id}"
        for match in ethanol_matches
    )


def test_sync_only_rehydrates_promoted_review_records(tmp_path: Path) -> None:
    persistence_path = tmp_path / "review_records.json"
    store = SqliteReviewRecordStore(persistence_path=persistence_path)
    extraction = _build_extraction("sample_hplc_detail_and_anchoring_article.html")
    review_record = store.create_from_extraction(extraction)
    store.update_status(
        review_record.review_record_id,
        ReviewRecordApprovalUpdate(
            status="approved",
            promote_to_local_corpus=False,
            entity_resolutions=[
                MolecularEntityResolutionInput(
                    local_identifier="intermediate 2",
                    smiles_string="c1ccccc1",
                    display_name="Intermediate 2",
                )
            ],
        ),
    )

    reloaded_store = SqliteReviewRecordStore.from_persistence_path(persistence_path)
    retrieval_store = SeededRetrievalStore(records=[])
    sync_promoted_review_records(reloaded_store.all_records(), retrieval_store)

    matches = retrieval_store.search("c1ccccc1", limit=1, min_score=0.99)

    assert reloaded_store.get(review_record.review_record_id).status == "approved"
    assert (
        reloaded_store.get(review_record.review_record_id).corpus_promotion.status
        == "not_promoted"
    )
    assert matches == []


def test_legacy_approved_review_records_without_promotion_metadata_still_rehydrate(
    tmp_path: Path,
) -> None:
    persistence_path = tmp_path / "review_records.json"
    store = SqliteReviewRecordStore(persistence_path=persistence_path)
    extraction = _build_extraction("sample_hplc_detail_and_anchoring_article.html")
    review_record = store.create_from_extraction(extraction)
    store.update_status(
        review_record.review_record_id,
        ReviewRecordApprovalUpdate(
            status="approved",
            entity_resolutions=[
                MolecularEntityResolutionInput(
                    local_identifier="intermediate 2",
                    smiles_string="c1ccccc1",
                    display_name="Intermediate 2",
                )
            ],
        ),
    )

    import sqlite3
    with sqlite3.connect(persistence_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT review_record_id, storage_payload FROM review_records")
        rows = list(cur)
        for row in rows:
            record_data = json.loads(row["storage_payload"])
            record_data.pop("corpus_promotion", None)
            conn.execute("UPDATE review_records SET storage_payload = ? WHERE review_record_id = ?", (json.dumps(record_data), row["review_record_id"]))

    reloaded_store = SqliteReviewRecordStore.from_persistence_path(persistence_path)
    retrieval_store = SeededRetrievalStore(records=[])
    sync_promoted_review_records(reloaded_store.all_records(), retrieval_store)
    matches = retrieval_store.search("c1ccccc1", limit=1, min_score=0.99)

    assert (
        reloaded_store.get(review_record.review_record_id).corpus_promotion.status
        == "promoted"
    )
    assert matches[0].record.record_id == f"approved-{review_record.review_record_id}"


def _build_extraction(fixture_name: str):
    document = ingest_html_document(
        SourceDocumentMetadata(
            source_document_id=f"persist-{fixture_name}",
            source_type="html",
            url=f"https://example.test/{fixture_name}",
        ),
        (FIXTURES_DIR / fixture_name).read_text(),
    )
    return extract_minimal_hplc(document)
