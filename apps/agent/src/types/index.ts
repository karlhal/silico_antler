export interface SystemSpecs {
  columnManufacturer: string;
  customManufacturer?: string;
  columnName: string;
  columnChemistry: string;
  customChemistry?: string;
  columnLengthMm: number | null;
  columnIdMm: number | null;
  particleSizeUm: number | null;
  availableSolvents: string[];
  detectorTypes: string[];
  instrumentModes: string[];
  maxPressureBar: number | null;
}

export interface DiscoveryTarget {
  requestText: string;
  analyteName: string;
  targetSmiles: string;
  targetResolvedName?: string | null;
  targetLookupSource?: string | null;
  targetLookupError?: string | null;
  targetResolving?: boolean;
  impurities: Compound[];
  matrix: string;
  customMatrix?: string;
  requireMS: boolean;
  maxRunTimeMin: number | null;
}

export type DiscoverySource = 'local_corpus' | 'open_access';

export type RecognitionState =
  | 'recognizing'
  | 'recognized'
  | 'ambiguous'
  | 'unresolved'
  | 'error';

export type FieldProvenance = 'provided' | 'recognized' | 'inferred' | 'missing';

export type StructurePreviewState = 'idle' | 'loading' | 'ready' | 'unavailable' | 'error';

export interface SourceTextSpan {
  start: number;
  end: number;
  text: string;
}

export interface RecognizedField {
  field: 'analyte' | 'impurity' | 'matrix' | 'detector' | 'runtime' | 'source_mode';
  value: string;
  status: RecognitionState;
  provenance: FieldProvenance;
  confidenceLabel: string;
  sourceTextSpan?: SourceTextSpan | null;
}

export interface RecognizedAnalyte extends RecognizedField {
  id: string;
  field: 'analyte' | 'impurity';
  resolvedSmiles?: string | null;
  resolvedName?: string | null;
  structurePreviewState: StructurePreviewState;
  lookupSource?: string | null;
  lookupError?: string | null;
  ambiguityCandidates?: string[];
}

export interface PromptRecognitionSummary {
  analytes: RecognizedAnalyte[];
  matrix: RecognizedField | null;
  detector: RecognizedField | null;
  runtime: RecognizedField | null;
  sourceMode: RecognizedField | null;
  unresolvedItems: string[];
}

export interface Compound {
  id: string;
  smiles: string;
  name: string | null;
  resolved: boolean;
  resolving?: boolean;
  lookupSource?: string | null;
  lookupError?: string | null;
}

export type DocumentKind = 'pdf' | 'html' | 'manual' | 'seeded';
export type ValidationStatus = 'unvalidated' | 'valid' | 'invalid' | 'needs_review';
export type ReviewRecordState = 'seeded' | 'draft' | 'approved' | 'rejected';
export type CorpusOrigin = 'seeded' | 'review_promoted';
export type RetrievalMatchType = 'exact' | 'similarity';
export type RecommendationTrustState =
  | 'review_backed'
  | 'seeded_corpus'
  | 'open_access_extracted'
  | 'local_file_extracted';
export type RecommendationRankingMode = 'target_only' | 'target_plus_impurities';
export type ImpurityHandlingMode =
  | 'not_requested'
  | 'active'
  | 'requested_but_untrusted';
export type RecommendationQueryIntent =
  | 'exact_request'
  | 'analyte_matrix_anchor'
  | 'family_expansion'
  | 'matrix_relaxed_fallback'
  | 'context_repair'
  | 'user_supplied';

export interface GradientPoint {
  time_min: number;
  percent_b: number;
}

export interface ScaledMethod {
  is_scaled: boolean;
  flow_rate_ml_min?: number | null;
  injection_volume_ul?: number | null;
  gradient_profile: GradientPoint[];
  run_time_min?: number | null;
  scaling_notes: string[];
  scaling_warnings: string[];
}

export interface EvidenceSnippet {
  text: string;
  page_number?: number | null;
  section_label?: string | null;
}

export interface RecommendationScoreBreakdown {
  total_score: number;
  system_match: number;
  analyte_match: number;
  matrix_fit: number;
  practical_fit: number;
  extraction_confidence: number;
  literature_relevance: number;
  features: RecommendationFeatureBreakdown;
}

export interface RecommendationFeatureBreakdown {
  target_chemistry_fit: number;
  impurity_compatibility: number;
  system_fit: number;
  detector_compatibility: number;
  matrix_fit: number;
  runtime_fit: number;
  extraction_completeness: number;
  evidence_quality: number;
  review_trust_prior: number;
  literature_specificity: number;
  missing_data_penalty: number;
}

