import type {
  AgentResultOrigin,
  DiscoveryTarget,
  Recommendation,
  RecommendationReportMeta,
  SystemSpecs
} from '../types'

const EXPORT_VERSION = '2026-04-18-agent-handoff-v2'

type ReportSourceMode = RecommendationReportMeta['source_mode']
type ResultOrigin = AgentResultOrigin | null

export interface AnalysisExportStatusSummary {
  export_version: string
  generated_at: string
  generated_at_label: string
  discovery_mode: AgentResultOrigin | 'unknown'
  discovery_mode_label: string
  report_freshness: 'current' | 'stale'
  report_freshness_label: string
  source_mode: ReportSourceMode
  source_mode_label: string
  search_query: string | null
  recommendation_count: number
  discovered_paper_count: number | null
  selected_recommendation_rank: number
  trust_state_label: string
  validation_status_label: string
  review_posture_label: string
  verification_posture_label: string
  manual_verification_required: boolean
  disclaimer: string
}

export interface AnalysisExportRankedAlternativeSummary {
  rank: number
  paper_id: string
  title: string
  citation: string
  source_kind_label: string
  total_fit_percent: string
  runtime_min: string
  trust_state_label: string
  validation_status_label: string
  review_posture_label: string
  comparison_summary: string
}

export interface AnalysisExportPayload {
  artifact_type: 'silico-agent-export'
  title: string
  status: AnalysisExportStatusSummary
  request_summary: {
    request_text: string | null
    analyte_name: string | null
    target_smiles: string | null
    target_resolved_name: string | null
    matrix: string | null
    require_mass_spectrometry: boolean
    max_run_time_min: number | null
    impurities: Array<{
      smiles: string
      name: string | null
      resolved: boolean
    }>
  }
  system_constraints: {
    column_manufacturer: string | null
    column_name: string | null
    column_chemistry: string | null
    column_length_mm: number | null
    column_inner_diameter_mm: number | null
    particle_size_um: number | null
    available_solvents: string[]
    detector_types: string[]
  }
  selected_recommendation: {
    rank: number
    paper_id: string
    title: string
    citation: string
    published_year: number | null
    doi: string | null
    url: string | null
    source_kind_label: string
    total_fit_percent: string
    comparison_summary: string
    ranking_summary: string
    extraction_rationale: string
    trust: {
      trust_state_label: string
      validation_status_label: string
      review_posture_label: string
      verification_posture_label: string
      retrieval_ready: boolean
      manual_verification_required: boolean
      warning_count: number
      issue_count_total: number
      corpus_origin_label: string
      review_record_id: string | null
    }
    method_summary: {
      runtime_min: string
      flow_rate_ml_min: string
      column_temperature_c: string
      mobile_phase_a: string
      mobile_phase_b: string
      gradient_summary: string
      gradient_profile: Array<{
        time_min: number
        percent_b: number
      }>
    }
    scoring: {
      total_fit_percent: string
      system_match_percent: string
      analyte_match_percent: string
      matrix_fit_percent: string
      practical_fit_percent: string
      extraction_confidence_percent: string
      literature_relevance_percent: string
    }
    source_document: {
      title: string | null
      source_type_label: string
      published_year: number | null
      doi: string | null
      url: string | null
      file_name: string | null
      source_document_id: string
    }
    evidence: {
      supporting_match_evidence: {
        meta: string
        text: string
      } | null
      snippets: Array<{
        meta: string
        text: string
      }>
    }
    diagnostics: {
      warnings: string[]
      scaling_notes: string[]
    }
  }
  ranked_alternatives: AnalysisExportRankedAlternativeSummary[]
  skipped_papers: Array<{
    stage_label: string
    title: string
    reason: string
    url: string | null
  }>
}

export interface BuildAnalysisExportInput {
  target: DiscoveryTarget
  systemSpecs: SystemSpecs
  sourceMode: ReportSourceMode
  searchQuery: string | null
  reportMeta: RecommendationReportMeta | null
  recommendations: Recommendation[]
  selectedRecommendationId: string | null
  resultOrigin: ResultOrigin
  hasStaleReport: boolean
}

function formatScorePercent(value: number | null | undefined): string {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : 'n/a'
}

function formatMetric(value: number | null | undefined, digits = 2): string {
  return typeof value === 'number' ? value.toFixed(digits) : 'n/a'
}

