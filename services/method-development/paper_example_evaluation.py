from __future__ import annotations

import json
from pathlib import Path
from typing import cast
import unicodedata

from app.hplc_extraction_schemas import MinimalHplcExtractionResponse
from app.hplc_text_extraction import extract_minimal_hplc
from app.retrieval_schemas import DocumentKind, MobilePhase, SourceDocumentMetadata
from app.source_document_ingestion import ingest_html_document, ingest_pdf_document


SERVICE_ROOT = Path(__file__).resolve().parent
PAPER_EXAMPLE_ROOT = SERVICE_ROOT / "tests" / "paper_example"
FIXTURE_ROOT = PAPER_EXAMPLE_ROOT / "expected"

STRING_TOLERANCE_FIELDS = {
    "chromatography_system.mode",
    "chromatography_system.column_name",
    "method_parameters.mobile_phase_a",
    "method_parameters.mobile_phase_b",
}
FLOAT_TOLERANCE_FIELDS = {
    "chromatography_system.column_length_mm": 0.1,
    "chromatography_system.column_inner_diameter_mm": 0.05,
    "chromatography_system.particle_size_um": 0.05,
    "method_parameters.flow_rate_ml_min": 0.05,
    "method_parameters.column_temperature_c": 0.5,
    "method_parameters.run_time_min": 0.5,
}
UNSUPPORTED_FIELDS = {
    "chromatography_system.guard_column",
    "chromatography_system.detector",
    "chromatography_system.ionization",
    "chromatography_system.acquisition_mode",
    "method_parameters.injection_volume_ul",
    "method_parameters.equilibration_time_min",
    "method_parameters.wavelength_nm",
    "method_parameters.sample_reconstitution",
    "method_parameters.selected_additive_condition",
    "method_parameters.sample_prep_notes",
}


def load_gold_fixtures() -> list[dict]:
    fixtures: list[dict] = []
    for path in sorted(FIXTURE_ROOT.glob("*.json")):
        payload = json.loads(path.read_text())
        if "paper_id" not in payload or "source_files" not in payload:
            continue
        fixtures.append(payload)
    return fixtures


def run_paper_example_evaluation() -> dict:
    fixtures = load_gold_fixtures()
    reports = []
    for fixture in fixtures:
        for source_kind in ("pdf", "html"):
            extraction = _extract_from_fixture_source(fixture, source_kind)
            reports.append(
                evaluate_extraction_against_fixture(
                    fixture=fixture,
                    source_kind=source_kind,
                    extraction=extraction,
                )
            )

    aggregate_supported = sum(
        report["summary"]["supported_total"] for report in reports
    )
    aggregate_matched = sum(report["summary"]["matched"] for report in reports)
    aggregate_missing = sum(report["summary"]["missing"] for report in reports)
    aggregate_mismatched = sum(report["summary"]["mismatched"] for report in reports)

    return {
        "fixtures_evaluated": len(fixtures),
        "reports": reports,
        "aggregate": {
            "supported_total": aggregate_supported,
            "matched": aggregate_matched,
            "missing": aggregate_missing,
            "mismatched": aggregate_mismatched,
            "match_ratio": round(aggregate_matched / aggregate_supported, 3)
            if aggregate_supported
            else None,
        },
    }


