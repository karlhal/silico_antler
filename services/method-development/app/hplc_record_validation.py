from __future__ import annotations

from .hplc_extraction_schemas import RetrievalRecordDraft
from .retrieval_schemas import RecordValidationState, ValidationIssue


def validate_record_draft(record_draft: RetrievalRecordDraft) -> RecordValidationState:
    issues: list[ValidationIssue] = []

    issues.extend(_validate_flow_and_pressure(record_draft))
    issues.extend(_validate_ph_compatibility(record_draft))
    issues.extend(_validate_duplicate_retention_assignments(record_draft))
    issues.extend(_validate_entity_linkage_readiness(record_draft))
    issues.extend(_validate_generic_anchor_resolution(record_draft))

    if any(issue.severity == "error" for issue in issues):
        return RecordValidationState(
            status="invalid",
            retrieval_ready=False,
            issues=issues,
        )

    if issues or record_draft.unresolved_requirements:
        return RecordValidationState(
            status="needs_review",
            retrieval_ready=False,
            issues=issues,
        )

    return RecordValidationState(
        status="valid",
        retrieval_ready=True,
        issues=issues,
    )


def _validate_flow_and_pressure(
    record_draft: RetrievalRecordDraft,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    system = record_draft.chromatography_system
    method = record_draft.method_parameters
    flow_rate = method.flow_rate_ml_min
    column_id = system.column_inner_diameter_mm
    pressure_index = (flow_rate * system.column_length_mm) / (
        max(system.particle_size_um, 0.1) * max(column_id, 0.1)
    )

    if column_id <= 2.1 and flow_rate > 1.5:
        issues.append(
            ValidationIssue(
                code="flow_rate_high_for_narrow_column",
                severity="error",
                message="Flow rate is implausibly high for a narrow-bore analytical column.",
                field_path="method_parameters.flow_rate_ml_min",
            )
        )
    elif column_id <= 2.1 and flow_rate > 1.0:
        issues.append(
            ValidationIssue(
                code="flow_rate_warning_for_narrow_column",
                severity="warning",
                message="Flow rate is unusually high for a narrow-bore analytical column.",
                field_path="method_parameters.flow_rate_ml_min",
            )
        )

    if pressure_index > 220:
        issues.append(
            ValidationIssue(
                code="pressure_index_extreme",
                severity="error",
                message="Combined flow, particle size, and column geometry imply an extreme pressure risk.",
                field_path="chromatography_system",
            )
        )
    elif pressure_index > 140:
        issues.append(
            ValidationIssue(
                code="pressure_index_high",
                severity="warning",
                message="Combined flow, particle size, and column geometry imply a high pressure risk.",
                field_path="chromatography_system",
            )
        )

    return issues


def _validate_ph_compatibility(
    record_draft: RetrievalRecordDraft,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    system = record_draft.chromatography_system
    phase_a = record_draft.method_parameters.mobile_phase_a
    ph_estimate = phase_a.ph_estimate
    if ph_estimate is None:
        return issues

    chemistry = system.stationary_phase_chemistry.lower()
    if chemistry in {"c18", "c8", "phenyl"}:
        if ph_estimate < 1.5 or ph_estimate > 10.0:
            issues.append(
                ValidationIssue(
                    code="ph_outside_stationary_phase_range",
                    severity="error",
                    message="Mobile phase pH falls outside a simple compatibility range for the stationary phase.",
                    field_path="method_parameters.mobile_phase_a.ph_estimate",
                )
            )
        elif ph_estimate < 2.0 or ph_estimate > 8.5:
            issues.append(
                ValidationIssue(
                    code="ph_stationary_phase_warning",
                    severity="warning",
                    message="Mobile phase pH is near the edge of a simple compatibility range for the stationary phase.",
                    field_path="method_parameters.mobile_phase_a.ph_estimate",
                )
            )

    return issues


def _validate_duplicate_retention_assignments(
    record_draft: RetrievalRecordDraft,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    retention_by_identifier: dict[str, list[float]] = {}
    for observation in record_draft.selected_retention_time_observations:
        if observation.local_identifier is None:
            continue
        key = observation.local_identifier.lower()
        retention_by_identifier.setdefault(key, []).append(
            observation.observed_retention_time_min
        )

    for identifier, values in retention_by_identifier.items():
        if len(values) < 2:
            continue
        if max(values) - min(values) > 0.5:
            issues.append(
                ValidationIssue(
                    code="conflicting_retention_assignment",
                    severity="error",
                    message=(
                        f"Conflicting retention times were selected for `{identifier}`."
                    ),
                    field_path="selected_retention_time_observations",
                )
            )

    return issues


def _validate_entity_linkage_readiness(
    record_draft: RetrievalRecordDraft,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for draft in record_draft.molecular_entity_drafts:
        if not draft.selected_for_record_draft:
            continue
        if draft.ready_for_retrieval_entity:
            continue
        issues.append(
            ValidationIssue(
                code="molecular_entity_unresolved",
                severity="warning",
                message=(
                    f"Molecular entity `{draft.local_identifier}` still lacks resolved SMILES linkage."
                ),
                field_path="molecular_entity_drafts",
            )
        )
    return issues


def _validate_generic_anchor_resolution(
    record_draft: RetrievalRecordDraft,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for draft in record_draft.molecular_entity_drafts:
        if not draft.selected_for_record_draft:
            continue
        if draft.smiles_linkage_status != "placeholder_generated":
            continue
        issues.append(
            ValidationIssue(
                code="generic_anchor_unresolved",
                severity="warning",
                message=(
                    f"Generic anchored entity `{draft.local_identifier}` still needs a concrete identifier before retrieval use."
                ),
                field_path="molecular_entity_drafts",
            )
        )
    return issues
