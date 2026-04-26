# surrogate-backend-model

Gradient physics and compound prediction data for the Silico AI surrogate.

## Structure

```
models/
  HILIC-LC_Small_Polar_v2/       ← active model
    base_prediction.json         ← analyte definitions (retention targets, peak geometry)
  HILIC-LC_Polar_Ionizable_v3/   ← planned
  RP-LC_Small_Molecule_v4/       ← planned
  MixedMode-LC_Basic_Analytes_v2/ ← planned
gradientPhysics.ts               ← piecewise-linear gradient engine + elution physics
```

## How it works

`gradientPhysics.ts` implements the gradient program model: a `%B`-over-time profile that drives analyte elution. Each analyte in `base_prediction.json` declares a target retention time; the physics layer converts that to the `%B` threshold at which the analyte elutes under the active gradient.

The active model is `HILIC-LC_Small_Polar_v2`. Swapping to a different model means pointing the import at a different `base_prediction.json` — the physics engine is model-agnostic.

## Model files

`base_prediction.json` fields per analyte:

| Field | Meaning |
|---|---|
| `targetRetentionTimeMin` | Intended elution time under the default gradient |
| `areaPct` | Relative detector response contribution |
| `widthAtMaxFlowMin` / `widthAtMinFlowMin` | Peak width bounds across the flow rate range |
