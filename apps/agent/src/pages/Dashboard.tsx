import { useEffect, useMemo, useRef, useState } from 'react'
import { downloadAnalysisExport } from '../lib/analysisExport'
import { navigateAgentAppRoute } from '../lib/appNavigation'
import { isLegacyStudioEnabled, type AgentRuntimeBootState } from '../lib/agentRuntime'
import { api, type AgentFollowUpRecommendationContext } from '../lib/api'
import { isSurrogateChatRequest, looksLikeFollowUpQuestion } from '../lib/chatIntents'
import { useAgentWorkflow } from '../hooks/useAgentWorkflow'
import { useAuth } from '../hooks/useAuth'
import { buildConversationPlanSummary } from '../components/dashboard/conversationViewModel'
import {
  DashboardView,
  type DashboardFollowUpTurn,
  type WorkflowIssue,
  type WorkflowOutcome
} from '../components/dashboard/DashboardView'
import type { DiscoveryTarget, Recommendation, SystemSpecs } from '../types'

const DEMO_SYSTEM_SPECS: SystemSpecs = {
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
}

function buildStarterTarget(requestText: string): DiscoveryTarget {
  const caffeineRequest = /\bcaffeine\b/i.test(requestText)

  return {
    requestText: '',
    analyteName: caffeineRequest ? 'Caffeine' : 'Metformin',
    targetSmiles: caffeineRequest
      ? 'Cn1cnc2n(C)c(=O)n(C)c(=O)c12'
      : 'CN(C)C(=N)N=C(N)N',
    targetResolvedName: caffeineRequest ? 'Caffeine' : 'Metformin',
    targetLookupSource: 'demo',
    targetLookupError: null,
    targetResolving: false,
    impurities: [],
    matrix: caffeineRequest ? 'Other' : 'Human Plasma',
    customMatrix: caffeineRequest ? 'Energy drink' : '',
    requireMS: !caffeineRequest,
    maxRunTimeMin: caffeineRequest ? 10 : null
  }
}

function statusToneForOutcome(
  outcome: WorkflowOutcome | null,
  hasReport: boolean,
  hasStaleReport: boolean,
  isBusy: boolean
): 'neutral' | 'success' | 'warning' | 'error' {
  if (isBusy) {
    return 'warning'
  }
  if (hasStaleReport) {
    return 'warning'
  }
  if (outcome?.kind === 'backend_error' || outcome?.kind === 'timeout') {
    return 'error'
  }
  if (
    outcome?.kind === 'validation' ||
    outcome?.kind === 'empty' ||
    outcome?.kind === 'interrupted' ||
    outcome?.kind === 'demo_safe_result'
  ) {
    return 'warning'
  }
  if (hasReport) {
    return 'success'
  }
  return 'neutral'
}

function formatStartupHealthLabel(status?: string | null): string {
  switch (status) {
    case 'healthy':
      return 'Healthy'
    case 'degraded':
      return 'Degraded'
    case 'unavailable':
      return 'Unavailable'
    default:
      return 'Unknown'
  }
}

function formatCachePolicyLabel(cachePolicy?: string | null): string {
  switch (cachePolicy) {
    case 'cached_preferred':
      return 'Cached preferred'
    case 'demo_safe':
      return 'Demo-safe'
    case 'live_preferred':
    default:
      return 'Live preferred'
  }
}

