import type {
  DiscoverySource,
  DiscoveryTarget,
  PromptRecognitionSummary,
  SystemSpecs,
  WorkflowPhase
} from '../../types'

export type PlanFieldStatus = 'provided' | 'recognized' | 'inferred' | 'missing'

export interface PlanFieldSummary {
  id:
    | 'analytes'
    | 'matrix'
    | 'impurities'
    | 'detector'
    | 'runtime'
    | 'sourceMode'
    | 'hardware'
    | 'unresolved'
    | 'defaults'
  label: string
  value: string
  status: PlanFieldStatus
}

export interface ConversationPlanSummary {
  fields: PlanFieldSummary[]
  inferredDefaults: string[]
  unresolvedItems: string[]
  recognitionSummary: string
  readinessSummary: string
}

const DEFAULT_SYSTEM: SystemSpecs = {
  columnManufacturer: 'Agilent',
  customManufacturer: '',
  columnName: '',
  columnChemistry: 'C18',
  customChemistry: '',
  columnLengthMm: 150,
  columnIdMm: 4.6,
  particleSizeUm: 5,
  availableSolvents: ['Water', 'Methanol'],
  detectorTypes: ['UV-Vis'],
  instrumentModes: [],
  maxPressureBar: null
}

const DEFAULT_TARGET: Pick<DiscoveryTarget, 'matrix' | 'requireMS' | 'maxRunTimeMin'> = {
  matrix: 'Human Plasma',
  requireMS: false,
  maxRunTimeMin: null
}

function formatSourceMode(source: DiscoverySource): string {
  return source === 'local_corpus' ? 'Local corpus' : 'Open access'
}

function formatMatrix(target: DiscoveryTarget): string {
  return target.matrix === 'Other' ? target.customMatrix?.trim() || 'Other matrix' : target.matrix
}

function formatHardware(systemSpecs: SystemSpecs): string {
  const manufacturer =
    systemSpecs.columnManufacturer === 'Other'
      ? systemSpecs.customManufacturer?.trim() || 'Custom manufacturer'
      : systemSpecs.columnManufacturer
  const chemistry =
    systemSpecs.columnChemistry === 'Other'
      ? systemSpecs.customChemistry?.trim() || 'Custom chemistry'
      : systemSpecs.columnChemistry
  const dimensions = [
    systemSpecs.columnLengthMm ? `${systemSpecs.columnLengthMm} mm` : null,
    systemSpecs.columnIdMm ? `${systemSpecs.columnIdMm} mm ID` : null,
    systemSpecs.particleSizeUm ? `${systemSpecs.particleSizeUm} um` : null
  ]
    .filter(Boolean)
    .join(' / ')
  const detectorSummary = systemSpecs.detectorTypes.length
    ? systemSpecs.detectorTypes.join(', ')
    : 'No detector selected'

  return [manufacturer, chemistry, dimensions, detectorSummary].filter(Boolean).join(' • ')
}

function sameArray(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index])
}

function isDefaultHardware(systemSpecs: SystemSpecs): boolean {
  return (
    systemSpecs.columnManufacturer === DEFAULT_SYSTEM.columnManufacturer &&
    (systemSpecs.customManufacturer || '') === DEFAULT_SYSTEM.customManufacturer &&
    systemSpecs.columnName === DEFAULT_SYSTEM.columnName &&
    systemSpecs.columnChemistry === DEFAULT_SYSTEM.columnChemistry &&
    (systemSpecs.customChemistry || '') === DEFAULT_SYSTEM.customChemistry &&
    systemSpecs.columnLengthMm === DEFAULT_SYSTEM.columnLengthMm &&
    systemSpecs.columnIdMm === DEFAULT_SYSTEM.columnIdMm &&
    systemSpecs.particleSizeUm === DEFAULT_SYSTEM.particleSizeUm &&
    sameArray(systemSpecs.availableSolvents, DEFAULT_SYSTEM.availableSolvents) &&
    sameArray(systemSpecs.detectorTypes, DEFAULT_SYSTEM.detectorTypes) &&
    sameArray(systemSpecs.instrumentModes || [], DEFAULT_SYSTEM.instrumentModes || []) &&
    systemSpecs.maxPressureBar === DEFAULT_SYSTEM.maxPressureBar
  )
}

