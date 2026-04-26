from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("pymilvus")

from app.milvus_retrieval_store import MilvusRetrievalStore
from app.retrieval_schemas import (
    ChromatographySystem,
    HplcMolecularEntity,
    MethodParameters,
    MobilePhase,
    RetrievalMethodRecord,
    RetrievalProvenance,
    RetrievalRecordReviewSummary,
    SourceDocumentMetadata,
)


def test_milvus_retrieval_store_can_rank_records_for_target_plus_impurity_queries(
    tmp_path,
) -> None:
    store = MilvusRetrievalStore(db_path=str(tmp_path / "mixture-test.db"))
    seeded_review = RetrievalRecordReviewSummary(
        record_state="seeded",
        validation_status="unvalidated",
        retrieval_ready=False,
    )

    store.upsert_record(
        _build_record(
            record_id="zzz-target-only",
            entities=[("ethanol", "CCO")],
        ),
        seeded_review,
    )
    store.upsert_record(
        _build_record(
            record_id="aaa-target-plus-impurity",
            entities=[("ethanol", "CCO"), ("acetone", "CC(=O)C")],
        ),
        seeded_review,
    )

    target_only_matches = store.search("CCO", limit=2)
    mixture_matches = store.search("CCO", impurity_smiles=["CC(=O)C"], limit=2)

    assert target_only_matches[0].record.record_id == "zzz-target-only"
    assert mixture_matches[0].record.record_id == "aaa-target-plus-impurity"
    assert len(mixture_matches[0].match_rationale.impurity_matches) == 1
    assert (
        mixture_matches[0]
        .match_rationale.impurity_matches[0]
        .matched_entity_local_identifier
        == "acetone"
    )
    assert "Mixture-aware score" in mixture_matches[0].match_rationale.summary


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
            evidence_snippets=[
                {
                    "section_label": "Seeded record",
                    "text": f"Synthetic seeded record for {record_id}.",
                }
            ],
        ),
    )