function formatRuntimeModeLabel(runtimeMode: ReturnType<typeof useAgentWorkflow>['runtimeMode']): string {
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

function formatRuntimeEndpointLabel(value: string): string {
  try {
    const parsed = new URL(value)
    const pathname = parsed.pathname.replace(/\/$/, '')
    return pathname ? `${parsed.origin}${pathname}` : parsed.origin
  } catch {
    return value
  }
}

function formatSystemSummary(systemSpecs: SystemSpecs): string {
  const manufacturer =
    systemSpecs.columnManufacturer === 'Other'
      ? systemSpecs.customManufacturer?.trim() || 'Custom manufacturer'
      : systemSpecs.columnManufacturer
  const chemistry =
    systemSpecs.columnChemistry === 'Other'
      ? systemSpecs.customChemistry?.trim() || 'Custom chemistry'
      : systemSpecs.columnChemistry

  return [
    manufacturer,
    chemistry,
    systemSpecs.columnLengthMm ? `${systemSpecs.columnLengthMm} mm` : null,
    systemSpecs.columnIdMm ? `${systemSpecs.columnIdMm} mm ID` : null,
    systemSpecs.particleSizeUm ? `${systemSpecs.particleSizeUm} um` : null,
    systemSpecs.detectorTypes.length ? systemSpecs.detectorTypes.join(', ') : null
  ]
    .filter(Boolean)
    .join(' • ')
}

function buildCoreMethodSummary(recommendation: Recommendation | null): string | null {
  if (!recommendation) {
    return null
  }

  const scaled = recommendation.recommended_method
  const extracted = recommendation.extraction.method_parameters
  const mobilePhaseA = extracted?.mobile_phase_a?.solvent
  const mobilePhaseB = extracted?.mobile_phase_b?.solvent
  const flowRate = scaled?.flow_rate_ml_min ?? extracted?.flow_rate_ml_min ?? null
  const runTime = scaled?.run_time_min ?? extracted?.run_time_min ?? null
  const temperature = extracted?.column_temperature_c ?? null
  const gradientProfile = scaled?.gradient_profile || extracted?.gradient_profile || []

  return [
    mobilePhaseA && mobilePhaseB ? `${mobilePhaseA} / ${mobilePhaseB}` : mobilePhaseA || mobilePhaseB || null,
    gradientProfile.length ? `${gradientProfile.length}-step gradient` : null,
    typeof flowRate === 'number' ? `${flowRate.toFixed(2)} mL/min` : null,
    typeof runTime === 'number' ? `${runTime.toFixed(2)} min runtime` : null,
    typeof temperature === 'number' ? `${temperature.toFixed(1)} °C` : null
  ]
    .filter(Boolean)
    .join(' • ') || null
}

function buildFollowUpRecommendationContext(
  recommendation: Recommendation | null
): AgentFollowUpRecommendationContext | null {
  if (!recommendation) {
    return null
  }

  const scaled = recommendation.recommended_method
  const extracted = recommendation.extraction.method_parameters

  return {
    paper_id: recommendation.paper_id,
    title: recommendation.title,
    citation: recommendation.citation || null,
    rationale: recommendation.rationale || null,
    core_method_summary: buildCoreMethodSummary(recommendation),
    flow_rate_ml_min: scaled?.flow_rate_ml_min ?? extracted?.flow_rate_ml_min ?? null,
    run_time_min: scaled?.run_time_min ?? extracted?.run_time_min ?? null,
    column_temperature_c: extracted?.column_temperature_c ?? null,
    is_scaled: Boolean(scaled?.is_scaled),
    mobile_phase_a: extracted?.mobile_phase_a
      ? {
          solvent: extracted.mobile_phase_a.solvent || null,
          additive: extracted.mobile_phase_a.additive || null,
          ph_estimate: extracted.mobile_phase_a.ph_estimate ?? null
        }
      : null,
    mobile_phase_b: extracted?.mobile_phase_b
      ? {
          solvent: extracted.mobile_phase_b.solvent || null,
          additive: extracted.mobile_phase_b.additive || null,
          ph_estimate: extracted.mobile_phase_b.ph_estimate ?? null
        }
      : null,
    gradient_profile: scaled?.gradient_profile || extracted?.gradient_profile || [],
    isocratic_percent_b: extracted?.isocratic_percent_b ?? null,
    trust_state: recommendation.trust.trust_state || null,
    validation_status: recommendation.trust.validation_status || null,
    warning_summary: recommendation.trust.warning_summary || [],
    scaling_notes: scaled?.scaling_notes || [],
    dominant_differentiator: recommendation.decision_trace?.dominant_differentiator || null
  }
}

export function Dashboard({
  runtimeBootState
}: {
  runtimeBootState: AgentRuntimeBootState
}) {
  const { user, signOut } = useAuth()
  const {
    phase,
    runOutcome,
    validationIssues,
    restoreNotice,
    staleReportNotice,
    runtimeMode,
    resultOrigin,
    systemSpecs,
    effectiveTarget,
    promptRecognition,
    setSystemSpecs,
    target,
    setTarget,
    source,
    setSource,
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
    loadRecentRun,
    recentRuns,
    activeRunRequestHash,
    steps,
    recommendations,
    reportMeta,
    activeRecommendation,
    setActiveRecommendationId
  } = useAgentWorkflow({
    runtimeConfig: runtimeBootState.runtimeConfig,
    startupHealth: runtimeBootState.startupHealth
  })

  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({})
  const [draftPrepared, setDraftPrepared] = useState(false)
  const [composerText, setComposerText] = useState(target.requestText)
  const [followUpTurns, setFollowUpTurns] = useState<DashboardFollowUpTurn[]>([])
  const skipNextPlanResetRef = useRef(false)
  const skipNextComposerSyncRef = useRef(false)

  const planSignature = useMemo(
    () =>
      JSON.stringify({
        requestText: target.requestText,
        source,
        target,
        systemSpecs
      }),
    [source, systemSpecs, target]
  )

  const issuesByField = useMemo(() => {
    return validationIssues.reduce<Record<string, WorkflowIssue[]>>((accumulator, issue) => {
      accumulator[issue.field] = [...(accumulator[issue.field] || []), issue as WorkflowIssue]
      return accumulator
    }, {})
  }, [validationIssues])

  const blockingIssues = validationIssues.filter((issue) => issue.severity === 'error')
  const isBusy = phase === 'discovering'
  const hasReport = recommendations.length > 0
  const hasStaleReport = Boolean(staleReportNotice)
  const statusLabel = (() => {
    if (isBusy) {
      return 'Processing'
    }
    if (hasStaleReport) {
      return 'Report stale'
    }
    if (
      runOutcome &&
      runOutcome.kind !== 'cached_result' &&
      runOutcome.kind !== 'demo_safe_result' &&
      !hasReport
    ) {
      return 'Needs attention'
    }
    if (hasReport) {
      return 'Report ready'
    }
    return 'Draft'
  })()
  const statusTone = statusToneForOutcome(runOutcome, hasReport, hasStaleReport, isBusy)
  const issueList = (field: string) => issuesByField[field] || []

  useEffect(() => {
    setClarificationAnswers({})
  }, [pendingClarification])

  useEffect(() => {
    if (skipNextComposerSyncRef.current) {
      skipNextComposerSyncRef.current = false
      return
    }
    setComposerText(target.requestText)
  }, [target.requestText])

  useEffect(() => {
    if (skipNextPlanResetRef.current) {
      skipNextPlanResetRef.current = false
      return
    }
    setDraftPrepared(false)
    setClarificationAnswers({})
  }, [planSignature])

  const activeChatRecommendation = activeRecommendation || recommendations[0] || null
  const shouldSendFollowUp =
    Boolean(target.requestText.trim()) && looksLikeFollowUpQuestion(composerText)

  const replaceFollowUpTurn = (turnId: string, nextTurn: DashboardFollowUpTurn) => {
    setFollowUpTurns((current) =>
      current.map((turn) => (turn.id === turnId ? nextTurn : turn))
    )
  }

  const handlePrepareRun = () => {
    const nextRequestText = composerText.trim()
    if (!nextRequestText) {
      return
    }

    skipNextPlanResetRef.current = true

    if (nextRequestText !== target.requestText.trim()) {
      setFollowUpTurns([])
      setTarget((current) => ({
        ...current,
        requestText: nextRequestText
      }))
    }

    setDraftPrepared(true)
    void prepareRunDraft({ requestTextOverride: nextRequestText })
  }

  const handleSelectStarterExample = (requestText: string) => {
    setFollowUpTurns([])
    skipNextComposerSyncRef.current = true
    setSystemSpecs(DEMO_SYSTEM_SPECS)
    setTarget(buildStarterTarget(requestText))
    setSource('open_access')
    setComposerText(requestText)
  }

  const handleSendFollowUp = async () => {
    const question = composerText.trim()
    if (!question) {
      return
    }

    const timestamp = Date.now()
    const userTurn: DashboardFollowUpTurn = {
      id: `user-${timestamp}`,
      speaker: 'user',
      title: 'Follow-up',
      body: question
    }
    const pendingAssistantTurn: DashboardFollowUpTurn = {
      id: `assistant-${timestamp}`,
      speaker: 'agent',
      title: 'Assistant',
      body: 'Thinking through the current report.',
      pending: true
    }

    setFollowUpTurns((current) => [...current, userTurn, pendingAssistantTurn])
    setComposerText('')

    if (isSurrogateChatRequest(question)) {
      replaceFollowUpTurn(pendingAssistantTurn.id, {
        id: pendingAssistantTurn.id,
        speaker: 'agent',
        title: '',
        body: activeChatRecommendation
          ? 'Sure!'
          : 'Sure — once a method is selected here, I can open the surrogate tab from this thread.',
        action: activeChatRecommendation
          ? {
              type: 'open_surrogate',
              label: 'Simulate',
              recommendationId: activeChatRecommendation.paper_id
            }
          : undefined
      })
      return
    }

    try {
      const response = await api.answerFollowUp({
        question,
        request_text: target.requestText,
        source_mode: source,
        runtime_mode: runtimeMode,
        result_origin: resultOrigin,
        system_summary: formatSystemSummary(systemSpecs),
        search_query_used: reportMeta?.search_query_used?.trim() || null,
        recommendations_count: recommendations.length,
        active_recommendation: buildFollowUpRecommendationContext(activeChatRecommendation),
        history: [...followUpTurns, userTurn]
          .filter((turn) => !turn.pending)
          .slice(-6)
          .map((turn) => ({
            role: turn.speaker === 'agent' ? 'assistant' : 'user',
            content: turn.body
          }))
      })

      replaceFollowUpTurn(pendingAssistantTurn.id, {
        id: pendingAssistantTurn.id,
        speaker: 'agent',
        title: response.source === 'openai' ? 'Assistant' : 'Grounded answer',
        body: response.answer
      })
    } catch (error) {
      replaceFollowUpTurn(pendingAssistantTurn.id, {
        id: pendingAssistantTurn.id,
        speaker: 'agent',
        title: 'Assistant',
        body:
          error instanceof Error && error.message
            ? error.message
            : 'I could not answer that follow-up yet.',
        tone: 'warning'
      })
    }
  }

  const handleSubmitClarification = (overrideAnswers?: Record<string, string>) => {
    skipNextPlanResetRef.current = true
    applyClarificationAnswers(overrideAnswers ?? clarificationAnswers)
    setClarificationAnswers({})
    setDraftPrepared(true)
    if (localClarificationPending) {
      approveClarification()
    } else {
      void prepareRunDraft({ skipClarify: true, skipLocalClarify: true })
    }
  }

  const handleDismissClarification = () => {
    skipClarification()
    setClarificationAnswers({})
    setDraftPrepared(true)
    if (localClarificationPending) {
      approveClarification()
    } else {
      void prepareRunDraft({ skipClarify: true, skipLocalClarify: true })
    }
  }

  const handleConfirmRun = () => {
    if (!draftPrepared) {
      handlePrepareRun()
      return
    }

    if (pendingClarification?.length) {
      return
    }

    if (phase === 'planning') {
      void approvePlan()
    } else {
      void runDiscovery({ skipClarify: true })
    }
  }

  const handleExport = (recommendationId?: string) => {
    const selectedRecommendation =
      (recommendationId
        ? recommendations.find((recommendation) => recommendation.paper_id === recommendationId)
        : activeRecommendation) || null

    if (!selectedRecommendation) {
      setExportError('Select a recommendation before exporting the analysis package.')
      return
    }

    setIsExporting(true)
    setExportError(null)

    try {
      downloadAnalysisExport({
        target,
        systemSpecs,
        sourceMode: reportMeta?.source_mode || source,
        searchQuery: reportMeta?.search_query_used?.trim() || null,
        reportMeta,
        recommendations,
        selectedRecommendationId: selectedRecommendation.paper_id,
        resultOrigin,
        hasStaleReport
      })
    } catch (error) {
      console.error('Analysis export failed:', error)
      setExportError(
        error instanceof Error && error.message
          ? error.message
          : 'Unable to create the export artifact.'
      )
    } finally {
      setIsExporting(false)
    }
  }

  const runButtonLabel = isBusy
    ? 'Running discovery'
    : hasStaleReport
      ? 'Run updated discovery'
      : hasReport
        ? 'Rerun discovery'
        : 'Run discovery'
  const draftActionLabel = draftPrepared
    ? 'Refresh plan'
    : hasReport
      ? 'Review updated plan'
      : 'Build plan'
  const composerActionLabel = shouldSendFollowUp ? 'Send' : draftActionLabel

  const runtimeHealth = runtimeBootState.startupHealth
  const runtimeBanner =
    Boolean(runtimeBootState.bootError) ||
    runtimeBootState.runtimeTarget === 'desktop' ||
    runtimeHealth?.status !== 'healthy'
      ? {
          tone:
            runtimeBootState.bootError || runtimeHealth?.status === 'unavailable'
              ? ('error' as const)
              : runtimeHealth?.status === 'degraded'
                ? ('warning' as const)
                : ('info' as const),
          title: runtimeBootState.bootError
            ? 'Runtime bootstrap degraded'
            : runtimeBootState.runtimeTarget === 'desktop'
              ? 'Desktop runtime ready'
              : 'Runtime health requires attention',
          message: runtimeBootState.bootError
            ? 'The app fell back to its current in-memory runtime config because the desktop shell did not return a complete startup state.'
            : runtimeHealth?.status === 'healthy'
              ? 'Service endpoints were injected through the runtime layer, so this launch no longer depends on Vite proxy assumptions.'
              : runtimeHealth?.status === 'degraded'
                ? 'One or more hosted dependencies responded in a degraded state at launch. Live discovery remains available, but runs may need a retry.'
                : 'Hosted dependencies were unreachable at launch. You can still review inputs, but new live requests may fail until connectivity returns.',
          details: [
            `Startup health: ${
              runtimeHealth
                ? `${formatStartupHealthLabel(runtimeHealth.status)}${
                    runtimeHealth.cached ? ' (cached)' : ''
                  }`
                : 'Unavailable'
            }`,
            `API base: ${formatRuntimeEndpointLabel(runtimeBootState.runtimeConfig.apiBaseUrl)}`,
            `Method-dev base: ${formatRuntimeEndpointLabel(
              runtimeBootState.runtimeConfig.methodDevBaseUrl
            )}`,
            `Cache policy: ${formatCachePolicyLabel(runtimeBootState.runtimeConfig.cachePolicy)}`,
            runtimeMode ? `Current mode: ${formatRuntimeModeLabel(runtimeMode)}` : null,
            runtimeHealth?.api.detail
              ? `API health detail: ${runtimeHealth.api.detail}`
              : `API health: ${formatStartupHealthLabel(runtimeHealth?.api.status)}`,
            runtimeHealth?.methodDev.detail
              ? `Method-dev health detail: ${runtimeHealth.methodDev.detail}`
              : `Method-dev health: ${formatStartupHealthLabel(runtimeHealth?.methodDev.status)}`
          ].filter(Boolean) as string[]
        }
      : null

  const runOutcomeActionLabel = runOutcome
    ? runOutcome.kind === 'validation'
      ? 'Review inputs'
      : runOutcome.kind === 'interrupted'
        ? 'Go to source step'
        : runOutcome.kind === 'cached_result' || runOutcome.kind === 'demo_safe_result'
          ? 'Retry live'
          : 'Retry discovery'
    : null

  const runOutcomeAction = runOutcome
    ? runOutcome.kind === 'validation'
      ? blockingIssues[0]?.stage === 'system_setup'
        ? goToSystemSetup
        : blockingIssues[0]?.stage === 'target_setup'
          ? goToTargetSetup
          : goToSourceSelection
      : runOutcome.kind === 'interrupted'
        ? goToSourceSelection
        : runOutcome.kind === 'cached_result' || runOutcome.kind === 'demo_safe_result'
          ? retryLiveDiscovery
          : rerunDiscovery
    : null

  const planSummary = useMemo(
    () =>
      buildConversationPlanSummary({
        target,
        effectiveTarget,
        source,
        systemSpecs,
        recognition: promptRecognition,
        validationIssues,
        pendingClarification,
        phase
      }),
    [effectiveTarget, pendingClarification, phase, promptRecognition, source, systemSpecs, target, validationIssues]
  )

  const canConfirmRun =
    !isBusy &&
    effectiveTarget.requestText.trim().length > 0 &&
    blockingIssues.length === 0 &&
    !pendingClarification?.length

  const runBlockerMessage =
    pendingClarification?.length
        ? 'Answer the outstanding clarification before running the live workflow.'
        : blockingIssues[0]?.message || null

  return (
    <DashboardView
      statusLabel={statusLabel}
      statusTone={statusTone}
      isBusy={isBusy}
      phase={phase}
      requestText={target.requestText}
      composerText={composerText}
      onRequestTextChange={setComposerText}
      onConfirmRecognition={confirmRecognition}
      onPrepareRun={shouldSendFollowUp ? () => void handleSendFollowUp() : handlePrepareRun}
      onConfirmRun={handleConfirmRun}
      onResetSession={() => {
        setFollowUpTurns([])
        resetSession()
      }}
      onSignOut={signOut}
      accountIdentifier={user?.identifier ?? null}
      onSelectStarterExample={handleSelectStarterExample}
      showLegacyStudio={isLegacyStudioEnabled()}
      onOpenStudio={() => navigateAgentAppRoute('/studio')}
      onOpenClassicStudio={() => navigateAgentAppRoute('/studio/classic')}
      onOpenSurrogatePlayground={(recommendationId) => {
        try {
          sessionStorage.setItem('silico_surrogate_recommendations', JSON.stringify(recommendations))
        } catch {
          // ignore storage errors
        }
        navigateAgentAppRoute(
          recommendationId
            ? `/surrogate?candidate=${encodeURIComponent(recommendationId)}`
            : '/surrogate'
        )
      }}
      runButtonLabel={runButtonLabel}
      draftActionLabel={composerActionLabel}
      draftPrepared={draftPrepared}
      canConfirmRun={canConfirmRun}
      runBlockerMessage={runBlockerMessage}
      followUpTurns={followUpTurns}
      planSummary={planSummary}
      promptRecognition={promptRecognition}
      source={source}
      onSourceChange={setSource}
      systemSpecs={systemSpecs}
      setSystemSpecs={setSystemSpecs}
      target={target}
      setTarget={setTarget}
      issueList={issueList}
      pendingClarification={pendingClarification}
      clarificationAnswers={clarificationAnswers}
      setClarificationAnswers={setClarificationAnswers}
      onSubmitClarification={handleSubmitClarification}
      onDismissClarification={handleDismissClarification}
      steps={steps}
      recommendations={recommendations}
      reportMeta={reportMeta}
      runtimeMode={runtimeMode}
      resultOrigin={resultOrigin}
      staleReportNotice={staleReportNotice}
      activeRecommendation={activeRecommendation}
      activeRecommendationId={activeRecommendation?.paper_id || null}
      onSelectRecommendation={setActiveRecommendationId}
      onRetryLive={() => void retryLiveDiscovery()}
      onExport={handleExport}
      onReviewUpdatedPlan={handlePrepareRun}
      isExporting={isExporting}
      canExport={recommendations.length > 0 && !isBusy && !isExporting}
      exportError={exportError}
      onDismissExportError={() => setExportError(null)}
      recentRuns={recentRuns}
      activeRunRequestHash={activeRunRequestHash}
      onLoadRecentRun={(requestHash) => {
        setFollowUpTurns([])
        loadRecentRun(requestHash)
      }}
      restoreNotice={restoreNotice}
      onDismissRestoreNotice={dismissRestoreNotice}
      runOutcome={runOutcome as WorkflowOutcome | null}
      onRunOutcomeAction={runOutcomeAction ? (() => void runOutcomeAction()) : null}
      runOutcomeActionLabel={runOutcomeActionLabel}
      runtimeBanner={runtimeBanner}
      onDismissStaleReportNotice={dismissStaleReportNotice}
      updateTargetSmiles={updateTargetSmiles}
      resolveTargetSmilesName={resolveTargetSmilesName}
      addImpurity={addImpurity}
      updateImpurity={updateImpurity}
      removeImpurity={removeImpurity}
      resolveImpurityName={resolveImpurityName}
    />
  )
}