export interface RecommendationDecisionTrace {
  retrieval_score?: number | null;
  viability_score: number;
  ranking_score: number;
  score_layers?: RecommendationScoreLayers | null;
  screening_model?: 'deterministic' | 'llm_reranker' | null;
  screening_summary?: string | null;
  screening_reasons: string[];
  query_provenance: RecommendationQueryVariant[];
  dominant_differentiator?: string | null;
  beat_runner_up_summary?: string | null;
}

export interface RecommendationScoreLayers {
  retrieval_relevance?: number | null;
  method_viability: number;
  final_fit: number;
  retrieval_relevance_summary: string;
  method_viability_summary: string;
  final_fit_summary: string;
}

export interface RecommendationIssueCounts {
  info: number;
  warning: number;
  error: number;
}

export interface RecommendationTrust {
  trust_state: RecommendationTrustState;
  validation_status: ValidationStatus;
  retrieval_ready: boolean;
  manual_verification_required: boolean;
  issue_counts: RecommendationIssueCounts;
  warning_summary: string[];
}

export interface RecommendationRankingContext {
  ranking_mode: RecommendationRankingMode;
  impurity_handling: ImpurityHandlingMode;
  impurity_count: number;
  summary: string;
}

export interface RetrievalImpurityMatch {
  query_canonical_smiles: string;
  matched_entity_local_identifier: string;
  matched_entity_display_name?: string | null;
  score: number;
}

export interface RetrievalMatchRationale {
  match_type: RetrievalMatchType;
  matched_entity_local_identifier: string;
  matched_entity_display_name?: string | null;
  matched_entity_observed_retention_time_min?: number | null;
  target_score: number;
  impurity_matches: RetrievalImpurityMatch[];
  aggregate_score: number;
  retrieval_score?: number | null;
  contextual_priors?: RetrievalContextualPriors | null;
  supporting_snippet?: EvidenceSnippet | null;
  summary: string;
}

export interface RetrievalContextualPriors {
  matrix_compatibility: number;
  detector_compatibility: number;
  method_family_compatibility: number;
  review_backed_prior: number;
  retrieval_ready_prior: number;
}

export interface RetrievalReviewSummary {
  record_state: ReviewRecordState;
  review_record_id?: string | null;
  validation_status: ValidationStatus;
  retrieval_ready: boolean;
  corpus_origin?: CorpusOrigin;
}

export interface MobilePhase {
  solvent: string;
  additive?: string | null;
  ph_estimate?: number | null;
}

export interface MethodParameters {
  mobile_phase_a: MobilePhase;
  mobile_phase_b?: MobilePhase | null;
  flow_rate_ml_min: number;
  column_temperature_c?: number | null;
  run_time_min?: number | null;
  gradient_profile: GradientPoint[];
  isocratic_percent_b?: number | null;
}

export interface SourceDocumentMetadata {
  source_document_id: string;
  source_type: DocumentKind;
  title?: string | null;
  doi?: string | null;
  url?: string | null;
  file_name?: string | null;
  published_year?: number | null;
}

export interface SourceDocumentUploadRequest {
  source_document: Omit<SourceDocumentMetadata, 'source_document_id'> & { source_document_id?: string };
  html_content?: string | null;
  pdf_base64?: string | null;
}

export interface MinimalHplcExtractionResponse {
  source_document: SourceDocumentMetadata;
  method_parameters?: MethodParameters | null;
  warnings: string[];
  retrieval_record_ready: boolean;
}

export interface ReviewRecordSummary {
  review_record_id: string;
  source_document_id: string;
  status: ReviewRecordState;
  title?: string | null;
  citation?: string | null;
  created_at: string;
  updated_at: string;
  promote_to_local_corpus: boolean;
}

export interface ReviewRecord {
  review_record_id: string;
  source_document_id: string;
  status: ReviewRecordState;
  extraction_snapshot: MinimalHplcExtractionResponse;
  review_notes?: string | null;
  promote_to_local_corpus: boolean;
  created_at: string;
  updated_at: string;
}

export interface MolecularEntityResolutionInput {
  query_name: string;
  resolved_smiles?: string | null;
}

export interface C12ReviewRecordOrchestrationRequest extends SourceDocumentUploadRequest {
  entity_resolutions?: MolecularEntityResolutionInput[];
  approve_if_ready?: boolean;
  retry_existing?: boolean;
}

export interface C12ReviewRecordOrchestrationResponse {
  source_document_id: string;
  budget: Record<string, unknown>;
  steps: Record<string, unknown>;
  review_record: ReviewRecord;
}

export interface ReviewRecordApproveRequest {
  review_notes?: string | null;
  promote_to_local_corpus?: boolean;
  entity_resolutions?: Record<string, string>;
}

export interface ReviewRecordRejectRequest {
  review_notes?: string | null;
}

