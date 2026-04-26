import {
  AgentResultOrigin,
  AgentRuntimeMode,
  DiscoverySource,
  GradientPoint,
  DiscoveryTarget,
  MethodRecommendationReport,
  RecommendationErrorDetail,
  RecommendationJobAccepted,
  RecommendationJobStatus,
  SystemSpecs,
  ReviewRecord,
  ReviewRecordSummary,
  ReviewRecordApproveRequest,
  ReviewRecordRejectRequest,
  SourceDocumentUploadRequest,
  SourceDocumentMetadata,
  C12ReviewRecordOrchestrationRequest,
  C12ReviewRecordOrchestrationResponse,
  ClarifyResponse
} from '../types'
import {
  buildApiServiceUrl,
  buildMethodDevServiceUrl
} from './agentRuntime'

interface SmilesNameResolution {
  smiles: string
  resolved_name: string
  source: string
  candidates: string[]
}

export interface AgentFollowUpHistoryTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface AgentFollowUpMobilePhase {
  solvent: string | null
  additive: string | null
  ph_estimate: number | null
}

export interface AgentFollowUpRecommendationContext {
  paper_id: string
  title: string
  citation: string | null
  rationale: string | null
  core_method_summary: string | null
  flow_rate_ml_min: number | null
  run_time_min: number | null
  column_temperature_c: number | null
  is_scaled: boolean
  mobile_phase_a: AgentFollowUpMobilePhase | null
  mobile_phase_b: AgentFollowUpMobilePhase | null
  gradient_profile: GradientPoint[]
  isocratic_percent_b: number | null
  trust_state: string | null
  validation_status: string | null
  warning_summary: string[]
  scaling_notes: string[]
  dominant_differentiator: string | null
}

export interface AgentFollowUpRequest {
  question: string
  request_text: string
  source_mode: DiscoverySource
  runtime_mode: AgentRuntimeMode | null
  result_origin: AgentResultOrigin | null
  system_summary: string
  search_query_used: string | null
  recommendations_count: number
  active_recommendation: AgentFollowUpRecommendationContext | null
  history: AgentFollowUpHistoryTurn[]
}

export interface AgentFollowUpResponse {
  answer: string
  source: string
}

interface FetchJsonInit extends RequestInit {
  timeoutMs?: number
}

const REQUEST_TIMEOUT_MS = 12000

type RecommendationSourceMode = MethodRecommendationReport['source_mode']

export class ApiError extends Error {
  status: number
  detail?: RecommendationErrorDetail | Record<string, unknown> | null
  constructor(
    message: string,
    status = 0,
    detail?: RecommendationErrorDetail | Record<string, unknown> | null
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail || null
  }
}

function createTimeoutSignal(
  initSignal?: AbortSignal,
  timeoutMs = REQUEST_TIMEOUT_MS
): {
  signal: AbortSignal
  cleanup: () => void
} {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)

  if (initSignal) {
    if (initSignal.aborted) {
      controller.abort()
    } else {
      initSignal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  return {
    signal: controller.signal,
    cleanup: () => window.clearTimeout(timeoutId)
  }
}

async function fetchJson<T>(path: string, init?: FetchJsonInit): Promise<T> {
  const timeoutMs =
    typeof init?.timeoutMs === 'number' && Number.isFinite(init.timeoutMs)
      ? init.timeoutMs
      : REQUEST_TIMEOUT_MS
  const { signal, cleanup } = createTimeoutSignal(init?.signal ?? undefined, timeoutMs)

  try {
    const response = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
      signal
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: 'Request failed' }))
      const detail = payload?.detail
      const message = Array.isArray(detail)
        ? payload.detail.map((item: any) => item?.msg).filter(Boolean).join('; ')
        : typeof detail === 'string'
          ? detail
          : typeof detail?.message === 'string'
            ? detail.message
            : 'Request failed'
      throw new ApiError(message || 'Request failed', response.status, detail || null)
    }
    return response.json()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(`Request timed out after ${timeoutMs / 1000} seconds`, 408)
    }
    if (error instanceof ApiError) {
      throw error
    }
    throw new ApiError(error instanceof Error ? error.message : 'Request failed', 0)
  } finally {
    cleanup()
  }
}

function appendQuery(
  path: string,
  query: Record<string, string | number | boolean | null | undefined>
): string {
  const params = new URLSearchParams()

  Object.entries(query).forEach(([key, value]) => {
    if (value === null || typeof value === 'undefined') {
      return
    }
    params.set(key, String(value))
  })

  if (!params.size) {
    return path
  }

  return `${path}${path.includes('?') ? '&' : '?'}${params.toString()}`
}

