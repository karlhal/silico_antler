from __future__ import annotations

import json
import os
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


class ReviewRecordNotFoundError(KeyError):
    pass


class ReviewRecordStatusError(ValueError):
    pass


DEFAULT_REVIEW_RECORDS_PATH = (
    Path(__file__).resolve().parents[3]
    / "tmp"
    / "method-development"
    / "review_records.json"
)
REVIEW_RECORDS_PATH_ENV = "SILICO_METHOD_DEVELOPMENT_REVIEW_RECORDS_PATH"


class InMemoryReviewRecordStore:
    def __init__(self, *, persistence_path: Path | None = None) -> None:
        self._records: dict[str, ReviewRecord] = {}
        self._next_index = 1
        self._persistence_path = persistence_path

    @classmethod
    def from_persistence_path(
        cls, persistence_path: Path | None = None
    ) -> InMemoryReviewRecordStore:
        store = cls(persistence_path=persistence_path)
        store._load()
        return store

    @classmethod
    def from_default_path(cls) -> InMemoryReviewRecordStore:
        raw_path = os.getenv(REVIEW_RECORDS_PATH_ENV)
        persistence_path = Path(raw_path) if raw_path else DEFAULT_REVIEW_RECORDS_PATH
        return cls.from_persistence_path(persistence_path)

    def create_from_extraction(
        self, extraction_snapshot: MinimalHplcExtractionResponse
    ) -> ReviewRecord:
        review_record_id = f"review-{self._next_index:04d}"
        self._next_index += 1
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
        self._records[review_record_id] = record
        self._persist()
        return record

    def list(self) -> list[ReviewRecordSummary]:
        return [
            ReviewRecordSummary(
                review_record_id=record.review_record_id,
                source_document_id=record.extraction_snapshot.source_document.source_document_id,
                status=record.status,
                validation=record.validation,
                provenance=record.provenance,
                corpus_promotion=record.corpus_promotion,
            )
            for record in sorted(
                self._records.values(), key=lambda item: item.review_record_id
            )
        ]

    def get(self, review_record_id: str) -> ReviewRecord:
        try:
            return self._records[review_record_id]
        except KeyError as exc:
            raise ReviewRecordNotFoundError(review_record_id) from exc

    def latest_for_source_document(
        self, source_document_id: str
    ) -> ReviewRecord | None:
        matching_records = [
            record
            for record in self._records.values()
            if record.extraction_snapshot.source_document.source_document_id
            == source_document_id
        ]
        if not matching_records:
            return None
        return max(matching_records, key=lambda record: record.review_record_id)

    def all_records(self) -> list[ReviewRecord]:
        return [self._records[key] for key in sorted(self._records.keys())]

    def update_status(
        self, review_record_id: str, payload: ReviewRecordStatusUpdate
    ) -> ReviewRecord:
        record = self.get(review_record_id)
        if (
            isinstance(payload, ReviewRecordApprovalUpdate)
            and payload.entity_resolutions
        ):
            record = self._apply_entity_resolutions(record, payload.entity_resolutions)
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

        updated_record = record.model_copy(
            update={
                "status": payload.status,
                "review_notes": payload.review_notes,
                "approved_record_snapshot": approved_record_snapshot,
                "corpus_promotion": corpus_promotion,
            }
        )
        self._records[review_record_id] = updated_record
        self._persist()
        return updated_record

    def update_promotion(
        self, review_record_id: str, *, promote_to_local_corpus: bool
    ) -> ReviewRecord:
        record = self.get(review_record_id)
        if not promote_to_local_corpus:
            updated_record = record.model_copy(
                update={"corpus_promotion": ReviewRecordCorpusPromotion()}
            )
            self._records[review_record_id] = updated_record
            self._persist()
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
        self._records[review_record_id] = updated_record
        self._persist()
        return updated_record

    def _load(self) -> None:
        if self._persistence_path is None or not self._persistence_path.exists():
            return
        next_index, records = _load_payload(self._persistence_path)
        self._next_index = next_index
        self._records = {record.review_record_id: record for record in records}

    def _persist(self) -> None:
        if self._persistence_path is None:
            return
        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "next_index": self._next_index,
            "records": [
                record.model_dump(mode="json") for record in self.all_records()
            ],
        }
        temp_path = self._persistence_path.with_suffix(
            f"{self._persistence_path.suffix}.tmp"
        )
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        temp_path.replace(self._persistence_path)

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


def _match_resolution(
    draft, resolution_map: dict[str, MolecularEntityResolutionInput]
) -> MolecularEntityResolutionInput | None:
    for key in [draft.local_identifier, *draft.aliases]:
        resolution = resolution_map.get(key.lower())
        if resolution is not None:
            return resolution
    return None


def _normalize_record_draft(record_draft):
    selected_drafts = [
        draft
        for draft in record_draft.molecular_entity_drafts
        if draft.selected_for_record_draft
    ]
    unresolved_requirements = [
        requirement
        for requirement in record_draft.unresolved_requirements
        if "molecular entity" not in requirement.lower()
        and "smiles" not in requirement.lower()
    ]
    if selected_drafts and not all(
        draft.ready_for_retrieval_entity and draft.smiles_string
        for draft in selected_drafts
    ):
        unresolved_requirements.append(
            "molecular entity drafts still require SMILES linkage before RetrievalMethodRecord assembly"
        )
    return record_draft.model_copy(
        update={"unresolved_requirements": unresolved_requirements}
    )


def _load_payload(file_path: Path) -> tuple[int, list[ReviewRecord]]:
    payload = json.loads(file_path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(
            "Review-record persistence file must contain an object payload"
        )

    next_index = payload.get("next_index", 1)
    raw_records = payload.get("records", [])
    if not isinstance(next_index, int) or next_index < 1:
        raise ValueError("Review-record persistence file has invalid next_index")
    if not isinstance(raw_records, list):
        raise ValueError("Review-record persistence file has invalid records payload")

    return next_index, [ReviewRecord(**item) for item in raw_records]
