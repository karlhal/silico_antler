import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type SetStateAction
} from 'react'
import {
  AgentDesktopRuntimeConfig,
  AgentResultOrigin,
  AgentRuntimeMode,
  AgentStartupHealth,
  CachedAgentRunSnapshot,
  ClarificationQuestion,
  Compound,
  DiscoveryTarget,
  DiscoverySource,
  PromptRecognitionSummary,
  MethodRecommendationReport,
  RecommendationJobStatus,
  RecommendationReportMeta,
  RecommendationRuntimeSummary,
  Recommendation,
  ResearchStep,
  SystemSpecs,
  WorkflowPhase
} from '../types'
import { ApiError, api, buildRecommendationPayload } from '../lib/api'
import {
  buildEmptyPromptRecognition,
  detectPromptRecognition,
  updateRecognizedAnalyte
} from '../lib/promptRecognition'
import {
  buildAgentRunRequestHash,
  getCachedAgentRunSnapshot,
  listCachedAgentRunSnapshots,
  saveCachedAgentRunSnapshot
} from '../lib/agentRunCache'

type EditablePhase = 'system_setup' | 'target_setup' | 'source_selection'
type ExtendedPhase = WorkflowPhase | 'failed'
type ValidationSeverity = 'error' | 'note'

interface ValidationIssue {
  id: string
  field: string
  stage: EditablePhase
  severity: ValidationSeverity
  message: string
}

interface RunOutcome {
  kind:
    | 'validation'
    | 'empty'
    | 'backend_error'
    | 'timeout'
    | 'interrupted'
    | 'cached_result'
    | 'demo_safe_result'
  title: string
  message: string
  details: string[]
}

interface WorkflowNotice {
  title: string
  message: string
}

interface WorkflowSessionSnapshot {
  version: 1
  phase: ExtendedPhase
  systemSpecs: SystemSpecs
  target: DiscoveryTarget
  source: DiscoverySource
  recommendations: Recommendation[]
  reportMeta: RecommendationReportMeta | null
  activeRecommendationId: string | null
  runtimeMode: AgentRuntimeMode | null
  resultOrigin: AgentResultOrigin | null
  runOutcome: RunOutcome | null
  validationIssues: ValidationIssue[]
  staleReportNotice: string | null
}

interface InitialWorkflowState {
  phase: ExtendedPhase
  systemSpecs: SystemSpecs
  target: DiscoveryTarget
  source: DiscoverySource
  recommendations: Recommendation[]
  reportMeta: RecommendationReportMeta | null
  activeRecommendationId: string | null
  runtimeMode: AgentRuntimeMode | null
  resultOrigin: AgentResultOrigin | null
  runOutcome: RunOutcome | null
  validationIssues: ValidationIssue[]
  staleReportNotice: string | null
  restoreNotice: WorkflowNotice | null
  steps: ResearchStep[]
}

interface UseAgentWorkflowOptions {
  runtimeConfig: AgentDesktopRuntimeConfig
  startupHealth: AgentStartupHealth | null
}

interface RecentRunSummary {
  requestHash: string
  createdAt: string
  createdAtLabel: string
  title: string
  subtitle: string
  sourceMode: MethodRecommendationReport['source_mode']
  candidateCount: number
  origin: AgentResultOrigin
}

const SESSION_STORAGE_KEY = 'silico.agent.workflow.v1'
const JOB_POLL_INTERVAL_MS = 1000
const JOB_PROGRESS_STALE_MS = 30000
const SHOWCASE_HANDOFF_QUERY_KEYS = [
  'origin',
  'cta',
  'source',
  'context'
] as const

let pendingShowcaseHandoffState: ShowcaseHandoffState | null = null

interface ShowcaseHandoffState {
  target: DiscoveryTarget
  source: DiscoverySource
  restoreNotice: WorkflowNotice
}

const BASE_STEPS: ResearchStep[] = [
  { id: 'query-papers', label: 'Querying open-access literature', status: 'pending' },
  { id: 'extract-methods', label: 'Extracting candidate method parameters', status: 'pending' },
  { id: 'match-system', label: 'Matching to your instrument constraints', status: 'pending' },
  { id: 'scale-physics', label: 'Applying physics-based column scaling', status: 'pending' },
  { id: 'final-rank', label: 'Ranking by target selectivity fit', status: 'pending' }
]

const KNOWN_MANUFACTURERS = new Set(['Agilent', 'Waters', 'Shimadzu', 'Thermo Fisher', 'YMC'])
const KNOWN_CHEMISTRIES = new Set(['C18', 'C8', 'Phenyl', 'HILIC', 'Silica'])
const KNOWN_MATRICES = new Set(['Human Plasma', 'Bovine Serum', 'Water', 'Solvent'])