export function buildRecommendationPayload(
  target: DiscoveryTarget,
  systemSpecs: SystemSpecs,
  sourceMode: RecommendationSourceMode
) {
  return {
    request_text:
      target.requestText ||
      `Separate ${target.analyteName || target.targetResolvedName || 'target analyte'}`,
    analyte_name: target.analyteName || target.targetResolvedName || null,
    target_smiles: target.targetSmiles || null,
    impurity_smiles: target.impurities
      .map((compound) => compound.smiles.trim())
      .filter(Boolean),
    matrix_hint:
      target.matrix === 'Other'
        ? target.customMatrix?.trim() || null
        : target.matrix || null,
    system_specs: {
      column_manufacturer:
        systemSpecs.columnManufacturer === 'Other'
          ? systemSpecs.customManufacturer?.trim() || null
          : systemSpecs.columnManufacturer || null,
      column_name: systemSpecs.columnName || null,
      column_chemistry:
        systemSpecs.columnChemistry === 'Other'
          ? systemSpecs.customChemistry?.trim() || null
          : systemSpecs.columnChemistry || null,
      column_length_mm: systemSpecs.columnLengthMm || null,
      column_inner_diameter_mm: systemSpecs.columnIdMm || null,
      particle_size_um: systemSpecs.particleSizeUm || null,
      available_solvents: systemSpecs.availableSolvents || [],
      detector_types: systemSpecs.detectorTypes || [],
      instrument_modes: systemSpecs.instrumentModes || [],
      max_pressure_bar: systemSpecs.maxPressureBar || null
    },
    require_mass_spectrometry: target.requireMS || false,
    source_mode: sourceMode,
    max_papers: 8,
    max_run_time_min: target.maxRunTimeMin || null
  }
}

export const api = {
  clarifyRequest: (
    target: DiscoveryTarget,
    systemSpecs: SystemSpecs,
    sourceMode: RecommendationSourceMode
  ) =>
    fetchJson<ClarifyResponse>(buildMethodDevServiceUrl('/recommendation/clarify'), {
      method: 'POST',
      body: JSON.stringify({
        request_text: target.requestText || '',
        analyte_name: target.analyteName || null,
        max_run_time_min: target.maxRunTimeMin || null,
        matrix_hint:
          target.matrix === 'Other'
            ? target.customMatrix?.trim() || null
            : target.matrix || null,
        detector_types: systemSpecs.detectorTypes || [],
        require_mass_spectrometry: target.requireMS || false,
      }),
      timeoutMs: 15000,
    }),

  resolveSmilesName: (smiles: string) =>
    fetchJson<SmilesNameResolution>(buildApiServiceUrl('/api/v1/chemistry/smiles/resolve'), {
      method: 'POST',
      body: JSON.stringify({ smiles })
    }),

  answerFollowUp: (payload: AgentFollowUpRequest) =>
    fetchJson<AgentFollowUpResponse>(buildApiServiceUrl('/api/v1/agent/follow-up'), {
      method: 'POST',
      body: JSON.stringify(payload),
      timeoutMs: 15000
    }),

  runRecommendationFlow: (
    target: DiscoveryTarget,
    systemSpecs: SystemSpecs,
    sourceMode: RecommendationSourceMode = 'open_access'
  ) =>
    fetchJson<MethodRecommendationReport>(
      appendQuery(buildMethodDevServiceUrl('/recommendation/run'), {
        response_detail: 'agent'
      }),
      {
      method: 'POST',
      body: JSON.stringify(buildRecommendationPayload(target, systemSpecs, sourceMode))
    }
    ),

  startRecommendationJob: (
    target: DiscoveryTarget,
    systemSpecs: SystemSpecs,
    sourceMode: RecommendationSourceMode = 'open_access'
  ) =>
    fetchJson<RecommendationJobAccepted>(
      appendQuery(buildMethodDevServiceUrl('/recommendation/runs'), {
        response_detail: 'agent'
      }),
      {
      method: 'POST',
      body: JSON.stringify(buildRecommendationPayload(target, systemSpecs, sourceMode))
    }
    ),

  getRecommendationJob: (jobId: string) =>
    fetchJson<RecommendationJobStatus>(
      appendQuery(buildMethodDevServiceUrl(`/recommendation/runs/${jobId}`), {
        response_detail: 'agent'
      })
    ),

  registerSourceDocument: (payload: SourceDocumentUploadRequest) =>
    fetchJson<SourceDocumentMetadata>(buildMethodDevServiceUrl('/source-documents/'), {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  getSourceDocument: (sourceDocumentId: string) =>
    fetchJson<SourceDocumentMetadata>(buildMethodDevServiceUrl(`/source-documents/${sourceDocumentId}`)),

  createReviewRecordFromSource: (sourceDocumentId: string) =>
    fetchJson<ReviewRecord>(buildMethodDevServiceUrl(`/review-records/from-source-documents/${sourceDocumentId}`), {
      method: 'POST'
    }),

  prepareC12ReviewRecord: (payload: C12ReviewRecordOrchestrationRequest) =>
    fetchJson<C12ReviewRecordOrchestrationResponse>(buildMethodDevServiceUrl('/c12/review-records/prepare'), {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  getReviewRecords: () =>
    fetchJson<ReviewRecordSummary[]>(buildMethodDevServiceUrl('/review-records')),

  getReviewRecord: (recordId: string) =>
    fetchJson<ReviewRecord>(buildMethodDevServiceUrl(`/review-records/${recordId}`)),

  approveReviewRecord: (recordId: string, payload: ReviewRecordApproveRequest) =>
    fetchJson<ReviewRecord>(buildMethodDevServiceUrl(`/review-records/${recordId}/approve`), {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  rejectReviewRecord: (recordId: string, payload: ReviewRecordRejectRequest) =>
    fetchJson<ReviewRecord>(buildMethodDevServiceUrl(`/review-records/${recordId}/reject`), {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  promoteReviewRecord: (recordId: string) =>
    fetchJson<ReviewRecord>(buildMethodDevServiceUrl(`/review-records/${recordId}/promote`), {
      method: 'POST'
    }),

  demoteReviewRecord: (recordId: string) =>
    fetchJson<ReviewRecord>(buildMethodDevServiceUrl(`/review-records/${recordId}/demote`), {
      method: 'POST'
    })
}
