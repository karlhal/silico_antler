from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List

TEMP_MIN = 25.0
TEMP_MAX = 80.0
MEOH_MIN = 0.0
MEOH_MAX = 100.0
RETENTION_CAP_S = 300.0
PEAK_SIGMA = 0.75


@dataclass(frozen=True)
class MoleculeProfile:
    label: str
    smiles: str
    base_rt_s: float
    temperature_slope: float
    meoh_slope: float
    cross_slope: float
    curvature: float


@dataclass(frozen=True)
class Preset:
    preset_id: str
    name: str
    description: str
    molecules: tuple[MoleculeProfile, ...]
    focus_temp_c: float
    focus_meoh_pct: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _retention_time_seconds(molecule: MoleculeProfile, preset: Preset, temperature_c: float, meoh_pct: float) -> float:
    temp_delta = temperature_c - preset.focus_temp_c
    meoh_delta = meoh_pct - preset.focus_meoh_pct
    distance_term = (temp_delta / 20.0) ** 2 + (meoh_delta / 35.0) ** 2

    rt = (
        molecule.base_rt_s
        + molecule.temperature_slope * temp_delta
        + molecule.meoh_slope * meoh_delta
        + molecule.cross_slope * temp_delta * meoh_delta / 100.0
        + molecule.curvature * distance_term
    )
    return round(_clamp(rt, 10.0, 360.0), 3)