function formatRuntime(value: number | null | undefined): string {
  return typeof value === 'number' ? value.toFixed(1) : 'n/a'
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

function formatVerificationPostureLabel(recommendation: Recommendation): string {
  if (recommendation.review_summary?.record_state) {
    return formatReviewStateLabel(recommendation.review_summary.record_state)
  }
  return recommendation.trust.manual_verification_required
    ? 'Manual verification required'
    : 'Verification posture clear'
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

function formatEvidenceSnippetMeta(
  snippet: Recommendation['evidence_snippets'][number]
): string {
  const parts = [
    snippet.section_label?.trim() || null,
    typeof snippet.page_number === 'number' ? `p. ${snippet.page_number}` : null
  ].filter(Boolean)
  return parts.length ? parts.join(' • ') : 'Evidence snippet'
}

function formatMobilePhase(phase?: {
  solvent?: string | null
  additive?: string | null
  ph_estimate?: number | null
} | null): string {
  if (!phase?.solvent) {
    return 'n/a'
  }

  const extras = [phase.additive, phase.ph_estimate ? `pH ${phase.ph_estimate}` : null].filter(
    Boolean
  )
  return extras.length ? `${phase.solvent} (${extras.join(', ')})` : phase.solvent
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

function buildRankSummary(recommendation: Recommendation): string {
  return (
    recommendation.decision_trace?.beat_runner_up_summary ||
    recommendation.decision_trace?.screening_summary ||
    recommendation.match_rationale?.summary ||
    recommendation.ranking_context.summary ||
    recommendation.rationale
  )
}

function uniqueStrings(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.map((value) => value?.trim()).filter(Boolean) as string[]))
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

function issueTotal(issueCounts?: { info: number; warning: number; error: number } | null): number {
  if (!issueCounts) {
    return 0
  }
  return issueCounts.info + issueCounts.warning + issueCounts.error
}

function buildComparisonSummary(
  recommendation: Recommendation,
  topRecommendation: Recommendation | null
): string {
  if (
    topRecommendation &&
    topRecommendation.paper_id === recommendation.paper_id &&
    recommendation.decision_trace?.beat_runner_up_summary
  ) {
    return recommendation.decision_trace.beat_runner_up_summary
  }

  if (!topRecommendation || topRecommendation.paper_id === recommendation.paper_id) {
    return 'Highest total fit for the current constraints.'
  }

  const scoreDelta = Math.max(
    0,
    Math.round(
      (
        (topRecommendation.decision_trace?.ranking_score ?? topRecommendation.score.total_score) -
        (recommendation.decision_trace?.ranking_score ?? recommendation.score.total_score)
      ) * 100
    )
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

function formatDiscoveryModeLabel(mode: ResultOrigin): string {
  switch (mode) {
    case 'cached':
      return 'Cached result'
    case 'demo_safe':
      return 'Demo-safe result'
    case 'live':
      return 'Live result'
    case 'live_degraded':
      return 'Live degraded result'
    default:
      return 'Unknown result origin'
  }
}

function formatFreshnessLabel(hasStaleReport: boolean): string {
  return hasStaleReport
    ? 'Previous-run export: inputs changed after this report was generated.'
    : 'Current report export: no newer input edits are marked.'
}

function formatColumnManufacturer(systemSpecs: SystemSpecs): string | null {
  if (systemSpecs.columnManufacturer === 'Other') {
    return systemSpecs.customManufacturer?.trim() || null
  }
  return systemSpecs.columnManufacturer.trim() || null
}

function formatColumnChemistry(systemSpecs: SystemSpecs): string | null {
  if (systemSpecs.columnChemistry === 'Other') {
    return systemSpecs.customChemistry?.trim() || null
  }
  return systemSpecs.columnChemistry.trim() || null
}

function buildGradientSummary(recommendation: Recommendation): string {
  const gradientProfile =
    recommendation.recommended_method?.gradient_profile ||
    recommendation.extraction.method_parameters?.gradient_profile ||
    []
  if (gradientProfile.length) {
    return `${gradientProfile.length} gradient steps`
  }

  const isocraticPercentB = recommendation.extraction.method_parameters?.isocratic_percent_b
  if (typeof isocraticPercentB === 'number') {
    return `${isocraticPercentB}% B isocratic`
  }

  return 'No gradient profile returned'
}

function buildFileTimestamp(date: Date): string {
  const year = String(date.getFullYear())
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}${month}${day}-${hours}${minutes}${seconds}`
}

function sanitizeFilenamePart(value: string | null | undefined): string {
  const sanitized = (value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)

  return sanitized || 'analysis'
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderListItems(items: string[]): string {
  if (!items.length) {
    return '<p class="empty-state">None returned.</p>'
  }

  return `<ul class="bullet-list">${items
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join('')}</ul>`
}

function renderPills(labels: string[]): string {
  return labels
    .filter(Boolean)
    .map((label) => `<span class="pill">${escapeHtml(label)}</span>`)
    .join('')
}

function renderDetailRows(rows: Array<{ label: string; value: string }>): string {
  return rows
    .map(
      (row) =>
        `<div class="detail-row"><dt>${escapeHtml(row.label)}</dt><dd>${escapeHtml(row.value)}</dd></div>`
    )
    .join('')
}

function formatGeneratedAtLabel(date: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'medium'
  }).format(date)
}

function buildEmbeddedJson(payload: AnalysisExportPayload): string {
  return JSON.stringify(payload, null, 2)
    .replace(/</g, '\\u003c')
    .replace(/-->/g, '--\\>')
    .replace(/<\/script/gi, '<\\/script')
}

export function buildAnalysisExportPayload(
  input: BuildAnalysisExportInput
): AnalysisExportPayload {
  const generatedAt = new Date()
  const generatedAtIso = generatedAt.toISOString()
  const generatedAtLabel = formatGeneratedAtLabel(generatedAt)
  const selectedRecommendation =
    input.recommendations.find(
      (recommendation) => recommendation.paper_id === input.selectedRecommendationId
    ) || input.recommendations[0]

  if (!selectedRecommendation) {
    throw new Error('No recommendation is available to export.')
  }

  const selectedRank =
    input.recommendations.findIndex(
      (recommendation) => recommendation.paper_id === selectedRecommendation.paper_id
    ) + 1
  const topRecommendation = input.recommendations[0] || null
  const warnings = collectWarningMessages(selectedRecommendation)
  const scalingNotes = collectScalingNotes(selectedRecommendation)
  const evidenceSnippets = selectedRecommendation.evidence_snippets.map((snippet) => ({
    meta: formatEvidenceSnippetMeta(snippet),
    text: snippet.text
  }))
  const sourceDocument = selectedRecommendation.extraction.source_document
  const gradientProfile =
    selectedRecommendation.recommended_method?.gradient_profile ||
    selectedRecommendation.extraction.method_parameters?.gradient_profile ||
    []

  return {
    artifact_type: 'silico-agent-export',
    title: `Silico Agent Export: ${selectedRecommendation.title}`,
    status: {
      export_version: EXPORT_VERSION,
      generated_at: generatedAtIso,
      generated_at_label: generatedAtLabel,
      discovery_mode: input.resultOrigin || 'unknown',
      discovery_mode_label: formatDiscoveryModeLabel(input.resultOrigin),
      report_freshness: input.hasStaleReport ? 'stale' : 'current',
      report_freshness_label: formatFreshnessLabel(input.hasStaleReport),
      source_mode: input.sourceMode,
      source_mode_label: formatSourceModeLabel(input.sourceMode),
      search_query: input.searchQuery,
      recommendation_count: input.recommendations.length,
      discovered_paper_count: input.reportMeta?.discovered_paper_count ?? null,
      selected_recommendation_rank: selectedRank,
      trust_state_label: formatTrustStateLabel(selectedRecommendation.trust.trust_state),
      validation_status_label: formatValidationStatusLabel(
        selectedRecommendation.trust.validation_status
      ),
      review_posture_label: formatReviewStateLabel(
        selectedRecommendation.review_summary?.record_state
      ),
      verification_posture_label: formatVerificationPostureLabel(selectedRecommendation),
      manual_verification_required: selectedRecommendation.trust.manual_verification_required,
      disclaimer:
        'Decision-support handoff only. This export is not laboratory approval, not an instrument-ready method file, and must be reviewed by a qualified scientist before operational use.'
    },
    request_summary: {
      request_text: input.target.requestText.trim() || null,
      analyte_name: input.target.analyteName.trim() || null,
      target_smiles: input.target.targetSmiles.trim() || null,
      target_resolved_name: input.target.targetResolvedName?.trim() || null,
      matrix:
        input.target.matrix === 'Other'
          ? input.target.customMatrix?.trim() || null
          : input.target.matrix || null,
      require_mass_spectrometry: input.target.requireMS,
      max_run_time_min: input.target.maxRunTimeMin,
      impurities: input.target.impurities
        .map((compound) => ({
          smiles: compound.smiles.trim(),
          name: compound.name?.trim() || null,
          resolved: compound.resolved
        }))
        .filter((compound) => compound.smiles)
    },
    system_constraints: {
      column_manufacturer: formatColumnManufacturer(input.systemSpecs),
      column_name: input.systemSpecs.columnName.trim() || null,
      column_chemistry: formatColumnChemistry(input.systemSpecs),
      column_length_mm: input.systemSpecs.columnLengthMm,
      column_inner_diameter_mm: input.systemSpecs.columnIdMm,
      particle_size_um: input.systemSpecs.particleSizeUm,
      available_solvents: [...input.systemSpecs.availableSolvents],
      detector_types: [...input.systemSpecs.detectorTypes]
    },
    selected_recommendation: {
      rank: selectedRank,
      paper_id: selectedRecommendation.paper_id,
      title: selectedRecommendation.title,
      citation: selectedRecommendation.citation,
      published_year: selectedRecommendation.published_year ?? null,
      doi: selectedRecommendation.doi ?? sourceDocument.doi ?? null,
      url: selectedRecommendation.url ?? sourceDocument.url ?? null,
      source_kind_label: formatSourceKindLabel(selectedRecommendation.source_kind),
      total_fit_percent: formatScorePercent(selectedRecommendation.score.total_score),
      comparison_summary: buildComparisonSummary(selectedRecommendation, topRecommendation),
      ranking_summary: buildRankSummary(selectedRecommendation),
      extraction_rationale: selectedRecommendation.rationale,
      trust: {
        trust_state_label: formatTrustStateLabel(selectedRecommendation.trust.trust_state),
        validation_status_label: formatValidationStatusLabel(
          selectedRecommendation.trust.validation_status
        ),
        review_posture_label: formatReviewStateLabel(
          selectedRecommendation.review_summary?.record_state
        ),
        verification_posture_label: formatVerificationPostureLabel(selectedRecommendation),
        retrieval_ready: selectedRecommendation.trust.retrieval_ready,
        manual_verification_required: selectedRecommendation.trust.manual_verification_required,
        warning_count: warnings.length,
        issue_count_total: issueTotal(selectedRecommendation.trust.issue_counts),
        corpus_origin_label: formatCorpusOriginLabel(
          selectedRecommendation.review_summary?.corpus_origin
        ),
        review_record_id: selectedRecommendation.review_summary?.review_record_id || null
      },
      method_summary: {
        runtime_min: formatRuntime(getRecommendationRuntime(selectedRecommendation)),
        flow_rate_ml_min: formatMetric(getRecommendationFlow(selectedRecommendation)),
        column_temperature_c: formatMetric(
          selectedRecommendation.extraction.method_parameters?.column_temperature_c,
          1
        ),
        mobile_phase_a: formatMobilePhase(
          selectedRecommendation.extraction.method_parameters?.mobile_phase_a
        ),
        mobile_phase_b: formatMobilePhase(
          selectedRecommendation.extraction.method_parameters?.mobile_phase_b
        ),
        gradient_summary: buildGradientSummary(selectedRecommendation),
        gradient_profile: gradientProfile.map((point) => ({
          time_min: point.time_min,
          percent_b: point.percent_b
        }))
      },
      scoring: {
        total_fit_percent: formatScorePercent(selectedRecommendation.score.total_score),
        system_match_percent: formatScorePercent(selectedRecommendation.score.system_match),
        analyte_match_percent: formatScorePercent(selectedRecommendation.score.analyte_match),
        matrix_fit_percent: formatScorePercent(selectedRecommendation.score.matrix_fit),
        practical_fit_percent: formatScorePercent(selectedRecommendation.score.practical_fit),
        extraction_confidence_percent: formatScorePercent(
          selectedRecommendation.score.extraction_confidence
        ),
        literature_relevance_percent: formatScorePercent(
          selectedRecommendation.score.literature_relevance
        )
      },
      source_document: {
        title: sourceDocument.title || null,
        source_type_label: formatSourceKindLabel(sourceDocument.source_type),
        published_year: sourceDocument.published_year ?? null,
        doi: sourceDocument.doi ?? null,
        url: sourceDocument.url ?? null,
        file_name: sourceDocument.file_name ?? null,
        source_document_id: sourceDocument.source_document_id
      },
      evidence: {
        supporting_match_evidence: selectedRecommendation.match_rationale?.supporting_snippet
          ? {
              meta: formatEvidenceSnippetMeta(
                selectedRecommendation.match_rationale.supporting_snippet
              ),
              text: selectedRecommendation.match_rationale.supporting_snippet.text
            }
          : null,
        snippets: evidenceSnippets
      },
      diagnostics: {
        warnings,
        scaling_notes: scalingNotes
      }
    },
    ranked_alternatives: input.recommendations
      .filter((recommendation) => recommendation.paper_id !== selectedRecommendation.paper_id)
      .map((recommendation, index) => ({
        rank:
          input.recommendations.findIndex((item) => item.paper_id === recommendation.paper_id) + 1,
        paper_id: recommendation.paper_id,
        title: recommendation.title,
        citation: recommendation.citation,
        source_kind_label: formatSourceKindLabel(recommendation.source_kind),
        total_fit_percent: formatScorePercent(recommendation.score.total_score),
        runtime_min: formatRuntime(getRecommendationRuntime(recommendation)),
        trust_state_label: formatTrustStateLabel(recommendation.trust.trust_state),
        validation_status_label: formatValidationStatusLabel(
          recommendation.trust.validation_status
        ),
        review_posture_label: formatReviewStateLabel(recommendation.review_summary?.record_state),
        comparison_summary: buildComparisonSummary(recommendation, topRecommendation)
      })),
    skipped_papers: (input.reportMeta?.skipped_papers || []).map((paper) => ({
      stage_label: formatSkipStageLabel(paper.stage),
      title: paper.title,
      reason: paper.reason,
      url: paper.url || null
    }))
  }
}

export function buildAnalysisExportFilename(payload: AnalysisExportPayload): string {
  const date = new Date(payload.status.generated_at)
  const stamp = buildFileTimestamp(date)
  const analytePart = sanitizeFilenamePart(payload.request_summary.analyte_name)
  const titlePart = sanitizeFilenamePart(payload.selected_recommendation.title)
  return `silico-analysis-${analytePart}-${titlePart}-rank-${payload.selected_recommendation.rank}-${stamp}.html`
}

export function renderAnalysisExportHtml(payload: AnalysisExportPayload): string {
  const selected = payload.selected_recommendation
  const embeddedJson = buildEmbeddedJson(payload)
  const summaryPills = renderPills([
    payload.status.source_mode_label,
    payload.status.discovery_mode_label,
    payload.status.report_freshness === 'stale' ? 'Stale export' : 'Current export',
    `Rank ${selected.rank}`,
    selected.trust.trust_state_label,
    selected.trust.validation_status_label,
    selected.trust.review_posture_label,
    selected.trust.manual_verification_required ? 'Manual verification required' : 'No extra manual verification flagged'
  ])
  const gradientMarkup = selected.method_summary.gradient_profile.length
    ? `<div class="gradient-grid">${selected.method_summary.gradient_profile
        .map(
          (point) =>
            `<div class="gradient-row"><span>${escapeHtml(formatRuntime(point.time_min))} min</span><span>${escapeHtml(String(point.percent_b))}% B</span></div>`
        )
        .join('')}</div>`
    : '<p class="empty-state">No gradient profile was returned for this recommendation.</p>'
  const skippedPapersMarkup = payload.skipped_papers.length
    ? `<div class="card-stack">${payload.skipped_papers
        .map(
          (paper) => `
            <article class="card">
              <p class="eyebrow">${escapeHtml(paper.stage_label)}</p>
              <h4>${escapeHtml(paper.title)}</h4>
              <p>${escapeHtml(paper.reason)}</p>
              ${
                paper.url
                  ? `<p><a href="${escapeHtml(paper.url)}">${escapeHtml(paper.url)}</a></p>`
                  : ''
              }
            </article>
          `
        )
        .join('')}</div>`
    : '<p class="empty-state">No skipped-paper diagnostics were returned for this report.</p>'
  const alternativesMarkup = payload.ranked_alternatives.length
    ? `<div class="card-stack">${payload.ranked_alternatives
        .map(
          (alternative) => `
            <article class="card">
              <div class="card-header">
                <p class="eyebrow">Rank ${escapeHtml(String(alternative.rank))}</p>
                <p class="metric">${escapeHtml(alternative.total_fit_percent)}</p>
              </div>
              <h4>${escapeHtml(alternative.title)}</h4>
              <p class="subtle">${escapeHtml(alternative.citation)}</p>
              <div class="pill-row">
                ${renderPills([
                  alternative.source_kind_label,
                  alternative.trust_state_label,
                  alternative.validation_status_label,
                  alternative.review_posture_label,
                  `${alternative.runtime_min} min runtime`
                ])}
              </div>
              <p>${escapeHtml(alternative.comparison_summary)}</p>
            </article>
          `
        )
        .join('')}</div>`
    : '<p class="empty-state">No additional ranked alternatives were returned.</p>'

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(payload.title)}</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7fa;
        --panel: #ffffff;
        --panel-alt: #f8fafc;
        --text: #142136;
        --muted: #5d6878;
        --line: #d9e1ea;
        --primary: #2643e9;
        --success-bg: #edf9f2;
        --success-text: #1e6b45;
        --warning-bg: #fff4dc;
        --warning-text: #8a6200;
        --shadow: 0 20px 50px rgba(20, 33, 54, 0.08);
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: linear-gradient(180deg, #eef3ff 0%, var(--bg) 28%, var(--bg) 100%);
        color: var(--text);
      }

      main {
        max-width: 1080px;
        margin: 0 auto;
        padding: 40px 20px 56px;
      }

      section {
        margin-top: 24px;
        padding: 24px;
        border: 1px solid var(--line);
        border-radius: 18px;
        background: var(--panel);
        box-shadow: var(--shadow);
      }

      h1, h2, h3, h4, p {
        margin: 0;
      }

      h1 {
        font-size: clamp(2rem, 4vw, 3rem);
        line-height: 1;
        letter-spacing: -0.04em;
      }

      h2 {
        font-size: 1.2rem;
        margin-bottom: 14px;
        letter-spacing: -0.02em;
      }

      h3 {
        font-size: 1rem;
        margin-bottom: 12px;
      }

      h4 {
        font-size: 1rem;
        margin-bottom: 8px;
      }

      p {
        line-height: 1.55;
      }

      a {
        color: var(--primary);
        word-break: break-all;
      }

      .hero {
        padding: 28px;
        background: linear-gradient(145deg, #ffffff 0%, #f2f5ff 100%);
      }

      .hero-top {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: space-between;
        gap: 20px;
      }

      .eyebrow {
        margin-bottom: 8px;
        color: var(--primary);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
      }

      .subtle {
        color: var(--muted);
      }

      .lede {
        margin-top: 14px;
        max-width: 760px;
        color: var(--muted);
      }

      .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 16px;
      }

      .pill {
        display: inline-flex;
        align-items: center;
        padding: 6px 10px;
        border: 1px solid var(--line);
        border-radius: 999px;
        background: var(--panel-alt);
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .status-banner {
        margin-top: 20px;
        padding: 16px 18px;
        border-radius: 14px;
        background: ${payload.status.manual_verification_required ? 'var(--warning-bg)' : 'var(--success-bg)'};
        color: ${payload.status.manual_verification_required ? 'var(--warning-text)' : 'var(--success-text)'};
      }

      .grid {
        display: grid;
        gap: 16px;
      }

      .grid.two {
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      }

      .detail-list {
        display: grid;
        gap: 10px;
      }

      .detail-row {
        display: grid;
        grid-template-columns: minmax(0, 180px) minmax(0, 1fr);
        gap: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--line);
      }

      .detail-row:last-child {
        border-bottom: 0;
        padding-bottom: 0;
      }

      dt {
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      dd {
        margin: 0;
      }

      .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
      }

      .metric-card,
      .card {
        padding: 16px;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: var(--panel-alt);
      }

      .metric-value {
        margin-top: 8px;
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.04em;
      }

      .card-stack {
        display: grid;
        gap: 12px;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: baseline;
      }

      .metric {
        font-size: 1.2rem;
        font-weight: 700;
        letter-spacing: -0.04em;
      }

      .bullet-list {
        margin: 0;
        padding-left: 20px;
        display: grid;
        gap: 8px;
      }

      .quote {
        padding: 16px;
        border-left: 4px solid var(--primary);
        background: #f2f6ff;
        border-radius: 0 14px 14px 0;
      }

      .gradient-grid {
        display: grid;
        gap: 8px;
      }

      .gradient-row {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 10px 12px;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-alt);
      }

      .empty-state {
        color: var(--muted);
      }

      .footnote {
        margin-top: 14px;
        font-size: 0.9rem;
        color: var(--muted);
      }

      @media (max-width: 720px) {
        .detail-row {
          grid-template-columns: 1fr;
          gap: 6px;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="hero-top">
          <div>
            <p class="eyebrow">Silico Agent Export Analysis</p>
            <h1>${escapeHtml(selected.title)}</h1>
            <p class="lede">${escapeHtml(payload.status.disclaimer)}</p>
          </div>
          <div class="subtle">
            <p><strong>Generated:</strong> ${escapeHtml(payload.status.generated_at_label)}</p>
            <p><strong>Export version:</strong> ${escapeHtml(payload.status.export_version)}</p>
          </div>
        </div>
        <div class="pill-row">${summaryPills}</div>
        <div class="status-banner">
          <p><strong>Review posture:</strong> ${escapeHtml(selected.trust.review_posture_label)}. <strong>Verification posture:</strong> ${escapeHtml(selected.trust.verification_posture_label)}.</p>
          <p>${escapeHtml(payload.status.report_freshness_label)}</p>
        </div>
      </section>

      <section>
        <h2>Request Context</h2>
        <dl class="detail-list">
          ${renderDetailRows([
            { label: 'Request', value: payload.request_summary.request_text || 'Not provided' },
            { label: 'Analyte', value: payload.request_summary.analyte_name || 'Not provided' },
            {
              label: 'Resolved target name',
              value: payload.request_summary.target_resolved_name || 'Not resolved'
            },
            {
              label: 'Target SMILES',
              value: payload.request_summary.target_smiles || 'Not provided'
            },
            { label: 'Matrix', value: payload.request_summary.matrix || 'Not provided' },
            {
              label: 'Detector requirement',
              value: payload.request_summary.require_mass_spectrometry ? 'MS required' : 'UV/PDA acceptable'
            },
            {
              label: 'Max runtime',
              value:
                typeof payload.request_summary.max_run_time_min === 'number'
                  ? `${payload.request_summary.max_run_time_min} min`
                  : 'Not specified'
            },
            {
              label: 'Secondary analytes',
              value: payload.request_summary.impurities.length
                ? payload.request_summary.impurities
                    .map((impurity) =>
                      impurity.name
                        ? `${impurity.name} (${impurity.smiles})`
                        : impurity.smiles
                    )
                    .join('; ')
                : 'No secondary analyte inputs'
            }
          ])}
        </dl>
      </section>

      <section>
        <h2>System Constraints</h2>
        <dl class="detail-list">
          ${renderDetailRows([
            {
              label: 'Column manufacturer',
              value: payload.system_constraints.column_manufacturer || 'Not provided'
            },
            {
              label: 'Column name',
              value: payload.system_constraints.column_name || 'Not provided'
            },
            {
              label: 'Stationary phase',
              value: payload.system_constraints.column_chemistry || 'Not provided'
            },
            {
              label: 'Column dimensions',
              value:
                payload.system_constraints.column_length_mm !== null ||
                payload.system_constraints.column_inner_diameter_mm !== null
                  ? `${payload.system_constraints.column_length_mm ?? 'n/a'} mm × ${payload.system_constraints.column_inner_diameter_mm ?? 'n/a'} mm`
                  : 'Not provided'
            },
            {
              label: 'Particle size',
              value:
                payload.system_constraints.particle_size_um !== null
                  ? `${payload.system_constraints.particle_size_um} um`
                  : 'Not provided'
            },
            {
              label: 'Available solvents',
              value: payload.system_constraints.available_solvents.length
                ? payload.system_constraints.available_solvents.join(', ')
                : 'Not specified'
            },
            {
              label: 'Detector types',
              value: payload.system_constraints.detector_types.length
                ? payload.system_constraints.detector_types.join(', ')
                : 'Not specified'
            }
          ])}
        </dl>
      </section>

      <section>
        <h2>Selected Recommendation</h2>
        <div class="grid two">
          <div class="metric-card">
            <p class="eyebrow">Primary candidate</p>
            <h3>${escapeHtml(selected.title)}</h3>
            <p class="subtle">${escapeHtml(selected.citation)}</p>
            <div class="pill-row">
              ${renderPills([
                selected.source_kind_label,
                `Rank ${selected.rank}`,
                selected.trust.trust_state_label,
                selected.trust.validation_status_label,
                selected.trust.review_posture_label
              ])}
            </div>
          </div>
          <div class="metric-card">
            <p class="eyebrow">Selection rationale</p>
            <p>${escapeHtml(selected.comparison_summary)}</p>
            <p class="footnote">${escapeHtml(selected.ranking_summary)}</p>
          </div>
        </div>
      </section>

      <section>
        <h2>Trust And Review Posture</h2>
        <div class="grid two">
          <div class="card">
            <h3>Status summary</h3>
            <dl class="detail-list">
              ${renderDetailRows([
                { label: 'Trust state', value: selected.trust.trust_state_label },
                { label: 'Validation posture', value: selected.trust.validation_status_label },
                { label: 'Review posture', value: selected.trust.review_posture_label },
                { label: 'Verification posture', value: selected.trust.verification_posture_label },
                {
                  label: 'Retrieval readiness',
                  value: selected.trust.retrieval_ready
                    ? 'Ready for retrieval reuse'
                    : 'Not yet retrieval-ready'
                },
                {
                  label: 'Manual verification',
                  value: selected.trust.manual_verification_required
                    ? 'Required before operational use'
                    : 'No extra manual verification flagged'
                },
                {
                  label: 'Corpus origin',
                  value: selected.trust.corpus_origin_label
                },
                {
                  label: 'Review record',
                  value: selected.trust.review_record_id || 'Not linked'
                }
              ])}
            </dl>
          </div>
          <div class="card">
            <h3>Warnings and issues</h3>
            <div class="metric-grid">
              <div class="metric-card">
                <p class="eyebrow">Warnings</p>
                <p class="metric-value">${escapeHtml(String(selected.trust.warning_count))}</p>
              </div>
              <div class="metric-card">
                <p class="eyebrow">Issue count</p>
                <p class="metric-value">${escapeHtml(String(selected.trust.issue_count_total))}</p>
              </div>
            </div>
            <div class="footnote">
              ${renderListItems(selected.diagnostics.warnings)}
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2>Method Summary</h2>
        <div class="metric-grid">
          <div class="metric-card">
            <p class="eyebrow">Total fit</p>
            <p class="metric-value">${escapeHtml(selected.scoring.total_fit_percent)}</p>
          </div>
          <div class="metric-card">
            <p class="eyebrow">Runtime</p>
            <p class="metric-value">${escapeHtml(selected.method_summary.runtime_min)}</p>
          </div>
          <div class="metric-card">
            <p class="eyebrow">Flow rate</p>
            <p class="metric-value">${escapeHtml(selected.method_summary.flow_rate_ml_min)}</p>
          </div>
          <div class="metric-card">
            <p class="eyebrow">Temperature</p>
            <p class="metric-value">${escapeHtml(selected.method_summary.column_temperature_c)}</p>
          </div>
        </div>
        <div class="grid two" style="margin-top: 16px;">
          <div class="card">
            <h3>Method details</h3>
            <dl class="detail-list">
              ${renderDetailRows([
                { label: 'Mobile phase A', value: selected.method_summary.mobile_phase_a },
                { label: 'Mobile phase B', value: selected.method_summary.mobile_phase_b },
                { label: 'Gradient summary', value: selected.method_summary.gradient_summary },
                { label: 'Extraction rationale', value: selected.extraction_rationale }
              ])}
            </dl>
          </div>
          <div class="card">
            <h3>Score breakdown</h3>
            <dl class="detail-list">
              ${renderDetailRows([
                { label: 'System match', value: selected.scoring.system_match_percent },
                { label: 'Analyte match', value: selected.scoring.analyte_match_percent },
                { label: 'Matrix fit', value: selected.scoring.matrix_fit_percent },
                { label: 'Practical fit', value: selected.scoring.practical_fit_percent },
                {
                  label: 'Extraction confidence',
                  value: selected.scoring.extraction_confidence_percent
                },
                {
                  label: 'Literature relevance',
                  value: selected.scoring.literature_relevance_percent
                }
              ])}
            </dl>
          </div>
        </div>
        <div class="card" style="margin-top: 16px;">
          <h3>Gradient profile</h3>
          ${gradientMarkup}
          <div class="footnote">
            ${renderListItems(selected.diagnostics.scaling_notes)}
          </div>
        </div>
      </section>

      <section>
        <h2>Evidence And Source Context</h2>
        <div class="grid two">
          <div class="card">
            <h3>Source document</h3>
            <dl class="detail-list">
              ${renderDetailRows([
                { label: 'Title', value: selected.source_document.title || 'Not returned' },
                { label: 'Source type', value: selected.source_document.source_type_label },
                {
                  label: 'Published year',
                  value:
                    selected.source_document.published_year !== null
                      ? String(selected.source_document.published_year)
                      : 'Not returned'
                },
                { label: 'DOI', value: selected.source_document.doi || 'Not returned' },
                { label: 'URL', value: selected.source_document.url || 'Not returned' },
                { label: 'File name', value: selected.source_document.file_name || 'Not returned' },
                {
                  label: 'Source document id',
                  value: selected.source_document.source_document_id
                }
              ])}
            </dl>
          </div>
          <div class="card">
            <h3>Supporting match evidence</h3>
            ${
              selected.evidence.supporting_match_evidence
                ? `<div class="quote">
                    <p class="eyebrow">${escapeHtml(selected.evidence.supporting_match_evidence.meta)}</p>
                    <p>${escapeHtml(selected.evidence.supporting_match_evidence.text)}</p>
                  </div>`
                : '<p class="empty-state">No supporting match snippet was returned for this recommendation.</p>'
            }
          </div>
        </div>
        <div class="card" style="margin-top: 16px;">
          <h3>Evidence snippets</h3>
          ${
            selected.evidence.snippets.length
              ? `<div class="card-stack">${selected.evidence.snippets
                  .map(
                    (snippet) => `
                      <article class="card">
                        <p class="eyebrow">${escapeHtml(snippet.meta)}</p>
                        <p>${escapeHtml(snippet.text)}</p>
                      </article>
                    `
                  )
                  .join('')}</div>`
              : '<p class="empty-state">No evidence snippets were returned for this recommendation.</p>'
          }
        </div>
      </section>

      <section>
        <h2>Alternative Candidates</h2>
        ${alternativesMarkup}
      </section>

      <section>
        <h2>Report Diagnostics</h2>
        <div class="grid two">
          <div class="card">
            <h3>Search context</h3>
            <dl class="detail-list">
              ${renderDetailRows([
                { label: 'Source mode', value: payload.status.source_mode_label },
                { label: 'Discovery mode', value: payload.status.discovery_mode_label },
                { label: 'Freshness', value: payload.status.report_freshness_label },
                {
                  label: 'Search query',
                  value: payload.status.search_query || 'No query was returned'
                },
                {
                  label: 'Candidates in report',
                  value: String(payload.status.recommendation_count)
                },
                {
                  label: 'Papers screened',
                  value:
                    payload.status.discovered_paper_count !== null
                      ? String(payload.status.discovered_paper_count)
                      : 'Not returned'
                }
              ])}
            </dl>
          </div>
          <div class="card">
            <h3>Skipped-paper diagnostics</h3>
            ${skippedPapersMarkup}
          </div>
        </div>
        <p class="footnote">
          This file also embeds a machine-readable JSON payload in <code>script#silico-export-payload</code> for traceability and downstream tooling.
        </p>
      </section>
    </main>
    <script id="silico-export-payload" type="application/json">${embeddedJson}</script>
  </body>
</html>`
}

export function downloadAnalysisExport(input: BuildAnalysisExportInput): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    throw new Error('Analysis export is only available in the browser.')
  }

  const payload = buildAnalysisExportPayload(input)
  const html = renderAnalysisExportHtml(payload)
  const filename = buildAnalysisExportFilename(payload)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const objectUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = objectUrl
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => {
    window.URL.revokeObjectURL(objectUrl)
  }, 0)

  return filename
}
