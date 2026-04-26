from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .hplc_extraction_schemas import MinimalHplcExtractionResponse
from .hplc_record_validation import validate_record_draft
from .review_record_materialization import (
    ReviewRecordMaterializationError,
    build_approved_record_snapshot,
    build_corpus_promotion,
)
from .retrieval_schemas import RecordValidationState
from .review_record_schemas import (
    MolecularEntityResolutionInput,
    ReviewRecord,
    ReviewRecordApprovalUpdate,
    ReviewRecordCorpusPromotion,
    ReviewRecordStatusUpdate,
    ReviewRecordSummary,
)
from .review_record_store import (
    ReviewRecordNotFoundError,
    ReviewRecordStatusError,
    _match_resolution,
    _normalize_record_draft,
)

DEFAULT_REVIEW_RECORDS_PATH = (
    Path(__file__).resolve().parents[3]
    / "tmp"
    / "method-development"
    / "review_records.db"
)
REVIEW_RECORDS_PATH_ENV = "SILICO_METHOD_DEVELOPMENT_REVIEW_RECORDS_PATH"


class SqliteReviewRecordStore:
    def __init__(self, *, persistence_path: Path | None = None) -> None:
        self._persistence_path = persistence_path
        db_path = str(persistence_path) if persistence_path else ":memory:"
        if persistence_path and not persistence_path.parent.exists():
            persistence_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    @classmethod
    def from_persistence_path(
        cls, persistence_path: Path | None = None
    ) -> SqliteReviewRecordStore:
        return cls(persistence_path=persistence_path)

    @classmethod
    def from_default_path(cls) -> SqliteReviewRecordStore:
        raw_path = os.getenv(REVIEW_RECORDS_PATH_ENV)
        persistence_path = Path(raw_path) if raw_path else DEFAULT_REVIEW_RECORDS_PATH
        return cls(persistence_path=persistence_path)

    def _init_db(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS review_records (
                    review_record_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    storage_payload TEXT NOT NULL,
                    updated_at DATETIME NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_record_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_record_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    actor TEXT,
                    rationale TEXT,
                    payload_summary TEXT,
                    FOREIGN KEY(review_record_id) REFERENCES review_records(review_record_id)
                );
                """
            )

    def _get_next_index(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM review_records")
        count = cur.fetchone()[0]
        return count + 1

    def create_from_extraction(
        self, extraction_snapshot: MinimalHplcExtractionResponse
    ) -> ReviewRecord:
        with self._conn:
            next_index = self._get_next_index()
            review_record_id = f"review-{next_index:04d}"
            
            record = ReviewRecord(
                review_record_id=review_record_id,
                provenance=extraction_snapshot.provenance,
                validation=(
                    extraction_snapshot.record_draft.validation
                    if extraction_snapshot.record_draft is not None
                    else RecordValidationState(status="needs_review", retrieval_ready=False)
                ),
                record_draft=extraction_snapshot.record_draft,
                extraction_snapshot=extraction_snapshot,
            )
            
            now = datetime.now(timezone.utc).isoformat()
            payload_json = json.dumps(record.model_dump(mode="json"))
            self._conn.execute(
                """
                INSERT INTO review_records (review_record_id, status, provenance, storage_payload, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (review_record_id, record.status, json.dumps(record.provenance.model_dump(mode="json")), payload_json, now)
            )
            
            self._conn.execute(
                """
                INSERT INTO review_record_events (review_record_id, event_type, timestamp, rationale, payload_summary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (review_record_id, "review_created", now, None, "Extraction snapshot ingested")
            )
        return record

    def list(self) -> list[ReviewRecordSummary]:
        cur = self._conn.execute("SELECT storage_payload FROM review_records ORDER BY review_record_id")
        records = [ReviewRecord(**json.loads(row["storage_payload"])) for row in cur]
        return [
            ReviewRecordSummary(
                review_record_id=record.review_record_id,
                source_document_id=record.extraction_snapshot.source_document.source_document_id,
                status=record.status,
                validation=record.validation,
                provenance=record.provenance,
                corpus_promotion=record.corpus_promotion,
            )
            for record in records
        ]

    def get(self, review_record_id: str) -> ReviewRecord:
        cur = self._conn.execute("SELECT storage_payload FROM review_records WHERE review_record_id = ?", (review_record_id,))
        row = cur.fetchone()
        if not row:
            raise ReviewRecordNotFoundError(review_record_id)
        return ReviewRecord(**json.loads(row["storage_payload"]))

    def latest_for_source_document(
        self, source_document_id: str
    ) -> ReviewRecord | None:
        cur = self._conn.execute(
            "SELECT storage_payload FROM review_records WHERE json_extract(storage_payload, '$.extraction_snapshot.source_document.source_document_id') = ? ORDER BY review_record_id DESC LIMIT 1",
            (source_document_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return ReviewRecord(**json.loads(row["storage_payload"]))

    def all_records(self) -> list[ReviewRecord]:
        cur = self._conn.execute("SELECT storage_payload FROM review_records ORDER BY review_record_id")
        return [ReviewRecord(**json.loads(row["storage_payload"])) for row in cur]

    def update_status(
        self, review_record_id: str, payload: ReviewRecordStatusUpdate
    ) -> ReviewRecord:
        with self._conn:
            record = self.get(review_record_id)
            
            events_to_log = []
            now = datetime.now(timezone.utc).isoformat()
            
            if (
                isinstance(payload, ReviewRecordApprovalUpdate)
                and payload.entity_resolutions
            ):
                record = self._apply_entity_resolutions(record, payload.entity_resolutions)
                events_to_log.append(("entity_resolutions_applied", payload.review_notes, f"Applied {len(payload.entity_resolutions)} entity resolutions"))

            if payload.status == "approved" and not record.validation.retrieval_ready:
                raise ReviewRecordStatusError(
                    "Only retrieval-ready records can be approved"
                )

            approved_record_snapshot = None
            corpus_promotion = ReviewRecordCorpusPromotion()
            if payload.status == "approved":
                candidate_record = record.model_copy(
                    update={
                        "status": payload.status,
                        "review_notes": payload.review_notes,
                    }
                )
                try:
                    approved_record_snapshot = build_approved_record_snapshot(
                        candidate_record
                    )
                except ReviewRecordMaterializationError as exc:
                    raise ReviewRecordStatusError(str(exc)) from exc
                promote_to_local_corpus = (
                    payload.promote_to_local_corpus
                    if isinstance(payload, ReviewRecordApprovalUpdate)
                    else False
                )
                corpus_promotion = build_corpus_promotion(
                    candidate_record,
                    promote_to_local_corpus=promote_to_local_corpus,
                )
                events_to_log.append(("review_approved", payload.review_notes, "Review approved"))
                if promote_to_local_corpus:
                    events_to_log.append(("promotion_enabled", payload.review_notes, "Promotion to local corpus enabled"))
            elif payload.status == "rejected":
                events_to_log.append(("review_rejected", payload.review_notes, "Review rejected"))

            updated_record = record.model_copy(
                update={
                    "status": payload.status,
                    "review_notes": payload.review_notes,
                    "approved_record_snapshot": approved_record_snapshot,
                    "corpus_promotion": corpus_promotion,
                }
            )
            
            payload_json = json.dumps(updated_record.model_dump(mode="json"))
            self._conn.execute(
                "UPDATE review_records SET status = ?, storage_payload = ?, updated_at = ? WHERE review_record_id = ?",
                (updated_record.status, payload_json, now, review_record_id)
            )
            
            for event_type, rationale, summary in events_to_log:
                self._conn.execute(
                    "INSERT INTO review_record_events (review_record_id, event_type, timestamp, rationale, payload_summary) VALUES (?, ?, ?, ?, ?)",
                    (review_record_id, event_type, now, rationale, summary)
                )

        return updated_record

    def update_promotion(
        self, review_record_id: str, *, promote_to_local_corpus: bool
    ) -> ReviewRecord:
        with self._conn:
            record = self.get(review_record_id)
            now = datetime.now(timezone.utc).isoformat()
            
            if not promote_to_local_corpus:
                updated_record = record.model_copy(
                    update={"corpus_promotion": ReviewRecordCorpusPromotion()}
                )
                payload_json = json.dumps(updated_record.model_dump(mode="json"))
                self._conn.execute(
                    "UPDATE review_records SET storage_payload = ?, updated_at = ? WHERE review_record_id = ?",
                    (payload_json, now, review_record_id)
                )
                self._conn.execute(
                    "INSERT INTO review_record_events (review_record_id, event_type, timestamp, rationale, payload_summary) VALUES (?, ?, ?, ?, ?)",
                    (review_record_id, "promotion_removed", now, None, "Promotion removed")
                )
                return updated_record

            if record.status != "approved":
                raise ReviewRecordStatusError(
                    "Only approved review records can be promoted into the local corpus"
                )

            try:
                approved_record_snapshot = build_approved_record_snapshot(record)
            except ReviewRecordMaterializationError as exc:
                raise ReviewRecordStatusError(str(exc)) from exc

            updated_record = record.model_copy(
                update={
                    "approved_record_snapshot": approved_record_snapshot,
                    "corpus_promotion": build_corpus_promotion(
                        record, promote_to_local_corpus=True
                    ),
                }
            )
            
            payload_json = json.dumps(updated_record.model_dump(mode="json"))
            self._conn.execute(
                "UPDATE review_records SET storage_payload = ?, updated_at = ? WHERE review_record_id = ?",
                (payload_json, now, review_record_id)
            )
            self._conn.execute(
                "INSERT INTO review_record_events (review_record_id, event_type, timestamp, rationale, payload_summary) VALUES (?, ?, ?, ?, ?)",
                (review_record_id, "promotion_enabled", now, None, "Promotion enabled")
            )
            
        return updated_record

    def _apply_entity_resolutions(
        self,
        record: ReviewRecord,
        entity_resolutions: list[MolecularEntityResolutionInput],
    ) -> ReviewRecord:
        record_draft = record.record_draft
        if record_draft is None:
            raise ReviewRecordStatusError(
                "Review record has no record_draft to resolve molecular entities"
            )

        resolution_map = {
            resolution.local_identifier.lower(): resolution
            for resolution in entity_resolutions
        }

        updated_drafts = []
        for draft in record_draft.molecular_entity_drafts:
            resolution = _match_resolution(draft, resolution_map)
            if resolution is None:
                updated_drafts.append(draft)
                continue
            updated_drafts.append(
                draft.model_copy(
                    update={
                        "smiles_string": resolution.smiles_string,
                        "display_name": resolution.display_name or draft.display_name,
                        "ready_for_retrieval_entity": True,
                    }
                )
            )

        updated_record_draft = record_draft.model_copy(
            update={"molecular_entity_drafts": updated_drafts}
        )
        normalized_record_draft = _normalize_record_draft(updated_record_draft)
        validation = validate_record_draft(normalized_record_draft)
        normalized_record_draft = normalized_record_draft.model_copy(
            update={
                "validation": validation,
                "ready_for_record_assembly": validation.retrieval_ready,
            }
        )
        updated_extraction_snapshot = record.extraction_snapshot.model_copy(
            update={
                "record_draft": normalized_record_draft,
                "molecular_entity_drafts": normalized_record_draft.molecular_entity_drafts,
                "retrieval_record_ready": validation.retrieval_ready,
            }
        )
        return record.model_copy(
            update={
                "record_draft": normalized_record_draft,
                "validation": validation,
                "extraction_snapshot": updated_extraction_snapshot,
            }
        )