def _gaussian(x: float, mu: float, sigma: float) -> float:
    return (1.0 / (sigma * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def _objective(retention_times: List[float]) -> Dict[str, float]:
    sorted_rt = sorted(retention_times)
    min_sep = min((b - a for a, b in zip(sorted_rt, sorted_rt[1:])), default=0.0)
    max_rt = max(sorted_rt, default=0.0)

    optimization_metric = min_sep if max_rt <= RETENTION_CAP_S else -1.0
    quality_score = max(optimization_metric, 0.0)

    return {
        "min_separation_s": round(min_sep, 3),
        "max_retention_s": round(max_rt, 3),
        "critical_resolution": round(min_sep / (4.0 * PEAK_SIGMA), 3),
        "optimization_metric_s": round(optimization_metric, 3),
        # Deprecated alias kept for backwards compatibility with older clients.
        "quality_score": round(quality_score, 3),
    }


PRESETS: Dict[str, Preset] = {
    "deck_scenario": Preset(
        preset_id="deck_scenario",
        name="Deck Scenario (12-molecule panel)",
        description="Deck-aligned fixed panel tuned for deterministic showcase behavior.",
        focus_temp_c=58.0,
        focus_meoh_pct=24.0,
        molecules=(
            MoleculeProfile("1", "CCOC(=O)c1c(sc(n1)C(C)C)NC(=O)C2COc3ccccc3O2", 22.7834, 0.0215, 0.0471, -0.0303, 6.1912),
            MoleculeProfile("2", "c1ccc(cc1)Cn2c(=O)c3ccc(cc3[nH]c2=S)C(=O)NCCC4=CCCCC4", 28.0688, -0.1190, 0.0702, 0.0153, 7.3458),
            MoleculeProfile("3", "CC1(C(=O)N(c2cc(ccc2O1)C(=O)N3CCOCC3)CC(=O)NCc4ccccc4)C", 33.1252, -0.0514, -0.0018, -0.0230, 8.6668),
            MoleculeProfile("4", "c1cc(cc(c1)F)c2cc(c(s2)C(=O)N[C@H]3CCCNC3)NC(=O)N", 38.1261, 0.0252, -0.0727, -0.0283, 8.7514),
            MoleculeProfile("5", "COCC(=O)N1C[C@@H]2CN(CCO2)C(=O)[C@@H]3C[C@@H](CN3Cc4c[nH]cn4)NC(=O)C[C@H]5[C@@H]([C@@H]([C@@H](C1)O5)O)O", 42.8532, 0.0292, -0.0554, 0.0551, 10.0085),
            MoleculeProfile("6", "Cc1ccc(cc1)C(C)(C)CN(C)C(=O)c2cc(ccn2)C(=O)O", 47.4350, 0.0450, 0.0541, -0.0571, 9.1513),
            MoleculeProfile("7", "c1cc(ccc1C2(CC2)C(=O)Nc3nc(cs3)CC(=O)O)Cl", 52.7233, 0.1075, 0.0029, 0.0337, 10.0699),
            MoleculeProfile("8", "Cc1ccc(cc1)N(CC(=O)Nc2ccc(c(c2)Cl)Cl)S(=O)(=O)C", 57.8310, -0.0413, 0.0599, -0.0191, 10.4430),
            MoleculeProfile("9", "Cc1ccn(n1)CCC(=O)N2CCC(CC2)c3cc4cc(c(cc4cn3)C)OC", 62.3824, 0.1130, 0.0245, 0.0239, 10.5708),
            MoleculeProfile("10", "CC(=C)CSc1nc2ccc(cc2c(=O)n1c3ccc(cc3)OC)I", 67.5149, 0.0409, -0.0395, -0.0442, 11.5068),
            MoleculeProfile("11", "CC1C(CC(N(C1c2ccccc2)C)c3ccccc3)O", 71.8603, -0.0112, -0.0429, 0.0500, 12.2416),
            MoleculeProfile("12", "Cc1c(ccc(n1)NCCO)[N+](=O)[O-]", 76.9561, -0.1125, -0.0405, 0.0257, 12.7647),
        ),
    ),
    "photostability_panel": Preset(
        preset_id="photostability_panel",
        name="Photostability Panel",
        description="A fixed degradation-style panel reflecting UV/heat stress analysis.",
        focus_temp_c=61.0,
        focus_meoh_pct=32.0,
        molecules=(
            MoleculeProfile("M1", "CCOC(=O)c1c(sc(n1)C(C)C)NC(=O)C2COc3ccccc3O2", 29.4, -0.06, 0.04, 0.02, 8.2),
            MoleculeProfile("M2", "c1ccc(cc1)Cn2c(=O)c3ccc(cc3[nH]c2=S)C(=O)NCCC4=CCCCC4", 35.5, -0.03, 0.08, -0.01, 7.8),
            MoleculeProfile("M3", "CC1(C(=O)N(c2cc(ccc2O1)C(=O)N3CCOCC3)CC(=O)NCc4ccccc4)C", 42.8, 0.02, -0.02, 0.04, 8.9),
            MoleculeProfile("M4", "c1cc(cc(c1)F)c2cc(c(s2)C(=O)N[C@H]3CCCNC3)NC(=O)N", 50.6, 0.04, -0.07, -0.03, 10.1),
            MoleculeProfile("M5", "COCC(=O)N1C[C@@H]2CN(CCO2)C(=O)[C@@H]3C[C@@H](CN3Cc4c[nH]cn4)NC(=O)C[C@H]5[C@@H]([C@@H]([C@@H](C1)O5)O)O", 59.2, 0.06, 0.01, -0.04, 9.6),
            MoleculeProfile("M6", "Cc1ccc(cc1)C(C)(C)CN(C)C(=O)c2cc(ccn2)C(=O)O", 70.1, 0.09, 0.03, 0.02, 11.2),
            MoleculeProfile("M7", "c1cc(ccc1C2(CC2)C(=O)Nc3nc(cs3)CC(=O)O)Cl", 79.3, 0.10, -0.05, 0.05, 12.4),
        ),
    ),
    "basic_api_mix": Preset(
        preset_id="basic_api_mix",
        name="Basic API Mix",
        description="A compact panel tuned to illustrate fast method exploration.",
        focus_temp_c=55.0,
        focus_meoh_pct=28.0,
        molecules=(
            MoleculeProfile("B1", "CCN(CC)CCOC(=O)c1ccccc1Cl", 24.1, -0.03, 0.05, -0.01, 6.5),
            MoleculeProfile("B2", "CC(C)NCC(O)COc1ccc(cc1)Cl", 30.6, -0.06, 0.07, 0.02, 7.0),
            MoleculeProfile("B3", "CCOC(=O)N1CCN(CC1)C2=NC=CC=C2", 38.3, -0.02, 0.02, -0.04, 8.1),
            MoleculeProfile("B4", "CC1=CC(=O)NC(=O)N1", 46.9, 0.03, -0.06, 0.01, 8.8),
            MoleculeProfile("B5", "CC(C)OC(=O)NCCC1=CN=CN1", 55.8, 0.08, -0.01, 0.03, 9.4),
            MoleculeProfile("B6", "CCOC(=O)C1=CC=CC=C1O", 66.2, 0.10, -0.04, -0.02, 10.3),
        ),
    ),
    "late_eluters": Preset(
        preset_id="late_eluters",
        name="Late-Eluter Stress Test",
        description="A heavier fixed set used to mimic difficult late-eluting separations.",
        focus_temp_c=63.0,
        focus_meoh_pct=35.0,
        molecules=(
            MoleculeProfile("L1", "CCOC(=O)NCCCc1ccccc1", 52.0, 0.04, 0.02, -0.03, 8.9),
            MoleculeProfile("L2", "CCN(CC)C(=O)c1ccc2ccccc2c1", 63.2, 0.06, -0.01, 0.01, 9.6),
            MoleculeProfile("L3", "CCOC(=O)c1ccc(cc1)N2CCN(CC2)C", 75.1, 0.08, -0.04, 0.02, 10.3),
            MoleculeProfile("L4", "CC(C)NCCOc1ccc2ncccc2c1", 89.7, 0.09, -0.07, -0.02, 11.4),
            MoleculeProfile("L5", "CCOC(=O)N1CCN(CC1)C2=CC=CC=C2C", 104.3, 0.11, -0.02, 0.03, 12.0),
            MoleculeProfile("L6", "CCN(CC)CCOC(=O)c1ccc2ccccc2c1Cl", 122.6, 0.12, -0.05, 0.04, 12.9),
            MoleculeProfile("L7", "CCOC(=O)NCCCc1ccc2ccccc2c1", 140.1, 0.13, -0.03, -0.01, 13.8),
        ),
    ),
}


def _compute_landscape(preset: Preset) -> Dict[str, object]:
    temp_axis = [float(t) for t in range(int(TEMP_MIN), int(TEMP_MAX) + 1)]
    meoh_axis = [float(m) for m in range(int(MEOH_MIN), int(MEOH_MAX) + 1)]

    values: List[List[float]] = []
    best_obj = -1.0
    best_temp = temp_axis[0]
    best_meoh = meoh_axis[0]

    for t in temp_axis:
        row: List[float] = []
        for m in meoh_axis:
            rt_values = [_retention_time_seconds(molecule, preset, t, m) for molecule in preset.molecules]
            summary = _objective(rt_values)
            obj = summary["optimization_metric_s"]
            row.append(round(obj, 3))
            if obj > best_obj:
                best_obj = obj
                best_temp = t
                best_meoh = m
        values.append(row)

    return {
        "temp_axis": temp_axis,
        "meoh_axis": meoh_axis,
        "values": values,
        "best_point": {
            "temperature_c": round(best_temp, 2),
            "meoh_pct": round(best_meoh, 2),
            "optimization_metric_s": round(best_obj, 3),
            # Deprecated alias kept for backwards compatibility with older clients.
            "quality_score": round(max(best_obj, 0.0), 3),
        },
    }


LANDSCAPES: Dict[str, Dict[str, object]] = {preset_id: _compute_landscape(preset) for preset_id, preset in PRESETS.items()}


def get_presets() -> List[Dict[str, object]]:
    payload: List[Dict[str, object]] = []
    for preset_id, preset in PRESETS.items():
        payload.append(
            {
                "preset_id": preset_id,
                "name": preset.name,
                "description": preset.description,
                "temperature_range": {"min": TEMP_MIN, "max": TEMP_MAX, "step": 0.1},
                "meoh_range": {"min": MEOH_MIN, "max": MEOH_MAX, "step": 0.1},
                "molecules": [{"label": m.label, "smiles": m.smiles} for m in preset.molecules],
                "landscape": LANDSCAPES[preset_id],
            }
        )
    return payload


def simulate(preset_id: str, temperature_c: float, meoh_pct: float) -> Dict[str, object]:
    if preset_id not in PRESETS:
        raise KeyError(f"Unknown preset_id: {preset_id}")

    preset = PRESETS[preset_id]
    rt_values = [_retention_time_seconds(molecule, preset, temperature_c, meoh_pct) for molecule in preset.molecules]

    peaks = []
    for molecule, rt in zip(preset.molecules, rt_values):
        peaks.append({"label": molecule.label, "smiles": molecule.smiles, "retention_time_s": rt})

    summary = _objective(rt_values)

    x_max = max(300.0, summary["max_retention_s"] + 30.0)
    points_count = 1400
    step = x_max / (points_count - 1)
    chromatogram_series = []

    for idx in range(points_count):
        x = idx * step
        y = 0.0
        for rt in rt_values:
            y += _gaussian(x, rt, PEAK_SIGMA)
        chromatogram_series.append({"x": round(x, 3), "y": round(y, 6)})

    landscape = LANDSCAPES[preset_id]
    heatmap_point = {
        "temperature_c": round(temperature_c, 2),
        "meoh_pct": round(meoh_pct, 2),
        "optimization_metric_s": summary["optimization_metric_s"],
        # Deprecated alias kept for backwards compatibility with older clients.
        "quality_score": summary["quality_score"],
        "best_point": landscape["best_point"],
    }

    return {
        "preset_id": preset_id,
        "peaks": peaks,
        "chromatogram_series": chromatogram_series,
        "heatmap_point": heatmap_point,
        "summary_metrics": summary,
    }
