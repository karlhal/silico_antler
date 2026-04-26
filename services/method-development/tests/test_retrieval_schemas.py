from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval_schemas import RetrievalMethodRecord


def build_valid_record() -> dict:
    return {
        "record_id": "method-001",
        "source_document": {
            "source_document_id": "doi:10.1000/example",
            "source_type": "pdf",
            "title": "Example HPLC Method",
            "published_year": 2024,
        },
        "molecular_entities": [
            {
                "local_identifier": "Compound 4a",
                "smiles_string": "CCO",
                "display_name": "ethanol",
                "observed_retention_time_min": 3.42,
            }
        ],
        "chromatography_system": {
            "mode": "rp_lc",
            "column_manufacturer": "Waters",
            "stationary_phase_chemistry": "C18",
            "column_length_mm": 100.0,
            "column_inner_diameter_mm": 2.1,
            "particle_size_um": 1.7,
        },
        "method_parameters": {
            "mobile_phase_a": {
                "solvent": "water",
                "additive": "0.1% formic acid",
                "ph_estimate": 2.8,
            },
            "mobile_phase_b": {
                "solvent": "acetonitrile",
            },
            "flow_rate_ml_min": 0.4,
            "column_temperature_c": 40.0,
            "gradient_profile": [
                {"time_min": 0.0, "percent_b": 5.0},
                {"time_min": 10.0, "percent_b": 95.0},
            ],
        },
        "provenance": {
            "extraction_mode": "parsed_text",
            "source_pages": [5, 6],
            "extraction_confidence": 0.87,
            "evidence_snippets": [
                {
                    "page_number": 5,
                    "section_label": "Experimental",
                    "text": "RP-LC was performed on a C18 column with a 5-95% B gradient over 10 min.",
                }
            ],
        },
        "validation": {
            "status": "needs_review",
            "retrieval_ready": True,
            "issues": [
                {
                    "code": "missing_doi",
                    "severity": "warning",
                    "message": "DOI missing from source metadata.",
                }
            ],
        },
    }


def test_retrieval_method_record_accepts_valid_payload() -> None:
    record = RetrievalMethodRecord(**build_valid_record())

    assert record.record_id == "method-001"
    assert record.chromatography_system.mode == "rp_lc"
    assert record.method_parameters.gradient_profile[1].percent_b == 95.0
    assert record.provenance.source_pages == [5, 6]
    assert record.validation.retrieval_ready is True


def test_retrieval_method_record_rejects_empty_molecular_entities() -> None:
    payload = build_valid_record()
    payload["molecular_entities"] = []

    with pytest.raises(ValidationError):
        RetrievalMethodRecord(**payload)


def test_retrieval_method_record_rejects_invalid_column_bounds() -> None:
    payload = build_valid_record()
    payload["chromatography_system"]["column_inner_diameter_mm"] = 0.5

    with pytest.raises(ValidationError):
        RetrievalMethodRecord(**payload)


def test_method_parameters_require_non_decreasing_gradient_times() -> None:
    payload = build_valid_record()
    payload["method_parameters"]["gradient_profile"] = [
        {"time_min": 5.0, "percent_b": 10.0},
        {"time_min": 4.0, "percent_b": 20.0},
    ]

    with pytest.raises(ValidationError, match="non-decreasing"):
        RetrievalMethodRecord(**payload)


def test_method_parameters_require_two_gradient_points_when_present() -> None:
    payload = build_valid_record()
    payload["method_parameters"]["gradient_profile"] = [
        {"time_min": 0.0, "percent_b": 5.0}
    ]

    with pytest.raises(ValidationError, match="at least two points"):
        RetrievalMethodRecord(**payload)


def test_provenance_confidence_must_be_between_zero_and_one() -> None:
    payload = build_valid_record()
    payload["provenance"]["extraction_confidence"] = 1.5

    with pytest.raises(ValidationError):
        RetrievalMethodRecord(**payload)