def evaluate_extraction_against_fixture(
    *, fixture: dict, source_kind: str, extraction: MinimalHplcExtractionResponse
) -> dict:
    fixture = _fixture_for_source_kind(fixture, source_kind)
    checks: list[dict] = []

    _add_scalar_check(
        checks,
        "chromatography_system.mode",
        fixture["expected"]["chromatography_system"].get("mode"),
        extraction.chromatography_system.mode
        if extraction.chromatography_system
        else None,
    )
    _add_scalar_check(
        checks,
        "chromatography_system.column_name",
        fixture["expected"]["chromatography_system"].get("column_name"),
        extraction.chromatography_system.column_name
        if extraction.chromatography_system
        else None,
    )
    _add_scalar_check(
        checks,
        "chromatography_system.column_length_mm",
        fixture["expected"]["chromatography_system"].get("column_length_mm"),
        extraction.chromatography_system.column_length_mm
        if extraction.chromatography_system
        else None,
    )
    _add_scalar_check(
        checks,
        "chromatography_system.column_inner_diameter_mm",
        fixture["expected"]["chromatography_system"].get("column_inner_diameter_mm"),
        extraction.chromatography_system.column_inner_diameter_mm
        if extraction.chromatography_system
        else None,
    )
    _add_scalar_check(
        checks,
        "chromatography_system.particle_size_um",
        fixture["expected"]["chromatography_system"].get("particle_size_um"),
        extraction.chromatography_system.particle_size_um
        if extraction.chromatography_system
        else None,
    )

    for unsupported_path in (
        "chromatography_system.guard_column",
        "chromatography_system.detector",
        "chromatography_system.ionization",
        "chromatography_system.acquisition_mode",
    ):
        _add_scalar_check(
            checks,
            unsupported_path,
            _nested_get(fixture["expected"], unsupported_path),
            None,
        )

    _add_scalar_check(
        checks,
        "method_parameters.mobile_phase_a",
        fixture["expected"]["method_parameters"].get("mobile_phase_a"),
        _format_mobile_phase(
            extraction.method_parameters.mobile_phase_a
            if extraction.method_parameters
            else None
        ),
    )
    _add_scalar_check(
        checks,
        "method_parameters.mobile_phase_b",
        fixture["expected"]["method_parameters"].get("mobile_phase_b"),
        _format_mobile_phase(
            extraction.method_parameters.mobile_phase_b
            if extraction.method_parameters
            else None
        ),
    )
    _add_scalar_check(
        checks,
        "method_parameters.flow_rate_ml_min",
        fixture["expected"]["method_parameters"].get("flow_rate_ml_min"),
        extraction.method_parameters.flow_rate_ml_min
        if extraction.method_parameters
        else None,
    )
    _add_scalar_check(
        checks,
        "method_parameters.column_temperature_c",
        fixture["expected"]["method_parameters"].get("column_temperature_c"),
        extraction.method_parameters.column_temperature_c
        if extraction.method_parameters
        else None,
    )
    _add_scalar_check(
        checks,
        "method_parameters.run_time_min",
        fixture["expected"]["method_parameters"].get("run_time_min"),
        extraction.method_parameters.run_time_min
        if extraction.method_parameters
        else None,
    )

    for unsupported_path in (
        "method_parameters.injection_volume_ul",
        "method_parameters.equilibration_time_min",
        "method_parameters.wavelength_nm",
        "method_parameters.sample_reconstitution",
        "method_parameters.selected_additive_condition",
        "method_parameters.sample_prep_notes",
    ):
        _add_scalar_check(
            checks,
            unsupported_path,
            _nested_get(fixture["expected"], unsupported_path),
            None,
        )

    checks.append(
        _evaluate_gradient(
            fixture["expected"]["method_parameters"].get("gradient_program", []),
            extraction,
        )
    )

    for entity in fixture["expected"].get("retention_entities", []):
        checks.append(_evaluate_retention_entity(entity, extraction))

    supported_checks = [
        check
        for check in checks
        if check["status"] in {"matched", "missing", "mismatched"}
    ]
    matched = sum(check["status"] == "matched" for check in supported_checks)
    missing = sum(check["status"] == "missing" for check in supported_checks)
    mismatched = sum(check["status"] == "mismatched" for check in supported_checks)

    return {
        "paper_id": fixture["paper_id"],
        "title": fixture["title"],
        "source_kind": source_kind,
        "source_file": fixture["source_files"][source_kind],
        "summary": {
            "supported_total": len(supported_checks),
            "matched": matched,
            "missing": missing,
            "mismatched": mismatched,
            "unsupported": sum(check["status"] == "unsupported" for check in checks),
            "match_ratio": round(matched / len(supported_checks), 3)
            if supported_checks
            else None,
        },
        "checks": checks,
    }