export function buildConversationPlanSummary({
  target,
  effectiveTarget,
  recognition,
  source,
  systemSpecs,
  validationIssues,
  pendingClarification,
  phase
}: {
  target: DiscoveryTarget
  effectiveTarget: DiscoveryTarget
  recognition: PromptRecognitionSummary
  source: DiscoverySource
  systemSpecs: SystemSpecs
  validationIssues: Array<{ message: string; severity: 'error' | 'note' }>
  pendingClarification: Array<{ question: string }> | null
  phase: WorkflowPhase
}): ConversationPlanSummary {
  const requestText = target.requestText.trim()
  const matrixValue = formatMatrix(effectiveTarget)
  const impurities = effectiveTarget.impurities
    .map((compound) => compound.name?.trim() || compound.smiles.trim())
    .filter(Boolean)
  const recognizedAnalytes = recognition.analytes
    .filter((analyte) => analyte.status === 'recognized')
    .map((analyte) => analyte.resolvedName || analyte.value)
  const sourceValue =
    source === 'open_access' && recognition.sourceMode?.status === 'recognized'
      ? recognition.sourceMode.value
      : formatSourceMode(source)
  const analyteValue =
    effectiveTarget.analyteName.trim() ||
    effectiveTarget.targetResolvedName?.trim() ||
    (effectiveTarget.targetSmiles.trim() ? 'Target structure provided' : 'Missing')
  const analyteStatus: PlanFieldStatus = target.analyteName.trim()
    ? 'provided'
    : recognizedAnalytes.length || effectiveTarget.targetResolvedName?.trim() || effectiveTarget.targetSmiles.trim()
      ? 'recognized'
      : 'missing'

  const matrixStatus: PlanFieldStatus =
    target.matrix !== DEFAULT_TARGET.matrix || Boolean(target.customMatrix?.trim())
      ? 'provided'
      : recognition.matrix
        ? 'recognized'
        : 'inferred'

  const runtimeStatus: PlanFieldStatus =
    target.maxRunTimeMin != null
      ? 'provided'
      : recognition.runtime
        ? 'recognized'
        : 'inferred'

  const sourceStatus: PlanFieldStatus =
    source === 'local_corpus'
      ? 'provided'
      : recognition.sourceMode
        ? 'recognized'
        : 'inferred'

  const hardwareStatus: PlanFieldStatus = isDefaultHardware(systemSpecs) ? 'inferred' : 'provided'
  const unresolvedItems = [
    ...validationIssues.filter((issue) => issue.severity === 'error').map((issue) => issue.message),
    ...(pendingClarification || []).map((question) => question.question),
    ...recognition.unresolvedItems
  ].filter(Boolean) as string[]

  const inferredDefaults = [
    matrixStatus === 'inferred' ? matrixValue : null,
    runtimeStatus === 'inferred'
      ? effectiveTarget.maxRunTimeMin == null
        ? 'Uncapped runtime'
        : `${effectiveTarget.maxRunTimeMin} min runtime limit`
      : null,
    sourceStatus === 'inferred' ? sourceValue : null,
    hardwareStatus === 'inferred' ? 'Default hardware profile' : null
  ].filter(Boolean) as string[]

  const fields: PlanFieldSummary[] = [
    {
      id: 'analytes',
      label: 'Analyte or analytes',
      value:
        recognizedAnalytes.length > 1 && !target.analyteName.trim()
          ? recognizedAnalytes.join(', ')
          : analyteValue,
      status: analyteStatus
    },
    {
      id: 'matrix',
      label: 'Matrix',
      value: matrixValue,
      status: matrixStatus
    },
    {
      id: 'impurities',
      label: 'Secondary analytes',
      value: impurities.length ? impurities.join(', ') : 'None specified',
      status:
        target.impurities.length > 0
          ? 'provided'
          : impurities.length
            ? 'recognized'
            : 'inferred'
    },
    {
      id: 'runtime',
      label: 'Runtime limit',
      value:
        effectiveTarget.maxRunTimeMin == null
          ? 'Uncapped'
          : `${effectiveTarget.maxRunTimeMin} min target limit`,
      status: runtimeStatus
    },
    {
      id: 'sourceMode',
      label: 'Source mode',
      value: sourceValue,
      status: sourceStatus
    },
    {
      id: 'hardware',
      label: 'Hardware summary',
      value: formatHardware(systemSpecs),
      status: hardwareStatus
    },
    {
      id: 'unresolved',
      label: 'Unresolved items',
      value: unresolvedItems.length ? unresolvedItems.join(' • ') : 'No blocking issues',
      status: unresolvedItems.length ? 'missing' : 'recognized'
    },
    {
      id: 'defaults',
      label: 'Inferred defaults',
      value: inferredDefaults.length ? inferredDefaults.join(' • ') : 'None',
      status: inferredDefaults.length ? 'inferred' : 'recognized'
    }
  ]

  const recognitionSummary = requestText
    ? [
        recognizedAnalytes.length
          ? `I recognized ${recognizedAnalytes.join(', ')} from the prompt.`
          : analyteStatus === 'missing'
            ? 'I have not confidently recognized an analyte yet.'
            : `I am carrying forward ${analyteValue}.`,
        `Matrix: ${matrixValue}.`,
        `Source mode: ${sourceValue}.`
      ].join(' ')
    : 'I am waiting for a request before I assemble the implementation plan.'
  const readinessSummary = (() => {
    if (phase === 'discovering') return 'Run in progress.'
    if (phase === 'recognition_verify') return 'Please verify the detected inputs.'
    if (phase === 'planning') return 'Implementation plan ready for review.'
    return unresolvedItems.length
      ? 'Clarify or resolve the remaining gaps before confirming the run.'
      : 'The run draft is ready for explicit confirmation.'
  })()

  return {
    fields,
    inferredDefaults,
    unresolvedItems,
    recognitionSummary,
    readinessSummary
  }
}
