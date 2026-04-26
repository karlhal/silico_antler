import { type Dispatch, type ReactNode, type SetStateAction, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Cpu,
  FileText,
  FlaskConical,
  Library,
  Loader2,
  MessageSquare,
  LogOut,
  Plus,
  RotateCcw,
  Search,
  Settings2,
  Sparkles,
  Sun,
  Moon,
  Workflow,
  X
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/hooks/useTheme'
import { isSurrogateChatRequest } from '@/lib/chatIntents'
import { SurrogatePreview } from '../surrogate'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/studio/components/ui/dialog'
import { ScrollArea } from '@/studio/components/ui/scroll-area'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Tooltip } from '../ui/Tooltip'
import type { ConversationPlanSummary } from './conversationViewModel'
import { TypewriterText } from './typewriter'
import type {
  AgentResultOrigin,
  AgentRuntimeMode,
  ClarificationQuestion,
  CompoundContext,
  DiscoverySource,
  DiscoveryTarget,
  DummySurrogateSession,
  DummySurrogateState,
  EvidenceSnippet,
  ExternalEvidenceTrace,
  PromptRecognitionSummary,
  RecognizedAnalyte,
  RecognitionState,
  Recommendation,
  RecommendationFeatureBreakdown,
  RecommendationReportMeta,
  RecommendationQueryVariant,
  ResearchStep,
  SystemSpecs,
  TrustRailStep,
  WorkflowPhase
} from '../../types'

type ValidationSeverity = 'error' | 'note'

export interface WorkflowIssue {
  id: string
  field: string
  stage: 'system_setup' | 'target_setup' | 'source_selection'
  severity: ValidationSeverity
  message: string
}

export interface WorkflowOutcome {
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

export interface WorkflowNotice {
  title: string
  message: string
}

export interface DashboardFollowUpTurn {
  id: string
  speaker: 'user' | 'agent'
  title: string
  body: string
  tone?: 'default' | 'warning'
  pending?: boolean
  action?: {
    type: 'open_surrogate'
    label: string
    recommendationId?: string | null
  }
}

export interface RecentRunSummary {
  requestHash: string
  createdAt: string
  createdAtLabel: string
  title: string
  subtitle: string
  sourceMode: 'local_corpus' | 'open_access' | 'local_files'
  candidateCount: number
  origin: AgentResultOrigin
}

type TooltipCopyKey =
  | 'trust_state'
  | 'validation_posture'
  | 'review_posture'
  | 'ranking_mode'
  | 'result_origin'
  | 'runtime_mode'

const manufacturers = ['Agilent', 'Waters', 'Shimadzu', 'Thermo Fisher', 'YMC', 'Other']
const chemistries = ['C18', 'C8', 'Phenyl', 'HILIC', 'Silica', 'Other']
const matrices = ['Human Plasma', 'Bovine Serum', 'Water', 'Solvent', 'Other']
const solvents = ['Water', 'Acetonitrile', 'Methanol', 'IPA', 'THF']
const detectors = ['UV-Vis', 'MS/MS', 'PDA', 'ELSD', 'RID']
const hardwareModes = ['RP-LC', 'HILIC', 'Normal Phase']

const TOOLTIP_COPY: Record<TooltipCopyKey, string> = {
  trust_state:
    'Shows whether the candidate comes from a reviewed corpus record, seeded reference, or a fresh document extraction.',
  validation_posture:
    'Summarizes whether the extracted method was validated, rejected, or still needs operator review.',
  review_posture:
    'Indicates the linked review-record state, if one exists for this source document.',
  ranking_mode:
    'Explains whether ranking used only the target analyte or also incorporated secondary analyte evidence.',
  result_origin:
    'Explains whether this report came from a live run, cached recovery, demo-safe fallback, or degraded live result.',
  runtime_mode:
    'Shows which runtime policy supplied the current report during this session.'
}

export interface DashboardViewProps {
  statusLabel: string
  statusTone: 'neutral' | 'success' | 'warning' | 'error'
  isBusy: boolean
  phase: WorkflowPhase
  requestText: string
  composerText: string
  onRequestTextChange: (value: string) => void
  onConfirmRecognition: () => void
  onPrepareRun: () => void
  onConfirmRun: () => void
  onResetSession: () => void
  onSignOut: () => void
  accountIdentifier: string | null
  onSelectStarterExample: (value: string) => void
  showLegacyStudio: boolean
  onOpenStudio: () => void
  onOpenClassicStudio: () => void
  onOpenSurrogatePlayground: (recommendationId?: string | null) => void
  runButtonLabel: string
  draftActionLabel: string
  draftPrepared: boolean
  canConfirmRun: boolean
  runBlockerMessage: string | null
  followUpTurns: DashboardFollowUpTurn[]
  planSummary: ConversationPlanSummary
  promptRecognition: PromptRecognitionSummary
  source: DiscoverySource
  onSourceChange: (value: DiscoverySource) => void
  systemSpecs: SystemSpecs
  setSystemSpecs: Dispatch<SetStateAction<SystemSpecs>>
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
  issueList: (field: string) => WorkflowIssue[]
  pendingClarification: ClarificationQuestion[] | null
  clarificationAnswers: Record<string, string>
  setClarificationAnswers: Dispatch<SetStateAction<Record<string, string>>>
  onSubmitClarification: (overrideAnswers?: Record<string, string>) => void
  onDismissClarification: () => void
  steps: ResearchStep[]
  recommendations: Recommendation[]
  reportMeta: RecommendationReportMeta | null
  runtimeMode: AgentRuntimeMode | null
  resultOrigin: AgentResultOrigin | null
  staleReportNotice: string | null
  activeRecommendation: Recommendation | null
  activeRecommendationId: string | null
  onSelectRecommendation: (paperId: string) => void
  onRetryLive: () => void
  onReviewUpdatedPlan: () => void
  onExport: (recommendationId?: string) => void
  isExporting: boolean
  canExport: boolean
  exportError: string | null
  onDismissExportError: () => void
  recentRuns: RecentRunSummary[]
  activeRunRequestHash: string | null
  onLoadRecentRun: (requestHash: string) => void
  restoreNotice: WorkflowNotice | null
  onDismissRestoreNotice: () => void
  runOutcome: WorkflowOutcome | null
  onRunOutcomeAction: (() => void) | null
  runOutcomeActionLabel: string | null
  runtimeBanner:
    | {
        tone: 'info' | 'warning' | 'error'
        title: string
        message: string
        details: string[]
      }
    | null
  onDismissStaleReportNotice: () => void
  updateTargetSmiles: (value: string) => void
  resolveTargetSmilesName: () => void
  addImpurity: () => void
  updateImpurity: (compoundId: string, value: string) => void
  removeImpurity: (compoundId: string) => void
  resolveImpurityName: (compoundId: string) => void
}

function parseNullableNumber(value: string): number | null {
  const parsed = parseFloat(value)
  return Number.isNaN(parsed) ? null : parsed
}

function formatScorePercent(value: number | null | undefined): string {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : 'n/a'
}

function formatMetric(value: number | undefined | null, digits = 2): string {
  return typeof value === 'number' ? value.toFixed(digits) : 'n/a'
}

function formatRuntime(value: number | undefined | null): string {
  return typeof value === 'number' ? value.toFixed(1) : 'n/a'
}

function formatCompoundName(context?: CompoundContext | null): string {
  return context?.resolved_name || context?.input_label || context?.input_smiles || 'Unresolved'
}

function formatCompoundWeight(context?: CompoundContext | null): string {
  return typeof context?.molecular_weight === 'number'
    ? context.molecular_weight.toFixed(2)
    : 'Unavailable'
}

function formatCompoundConfidenceLabel(confidence?: string | null): string {
  switch (confidence) {
    case 'high':
      return 'High-confidence lookup'
    case 'medium':
      return 'Medium-confidence lookup'
    case 'low':
      return 'Low-confidence lookup'
    case 'unresolved':
      return 'Lookup unresolved'
    default:
      return 'Lookup unavailable'
  }
}

function compoundConfidenceTone(confidence?: string | null): 'muted' | 'neutral' | 'warning' | 'error' | 'success' {
  switch (confidence) {
    case 'high':
      return 'success'
    case 'medium':
      return 'neutral'
    case 'low':
      return 'warning'
    case 'unresolved':
      return 'warning'
    default:
      return 'muted'
  }
}

function formatSourceKindLabel(sourceKind?: string | null): string {
  switch (sourceKind) {
    case 'seeded':
      return 'Seeded source'
    case 'manual':
      return 'Manual source'
    case 'html':
      return 'HTML full text'
    case 'pdf':
      return 'PDF full text'
    default:
      return 'Unknown source'
  }
}

function formatTrustStateLabel(trustState?: string | null): string {
  switch (trustState) {
    case 'review_backed':
      return 'Review-backed'
    case 'seeded_corpus':
      return 'Seeded corpus'
    case 'open_access_extracted':
      return 'Open-access extract'
    case 'local_file_extracted':
      return 'Local extract'
    default:
      return 'Trust unavailable'
  }
}

function formatValidationStatusLabel(status?: string | null): string {
  switch (status) {
    case 'valid':
      return 'Valid'
    case 'invalid':
      return 'Invalid'
    case 'needs_review':
      return 'Needs review'
    case 'unvalidated':
    default:
      return 'Unvalidated'
  }
}

function formatRankingModeLabel(rankingMode?: string | null, impurityHandling?: string | null): string {
  if (impurityHandling === 'requested_but_untrusted') {
    return 'Target-only fallback'
  }
  if (rankingMode === 'target_plus_impurities') {
    return 'Mixture-aware ranking'
  }
  return 'Target-only ranking'
}

function formatReviewStateLabel(reviewState?: string | null): string {
  switch (reviewState) {
    case 'approved':
      return 'Approved review'
    case 'draft':
      return 'Draft review'
    case 'rejected':
      return 'Rejected review'
    case 'seeded':
      return 'Seeded record'
    default:
      return 'No review record'
  }
}

function formatSourceModeLabel(sourceMode?: string | null): string {
  switch (sourceMode) {
    case 'local_corpus':
      return 'Local corpus'
    case 'open_access':
      return 'Open access'
    case 'local_files':
      return 'Local files'
    default:
      return 'Unknown source mode'
  }
}

function formatCorpusOriginLabel(corpusOrigin?: string | null): string {
  switch (corpusOrigin) {
    case 'review_promoted':
      return 'Review-promoted corpus'
    case 'seeded':
      return 'Seeded corpus'
    default:
      return 'Corpus origin unavailable'
  }
}

function formatSkipStageLabel(stage?: string | null): string {
  switch (stage) {
    case 'screening':
      return 'Screening'
    case 'fetch':
      return 'Fetch'
    case 'extraction':
      return 'Extraction'
    default:
      return 'Skipped'
  }
}

function formatQueryIntentLabel(intent?: string | null): string {
  switch (intent) {
    case 'exact_request':
      return 'Exact request'
    case 'analyte_matrix_anchor':
      return 'Analyte and matrix'
    case 'family_expansion':
      return 'Family expansion'
    case 'matrix_relaxed_fallback':
      return 'Matrix relaxed'
    case 'context_repair':
      return 'Context repair'
    case 'user_supplied':
      return 'User supplied'
    default:
      return 'Query'
  }
}

function formatRuntimeModeLabel(runtimeMode: AgentRuntimeMode): string {
  switch (runtimeMode) {
    case 'cached':
      return 'Cached'
    case 'demo_safe':
      return 'Demo-safe'
    case 'live':
      return 'Live'
    default:
      return 'Unknown'
  }
}

function formatResultOriginLabel(origin: AgentResultOrigin): string {
  switch (origin) {
    case 'cached':
      return 'Cached result'
    case 'demo_safe':
      return 'Demo-safe result'
    case 'live_degraded':
      return 'Live degraded result'
    case 'live':
      return 'Live result'
    default:
      return 'Result origin unavailable'
  }
}

function runtimeModeTone(runtimeMode: AgentRuntimeMode): 'muted' | 'neutral' | 'warning' | 'success' {
  switch (runtimeMode) {
    case 'cached':
      return 'neutral'
    case 'demo_safe':
      return 'warning'
    case 'live':
      return 'success'
    default:
      return 'muted'
  }
}

function resultOriginTone(origin: AgentResultOrigin): 'muted' | 'neutral' | 'warning' | 'success' {
  switch (origin) {
    case 'cached':
      return 'neutral'
    case 'demo_safe':
    case 'live_degraded':
      return 'warning'
    case 'live':
      return 'success'
    default:
      return 'muted'
  }
}

function formatVerificationPostureLabel(recommendation: Recommendation): string {
  if (recommendation.review_summary?.record_state) {
    return formatReviewStateLabel(recommendation.review_summary.record_state)
  }
  return recommendation.trust.manual_verification_required
    ? 'Manual verification'
    : 'Verification complete'
}

function verificationTone(
  recommendation: Recommendation
): 'muted' | 'neutral' | 'warning' | 'error' | 'success' {
  switch (recommendation.review_summary?.record_state) {
    case 'approved':
      return 'success'
    case 'seeded':
      return 'neutral'
    case 'rejected':
      return 'error'
    case 'draft':
      return 'warning'
    default:
      return recommendation.trust.manual_verification_required ? 'warning' : 'success'
  }
}

function validationTone(
  status?: string | null
): 'muted' | 'neutral' | 'warning' | 'error' | 'success' {
  switch (status) {
    case 'valid':
      return 'success'
    case 'invalid':
      return 'error'
    case 'needs_review':
    case 'unvalidated':
      return 'warning'
    default:
      return 'muted'
  }
}

function detailToneFromPillTone(
  tone: 'muted' | 'neutral' | 'warning' | 'error' | 'success'
): 'default' | 'warning' | 'error' | 'success' {
  if (tone === 'warning' || tone === 'error' || tone === 'success') {
    return tone
  }
  return 'default'
}

function buildRankSummary(recommendation: Recommendation): string {
  return (
    recommendation.match_rationale?.summary ||
    recommendation.ranking_context.summary ||
    recommendation.rationale
  )
}

function countExperimentalSettings(recommendation: Recommendation): number {
  const methodParameters = recommendation.extraction.method_parameters
  const countedSettings = new Set<string>()

  if (methodParameters?.mobile_phase_a?.solvent) countedSettings.add('mobile_phase_a_solvent')
  if (methodParameters?.mobile_phase_a?.additive) countedSettings.add('mobile_phase_a_additive')
  if (typeof methodParameters?.mobile_phase_a?.ph_estimate === 'number') countedSettings.add('mobile_phase_a_ph')

  if (methodParameters?.mobile_phase_b?.solvent) countedSettings.add('mobile_phase_b_solvent')
  if (methodParameters?.mobile_phase_b?.additive) countedSettings.add('mobile_phase_b_additive')
  if (typeof methodParameters?.mobile_phase_b?.ph_estimate === 'number') countedSettings.add('mobile_phase_b_ph')

  if (typeof methodParameters?.flow_rate_ml_min === 'number') countedSettings.add('flow_rate')
  if (typeof methodParameters?.column_temperature_c === 'number') countedSettings.add('column_temperature')
  if (typeof methodParameters?.run_time_min === 'number') countedSettings.add('run_time')

  if (methodParameters?.gradient_profile?.length) {
    countedSettings.add('gradient_profile')
  } else if (typeof methodParameters?.isocratic_percent_b === 'number') {
    countedSettings.add('isocratic_percent_b')
  }

  return countedSettings.size
}

function countValidationEvidenceSnippets(recommendation: Recommendation): number {
  const snippetKeys = new Set<string>()
  const allSnippets = [
    recommendation.match_rationale?.supporting_snippet || null,
    ...recommendation.evidence_snippets
  ].filter(Boolean) as EvidenceSnippet[]

  allSnippets.forEach((snippet) => {
    snippetKeys.add(
      [
        snippet.text?.trim() || '',
        snippet.section_label?.trim() || '',
        typeof snippet.page_number === 'number' ? String(snippet.page_number) : ''
      ].join('::')
    )
  })

  return snippetKeys.size
}

function buildFitHighlightsSummary(recommendation: Recommendation): string {
  const highlights: string[] = []
  const matrixCompatibility = recommendation.match_rationale?.contextual_priors?.matrix_compatibility ?? null
  const detectorCompatibility = recommendation.match_rationale?.contextual_priors?.detector_compatibility ?? null
  const methodFamilyCompatibility =
    recommendation.match_rationale?.contextual_priors?.method_family_compatibility ?? null

  if (recommendation.match_rationale?.match_type === 'exact') {
    highlights.push('Exact molecular match')
  } else if (recommendation.match_rationale?.match_type === 'similarity') {
    highlights.push('Similarity match')
  }

  if (recommendation.score.matrix_fit >= 0.95 || (matrixCompatibility !== null && matrixCompatibility >= 0.95)) {
    highlights.push('Exact matrix match')
  } else if (recommendation.score.matrix_fit >= 0.8 || (matrixCompatibility !== null && matrixCompatibility >= 0.8)) {
    highlights.push('Good matrix match')
  }

  if (detectorCompatibility !== null && detectorCompatibility >= 0.95) {
    highlights.push('Detector match')
  } else if (detectorCompatibility !== null && detectorCompatibility >= 0.8) {
    highlights.push('Detector-compatible')
  }

  if (recommendation.score.system_match >= 0.95) {
    highlights.push('Strong hardware match')
  } else if (recommendation.score.system_match >= 0.8 || (methodFamilyCompatibility !== null && methodFamilyCompatibility >= 0.8)) {
    highlights.push('Good column/system match')
  }

  if (recommendation.recommended_method?.is_scaled) {
    highlights.push('Scaled to your system')
  }

  if (!highlights.length) {
    return buildRankSummary(recommendation)
  }

  return highlights.slice(0, 4).join(', ')
}

function formatEvidenceSnippetMeta(snippet: EvidenceSnippet): string {
  const parts = [
    snippet.section_label?.trim() || null,
    typeof snippet.page_number === 'number' ? `p. ${snippet.page_number}` : null
  ].filter(Boolean)
  return parts.length ? parts.join(' • ') : 'Evidence snippet'
}

function issueTotal(issueCounts?: { info: number; warning: number; error: number } | null): number {
  if (!issueCounts) {
    return 0
  }
  return issueCounts.info + issueCounts.warning + issueCounts.error
}

function uniqueStrings(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.map((value) => value?.trim()).filter(Boolean) as string[]))
}