def _fixture_for_source_kind(fixture: dict, source_kind: str) -> dict:
    override = fixture.get("source_overrides", {}).get(source_kind)
    if override is None:
        return fixture

    merged = json.loads(json.dumps(fixture))
    override_expected = override.get("expected", {})
    for key, value in override_expected.items():
        if value == {}:
            merged["expected"][key] = {}
        elif isinstance(value, dict) and isinstance(merged["expected"].get(key), dict):
            merged["expected"][key] = {**merged["expected"][key], **value}
        else:
            merged["expected"][key] = value
    return merged


def _extract_from_fixture_source(
    fixture: dict, source_kind: str
) -> MinimalHplcExtractionResponse:
    source_path = _resolve_source_path(fixture["source_files"][source_kind])
    metadata = SourceDocumentMetadata(
        source_document_id=f"{fixture['paper_id']}-{source_kind}",
        source_type=cast(DocumentKind, source_kind),
        title=fixture["title"],
        file_name=source_path.name,
    )
    if source_kind == "pdf":
        document = ingest_pdf_document(metadata, source_path.read_bytes())
    elif source_kind == "html":
        document = ingest_html_document(metadata, source_path.read_text())
    else:
        raise ValueError(f"Unsupported source kind: {source_kind}")
    return extract_minimal_hplc(document)


def _resolve_source_path(configured_name: str) -> Path:
    direct_path = PAPER_EXAMPLE_ROOT / configured_name
    if direct_path.exists():
        return direct_path

    target_name = _normalize_text(configured_name)
    for candidate in PAPER_EXAMPLE_ROOT.iterdir():
        if candidate.is_file() and _normalize_text(candidate.name) == target_name:
            return candidate

    raise FileNotFoundError(f"Could not resolve source fixture path: {configured_name}")


def _evaluate_gradient(
    expected_gradient: list[dict], extraction: MinimalHplcExtractionResponse
) -> dict:
    actual_gradient = (
        [
            {"time_min": point.time_min, "percent_b": point.percent_b}
            for point in extraction.method_parameters.gradient_profile
        ]
        if extraction.method_parameters
        else []
    )
    if not expected_gradient:
        return {
            "field_path": "method_parameters.gradient_program",
            "status": "unsupported",
            "expected": expected_gradient,
            "actual": actual_gradient,
            "note": "No expected gradient defined",
        }
    if not actual_gradient:
        return {
            "field_path": "method_parameters.gradient_program",
            "status": "missing",
            "expected": expected_gradient,
            "actual": actual_gradient,
            "note": "No gradient profile in extraction output",
        }

    normalized_expected = [
        {
            "time_min": round(point["time_min"], 2),
            "percent_b": round(point["b_pct"], 2),
        }
        for point in expected_gradient
        if point.get("b_pct") is not None
    ]
    normalized_actual = [
        {
            "time_min": round(point["time_min"], 2),
            "percent_b": round(point["percent_b"], 2),
        }
        for point in actual_gradient
    ]

    status = "matched" if normalized_expected == normalized_actual else "mismatched"
    return {
        "field_path": "method_parameters.gradient_program",
        "status": status,
        "expected": normalized_expected,
        "actual": normalized_actual,
        "note": None
        if status == "matched"
        else "Gradient profile differs from gold fixture",
    }


def _evaluate_retention_entity(
    expected_entity: dict, extraction: MinimalHplcExtractionResponse
) -> dict:
    expected_name = str(expected_entity.get("name", ""))
    expected_rt = float(expected_entity.get("retention_time_min", 0.0))
    observations = extraction.retention_time_observations
    best_match = None
    for observation in observations:
        actual_name = observation.local_identifier
        if actual_name is None:
            continue
        same_name = _normalized_label_match(actual_name, expected_name)
        same_rt = abs(observation.observed_retention_time_min - expected_rt) <= 0.2
        if same_name and same_rt:
            best_match = observation
            break
    if best_match is None:
        rt_only_matches = [
            observation
            for observation in observations
            if abs(observation.observed_retention_time_min - expected_rt) <= 0.2
        ]
        if len(rt_only_matches) == 1:
            best_match = rt_only_matches[0]
    if best_match is not None:
        return {
            "field_path": f"retention_entities.{expected_name}",
            "status": "matched",
            "expected": expected_entity,
            "actual": {
                "name": best_match.local_identifier,
                "retention_time_min": best_match.observed_retention_time_min,
            },
            "note": None,
        }

    if not observations:
        status = "missing"
        note = "No retention observations in extraction output"
    else:
        status = "mismatched"
        note = "Retention observations present but expected entity was not matched"
    return {
        "field_path": f"retention_entities.{expected_name}",
        "status": status,
        "expected": expected_entity,
        "actual": [
            {
                "name": observation.local_identifier,
                "retention_time_min": observation.observed_retention_time_min,
            }
            for observation in observations[:10]
        ],
        "note": note,
    }