export interface RecommendationCandidate {
  paper_id: string;
  title: string;
  citation: string;
  score: RecommendationScoreBreakdown;
  rationale: string;
  source_kind: DocumentKind;
  extraction: MinimalHplcExtractionResponse;
  evidence_snippets: EvidenceSnippet[];
  trust: RecommendationTrust;
  ranking_context: RecommendationRankingContext;
  match_rationale?: RetrievalMatchRationale | null;
  review_summary?: RetrievalReviewSummary | null;
  decision_trace?: RecommendationDecisionTrace | null;
  recommended_method?: ScaledMethod | null;
  doi?: string | null;
  url?: string | null;
  published_year?: number | null;
}

export interface RecommendationQueryVariant {
  variant_id: string;
  intent: RecommendationQueryIntent;
  query_text: string;
}

export interface OpenAccessPaperCandidate {
  paper_id: string;
  title: string;
  doi?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  published_year?: number | null;
  source_name?: string | null;
  abstract?: string | null;
  open_access: boolean;
  query_provenance: RecommendationQueryVariant[];
}

export type CompoundContextConfidence = 'high' | 'medium' | 'low' | 'unresolved';

export interface CompoundSourceIds {
  pubchem_cid?: string | null;
  chembl_id?: string | null;
}

export interface CompoundContext {
  input_label?: string | null;
  input_smiles?: string | null;
  resolved_name?: string | null;
  canonical_smiles?: string | null;
  source_ids: CompoundSourceIds;
  formula?: string | null;
  molecular_weight?: number | null;
  synonyms: string[];
  lookup_sources: string[];
  warnings: string[];
  confidence: CompoundContextConfidence;
}

export interface ExternalEvidenceTrace {
  query_terms_used: string[];
  source_clients_attempted: string[];
  source_clients_succeeded: string[];
  source_clients_failed: string[];
  truncation_warnings: string[];
  skipped_reason_counts: Record<string, number>;
}

export interface RecommendationSkippedPaper {
  paper_id: string;
  title: string;
  stage: 'screening' | 'fetch' | 'extraction';
  reason: string;
  url?: string | null;
  query_provenance: RecommendationQueryVariant[];
}

export type RecommendationRuntimeStatus =
  | 'completed'
  | 'completed_with_degraded_source'
  | 'completed_with_demo_fallback'
  | 'no_trustworthy_candidates'
  | 'upstream_unavailable'
  | 'request_invalid';

export type RecommendationFailureClassification =
  | 'search_failure'
  | 'fetch_failure'
  | 'extraction_failure'
  | 'retrieval_store_unavailable'
  | 'llm_observer_unavailable'
  | 'timeout'
  | 'request_invalid';

export interface RecommendationRuntimeBudget {
  max_papers_requested: number;
  search_budget_used?: number | null;
  queries_attempted: number;
  open_access_timeout_sec?: number | null;
  llm_observer_enabled: boolean;
  rate_limit_policy: string;
}

export interface RecommendationRuntimeSummary {
  request_id: string;
  status: RecommendationRuntimeStatus;
  summary: string;
  degraded: boolean;
  failure_classification?: RecommendationFailureClassification | null;
  budget: RecommendationRuntimeBudget;
  branch_decisions: string[];
}

export interface RecommendationDiscoverySummary {
  discovered_paper_count: number;
  skipped_paper_count: number;
  skipped_papers_truncated: boolean;
  skipped_papers_preview: RecommendationSkippedPaper[];
  considered_candidate_count: number;
  considered_candidates_truncated: boolean;
  repeated_extraction_exception_count: number;
}

export interface RecommendationErrorDetail {
  request_id: string;
  runtime_status: RecommendationRuntimeStatus;
  failure_classification: RecommendationFailureClassification;
  failure_stage?: RecommendationJobStage | null;
  message: string;
  retryable: boolean;
}

export interface MethodRecommendationReport {
  source_mode: 'local_files' | 'local_corpus' | 'open_access';
  search_query_used?: string | null;
  target_compound_context?: CompoundContext | null;
  impurity_compound_contexts?: CompoundContext[];
  external_evidence_trace?: ExternalEvidenceTrace | null;
  discovered_papers: OpenAccessPaperCandidate[];
  skipped_papers: RecommendationSkippedPaper[];
  discovery_summary?: RecommendationDiscoverySummary | null;
  considered_candidates: RecommendationCandidate[];
  recommended_candidate?: RecommendationCandidate | null;
  runtime?: RecommendationRuntimeSummary | null;
}

