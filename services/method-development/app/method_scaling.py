from __future__ import annotations

from .recommendation_schemas import RecommendedMethod, SystemSpecs
from .retrieval_schemas import ChromatographySystem, GradientPoint, MethodParameters

_DEFAULT_SOURCE_INJECTION_VOLUME_UL = 10.0


def scale_method_for_system(
    system_specs: SystemSpecs | None,
    source_system: ChromatographySystem | None,
    method_parameters: MethodParameters | None,
) -> RecommendedMethod:
    if (
        not system_specs
        or not source_system
        or not method_parameters
        or not method_parameters.flow_rate_ml_min
        or not system_specs.column_inner_diameter_mm
        or not system_specs.column_length_mm
    ):
        return RecommendedMethod(is_scaled=False)

    id_ratio = (
        system_specs.column_inner_diameter_mm / source_system.column_inner_diameter_mm
    )
    length_ratio = system_specs.column_length_mm / source_system.column_length_mm

    scaled_flow = round(method_parameters.flow_rate_ml_min * (id_ratio**2), 2)
    scaled_runtime = (
        round(method_parameters.run_time_min * length_ratio, 1)
        if method_parameters.run_time_min
        else None
    )
    scaled_gradient = [
        GradientPoint(
            time_min=round(point.time_min * length_ratio, 2),
            percent_b=point.percent_b,
        )
        for point in method_parameters.gradient_profile
    ]
    scaled_injection_volume = round(
        _DEFAULT_SOURCE_INJECTION_VOLUME_UL * (id_ratio**2) * length_ratio,
        1,
    )

    scaling_notes = [
        (
            f"Flow rate adjusted from {method_parameters.flow_rate_ml_min} to "
            f"{scaled_flow} mL/min based on column ID."
        ),
        f"Gradient times adjusted by factor of {length_ratio:.2f} based on column length.",
        (
            "Injection volume estimated from column volume scaling using a "
            f"default {_DEFAULT_SOURCE_INJECTION_VOLUME_UL:.1f} uL literature injection."
        ),
    ]
    if scaled_runtime is not None:
        scaling_notes.append(
            (
                f"Run time adjusted from {method_parameters.run_time_min} to "
                f"{scaled_runtime} min based on column length."
            )
        )

    scaling_warnings: list[str] = []
    if system_specs.particle_size_um and source_system.particle_size_um:
        if system_specs.particle_size_um < source_system.particle_size_um:
            scaling_warnings.append(
                (
                    f"Target particle size {system_specs.particle_size_um} um is smaller than "
                    f"the literature method's {source_system.particle_size_um} um particles; "
                    "backpressure may increase."
                )
            )

    if scaled_runtime is None and not scaled_gradient:
        scaling_warnings.append(
            "Source method did not include runtime or gradient details, so only flow rate and injection volume were scaled."
        )
    elif scaled_runtime is None:
        scaling_warnings.append(
            "Source method did not include a total runtime, so gradient times were scaled without a final runtime estimate."
        )

    return RecommendedMethod(
        is_scaled=True,
        flow_rate_ml_min=scaled_flow,
        injection_volume_ul=scaled_injection_volume,
        gradient_profile=scaled_gradient,
        run_time_min=scaled_runtime,
        scaling_notes=scaling_notes,
        scaling_warnings=scaling_warnings,
    )
