from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from pymilvus import MilvusClient, DataType

from .chemistry import (
    DEFAULT_FINGERPRINT_NUM_BITS,
    NormalizedMolecule,
    normalize_molecule,
    tanimoto_similarity,
)
from .retrieval_schemas import (
    RetrievalContextualPriors,
    RetrievalImpurityMatch,
    RetrievalMatchRationale,
    RetrievalMethodRecord,
    RetrievalRecordReviewSummary,
)
from .retrieval_store import (
    RetrievalEntityMatch,
    RetrievalRecordMatch,
    _build_contextual_priors,
    _compute_aggregate_score,
    _compute_retrieval_score,
    _index_record,
)

MILVUS_DB_PATH = os.environ.get("MILVUS_DB_PATH", "silico_retrieval.db")
COLLECTION_NAME = "hplc_methods"


@dataclass(frozen=True)
class _MilvusImpurityMatch:
    query_canonical_smiles: str
    matched_entity: RetrievalEntityMatch


class MilvusRetrievalStore:
    def __init__(self, db_path: str = MILVUS_DB_PATH) -> None:
        self.client = MilvusClient(db_path)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.has_collection(COLLECTION_NAME):
            schema = self.client.create_schema(
                auto_id=False,
                enable_dynamic_field=True,
            )
            schema.add_field(field_name="pk", datatype=DataType.INT64, is_primary=True, auto_id=True)
            schema.add_field(field_name="record_id", datatype=DataType.VARCHAR, max_length=200)
            schema.add_field(field_name="local_identifier", datatype=DataType.VARCHAR, max_length=200)
            schema.add_field(field_name="fingerprint", datatype=DataType.BINARY_VECTOR, dim=DEFAULT_FINGERPRINT_NUM_BITS)
            
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                schema=schema,
            )

        indices = self.client.list_indexes(collection_name=COLLECTION_NAME)
        if "fingerprint" not in indices:
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="fingerprint",
                index_type="BIN_FLAT",
                metric_type="JACCARD",
            )
            self.client.create_index(
                collection_name=COLLECTION_NAME,
                index_params=index_params
            )
            self.client.load_collection(collection_name=COLLECTION_NAME)

    def search(
        self,
        query_smiles: str,
        *,
        impurity_smiles: list[str] | tuple[str, ...] | None = None,
        limit: int = 5,
        min_score: float = 0.0,
        matrix_hint: str | None = None,
        preferred_mode: str | None = None,
        require_mass_spectrometry: bool = False,
        apply_contextual_priors: bool = False,
    ) -> list[RetrievalRecordMatch]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0")

        normalized_query = normalize_molecule(query_smiles)
        normalized_impurities = tuple(
            normalize_molecule(smiles) for smiles in (impurity_smiles or [])
        )

        candidate_records = self._collect_candidate_records(
            normalized_query=normalized_query,
            normalized_impurities=normalized_impurities,
            limit=limit,
        )

        matches: list[RetrievalRecordMatch] = []
        for record, review_summary in candidate_records.values():
            target_match = self._best_entity_match(record, normalized_query)
            if target_match is None:
                continue

            impurity_matches = [
                _MilvusImpurityMatch(
                    query_canonical_smiles=impurity.canonical_smiles,
                    matched_entity=matched_entity,
                )
                for impurity in normalized_impurities
                if (
                    matched_entity := self._best_entity_match(record, impurity)
                )
                is not None
            ]
            aggregate_score = _compute_aggregate_score(
                target_match.score, impurity_matches
            )
            contextual_priors: RetrievalContextualPriors | None = (
                _build_contextual_priors(
                    _index_record(record, review_summary),
                    matrix_hint=matrix_hint,
                    preferred_mode=preferred_mode,
                    require_mass_spectrometry=require_mass_spectrometry,
                )
                if apply_contextual_priors
                else None
            )
            retrieval_score = (
                _compute_retrieval_score(aggregate_score, contextual_priors)
                if contextual_priors is not None
                else aggregate_score
            )
            if retrieval_score < min_score:
                continue

            matches.append(
                RetrievalRecordMatch(
                    record=record,
                    score=retrieval_score,
                    matched_entity=target_match,
                    match_rationale=self._build_rationale(
                        record=record,
                        matched_entity=target_match,
                        query_canonical_smiles=normalized_query.canonical_smiles,
                        impurity_matches=impurity_matches,
                        aggregate_score=aggregate_score,
                        retrieval_score=retrieval_score,
                        contextual_priors=contextual_priors,
                    ),
                    review_summary=review_summary,
                )
            )

        sorted_matches = sorted(
            matches,
            key=lambda match: (match.score, match.record.record_id),
            reverse=True,
        )
        return sorted_matches[:limit]

    def upsert_record(
        self,
        record: RetrievalMethodRecord,
        review_summary: RetrievalRecordReviewSummary,
    ) -> None:
        # Remove existing entries for this record
        self.remove_record(record.record_id)

        data = []
        for entity in record.molecular_entities:
            normalized = normalize_molecule(entity.smiles_string)
            data.append({
                "record_id": record.record_id,
                "local_identifier": entity.local_identifier,
                "fingerprint": self._fingerprint_to_bytes(normalized.fingerprint.bitstring),
                "record_json": record.model_dump_json(),
                "review_summary_json": review_summary.model_dump_json()
            })
        
        self.client.insert(collection_name=COLLECTION_NAME, data=data)

    def remove_record(self, record_id: str) -> None:
        self.client.delete(
            collection_name=COLLECTION_NAME,
            filter=f'record_id == "{record_id}"'
        )

    def _fingerprint_to_bytes(self, bitstring: str) -> bytes:
        # Milvus binary vector expects bytes. 
        # RDKit bitstring is '0101...'
        # We need to pack it.
        byte_arr = bytearray()
        for i in range(0, len(bitstring), 8):
            byte = bitstring[i:i+8]
            # Reverse bit order within byte if needed? 
            # Milvus expects the first bit to be the highest bit of the first byte.
            byte_arr.append(int(byte.ljust(8, '0'), 2))
        return bytes(byte_arr)

    def _search_entities(
        self, molecule: NormalizedMolecule, *, limit: int
    ) -> list[dict[str, Any]]:
        query_vector = self._fingerprint_to_bytes(molecule.fingerprint.bitstring)
        results = self.client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=limit,
            output_fields=[
                "record_id",
                "local_identifier",
                "record_json",
                "review_summary_json",
            ],
            search_params={"metric_type": "JACCARD", "params": {}},
        )
        if not results:
            return []
        return list(results[0])

    def _collect_candidate_records(
        self,
        *,
        normalized_query: NormalizedMolecule,
        normalized_impurities: tuple[NormalizedMolecule, ...],
        limit: int,
    ) -> dict[str, tuple[RetrievalMethodRecord, RetrievalRecordReviewSummary]]:
        search_limit = max(limit * max(len(normalized_impurities) + 1, 2) * 5, 25)
        candidate_records: dict[
            str, tuple[RetrievalMethodRecord, RetrievalRecordReviewSummary]
        ] = {}
        for molecule in (normalized_query, *normalized_impurities):
            for hit in self._search_entities(molecule, limit=search_limit):
                record_id = hit["entity"]["record_id"]
                if record_id in candidate_records:
                    continue
                candidate_records[record_id] = (
                    RetrievalMethodRecord(**json.loads(hit["entity"]["record_json"])),
                    RetrievalRecordReviewSummary(
                        **json.loads(hit["entity"]["review_summary_json"])
                    ),
                )
        return candidate_records

    def _best_entity_match(
        self, record: RetrievalMethodRecord, query: NormalizedMolecule
    ) -> RetrievalEntityMatch | None:
        best_match: RetrievalEntityMatch | None = None
        for entity in record.molecular_entities:
            normalized_entity = normalize_molecule(entity.smiles_string)
            score = tanimoto_similarity(
                query.fingerprint, normalized_entity.fingerprint
            )
            if best_match is None or score > best_match.score:
                best_match = RetrievalEntityMatch(
                    local_identifier=entity.local_identifier,
                    canonical_smiles=normalized_entity.canonical_smiles,
                    display_name=entity.display_name,
                    observed_retention_time_min=entity.observed_retention_time_min,
                    score=score,
                )
        return best_match

    def _build_rationale(
        self,
        *,
        record: RetrievalMethodRecord,
        matched_entity: RetrievalEntityMatch,
        query_canonical_smiles: str,
        impurity_matches: list[_MilvusImpurityMatch],
        aggregate_score: float,
        retrieval_score: float,
        contextual_priors: RetrievalContextualPriors | None,
    ) -> RetrievalMatchRationale:
        match_type = (
            "exact"
            if matched_entity.canonical_smiles == query_canonical_smiles
            else "similarity"
        )
        matched_name = matched_entity.display_name or matched_entity.local_identifier
        if impurity_matches:
            impurity_average = sum(
                match.matched_entity.score for match in impurity_matches
            ) / len(impurity_matches)
            chemistry_summary = (
                f"Mixture-aware score {aggregate_score:.2f}: target '{matched_name}' "
                f"contributes {matched_entity.score:.2f} and impurities average "
                f"{impurity_average:.2f}."
            )
        else:
            chemistry_summary = (
                f"Exact molecular match to '{matched_name}'."
                if match_type == "exact"
                else f"Top similarity match to '{matched_name}' with score {matched_entity.score:.2f}."
            )
        summary = chemistry_summary
        if contextual_priors is not None:
            boosts: list[str] = []
            if contextual_priors.matrix_compatibility >= 0.75:
                boosts.append("matrix-compatible evidence")
            if contextual_priors.detector_compatibility >= 0.75:
                boosts.append("detector-compatible evidence")
            if contextual_priors.method_family_compatibility >= 0.75:
                boosts.append("method-family compatibility")
            if contextual_priors.review_backed_prior >= 0.75:
                boosts.append("review-backed prior")
            if contextual_priors.retrieval_ready_prior >= 0.75:
                boosts.append("retrieval-ready prior")
            boost_suffix = f" Context priors: {', '.join(boosts[:3])}." if boosts else ""
            summary = f"Retrieval score {retrieval_score:.2f}. {chemistry_summary}{boost_suffix}"
        supporting_snippet = next(iter(record.provenance.evidence_snippets), None)
        return RetrievalMatchRationale(
            match_type=match_type,
            matched_entity_local_identifier=matched_entity.local_identifier,
            matched_entity_display_name=matched_entity.display_name,
            matched_entity_observed_retention_time_min=matched_entity.observed_retention_time_min,
            target_score=matched_entity.score,
            impurity_matches=[
                RetrievalImpurityMatch(
                    query_canonical_smiles=match.query_canonical_smiles,
                    matched_entity_local_identifier=match.matched_entity.local_identifier,
                    matched_entity_display_name=match.matched_entity.display_name,
                    score=match.matched_entity.score,
                )
                for match in impurity_matches
            ],
            aggregate_score=aggregate_score,
            retrieval_score=retrieval_score,
            contextual_priors=contextual_priors,
            supporting_snippet=supporting_snippet,
            summary=summary[:400],
        )