function createDefaultSystemSpecs(): SystemSpecs {
  return {
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
}

function createDefaultTarget(): DiscoveryTarget {
  return {
    requestText: '',
    analyteName: '',
    targetSmiles: '',
    targetResolvedName: null,
    targetLookupSource: null,
    targetLookupError: null,
    targetResolving: false,
    impurities: [],
    matrix: 'Human Plasma',
    customMatrix: '',
    requireMS: false,
    maxRunTimeMin: null
  }
}

function createRecognizedCompound(id: string, smiles: string, name: string | null): Compound {
  return {
    id,
    smiles,
    name,
    resolved: Boolean(name),
    resolving: false,
    lookupSource: 'prompt_recognition',
    lookupError: null
  }
}

function buildEffectiveTarget(
  target: DiscoveryTarget,
  recognition: PromptRecognitionSummary
): DiscoveryTarget {
  const recognizedTarget = recognition.analytes.find((analyte) => analyte.status === 'recognized')
  const recognizedImpurities = recognition.analytes.filter(
    (analyte) => analyte.status === 'recognized' && analyte.id !== recognizedTarget?.id
  )

  const recognizedMatrix = recognition.matrix?.status === 'recognized' ? recognition.matrix.value : null
  const recognizedRuntime =
    recognition.runtime?.status === 'recognized'
      ? parseFloat(recognition.runtime.value)
      : null
  const recognizedRequireMS =
    recognition.detector?.status === 'recognized'
      ? /ms/i.test(recognition.detector.value)
      : false

  const matrixShouldOverlay =
    (!target.customMatrix?.trim() && target.matrix === 'Human Plasma' && Boolean(recognizedMatrix))

  return {
    ...target,
    analyteName: target.analyteName.trim() || recognizedTarget?.resolvedName || recognizedTarget?.value || '',
    targetSmiles: target.targetSmiles.trim() || recognizedTarget?.resolvedSmiles || '',
    targetResolvedName:
      target.targetResolvedName || recognizedTarget?.resolvedName || null,
    targetLookupSource:
      target.targetLookupSource || recognizedTarget?.lookupSource || null,
    targetLookupError:
      target.targetLookupError || recognizedTarget?.lookupError || null,
    impurities:
      target.impurities.length > 0
        ? target.impurities
        : recognizedImpurities
            .filter((analyte) => analyte.resolvedSmiles)
            .map((analyte) =>
              createRecognizedCompound(
                `recognized-${analyte.id}`,
                analyte.resolvedSmiles || '',
                analyte.resolvedName || analyte.value
              )
            ),
    matrix: matrixShouldOverlay && recognizedMatrix ? recognizedMatrix : target.matrix,
    customMatrix: matrixShouldOverlay ? '' : target.customMatrix,
    requireMS: target.requireMS || recognizedRequireMS,
    maxRunTimeMin:
      target.maxRunTimeMin == null && recognizedRuntime != null
        ? recognizedRuntime
        : target.maxRunTimeMin
  }
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function sanitizeQueryText(value: string | null, maxLength: number): string | null {
  if (!value) {
    return null
  }

  const trimmed = value.trim().replace(/\s+/g, ' ')
  if (!trimmed) {
    return null
  }

  return trimmed.slice(0, maxLength)
}

function clearShowcaseHandoffFromUrl() {
  if (typeof window === 'undefined' || typeof window.history?.replaceState !== 'function') {
    return
  }

  const url = new URL(window.location.href)
  SHOWCASE_HANDOFF_QUERY_KEYS.forEach((key) => {
    url.searchParams.delete(key)
  })

  const nextSearch = url.searchParams.toString()
  const nextUrl = `${url.pathname}${nextSearch ? `?${nextSearch}` : ''}${url.hash}`
  window.history.replaceState(window.history.state, '', nextUrl)
}

function readShowcaseHandoffState(): ShowcaseHandoffState | null {
  if (pendingShowcaseHandoffState) {
    const state = pendingShowcaseHandoffState
    pendingShowcaseHandoffState = null
    return state
  }

  if (typeof window === 'undefined') {
    return null
  }

  const params = new URLSearchParams(window.location.search)
  if (params.get('origin') !== 'showcase') {
    return null
  }

  const sourceParam = params.get('source')
  const source: DiscoverySource =
    sourceParam === 'local_corpus' || sourceParam === 'open_access'
      ? sourceParam
      : 'open_access'

  const ctaLocation = sanitizeQueryText(params.get('cta'), 80)
  const context = sanitizeQueryText(params.get('context'), 120)

  const handoffState: ShowcaseHandoffState = {
    target: {
      ...createDefaultTarget()
    },
    source,
    restoreNotice: {
      title: 'Showcase context loaded',
      message: [
        'You came from the interactive showcase.',
        context ? `Source context: ${context}.` : null,
        ctaLocation ? `Entry point: ${ctaLocation}.` : null,
        'The showcase uses deterministic demo data and does not provide real analyte inputs.',
        'Enter a real analyte, SMILES, or separation goal before running live discovery.'
      ]
        .filter(Boolean)
        .join(' ')
    }
  }

  pendingShowcaseHandoffState = handoffState
  clearShowcaseHandoffFromUrl()

  return handoffState
}

function cloneSystemSpecs(systemSpecs: SystemSpecs): SystemSpecs {
  return {
    ...systemSpecs,
    availableSolvents: [...systemSpecs.availableSolvents],
    detectorTypes: [...systemSpecs.detectorTypes],
    instrumentModes: [...(systemSpecs.instrumentModes || [])]
  }
}

function cloneTarget(target: DiscoveryTarget): DiscoveryTarget {
  return {
    ...target,
    targetResolving: false,
    impurities: target.impurities.map((compound) => ({
      ...compound,
      resolving: false
    }))
  }
}

function cloneReportMeta(
  reportMeta: RecommendationReportMeta | null
): RecommendationReportMeta | null {
  if (!reportMeta) {
    return null
  }

  return {
    ...reportMeta,
    target_compound_context: reportMeta.target_compound_context
      ? { ...reportMeta.target_compound_context }
      : null,
    impurity_compound_contexts: [...(reportMeta.impurity_compound_contexts || [])],
    external_evidence_trace: reportMeta.external_evidence_trace
      ? { ...reportMeta.external_evidence_trace }
      : null,
    skipped_papers: [...reportMeta.skipped_papers],
    runtime: reportMeta.runtime ? { ...reportMeta.runtime } : null
  }
}

function buildReportMeta(
  source: DiscoverySource,
  report: MethodRecommendationReport | null
): RecommendationReportMeta {
  return {
    source_mode: report?.source_mode || source,
    search_query_used: report?.search_query_used || null,
    target_compound_context: report?.target_compound_context || null,
    impurity_compound_contexts: report?.impurity_compound_contexts || [],
    external_evidence_trace: report?.external_evidence_trace || null,
    skipped_papers: [
      ...(
        report?.discovery_summary?.skipped_papers_preview ||
        report?.skipped_papers ||
        []
      )
    ],
    discovered_paper_count:
      report?.discovery_summary?.discovered_paper_count ??
      report?.discovered_papers?.length ??
      0,
    skipped_paper_count:
      report?.discovery_summary?.skipped_paper_count ??
      report?.skipped_papers?.length ??
      0,
    skipped_papers_truncated: report?.discovery_summary?.skipped_papers_truncated ?? false,
    considered_candidate_count:
      report?.discovery_summary?.considered_candidate_count ??
      report?.considered_candidates?.length ??
      0,
    considered_candidates_truncated:
      report?.discovery_summary?.considered_candidates_truncated ?? false,
    repeated_extraction_exception_count:
      report?.discovery_summary?.repeated_extraction_exception_count ?? 0,
    runtime: report?.runtime || null
  }
}

function buildRecommendationRequestSnapshot(
  target: DiscoveryTarget,
  systemSpecs: SystemSpecs,
  source: DiscoverySource,
  runtimeConfig: AgentDesktopRuntimeConfig
): Record<string, unknown> {
  return {
    recommendation_request: buildRecommendationPayload(target, systemSpecs, source),
    runtime_config: {
      cache_policy: runtimeConfig.cachePolicy,
      demo_snapshot_version: runtimeConfig.demoSnapshotVersion
    }
  }
}

function deriveResultOrigin(report: MethodRecommendationReport | null): AgentResultOrigin {
  return report?.runtime?.degraded ? 'live_degraded' : 'live'
}

function formatSnapshotCreatedAt(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(parsed)
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function readStringField(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function readNumberField(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function readBooleanField(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function normalizeSourceMode(value: unknown): MethodRecommendationReport['source_mode'] {
  return value === 'local_corpus' || value === 'open_access' || value === 'local_files'
    ? value
    : 'open_access'
}

function restoreSystemSpecsFromCachedSnapshot(snapshot: CachedAgentRunSnapshot): SystemSpecs {
  const requestPayload = isObjectRecord(snapshot.request.recommendation_request)
    ? snapshot.request.recommendation_request
    : null
  const systemSpecs = isObjectRecord(requestPayload?.system_specs) ? requestPayload.system_specs : null
  const manufacturer = readStringField(systemSpecs?.column_manufacturer)
  const chemistry = readStringField(systemSpecs?.column_chemistry)

  return {
    columnManufacturer: manufacturer && KNOWN_MANUFACTURERS.has(manufacturer) ? manufacturer : 'Other',
    customManufacturer:
      manufacturer && !KNOWN_MANUFACTURERS.has(manufacturer) ? manufacturer : '',
    columnName: readStringField(systemSpecs?.column_name) || '',
    columnChemistry: chemistry && KNOWN_CHEMISTRIES.has(chemistry) ? chemistry : 'Other',
    customChemistry: chemistry && !KNOWN_CHEMISTRIES.has(chemistry) ? chemistry : '',
    columnLengthMm: readNumberField(systemSpecs?.column_length_mm),
    columnIdMm: readNumberField(systemSpecs?.column_inner_diameter_mm),
    particleSizeUm: readNumberField(systemSpecs?.particle_size_um),
    availableSolvents: Array.isArray(systemSpecs?.available_solvents)
      ? systemSpecs.available_solvents.filter(
          (value): value is string => typeof value === 'string' && value.trim().length > 0
        )
      : [],
    detectorTypes: Array.isArray(systemSpecs?.detector_types)
      ? systemSpecs.detector_types.filter(
          (value): value is string => typeof value === 'string' && value.trim().length > 0
        )
      : [],
    instrumentModes: Array.isArray(systemSpecs?.instrument_modes)
      ? systemSpecs.instrument_modes.filter(
          (value): value is string => typeof value === 'string' && value.trim().length > 0
        )
      : [],
    maxPressureBar: readNumberField(systemSpecs?.max_pressure_bar)
  }
}

function restoreTargetFromCachedSnapshot(snapshot: CachedAgentRunSnapshot): DiscoveryTarget {
  const requestPayload = isObjectRecord(snapshot.request.recommendation_request)
    ? snapshot.request.recommendation_request
    : null
  const matrixHint = readStringField(requestPayload?.matrix_hint)

  return {
    requestText: readStringField(requestPayload?.request_text) || '',
    analyteName: readStringField(requestPayload?.analyte_name) || '',
    targetSmiles: readStringField(requestPayload?.target_smiles) || '',
    targetResolvedName: null,
    targetLookupSource: null,
    targetLookupError: null,
    targetResolving: false,
    impurities: Array.isArray(requestPayload?.impurity_smiles)
      ? requestPayload.impurity_smiles
          .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
          .map((smiles) => createCompound(smiles))
      : [],
    matrix: matrixHint && KNOWN_MATRICES.has(matrixHint) ? matrixHint : matrixHint ? 'Other' : 'Human Plasma',
    customMatrix: matrixHint && !KNOWN_MATRICES.has(matrixHint) ? matrixHint : '',
    requireMS: readBooleanField(requestPayload?.require_mass_spectrometry),
    maxRunTimeMin: readNumberField(requestPayload?.max_run_time_min)
  }
}

function restoreSourceFromCachedSnapshot(snapshot: CachedAgentRunSnapshot): DiscoverySource {
  const requestPayload = isObjectRecord(snapshot.request.recommendation_request)
    ? snapshot.request.recommendation_request
    : null
  const sourceMode = normalizeSourceMode(requestPayload?.source_mode ?? snapshot.report.source_mode)
  return sourceMode === 'local_corpus' ? 'local_corpus' : 'open_access'
}

function buildRecentRunSummary(snapshot: CachedAgentRunSnapshot): RecentRunSummary {
  const requestPayload = isObjectRecord(snapshot.request.recommendation_request)
    ? snapshot.request.recommendation_request
    : null
  const analyteName = readStringField(requestPayload?.analyte_name)
  const requestText = readStringField(requestPayload?.request_text)
  const sourceMode = normalizeSourceMode(requestPayload?.source_mode ?? snapshot.report.source_mode)
  const candidateCount = snapshot.report.considered_candidates.length
  const discoveredCount = snapshot.report.discovered_papers.length

  return {
    requestHash: snapshot.requestHash,
    createdAt: snapshot.createdAt,
    createdAtLabel: formatSnapshotCreatedAt(snapshot.createdAt),
    title: analyteName || requestText || 'Cached recommendation run',
    subtitle:
      requestText && analyteName && requestText !== analyteName
        ? requestText
        : sourceMode === 'open_access'
          ? `${candidateCount} candidates • ${discoveredCount} papers screened`
          : `${candidateCount} candidates • local corpus retrieval`,
    sourceMode,
    candidateCount,
    origin: snapshot.origin
  }
}

function isDefaultSystemSpecs(systemSpecs: SystemSpecs): boolean {
  return JSON.stringify(cloneSystemSpecs(systemSpecs)) === JSON.stringify(createDefaultSystemSpecs())
}

function isDefaultTarget(target: DiscoveryTarget): boolean {
  return JSON.stringify(cloneTarget(target)) === JSON.stringify(createDefaultTarget())
}

function buildInitialSteps(source: DiscoverySource): ResearchStep[] {
  return BASE_STEPS.map((step) =>
    step.id === 'query-papers'
      ? {
          ...step,
          label:
            source === 'local_corpus'
              ? 'Querying curated local corpus'
              : 'Querying open-access literature'
        }
      : { ...step }
  )
}

function buildStepProgress(
  source: DiscoverySource,
  activeIndex: number | null,
  errorIndex?: number | null,
  activeDetail?: string | null
): ResearchStep[] {
  return buildInitialSteps(source).map((step, index) => {
    if (errorIndex === index) {
      return { ...step, status: 'error' }
    }
    if (activeIndex === null || index < activeIndex) {
      return { ...step, status: 'completed' }
    }
    if (index === activeIndex) {
      return { ...step, status: 'active', detail: activeDetail || undefined }
    }
    return { ...step, status: 'pending' }
  })
}

function delay(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

const DISCOVERY_STAGE_FLOOR_MS = 2000
const DISCOVERY_PACED_STAGE_INDEXES = [1, 2, 3, 4] as const

async function playMinimumDiscoveryPacing(
  source: DiscoverySource,
  runStartedAt: number,
  setSteps: (steps: ResearchStep[]) => void,
  startStageIndex = 1
) {
  const stageIndexes = DISCOVERY_PACED_STAGE_INDEXES.filter(
    (stageIndex) => stageIndex >= startStageIndex
  )
  if (!stageIndexes.length) {
    return
  }

  const minimumTotalMs =
    DISCOVERY_PACED_STAGE_INDEXES.length * DISCOVERY_STAGE_FLOOR_MS
  const elapsed = Date.now() - runStartedAt
  const remaining = Math.max(0, minimumTotalMs - elapsed)
  if (remaining <= 0) {
    return
  }

  const stageDelay = Math.ceil(remaining / stageIndexes.length)
  for (const activeIndex of stageIndexes) {
    setSteps(buildStepProgress(source, activeIndex))
    await delay(stageDelay)
  }
}

function formatJobProgressDetail(status: RecommendationJobStatus): string {
  if (typeof status.items_total === 'number' && status.items_total > 0) {
    const completed = Math.min(status.items_completed, status.items_total)
    if (status.stage === 'query_papers') {
      return `${status.message} (query ${completed} of ${status.items_total})`
    }
    if (status.stage === 'extract_methods') {
      return `${status.message} (paper ${completed} of ${status.items_total})`
    }
    return `${status.message} (${completed}/${status.items_total})`
  }
  return status.message
}

function buildStepsFromJobStatus(
  source: DiscoverySource,
  status: RecommendationJobStatus
): ResearchStep[] {
  const detail = formatJobProgressDetail(status)
  switch (status.stage) {
    case 'queued':
    case 'query_papers':
      return buildStepProgress(source, 0, undefined, detail)
    case 'extract_methods':
      return buildStepProgress(source, 1, undefined, detail)
    case 'match_system':
      return buildStepProgress(source, 2, undefined, detail)
    case 'scale_physics':
      return buildStepProgress(source, 3, undefined, detail)
    case 'final_rank':
      return buildStepProgress(source, 4, undefined, detail)
    case 'completed':
      return buildStepProgress(source, null)
    case 'failed':
      return buildStepProgress(source, 1, 1, detail)
    default:
      return buildInitialSteps(source)
  }
}

function createCompoundId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `compound-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function createCompound(smiles = '', name: string | null = null): Compound {
  return {
    id: createCompoundId(),
    smiles,
    name,
    resolved: Boolean(name),
    resolving: false,
    lookupSource: name ? 'demo' : null,
    lookupError: null
  }
}

function buildValidationIssues(
  target: DiscoveryTarget,
  systemSpecs: SystemSpecs,
  source: DiscoverySource
): ValidationIssue[] {
  const issues: ValidationIssue[] = []

  if (
    !target.requestText.trim() &&
    !target.analyteName.trim() &&
    !target.targetSmiles.trim()
  ) {
    issues.push({
      id: 'target-required',
      field: 'requestText',
      stage: 'target_setup',
      severity: 'error',
      message: 'Provide a request, analyte name, or target SMILES before running discovery.'
    })
  } else {
    if (!target.requestText.trim()) {
      issues.push({
        id: 'request-context',
        field: 'requestText',
        stage: 'target_setup',
        severity: 'note',
        message: 'Optional: a short natural-language request gives the run better scientific context.'
      })
    }

    if (!target.analyteName.trim() && !target.targetResolvedName) {
      issues.push({
        id: 'analyte-context',
        field: 'analyteName',
        stage: 'target_setup',
        severity: 'note',
        message: 'Optional: naming the analyte makes the report easier to scan after reruns.'
      })
    }
  }

  if (
    systemSpecs.columnManufacturer === 'Other' &&
    !systemSpecs.customManufacturer?.trim()
  ) {
    issues.push({
      id: 'custom-manufacturer',
      field: 'customManufacturer',
      stage: 'system_setup',
      severity: 'error',
      message: 'Add a custom column manufacturer before running discovery.'
    })
  }

  if (
    systemSpecs.columnChemistry === 'Other' &&
    !systemSpecs.customChemistry?.trim()
  ) {
    issues.push({
      id: 'custom-chemistry',
      field: 'customChemistry',
      stage: 'system_setup',
      severity: 'error',
      message: 'Add a custom stationary phase before running discovery.'
    })
  }

  if (!systemSpecs.availableSolvents.length) {
    issues.push({
      id: 'solvent-guidance',
      field: 'availableSolvents',
      stage: 'system_setup',
      severity: 'note',
      message: 'Optional: selecting at least one solvent narrows the recommended method space.'
    })
  }

  if (!systemSpecs.detectorTypes.length) {
    issues.push({
      id: 'detector-guidance',
      field: 'detectorTypes',
      stage: 'system_setup',
      severity: 'note',
      message: 'Optional: selecting at least one detector clarifies what the instrument can validate.'
    })
  }

  if (target.matrix === 'Other' && !target.customMatrix?.trim()) {
    issues.push({
      id: 'custom-matrix',
      field: 'customMatrix',
      stage: 'target_setup',
      severity: 'error',
      message: 'Add a custom sample matrix before running discovery.'
    })
  }

  if (target.impurities.some((compound) => !compound.smiles.trim())) {
    issues.push({
      id: 'empty-impurity',
      field: 'impurities',
      stage: 'target_setup',
      severity: 'error',
      message: 'Remove empty impurity rows or enter a SMILES for each impurity.'
    })
  }

  if (source === 'local_corpus' && !target.targetSmiles.trim()) {
    issues.push({
      id: 'local-corpus-smiles',
      field: 'targetSmiles',
      stage: 'target_setup',
      severity: 'error',
      message:
        'Local Corpus search requires a target SMILES. Add one above or switch to Open Access.'
    })
  } else if (source === 'open_access' && !target.targetSmiles.trim()) {
    issues.push({
      id: 'open-access-smiles-guidance',
      field: 'targetSmiles',
      stage: 'target_setup',
      severity: 'note',
      message: 'Optional: target SMILES improves structure-aware matching and comparison.'
    })
  }

  return issues
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (
    error instanceof ApiError &&
    error.detail &&
    typeof error.detail === 'object' &&
    'message' in error.detail &&
    typeof error.detail.message === 'string'
  ) {
    return error.detail.message
  }
  return error instanceof Error && error.message ? error.message : fallback
}

function formatSkippedPaperReason(reason: string): string {
  return reason.replace(/\s+/g, ' ').trim()
}

function buildOpenAccessFailureDetails(report: MethodRecommendationReport): string[] {
  const stagePriority: Record<'screening' | 'fetch' | 'extraction', number> = {
    extraction: 0,
    fetch: 1,
    screening: 2
  }
  const uniqueReasons = new Set<string>()
  const prioritizedSkips = [...(report.skipped_papers || [])].sort(
    (left, right) => stagePriority[left.stage] - stagePriority[right.stage]
  )

  for (const skippedPaper of prioritizedSkips) {
    const reason = formatSkippedPaperReason(skippedPaper.reason)
    if (!reason) {
      continue
    }

    uniqueReasons.add(
      `${skippedPaper.stage.toUpperCase()}: ${skippedPaper.title} — ${reason}`
    )

    if (uniqueReasons.size >= 4) {
      break
    }
  }

  return Array.from(uniqueReasons)
}

function buildValidationOutcome(issues: ValidationIssue[]): RunOutcome {
  const blockingIssues = issues.filter((issue) => issue.severity === 'error')
  return {
    kind: 'validation',
    title: 'Review the highlighted inputs',
    message:
      blockingIssues[0]?.message ||
      'Complete the required inputs before running discovery.',
    details: blockingIssues.map((issue) => issue.message)
  }
}

function buildEmptyOutcome(
  source: DiscoverySource,
  report: MethodRecommendationReport | null,
  runtimeMode: string | null = null
): RunOutcome {
  if (runtimeMode === 'demo_safe' || report?.runtime?.status === 'completed_with_demo_fallback') {
    return {
      kind: 'empty',
      title: 'No mock data available for this query',
      message: 'The interactive showcase only provides mock data for specific scenarios. Try using the default demo molecule or switch to live mode.',
      details: []
    }
  }

  if (report && source === 'open_access') {
    const runtimeStatus = report.runtime?.status || null
    const discovered = report.discovery_summary?.discovered_paper_count ?? report.discovered_papers?.length ?? 0
    const considered = report.discovery_summary?.considered_candidate_count ?? report.considered_candidates?.length ?? 0

    if (runtimeStatus === 'no_trustworthy_candidates') {
      if (discovered === 0) {
        return {
          kind: 'empty',
          title: 'No open-access papers matched this query',
          message: 'Inputs were preserved. Tighten the target description, add a target SMILES, or try a different evidence source.',
          details: []
        }
      }

      if (discovered > 0 && considered === 0) {
        return {
          kind: 'empty',
          title: `Found ${discovered} papers, but extraction failed`,
          message: 'The papers found did not contain sufficient, high-quality analytical method details for extraction.',
          details: buildOpenAccessFailureDetails(report)
        }
      }

      return {
        kind: 'empty',
        title: 'Methods extracted, but viability checks failed',
        message: 'Methods were isolated but failed safety boundaries, pressure limits, or core chemical compatibility checks.',
        details: []
      }
    }
    return {
      kind: 'empty',
      title: 'Discovery finished without a recommendation',
      message:
        report.runtime?.summary ||
        'The search found papers, but none produced a trustworthy method candidate for the current constraints.',
      details: buildOpenAccessFailureDetails(report)
    }
  }

  if (source === 'local_corpus') {
    return {
      kind: 'empty',
      title: 'No local corpus methods matched this target',
      message:
        'Try a different target SMILES, add impurities, or switch to Open Access to broaden retrieval.',
      details: []
    }
  }

  return {
    kind: 'empty',
    title: 'The current run returned no recommendations',
    message: 'Inputs were preserved so you can adjust them and rerun without resetting.',
    details: []
  }
}

function buildFailureOutcome(error: unknown): RunOutcome {
  const fallbackMessage = 'The discovery service could not complete this run.'
  const errorMessage = getApiErrorMessage(error, fallbackMessage)
  const runtimeStatus =
    error instanceof ApiError &&
    error.detail &&
    typeof error.detail === 'object' &&
    'runtime_status' in error.detail &&
    typeof error.detail.runtime_status === 'string'
      ? error.detail.runtime_status
      : null

  if (error instanceof ApiError && error.status === 408) {
    return {
      kind: 'timeout',
      title: 'Discovery request timed out',
      message:
        'The service did not finish in time. Inputs were preserved so you can retry or switch source.',
      details: [errorMessage]
    }
  }

  if (runtimeStatus === 'upstream_unavailable') {
    return {
      kind: 'backend_error',
      title: 'Live discovery is unavailable',
      message:
        'The method-development service could not complete the live run. Inputs were preserved so you can retry or switch source.',
      details: [errorMessage]
    }
  }

  return {
    kind: 'backend_error',
    title: 'Discovery service failed',
    message:
      'The request could not be completed. Inputs were preserved so you can revise and rerun without starting over.',
    details: [errorMessage]
  }
}

function buildCachedResultOutcome(snapshot: CachedAgentRunSnapshot): RunOutcome {
  return {
    kind: 'cached_result',
    title: 'Showing cached result',
    message:
      'Live discovery was unavailable, so the report below was restored from the latest matching successful run stored on this device.',
    details: [
      `Cached at ${formatSnapshotCreatedAt(snapshot.createdAt)}.`,
      snapshot.origin === 'live_degraded'
        ? 'The original live run completed in a degraded state, so cached diagnostics may include degradation details.'
        : 'Use Retry live to refresh this request against the hosted method-development service.'
    ]
  }
}

function formatRuntimeStatusLabel(runtime: RecommendationRuntimeSummary | null): string | null {
  if (!runtime) {
    return null
  }

  switch (runtime.status) {
    case 'completed':
      return 'Runtime completed'
    case 'completed_with_degraded_source':
      return 'Runtime degraded'
    case 'no_trustworthy_candidates':
      return 'No trustworthy candidates'
    case 'upstream_unavailable':
      return 'Runtime unavailable'
    case 'request_invalid':
      return 'Request invalid'
    case 'completed_with_demo_fallback':
      return 'Demo-safe result'
    default:
      return null
  }
}

function normalizeStoredRunOutcome(value: unknown): RunOutcome | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  const parsed = value as Record<string, unknown>
  const rawKind = typeof parsed.kind === 'string' ? parsed.kind : undefined
  const kind = rawKind === 'demo_fallback' ? undefined : rawKind

  if (
    kind !== 'validation' &&
    kind !== 'empty' &&
    kind !== 'backend_error' &&
    kind !== 'timeout' &&
    kind !== 'interrupted' &&
    kind !== 'cached_result'
  ) {
    return null
  }

  return {
    kind,
    title: typeof parsed.title === 'string' ? parsed.title : 'Workflow notice',
    message: typeof parsed.message === 'string' ? parsed.message : '',
    details: Array.isArray(parsed.details)
      ? parsed.details.filter((detail): detail is string => typeof detail === 'string')
      : []
  }
}

function normalizeStoredRuntimeMode(value: unknown): AgentRuntimeMode | null {
  if (value === 'live' || value === 'cached') {
    return value
  }

  return null
}

function normalizeStoredResultOrigin(value: unknown): AgentResultOrigin | null {
  if (
    value === 'live' ||
    value === 'cached' ||
    value === 'live_degraded'
  ) {
    return value
  }

  return null
}

function readStoredSnapshot(): WorkflowSessionSnapshot | null {
  if (!isBrowser()) {
    return null
  }

  try {
    const rawValue = window.localStorage.getItem(SESSION_STORAGE_KEY)
    if (!rawValue) {
      return null
    }

    const parsed = JSON.parse(rawValue) as Partial<WorkflowSessionSnapshot>
    if (
      parsed.version !== 1 ||
      !parsed.systemSpecs ||
      !parsed.target ||
      !parsed.source
    ) {
      return null
    }

    const rawRuntimeMode =
      'runtimeMode' in parsed
        ? parsed.runtimeMode
        : (parsed as Record<string, unknown>).discoveryMode
    const rawResultOrigin =
      'resultOrigin' in parsed
        ? parsed.resultOrigin
        : (parsed as Record<string, unknown>).discoveryMode
    if (
      rawRuntimeMode === 'demo_safe' ||
      rawRuntimeMode === 'demo' ||
      rawResultOrigin === 'demo_safe' ||
      rawResultOrigin === 'demo'
    ) {
      return null
    }

    return {
      version: 1,
      phase:
        parsed.phase === 'system_setup' ||
        parsed.phase === 'target_setup' ||
        parsed.phase === 'source_selection' ||
        parsed.phase === 'recognition_verify' ||
        parsed.phase === 'planning' ||
        parsed.phase === 'discovering' ||
        parsed.phase === 'completed' ||
        parsed.phase === 'failed'
          ? parsed.phase
          : 'system_setup',
      systemSpecs: cloneSystemSpecs(parsed.systemSpecs as SystemSpecs),
      target: cloneTarget(parsed.target as DiscoveryTarget),
      source:
        parsed.source === 'local_corpus' || parsed.source === 'open_access'
          ? parsed.source
          : 'open_access',
      recommendations: Array.isArray(parsed.recommendations)
        ? (parsed.recommendations as Recommendation[])
        : [],
      reportMeta: parsed.reportMeta
        ? cloneReportMeta(parsed.reportMeta as RecommendationReportMeta)
        : null,
      activeRecommendationId:
        typeof parsed.activeRecommendationId === 'string' || parsed.activeRecommendationId === null
          ? parsed.activeRecommendationId
          : null,
      runtimeMode: normalizeStoredRuntimeMode(rawRuntimeMode),
      resultOrigin: normalizeStoredResultOrigin(rawResultOrigin),
      runOutcome: normalizeStoredRunOutcome(parsed.runOutcome),
      validationIssues: Array.isArray(parsed.validationIssues)
        ? (parsed.validationIssues as ValidationIssue[])
        : [],
      staleReportNotice:
        typeof parsed.staleReportNotice === 'string' ? parsed.staleReportNotice : null
    }
  } catch {
    return null
  }
}

function writeStoredSnapshot(snapshot: WorkflowSessionSnapshot) {
  if (!isBrowser()) {
    return
  }

  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(snapshot))
}

function clearStoredSnapshot() {
  if (!isBrowser()) {
    return
  }

  window.localStorage.removeItem(SESSION_STORAGE_KEY)
}

function buildInitialWorkflowState(): InitialWorkflowState {
  const fallbackSource: DiscoverySource = 'open_access'
  const fallbackRecommendations: Recommendation[] = []
  const fallbackActiveRecommendationId = null
  const showcaseHandoff = readShowcaseHandoffState()

  if (showcaseHandoff) {
    return {
      phase: 'target_setup',
      systemSpecs: createDefaultSystemSpecs(),
      target: showcaseHandoff.target,
      source: showcaseHandoff.source,
      recommendations: fallbackRecommendations,
      reportMeta: null,
      activeRecommendationId: fallbackActiveRecommendationId,
      runtimeMode: null,
      resultOrigin: null,
      runOutcome: null,
      validationIssues: [],
      staleReportNotice: null,
      restoreNotice: showcaseHandoff.restoreNotice,
      steps: buildInitialSteps(showcaseHandoff.source)
    }
  }

  const snapshot = readStoredSnapshot()

  if (!snapshot) {
    return {
      phase: 'system_setup',
      systemSpecs: createDefaultSystemSpecs(),
      target: createDefaultTarget(),
      source: fallbackSource,
      recommendations: fallbackRecommendations,
      reportMeta: null,
      activeRecommendationId: fallbackActiveRecommendationId,
      runtimeMode: null,
      resultOrigin: null,
      runOutcome: null,
      validationIssues: [],
      staleReportNotice: null,
      restoreNotice: null,
      steps: buildInitialSteps(fallbackSource)
    }
  }

  const recommendations = [...snapshot.recommendations]
  const reportMeta = cloneReportMeta(snapshot.reportMeta)
  const activeRecommendationId =
    recommendations.find((recommendation) => recommendation.paper_id === snapshot.activeRecommendationId)
      ?.paper_id ||
    recommendations[0]?.paper_id ||
    null

  if (snapshot.phase === 'discovering') {
    return {
      phase: 'source_selection',
      systemSpecs: snapshot.systemSpecs,
      target: snapshot.target,
      source: snapshot.source,
      recommendations,
      reportMeta,
      activeRecommendationId,
      runtimeMode: snapshot.runtimeMode,
      resultOrigin: snapshot.resultOrigin,
      runOutcome: {
        kind: 'interrupted',
        title: 'Previous discovery was interrupted',
        message:
          'The page refreshed while discovery was running. Your inputs were restored at the source step so you can rerun safely.',
        details: []
      },
      validationIssues: snapshot.validationIssues,
      staleReportNotice: snapshot.staleReportNotice,
      restoreNotice: {
        title: 'Session restored after interruption',
        message:
          'The in-progress run was not resumed automatically. Review the inputs and rerun when ready.'
      },
      steps: buildInitialSteps(snapshot.source)
    }
  }

  const firstBlockingIssue = snapshot.validationIssues.find(
    (issue) => issue.severity === 'error'
  )

  const phase =
    snapshot.phase === 'failed' && snapshot.runOutcome?.kind === 'validation'
      ? firstBlockingIssue?.stage || 'target_setup'
      : snapshot.phase === 'completed' && recommendations.length === 0
        ? 'source_selection'
        : snapshot.phase

  return {
    phase,
    systemSpecs: snapshot.systemSpecs,
    target: snapshot.target,
    source: snapshot.source,
    recommendations,
    reportMeta,
    activeRecommendationId,
    runtimeMode: snapshot.runtimeMode,
    resultOrigin: snapshot.resultOrigin,
    runOutcome: snapshot.runOutcome,
    validationIssues: snapshot.validationIssues,
    staleReportNotice: snapshot.staleReportNotice,
    restoreNotice: {
      title: 'Session restored',
      message: recommendations.length
        ? 'Restored your latest draft and the most recent recommendation report.'
        : 'Restored your latest draft so you can keep working without resetting.'
    },
    steps: buildInitialSteps(snapshot.source)
  }
}

async function waitForNextPaint() {
  if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') {
    return
  }

  await new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => resolve())
  })
}

async function pollRecommendationJob(
  jobId: string,
  source: DiscoverySource,
  onProgress: (status: RecommendationJobStatus) => void
): Promise<RecommendationJobStatus> {
  let lastUpdatedAt: string | null = null
  let lastProgressAt = Date.now()

  while (true) {
    const status = await api.getRecommendationJob(jobId)
    onProgress(status)

    if (status.updated_at !== lastUpdatedAt) {
      lastUpdatedAt = status.updated_at
      lastProgressAt = Date.now()
    } else if (Date.now() - lastProgressAt > JOB_PROGRESS_STALE_MS) {
      throw new ApiError(
        `Recommendation job stopped reporting progress for ${JOB_PROGRESS_STALE_MS / 1000} seconds while ${buildStepsFromJobStatus(source, status).find((step) => step.status === 'active')?.label?.toLowerCase() || 'running discovery'}.`,
        408
      )
    }

    if (status.state === 'completed') {
      return status
    }

    if (status.state === 'failed') {
      throw new ApiError(
        status.error_detail?.message || status.error_message || 'Recommendation job failed before producing a report.',
        500,
        status.error_detail || null
      )
    }

    await delay(JOB_POLL_INTERVAL_MS)
  }
}

function buildLocalClarificationQuestions(
  systemSpecs: SystemSpecs,
  target: DiscoveryTarget
): ClarificationQuestion[] {
  const questions: ClarificationQuestion[] = []

  if (target.maxRunTimeMin === null) {
    questions.push({
      id: 'local_runtime',
      question: "What's your target runtime limit? Leave blank to keep it uncapped.",
      placeholder: 'e.g. 15 min — or leave blank for no limit'
    })
  }

  if ((systemSpecs.instrumentModes || []).length === 0) {
    questions.push({
      id: 'local_modes',
      question: 'Which LC modes does your instrument support? (e.g. RP-LC, HILIC, Normal Phase)',
      placeholder: 'e.g. RP-LC, HILIC — or leave blank'
    })
  }

  if (systemSpecs.availableSolvents.length === 0) {
    questions.push({
      id: 'local_solvents',
      question: 'Which solvents are available on your system?',
      placeholder: 'e.g. Acetonitrile, Methanol, Water — or leave blank'
    })
  }

  if (systemSpecs.detectorTypes.length === 0) {
    questions.push({
      id: 'local_detectors',
      question: 'What detectors are available?',
      placeholder: 'e.g. UV-Vis, MS/MS, PDA — or leave blank'
    })
  }

  if (
    systemSpecs.columnLengthMm === null &&
    systemSpecs.columnIdMm === null &&
    systemSpecs.particleSizeUm === null
  ) {
    questions.push({
      id: 'local_column_dims',
      question: 'Any column dimension constraints?',
      placeholder: 'e.g. 50 mm × 2.1 mm, 1.7 µm particles — or leave blank'
    })
  }

  if (systemSpecs.maxPressureBar === null) {
    questions.push({
      id: 'local_pressure',
      question: "What's your system pressure limit? Leave blank if there's no constraint.",
      placeholder: 'e.g. 1000 bar — or leave blank for no limit'
    })
  }

  return questions
}

export function useAgentWorkflow({ runtimeConfig, startupHealth }: UseAgentWorkflowOptions) {
  const initialState = useMemo(() => buildInitialWorkflowState(), [])

  const [phase, setPhase] = useState<ExtendedPhase>(initialState.phase)
  const [systemSpecsState, setSystemSpecsState] = useState<SystemSpecs>(
    initialState.systemSpecs
  )
  const [targetState, setTargetState] = useState<DiscoveryTarget>(initialState.target)
  const [sourceState, setSourceState] = useState<DiscoverySource>(initialState.source)
  const [steps, setSteps] = useState<ResearchStep[]>(initialState.steps)
  const [recommendations, setRecommendations] = useState<Recommendation[]>(
    initialState.recommendations
  )
  const [reportMeta, setReportMeta] = useState<RecommendationReportMeta | null>(
    initialState.reportMeta
  )
  const [activeRecommendationId, setActiveRecommendationId] = useState<string | null>(
    initialState.activeRecommendationId
  )
  const [runtimeMode, setRuntimeMode] = useState<AgentRuntimeMode | null>(
    initialState.runtimeMode
  )
  const [resultOrigin, setResultOrigin] = useState<AgentResultOrigin | null>(
    initialState.resultOrigin
  )
  const [runOutcome, setRunOutcome] = useState<RunOutcome | null>(initialState.runOutcome)
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>(
    initialState.validationIssues
  )
  const [restoreNotice, setRestoreNotice] = useState<WorkflowNotice | null>(
    initialState.restoreNotice
  )
  const [staleReportNotice, setStaleReportNotice] = useState<string | null>(
    initialState.staleReportNotice
  )
  const [recentSnapshots, setRecentSnapshots] = useState<CachedAgentRunSnapshot[]>(() =>
    listCachedAgentRunSnapshots()
  )
  const [activeRunRequestHash, setActiveRunRequestHash] = useState<string | null>(null)
  const [pendingClarification, setPendingClarification] = useState<ClarificationQuestion[] | null>(null)
  const [localClarificationPending, setLocalClarificationPending] = useState(false)
  const [localClarifyDone, setLocalClarifyDone] = useState(false)
  const [promptRecognition, setPromptRecognition] = useState<PromptRecognitionSummary>(
    buildEmptyPromptRecognition()
  )

  const hasReport = recommendations.length > 0
  const effectiveTarget = useMemo(
    () => buildEffectiveTarget(targetState, promptRecognition),
    [promptRecognition, targetState]
  )
  const recentRuns = useMemo(
    () => recentSnapshots.map((snapshot) => buildRecentRunSummary(snapshot)),
    [recentSnapshots]
  )

  useEffect(() => {
    const requestText = targetState.requestText.trim()
    if (!requestText) {
      setPromptRecognition(buildEmptyPromptRecognition())
      return
    }

    let cancelled = false
    const timeoutId = window.setTimeout(() => {
      const detected = detectPromptRecognition(requestText)
      setPromptRecognition(detected)

      const analytesToResolve = detected.analytes.filter(
        (analyte) => analyte.status === 'recognizing' && analyte.resolvedSmiles
      )

      if (!analytesToResolve.length) {
        return
      }

      void Promise.all(
        analytesToResolve.map(async (analyte) => {
          try {
            const result = await api.resolveSmilesName(analyte.resolvedSmiles || '')
            if (cancelled) {
              return
            }

            setPromptRecognition((current) => ({
              ...current,
              analytes: current.analytes.map((item) =>
                item.id === analyte.id
                  ? updateRecognizedAnalyte(item, {
                      status: 'recognized',
                      value: result.resolved_name || item.value,
                      resolvedName: result.resolved_name,
                      resolvedSmiles: result.smiles,
                      lookupSource: result.source,
                      lookupError: null,
                      confidenceLabel: 'resolved from SMILES'
                    })
                  : item
              ),
              unresolvedItems: current.unresolvedItems.filter(
                (message) => !message.includes(analyte.value)
              )
            }))
          } catch (error) {
            if (cancelled) {
              return
            }

            const message = getApiErrorMessage(error, 'Unable to resolve recognized analyte.')
            setPromptRecognition((current) => ({
              ...current,
              analytes: current.analytes.map((item) =>
                item.id === analyte.id
                  ? updateRecognizedAnalyte(item, {
                      status: error instanceof ApiError && error.status === 404 ? 'unresolved' : 'error',
                      lookupError: message,
                      lookupSource: null,
                      resolvedName: null
                    })
                  : item
              ),
              unresolvedItems: [
                ...current.unresolvedItems.filter((existing) => existing !== message),
                message
              ]
            }))
          }
        })
      )
    }, 220)

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [targetState.requestText])

  useEffect(() => {
    if (
      phase === 'system_setup' &&
      isDefaultSystemSpecs(systemSpecsState) &&
      isDefaultTarget(targetState) &&
      sourceState === 'open_access' &&
      recommendations.length === 0 &&
      activeRecommendationId === null &&
      runtimeMode === null &&
      resultOrigin === null &&
      runOutcome === null &&
      validationIssues.length === 0 &&
      staleReportNotice === null
    ) {
      clearStoredSnapshot()
      return
    }

    writeStoredSnapshot({
      version: 1,
      phase,
      systemSpecs: cloneSystemSpecs(systemSpecsState),
      target: cloneTarget(targetState),
      source: sourceState,
      recommendations,
      reportMeta,
      activeRecommendationId,
      runtimeMode,
      resultOrigin,
      runOutcome,
      validationIssues,
      staleReportNotice
    })
  }, [
    activeRecommendationId,
    phase,
    reportMeta,
    resultOrigin,
    recommendations,
    runOutcome,
    runtimeMode,
    sourceState,
    staleReportNotice,
    systemSpecsState,
    targetState,
    validationIssues
  ])

  const clearValidationIssues = useCallback((fields: string[]) => {
    setValidationIssues((current) =>
      current.filter((issue) => !fields.includes(issue.field))
    )
  }, [])

  const markDraftAsEdited = useCallback(
    (stage: EditablePhase, fields: string[]) => {
      const hasSubmittedRequest = Boolean(targetState.requestText.trim())
      const shouldPreserveConversationPhase =
        phase === 'recognition_verify' ||
        phase === 'planning' ||
        phase === 'completed' ||
        phase === 'failed'
      setPhase(
        hasSubmittedRequest && shouldPreserveConversationPhase ? phase : stage
      )
      clearValidationIssues(fields)

      if (hasReport) {
        setStaleReportNotice(
          'Inputs changed. The report below still reflects the last successful run. Rerun discovery to refresh it.'
        )
      }
    },
    [clearValidationIssues, hasReport, phase, targetState.requestText]
  )

  const setSystemSpecs = useCallback(
    (value: SetStateAction<SystemSpecs>) => {
      markDraftAsEdited('system_setup', [
        'columnManufacturer',
        'customManufacturer',
        'columnName',
        'columnChemistry',
        'customChemistry',
        'columnLengthMm',
        'columnIdMm',
        'particleSizeUm',
        'availableSolvents',
        'detectorTypes',
        'instrumentModes',
        'maxPressureBar'
      ])

      setSystemSpecsState((current) => {
        const nextValue = typeof value === 'function' ? value(current) : value
        return cloneSystemSpecs(nextValue)
      })
    },
    [markDraftAsEdited]
  )

  const setTarget = useCallback(
    (value: SetStateAction<DiscoveryTarget>) => {
      markDraftAsEdited('target_setup', [
        'requestText',
        'analyteName',
        'targetSmiles',
        'matrix',
        'customMatrix',
        'impurities',
        'requireMS',
        'maxRunTimeMin'
      ])

      setTargetState((current) => {
        const nextValue = typeof value === 'function' ? value(current) : value
        return cloneTarget(nextValue)
      })
    },
    [markDraftAsEdited]
  )

  const setSource = useCallback(
    (nextSource: DiscoverySource) => {
      markDraftAsEdited('source_selection', ['targetSmiles'])
      setSourceState(nextSource)
      setSteps(buildInitialSteps(nextSource))
    },
    [markDraftAsEdited]
  )

  const goToSystemSetup = useCallback(() => {
    setPhase('system_setup')
  }, [])

  const goToTargetSetup = useCallback(() => {
    setPhase('target_setup')
  }, [])

  const goToSourceSelection = useCallback(() => {
    setPhase('source_selection')
    setSteps(buildInitialSteps(sourceState))
  }, [sourceState])

  const dismissRestoreNotice = useCallback(() => {
    setRestoreNotice(null)
  }, [])

  const dismissStaleReportNotice = useCallback(() => {
    setStaleReportNotice(null)
  }, [])

  const resetSession = useCallback(() => {
    clearStoredSnapshot()
    setPhase('system_setup')
    setSystemSpecsState(createDefaultSystemSpecs())
    setTargetState(createDefaultTarget())
    setSourceState('open_access')
    setSteps(buildInitialSteps('open_access'))
    setRecommendations([])
    setReportMeta(null)
    setActiveRecommendationId(null)
    setRuntimeMode(null)
    setResultOrigin(null)
    setActiveRunRequestHash(null)
    setRunOutcome(null)
    setValidationIssues([])
    setRestoreNotice(null)
    setStaleReportNotice(null)
    setPendingClarification(null)
    setLocalClarifyDone(false)
  }, [])

  const loadDemoData = useCallback(() => {
    setPhase('source_selection')
    setSystemSpecsState({
      columnManufacturer: 'Waters',
      customManufacturer: '',
      columnName: 'Acquity BEH C18',
      columnChemistry: 'C18',
      customChemistry: '',
      columnLengthMm: 50,
      columnIdMm: 2.1,
      particleSizeUm: 1.7,
      availableSolvents: ['Acetonitrile', 'Methanol', 'Water'],
      detectorTypes: ['UV/PDA', 'MS/MS'],
      instrumentModes: [],
      maxPressureBar: 0
    })
    setTargetState({
      requestText: '',
      analyteName: 'Metformin',
      targetSmiles: 'CN(C)C(=N)N=C(N)N',
      targetResolvedName: 'Metformin',
      targetLookupSource: 'demo',
      targetLookupError: null,
      targetResolving: false,
      impurities: [],
      matrix: 'Human Plasma',
      customMatrix: '',
      requireMS: false,
      maxRunTimeMin: null
    })
    setSourceState('open_access')
    setSteps(buildInitialSteps('open_access'))
    setRuntimeMode(null)
    setResultOrigin(null)
    setActiveRunRequestHash(null)
    setRecommendations([])
    setReportMeta(null)
    setActiveRecommendationId(null)
    setRunOutcome(null)
    setValidationIssues([])
    setRestoreNotice(null)
    setStaleReportNotice(null)
    setPendingClarification(null)
    setLocalClarifyDone(false)
  }, [])

  const updateTargetSmiles = useCallback(
    (smiles: string) => {
      markDraftAsEdited('target_setup', ['targetSmiles'])
      setTargetState((current) => ({
        ...current,
        targetSmiles: smiles,
        targetResolvedName: null,
        targetLookupSource: null,
        targetLookupError: null,
        targetResolving: false
      }))
    },
    [markDraftAsEdited]
  )

  const resolveTargetSmilesName = useCallback(async () => {
    const smiles = targetState.targetSmiles.trim()

    if (!smiles) {
      setTargetState((current) => ({
        ...current,
        targetLookupError: 'Enter a target SMILES first.',
        targetResolvedName: null,
        targetLookupSource: null,
        targetResolving: false
      }))
      return
    }

    setTargetState((current) => ({
      ...current,
      targetResolving: true,
      targetLookupError: null
    }))

    try {
      const result = await api.resolveSmilesName(smiles)
      setTargetState((current) => ({
        ...current,
        analyteName: current.analyteName || result.resolved_name,
        targetResolvedName: result.resolved_name,
        targetLookupSource: result.source,
        targetLookupError: null,
        targetResolving: false
      }))
    } catch (error) {
      setTargetState((current) => ({
        ...current,
        targetResolvedName: null,
        targetLookupSource: null,
        targetLookupError: getApiErrorMessage(error, 'Unable to resolve molecule name.'),
        targetResolving: false
      }))
    }
  }, [targetState.targetSmiles])

  const addImpurity = useCallback(() => {
    markDraftAsEdited('target_setup', ['impurities'])
    setTargetState((current) => ({
      ...current,
      impurities: [...current.impurities, createCompound()]
    }))
  }, [markDraftAsEdited])

  const updateImpurity = useCallback(
    (compoundId: string, smiles: string) => {
      markDraftAsEdited('target_setup', ['impurities'])
      setTargetState((current) => ({
        ...current,
        impurities: current.impurities.map((compound) =>
          compound.id === compoundId
            ? {
                ...compound,
                smiles,
                name: null,
                resolved: false,
                resolving: false,
                lookupSource: null,
                lookupError: null
              }
            : compound
        )
      }))
    },
    [markDraftAsEdited]
  )

  const removeImpurity = useCallback(
    (compoundId: string) => {
      markDraftAsEdited('target_setup', ['impurities'])
      setTargetState((current) => ({
        ...current,
        impurities: current.impurities.filter((compound) => compound.id !== compoundId)
      }))
    },
    [markDraftAsEdited]
  )

  const resolveImpurityName = useCallback(
    async (compoundId: string) => {
      const compound = targetState.impurities.find((item) => item.id === compoundId)
      const smiles = compound?.smiles.trim() || ''

      if (!smiles) {
        setTargetState((current) => ({
          ...current,
          impurities: current.impurities.map((item) =>
            item.id === compoundId
              ? {
                  ...item,
                  lookupError: 'Enter an impurity SMILES first.',
                  lookupSource: null,
                  resolving: false,
                  resolved: false
                }
              : item
          )
        }))
        return
      }

      setTargetState((current) => ({
        ...current,
        impurities: current.impurities.map((item) =>
          item.id === compoundId
            ? {
                ...item,
                resolving: true,
                lookupError: null
              }
            : item
        )
      }))

      try {
        const result = await api.resolveSmilesName(smiles)
        setTargetState((current) => ({
          ...current,
          impurities: current.impurities.map((item) =>
            item.id === compoundId
              ? {
                  ...item,
                  name: result.resolved_name,
                  resolved: true,
                  resolving: false,
                  lookupSource: result.source,
                  lookupError: null
                }
              : item
          )
        }))
      } catch (error) {
        setTargetState((current) => ({
          ...current,
          impurities: current.impurities.map((item) =>
            item.id === compoundId
              ? {
                  ...item,
                  name: null,
                  resolved: false,
                  resolving: false,
                  lookupSource: null,
                  lookupError: getApiErrorMessage(
                    error,
                    'Unable to resolve impurity molecule name.'
                  )
                }
              : item
          )
        }))
      }
    },
    [targetState.impurities]
  )

  const applyReportState = useCallback(
    ({
      report,
      source,
      nextRuntimeMode,
      nextResultOrigin,
      nextOutcome,
      requestHash
    }: {
      report: MethodRecommendationReport
      source: DiscoverySource
      nextRuntimeMode: AgentRuntimeMode
      nextResultOrigin: AgentResultOrigin
      nextOutcome: RunOutcome | null
      requestHash?: string | null
    }) => {
      const results = report.considered_candidates || []
      if (!results.length) {
        setRunOutcome(buildEmptyOutcome(source, report, nextRuntimeMode))
        setRuntimeMode(nextRuntimeMode)
        setResultOrigin(nextResultOrigin)
        setSteps(buildStepProgress(source, 1, 1))
        setPhase('failed')
        setActiveRunRequestHash(requestHash || null)
        return false
      }

      const recommendedId = report.recommended_candidate?.paper_id || results[0]?.paper_id || null

      setRecommendations(results)
      setReportMeta(buildReportMeta(source, report))
      setActiveRecommendationId(recommendedId)
      setRuntimeMode(nextRuntimeMode)
      setResultOrigin(nextResultOrigin)
      setRunOutcome(nextOutcome)
      setStaleReportNotice(null)
      setSteps(buildStepProgress(source, null))
      setPhase('completed')
      setActiveRunRequestHash(requestHash || null)
      return true
    },
    []
  )

  const runDiscovery = useCallback(
    async (options?: { forceLive?: boolean; skipClarify?: boolean; skipRecognition?: boolean }) => {
      setRecommendations([])
      const issues = buildValidationIssues(effectiveTarget, systemSpecsState, sourceState)
      const blockingIssues = issues.filter((issue) => issue.severity === 'error')

      setValidationIssues(issues)
      setRestoreNotice(null)

      if (blockingIssues.length > 0) {
        const outcome = buildValidationOutcome(issues)
        setRunOutcome(outcome)
        setPhase(blockingIssues[0]?.stage || 'target_setup')
        return
      }

      // 1. Recognition Stage: Before running anything, show the user what we detected
      if (!options?.skipRecognition) {
        setPhase('recognition_verify')
        return
      }

      const request = buildRecommendationRequestSnapshot(
        effectiveTarget,
        systemSpecsState,
        sourceState,
        runtimeConfig
      )
      const requestHash = buildAgentRunRequestHash(request)
      const cachedSnapshot = getCachedAgentRunSnapshot(requestHash)
      const shouldPreferCached =
        !options?.forceLive &&
        Boolean(cachedSnapshot) &&
        (runtimeConfig.cachePolicy === 'cached_preferred' ||
          startupHealth?.status === 'unavailable' ||
          startupHealth?.methodDev.status === 'unavailable')

      setValidationIssues(issues)
      setRestoreNotice(null)
      setSteps(buildStepProgress(sourceState, 0))

      if (blockingIssues.length > 0) {
        const outcome = buildValidationOutcome(issues)
        setRunOutcome(outcome)
        setPhase(blockingIssues[0]?.stage || 'target_setup')
        return
      }

      // Clarification step: ask about important missing parameters before running
      if (!options?.skipClarify) {
        try {
          const clarifyResult = await api.clarifyRequest(
            effectiveTarget,
            systemSpecsState,
            sourceState
          )
          if (clarifyResult.questions.length > 0) {
            setPendingClarification(clarifyResult.questions)
            return
          }
        } catch {
          // Clarification is best-effort; proceed to discovery on any error
        }
      }
      setPendingClarification(null)

      setPhase('discovering')
      setRunOutcome(null)
      setRuntimeMode(null)
      setResultOrigin(null)
      setActiveRunRequestHash(null)
      const runStartedAt = Date.now()

      const commitCachedSnapshot = async (snapshot: CachedAgentRunSnapshot) => {
        await waitForNextPaint()
        await playMinimumDiscoveryPacing(sourceState, runStartedAt, setSteps)
        applyReportState({
          report: snapshot.report,
          source: restoreSourceFromCachedSnapshot(snapshot),
          nextRuntimeMode: 'cached',
          nextResultOrigin: 'cached',
          nextOutcome: buildCachedResultOutcome(snapshot),
          requestHash: snapshot.requestHash
        })
      }

      if (shouldPreferCached && cachedSnapshot) {
        await commitCachedSnapshot(cachedSnapshot)
        return
      }

      try {
        await waitForNextPaint()
        setSteps(buildStepProgress(sourceState, 1))

        let report: MethodRecommendationReport | null = null
        let furthestObservedStageIndex = 1

        try {
          const job = await api.startRecommendationJob(
            effectiveTarget,
            systemSpecsState,
            sourceState
          )
          const jobStatus = await pollRecommendationJob(job.job_id, sourceState, (status) => {
            if (status.stage === 'match_system') {
              furthestObservedStageIndex = Math.max(furthestObservedStageIndex, 2)
            } else if (status.stage === 'scale_physics') {
              furthestObservedStageIndex = Math.max(furthestObservedStageIndex, 3)
            } else if (status.stage === 'final_rank') {
              furthestObservedStageIndex = Math.max(furthestObservedStageIndex, 4)
            }
            if (status.state === 'completed') {
              return
            }
            setSteps(buildStepsFromJobStatus(sourceState, status))
          })
          report = jobStatus.report || null
          if (!report) {
            throw new ApiError('Recommendation job completed without a final report.', 500)
          }
        } catch (error) {
          if (cachedSnapshot) {
            await commitCachedSnapshot(cachedSnapshot)
            return
          }
          throw error
        }

        if (!report) {
          throw new ApiError('Recommendation job completed without a final report.', 500)
        }

        await playMinimumDiscoveryPacing(
          sourceState,
          runStartedAt,
          setSteps,
          furthestObservedStageIndex
        )

        const origin = deriveResultOrigin(report)
        const committed = applyReportState({
          report,
          source: sourceState,
          nextRuntimeMode: 'live',
          nextResultOrigin: origin,
          nextOutcome: null,
          requestHash
        })
        if (!committed) {
          return
        }

        saveCachedAgentRunSnapshot({
          schemaVersion: 1,
          requestHash,
          createdAt: new Date().toISOString(),
          origin,
          request,
          report,
          runtimeSummary: report.runtime || null
        })
        setRecentSnapshots(listCachedAgentRunSnapshots())
      } catch (error) {
        console.error('Discovery failed:', error)
        const outcome = buildFailureOutcome(error)
        setRunOutcome(outcome)
        setRuntimeMode(null)
        setResultOrigin(null)
        setActiveRunRequestHash(null)
        setSteps(buildStepProgress(sourceState, 1, 1))
        setPhase('failed')
      }
    },
    [applyReportState, effectiveTarget, runtimeConfig, sourceState, startupHealth, systemSpecsState]
  )

  const confirmRecognition = useCallback(() => {
    const localQuestions = buildLocalClarificationQuestions(systemSpecsState, effectiveTarget)
    if (localQuestions.length > 0) {
      setLocalClarificationPending(true)
      setPendingClarification(localQuestions)
      return
    }
    setLocalClarifyDone(false)
    setPhase('planning')
  }, [effectiveTarget, systemSpecsState])

  const approveClarification = useCallback(() => {
    setLocalClarifyDone(false)
    setLocalClarificationPending(false)
    setPhase('planning')
  }, [])

  const approvePlan = useCallback(async () => {
    await runDiscovery({ skipClarify: true, skipRecognition: true })
  }, [runDiscovery])

  const prepareRunDraft = useCallback(
    async (options?: { skipClarify?: boolean; skipLocalClarify?: boolean; requestTextOverride?: string }) => {
      const trimmedOverride = options?.requestTextOverride?.trim()
      const nextRecognition =
        typeof trimmedOverride === 'string'
          ? (trimmedOverride
              ? detectPromptRecognition(trimmedOverride)
              : buildEmptyPromptRecognition())
          : promptRecognition
      const nextTarget =
        typeof trimmedOverride === 'string'
          ? cloneTarget({
              ...targetState,
              requestText: trimmedOverride
            })
          : targetState
      const nextEffectiveTarget = buildEffectiveTarget(nextTarget, nextRecognition)
      const issues = buildValidationIssues(nextEffectiveTarget, systemSpecsState, sourceState)
      const blockingIssues = issues.filter((issue) => issue.severity === 'error')

      if (typeof trimmedOverride === 'string') {
        setPromptRecognition(nextRecognition)
      }

      setValidationIssues(issues)
      setRestoreNotice(null)

      if (blockingIssues.length > 0) {
        const outcome = buildValidationOutcome(issues)
        setRunOutcome(outcome)
        setPendingClarification(null)
        setPhase(blockingIssues[0]?.stage || 'target_setup')
        return {
          ready: false,
          blockingIssues,
          clarificationQuestions: [] as ClarificationQuestion[]
        }
      }

      setRunOutcome(null)
      setPendingClarification(null)
      setPhase('recognition_verify')

      if (!options?.skipClarify) {
        api.clarifyRequest(nextEffectiveTarget, systemSpecsState, sourceState)
          .then((clarifyResult) => {
            if (clarifyResult.questions.length > 0) {
              setPendingClarification(clarifyResult.questions)
            }
          })
          .catch(() => {
            // Clarification is best-effort; preparation still succeeds when the endpoint is unavailable.
          })
      }

      return {
        ready: true,
        blockingIssues: [] as ValidationIssue[],
        clarificationQuestions: [] as ClarificationQuestion[]
      }
    },
    [promptRecognition, sourceState, systemSpecsState, targetState]
  )

  const loadRecentRun = useCallback(
    (requestHash: string) => {
      const snapshot =
        recentSnapshots.find((recentSnapshot) => recentSnapshot.requestHash === requestHash) ||
        getCachedAgentRunSnapshot(requestHash)

      if (!snapshot) {
        return
      }

      setRecentSnapshots(listCachedAgentRunSnapshots())
      const restoredSource = restoreSourceFromCachedSnapshot(snapshot)
      setSystemSpecsState(restoreSystemSpecsFromCachedSnapshot(snapshot))
      setTargetState(restoreTargetFromCachedSnapshot(snapshot))
      setSourceState(restoredSource)
      setValidationIssues([])
      setPendingClarification(null)
      setRestoreNotice({
        title: 'Recent run loaded',
        message:
          'Loaded a cached recommendation run from local history and restored its saved inputs into the current workspace.'
      })

      applyReportState({
        report: snapshot.report,
        source: restoredSource,
        nextRuntimeMode: 'cached',
        nextResultOrigin: 'cached',
        nextOutcome: buildCachedResultOutcome(snapshot),
        requestHash: snapshot.requestHash
      })
    },
    [applyReportState, recentSnapshots]
  )

  const rerunDiscovery = useCallback(async () => {
    await runDiscovery()
  }, [runDiscovery])

  const retryLiveDiscovery = useCallback(async () => {
    await runDiscovery({ forceLive: true })
  }, [runDiscovery])

  const applyClarificationAnswers = useCallback((answers: Record<string, string>) => {
    const enrichments = Object.entries(answers)
      .filter(([, value]) => value.trim())
      .map(([, value]) => value.trim())

    if (enrichments.length > 0) {
      setTargetState((prev) => ({
        ...prev,
        requestText: prev.requestText
          ? `${prev.requestText}. ${enrichments.join('. ')}`
          : enrichments.join('. ')
      }))
    }

    setPendingClarification(null)
    setLocalClarificationPending(false)
    setLocalClarifyDone(true)
  }, [])

  const skipClarification = useCallback(() => {
    setPendingClarification(null)
    setLocalClarificationPending(false)
    setLocalClarifyDone(true)
  }, [])

  const submitClarification = useCallback(
    async (answers: Record<string, string>) => {
      applyClarificationAnswers(answers)
      await runDiscovery({ skipClarify: true })
    },
    [applyClarificationAnswers, runDiscovery]
  )

  const dismissClarification = useCallback(async () => {
    skipClarification()
    await runDiscovery({ skipClarify: true })
  }, [runDiscovery, skipClarification])

  const activeRecommendation = useMemo(
    () =>
      recommendations.find(
        (recommendation) => recommendation.paper_id === activeRecommendationId
      ) ||
      recommendations[0] ||
      null,
    [activeRecommendationId, recommendations]
  )
  const runtimeStatusLabel = formatRuntimeStatusLabel(reportMeta?.runtime || null)

  return {
    phase,
    runOutcome,
    validationIssues,
    restoreNotice,
    staleReportNotice,
    runtimeMode,
    resultOrigin,
    systemSpecs: systemSpecsState,
    effectiveTarget,
    promptRecognition,
    setSystemSpecs,
    target: targetState,
    setTarget,
    source: sourceState,
    setSource,
    loadDemoData,
    goToSystemSetup,
    goToTargetSetup,
    goToSourceSelection,
    dismissRestoreNotice,
    dismissStaleReportNotice,
    resetSession,
    updateTargetSmiles,
    resolveTargetSmilesName,
    addImpurity,
    updateImpurity,
    removeImpurity,
    resolveImpurityName,
    confirmRecognition,
    approveClarification,
    approvePlan,
    prepareRunDraft,
    runDiscovery,
    rerunDiscovery,
    retryLiveDiscovery,
    pendingClarification,
    localClarificationPending,
    applyClarificationAnswers,
    skipClarification,
    submitClarification,
    dismissClarification,
    loadRecentRun,
    recentRuns,
    activeRunRequestHash,
    steps,
    recommendations,
    reportMeta,
    runtimeStatusLabel,
    activeRecommendation,
    setActiveRecommendationId
  }
}
