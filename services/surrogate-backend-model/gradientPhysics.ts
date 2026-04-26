import modelData from './models/HILIC-LC_Small_Polar_v2/base_prediction.json'

export interface GradientProgram {
  initialPercentB: number
  holdUntilMin: number
  rampEndMin: number
  finalPercentB: number
  purgeUntilMin: number
  conditioningStartMin: number
  reequilibrateUntilMin: number
}

export interface GradientPoint {
  timeMin: number
  percentB: number
}

export type GradientHandleId =
  | 'hold'
  | 'final'
  | 'purge-high'
  | 'purge-low'
  | 'end'

export interface GradientHandle {
  id: GradientHandleId
  timeMin: number
  percentB: number
  movableY: boolean
}

export interface GradientCompoundDefinition {
  id: string
  label: string
  compoundName: string
  smiles: string
  thresholdPercentB: number
  areaPct: number
  widthAtMaxFlowMin: number
  widthAtMinFlowMin: number
}

export const FLOW_RATE_LIMITS = {
  min: 0.1,
  max: 0.6,
  step: 0.01
} as const

export const DEFAULT_FLOW_RATE_ML_MIN = 0.2

export const DEFAULT_GRADIENT_PROGRAM: GradientProgram = {
  initialPercentB: 10,
  holdUntilMin: 0,
  rampEndMin: 2.7,
  finalPercentB: 70,
  purgeUntilMin: 2.7,
  conditioningStartMin: 2.71,
  reequilibrateUntilMin: 3
}

export function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function roundTo(value: number, digits = 3): number {
  const multiplier = 10 ** digits
  return Math.round(value * multiplier) / multiplier
}

export function normalizeGradientProgram(program: GradientProgram): GradientProgram {
  const initialPercentB = clampNumber(program.initialPercentB, 0, 35)
  const holdUntilMin = clampNumber(program.holdUntilMin, 0, 1.4)
  const rampEndMin = clampNumber(program.rampEndMin, holdUntilMin + 0.25, 3.4)
  const finalPercentB = clampNumber(program.finalPercentB, initialPercentB + 10, 100)
  const purgeUntilMin = clampNumber(program.purgeUntilMin, rampEndMin, 4.2)
  const conditioningStartMin = clampNumber(
    program.conditioningStartMin,
    purgeUntilMin + 0.01,
    4.4
  )
  const reequilibrateUntilMin = clampNumber(
    program.reequilibrateUntilMin,
    conditioningStartMin + 0.05,
    5
  )

  return {
    initialPercentB: roundTo(initialPercentB, 1),
    holdUntilMin: roundTo(holdUntilMin, 2),
    rampEndMin: roundTo(rampEndMin, 2),
    finalPercentB: roundTo(finalPercentB, 1),
    purgeUntilMin: roundTo(purgeUntilMin, 2),
    conditioningStartMin: roundTo(conditioningStartMin, 2),
    reequilibrateUntilMin: roundTo(reequilibrateUntilMin, 2)
  }
}

export function buildGradientProgramPoints(program: GradientProgram): GradientPoint[] {
  const normalized = normalizeGradientProgram(program)

  return [
    { timeMin: 0, percentB: normalized.initialPercentB },
    { timeMin: normalized.holdUntilMin, percentB: normalized.initialPercentB },
    { timeMin: normalized.rampEndMin, percentB: normalized.finalPercentB },
    { timeMin: normalized.purgeUntilMin, percentB: normalized.finalPercentB },
    { timeMin: normalized.conditioningStartMin, percentB: normalized.initialPercentB },
    { timeMin: normalized.reequilibrateUntilMin, percentB: normalized.initialPercentB }
  ]
}