def _add_scalar_check(
    checks: list[dict], field_path: str, expected_value: object, actual_value: object
) -> None:
    if expected_value is None:
        return
    if field_path in UNSUPPORTED_FIELDS:
        checks.append(
            {
                "field_path": field_path,
                "status": "unsupported",
                "expected": expected_value,
                "actual": actual_value,
                "note": "Gold fixture field is not yet represented in extraction output schema",
            }
        )
        return

    if field_path in STRING_TOLERANCE_FIELDS:
        if actual_value is None:
            status = "missing"
        else:
            normalized_expected = _normalize_text(str(expected_value))
            normalized_actual = _normalize_text(str(actual_value))
            status = (
                "matched"
                if normalized_expected == normalized_actual
                or normalized_expected in normalized_actual
                or normalized_actual in normalized_expected
                else "mismatched"
            )
    elif field_path in FLOAT_TOLERANCE_FIELDS:
        if actual_value is None:
            status = "missing"
        else:
            tolerance = FLOAT_TOLERANCE_FIELDS[field_path]
            status = (
                "matched"
                if abs(
                    float(cast("float", expected_value))
                    - float(cast("float", actual_value))
                )
                <= tolerance
                else "mismatched"
            )
    else:
        status = "matched" if expected_value == actual_value else "mismatched"

    checks.append(
        {
            "field_path": field_path,
            "status": status,
            "expected": expected_value,
            "actual": actual_value,
            "note": None if status == "matched" else f"Mismatch for {field_path}",
        }
    )


def _format_mobile_phase(phase: MobilePhase | None) -> str | None:
    if phase is None:
        return None
    parts = [phase.solvent]
    if phase.additive:
        parts.append(phase.additive)
    if phase.ph_estimate is not None:
        parts.append(f"pH {phase.ph_estimate}")
    return ", ".join(parts)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    for old, new in {
        "α": "alpha",
        "β": "beta",
        "γ": "gamma",
        "δ": "delta",
        "µ": "u",
        "μ": "u",
    }.items():
        normalized = normalized.replace(old, new)
    for dash in ("–", "—", "−"):
        normalized = normalized.replace(dash, "-")
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    for old, new in {
        "methanol": "meoh",
        "acetonitrile": "acn",
        "methyl tert butyl ether": "mtbe",
        "methyl tert-butyl ether": "mtbe",
        "of acetic acid": "acetic acid",
        "reversed phase column": "",
        "column used was": "",
        "separation was performed on": "",
        "with": "",
    }.items():
        normalized = normalized.replace(old, new)
    for old, new in {
        "%": " percent ",
        "->": " to ",
        "-": " ",
        "/": " ",
        "_": " ",
        "(": " ",
        ")": " ",
        ",": " ",
        ":": " ",
        ";": " ",
    }.items():
        normalized = normalized.replace(old, new)
    return " ".join(normalized.split())


def _normalized_label_match(actual: str, expected: str) -> bool:
    normalized_actual = _normalize_text(actual)
    normalized_expected = _normalize_text(expected)
    if normalized_actual == normalized_expected:
        return True
    if normalized_actual.replace(" ", "") == normalized_expected.replace(" ", ""):
        return True
    if normalized_actual.endswith(normalized_expected):
        return True
    if normalized_expected.endswith(normalized_actual):
        return True
    return False


def _nested_get(payload: dict, dotted_path: str) -> object:
    current: object = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