export interface RecommendationReportMeta {
  source_mode: MethodRecommendationReport['source_mode'];
  search_query_used?: string | null;
  target_compound_context?: CompoundContext | null;
  impurity_compound_contexts: CompoundContext[];
  external_evidence_trace?: ExternalEvidenceTrace | null;
  skipped_papers: RecommendationSkippedPaper[];
  discovered_paper_count: number;
  skipped_paper_count: number;
  skipped_papers_truncated: boolean;
  considered_candidate_count: number;
  considered_candidates_truncated: boolean;
  repeated_extraction_exception_count: number;
  runtime?: RecommendationRuntimeSummary | null;
}

export type RecommendationJobState = 'queued' | 'running' | 'completed' | 'failed';
export type RecommendationJobStage =
  | 'queued'
  | 'query_papers'
  | 'extract_methods'
  | 'match_system'
  | 'scale_physics'
  | 'final_rank'
  | 'completed'
  | 'failed';

export interface RecommendationJobAccepted {
  job_id: string;
  state: RecommendationJobState;
  stage: RecommendationJobStage;
  status_url: string;
}

export interface RecommendationJobStatus {
  job_id: string;
  state: RecommendationJobState;
  stage: RecommendationJobStage;
  message: string;
  created_at: string;
  updated_at: string;
  source_mode: MethodRecommendationReport['source_mode'];
  items_completed: number;
  items_total?: number | null;
  report?: MethodRecommendationReport | null;
  runtime?: RecommendationRuntimeSummary | null;
  error_detail?: RecommendationErrorDetail | null;
  error_message?: string | null;
}

export type DummySurrogateState = 'idle' | 'launching' | 'ready' | 'failed';

export interface DummySurrogatePrediction {
  headline: string;
  summary: string;
  predictedRetentionWindowMin: [number, number];
  confidenceLabel: string;
  signalQualityLabel: string;
}

export interface DummySurrogateWindowScan {
  id: string;
  label: string;
  testedWindow: string;
  posture: 'stable' | 'watch' | 'unstable';
  summary: string;
}

export interface DummySurrogateSession {
  sessionId: string;
  state: Exclude<DummySurrogateState, 'idle'>;
  modeLabel: string;
  simulationLabel: string;
  methodTitle: string;
  prediction: DummySurrogatePrediction;
  operatingWindows: DummySurrogateWindowScan[];
  nextStepLabel: string;
  nextStepSummary: string;
  warnings: string[];
}

export type StepStatus = 'pending' | 'active' | 'completed' | 'error';

export interface ResearchStep {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
  timestamp?: string;
}

export type Recommendation = RecommendationCandidate;

export type WorkflowPhase =
  | 'system_setup'
  | 'target_setup'
  | 'source_selection'
  | 'recognition_verify'
  | 'planning'
  | 'discovering'
  | 'completed'
  | 'failed';

export interface ClarificationQuestion {
  id: string;
  question: string;
  placeholder: string;
}

export interface ClarifyResponse {
  questions: ClarificationQuestion[];
}

export type AgentCachePolicy = 'live_preferred' | 'cached_preferred' | 'demo_safe';
export type AgentStartupHealthStatus = 'healthy' | 'degraded' | 'unavailable';

export interface AgentDesktopRuntimeConfig {
  apiBaseUrl: string;
  methodDevBaseUrl: string;
  operatorModeEnabled: boolean;
  cachePolicy: AgentCachePolicy;
  demoSnapshotVersion: string;
  startupHealthTtlSec: number;
}

export interface AgentServiceHealth {
  status: AgentStartupHealthStatus;
  checkedAt: string;
  endpoint: string;
  responseTimeMs: number | null;
  detail?: string | null;
}

export interface AgentStartupHealth {
  status: AgentStartupHealthStatus;
  checkedAt: string;
  cached: boolean;
  api: AgentServiceHealth;
  methodDev: AgentServiceHealth;
}

export type AgentRuntimeMode = 'live' | 'cached' | 'demo_safe';
export type AgentResultOrigin = 'live' | 'cached' | 'demo_safe' | 'live_degraded';

export type TrustRailStepId =
  | 'source_origin'
  | 'extraction_status'
  | 'validation_review'
  | 'scaling_system_fit'
  | 'recommendation_outcome'
  | 'corpus_reuse';

export type TrustRailStepTone = 'muted' | 'neutral' | 'warning' | 'error' | 'success';

export interface TrustRailStep {
  id: TrustRailStepId;
  label: string;
  value: string;
  detail: string;
  tone: TrustRailStepTone;
}

export interface CachedAgentRunSnapshot {
  schemaVersion: 1;
  requestHash: string;
  createdAt: string;
  origin: AgentResultOrigin;
  request: Record<string, unknown>;
  report: MethodRecommendationReport;
  runtimeSummary: RecommendationRuntimeSummary | null;
}