function getRecommendationRuntime(recommendation: Recommendation): number | null {
  return (
    recommendation.recommended_method?.run_time_min ??
    recommendation.extraction.method_parameters?.run_time_min ??
    null
  )
}

function getRecommendationFlow(recommendation: Recommendation): number | null {
  return (
    recommendation.recommended_method?.flow_rate_ml_min ??
    recommendation.extraction.method_parameters?.flow_rate_ml_min ??
    null
  )
}

function collectWarningMessages(recommendation: Recommendation): string[] {
  return uniqueStrings([
    ...recommendation.trust.warning_summary,
    ...recommendation.extraction.warnings,
    ...(recommendation.recommended_method?.scaling_warnings || [])
  ])
}

function collectScalingNotes(recommendation: Recommendation): string[] {
  return uniqueStrings(recommendation.recommended_method?.scaling_notes || [])
}

function buildComparisonSummary(
  recommendation: Recommendation,
  topRecommendation: Recommendation | null
): string {
  if (!topRecommendation || topRecommendation.paper_id === recommendation.paper_id) {
    return 'Highest total fit for the current constraints.'
  }

  const scoreDelta = Math.max(
    0,
    Math.round((topRecommendation.score.total_score - recommendation.score.total_score) * 100)
  )
  const runtimeDelta = (() => {
    const topRuntime = getRecommendationRuntime(topRecommendation)
    const currentRuntime = getRecommendationRuntime(recommendation)
    if (topRuntime === null || currentRuntime === null) {
      return null
    }
    return currentRuntime - topRuntime
  })()

  const parts: string[] = []
  if (scoreDelta > 0) {
    parts.push(`${scoreDelta}% lower total score`)
  }
  if (runtimeDelta !== null && Math.abs(runtimeDelta) >= 0.1) {
    parts.push(
      runtimeDelta > 0
        ? `${runtimeDelta.toFixed(1)} min slower`
        : `${Math.abs(runtimeDelta).toFixed(1)} min faster`
    )
  }

  return parts.length ? parts.join(', ') : 'Alternative tradeoff candidate.'
}

function buildGradientSummary(recommendation: Recommendation): string {
  const gradientProfile =
    recommendation.recommended_method?.gradient_profile ||
    recommendation.extraction.method_parameters?.gradient_profile ||
    []

  if (gradientProfile.length) {
    return `${gradientProfile.length}-step gradient`
  }

  const isocraticPercentB = recommendation.extraction.method_parameters?.isocratic_percent_b
  if (typeof isocraticPercentB === 'number') {
    return `${isocraticPercentB}% B isocratic`
  }

  return 'Gradient unavailable'
}

function buildCoreMethodSummary(recommendation: Recommendation): string {
  const parts = [
    (() => {
      const phaseA = recommendation.extraction.method_parameters?.mobile_phase_a?.solvent
      const phaseB = recommendation.extraction.method_parameters?.mobile_phase_b?.solvent
      if (phaseA && phaseB) {
        return `${phaseA} / ${phaseB}`
      }
      return phaseA || phaseB || null
    })(),
    buildGradientSummary(recommendation),
    (() => {
      const flow = getRecommendationFlow(recommendation)
      return flow !== null ? `${formatMetric(flow)} mL/min` : null
    })(),
    (() => {
      const temperature = recommendation.extraction.method_parameters?.column_temperature_c
      return typeof temperature === 'number' ? `${formatMetric(temperature, 1)} °C` : null
    })()
  ].filter(Boolean)

  return parts.length ? parts.join(' • ') : 'Core method summary unavailable.'
}

function buildScalingSummary(recommendation: Recommendation): string {
  const notes = collectScalingNotes(recommendation)
  if (notes.length) {
    return notes[0]
  }

  const warnings = collectWarningMessages(recommendation)
  if (warnings.length) {
    return warnings[0]
  }

  if (recommendation.recommended_method?.is_scaled) {
    return 'Physics-based scaling was applied for the current system constraints.'
  }

  return 'No additional scaling adjustments were returned for this candidate.'
}

function buildTopFitDifferentiator(topRecommendation: Recommendation, runnerUpRecommendation: Recommendation): string {
  const scoreDimensions = [
    {
      label: 'system fit',
      delta: topRecommendation.score.system_match - runnerUpRecommendation.score.system_match
    },
    {
      label: 'analyte match',
      delta: topRecommendation.score.analyte_match - runnerUpRecommendation.score.analyte_match
    },
    {
      label: 'matrix fit',
      delta: topRecommendation.score.matrix_fit - runnerUpRecommendation.score.matrix_fit
    },
    {
      label: 'practical fit',
      delta: topRecommendation.score.practical_fit - runnerUpRecommendation.score.practical_fit
    }
  ].sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))

  const strongestScoreLead = scoreDimensions[0]
  if (strongestScoreLead && Math.abs(strongestScoreLead.delta) >= 0.03) {
    return `${Math.round(Math.abs(strongestScoreLead.delta) * 100)} points stronger on ${strongestScoreLead.label}.`
  }

  const topVerification = formatVerificationPostureLabel(topRecommendation)
  const runnerUpVerification = formatVerificationPostureLabel(runnerUpRecommendation)
  if (topVerification !== runnerUpVerification) {
    return `${topVerification} posture instead of ${runnerUpVerification.toLowerCase()}.`
  }

  return buildComparisonSummary(runnerUpRecommendation, topRecommendation)
}

function buildTrustEvidenceSummary(recommendation: Recommendation): string {
  const settingCount = countExperimentalSettings(recommendation)
  const evidenceCount = countValidationEvidenceSnippets(recommendation)
  return `${settingCount} experimental settings found. ${evidenceCount} evidence snippets found.`
}

function buildDecisionTraceSummary(recommendation: Recommendation): string {
  const trace = recommendation.decision_trace
  if (!trace) {
    return 'No backend decision trace was returned for this candidate.'
  }

  const parts = [
    trace.screening_summary,
    trace.dominant_differentiator,
    trace.beat_runner_up_summary,
    `Final ranking ${formatScorePercent(trace.ranking_score)}; viability ${formatScorePercent(trace.viability_score)}${
      typeof trace.retrieval_score === 'number' ? `; retrieval ${formatScorePercent(trace.retrieval_score)}` : ''
    }.`
  ].filter(Boolean)

  return parts.join(' ')
}

function buildQueryProvenanceSummary(queries: RecommendationQueryVariant[]): string {
  if (!queries.length) {
    return 'No search-query provenance was returned for this candidate.'
  }
  return queries
    .slice(0, 3)
    .map((query) => `${formatQueryIntentLabel(query.intent)}: ${query.query_text}`)
    .join(' | ')
}

function topScoreFeatures(features: RecommendationFeatureBreakdown, limit = 5) {
  const labels: Array<{ key: keyof RecommendationFeatureBreakdown; label: string; direction: 'positive' | 'penalty' }> = [
    { key: 'target_chemistry_fit', label: 'Target chemistry', direction: 'positive' },
    { key: 'impurity_compatibility', label: 'Impurity compatibility', direction: 'positive' },
    { key: 'system_fit', label: 'System fit', direction: 'positive' },
    { key: 'detector_compatibility', label: 'Detector compatibility', direction: 'positive' },

    { key: 'runtime_fit', label: 'Runtime fit', direction: 'positive' },
    { key: 'extraction_completeness', label: 'Extraction completeness', direction: 'positive' },
    { key: 'evidence_quality', label: 'Evidence quality', direction: 'positive' },
    { key: 'review_trust_prior', label: 'Review trust prior', direction: 'positive' },
    { key: 'literature_specificity', label: 'Literature specificity', direction: 'positive' },
    { key: 'missing_data_penalty', label: 'Missing data penalty', direction: 'penalty' }
  ]

  return labels
    .map((item) => ({ ...item, value: features[item.key] }))
    .sort((left, right) => right.value - left.value)
    .slice(0, limit)
}

function buildMethodSummaryLine(recommendation: Recommendation): string {
  const runtime = getRecommendationRuntime(recommendation)
  const flow = getRecommendationFlow(recommendation)
  const parts = [
    buildGradientSummary(recommendation),
    runtime !== null ? `${formatRuntime(runtime)} min runtime` : null,
    flow !== null ? `${formatMetric(flow)} mL/min flow` : null
  ].filter(Boolean)

  return parts.length ? parts.join(' • ') : buildCoreMethodSummary(recommendation)
}

function buildDummySurrogateSession(
  recommendation: Recommendation,
  topRecommendation: Recommendation | null
): DummySurrogateSession {
  const runtime = getRecommendationRuntime(recommendation) ?? 12
  const flow = getRecommendationFlow(recommendation) ?? 0.8
  const temperature = recommendation.extraction.method_parameters?.column_temperature_c ?? 32
  const totalFit = Math.round(recommendation.score.total_score * 100)
  const center = Math.max(1, runtime * 0.64)
  const spread = Math.max(0.4, runtime * 0.1)
  const scoreDelta = topRecommendation
    ? Math.max(0, Math.round((topRecommendation.score.total_score - recommendation.score.total_score) * 100))
    : 0

  return {
    sessionId: `demo-${recommendation.paper_id}`,
    state: 'ready',
    modeLabel: 'Desktop-inspired surrogate preview',
    simulationLabel: 'Simulated only. No sidecar calls. No scientific validity implied.',
    methodTitle: recommendation.title,
    prediction: {
      headline:
        totalFit >= 85
          ? 'Predicted separation posture stays inside the preferred operating band.'
          : 'Predicted separation posture is plausible but carries tighter operating margins.',
      summary: `Demo surrogate predicts a ${Math.max(72, totalFit - 4)}-${Math.min(
        98,
        totalFit + 3
      )}% selectivity-fit envelope with the current scaled method.`,
      predictedRetentionWindowMin: [
        parseFloat((center - spread).toFixed(1)),
        parseFloat((center + spread).toFixed(1))
      ],
      confidenceLabel:
        recommendation.trust.manual_verification_required || totalFit < 80
          ? 'Operator review still required'
          : 'Stable demo preview',
      signalQualityLabel:
        recommendation.score.practical_fit >= 0.8
          ? 'Clean synthetic peak-shape forecast'
          : 'Moderate synthetic peak broadening'
    },
    operatingWindows: [
      {
        id: 'runtime',
        label: 'Runtime window',
        testedWindow: `${Math.max(1, runtime - 1.5).toFixed(1)} to ${(runtime + 1.2).toFixed(1)} min`,
        posture: recommendation.score.practical_fit >= 0.8 ? 'stable' : 'watch',
        summary:
          recommendation.score.practical_fit >= 0.8
            ? 'Predicted retention remains centered with small timing drift.'
            : 'Faster pushes begin to compress selectivity in the demo model.'
      },
      {
        id: 'flow',
        label: 'Flow-rate window',
        testedWindow: `${Math.max(0.15, flow - 0.12).toFixed(2)} to ${(flow + 0.14).toFixed(2)} mL/min`,
        posture: recommendation.score.system_match >= 0.8 ? 'stable' : 'watch',
        summary:
          recommendation.score.system_match >= 0.8
            ? 'System-fit remains inside the synthetic pressure band.'
            : 'Higher flow begins to narrow the synthetic margin to the runner-up.'
      },
      {
        id: 'temperature',
        label: 'Temperature window',
        testedWindow: `${Math.max(20, temperature - 4).toFixed(0)} to ${(temperature + 5).toFixed(0)} °C`,
        posture: recommendation.score.matrix_fit >= 0.75 ? 'stable' : 'unstable',
        summary:
          recommendation.score.matrix_fit >= 0.75
            ? 'Matrix-fit signal stays coherent across a modest temperature sweep.'
            : 'Temperature drift quickly destabilizes the demo matrix-fit score.'
      }
    ],
    nextStepLabel: 'Run a narrow synthetic scan',
    nextStepSummary:
      scoreDelta > 0
        ? 'Use the demo scan to compare this candidate against the top fit under a tighter runtime window before investing in a wet-lab check.'
        : 'Use the demo scan to probe runtime and flow tolerance before moving into a wet-lab check.',
    warnings: [
      'Demo-only surrogate preview. It is a UX simulation, not a validated chromatographic model.',
      'The displayed operating windows are synthesized from frontend recommendation payloads only.'
    ]
  }
}

function buildExtractionStatusStep(recommendation: Recommendation): Pick<TrustRailStep, 'value' | 'detail' | 'tone'> {
  const hasMethodParameters = Boolean(recommendation.extraction.method_parameters)
  const hasSnippetPreview = Boolean(
    recommendation.match_rationale?.supporting_snippet || recommendation.evidence_snippets.length
  )
  const warningCount = collectWarningMessages(recommendation).length

  if (hasMethodParameters && hasSnippetPreview && warningCount === 0) {
    return {
      value: 'Extracted',
      detail: 'Method parameters and at least one supporting snippet were returned.',
      tone: 'success'
    }
  }

  if (hasMethodParameters && hasSnippetPreview) {
    return {
      value: 'Extracted with warnings',
      detail: `${warningCount} warning${warningCount === 1 ? '' : 's'} were attached to the extract.`,
      tone: 'warning'
    }
  }

  if (hasMethodParameters) {
    return {
      value: 'Method only',
      detail: 'Method parameters were returned without a visible supporting snippet.',
      tone: 'warning'
    }
  }

  return {
    value: 'Partial extract',
    detail: 'The candidate does not yet expose a full method summary.',
    tone: 'error'
  }
}

function buildTrustRailSteps(
  recommendation: Recommendation,
  options: {
    reportSourceMode: string
    resultOrigin: AgentResultOrigin | null
    rank: number
    topRecommendation: Recommendation | null
  }
): TrustRailStep[] {
  const extractionStatus = buildExtractionStatusStep(recommendation)
  const reviewLabel = recommendation.review_summary
    ? formatReviewStateLabel(recommendation.review_summary.record_state)
    : null
  const validationLabel = formatValidationStatusLabel(recommendation.trust.validation_status)
  const resultLabel = options.resultOrigin
    ? formatResultOriginLabel(options.resultOrigin)
    : 'Result origin unavailable'
  const scalingSummary = buildScalingSummary(recommendation)
  const rankLabel = options.rank === 0 ? 'Top fit' : `Rank ${options.rank + 1}`

  return [
    {
      id: 'source_origin',
      label: 'Source origin',
      value: formatSourceModeLabel(options.reportSourceMode),
      detail: `${formatSourceKindLabel(recommendation.source_kind)} returned as ${resultLabel.toLowerCase()}.`,
      tone: options.resultOrigin ? resultOriginTone(options.resultOrigin) : 'muted'
    },
    {
      id: 'extraction_status',
      label: 'Extraction status',
      value: extractionStatus.value,
      detail: extractionStatus.detail,
      tone: extractionStatus.tone
    },
    {
      id: 'validation_review',
      label: 'Validation and review',
      value: reviewLabel || validationLabel,
      detail: reviewLabel
        ? `${reviewLabel}. ${validationLabel}.`
        : recommendation.trust.manual_verification_required
          ? `${validationLabel}. Manual verification is still required before operational use.`
          : `${validationLabel}. No linked review record was returned.`,
      tone: reviewLabel
        ? verificationTone(recommendation)
        : validationTone(recommendation.trust.validation_status)
    },
    {
      id: 'scaling_system_fit',
      label: 'Scaling and system fit',
      value: recommendation.recommended_method?.is_scaled ? 'Scaled to system' : 'System-fit checked',
      detail: `System match ${formatScorePercent(recommendation.score.system_match)}. Practical fit ${formatScorePercent(recommendation.score.practical_fit)}. ${scalingSummary}`,
      tone:
        recommendation.score.system_match >= 0.8 && recommendation.score.practical_fit >= 0.75
          ? 'success'
          : recommendation.score.system_match >= 0.65
            ? 'neutral'
            : 'warning'
    },
    {
      id: 'recommendation_outcome',
      label: 'Recommendation outcome',
      value: rankLabel,
      detail: `${formatScorePercent(recommendation.score.total_score)} total fit. ${buildComparisonSummary(
        recommendation,
        options.topRecommendation
      )}`,
      tone: options.rank === 0 ? 'success' : 'neutral'
    },
    {
      id: 'corpus_reuse',
      label: 'Corpus reuse',
      value:
        recommendation.review_summary?.corpus_origin === 'review_promoted'
          ? 'Promoted corpus'
          : recommendation.trust.retrieval_ready
            ? 'Reuse ready'
            : 'Needs operator review',
      detail:
        recommendation.review_summary?.corpus_origin === 'review_promoted'
          ? 'This recommendation is already backed by a review-promoted corpus record.'
          : recommendation.review_summary?.review_record_id
            ? `Review record ${recommendation.review_summary.review_record_id} is linked to this source.`
            : 'No linked review record or promoted corpus entry was returned for this candidate.',
      tone:
        recommendation.review_summary?.corpus_origin === 'review_promoted'
          ? 'success'
          : recommendation.trust.retrieval_ready
            ? 'neutral'
            : 'warning'
    }
  ]
}

function outcomeTone(kind: WorkflowOutcome['kind']): 'info' | 'warning' | 'error' | 'success' {
  switch (kind) {
    case 'cached_result':
    case 'demo_safe_result':
      return 'info'
    case 'validation':
    case 'empty':
    case 'interrupted':
      return 'warning'
    case 'backend_error':
    case 'timeout':
      return 'error'
    default:
      return 'info'
  }
}

function trustTone(trustState?: string | null): 'muted' | 'neutral' | 'warning' | 'success' {
  switch (trustState) {
    case 'review_backed':
      return 'success'
    case 'seeded_corpus':
      return 'neutral'
    case 'open_access_extracted':
    case 'local_file_extracted':
    default:
      return 'warning'
  }
}

function rankingTone(
  rankingMode?: string | null,
  impurityHandling?: string | null
): 'muted' | 'neutral' | 'warning' | 'success' {
  if (impurityHandling === 'requested_but_untrusted') {
    return 'warning'
  }
  if (rankingMode === 'target_plus_impurities') {
    return 'success'
  }
  return 'muted'
}

