import type { DummySurrogateSession, Recommendation } from '../../types'
import {
  DEFAULT_FLOW_RATE_ML_MIN,
  DEFAULT_GRADIENT_PROGRAM,
  DEMO_GRADIENT_COMPOUNDS,
  FLOW_RATE_LIMITS,
  clampNumber,
  findGradientThresholdCrossing,
  normalizeGradientProgram,
  roundTo,
  type GradientProgram
} from '@surrogate-backend-model/gradientPhysics'

export interface SurrogateTuningValues {
  flowRateMlMin: number
  gradientProgram: GradientProgram
}

export interface SurrogatePeak {
  id: string
  label: string
  compound_name: string
  smiles: string
  retention_time_min: number
  area_pct: number
  width_min: number
  role: 'analyte'
}

export interface SurrogateChartPoint {
  x: number
  y: number
}

export interface SurrogateSummaryMetrics {
  min_separation_min: number
  max_retention_min: number
  critical_resolution: number
  optimization_metric_min: number
  quality_score: number
}

export interface SurrogateLandscapeBestPoint {
  temperature_c: number
  meoh_pct: number
  optimization_metric_s: number
  quality_score: number
}

export interface SurrogateLandscape {
  temp_axis: number[]
  meoh_axis: number[]
  values: number[][]
  best_point: SurrogateLandscapeBestPoint
}

export interface SurrogatePrediction {
  peaks: SurrogatePeak[]
  chromatogram_series: SurrogateChartPoint[]
  summary_metrics: SurrogateSummaryMetrics
}

export interface SurrogateWorkbenchData {
  session: DummySurrogateSession
  prediction: SurrogatePrediction
  reference_summary: SurrogateSummaryMetrics
}

const PEAK_ROLE_LABELS: Record<SurrogatePeak['role'], string> = {
  analyte: 'Analyte'
}

function gaussian(x: number, mean: number, sigma: number, amplitude: number): number {
  const exponent = -((x - mean) ** 2) / (2 * sigma ** 2)
  return amplitude * Math.exp(exponent)
}

function postureFromScore(score: number): 'stable' | 'watch' | 'unstable' {
  if (score >= 0.84) {
    return 'stable'
  }
  if (score >= 0.7) {
    return 'watch'
  }
  return 'unstable'
}

function average(values: number[]): number {
  if (!values.length) {
    return 0
  }
  return values.reduce((total, value) => total + value, 0) / values.length
}

