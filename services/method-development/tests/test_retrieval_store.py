from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.chemistry import InvalidSmilesError
from app.retrieval_schemas import (
    ChromatographySystem,
    HplcMolecularEntity,
    MethodParameters,
    MobilePhase,
    RetrievalMethodRecord,
    RetrievalProvenance,
    SourceDocumentMetadata,
)
from app.retrieval_store import SeededRetrievalStore, load_seed_method_records


def test_load_seed_method_records_returns_valid_schema_records() -> None:
    records = load_seed_method_records()

    assert len(records) == 8
    assert records[0].validation.retrieval_ready is True
    assert all(record.source_document.source_type == "seeded" for record in records)


def test_seeded_retrieval_store_returns_exact_match_first() -> None:
    store = SeededRetrievalStore.from_seed_file()

    matches = store.search("CCO", limit=3)

    assert len(matches) == 3
    assert matches[0].record.record_id == "seed-ethanol-rp18"
    assert matches[0].matched_entity.local_identifier == "ethanol"
    assert matches[0].score == pytest.approx(1.0)
    assert matches[0].match_rationale.match_type == "exact"
    assert matches[0].match_rationale.matched_entity_display_name == "ethanol"
    assert matches[0].match_rationale.supporting_snippet is not None
    assert "Exact molecular match" in matches[0].match_rationale.summary


def test_seeded_retrieval_store_can_match_secondary_exact_record() -> None:
    store = SeededRetrievalStore.from_seed_file()

    matches = store.search("CC(C)O", limit=2)

    assert matches[0].record.record_id == "seed-isopropanol-rp18"
    assert matches[0].score == pytest.approx(1.0)
    assert matches[1].match_rationale.match_type == "similarity"


def test_seeded_retrieval_store_respects_min_score_filter() -> None:
    store = SeededRetrievalStore.from_seed_file()

    matches = store.search("CCO", limit=10, min_score=0.99)

    assert [match.record.record_id for match in matches] == ["seed-ethanol-rp18"]


def test_seeded_retrieval_store_can_rank_records_for_target_plus_impurity_queries() -> (
    None
):
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

    target_only_matches = store.search("CCO", limit=2)
    mixture_matches = store.search("CCO", impurity_smiles=["CC(=O)C"], limit=2)

    assert target_only_matches[0].record.record_id == "record-target-only"
    assert mixture_matches[0].record.record_id == "record-multi-analyte"
    assert mixture_matches[0].score > mixture_matches[1].score
    assert (
        mixture_matches[0].match_rationale.aggregate_score == mixture_matches[0].score
    )
    assert len(mixture_matches[0].match_rationale.impurity_matches) == 1
    assert (
        mixture_matches[0]
        .match_rationale.impurity_matches[0]
        .matched_entity_local_identifier
        == "acetone"
    )


def test_seeded_retrieval_store_uses_aggregate_score_for_min_score_filter() -> None:
    store = SeededRetrievalStore(
        records=[
            _build_record(
                record_id="record-target-only",
                entities=[("ethanol", "CCO")],
            )
        ]
    )

    matches = store.search("CCO", impurity_smiles=["CC(=O)C"], min_score=0.8)

    assert matches == []


def test_seeded_retrieval_store_returns_empty_list_when_no_records_exist() -> None:
    store = SeededRetrievalStore(records=[])

    assert store.search("CCO") == []


def test_seeded_retrieval_store_rejects_invalid_query_smiles() -> None:
    store = SeededRetrievalStore.from_seed_file()

    with pytest.raises(InvalidSmilesError):
        store.search("not-a-smiles")


def test_seeded_retrieval_store_validates_search_arguments() -> None:
    store = SeededRetrievalStore.from_seed_file()

    with pytest.raises(ValueError, match="at least 1"):
        store.search("CCO", limit=0)

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        store.search("CCO", min_score=1.5)


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
