import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, GripVertical } from 'lucide-react'
import type { Recommendation } from '../../types'
import { ChromatogramChart } from './ChromatogramChart'
import { GradientProfileEditor } from './GradientProfileEditor'
import {
  DEFAULT_FLOW_RATE_ML_MIN,
  DEFAULT_GRADIENT_PROGRAM,
  FLOW_RATE_LIMITS,
  normalizeGradientProgram
} from '@surrogate-backend-model/gradientPhysics'
import {
  buildSurrogateWorkbenchData,
  type SurrogatePeak,
  type SurrogateTuningValues
} from './surrogateModel'
import './surrogateWorkbench.css'

const HPLC_SETTING_TOKENS = [
  'Flow rate',
  'Temperature',
  'Mobile phase A',
  'Mobile phase B',
  'Buffer additive',
  'pH',
  'Gradient profile',
  'Injection volume',
  'Sample diluent'
] as const

const MATCHED_MODEL_OPTIONS = [
  'HILIC-LC_Small_Polar_v2',
  'HILIC-LC_Polar_Ionizable_v3',
  'RP-LC_Small_Molecule_v4',
  'MixedMode-LC_Basic_Analytes_v2'
] as const

const SIMULATION_STEPS = [
  'setting up bespoke model',
  'sweeping parameters',
  'finding optimal combination of flow rate and the right gradient profile',
  'Done!'
] as const

type SimulationState = 'idle' | 'running' | 'done'

type SettingBucket = 'variable' | 'fixed'

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-list-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function PeakListItem({
  peak,
  active,
  onClick
}: {
  peak: SurrogatePeak
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={active ? 'peak-list-item active' : 'peak-list-item'}
    >
      <div className="peak-list-topline">
        <strong>{peak.compound_name}</strong>
        <span>{`${peak.retention_time_min.toFixed(2)} min`}</span>
      </div>
      <p className="peak-list-meta">
        {`${peak.area_pct.toFixed(1)}% area | width ${peak.width_min.toFixed(2)} min`}
      </p>
    </button>
  )
}

function SettingChip({
  label,
  onDragStart,
  onDragEnd
}: {
  label: string
  onDragStart: () => void
  onDragEnd: () => void
}) {
  return (
    <div
      className="setting-chip"
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      <GripVertical className="setting-chip-icon" />
      <span>{label}</span>
    </div>
  )
}