function buildPrediction(
  tuning: SurrogateTuningValues
): SurrogatePrediction {
  const gradientProgram = normalizeGradientProgram(tuning.gradientProgram)
  const flowRateMlMin = clampNumber(
    tuning.flowRateMlMin,
    FLOW_RATE_LIMITS.min,
    FLOW_RATE_LIMITS.max
  )
  const flowFraction =
    (flowRateMlMin - FLOW_RATE_LIMITS.min) /
    (FLOW_RATE_LIMITS.max - FLOW_RATE_LIMITS.min)

  const peaks = DEMO_GRADIENT_COMPOUNDS.map((compound) => {
    const retentionTimeMin = findGradientThresholdCrossing(
      gradientProgram,
      compound.thresholdPercentB
    )
    const baseWidth =
      compound.widthAtMinFlowMin +
      (compound.widthAtMaxFlowMin - compound.widthAtMinFlowMin) * flowFraction
    const widthMin = roundTo(baseWidth * (1 + retentionTimeMin * 0.04), 3)

    return {
      id: compound.id,
      label: compound.label,
      compound_name: compound.compoundName,
      smiles: compound.smiles,
      retention_time_min: roundTo(retentionTimeMin, 3),
      area_pct: compound.areaPct,
      width_min: widthMin,
      role: 'analyte' as const
    }
  })

  const amplitudeFactors = peaks.map((peak) => (peak.area_pct / 100) / Math.max(0.01, peak.width_min))
  const amplitudeScale = 0.92 / Math.max(...amplitudeFactors, 1)
  const amplitudes = amplitudeFactors.map((factor) => factor * amplitudeScale)
  const maxX = Math.max(
    gradientProgram.reequilibrateUntilMin,
    peaks[peaks.length - 1]?.retention_time_min ?? 0,
    2.6
  )
  const seriesPointTotal = 420
  const chromatogram_series: SurrogateChartPoint[] = Array.from(
    { length: seriesPointTotal + 1 },
    (_, index) => {
      const x = (index / seriesPointTotal) * maxX
      const noise = 0.008 + Math.sin(index / 18) * 0.0015 + Math.cos(index / 33) * 0.001
      const y = peaks.reduce((total, peak, peakIndex) => {
        return total + gaussian(x, peak.retention_time_min, peak.width_min, amplitudes[peakIndex])
      }, noise)

      return {
        x: roundTo(x, 3),
        y: roundTo(y, 4)
      }
    }
  )

  const peakGaps = peaks
    .slice(1)
    .map((peak, index) => peak.retention_time_min - peaks[index].retention_time_min)
  const minSeparation = Math.min(...peakGaps)
  const averageWidth = average(peaks.map((peak) => peak.width_min))
  const criticalResolution = roundTo(
    clampNumber(minSeparation / Math.max(0.02, averageWidth), 0.8, 18),
    3
  )
  const maxRetention = peaks[peaks.length - 1]?.retention_time_min ?? maxX
  const optimizationMetric = roundTo(Math.max(0.1, minSeparation - averageWidth * 0.45), 3)
  const qualityScore = roundTo(
    clampNumber(
      72 +
        criticalResolution * 1.8 +
        flowFraction * 8 -
        Math.max(0, maxRetention - 2.1) * 8,
      58,
      99
    ),
    1
  )

  return {
    peaks,
    chromatogram_series,
    summary_metrics: {
      min_separation_min: roundTo(minSeparation, 3),
      max_retention_min: roundTo(maxRetention, 3),
      critical_resolution: criticalResolution,
      optimization_metric_min: optimizationMetric,
      quality_score: qualityScore
    }
  }
}

export function getPeakRoleLabel(role: SurrogatePeak['role']): string {
  return PEAK_ROLE_LABELS[role]
}

export function getRecommendationRuntime(_: Recommendation): number {
  return DEFAULT_GRADIENT_PROGRAM.reequilibrateUntilMin
}

export function getRecommendationFlow(_: Recommendation): number {
  return DEFAULT_FLOW_RATE_ML_MIN
}

export function getRecommendationTemperature(_: Recommendation): number {
  return 40
}

export function getRecommendationMeoh(_: Recommendation): number {
  return DEFAULT_GRADIENT_PROGRAM.initialPercentB
}

export function createSurrogateTuningValues(_: Recommendation): SurrogateTuningValues {
  return {
    flowRateMlMin: DEFAULT_FLOW_RATE_ML_MIN,
    gradientProgram: { ...DEFAULT_GRADIENT_PROGRAM }
  }
}