function formatHardwareSummary(systemSpecs: SystemSpecs): string {
  const manufacturer =
    systemSpecs.columnManufacturer === 'Other'
      ? systemSpecs.customManufacturer?.trim() || 'Custom manufacturer'
      : systemSpecs.columnManufacturer
  const chemistry =
    systemSpecs.columnChemistry === 'Other'
      ? systemSpecs.customChemistry?.trim() || 'Custom chemistry'
      : systemSpecs.columnChemistry
  const dims = [
    systemSpecs.columnLengthMm ? `${systemSpecs.columnLengthMm} mm` : null,
    systemSpecs.columnIdMm ? `${systemSpecs.columnIdMm} mm ID` : null,
    systemSpecs.particleSizeUm ? `${systemSpecs.particleSizeUm} um` : null
  ]
    .filter(Boolean)
    .join(' / ')
  const detectorSummary = systemSpecs.detectorTypes.length
    ? systemSpecs.detectorTypes.join(', ')
    : 'No detectors selected'
  return [manufacturer, chemistry, dims, detectorSummary].filter(Boolean).join(' • ')
}

function formatStructureSummary(target: DiscoveryTarget): string {
  if (!target.targetSmiles.trim() && target.impurities.length === 0) {
    return 'Text-driven run'
  }
  const parts = [
    target.targetSmiles.trim() ? 'Target structure present' : null,
    target.impurities.length
      ? `${target.impurities.length} secondary analyte${target.impurities.length === 1 ? '' : 's'} added`
      : null
  ].filter(Boolean)
  return parts.join(' • ')
}

function formatMatrixSummary(target: DiscoveryTarget): string {
  return target.matrix === 'Other' ? target.customMatrix?.trim() || 'Other matrix' : target.matrix
}

function StatusPill({
  label,
  tone = 'muted'
}: {
  label: string
  tone?: 'muted' | 'neutral' | 'warning' | 'error' | 'success'
}) {
  const toneClass = {
    muted: 'border-border/90 bg-transparent text-muted-foreground',
    neutral: 'border-foreground/12 bg-background/70 text-foreground/80',
    warning:
      'border-amber-400/75 bg-amber-100/90 text-amber-950 dark:border-amber-400/70 dark:bg-amber-100/90 dark:text-amber-950',
    error:
      'border-rose-300/60 bg-rose-50/80 text-rose-900 dark:border-rose-500/35 dark:bg-rose-500/10 dark:text-rose-200',
    success:
      'border-emerald-400/70 bg-emerald-100/90 text-emerald-950 dark:border-emerald-400/70 dark:bg-emerald-100/90 dark:text-emerald-950'
  }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium leading-none',
        toneClass[tone]
      )}
    >
      {label}
    </span>
  )
}

function StatusPillWithTooltip({
  label,
  tone = 'muted',
  tooltipKey
}: {
  label: string
  tone?: 'muted' | 'neutral' | 'warning' | 'error' | 'success'
  tooltipKey: TooltipCopyKey
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <StatusPill label={label} tone={tone} />
      <Tooltip label={`${label} definition`} content={TOOLTIP_COPY[tooltipKey]} />
    </span>
  )
}

function NoticeBanner({
  tone,
  title,
  message,
  details = [],
  actionLabel,
  onAction,
  dismissLabel,
  onDismiss
}: {
  tone: 'info' | 'warning' | 'error' | 'success'
  title: string
  message: string
  details?: string[]
  actionLabel?: string
  onAction?: () => void
  dismissLabel?: string
  onDismiss?: () => void
}) {
  const toneClass = {
    info: 'border-primary/20 bg-primary/[0.05] shadow-[0_18px_42px_-36px_rgba(39,78,153,0.38)]',
    warning:
      'border-amber-300/75 bg-amber-50/95 text-amber-950 shadow-[0_18px_42px_-36px_rgba(120,80,22,0.45)] dark:border-amber-400/70 dark:bg-amber-100/95 dark:text-amber-950',
    error: 'border-destructive/25 bg-destructive/5 shadow-[0_18px_42px_-36px_rgba(120,20,20,0.45)] dark:border-destructive/35 dark:bg-destructive/10',
    success:
      'border-emerald-300/60 bg-emerald-50/80 shadow-[0_18px_42px_-36px_rgba(16,120,80,0.35)] dark:border-emerald-400/70 dark:bg-emerald-100/90 dark:text-emerald-950'
  }

  const iconTone = {
    info: 'text-primary',
    warning: 'text-amber-700 dark:text-amber-700',
    error: 'text-destructive',
    success: 'text-emerald-700 dark:text-emerald-700'
  }

  return (
    <div className={cn('rounded-xl border px-4 py-4 md:px-5 md:py-4', toneClass[tone])}>
      <div className="flex items-start gap-3">
        <AlertTriangle className={cn('mt-0.5 size-4 shrink-0', iconTone[tone])} />
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <p className="text-xs font-medium text-foreground/72">
              {title}
            </p>
            <p className="mt-1 text-sm leading-relaxed text-foreground/85">{message}</p>
          </div>
          {!!details.length && (
            <div className="space-y-1.5">
              {details.map((detail) => (
                <p key={detail} className="text-xs leading-relaxed text-foreground/70">
                  {detail}
                </p>
              ))}
            </div>
          )}
          {(actionLabel || dismissLabel) && (
            <div className="flex flex-wrap gap-2 pt-1">
              {actionLabel && onAction ? (
                <Button
                  onClick={onAction}
                  size="sm"
                  variant={tone === 'error' ? 'destructive' : 'outline'}
                  className="h-8 rounded-lg text-xs font-medium"
                >
                  {actionLabel}
                </Button>
              ) : null}
              {dismissLabel && onDismiss ? (
                <Button
                  onClick={onDismiss}
                  size="sm"
                  variant="ghost"
                  className="h-8 rounded-lg text-xs font-medium"
                >
                  {dismissLabel}
                </Button>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricTile({
  label,
  value,
  unit,
  emphasize = false
}: {
  label: string
  value: string
  unit?: string
  emphasize?: boolean
}) {
  return (
    <div className="rounded-md border border-border/80 bg-card/70 px-3 py-3 shadow-[0_10px_26px_-24px_rgba(49,58,91,0.34)]">
      <p className="text-[11px] font-medium text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          'mt-2 break-words text-[1.55rem] font-semibold leading-none text-foreground',
          emphasize && 'text-primary'
        )}
      >
        {value}
        {unit ? (
          <span className="ml-1 font-sans text-xs font-medium text-muted-foreground">
            {unit}
          </span>
        ) : null}
      </p>
    </div>
  )
}

function DetailField({
  label,
  value,
  tone = 'default',
  tooltipKey
}: {
  label: string
  value: string
  tone?: 'default' | 'success' | 'warning' | 'error'
  tooltipKey?: TooltipCopyKey
}) {
  const toneClass = {
    default: 'border-border/80 bg-card/55 text-foreground',
    success:
      'border-emerald-300/60 bg-emerald-50 text-emerald-950 dark:border-emerald-400/70 dark:bg-emerald-100/90 dark:text-emerald-950',
    warning:
      'border-amber-300/60 bg-amber-50 text-amber-950 dark:border-amber-400/70 dark:bg-amber-100/90 dark:text-amber-950',
    error:
      'border-destructive/20 bg-destructive/5 text-destructive dark:border-destructive/35 dark:bg-destructive/10'
  }

  return (
    <div className={cn('min-w-0 rounded-md px-1 py-1.5', toneClass[tone])}>
      <div className="flex items-center gap-1.5">
        <p className="text-[11px] font-medium text-muted-foreground">
          {label}
        </p>
        {tooltipKey ? (
          <Tooltip label={`${label} definition`} content={TOOLTIP_COPY[tooltipKey]} />
        ) : null}
      </div>
      <p className="mt-2 break-words text-sm font-medium leading-relaxed">{value}</p>
    </div>
  )
}

function DisclosurePanel({
  title,
  description,
  defaultOpen = false,
  children
}: {
  title: string
  description?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  return (
    <details open={defaultOpen} className="group rounded-md border border-border bg-background/90">
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-4 py-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-primary/75">
            {title}
          </p>
          {description ? <p className="mt-1 text-sm leading-relaxed text-foreground/75">{description}</p> : null}
        </div>
        <ChevronDown className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border px-4 py-4">{children}</div>
    </details>
  )
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-foreground/80">{label}</p>
        <p className="text-sm font-semibold text-foreground">{formatScorePercent(value)}</p>
      </div>
      <div className="h-2 rounded-full bg-muted">
        <div
          className="h-2 rounded-full bg-primary transition-all"
          style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }}
        />
      </div>
    </div>
  )
}

function FieldIssues({ issues }: { issues: WorkflowIssue[] }) {
  if (!issues.length) {
    return null
  }

  return (
    <div className="space-y-1.5">
      {issues.map((issue) => (
        <p
          key={issue.id}
          className={cn(
            'text-xs leading-relaxed',
            issue.severity === 'error' ? 'text-destructive' : 'text-muted-foreground'
          )}
        >
          {issue.message}
        </p>
      ))}
    </div>
  )
}

function ReportZone({
  eyebrow,
  title,
  description,
  actions,
  children
}: {
  eyebrow: string
  title: string
  description: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="px-1 py-1">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-primary/75">
            {eyebrow}
          </p>
          <h3 className="mt-2 text-xl font-semibold tracking-tight text-foreground">{title}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2 md:justify-end">{actions}</div> : null}
      </div>
      <div className="mt-4 border-t border-border/70 pt-4">{children}</div>
    </section>
  )
}

function TrustRail({ steps }: { steps: TrustRailStep[] }) {
  const toneClass: Record<TrustRailStep['tone'], string> = {
    muted: 'border-border bg-background text-muted-foreground',
    neutral: 'border-foreground/12 bg-background text-foreground/80',
    warning:
      'border-amber-400/75 bg-amber-100/90 text-amber-950 dark:border-amber-400/70 dark:bg-amber-100/90 dark:text-amber-950',
    error:
      'border-rose-300/60 bg-rose-50/80 text-rose-900 dark:border-rose-500/35 dark:bg-rose-500/10 dark:text-rose-200',
    success:
      'border-emerald-400/70 bg-emerald-100/90 text-emerald-950 dark:border-emerald-400/70 dark:bg-emerald-100/90 dark:text-emerald-950'
  }

  return (
    <details className="group rounded-xl border border-border bg-card/80" open>
      <summary className="flex cursor-pointer list-none flex-col gap-3 px-4 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-medium text-primary/75">
              Trust rail
            </p>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              Trace the decision path from document origin through extraction, validation, scaling, and corpus reuse.
            </p>
          </div>
          <ChevronDown className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {steps.map((step, index) => (
            <div
              key={step.id}
              className={cn('flex items-center gap-3 rounded-lg border px-3 py-3 text-left', toneClass[step.tone])}
            >
              <div className="flex shrink-0 items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full border border-current/20 text-[10px] font-semibold">
                  {index + 1}
                </span>
                {index < steps.length - 1 ? (
                  <ArrowRight className="hidden size-3 text-current/45 xl:block" />
                ) : null}
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-medium text-current/75">
                  {step.label}
                </p>
                <p className="mt-1 text-sm font-medium text-current">{step.value}</p>
              </div>
            </div>
          ))}
        </div>
      </summary>
      <div className="border-t border-border px-4 py-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {steps.map((step) => (
            <div key={`${step.id}-detail`} className="rounded-xl border border-border bg-background px-4 py-4">
              <p className="text-[11px] font-medium text-muted-foreground">
                {step.label}
              </p>
              <p className="mt-2 text-sm font-semibold text-foreground">{step.value}</p>
              <p className="mt-2 text-sm leading-relaxed text-foreground/78">{step.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </details>
  )
}

const STARTER_EXAMPLES = [
  'Quantification of Metformin in human plasma by HPLC-MS/MS for a bioequivalence study',
  'Develop a short HPLC-UV method for caffeine in energy drink samples with robust peak shape'
] as const

function EmptyState(props: {
  onSelectExample: (value: string) => void
}) {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col items-center justify-center px-2 pb-12 pt-8 text-center md:pt-12">
      <h2 className="text-[1.75rem] font-semibold tracking-tight text-foreground md:text-[2rem]">
        What would you like to separate?
      </h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
        Describe the target, matrix, and practical constraints. The agent will retrieve relevant literature, scale it to your system, find the best fit and extract their settings.
      </p>
      <div className="mt-12 grid w-full max-w-2xl gap-4 sm:grid-cols-2">
        {STARTER_EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => props.onSelectExample(example)}
            className="group flex min-h-[8.25rem] items-start rounded-xl border border-border bg-background px-5 py-5 text-left text-[1.05rem] leading-7 text-foreground/68 shadow-[0_18px_48px_-34px_rgba(49,58,91,0.45)] transition hover:-translate-y-0.5 hover:border-primary/45 hover:text-foreground hover:shadow-[0_22px_58px_-34px_rgba(49,58,91,0.6)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="line-clamp-4">{example}</span>
            <ArrowUpRight className="ml-auto mt-1 size-4 shrink-0 opacity-0 transition group-hover:opacity-70" />
          </button>
        ))}
      </div>
    </div>
  )
}

const TURN_VARIANTS = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.42,
      ease: [0.22, 1, 0.36, 1]
    }
  }
} as const

const RESULT_VARIANTS = {
  hidden: { opacity: 0, y: 22, scale: 0.985 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.45,
      ease: [0.22, 1, 0.36, 1]
    }
  }
} as const

type MotionPreset = 'none' | 'recognition' | 'typing' | 'plan' | 'run' | 'result'

function CopilotTurn({
  speaker,
  title,
  body,
  tone = 'default',
  motionPreset = 'none',
  typewriter = false,
  plain = false,
  icon,
  iconTone = 'default',
  children
}: {
  speaker: 'agent' | 'user'
  title: string
  body: string
  tone?: 'default' | 'warning'
  motionPreset?: MotionPreset
  typewriter?: boolean
  plain?: boolean
  icon?: ReactNode
  iconTone?: 'default' | 'destructive'
  children?: ReactNode
}) {
  const prefersReducedMotion = useReducedMotion()
  const animateTurn = motionPreset !== 'none' && !prefersReducedMotion
  const turnBody = typewriter ? (
    <TypewriterText
      as="p"
      text={body}
      active
      completionKey={`${title}-${body}`}
      className="mt-2 text-sm leading-relaxed text-foreground/85"
    />
  ) : (
    <p className="mt-2 text-sm leading-relaxed text-foreground/85">{body}</p>
  )

  const content = (
    <div
      className={cn(
        'flex gap-3',
        speaker === 'user' ? 'justify-end' : 'justify-start'
      )}
    >
      {speaker === 'agent' ? (
        <div className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-full border',
          iconTone === 'destructive'
            ? 'border-destructive/30 bg-destructive/10 text-destructive'
            : 'border-primary/20 bg-primary/10 text-primary'
        )}>
          {icon ?? <Workflow className="size-4" />}
        </div>
      ) : null}
      <div
        className={cn(
          'min-w-0 rounded-2xl border px-4 py-3',
          speaker === 'agent'
            ? plain
              ? 'max-w-[min(48rem,100%)] border-transparent bg-transparent px-0 py-0'
              : 'max-w-[min(48rem,100%)] border-border bg-card/75 shadow-[0_16px_42px_-36px_rgba(49,58,91,0.42)]'
            : 'max-w-[min(42rem,82%)] border-primary/15 bg-primary/[0.08] shadow-[0_16px_42px_-38px_rgba(39,78,153,0.34)]',
          tone === 'warning'
            ? 'border-amber-300/70 bg-amber-50/90 dark:border-amber-400/70 dark:bg-amber-100/90'
            : ''
        )}
      >
        {title ? <p className="text-xs font-medium text-muted-foreground">{title}</p> : null}
        {turnBody}
        {children ? <div className="mt-4">{children}</div> : null}
      </div>
      {speaker === 'user' ? (
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-background text-foreground">
          <MessageSquare className="size-4" />
        </div>
      ) : null}
    </div>
  )

  if (!animateTurn) {
    return content
  }

  return (
    <motion.div
      variants={motionPreset === 'result' ? RESULT_VARIANTS : TURN_VARIANTS}
      initial="hidden"
      animate="visible"
      exit="hidden"
    >
      {content}
    </motion.div>
  )
}

function StageAcceptedMarker({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pl-11">
      <span className="h-px w-8 bg-border" aria-hidden="true" />
      <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/70 bg-emerald-100/95 px-3 py-1 text-xs font-semibold text-emerald-950 shadow-[0_10px_28px_-24px_rgba(16,120,80,0.55)] dark:border-emerald-400/70 dark:bg-emerald-100/95 dark:text-emerald-950">
        <CheckCircle2 className="size-3.5" />
        {label}
      </div>
    </div>
  )
}

function recognitionTone(status: RecognitionState): 'muted' | 'neutral' | 'warning' | 'success' {
  switch (status) {
    case 'recognized':
      return 'success'
    case 'recognizing':
      return 'neutral'
    case 'ambiguous':
    case 'unresolved':
    case 'error':
      return 'warning'
    default:
      return 'muted'
  }
}

function recognitionLabel(status: RecognitionState): string {
  switch (status) {
    case 'recognized':
      return 'recognized'
    case 'recognizing':
      return 'recognizing'
    case 'ambiguous':
      return 'ambiguous'
    case 'unresolved':
      return 'unresolved'
    case 'error':
      return 'error'
    default:
      return status
  }
}

function extractSmilesAtoms(smiles: string): string[] {
  return (smiles.match(/\[[^\]]+\]|Br|Cl|[A-Z][a-z]?|[cnops]/g) || [])
    .map((token) => token.replace(/^\[|\]$/g, '').replace(/[@+\-0-9H]/g, ''))
    .filter(Boolean)
    .slice(0, 10)
}