export function SurrogateWorkbench({
  selectedRecommendation,
  selectedRecommendationId,
  resetToken,
  tuning,
  onTuningChange
}: {
  selectedRecommendation: Recommendation
  selectedRecommendationId: string
  resetToken: number
  tuning: SurrogateTuningValues
  onTuningChange: (next: SurrogateTuningValues) => void
}) {
  const [activePeakIndex, setActivePeakIndex] = useState<number | null>(0)
  const [draggingSetting, setDraggingSetting] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>(MATCHED_MODEL_OPTIONS[0])
  const [simulationState, setSimulationState] = useState<SimulationState>('idle')
  const [simulationStepIndex, setSimulationStepIndex] = useState<number>(-1)
  const [settingBuckets, setSettingBuckets] = useState<Record<SettingBucket, string[]>>({
    variable: [],
    fixed: [...HPLC_SETTING_TOKENS]
  })
  const workbench = useMemo(
    () => buildSurrogateWorkbenchData(selectedRecommendation, null, tuning),
    [selectedRecommendation, tuning]
  )

  useEffect(() => {
    setActivePeakIndex(0)
  }, [resetToken, selectedRecommendationId])

  useEffect(() => {
    setSettingBuckets({
      variable: [],
      fixed: [...HPLC_SETTING_TOKENS]
    })
    setSelectedModel(MATCHED_MODEL_OPTIONS[0])
    setSimulationState('idle')
    setSimulationStepIndex(-1)
  }, [resetToken, selectedRecommendationId])

  useEffect(() => {
    if (simulationState !== 'running') {
      return
    }

    const timers = [
      window.setTimeout(() => setSimulationStepIndex(1), 900),
      window.setTimeout(() => setSimulationStepIndex(2), 3600),
      window.setTimeout(() => setSimulationStepIndex(3), 7200),
      window.setTimeout(() => setSimulationState('done'), 8200)
    ]

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [simulationState])

  useEffect(() => {
    const activeVariableSet = new Set(settingBuckets.variable)
    const normalizedGradient = normalizeGradientProgram(tuning.gradientProgram)
    const defaultGradient = normalizeGradientProgram(DEFAULT_GRADIENT_PROGRAM)
    const gradientChanged =
      normalizedGradient.initialPercentB !== defaultGradient.initialPercentB ||
      normalizedGradient.holdUntilMin !== defaultGradient.holdUntilMin ||
      normalizedGradient.rampEndMin !== defaultGradient.rampEndMin ||
      normalizedGradient.finalPercentB !== defaultGradient.finalPercentB ||
      normalizedGradient.purgeUntilMin !== defaultGradient.purgeUntilMin ||
      normalizedGradient.conditioningStartMin !== defaultGradient.conditioningStartMin ||
      normalizedGradient.reequilibrateUntilMin !== defaultGradient.reequilibrateUntilMin

    if (
      !activeVariableSet.has('Flow rate') &&
      tuning.flowRateMlMin !== DEFAULT_FLOW_RATE_ML_MIN
    ) {
      onTuningChange({
        ...tuning,
        flowRateMlMin: DEFAULT_FLOW_RATE_ML_MIN
      })
      return
    }

    if (!activeVariableSet.has('Gradient profile') && gradientChanged) {
      onTuningChange({
        ...tuning,
        gradientProgram: { ...DEFAULT_GRADIENT_PROGRAM }
      })
    }
  }, [onTuningChange, settingBuckets.variable, tuning])

  useEffect(() => {
    if (!workbench.prediction.peaks.length) {
      setActivePeakIndex(null)
      return
    }

    if (activePeakIndex === null || !workbench.prediction.peaks[activePeakIndex]) {
      setActivePeakIndex(0)
    }
  }, [activePeakIndex, workbench.prediction.peaks])

  const currentMetrics = workbench.prediction.summary_metrics
  const referenceSummary = workbench.reference_summary
  const variableSettingCount = settingBuckets.variable.length
  const fixedSettingCount = settingBuckets.fixed.length
  const activeVariableSet = new Set(settingBuckets.variable)
  const showsFlowControl = activeVariableSet.has('Flow rate')
  const showsGradientControl = activeVariableSet.has('Gradient profile')
  const showWorkbenchResults = simulationState === 'done'

  const moveSettingToBucket = (setting: string, nextBucket: SettingBucket) => {
    setSettingBuckets((current) => {
      const sourceBucket =
        current.variable.includes(setting) ? 'variable' : current.fixed.includes(setting) ? 'fixed' : null

      if (!sourceBucket || sourceBucket === nextBucket) {
        return current
      }

      return {
        variable:
          nextBucket === 'variable'
            ? [...current.variable, setting]
            : current.variable.filter((item) => item !== setting),
        fixed:
          nextBucket === 'fixed'
            ? [...current.fixed, setting]
            : current.fixed.filter((item) => item !== setting)
      }
    })
    setDraggingSetting(null)
  }

  const startSimulation = () => {
    if (simulationState === 'running') {
      return
    }

    setSimulationStepIndex(0)
    setSimulationState('running')
  }

  return (
    <div className="surrogate-workbench-shell mt-8">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="space-y-4 min-w-0">
          {!showWorkbenchResults ? (
            <section
              className="simulate-launch-card rounded-[1.4rem] border border-border bg-card/75 px-5 py-5"
              aria-busy={simulationState === 'running'}
            >
              <div className="simulate-launch-head">
                <div>
                  <h2>Match model</h2>
                </div>
              </div>

              <div className="simulate-launch-grid">
                <label className="simulate-field">
                  <span className="field-label">Model found!</span>
                  <select
                    value={selectedModel}
                    onChange={(event) => setSelectedModel(event.target.value)}
                    className="simulate-select"
                    aria-label="Matched model"
                    disabled={simulationState === 'running'}
                  >
                    {MATCHED_MODEL_OPTIONS.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="simulate-match-list" aria-label="Model compatibility checks">
                  {['Hardware', 'Solvent', 'Detector'].map((item) => (
                    <div key={item} className="simulate-match-item">
                      <CheckCircle2 className="simulate-match-icon" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              {simulationState === 'running' ? (
                <div className="simulation-progress-shell" role="status" aria-live="polite">
                  <div className="simulation-progress-bar" aria-hidden="true">
                    <span
                      style={{
                        width: `${((simulationStepIndex + 1) / SIMULATION_STEPS.length) * 100}%`
                      }}
                    />
                  </div>
                  <div className="simulation-step-list">
                    {SIMULATION_STEPS.map((step, index) => {
                      const status =
                        index < simulationStepIndex
                          ? 'done'
                          : index === simulationStepIndex
                            ? 'active'
                            : 'pending'

                      return (
                        <div
                          key={step}
                          className={`simulation-step-item simulation-step-${status}`}
                        >
                          <span className="simulation-step-marker" aria-hidden="true" />
                          <span>{step}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <button type="button" className="simulate-button" onClick={startSimulation}>
                  simulate
                </button>
              )}
            </section>
          ) : null}

          {showWorkbenchResults && (showsFlowControl || showsGradientControl) ? (
            <section className="rounded-[1.4rem] border border-border bg-card/75 px-5 py-5">
              <div className="variable-control-stack">
                {showsFlowControl ? (
                  <div className="variable-control-block">
                    <div className="variable-control-head">
                      <h3>Flow rate</h3>
                      <strong>{`${tuning.flowRateMlMin.toFixed(2)} mL/min`}</strong>
                    </div>
                    <input
                      id="surrogate-flow-rate"
                      className="slider"
                      type="range"
                      min={String(FLOW_RATE_LIMITS.min)}
                      max={String(FLOW_RATE_LIMITS.max)}
                      step={String(FLOW_RATE_LIMITS.step)}
                      value={tuning.flowRateMlMin}
                      onChange={(event) =>
                        onTuningChange({
                          ...tuning,
                          flowRateMlMin: Number(event.target.value)
                        })
                      }
                    />
                  </div>
                ) : null}

                {showsGradientControl ? (
                  <div className="variable-control-block gradient-block">
                    <div className="variable-control-head">
                      <h3>Gradient profile</h3>
                      <strong>{`${tuning.gradientProgram.initialPercentB.toFixed(0)} to ${tuning.gradientProgram.finalPercentB.toFixed(0)} %B`}</strong>
                    </div>
                    <GradientProfileEditor
                      program={tuning.gradientProgram}
                      onChange={(gradientProgram) =>
                        onTuningChange({
                          ...tuning,
                          gradientProgram
                        })
                      }
                    />
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          {showWorkbenchResults ? (
            <section className="rounded-[1.4rem] border border-border bg-card/75 overflow-hidden">
              <div className="surface-head compact-head">
                <div>
                  <h3>Chromatogram</h3>
                </div>
              </div>
              <ChromatogramChart
                activePeakIndex={activePeakIndex}
                peaks={workbench.prediction.peaks}
                series={workbench.prediction.chromatogram_series}
                title={`Flow ${tuning.flowRateMlMin.toFixed(2)} mL/min | Gradient ${tuning.gradientProgram.initialPercentB.toFixed(0)}-${tuning.gradientProgram.finalPercentB.toFixed(0)} %B`}
                onPeakSelect={setActivePeakIndex}
              />
            </section>
          ) : null}
        </section>

        <aside className="space-y-4">
          <section className="rounded-[1.4rem] border border-border bg-card/75 px-5 py-5">
            <div className="settings-board-head">
              <div>
                <h3 className="font-serif text-base text-foreground">Experimental conditions</h3>
              </div>
              <p className="settings-board-summary">
                {`${variableSettingCount} variable / ${fixedSettingCount} fixed`}
              </p>
            </div>

            <div className="settings-board-grid mt-4">
              {(['variable', 'fixed'] as SettingBucket[]).map((bucket) => (
                <div
                  key={bucket}
                  className="settings-dropzone"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault()
                    if (draggingSetting) {
                      moveSettingToBucket(draggingSetting, bucket)
                    }
                  }}
                >
                  <div className="settings-dropzone-head">
                    <h4>{bucket === 'variable' ? 'Variable settings' : 'Fixed settings'}</h4>
                    <span>{settingBuckets[bucket].length}</span>
                  </div>

                  <div className="settings-chip-grid">
                    {settingBuckets[bucket].length ? (
                      settingBuckets[bucket].map((setting) => (
                        <SettingChip
                          key={setting}
                          label={setting}
                          onDragStart={() => setDraggingSetting(setting)}
                          onDragEnd={() => setDraggingSetting(null)}
                        />
                      ))
                    ) : (
                      <div className="settings-dropzone-empty">Drop settings here</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {showWorkbenchResults ? (
            <>
              <section className="rounded-[1.4rem] border border-border bg-card/75 px-5 py-5">
                <div>
                  <h3 className="font-serif text-base text-foreground">Separation summary</h3>
                  <p className="mini-note mt-1">
                    {`Standard pair gap ${referenceSummary.min_separation_min.toFixed(2)} min`}
                  </p>
                </div>

                <div className="metric-list mt-4" aria-label="Separation summary">
                  <MetricRow
                    label="Metformin retention"
                    value={`${workbench.prediction.peaks[0]?.retention_time_min.toFixed(2) || '0.00'} min`}
                  />
                  <MetricRow
                    label="Rosuvastatin retention"
                    value={`${workbench.prediction.peaks[1]?.retention_time_min.toFixed(2) || '0.00'} min`}
                  />
                  <MetricRow
                    label="Current pair separation"
                    value={`${currentMetrics.min_separation_min.toFixed(2)} min`}
                  />
                  <MetricRow
                    label="Critical resolution"
                    value={currentMetrics.critical_resolution.toFixed(2)}
                  />
                  <MetricRow
                    label="Current max retention"
                    value={`${currentMetrics.max_retention_min.toFixed(2)} min`}
                  />
                  <MetricRow
                    label="Quality score"
                    value={`${currentMetrics.quality_score.toFixed(1)} / 99`}
                  />
                </div>
              </section>

              <section className="rounded-[1.4rem] border border-border bg-card/75 px-5 py-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="font-serif text-base text-foreground">Peak list</h3>
                    <p className="mini-note mt-1">
                      {`${workbench.prediction.peaks.length} peak${workbench.prediction.peaks.length === 1 ? '' : 's'}`}
                    </p>
                  </div>
                </div>

                <div className="peak-list mt-4">
                  {workbench.prediction.peaks.map((peak, index) => (
                    <PeakListItem
                      key={`${peak.label}-${peak.retention_time_min}`}
                      peak={peak}
                      active={activePeakIndex === index}
                      onClick={() => setActivePeakIndex(index)}
                    />
                  ))}
                </div>
              </section>
            </>
          ) : null}
        </aside>
      </div>
    </div>
  )
}