export function buildDummySurrogateSession(
  recommendation: Recommendation,
  topRecommendation: Recommendation | null,
  tuning: Partial<SurrogateTuningValues> = {}
): DummySurrogateSession {
  const defaults = createSurrogateTuningValues(recommendation)
  const mergedTuning: SurrogateTuningValues = {
    flowRateMlMin: clampNumber(
      tuning.flowRateMlMin ?? defaults.flowRateMlMin,
      FLOW_RATE_LIMITS.min,
      FLOW_RATE_LIMITS.max
    ),
    gradientProgram: normalizeGradientProgram({
      ...defaults.gradientProgram,
      ...(tuning.gradientProgram ?? {})
    })
  }
  const prediction = buildPrediction(mergedTuning)
  const metformin = prediction.peaks[0]
  const afatinib = prediction.peaks[1]
  const scoreDelta = topRecommendation
    ? Math.max(
        0,
        Math.round((topRecommendation.score.total_score - recommendation.score.total_score) * 100)
      )
    : 0
  const flowPosture = postureFromScore(
    0.72 +
      (mergedTuning.flowRateMlMin - DEFAULT_FLOW_RATE_ML_MIN) * 0.9 +
      prediction.summary_metrics.critical_resolution / 18
  )
  const gradientSpan =
    mergedTuning.gradientProgram.finalPercentB - mergedTuning.gradientProgram.initialPercentB
  const gradientPosture = postureFromScore(
    0.68 +
      Math.min(0.18, gradientSpan / 100) +
      Math.min(0.14, prediction.summary_metrics.min_separation_min / 2.5)
  )

  return {
    sessionId: `demo-${recommendation.paper_id}`,
    state: 'ready',
    modeLabel: 'Interactive flow and gradient demo',
    simulationLabel: 'Frontend-only chromatogram demo. No sidecar calls or scientific validation implied.',
    methodTitle: recommendation.title,
    prediction: {
      headline:
        prediction.summary_metrics.critical_resolution >= 6
          ? 'Metformin and rosuvastatin remain clearly separated in the current demo program.'
          : 'Metformin and rosuvastatin still separate, but the margin narrows in the current demo program.',
      summary: `Metformin elutes at ${metformin.retention_time_min.toFixed(2)} min and rosuvastatin at ${afatinib.retention_time_min.toFixed(2)} min under the current gradient.`,
      predictedRetentionWindowMin: [
        roundTo(metformin.retention_time_min, 2),
        roundTo(afatinib.retention_time_min, 2)
      ],
      confidenceLabel:
        prediction.summary_metrics.quality_score >= 84
          ? 'Stable demo preview'
          : 'Demo preview with moderate spread',
      signalQualityLabel:
        mergedTuning.flowRateMlMin >= 0.45
          ? 'Sharper synthetic peak envelopes'
          : 'Broader synthetic peak envelopes'
    },
    operatingWindows: [
      {
        id: 'flow',
        label: 'Flow window',
        testedWindow: `${FLOW_RATE_LIMITS.min.toFixed(2)} to ${FLOW_RATE_LIMITS.max.toFixed(2)} mL/min`,
        posture: flowPosture,
        summary:
          flowPosture === 'stable'
            ? 'Higher Waters-style flow compresses the pair into sharper synthetic peaks.'
            : flowPosture === 'watch'
              ? 'Lower flow broadens the peaks but keeps the pair readable.'
              : 'Very low flow spreads the synthetic envelopes and softens the pair.'
      },
      {
        id: 'gradient',
        label: 'Gradient window',
        testedWindow: `${mergedTuning.gradientProgram.initialPercentB.toFixed(0)} to ${mergedTuning.gradientProgram.finalPercentB.toFixed(0)} %B`,
        posture: gradientPosture,
        summary:
          gradientPosture === 'stable'
            ? 'Retention tracks the gradient threshold cleanly in the current program.'
            : gradientPosture === 'watch'
              ? 'Gradient timing remains plausible but moves the pair closer together.'
              : 'An aggressive program destabilizes the synthetic separation window.'
      }
    ],
    nextStepLabel: 'Edit the gradient handles',
    nextStepSummary:
      scoreDelta > 0
        ? 'Use the draggable gradient handles to compare this candidate against the top recommendation before a wet-lab run.'
        : 'Use flow rate and gradient shape together to stress-test the pair before a wet-lab run.',
    warnings: [
      'Demo-only surrogate preview. It is a UX simulation, not a validated chromatographic model.',
      'Retention is driven by a simplified gradient threshold model stored in the local surrogate backend-model folder.'
    ]
  }
}

export function buildSurrogateWorkbenchData(
  recommendation: Recommendation,
  topRecommendation: Recommendation | null,
  tuning: SurrogateTuningValues
): SurrogateWorkbenchData {
  const prediction = buildPrediction(tuning)
  const referenceSummary = buildPrediction(createSurrogateTuningValues(recommendation)).summary_metrics

  return {
    session: buildDummySurrogateSession(recommendation, topRecommendation, tuning),
    prediction,
    reference_summary: referenceSummary
  }
}