function ChemicalStructurePreview({
  analyte,
  compact = false
}: {
  analyte: RecognizedAnalyte
  compact?: boolean
}) {
  const atoms = extractSmilesAtoms(analyte.resolvedSmiles || '')

  if (analyte.structurePreviewState === 'loading') {
    return (
      <div className="flex h-24 items-center justify-center rounded-xl border border-dashed border-border bg-card/40 text-xs text-muted-foreground motion-reduce:transition-none">
        <Loader2 className="mr-2 size-3 animate-spin" />
        Resolving structure preview
      </div>
    )
  }

  if (analyte.structurePreviewState !== 'ready' || atoms.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center rounded-xl border border-dashed border-border bg-card/40 px-3 text-center text-xs text-muted-foreground motion-reduce:transition-none">
        Structure preview unavailable
      </div>
    )
  }

  const width = compact ? 220 : 320
  const height = compact ? 96 : 128
  const step = Math.max(24, Math.min(42, Math.floor((width - 48) / Math.max(atoms.length - 1, 1))))

  return (
    <div className="rounded-xl border border-primary/10 bg-gradient-to-br from-primary/[0.06] via-background to-card p-2 transition-all duration-200 motion-reduce:transition-none">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full">
        {atoms.map((atom, index) => {
          const x = 24 + index * step
          const y = 24 + ((index % 2) * 20)
          const nextX = 24 + (index + 1) * step
          const nextY = 24 + (((index + 1) % 2) * 20)
          return (
            <g key={`${atom}-${index}`}>
              {index < atoms.length - 1 ? (
                <line
                  x1={x + 8}
                  y1={y + 20}
                  x2={nextX - 8}
                  y2={nextY + 20}
                  stroke="currentColor"
                  strokeOpacity="0.24"
                  strokeWidth="2"
                />
              ) : null}
              <circle cx={x} cy={y + 20} r="12" fill="currentColor" fillOpacity={atom === 'C' ? 0.08 : 0.14} />
              <text
                x={x}
                y={y + 24}
                textAnchor="middle"
                fontSize="11"
                fontWeight="700"
                fill="currentColor"
              >
                {atom}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

function RecognitionSurface({
  recognition,
  compact = false
}: {
  recognition: PromptRecognitionSummary
  compact?: boolean
}) {
  const hasContent =
    recognition.analytes.length > 0 ||
    recognition.matrix ||
    recognition.detector ||
    recognition.runtime ||
    recognition.sourceMode

  if (!hasContent) {
    return null
  }

  const contextFields = [
    recognition.matrix,
    recognition.detector,
    recognition.runtime,
    recognition.sourceMode
  ].filter(Boolean)
  const primaryAnalyte =
    recognition.analytes.find((analyte) => analyte.status === 'recognized') || recognition.analytes[0] || null
  const summaryParts = [
    primaryAnalyte?.resolvedName || primaryAnalyte?.value,
    recognition.matrix?.value,
    recognition.detector?.value
  ].filter(Boolean)

  if (compact) {
    return (
      <details className="group rounded-xl border border-border bg-background/70 px-3 py-2.5 transition-colors open:bg-card/45">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-medium text-muted-foreground">Recognized inputs</p>
            <p className="mt-0.5 truncate text-sm text-foreground/84">
              {summaryParts.length ? summaryParts.join(' • ') : 'Recognition details available'}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {primaryAnalyte ? (
              <StatusPill label={recognitionLabel(primaryAnalyte.status)} tone={recognitionTone(primaryAnalyte.status)} />
            ) : null}
            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
          </div>
        </summary>
        <div className="mt-3 border-t border-border/70 pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-medium text-muted-foreground">Details</p>
            {contextFields.map((field) => (
              <StatusPill
                key={`${field?.field}-${field?.value}`}
                label={`${field?.field === 'source_mode' ? 'Source' : field?.field}: ${field?.value}`}
                tone="muted"
              />
            ))}
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {recognition.analytes.map((analyte) => (
              <div
                key={analyte.id}
                className="rounded-lg border border-border/80 bg-background/80 px-3 py-2.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {analyte.resolvedName || analyte.value}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {analyte.resolvedSmiles || 'SMILES unresolved'}
                    </p>
                  </div>
                  <StatusPill label={recognitionLabel(analyte.status)} tone={recognitionTone(analyte.status)} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </details>
    )
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-background/88 px-4 py-4 transition-all duration-200 motion-reduce:transition-none">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-medium text-muted-foreground">
          Recognition
        </p>
        {contextFields.map((field) => (
          <StatusPill
            key={`${field?.field}-${field?.value}`}
            label={`${field?.field === 'source_mode' ? 'Source' : field?.field}: ${field?.value}`}
            tone="muted"
          />
        ))}
      </div>
      <div className={cn('grid gap-3', compact ? 'md:grid-cols-1' : 'md:grid-cols-2')}>
        {recognition.analytes.map((analyte) => (
          <div
            key={analyte.id}
            className="rounded-xl border border-border/80 bg-card/40 p-3 transition-all duration-200 motion-reduce:transition-none"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{analyte.resolvedName || analyte.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {analyte.field === 'impurity' ? 'Recognized secondary analyte' : 'Recognized analyte'}
                </p>
              </div>
              <StatusPill label={recognitionLabel(analyte.status)} tone={recognitionTone(analyte.status)} />
            </div>
            <div className="mt-3 space-y-3">
              {!compact ? <ChemicalStructurePreview analyte={analyte} compact={compact} /> : null}
              <div className="space-y-1 text-sm leading-relaxed text-foreground/78">
                <p>
                  <span className="font-medium text-foreground">SMILES:</span>{' '}
                  {analyte.resolvedSmiles || 'Unresolved'}
                </p>
                <p>
                  <span className="font-medium text-foreground">Provenance:</span> {analyte.provenance}
                </p>
                <p>
                  <span className="font-medium text-foreground">Confidence:</span> {analyte.confidenceLabel}
                </p>
                {analyte.lookupSource ? (
                  <p>
                    <span className="font-medium text-foreground">Lookup:</span> {analyte.lookupSource}
                  </p>
                ) : null}
                {analyte.ambiguityCandidates?.length ? (
                  <p>
                    <span className="font-medium text-foreground">Candidates:</span>{' '}
                    {analyte.ambiguityCandidates.join(', ')}
                  </p>
                ) : null}
                {analyte.lookupError ? (
                  <p className="text-destructive">{analyte.lookupError}</p>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SourceModeToggle({
  value,
  onChange,
  disabled
}: {
  value: DiscoverySource
  onChange: (value: DiscoverySource) => void
  disabled?: boolean
}) {
  const isLocal = value === 'local_corpus'

  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-border bg-background/80 p-1">
      {([
        { value: 'local_corpus' as const, label: 'Corpus', icon: Library },
        { value: 'open_access' as const, label: 'Open', icon: Search }
      ]).map((option) => {
        const selected = value === option.value
        const Icon = option.icon
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option.value)}
            aria-pressed={selected}
            className={cn(
              'inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 sm:h-7 sm:px-2.5',
              selected
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground',
              disabled && 'pointer-events-none opacity-60'
            )}
          >
            <Icon className="size-3" />
            {option.label}
          </button>
        )
      })}
      <span className="sr-only">
        Source mode is {isLocal ? 'Local corpus' : 'Open access'}
      </span>
    </div>
  )
}

function AgentPlanTurn({
  summary,
  draftPrepared,
  canConfirmRun,
  runBlockerMessage,
  isBusy,
  onConfirmRun,
  hasUnresolvedQuestions,
  onAnswerUnresolved,
  onOpenSettings
}: {
  summary: ConversationPlanSummary
  draftPrepared: boolean
  canConfirmRun: boolean
  runBlockerMessage: string | null
  isBusy: boolean
  onConfirmRun: () => void
  hasUnresolvedQuestions: boolean
  onAnswerUnresolved: () => void
  onOpenSettings: (tab: 'hardware' | 'structures' | 'run') => void
}) {
  const visibleFields = summary.fields.filter(
    (field) =>
      field.id !== 'sourceMode' &&
      field.id !== 'defaults' &&
      field.id !== 'unresolved' &&
      !(field.id === 'impurities' && field.value === 'None specified')
  )

  return (
    <CopilotTurn
      speaker="agent"
      title="Implementation plan"
      body={summary.readinessSummary}
      motionPreset="plan"
      plain
    >
      <div className="space-y-3">
        <div className="border-t border-border/70 pt-3">
          <div className="mt-3 flex flex-wrap gap-2">
            {visibleFields.map((field) => (
              <button
                key={field.id}
                type="button"
                onClick={() => {
                  if (field.id === 'hardware') onOpenSettings('hardware')
                  if (field.id === 'runtime' || field.id === 'matrix' || field.id === 'detector') onOpenSettings('run')
                  if (field.id === 'analytes') onOpenSettings('structures')
                }}
                className="inline-flex max-w-full items-center gap-2 rounded-full border border-border bg-card/70 px-2.5 py-1.5 text-left text-xs text-foreground/82 shadow-[0_8px_22px_-20px_rgba(49,58,91,0.42)] transition-all duration-200 hover:-translate-y-0.5 hover:bg-card hover:shadow-[0_14px_28px_-24px_rgba(49,58,91,0.5)] active:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25"
              >
                <span className="shrink-0 text-muted-foreground">{field.label}</span>
                <span className="truncate font-medium">{field.value}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => {
              if (!canConfirmRun && hasUnresolvedQuestions) {
                onAnswerUnresolved()
                return
              }
              onConfirmRun()
            }}
            disabled={isBusy}
            className="h-9 rounded-lg text-[11px] font-medium transition-transform active:scale-[0.98]"
          >
            {isBusy ? <Loader2 className="mr-2 size-3 animate-spin" /> : <ArrowRight className="mr-2 size-3" />}
            Confirm and run
          </Button>
          <Button
            onClick={() => onOpenSettings('hardware')}
            variant="ghost"
            className="h-9 rounded-lg text-[11px] font-medium transition-transform hover:-translate-y-0.5 active:scale-[0.98]"
          >
            Revise hardware
          </Button>
          <Button
            onClick={() => onOpenSettings('structures')}
            variant="ghost"
            className="h-9 rounded-lg text-[11px] font-medium transition-transform hover:-translate-y-0.5 active:scale-[0.98]"
          >
            Revise recognized details
          </Button>
          <Button
            onClick={onAnswerUnresolved}
            variant="ghost"
            className="h-9 rounded-lg text-[11px] font-medium transition-transform hover:-translate-y-0.5 active:scale-[0.98]"
          >
            {hasUnresolvedQuestions ? 'Answer unresolved question' : 'Ask a follow-up question'}
          </Button>
        </div>
        {runBlockerMessage ? (
          <p className="text-xs leading-5 text-amber-700 dark:text-amber-300">
            {runBlockerMessage}
          </p>
        ) : null}
      </div>
    </CopilotTurn>
  )
}

const LC_MODES = ['RP-LC', 'HILIC', 'Normal Phase'] as const

function ClarificationWorkspace(props: {
  requestText: string
  pendingClarification: ClarificationQuestion[] | null
  clarificationAnswers: Record<string, string>
  setClarificationAnswers: Dispatch<SetStateAction<Record<string, string>>>
  onSubmitClarification: (overrideAnswers?: Record<string, string>) => void
  onDismissClarification: () => void
}) {
  const [submittedClarifications, setSubmittedClarifications] = useState<Array<{ id: string; answer: string }>>([])
  const [addressedQuestions, setAddressedQuestions] = useState<Record<string, string>>({})
  // Snapshot of the last active question set — kept visible (greyed out) after submission.
  const [frozenQuestions, setFrozenQuestions] = useState<ClarificationQuestion[] | null>(null)

  const questions = props.pendingClarification ?? []
  const activeIds = useMemo(() => new Set(questions.map((q) => q.id)), [questions])

  // Reset when a new active question set arrives (new pendingClarification reference).
  // Do NOT reset on requestText changes — applyClarificationAnswers appends to requestText
  // which would wipe frozenQuestions immediately after they are saved.
  useEffect(() => {
    if (props.pendingClarification && props.pendingClarification.length > 0) {
      setSubmittedClarifications([])
      setAddressedQuestions({})
      setFrozenQuestions(null)
    }
  }, [props.pendingClarification])

  // Filter stale addressed entries to only count IDs from the current active set
  const currentAddressed = useMemo(
    () => Object.fromEntries(Object.entries(addressedQuestions).filter(([id]) => activeIds.has(id))),
    [addressedQuestions, activeIds]
  )

  const displayQuestions = questions.length > 0 ? questions : (frozenQuestions ?? [])
  const isCompleted = questions.length === 0 && frozenQuestions !== null

  const markAddressed = (questionId: string, answer: string) => {
    if (answer.trim()) {
      setSubmittedClarifications((current) => [
        ...current.filter((item) => item.id !== questionId),
        { id: questionId, answer: answer.trim() }
      ])
    }
    const next = { ...addressedQuestions, [questionId]: answer }
    setAddressedQuestions(next)
    const nextCurrent = Object.fromEntries(Object.entries(next).filter(([id]) => activeIds.has(id)))
    if (questions.length > 0 && Object.keys(nextCurrent).length >= questions.length) {
      setFrozenQuestions([...questions])
      props.onSubmitClarification(nextCurrent)
    }
  }

  if (!displayQuestions.length) {
    return null
  }

  return (
    <section id="clarification-workspace" className="space-y-4">
      {displayQuestions.map((question) => {
        const isAddressed = isCompleted || question.id in currentAddressed
        const isLcModes = question.id === 'local_modes'
        const selectedModes = isLcModes
          ? (props.clarificationAnswers[question.id] || '').split(',').map((m) => m.trim()).filter(Boolean)
          : []

        const toggleMode = (mode: string) => {
          const next = selectedModes.includes(mode)
            ? selectedModes.filter((m) => m !== mode)
            : [...selectedModes, mode]
          props.setClarificationAnswers((current) => ({
            ...current,
            [question.id]: next.join(', ')
          }))
        }

        return (
          <div key={question.id} className={cn('space-y-3', isAddressed && 'opacity-50')}>
            <CopilotTurn
              speaker="agent"
              title="Clarification needed"
              body={question.question}
              icon={<AlertCircle className="size-4" />}
              iconTone="destructive"
            >
              {!isAddressed && !isCompleted && (isLcModes ? (
                <div className="flex flex-wrap gap-2">
                  {LC_MODES.map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => toggleMode(mode)}
                      className={cn(
                        'h-8 rounded-md border px-3 text-xs font-medium transition-colors',
                        selectedModes.includes(mode)
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border bg-background text-foreground hover:bg-muted'
                      )}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              ) : (
                <Input
                  value={props.clarificationAnswers[question.id] || ''}
                  onChange={(event) =>
                    props.setClarificationAnswers((current) => ({
                      ...current,
                      [question.id]: event.target.value
                    }))
                  }
                  placeholder={question.placeholder}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      markAddressed(question.id, props.clarificationAnswers[question.id] || '')
                    }
                  }}
                />
              ))}
            </CopilotTurn>
            {submittedClarifications
              .filter((item) => item.id === question.id)
              .map((item, index) => (
                <CopilotTurn
                  key={`${item.id}-${index}`}
                  speaker="user"
                  title="Your clarification"
                  body={item.answer}
                />
              ))}
            {!isCompleted && (isAddressed ? (
              <div className="flex items-center gap-2 pl-14 text-xs text-muted-foreground">
                <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                <span>Noted</span>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2 pl-14">
                <Button
                  onClick={() => markAddressed(question.id, props.clarificationAnswers[question.id] || '')}
                  className="h-9 rounded-lg text-[11px] font-medium"
                >
                  <ArrowUpRight className="mr-2 size-3" />
                  Update plan
                </Button>
                <Button
                  onClick={() => markAddressed(question.id, '')}
                  variant="ghost"
                  className="h-9 rounded-lg text-[11px] font-medium"
                >
                  Leave blank
                </Button>
              </div>
            ))}
          </div>
        )
      })}
    </section>
  )
}

function LiveRunWorkspace({
  steps,
  hasPreservedReport: _hasPreservedReport
}: {
  steps: ResearchStep[]
  hasPreservedReport: boolean
}) {
  const prefersReducedMotion = useReducedMotion()
  const activeStep = steps.find((step) => step.status === 'active')
  const completedSteps = steps.filter((step) => step.status === 'completed')
  const pendingSteps = steps.filter((step) => step.status !== 'completed' && step.status !== 'active')

  return (
    <section className="border-t border-border/70 pt-4">
      <div className="rounded-xl border border-primary/20 bg-primary/[0.045] px-4 py-4 shadow-[0_18px_42px_-34px_rgba(39,78,153,0.34)]">
        <div className="flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-background/80 text-primary shadow-[0_10px_22px_-20px_rgba(39,78,153,0.48)]">
            <Loader2 className="size-5 animate-spin" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-primary/75">
              live run
            </p>
            <p className="mt-2 text-base font-semibold text-foreground">
              {activeStep?.label || 'Running discovery'}
            </p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              {activeStep?.detail || 'The agent is advancing through the existing retrieval and ranking pipeline.'}
            </p>
            <p className="mt-3 text-xs font-medium text-primary/75">
              Reading sources, checking extractable method details, and preparing the next scored state.
            </p>
          </div>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-primary/10">
          {prefersReducedMotion ? (
            <div className="h-full w-2/5 rounded-full bg-primary/55" />
          ) : (
            <motion.div
              className="h-full w-1/3 rounded-full bg-primary/65"
              animate={{ x: ['-120%', '320%'] }}
              transition={{ duration: 1.65, repeat: Number.POSITIVE_INFINITY, ease: 'easeInOut' }}
            />
          )}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {completedSteps.length ? (
          <div className="space-y-2">
            <p className="text-[11px] font-medium text-muted-foreground">Completed</p>
            {completedSteps.map((step) => (
              <div key={step.id} className="flex items-start gap-2 text-sm text-foreground/78">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-700 dark:text-emerald-300" />
                <div className="min-w-0">
                  <p>{step.label}</p>
                  {step.detail ? (
                    <p className="text-xs leading-relaxed text-muted-foreground">{step.detail}</p>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : null}
        {pendingSteps.length ? (
          <div className="space-y-2">
            <p className="text-[11px] font-medium text-muted-foreground">Remaining</p>
            {pendingSteps.map((step) => (
              <div key={step.id} className="flex items-start gap-2 text-sm text-muted-foreground">
                <Clock3 className="mt-0.5 size-4 shrink-0" />
                <span>{step.label}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function CompoundEvidencePanel({
  targetContext,
  impurityContexts,
  trace
}: {
  targetContext: CompoundContext | null
  impurityContexts: CompoundContext[]
  trace: ExternalEvidenceTrace | null
}) {
  const sourceLabels = trace
    ? [
        `${trace.source_clients_succeeded.length} succeeded`,
        `${trace.source_clients_failed.length} failed`
      ]
    : []

  return (
    <div className="rounded-xl border border-border/70 bg-card/75 px-4 py-4 shadow-[0_16px_44px_-38px_rgba(49,58,91,0.42)]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-primary/70">
            Compound intelligence
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {targetContext ? (
            <StatusPill label={formatCompoundConfidenceLabel(targetContext.confidence)} tone={compoundConfidenceTone(targetContext.confidence)} />
          ) : null}
          {sourceLabels.map((label) => (
            <StatusPill key={label} label={label} tone={label.includes('failed') && !label.startsWith('0') ? 'warning' : 'neutral'} />
          ))}
        </div>
      </div>

      <div
        className={cn(
          'mt-4 grid gap-3',
          trace?.query_terms_used.length
            ? 'lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.78fr)]'
            : null
        )}
      >
        <div className="grid gap-3 md:grid-cols-3">
          <DetailField label="Resolved target" value={formatCompoundName(targetContext)} />
          <DetailField label="Formula" value={targetContext?.formula || 'Unavailable'} />
          <DetailField label="Molecular weight" value={formatCompoundWeight(targetContext)} />
        </div>

        {trace?.query_terms_used.length ? (
          <div className="rounded-lg border border-border/80 bg-background/70 px-3 py-3 shadow-[0_10px_26px_-24px_rgba(49,58,91,0.36)]">
            <p className="text-[11px] font-medium text-muted-foreground">Search terms used</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {trace.query_terms_used.slice(0, 8).map((term) => (
                <StatusPill key={term} label={term} tone="muted" />
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {targetContext?.synonyms.length || impurityContexts.length ? (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div className="rounded-lg border border-border/80 bg-background/70 px-3 py-3">
            <p className="text-[11px] font-medium text-muted-foreground">Synonyms</p>
            <p className="mt-2 text-sm leading-relaxed text-foreground/78">
              {targetContext?.synonyms.slice(0, 5).join(', ') || 'No synonyms returned.'}
            </p>
          </div>
          <div className="rounded-lg border border-border/80 bg-background/70 px-3 py-3">
            <p className="text-[11px] font-medium text-muted-foreground">
              User-specified secondary analytes
            </p>
            <p className="mt-2 text-sm leading-relaxed text-foreground/78">
              {impurityContexts.length
                ? impurityContexts
                    .map(
                      (context) =>
                        context.resolved_name || context.input_smiles || 'Unresolved secondary analyte'
                    )
                    .join(', ')
                : 'No user-specified secondary analyte context returned.'}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function ReportWorkspace(props: {
  recommendations: Recommendation[]
  activeRecommendation: Recommendation | null
  activeRecommendationId: string | null
  onSelectRecommendation: (paperId: string) => void
  reportMeta: RecommendationReportMeta | null
  source: DiscoverySource
  resultOrigin: AgentResultOrigin | null
  runtimeMode: AgentRuntimeMode | null
  onRetryLive: () => void
  onReviewUpdatedPlan: () => void
  onExport: (recommendationId?: string) => void
  canExport: boolean
  isExporting: boolean
  runButtonLabel: string
  isBusy: boolean
  onOpenSurrogatePlayground: (recommendationId?: string | null) => void
  recentRuns: RecentRunSummary[]
  activeRunRequestHash: string | null
  onLoadRecentRun: (requestHash: string) => void
}) {
  const [showHistory, setShowHistory] = useState(false)
  const topRecommendation = props.recommendations[0] || null
  const reportSourceMode = props.reportMeta?.source_mode || props.source
  const discoveredPaperCount = props.reportMeta?.discovered_paper_count ?? 0
  const skippedPaperCount = props.reportMeta?.skipped_paper_count ?? 0
  const skippedPapersTruncated = props.reportMeta?.skipped_papers_truncated ?? false
  const consideredCandidateCount =
    props.reportMeta?.considered_candidate_count ?? props.recommendations.length
  const consideredCandidatesTruncated = props.reportMeta?.considered_candidates_truncated ?? false
  const repeatedExtractionExceptionCount =
    props.reportMeta?.repeated_extraction_exception_count ?? 0
  const runtimeSummary = props.reportMeta?.runtime || null
  const openAccessSkipDiagnostics = useMemo(() => {
    if (reportSourceMode !== 'open_access') {
      return []
    }
    const stagePriority: Record<'screening' | 'fetch' | 'extraction', number> = {
      extraction: 0,
      fetch: 1,
      screening: 2
    }
    return [...(props.reportMeta?.skipped_papers || [])].sort(
      (left, right) => stagePriority[left.stage] - stagePriority[right.stage]
    )
  }, [props.reportMeta, reportSourceMode])

  const activeRecommendation = props.activeRecommendation || topRecommendation
  const comparisonRecommendation =
    props.recommendations.find(
      (recommendation) => recommendation.paper_id !== activeRecommendation?.paper_id
    ) || null
  const activeRecommendationIndex = activeRecommendation
    ? props.recommendations.findIndex(
        (recommendation) => recommendation.paper_id === activeRecommendation.paper_id
      )
    : -1

  if (!props.recommendations.length && !props.recentRuns.length) {
    return (
      <section className="rounded-lg border border-dashed border-border bg-card p-6 text-sm leading-relaxed text-muted-foreground">
        Run discovery to populate a comparison-ready report. Successful reports remain visible while you revise inputs or rerun discovery.
      </section>
    )
  }

  return (
    <>
      <motion.section
        className="space-y-5"
        variants={RESULT_VARIANTS}
        initial="hidden"
        animate="visible"
      >
        <ReportZone
          eyebrow="Completed run"
          title="I found these methods from your request"
          description="I ranked the returned methods against the analyte, matrix, detector requirement, and current hardware profile. Select a method to expand the details in place."
          actions={
            <>
              {props.resultOrigin && props.resultOrigin !== 'live' ? (
                <Button
                  onClick={props.onRetryLive}
                  disabled={props.isBusy}
                  variant="outline"
                  className="h-8 rounded-lg text-[11px] font-medium"
                >
                  <RotateCcw className="mr-2 size-3" />
                  Retry live
                </Button>
              ) : null}
              <Button
                onClick={props.onReviewUpdatedPlan}
                disabled={props.isBusy}
                className="h-8 rounded-lg text-[11px] font-medium"
              >
                {props.isBusy ? (
                  <Loader2 className="mr-2 size-3 animate-spin" />
                ) : (
                  <RotateCcw className="mr-2 size-3" />
                )}
                Review updated plan
              </Button>
            </>
          }
        >
          <div className="space-y-4">
            <div className="rounded-xl border border-border/70 bg-card/75 px-4 py-3 shadow-[0_16px_44px_-38px_rgba(49,58,91,0.38)]">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-muted-foreground">
                    {props.recommendations.length} methods from {formatSourceModeLabel(reportSourceMode).toLowerCase()}
                    {props.resultOrigin ? ` • ${formatResultOriginLabel(props.resultOrigin).toLowerCase()}` : ''}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-foreground/82">
                    {activeRecommendation
                      ? `${activeRecommendationIndex > 0 ? `Selected method #${activeRecommendationIndex + 1}` : 'Best current match'}: ${activeRecommendation.title}. ${buildMethodSummaryLine(activeRecommendation)}.`
                      : 'No active recommendation is selected yet.'}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {props.recommendations.map((recommendation, index) => {
                    const selected = activeRecommendation?.paper_id === recommendation.paper_id
                    return (
                      <button
                        key={`quick-${recommendation.paper_id}`}
                        type="button"
                        onClick={() => props.onSelectRecommendation(recommendation.paper_id)}
                        aria-pressed={selected}
                        className={cn(
                          'h-8 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25',
                          selected
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border bg-background/70 text-muted-foreground hover:bg-card hover:text-foreground'
                        )}
                      >
                        {index === 0 ? 'Best' : `#${index + 1}`}
                      </button>
                    )
                  })}
                </div>
              </div>
                {reportSourceMode === 'open_access' && props.recommendations.length ? (
                  <div className="mt-4 grid gap-2 sm:grid-cols-4">
                    <MetricTile label="Shortlisted" value={String(discoveredPaperCount)} />
                    <MetricTile label="Viable" value={String(consideredCandidateCount)} />
                    <MetricTile label="Skipped" value={String(skippedPaperCount)} />
                    <MetricTile label="Repeat error" value={String(repeatedExtractionExceptionCount)} />
                  </div>
                ) : null}
                {runtimeSummary || props.reportMeta?.search_query_used ? (
                  <div className="mt-4 rounded-md border border-border/80 bg-background/70 px-3 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {runtimeSummary ? (
                        <>
                          <StatusPill
                            label={runtimeSummary.degraded ? 'Runtime degraded' : 'Runtime complete'}
                            tone={runtimeSummary.degraded ? 'warning' : 'success'}
                          />
                          <StatusPill
                            label={runtimeSummary.status.replace(/_/g, ' ')}
                            tone={runtimeSummary.degraded ? 'warning' : 'muted'}
                          />
                        </>
                      ) : null}
                      {props.reportMeta?.search_query_used ? (
                        <StatusPill label="Search query returned" tone="neutral" />
                      ) : null}
                      {consideredCandidatesTruncated ? (
                        <StatusPill label="Candidate preview truncated" tone="warning" />
                      ) : null}
                    </div>
                    {runtimeSummary?.summary ? (
                      <p className="mt-2 text-sm leading-relaxed text-foreground/78">
                        {runtimeSummary.summary}
                      </p>
                    ) : null}
                    {props.reportMeta?.search_query_used ? (
                      <p className="mt-2 break-words text-xs leading-relaxed text-muted-foreground">
                        Query: {props.reportMeta.search_query_used}
                      </p>
                    ) : null}
                    {runtimeSummary?.branch_decisions.length ? (
                      <ul className="mt-3 space-y-1.5 text-xs leading-relaxed text-muted-foreground">
                        {runtimeSummary.branch_decisions.slice(0, 3).map((decision) => (
                          <li key={decision} className="break-words">
                            {decision}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
            </div>

            {(props.reportMeta?.target_compound_context || props.reportMeta?.external_evidence_trace) ? (
              <CompoundEvidencePanel
                targetContext={props.reportMeta?.target_compound_context || null}
                impurityContexts={props.reportMeta?.impurity_compound_contexts || []}
                trace={props.reportMeta?.external_evidence_trace || null}
              />
            ) : null}

            {props.recommendations.length ? (
              <div className="space-y-3">
                {props.recommendations.map((recommendation, index) => {
                  const active = activeRecommendation?.paper_id === recommendation.paper_id
                  const warningCount = Math.max(
                    issueTotal(recommendation.trust.issue_counts),
                    collectWarningMessages(recommendation).length
                  )

                  return (
                    <article
                      key={recommendation.paper_id}
                      className={cn(
                        'rounded-xl border bg-card/78 text-left shadow-[0_16px_44px_-38px_rgba(49,58,91,0.45)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_52px_-42px_rgba(49,58,91,0.6)]',
                        index === 0 ? 'border-primary/25' : 'border-border/85',
                        active && 'ring-1 ring-primary/25'
                      )}
                    >
                      <div
                        role="button"
                        tabIndex={0}
                        onClick={() => props.onSelectRecommendation(recommendation.paper_id)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            props.onSelectRecommendation(recommendation.paper_id)
                          }
                        }}
                        aria-expanded={active}
                        className="group w-full cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25"
                      >
                        <div className="grid gap-3 px-4 py-3.5 lg:grid-cols-[minmax(0,1fr)_8rem] lg:items-start">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex flex-wrap gap-2">
                              <StatusPill
                                label={index === 0 ? 'Top fit' : `Rank ${index + 1}`}
                                tone={index === 0 ? 'success' : 'neutral'}
                              />
                              {warningCount ? (
                                <StatusPill
                                  label={`${warningCount} issue${warningCount === 1 ? '' : 's'}`}
                                  tone="warning"
                                />
                              ) : null}
                            </div>
                            <Button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                props.onExport(recommendation.paper_id)
                              }}
                              disabled={!props.canExport}
                              variant="outline"
                              className="h-8 rounded-lg text-[11px] font-medium"
                            >
                              {props.isExporting ? (
                                <Loader2 className="mr-2 size-3 animate-spin" />
                              ) : (
                                <FileText className="mr-2 size-3" />
                              )}
                              {props.isExporting ? 'Exporting' : 'Export'}
                            </Button>
                          </div>
                          <div className="mt-3 flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <h3 className="break-words text-base font-semibold tracking-tight text-foreground">
                                {recommendation.title}
                              </h3>
                              <p className="mt-1 line-clamp-2 break-words text-xs leading-relaxed text-muted-foreground">
                                {recommendation.citation}
                              </p>
                              <p className="mt-2 text-sm leading-relaxed text-foreground/76">
                                {buildMethodSummaryLine(recommendation)}
                              </p>
                            </div>
                            <ChevronDown className={cn('mt-1 size-4 shrink-0 text-muted-foreground transition-transform', active && 'rotate-180')} />
                          </div>
                        </div>

                        <div className="rounded-lg border border-border/70 bg-card/45 px-3 py-3 lg:text-right">
                          <p className="text-[11px] font-medium text-muted-foreground">Fit</p>
                          <p className="mt-1 text-2xl font-semibold leading-none text-primary">
                            {formatScorePercent(recommendation.score.total_score)}
                          </p>
                        </div>
                        </div>
                      </div>
                      {active ? (
                        <div className="border-t border-border/80 px-4 py-4">
                          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(15rem,0.72fr)]">
                            <div className="grid gap-x-5 gap-y-3 md:grid-cols-2">
                              <DetailField label="Why it fits" value={buildFitHighlightsSummary(recommendation)} />
                              <DetailField label="Trust and evidence" value={buildTrustEvidenceSummary(recommendation)} />
                            </div>
                            <div className="space-y-3 rounded-lg border border-border/80 bg-background/60 px-4 py-4 shadow-[0_12px_32px_-28px_rgba(49,58,91,0.4)]">
                              <ScoreRow label="System match" value={recommendation.score.system_match} />
                              <ScoreRow label="Analyte match" value={recommendation.score.analyte_match} />
                              <ScoreRow label="Matrix fit" value={recommendation.score.matrix_fit} />
                              <ScoreRow label="Practical fit" value={recommendation.score.practical_fit} />
                            </div>
                          </div>
                          <DisclosurePanel title="Backend decision trace" description="Ranking rationale, viability scores, and screening reasons produced by the recommendation engine.">
                            <p className="break-words text-sm leading-relaxed text-foreground/80">
                              {buildDecisionTraceSummary(recommendation)}
                            </p>
                            {recommendation.decision_trace?.screening_reasons.length ? (
                              <ul className="mt-3 space-y-1.5 text-xs leading-relaxed text-muted-foreground">
                                {recommendation.decision_trace.screening_reasons.slice(0, 3).map((reason) => (
                                  <li key={reason} className="break-words">
                                    {reason}
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                          </DisclosurePanel>
                          <DisclosurePanel
                            title="Score features and evidence"
                            description="Backend feature values, snippets, and trust caveats used to explain this rank."
                          >
                            <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                              <div className="space-y-3">
                                {topScoreFeatures(recommendation.score.features).map((feature) => (
                                  <ScoreRow
                                    key={feature.key}
                                    label={`${feature.label}${feature.direction === 'penalty' ? ' (penalty)' : ''}`}
                                    value={feature.value}
                                  />
                                ))}
                              </div>
                              <div className="space-y-3">
                                <div className="rounded-md border border-border bg-card/50 px-3 py-3">
                                  <p className="text-[11px] font-medium text-muted-foreground">
                                    Trust summary
                                  </p>
                                  <p className="mt-2 text-sm leading-relaxed text-foreground/80">
                                    {formatTrustStateLabel(recommendation.trust.trust_state)} / {formatValidationStatusLabel(recommendation.trust.validation_status)}
                                    {recommendation.trust.manual_verification_required ? '. Manual verification required.' : '. Manual verification not flagged.'}
                                  </p>
                                  {recommendation.trust.warning_summary.length ? (
                                    <ul className="mt-2 space-y-1 text-xs leading-relaxed text-muted-foreground">
                                      {recommendation.trust.warning_summary.slice(0, 3).map((warning) => (
                                        <li key={warning} className="break-words">
                                          {warning}
                                        </li>
                                      ))}
                                    </ul>
                                  ) : null}
                                </div>
                                {recommendation.evidence_snippets.length ? (
                                  recommendation.evidence_snippets.slice(0, 3).map((snippet) => (
                                    <div
                                      key={`${formatEvidenceSnippetMeta(snippet)}-${snippet.text.slice(0, 40)}`}
                                      className="rounded-md border border-border bg-card/50 px-3 py-3"
                                    >
                                      <p className="text-[11px] font-medium text-muted-foreground">
                                        {formatEvidenceSnippetMeta(snippet)}
                                      </p>
                                      <p className="mt-2 break-words text-sm leading-relaxed text-foreground/80">
                                        {snippet.text}
                                      </p>
                                    </div>
                                  ))
                                ) : (
                                  <div className="rounded-md border border-dashed border-border bg-card/50 px-3 py-3 text-sm text-muted-foreground">
                                    No evidence snippets were returned for this candidate.
                                  </div>
                                )}
                              </div>
                            </div>
                          </DisclosurePanel>
                          <div className="mt-4">
                            <SurrogatePreview
                              recommendation={recommendation}
                              topRecommendation={topRecommendation}
                              isVisible={active}
                              onOpenPlayground={() =>
                                props.onOpenSurrogatePlayground(recommendation.paper_id)
                              }
                            />
                          </div>
                        </div>
                      ) : null}
                    </article>
                  )
                })}
              </div>
            ) : (
              <div className="rounded-md border border-dashed border-border bg-background px-4 py-6 text-sm text-muted-foreground">
                No active report is loaded. Open a recent run to restore a cached report into this workspace.
              </div>
            )}

            {reportSourceMode === 'open_access' ? (
              <DisclosurePanel
                title="Skipped-paper diagnostics"
                description="Backend skip previews grouped by the stage where each paper dropped out."
                defaultOpen={skippedPaperCount > 0}
              >
                {openAccessSkipDiagnostics.length ? (
                  <div className="space-y-3">
                    {skippedPapersTruncated || skippedPaperCount > openAccessSkipDiagnostics.length ? (
                      <div className="rounded-md border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                        Showing {openAccessSkipDiagnostics.length} skipped-paper previews from {skippedPaperCount} total skipped papers.
                      </div>
                    ) : null}
                    {openAccessSkipDiagnostics.map((skippedPaper) => (
                      (() => {
                        const queryProvenance = skippedPaper.query_provenance || []
                        return (
                          <div
                            key={`${skippedPaper.stage}-${skippedPaper.paper_id}`}
                            className="rounded-md border border-border bg-card/55 px-3 py-3"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <StatusPill label={formatSkipStageLabel(skippedPaper.stage)} tone="warning" />
                              {queryProvenance.length ? (
                                <StatusPill
                                  label={`${queryProvenance.length} quer${queryProvenance.length === 1 ? 'y' : 'ies'}`}
                                  tone="muted"
                                />
                              ) : null}
                            </div>
                            <p className="mt-2 break-words text-sm font-medium text-foreground">
                              {skippedPaper.title}
                            </p>
                            <p className="mt-1 break-words text-sm leading-relaxed text-foreground/76">
                              {skippedPaper.reason}
                            </p>
                            {queryProvenance.length ? (
                              <p className="mt-2 break-words text-xs leading-relaxed text-muted-foreground">
                                {buildQueryProvenanceSummary(queryProvenance)}
                              </p>
                            ) : null}
                          </div>
                        )
                      })()
                    ))}
                  </div>
                ) : skippedPaperCount > 0 ? (
                  <div className="rounded-md border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                    {skippedPaperCount} papers were skipped, but no compact preview was returned.
                  </div>
                ) : (
                  <div className="rounded-md border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                    No skipped-paper diagnostics for this open-access report.
                  </div>
                )}
              </DisclosurePanel>
            ) : null}

            {props.recentRuns.length ? (
              <div className="rounded-xl border border-border bg-card/60">
                <button
                  type="button"
                  onClick={() => setShowHistory((current) => !current)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left"
                >
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">
                      Recent runs
                    </p>
                    <p className="mt-1 text-sm text-foreground/75">
                      Restore a matching cached report without losing the current draft.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusPill label={`${props.recentRuns.length} saved`} tone="neutral" />
                    <ChevronDown className={cn('size-4 text-muted-foreground transition-transform', showHistory && 'rotate-180')} />
                  </div>
                </button>
                {showHistory ? (
                  <div className="space-y-2 border-t border-border px-4 py-4">
                    {props.recentRuns.map((recentRun) => {
                      const active = props.activeRunRequestHash === recentRun.requestHash
                      return (
                        <button
                          key={recentRun.requestHash}
                          type="button"
                          onClick={() => props.onLoadRecentRun(recentRun.requestHash)}
                          className={cn(
                            'w-full rounded-lg border px-4 py-3 text-left transition-all',
                            active
                              ? 'border-primary/35 bg-[color:oklch(96.4%_0.012_250)]'
                              : 'border-border bg-background hover:border-primary/20 hover:bg-card/80'
                          )}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <h3 className="break-words text-sm font-semibold tracking-tight text-foreground">
                                {recentRun.title}
                              </h3>
                              <p className="mt-1 break-words text-xs leading-relaxed text-muted-foreground">
                                {recentRun.subtitle}
                              </p>
                            </div>
                            <div className="shrink-0 text-right">
                              <p className="text-xs font-medium text-muted-foreground">
                                {recentRun.createdAtLabel}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {recentRun.candidateCount} candidates
                              </p>
                            </div>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </ReportZone>
      </motion.section>

      {activeRecommendation ? (
        <div className="sr-only">
          Selected recommendation {activeRecommendationIndex + 1}: {activeRecommendation.title}
          {comparisonRecommendation ? `. Comparison method: ${comparisonRecommendation.title}.` : ''}
        </div>
      ) : null}
    </>
  )
}

function RecommendationDetailDialog({
  recommendation,
  open,
  onOpenChange,
  resultOrigin,
  runtimeMode,
  reportSourceMode,
  rank,
  topRecommendation,
  runnerUpRecommendation,
  openAccessSkipDiagnostics,
  skippedPaperCount,
  onOpenSurrogatePlayground
}: {
  recommendation: Recommendation | null
  open: boolean
  onOpenChange: (open: boolean) => void
  resultOrigin: AgentResultOrigin | null
  runtimeMode: AgentRuntimeMode | null
  reportSourceMode: string
  rank: number
  topRecommendation: Recommendation | null
  runnerUpRecommendation: Recommendation | null
  openAccessSkipDiagnostics: RecommendationReportMeta['skipped_papers']
  skippedPaperCount: number
  onOpenSurrogatePlayground: (recommendationId?: string | null) => void
}) {
  const [surrogateState, setSurrogateState] = useState<DummySurrogateState>('idle')
  const [surrogateSession, setSurrogateSession] = useState<DummySurrogateSession | null>(null)

  useEffect(() => {
    if (!open) {
      setSurrogateState('idle')
      setSurrogateSession(null)
    }
  }, [open, recommendation?.paper_id])

  useEffect(() => {
    if (!open || surrogateState !== 'launching' || !recommendation) {
      return
    }

    const timer = window.setTimeout(() => {
      setSurrogateSession(buildDummySurrogateSession(recommendation, topRecommendation))
      setSurrogateState('ready')
    }, 850)

    return () => window.clearTimeout(timer)
  }, [open, recommendation, surrogateState, topRecommendation])

  if (!recommendation) {
    return null
  }

  const evidencePreview =
    recommendation.match_rationale?.supporting_snippet || recommendation.evidence_snippets[0] || null
  const warningMessages = collectWarningMessages(recommendation)
  const scalingNotes = collectScalingNotes(recommendation)
  const trustSteps = buildTrustRailSteps(recommendation, {
    reportSourceMode,
    resultOrigin,
    rank: rank >= 0 ? rank : 0,
    topRecommendation
  })
  const comparisonSummary = buildComparisonSummary(recommendation, topRecommendation)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl border-border bg-background/96 p-0 shadow-2xl">
        <motion.div
          initial={{ opacity: 0, y: 18, scale: 0.985 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 18, scale: 0.985 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <DialogHeader className="border-b border-border px-6 py-5 text-left">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary/70">
              Result detail
            </p>
            <DialogTitle className="mt-2 text-2xl tracking-tight">{recommendation.title}</DialogTitle>
            <DialogDescription className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              Deep inspection stays one interaction away from the transcript. Trust, evidence, provenance, caveats, and the demo-only surrogate branch all live here.
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="h-[min(78vh,54rem)]">
            <div className="space-y-6 px-6 py-6">
              <div className="flex flex-wrap gap-2">
                <StatusPill label={rank <= 0 ? 'Top fit' : `Rank ${rank + 1}`} tone={rank <= 0 ? 'success' : 'neutral'} />
                <StatusPill label={formatSourceModeLabel(reportSourceMode)} tone="muted" />
                {resultOrigin ? (
                  <StatusPill label={formatResultOriginLabel(resultOrigin)} tone={resultOriginTone(resultOrigin)} />
                ) : null}
                {runtimeMode ? (
                  <StatusPill label={formatRuntimeModeLabel(runtimeMode)} tone={runtimeModeTone(runtimeMode)} />
                ) : null}
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
                <div className="space-y-4">
                  <div className="rounded-2xl border border-border bg-card/60 px-5 py-5">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      Method summary
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-foreground/84">
                      {buildCoreMethodSummary(recommendation)}
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <MetricTile label="Total fit" value={formatScorePercent(recommendation.score.total_score)} emphasize />
                      <MetricTile label="Runtime" value={formatRuntime(getRecommendationRuntime(recommendation))} unit="min" />
                      <MetricTile label="Flow rate" value={formatMetric(getRecommendationFlow(recommendation))} unit="mL/min" />
                      <MetricTile
                        label="Temperature"
                        value={formatMetric(recommendation.extraction.method_parameters?.column_temperature_c, 1)}
                        unit="°C"
                      />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border bg-card/50 px-5 py-5">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      Why it fits
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-foreground/84">
                      {buildRankSummary(recommendation)}
                    </p>
                    <div className="mt-4 space-y-3">
                      <ScoreRow label="System match" value={recommendation.score.system_match} />
                      <ScoreRow label="Analyte match" value={recommendation.score.analyte_match} />
                      <ScoreRow label="Matrix fit" value={recommendation.score.matrix_fit} />
                      <ScoreRow label="Practical fit" value={recommendation.score.practical_fit} />
                    </div>
                    <div className="mt-4 rounded-xl border border-border bg-background px-4 py-4">
                      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                        Comparison context
                      </p>
                      <p className="mt-2 text-sm leading-relaxed text-foreground/82">
                        {comparisonSummary}
                      </p>
                      <p className="mt-2 text-sm leading-relaxed text-foreground/82">
                        {runnerUpRecommendation
                          ? buildTopFitDifferentiator(recommendation, runnerUpRecommendation)
                          : 'No runner-up candidate was returned for this report.'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="rounded-2xl border border-border bg-card/50 px-5 py-5">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      Trust and validation posture
                    </p>
                    <div className="mt-4">
                      <TrustRail steps={trustSteps} />
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <DetailField
                        label="Trust state"
                        value={formatTrustStateLabel(recommendation.trust.trust_state)}
                        tone={trustTone(recommendation.trust.trust_state) === 'success' ? 'success' : 'warning'}
                        tooltipKey="trust_state"
                      />
                      <DetailField
                        label="Validation"
                        value={formatValidationStatusLabel(recommendation.trust.validation_status)}
                        tone={
                          validationTone(recommendation.trust.validation_status) === 'success'
                            ? 'success'
                            : validationTone(recommendation.trust.validation_status) === 'error'
                              ? 'error'
                              : 'warning'
                        }
                        tooltipKey="validation_posture"
                      />
                      <DetailField
                        label="Verification posture"
                        value={formatVerificationPostureLabel(recommendation)}
                        tone={detailToneFromPillTone(verificationTone(recommendation))}
                        tooltipKey="review_posture"
                      />
                      <DetailField label="Scaling notes" value={buildScalingSummary(recommendation)} />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border bg-card/50 px-5 py-5">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      Evidence preview
                    </p>
                    {evidencePreview ? (
                      <>
                        <p className="mt-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                          {formatEvidenceSnippetMeta(evidencePreview)}
                        </p>
                        <p className="mt-2 text-sm leading-relaxed text-foreground/82">{evidencePreview.text}</p>
                      </>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">
                        No evidence snippet was returned for this candidate.
                      </p>
                    )}
                  </div>

                  <div className="rounded-2xl border border-border bg-card/50 px-5 py-5">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      Provenance
                    </p>
                    <p className="mt-2 text-sm font-medium text-foreground">
                      {recommendation.extraction.source_document.title || recommendation.title}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <StatusPill label={formatSourceKindLabel(recommendation.source_kind)} tone="muted" />
                      {typeof recommendation.extraction.source_document.published_year === 'number' ? (
                        <StatusPill label={String(recommendation.extraction.source_document.published_year)} tone="neutral" />
                      ) : null}
                    </div>
                    <div className="mt-4 space-y-2 text-sm leading-relaxed text-foreground/76">
                      {recommendation.extraction.source_document.doi ? (
                        <p className="break-words">DOI: {recommendation.extraction.source_document.doi}</p>
                      ) : null}
                      {recommendation.extraction.source_document.url ? (
                        <a
                          href={recommendation.extraction.source_document.url}
                          target="_blank"
                          rel="noreferrer"
                          className="break-all text-primary underline underline-offset-2"
                        >
                          {recommendation.extraction.source_document.url}
                        </a>
                      ) : null}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border bg-card/50 px-5 py-5">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      Warnings and scaling notes
                    </p>
                    <div className="mt-4 space-y-2">
                      {warningMessages.map((warning) => (
                        <div
                          key={warning}
                          className="rounded-xl border border-amber-300/70 bg-amber-50 px-3 py-2 text-sm leading-relaxed text-amber-950 dark:border-amber-400/70 dark:bg-amber-100/90 dark:text-amber-950"
                        >
                          {warning}
                        </div>
                      ))}
                      {scalingNotes.map((note) => (
                        <div
                          key={note}
                          className="rounded-xl border border-border bg-background px-3 py-2 text-sm leading-relaxed text-foreground/75"
                        >
                          {note}
                        </div>
                      ))}
                      {!warningMessages.length && !scalingNotes.length ? (
                        <div className="rounded-xl border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                          No warnings or scaling notes for this candidate.
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <SurrogatePreview
                recommendation={recommendation}
                topRecommendation={topRecommendation}
                isVisible={open}
                onOpenPlayground={() => {
                  onOpenChange(false)
                  onOpenSurrogatePlayground(recommendation.paper_id)
                }}
              />

              <DisclosurePanel
                title="Skipped-paper diagnostics"
                description="Open-access skip reasons stay inspectable without taking over the main popup."
              >
                {reportSourceMode !== 'open_access' ? (
                  <div className="rounded-xl border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                    Skip diagnostics are only produced for open-access runs.
                  </div>
                ) : openAccessSkipDiagnostics.length ? (
                  <div className="space-y-3">
                    {skippedPaperCount > openAccessSkipDiagnostics.length ? (
                      <div className="rounded-xl border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                        Showing {openAccessSkipDiagnostics.length} skipped-paper diagnostics from a total of {skippedPaperCount}.
                      </div>
                    ) : null}
                    {openAccessSkipDiagnostics.map((skippedPaper) => (
                      <div
                        key={`${skippedPaper.stage}-${skippedPaper.paper_id}`}
                        className="rounded-xl border border-border bg-background p-3"
                      >
                        <StatusPill label={formatSkipStageLabel(skippedPaper.stage)} tone="warning" />
                        <p className="mt-2 break-words text-sm font-medium text-foreground">
                          {skippedPaper.title}
                        </p>
                        <p className="mt-1 break-words text-sm leading-relaxed text-foreground/75">
                          {skippedPaper.reason}
                        </p>
                        {skippedPaper.url ? (
                          <a
                            href={skippedPaper.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 block break-all text-sm text-primary underline underline-offset-2"
                          >
                            {skippedPaper.url}
                          </a>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-border bg-background px-3 py-3 text-sm text-muted-foreground">
                    No skipped-paper diagnostics for this open-access report.
                  </div>
                )}
              </DisclosurePanel>
            </div>
          </ScrollArea>
        </motion.div>
      </DialogContent>
    </Dialog>
  )
}

function SourceSegmentedControl({
  value,
  onChange,
  disabled
}: {
  value: DiscoverySource
  onChange: (value: DiscoverySource) => void
  disabled?: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-1">
      <div className="grid grid-cols-2 gap-1">
        {([
          {
            value: 'open_access' as const,
            label: 'Open access',
            helper: 'Search fresh open-access literature and extract methods from returned papers.',
            icon: Search
          },
          {
            value: 'local_corpus' as const,
            label: 'Local corpus',
            helper: 'Rank against your promoted and seeded corpus. Structure-aware inputs help this mode most.',
            icon: Library
          }
        ]).map((option) => {
          const selected = value === option.value
          const Icon = option.icon
          return (
            <button
              key={option.value}
              type="button"
              disabled={disabled}
              onClick={() => onChange(option.value)}
              className={cn(
                'rounded-md px-3 py-2 text-left transition-colors',
                selected ? 'bg-card shadow-sm' : 'hover:bg-muted/40'
              )}
            >
              <div className="flex items-center gap-2">
                <Icon className={cn('size-3.5', selected ? 'text-primary' : 'text-muted-foreground')} />
                <span className="text-xs font-medium text-foreground">
                  {option.label}
                </span>
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{option.helper}</p>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function ContextRail({
  source,
  onSourceChange,
  target,
  setTarget,
  systemSpecs,
  onOpenSettings
}: {
  source: DiscoverySource
  onSourceChange: (value: DiscoverySource) => void
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
  systemSpecs: SystemSpecs
  onOpenSettings: (tab: 'hardware' | 'structures' | 'run') => void
}) {
  return (
    <div className="space-y-2 border-t border-border/70 pt-2">
      <SourceModeToggle value={source} onChange={onSourceChange} />
      <div className="grid gap-1.5 md:grid-cols-3">
        <button
          type="button"
          onClick={() => onOpenSettings('hardware')}
          className="rounded-md px-2.5 py-2 text-left transition-colors hover:bg-muted/50"
        >
          <div className="flex items-center gap-2">
            <Cpu className="size-3.5 text-primary" />
            <p className="text-xs font-medium text-muted-foreground">
              Hardware
            </p>
          </div>
          <p className="mt-1 truncate text-[12px] text-foreground/82">{formatHardwareSummary(systemSpecs)}</p>
        </button>
        <button
          type="button"
          onClick={() => onOpenSettings('structures')}
          className="rounded-md px-2.5 py-2 text-left transition-colors hover:bg-muted/50"
        >
          <div className="flex items-center gap-2">
            <Settings2 className="size-3.5 text-primary" />
            <p className="text-xs font-medium text-muted-foreground">
              Structures
            </p>
          </div>
          <p className="mt-1 truncate text-[12px] text-foreground/82">{formatStructureSummary(target)}</p>
        </button>
        <button
          type="button"
          onClick={() => onOpenSettings('run')}
          className="rounded-md px-2.5 py-2 text-left transition-colors hover:bg-muted/50"
        >
          <div className="flex items-center gap-2">
            <Settings2 className="size-3.5 text-primary" />
            <p className="text-xs font-medium text-muted-foreground">
              Run settings
            </p>
          </div>
          <p className="mt-1 truncate text-[12px] text-foreground/82">
            {formatMatrixSummary(target)}
            {' • '}
            {target.maxRunTimeMin ? `${target.maxRunTimeMin} min limit` : 'Uncapped'}
          </p>
        </button>
      </div>
    </div>
  )
}

function RunSettingsPanel({
  target,
  setTarget
}: {
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Matrix
        </p>
        <div className="mt-4 space-y-2">
          <Select
            value={target.matrix}
            onChange={(event) =>
              setTarget((current) => ({
                ...current,
                matrix: event.target.value,
                customMatrix: event.target.value === 'Other' ? current.customMatrix || '' : ''
              }))
            }
          >
            {matrices.map((matrix) => (
              <option key={matrix}>{matrix}</option>
            ))}
          </Select>
          {target.matrix === 'Other' ? (
            <Input
              value={target.customMatrix || ''}
              onChange={(event) =>
                setTarget((current) => ({
                  ...current,
                  customMatrix: event.target.value
                }))
              }
              placeholder="Custom matrix"
            />
          ) : null}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Runtime
        </p>
        <div className="mt-4 space-y-3">
          <label className="flex items-center gap-2 text-sm text-foreground/80">
            <input
              type="checkbox"
              checked={target.maxRunTimeMin === null}
              onChange={(event) =>
                setTarget((current) => ({
                  ...current,
                  maxRunTimeMin: event.target.checked ? null : 15
                }))
              }
            />
            Uncapped
          </label>
          {target.maxRunTimeMin !== null ? (
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={target.maxRunTimeMin ?? ''}
                onChange={(event) =>
                  setTarget((current) => ({
                    ...current,
                    maxRunTimeMin: parseNullableNumber(event.target.value)
                  }))
                }
                placeholder="Minutes"
              />
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                min
              </span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function MatrixPanel({
  target,
  setTarget
}: {
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
}) {
  return (
    <div className="rounded-xl border border-border bg-background px-4 py-4">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
        Matrix
      </p>
      <div className="mt-4 space-y-2">
        <Select
          value={target.matrix}
          onChange={(event) =>
            setTarget((current) => ({
              ...current,
              matrix: event.target.value,
              customMatrix: event.target.value === 'Other' ? current.customMatrix || '' : ''
            }))
          }
        >
          {matrices.map((matrix) => (
            <option key={matrix}>{matrix}</option>
          ))}
        </Select>
        {target.matrix === 'Other' ? (
          <Input
            value={target.customMatrix || ''}
            onChange={(event) =>
              setTarget((current) => ({ ...current, customMatrix: event.target.value }))
            }
            placeholder="Custom matrix"
          />
        ) : null}
      </div>
    </div>
  )
}

function RuntimePanel({
  target,
  setTarget
}: {
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
}) {
  return (
    <div className="rounded-xl border border-border bg-background px-4 py-4">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
        Runtime
      </p>
      <div className="mt-4 space-y-3">
        <label className="flex items-center gap-2 text-sm text-foreground/80">
          <input
            type="checkbox"
            checked={target.maxRunTimeMin === null}
            onChange={(event) =>
              setTarget((current) => ({
                ...current,
                maxRunTimeMin: event.target.checked ? null : 15
              }))
            }
          />
          Uncapped
        </label>
        {target.maxRunTimeMin !== null ? (
          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={target.maxRunTimeMin ?? ''}
              onChange={(event) =>
                setTarget((current) => ({
                  ...current,
                  maxRunTimeMin: parseNullableNumber(event.target.value)
                }))
              }
              placeholder="Minutes"
            />
            <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              min
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function HardwarePanel({
  systemSpecs,
  setSystemSpecs,
  issueList,
  isBusy
}: {
  systemSpecs: SystemSpecs
  setSystemSpecs: Dispatch<SetStateAction<SystemSpecs>>
  issueList: (field: string) => WorkflowIssue[]
  isBusy: boolean
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-background px-4 py-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            Column configuration
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Manufacturer
              </label>
              <Select
                value={systemSpecs.columnManufacturer}
                disabled={isBusy}
                onChange={(event) =>
                  setSystemSpecs((current) => ({
                    ...current,
                    columnManufacturer: event.target.value,
                    customManufacturer:
                      event.target.value === 'Other' ? current.customManufacturer || '' : ''
                  }))
                }
              >
                {manufacturers.map((manufacturer) => (
                  <option key={manufacturer}>{manufacturer}</option>
                ))}
              </Select>
              {systemSpecs.columnManufacturer === 'Other' ? (
                <Input
                  value={systemSpecs.customManufacturer || ''}
                  onChange={(event) =>
                    setSystemSpecs((current) => ({
                      ...current,
                      customManufacturer: event.target.value
                    }))
                  }
                  placeholder="Custom manufacturer"
                />
              ) : null}
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Chemistry
              </label>
              <Select
                value={systemSpecs.columnChemistry}
                disabled={isBusy}
                onChange={(event) =>
                  setSystemSpecs((current) => ({
                    ...current,
                    columnChemistry: event.target.value,
                    customChemistry:
                      event.target.value === 'Other' ? current.customChemistry || '' : ''
                  }))
                }
              >
                {chemistries.map((chemistry) => (
                  <option key={chemistry}>{chemistry}</option>
                ))}
              </Select>
              {systemSpecs.columnChemistry === 'Other' ? (
                <Input
                  value={systemSpecs.customChemistry || ''}
                  onChange={(event) =>
                    setSystemSpecs((current) => ({
                      ...current,
                      customChemistry: event.target.value
                    }))
                  }
                  placeholder="Custom chemistry"
                />
              ) : null}
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Identifier
              </label>
              <Input
                value={systemSpecs.columnName}
                disabled={isBusy}
                placeholder="e.g. Acquity UPLC BEH C18"
                onChange={(event) =>
                  setSystemSpecs((current) => ({
                    ...current,
                    columnName: event.target.value
                  }))
                }
              />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-background px-4 py-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            Flow path
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Length (mm)
              </label>
              <Input
                type="number"
                value={systemSpecs.columnLengthMm ?? ''}
                onChange={(event) =>
                  setSystemSpecs((current) => ({
                    ...current,
                    columnLengthMm: parseNullableNumber(event.target.value)
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Inner diameter (mm)
              </label>
              <Input
                type="number"
                value={systemSpecs.columnIdMm ?? ''}
                onChange={(event) =>
                  setSystemSpecs((current) => ({
                    ...current,
                    columnIdMm: parseNullableNumber(event.target.value)
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Particle size (um)
              </label>
              <Input
                type="number"
                step="0.1"
                value={systemSpecs.particleSizeUm ?? ''}
                onChange={(event) =>
                  setSystemSpecs((current) => ({
                    ...current,
                    particleSizeUm: parseNullableNumber(event.target.value)
                  }))
                }
              />
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Pressure limit
        </p>
        <div className="mt-4 flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-foreground/80">
            <input
              type="checkbox"
              checked={systemSpecs.maxPressureBar === 0}
              disabled={isBusy}
              onChange={(event) =>
                setSystemSpecs((current) => ({
                  ...current,
                  maxPressureBar: event.target.checked ? 0 : null
                }))
              }
            />
            No limit
          </label>
          {systemSpecs.maxPressureBar !== 0 ? (
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={systemSpecs.maxPressureBar ?? ''}
                className="w-32"
                onChange={(event) =>
                  setSystemSpecs((current) => ({
                    ...current,
                    maxPressureBar: parseNullableNumber(event.target.value)
                  }))
                }
                placeholder="bar"
              />
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">bar</span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Solvents and modes
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div>
            <p className="text-xs font-medium text-foreground">Available solvents</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {solvents.map((solvent) => {
                const selected = systemSpecs.availableSolvents.includes(solvent)
                return (
                  <button
                    key={solvent}
                    type="button"
                    disabled={isBusy}
                    onClick={() =>
                      setSystemSpecs((current) => ({
                        ...current,
                        availableSolvents: selected
                          ? current.availableSolvents.filter((item) => item !== solvent)
                          : [...current.availableSolvents, solvent]
                      }))
                    }
                    className={cn(
                      'rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                      selected
                        ? 'border-primary/30 bg-primary/10 text-primary'
                        : 'border-border bg-card/40 text-foreground/78 hover:border-primary/20'
                    )}
                  >
                    {solvent}
                  </button>
                )
              })}
            </div>
            <div className="mt-2">
              <FieldIssues issues={issueList('availableSolvents')} />
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-foreground">Hardware modes</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {hardwareModes.map((mode) => {
                const selected = systemSpecs.instrumentModes?.includes(mode)
                return (
                  <button
                    key={mode}
                    type="button"
                    disabled={isBusy}
                    onClick={() =>
                      setSystemSpecs((current) => ({
                        ...current,
                        instrumentModes: selected
                          ? (current.instrumentModes || []).filter((item) => item !== mode)
                          : [...(current.instrumentModes || []), mode]
                      }))
                    }
                    className={cn(
                      'rounded-full border px-4 py-1.5 text-xs font-medium transition-colors',
                      selected
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-card/40 text-muted-foreground hover:border-primary/20 hover:text-foreground'
                    )}
                  >
                    {mode}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Detector array
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {detectors.map((detector) => {
            const selected = systemSpecs.detectorTypes.includes(detector)
            return (
              <button
                key={detector}
                type="button"
                disabled={isBusy}
                onClick={() =>
                  setSystemSpecs((current) => ({
                    ...current,
                    detectorTypes: selected
                      ? current.detectorTypes.filter((item) => item !== detector)
                      : [...current.detectorTypes, detector]
                  }))
                }
                className={cn(
                  'rounded-lg border px-3 py-4 text-sm transition-colors',
                  selected
                    ? 'border-primary/30 bg-primary/10 text-primary'
                    : 'border-border bg-card/40 text-foreground/78 hover:border-primary/20'
                )}
              >
                {detector}
              </button>
            )
          })}
        </div>
        <div className="mt-2">
          <FieldIssues issues={issueList('detectorTypes')} />
        </div>
      </div>
    </div>
  )
}

function StructuresPanel({
  source,
  onSourceChange,
  target,
  setTarget,
  issueList,
  isBusy,
  updateTargetSmiles,
  resolveTargetSmilesName,
  addImpurity,
  updateImpurity,
  removeImpurity,
  resolveImpurityName
}: {
  source: DiscoverySource
  onSourceChange: (value: DiscoverySource) => void
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
  issueList: (field: string) => WorkflowIssue[]
  isBusy: boolean
  updateTargetSmiles: (value: string) => void
  resolveTargetSmilesName: () => void
  addImpurity: () => void
  updateImpurity: (compoundId: string, value: string) => void
  removeImpurity: (compoundId: string) => void
  resolveImpurityName: (compoundId: string) => void
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Recognized details
        </p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Update the live draft here. Closing this modal keeps the current transcript and refreshes the implementation-plan summary in place.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Analyte label
            </label>
            <Input
              value={target.analyteName}
              disabled={isBusy}
              placeholder="e.g. Caffeine"
              onChange={(event) =>
                setTarget((current) => ({
                  ...current,
                  analyteName: event.target.value
                }))
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Source mode
            </label>
            <Select
              value={source}
              disabled={isBusy}
              onChange={(event) => onSourceChange(event.target.value as DiscoverySource)}
            >
              <option value="open_access">Open access</option>
              <option value="local_corpus">Local corpus</option>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Matrix
            </label>
            <Select
              value={target.matrix}
              disabled={isBusy}
              onChange={(event) =>
                setTarget((current) => ({
                  ...current,
                  matrix: event.target.value,
                  customMatrix: event.target.value === 'Other' ? current.customMatrix || '' : ''
                }))
              }
            >
              {matrices.map((matrix) => (
                <option key={matrix}>{matrix}</option>
              ))}
            </Select>
            {target.matrix === 'Other' ? (
              <Input
                value={target.customMatrix || ''}
                disabled={isBusy}
                onChange={(event) =>
                  setTarget((current) => ({
                    ...current,
                    customMatrix: event.target.value
                  }))
                }
                placeholder="Custom matrix"
              />
            ) : null}
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Runtime target
            </label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={target.maxRunTimeMin ?? ''}
                disabled={isBusy}
                onChange={(event) =>
                  setTarget((current) => ({
                    ...current,
                    maxRunTimeMin: parseNullableNumber(event.target.value)
                  }))
                }
                placeholder="Optional"
              />
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                min
              </span>
            </div>
          </div>
        </div>
      </div>
      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Target structure
            </p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              Leave this empty for text-only open-access discovery. Add it when Local Corpus or structure-aware ranking matters.
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1 space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Target SMILES
            </label>
            <Input
              value={target.targetSmiles}
              disabled={isBusy || target.targetResolving}
              placeholder="Enter target SMILES"
              onChange={(event) => updateTargetSmiles(event.target.value)}
              className="font-mono text-[11px]"
            />
          </div>
          <Button
            onClick={resolveTargetSmilesName}
            disabled={isBusy || !target.targetSmiles.trim() || Boolean(target.targetResolving)}
            variant="outline"
            className="h-10 rounded-lg text-[11px] font-medium"
          >
            {target.targetResolving ? (
              <Loader2 className="mr-2 size-3 animate-spin" />
            ) : (
              <Search className="mr-2 size-3" />
            )}
            Resolve
          </Button>
        </div>
        {target.targetResolvedName ? (
          <p className="mt-3 text-xs leading-relaxed text-foreground/80">
            Resolved as <span className="font-semibold">{target.targetResolvedName}</span>
            {target.targetLookupSource ? ` via ${target.targetLookupSource}` : ''}.
          </p>
        ) : null}
        {target.targetLookupError ? (
          <p className="mt-2 text-xs leading-relaxed text-destructive">{target.targetLookupError}</p>
        ) : null}
        <div className="mt-2">
          <FieldIssues issues={issueList('targetSmiles')} />
        </div>
      </div>

      <div className="rounded-xl border border-border bg-background px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Impurity structures
            </p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              Optional. Add co-eluters only when they should influence ranking.
            </p>
          </div>
          <Button
            onClick={addImpurity}
            disabled={isBusy}
            variant="outline"
            size="sm"
            className="h-8 rounded-lg text-xs font-medium"
          >
            <Plus className="mr-2 size-3" />
            Add
          </Button>
        </div>

        {target.impurities.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-border bg-card/40 px-3 py-3 text-xs text-muted-foreground">
            No secondary analyte molecules added.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {target.impurities.map((compound, index) => (
              <div key={compound.id} className="rounded-xl border border-border bg-card/40 p-3">
                <div className="flex flex-col gap-3">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
                    <div className="min-w-0 flex-1 space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                        Secondary analyte {index + 1}
                      </label>
                      <Input
                        value={compound.smiles}
                        disabled={isBusy || compound.resolving}
                        placeholder="Enter secondary analyte SMILES"
                        onChange={(event) => updateImpurity(compound.id, event.target.value)}
                        className="font-mono text-[11px]"
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() => resolveImpurityName(compound.id)}
                        disabled={isBusy || !compound.smiles.trim() || Boolean(compound.resolving)}
                        variant="outline"
                        size="sm"
                        className="h-9 rounded-lg text-xs font-medium"
                      >
                        {compound.resolving ? (
                          <Loader2 className="mr-2 size-3 animate-spin" />
                        ) : (
                          <Search className="mr-2 size-3" />
                        )}
                        Resolve
                      </Button>
                      <Button
                        onClick={() => removeImpurity(compound.id)}
                        disabled={isBusy}
                        variant="ghost"
                        size="sm"
                        className="h-9 rounded-lg text-xs font-medium"
                      >
                        <X className="mr-2 size-3" />
                        Remove
                      </Button>
                    </div>
                  </div>
                  {compound.name ? (
                    <p className="text-xs leading-relaxed text-foreground/80">
                      Resolved as <span className="font-semibold">{compound.name}</span>
                      {compound.lookupSource ? ` via ${compound.lookupSource}` : ''}.
                    </p>
                  ) : null}
                  {compound.lookupError ? (
                    <p className="text-xs leading-relaxed text-destructive">{compound.lookupError}</p>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-2">
          <FieldIssues issues={issueList('impurities')} />
        </div>
      </div>
    </div>
  )
}

function DraftEditDialog(props: {
  activeTab: 'hardware' | 'structures' | 'run' | 'matrix' | 'runtime' | null
  onClose: () => void
  onTabChange: (tab: 'hardware' | 'structures' | 'run' | 'matrix' | 'runtime') => void
  source: DiscoverySource
  onSourceChange: (value: DiscoverySource) => void
  systemSpecs: SystemSpecs
  setSystemSpecs: Dispatch<SetStateAction<SystemSpecs>>
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
  issueList: (field: string) => WorkflowIssue[]
  isBusy: boolean
  updateTargetSmiles: (value: string) => void
  resolveTargetSmilesName: () => void
  addImpurity: () => void
  updateImpurity: (compoundId: string, value: string) => void
  removeImpurity: (compoundId: string) => void
  resolveImpurityName: (compoundId: string) => void
}) {
  return (
    <Dialog open={Boolean(props.activeTab)} onOpenChange={(open) => (!open ? props.onClose() : undefined)}>
      <DialogContent className="flex max-h-[88vh] max-w-5xl flex-col gap-0 overflow-hidden border-border/80 bg-background/92 p-0 shadow-[0_28px_80px_-38px_rgba(49,58,91,0.55)] backdrop-blur-xl data-[state=open]:duration-300 data-[state=open]:zoom-in-95">
        <DialogHeader className="border-b border-border px-5 py-5 text-left">
          <DialogTitle className="text-xl tracking-tight">
            {props.activeTab === 'hardware'
              ? 'Hardware profile'
              : props.activeTab === 'structures'
                ? 'Recognized details'
                : props.activeTab === 'matrix'
                  ? 'Matrix settings'
                  : props.activeTab === 'runtime'
                    ? 'Runtime settings'
                    : 'Run settings'}
          </DialogTitle>
          <DialogDescription className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Adjust the active draft without leaving the thread. Closing this modal keeps the transcript intact and refreshes the current implementation-plan summary.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="min-h-0 flex-1">
          <div className="px-5 py-5">
            {props.activeTab === 'hardware' ? (
              <div className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
                <HardwarePanel
                  systemSpecs={props.systemSpecs}
                  setSystemSpecs={props.setSystemSpecs}
                  issueList={props.issueList}
                  isBusy={props.isBusy}
                />
              </div>
            ) : null}
            {props.activeTab === 'structures' ? (
              <div className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
                <StructuresPanel
                  source={props.source}
                  onSourceChange={props.onSourceChange}
                  target={props.target}
                  setTarget={props.setTarget}
                  issueList={props.issueList}
                  isBusy={props.isBusy}
                  updateTargetSmiles={props.updateTargetSmiles}
                  resolveTargetSmilesName={props.resolveTargetSmilesName}
                  addImpurity={props.addImpurity}
                  updateImpurity={props.updateImpurity}
                  removeImpurity={props.removeImpurity}
                  resolveImpurityName={props.resolveImpurityName}
                />
              </div>
            ) : null}
            {props.activeTab === 'run' ? (
              <div className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
                <RunSettingsPanel target={props.target} setTarget={props.setTarget} />
              </div>
            ) : null}
            {props.activeTab === 'matrix' ? (
              <div className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
                <MatrixPanel target={props.target} setTarget={props.setTarget} />
              </div>
            ) : null}
            {props.activeTab === 'runtime' ? (
              <div className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
                <RuntimePanel target={props.target} setTarget={props.setTarget} />
              </div>
            ) : null}
          </div>
        </ScrollArea>
        <div className="flex items-center justify-end gap-3 border-t border-border bg-background px-5 py-4">
          <Button
            onClick={props.onClose}
            className="h-9 rounded-lg px-4 text-[11px] font-medium"
          >
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function ComposerDock(props: {
  composerText: string
  onRequestTextChange: (value: string) => void
  onPrepareRun: () => void
  runButtonLabel: string
  isBusy: boolean
  source: DiscoverySource
  onSourceChange: (value: DiscoverySource) => void
  target: DiscoveryTarget
  setTarget: Dispatch<SetStateAction<DiscoveryTarget>>
  systemSpecs: SystemSpecs
  settingsTab: 'hardware' | 'structures' | 'run' | 'matrix' | 'runtime' | null
  setSettingsTab: Dispatch<SetStateAction<'hardware' | 'structures' | 'run' | 'matrix' | 'runtime' | null>>
}) {
  return (
    <div className="shrink-0 pb-safe">
      <div className="mx-auto max-w-5xl px-4 pb-3 pt-1 md:px-6">
        <div className="relative">
          <div className="space-y-2 rounded-xl border border-border/70 bg-background/65 px-3 py-2.5 shadow-[0_18px_60px_-36px_rgba(49,58,91,0.45)] backdrop-blur-2xl supports-[backdrop-filter]:bg-background/58">
          {false ? (
            <ContextRail
              source={props.source}
              onSourceChange={props.onSourceChange}
              target={props.target}
              setTarget={props.setTarget}
              systemSpecs={props.systemSpecs}
              onOpenSettings={(tab) =>
                props.setSettingsTab((current) => (current === tab ? null : tab))
              }
            />
          ) : null}
          <textarea
            id="dashboard-composer-textarea"
            value={props.composerText}
            disabled={props.isBusy}
            aria-label="Describe the separation request"
            placeholder="Describe the analyte, matrix, and practical constraints."
            onChange={(event) => props.onRequestTextChange(event.target.value)}
            className="min-h-[48px] w-full resize-none bg-transparent px-1 py-1 text-[14px] leading-6 text-foreground placeholder:text-muted-foreground focus-visible:outline-none"
          />
          <div className="flex flex-col gap-2 pt-1 md:flex-row md:items-center md:justify-between">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5 px-1">
              <Button
                variant="outline"
                onClick={() => props.setSettingsTab((current) => (current === 'hardware' ? null : 'hardware'))}
                className="h-9 rounded-full px-4 text-[11px] font-medium"
              >
                <Settings2 className="mr-2 size-3.5" />
                Hardware
              </Button>
              <Button
                variant="outline"
                onClick={() => props.setSettingsTab((current) => (current === 'runtime' ? null : 'runtime'))}
                className="h-9 rounded-full px-4 text-[11px] font-medium"
              >
                <Clock3 className="mr-2 size-3.5" />
                Runtime
              </Button>
              <Button
                variant="outline"
                onClick={() => props.setSettingsTab((current) => (current === 'matrix' ? null : 'matrix'))}
                className="h-9 rounded-full px-4 text-[11px] font-medium"
              >
                <FlaskConical className="mr-2 size-3.5" />
                Matrix
              </Button>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2 md:shrink-0">
              <SourceModeToggle
                value={props.source}
                onChange={props.onSourceChange}
                disabled={props.isBusy}
              />
              <Button
                onClick={props.onPrepareRun}
                disabled={props.isBusy || !props.composerText.trim()}
                className="h-10 rounded-lg px-5 text-[11px] font-medium sm:h-9"
              >
                {props.isBusy ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <ArrowUpRight className="mr-2 size-4" />
                )}
                {props.runButtonLabel}
              </Button>
            </div>
          </div>
        </div>
        </div>
      </div>
    </div>
  )
}

export function DashboardView(props: DashboardViewProps) {
  const { theme, toggle: toggleTheme } = useTheme()
  const [settingsTab, setSettingsTab] = useState<'hardware' | 'structures' | 'run' | 'matrix' | 'runtime' | null>(null)
  const mainRef = useRef<HTMLElement | null>(null)
  const attentionEndRef = useRef<HTMLDivElement | null>(null)
  const hasReport = props.recommendations.length > 0
  const hasConversation =
    (props.requestText?.trim().length ?? 0) > 0 ||
    hasReport ||
    props.isBusy ||
    props.followUpTurns.length > 0
  const surrogateChatRequested = isSurrogateChatRequest(props.requestText || '')
  const surrogateRecommendation =
    props.activeRecommendation || props.recommendations[0] || null
  const canLaunchSurrogateFromChat =
    surrogateChatRequested && Boolean(surrogateRecommendation)
  const resultTurnBody =
    props.recommendations.length === 1
      ? 'I found one candidate. Open it here to compare the rationale and scores, or revise the draft below.'
      : `I found ${props.recommendations.length} candidates. Open one here to compare the rationale and scores, or revise the draft below.`

  const consolidatedNotices = [
    props.runtimeBanner ? (
      <NoticeBanner
        key="runtime"
        tone={props.runtimeBanner.tone}
        title={props.runtimeBanner.title}
        message={props.runtimeBanner.message}
        details={props.runtimeBanner.details}
      />
    ) : null,
    props.restoreNotice ? (
      <NoticeBanner
        key="restore"
        tone="info"
        title={props.restoreNotice.title}
        message={props.restoreNotice.message}
        dismissLabel="Dismiss"
        onDismiss={props.onDismissRestoreNotice}
      />
    ) : null,
    props.staleReportNotice ? (
      <NoticeBanner
        key="stale"
        tone="warning"
        title="Report requires rerun"
        message={props.staleReportNotice}
        actionLabel={props.isBusy ? undefined : 'Refresh plan'}
        onAction={props.isBusy ? undefined : props.onPrepareRun}
        dismissLabel="Hide"
        onDismiss={props.onDismissStaleReportNotice}
      />
    ) : null,
    props.runOutcome ? (
      <NoticeBanner
        key="outcome"
        tone={outcomeTone(props.runOutcome.kind)}
        title={props.runOutcome.title}
        message={props.runOutcome.message}
        details={props.runOutcome.details}
        actionLabel={props.runOutcomeActionLabel || undefined}
        onAction={props.onRunOutcomeAction || undefined}
      />
    ) : null,
    props.exportError ? (
      <NoticeBanner
        key="export"
        tone="error"
        title="Export failed"
        message="The handoff artifact could not be created."
        details={[props.exportError]}
        dismissLabel="Dismiss"
        onDismiss={props.onDismissExportError}
      />
    ) : null
  ].filter(Boolean)

  useEffect(() => {
    if (!hasConversation && !consolidatedNotices.length) {
      return
    }

    const timeout = window.setTimeout(() => {
      attentionEndRef.current?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'end'
      })
    }, 80)

    return () => window.clearTimeout(timeout)
  }, [
    hasConversation,
    consolidatedNotices.length,
    props.phase,
    props.recommendations.length,
    props.followUpTurns.length,
    props.pendingClarification?.length,
    props.runOutcome?.title
  ])

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-[14px] text-foreground">
      <header className="relative z-40 shrink-0 border-b border-border bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 md:flex-nowrap md:px-6">
          <div className="flex min-w-0 flex-1 basis-[8rem] items-center gap-2.5 sm:basis-auto sm:gap-3">
            <div className="min-w-0">
              <p className="font-serif text-[1.05rem] font-medium tracking-normal">silico Apriori</p>
              <p className="hidden text-xs leading-relaxed text-muted-foreground sm:block">
                method development agent
              </p>
            </div>
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
            {props.showLegacyStudio ? (
              <>
                <Button
                  onClick={props.onOpenStudio}
                  variant="outline"
                  size="sm"
                  className="hidden h-8 rounded-lg text-[11px] font-medium md:inline-flex"
                >
                  <ArrowUpRight className="mr-2 size-3" />
                  Studio preview
                </Button>
                <Button
                  onClick={props.onOpenClassicStudio}
                  variant="outline"
                  size="sm"
                  className="hidden h-8 rounded-lg text-[11px] font-medium xl:inline-flex"
                >
                  <Sparkles className="mr-2 size-3" />
                  Classic shell
                </Button>
              </>
            ) : null}
            <Button
              onClick={() => props.onOpenSurrogatePlayground()}
              variant="outline"
              size="sm"
              className="hidden h-8 rounded-lg text-[11px] font-medium lg:inline-flex"
            >
              <Cpu className="mr-2 size-3" />
              Surrogate lab
            </Button>
            <Button
              onClick={toggleTheme}
              variant="outline"
              size="sm"
              className="h-8 rounded-lg px-3 text-[11px] font-medium"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? (
                <Moon className="size-3.5 sm:mr-2" />
              ) : (
                <Sun className="size-3.5 sm:mr-2" />
              )}
              <span className="hidden sm:inline">{theme}</span>
            </Button>
            <Button
              onClick={props.onSignOut}
              variant="ghost"
              size="sm"
              className="h-8 rounded-lg px-3 text-[11px] font-medium"
              title={
                props.accountIdentifier
                  ? `Signed in as ${props.accountIdentifier}`
                  : 'Sign out'
              }
            >
              <LogOut className="size-3.5 sm:mr-2" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
            <Button
              onClick={props.onResetSession}
              variant="ghost"
              size="sm"
              disabled={props.isBusy}
              className="h-8 rounded-lg px-2 text-[11px] font-medium sm:px-4"
              aria-label="Reset session"
              title="Reset session"
            >
              <RotateCcw className="size-3.5 sm:mr-2" />
              <span className="hidden sm:inline">Reset session</span>
            </Button>
          </div>
        </div>
      </header>

      <main ref={mainRef} className="flex-1 overflow-y-auto pb-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-5 px-4 py-6 md:px-6 md:py-7">
          {!hasConversation && !props.pendingClarification?.length ? (
            <EmptyState onSelectExample={props.onSelectStarterExample} />
          ) : null}

          {hasConversation ? (
            <section className="space-y-4">
              <AnimatePresence initial={false}>
              {props.requestText?.trim() ? (
                <CopilotTurn
                  key="user-prompt"
                  speaker="user"
                  title="User prompt"
                  body={props.requestText.trim()}
                />
              ) : null}

              {props.requestText?.trim() && surrogateChatRequested ? (
                <CopilotTurn
                  key="agent-surrogate-intent"
                  speaker="agent"
                  title="Surrogate"
                  body={
                    canLaunchSurrogateFromChat
                      ? 'Sure!'
                      : 'Sure — once a method is selected here, I can open the surrogate tab from this thread.'
                  }
                  motionPreset="result"
                >
                  {canLaunchSurrogateFromChat && surrogateRecommendation ? (
                    <div className="pt-1">
                      <Button
                        onClick={() =>
                          props.onOpenSurrogatePlayground(surrogateRecommendation.paper_id)
                        }
                        className="h-9 rounded-lg text-[11px] font-medium"
                      >
                        <Cpu className="mr-2 size-3.5" />
                        Simulate
                      </Button>
                    </div>
                  ) : null}
                </CopilotTurn>
              ) : null}

              {props.requestText?.trim() &&
              !surrogateChatRequested &&
              (props.phase === 'recognition_verify' || props.phase === 'planning' || props.phase === 'discovering' || hasReport) ? (
                <CopilotTurn
                  key="agent-recognition"
                  speaker="agent"
                  title="Recognition"
                  body={props.phase === 'recognition_verify' 
                    ? "I’ve analyzed your request. Please verify the detected analytes and your hardware configuration before we build the implementation plan."
                    : "I’ve analyzed your request and verified the detected analytes and hardware configuration."
                  }
                  motionPreset="recognition"
                  typewriter={props.phase === 'recognition_verify'}
                  plain
                >
                  <div className="space-y-3 border-t border-border/70 pt-3">
                    <RecognitionSurface recognition={props.promptRecognition} compact />
                    {props.phase === 'recognition_verify' && (
                      <div className="flex flex-wrap gap-2 pt-2">
                        <Button
                          onClick={props.onConfirmRecognition}
                          disabled={Boolean(props.pendingClarification?.length)}
                          className="h-9 rounded-lg text-[11px] font-medium"
                        >
                          <CheckCircle2 className="mr-2 size-3.5" />
                          Confirm & Continue
                        </Button>
                        <Button 
                          onClick={() => setSettingsTab('hardware')}
                          variant="outline"
                          className="h-9 rounded-lg text-[11px] font-medium"
                        >
                          <Settings2 className="mr-2 size-3.5" />
                          Edit Hardware
                        </Button>
                      </div>
                    )}
                  </div>
                </CopilotTurn>
              ) : null}

              {props.requestText?.trim() &&
              !surrogateChatRequested &&
              (props.phase === 'planning' || props.phase === 'discovering' || hasReport) ? (
                <StageAcceptedMarker key="inputs-accepted" label="Inputs accepted" />
              ) : null}

              {!surrogateChatRequested ? (
                <ClarificationWorkspace
                  key="clarification-workspace"
                  requestText={props.requestText || ''}
                  pendingClarification={props.pendingClarification}
                  clarificationAnswers={props.clarificationAnswers}
                  setClarificationAnswers={props.setClarificationAnswers}
                  onSubmitClarification={props.onSubmitClarification}
                  onDismissClarification={props.onDismissClarification}
                />
              ) : null}

              {props.requestText?.trim() &&
              !surrogateChatRequested &&
              !props.pendingClarification?.length &&
              (props.phase === 'planning' || props.phase === 'discovering' || hasReport) ? (
                <div key="agent-plan-wrapper" className="space-y-4">
                  <AgentPlanTurn
                    summary={props.planSummary}
                    draftPrepared={props.draftPrepared}
                    canConfirmRun={props.canConfirmRun}
                    runBlockerMessage={props.runBlockerMessage}
                    isBusy={props.isBusy}
                    onConfirmRun={props.onConfirmRun}
                    hasUnresolvedQuestions={
                      props.planSummary.unresolvedItems.length > 0 ||
                      Boolean(props.pendingClarification?.length)
                    }
                    onAnswerUnresolved={() => {
                      const element = document.getElementById('clarification-workspace')
                      if (element) {
                        element.scrollIntoView({
                          behavior:
                            typeof window !== 'undefined' &&
                            window.matchMedia('(prefers-reduced-motion: reduce)').matches
                              ? 'auto'
                              : 'smooth',
                          block: 'start'
                        })
                        return
                      }
                      const composer = document.getElementById('dashboard-composer-textarea')
                      if (composer instanceof HTMLTextAreaElement) {
                        composer.focus()
                        composer.scrollIntoView({
                          behavior:
                            typeof window !== 'undefined' &&
                            window.matchMedia('(prefers-reduced-motion: reduce)').matches
                              ? 'auto'
                              : 'smooth',
                          block: 'center'
                        })
                        return
                      }
                      setSettingsTab('run')
                    }}
                    onOpenSettings={(tab) =>
                      setSettingsTab((current) => (current === tab ? null : tab))
                    }
                  />
                </div>
              ) : null}

              {props.requestText?.trim() &&
              !surrogateChatRequested &&
              (props.phase === 'discovering' || hasReport) ? (
                <StageAcceptedMarker key="plan-accepted" label="Plan accepted" />
              ) : null}

              {props.isBusy && !surrogateChatRequested ? (
                <CopilotTurn
                  key="run-progress"
                  speaker="agent"
                  title="Run progress"
                  body="The run stays in this thread while retrieval, scaling, and ranking advance."
                  motionPreset="run"
                  plain
                >
                  <LiveRunWorkspace steps={props.steps} hasPreservedReport={hasReport} />
                </CopilotTurn>
              ) : null}

              {hasReport ? (
                <CopilotTurn
                  key="result-cards"
                  speaker="agent"
                  title="Methods found"
                  body={resultTurnBody}
                  motionPreset="result"
                  plain
                >
                  <ReportWorkspace
                    recommendations={props.recommendations}
                    activeRecommendation={props.activeRecommendation}
                    activeRecommendationId={props.activeRecommendationId}
                    onSelectRecommendation={props.onSelectRecommendation}
                    reportMeta={props.reportMeta}
                    source={props.source}
                    resultOrigin={props.resultOrigin}
                    runtimeMode={props.runtimeMode}
                    onRetryLive={props.onRetryLive}
                    onReviewUpdatedPlan={props.onReviewUpdatedPlan}
                    onExport={props.onExport}
                    canExport={props.canExport}
                    isExporting={props.isExporting}
                    runButtonLabel={props.runButtonLabel}
                    isBusy={props.isBusy}
                    onOpenSurrogatePlayground={props.onOpenSurrogatePlayground}
                    recentRuns={props.recentRuns}
                    activeRunRequestHash={props.activeRunRequestHash}
                    onLoadRecentRun={props.onLoadRecentRun}
                  />
                </CopilotTurn>
              ) : null}

              {props.followUpTurns.map((turn) => (
                <CopilotTurn
                  key={turn.id}
                  speaker={turn.speaker}
                  title={turn.title}
                  body={turn.body}
                  tone={turn.tone || 'default'}
                  motionPreset={turn.pending ? 'typing' : 'result'}
                >
                  {turn.action?.type === 'open_surrogate' ? (
                    <div className="pt-1">
                      <Button
                        onClick={() =>
                          props.onOpenSurrogatePlayground(turn.action?.recommendationId || undefined)
                        }
                        className="h-9 rounded-lg text-[11px] font-medium"
                      >
                        <Cpu className="mr-2 size-3.5" />
                        {turn.action.label}
                      </Button>
                    </div>
                  ) : null}
                </CopilotTurn>
              ))}
              </AnimatePresence>
            </section>
          ) : null}

          {consolidatedNotices.length ? <div className="space-y-3">{consolidatedNotices}</div> : null}
          <div ref={attentionEndRef} aria-hidden="true" />
        </div>
      </main>

      <DraftEditDialog
        activeTab={settingsTab}
        onClose={() => setSettingsTab(null)}
        onTabChange={setSettingsTab}
        source={props.source}
        onSourceChange={props.onSourceChange}
        systemSpecs={props.systemSpecs}
        setSystemSpecs={props.setSystemSpecs}
        target={props.target}
        setTarget={props.setTarget}
        issueList={props.issueList}
        isBusy={props.isBusy}
        updateTargetSmiles={props.updateTargetSmiles}
        resolveTargetSmilesName={props.resolveTargetSmilesName}
        addImpurity={props.addImpurity}
        updateImpurity={props.updateImpurity}
        removeImpurity={props.removeImpurity}
        resolveImpurityName={props.resolveImpurityName}
      />

      <ComposerDock
        composerText={props.composerText}
        onRequestTextChange={props.onRequestTextChange}
        onPrepareRun={props.onPrepareRun}
        runButtonLabel={props.draftActionLabel}
        isBusy={props.isBusy}
        source={props.source}
        onSourceChange={props.onSourceChange}
        target={props.target}
        setTarget={props.setTarget}
        systemSpecs={props.systemSpecs}
        settingsTab={settingsTab}
        setSettingsTab={setSettingsTab}
      />
    </div>
  )
}