export function getGradientHandles(program: GradientProgram): GradientHandle[] {
  const normalized = normalizeGradientProgram(program)

  return [
    {
      id: 'hold',
      timeMin: normalized.holdUntilMin,
      percentB: normalized.initialPercentB,
      movableY: true
    },
    {
      id: 'final',
      timeMin: normalized.rampEndMin,
      percentB: normalized.finalPercentB,
      movableY: true
    },
    {
      id: 'purge-high',
      timeMin: normalized.purgeUntilMin,
      percentB: normalized.finalPercentB,
      movableY: false
    },
    {
      id: 'purge-low',
      timeMin: normalized.conditioningStartMin,
      percentB: normalized.initialPercentB,
      movableY: false
    },
    {
      id: 'end',
      timeMin: normalized.reequilibrateUntilMin,
      percentB: normalized.initialPercentB,
      movableY: false
    }
  ]
}

export function moveGradientHandle(
  program: GradientProgram,
  handleId: GradientHandleId,
  nextTimeMin: number,
  nextPercentB: number
): GradientProgram {
  const normalized = normalizeGradientProgram(program)

  switch (handleId) {
    case 'hold':
      return normalizeGradientProgram({
        ...normalized,
        holdUntilMin: nextTimeMin,
        initialPercentB: nextPercentB
      })
    case 'final':
      return normalizeGradientProgram({
        ...normalized,
        rampEndMin: nextTimeMin,
        finalPercentB: nextPercentB
      })
    case 'purge-high':
      return normalizeGradientProgram({
        ...normalized,
        purgeUntilMin: nextTimeMin
      })
    case 'purge-low':
      return normalizeGradientProgram({
        ...normalized,
        conditioningStartMin: nextTimeMin
      })
    case 'end':
      return normalizeGradientProgram({
        ...normalized,
        reequilibrateUntilMin: nextTimeMin
      })
  }
}

export function evaluateGradientPercent(program: GradientProgram, timeMin: number): number {
  const normalized = normalizeGradientProgram(program)

  if (timeMin <= normalized.holdUntilMin) {
    return normalized.initialPercentB
  }

  if (timeMin <= normalized.rampEndMin) {
    const rampFraction =
      (timeMin - normalized.holdUntilMin) /
      Math.max(0.001, normalized.rampEndMin - normalized.holdUntilMin)

    return roundTo(
      normalized.initialPercentB +
        (normalized.finalPercentB - normalized.initialPercentB) * rampFraction,
      3
    )
  }

  if (timeMin <= normalized.purgeUntilMin) {
    return normalized.finalPercentB
  }

  if (timeMin <= normalized.conditioningStartMin) {
    const descentFraction =
      (timeMin - normalized.purgeUntilMin) /
      Math.max(0.001, normalized.conditioningStartMin - normalized.purgeUntilMin)

    return roundTo(
      normalized.finalPercentB +
        (normalized.initialPercentB - normalized.finalPercentB) * descentFraction,
      3
    )
  }

  return normalized.initialPercentB
}

export function findGradientThresholdCrossing(
  program: GradientProgram,
  thresholdPercentB: number
): number {
  const normalized = normalizeGradientProgram(program)

  if (thresholdPercentB <= normalized.initialPercentB) {
    return 0.05
  }

  if (thresholdPercentB >= normalized.finalPercentB) {
    return normalized.rampEndMin
  }

  const rampFraction =
    (thresholdPercentB - normalized.initialPercentB) /
    Math.max(0.001, normalized.finalPercentB - normalized.initialPercentB)

  return roundTo(
    normalized.holdUntilMin +
      (normalized.rampEndMin - normalized.holdUntilMin) * rampFraction,
    3
  )
}

function buildThresholdForTargetTime(targetTimeMin: number): number {
  return evaluateGradientPercent(DEFAULT_GRADIENT_PROGRAM, targetTimeMin)
}

export const DEMO_GRADIENT_COMPOUNDS: GradientCompoundDefinition[] = modelData.analytes.map(
  (a) => ({
    id: a.id,
    label: a.label,
    compoundName: a.compoundName,
    smiles: a.smiles,
    thresholdPercentB: buildThresholdForTargetTime(a.targetRetentionTimeMin),
    areaPct: a.areaPct,
    widthAtMaxFlowMin: a.widthAtMaxFlowMin,
    widthAtMinFlowMin: a.widthAtMinFlowMin,
  })
)
