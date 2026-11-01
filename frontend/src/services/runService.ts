import { apiDownload, apiRequest } from "./api";
import type { ApiPage } from "./api";

export type RunStatus = "PENDING" | "RUNNING" | "SUCCESS" | "PARTIAL" | "FAILED" | "CANCELLED";

export interface RunCounts {
  input: number;
  accepted: number;
  rejected: number;
  duplicates: number;
  published: number;
}

export interface RunStage {
  stage_name: string;
  attempt_id: string;
  status: string;
  input_count: number;
  output_count: number;
  reject_count: number;
  duration_ms: number;
  details: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
}

export interface PipelineRun {
  run_id: string;
  pipeline_id: string;
  source_file_id: string;
  status: RunStatus;
  counts: RunCounts;
  profile: Record<string, unknown>;
  error: { code: string; message: string } | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  stages: RunStage[];
}

export interface QuarantinedRecord {
  attempt_id: string;
  source_file_id: string;
  source_row_number: number;
  original_payload: Record<string, string | string[] | null>;
  reason_code: string;
  rejection_reasons: string[];
}

export interface QuarantinePage {
  items: QuarantinedRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface Reconciliation {
  run_id: string;
  counts: RunCounts;
  accepted_amounts_by_currency: Record<string, string>;
  published_amounts_by_currency: Record<string, string>;
  balanced: boolean;
  checks: Record<string, boolean>;
}

export type Page<T> = ApiPage<T>;

export interface DuplicateRecord {
  run_id: string;
  attempt_id: string;
  source_row_number: number;
  duplicate_of_row_number: number;
  duplicate_key: string;
}

export interface AuditEvent {
  audit_event_id: number;
  run_id: string | null;
  event_type: string;
  event_data: Record<string, unknown>;
  created_at: string;
}

export type ValidationStatus = "PASS" | "FAIL" | "WARNING" | "ERROR" | "SKIPPED" | "NOT_APPLICABLE" | "REQUIRES_CONFIGURATION" | "BLOCKED";

export interface ValidationExecutionRecord {
  validation_execution_id: number;
  run_id: string;
  attempt_id: string;
  validation_id: string;
  name: string;
  category: string;
  status: ValidationStatus;
  severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  applicability: string;
  applicability_reason: string;
  execution_stage: string;
  checked_rows: number;
  passed_rows: number;
  failed_rows: number;
  failure_percentage: number;
  affected_columns: string[];
  failure_examples: Array<{ source_row_number?: number }>;
  message: string;
  recommendation: string | null;
  execution_time_ms: number;
  rule_version: string;
  configuration_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface ValidationRunSummary {
  attempt_id: string;
  total_records: number;
  executed: number;
  passed: number;
  failed: number;
  warnings: number;
  errors: number;
  skipped: number;
  not_applicable: number;
  requires_configuration: number;
  blocked: number;
  applicable: number;
  checked_rows: number;
  failed_rows: number;
  execution_duration_ms: number;
}

export interface ValidationRunResults {
  run_id: string;
  attempt_id: string | null;
  summary: ValidationRunSummary | null;
  items: ValidationExecutionRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface ValidationHistoryRecord extends ValidationExecutionRecord {
  pipeline_id: string;
  source_file_id: string;
  original_filename: string;
  attempt_number: number;
}

export interface ValidationHistory {
  items: ValidationHistoryRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface QualityScore {
  run_id: string;
  attempt_id: string | null;
  score: number | null;
  score_status: "AVAILABLE" | "INSUFFICIENT_DATA";
  coverage_percent: number | null;
  applicable_checks: number;
  executed_checks: number;
  passed_checks: number;
  failed_checks: number;
  warning_checks: number;
  skipped_checks: number;
  not_applicable_checks: number;
  requires_configuration_checks: number;
  blocked_checks: number;
  dataset_level_failures: number;
  catalog_total: number;
  catalog_eligible_checks: number;
  catalog_coverage_percent: number | null;
  insufficiency_reasons: string[];
  score_scope: string;
  methodology: Record<string, unknown>;
}

export interface QualityBaseline {
  baseline_id: string;
  dataset_identity: string;
  pipeline_id: string;
  source_file_id: string;
  run_id: string;
  attempt_id: string;
  schema_version: string | null;
  baseline_version: number;
  sample_size: number;
  reference_period_start: string;
  reference_period_end: string;
  statistical_configuration: Record<string, unknown>;
  created_at: string;
}

export interface ValidationFailureChange {
  validation_id: string;
  baseline_status: string | null;
  current_status: string | null;
  baseline_failure_rate: number | null;
  current_failure_rate: number | null;
  delta_percentage_points: number | null;
  assessment: string;
}

export interface QualityBaselineComparison {
  baseline_id: string;
  baseline_version: number;
  dataset_identity: string;
  target_run_id: string;
  target_attempt_id: string;
  target_source_file_id: string;
  row_count_change: { baseline: number; current: number; delta: number; delta_percent: number | null };
  null_rate_changes: Array<{ column: string; baseline_rate: number | null; current_rate: number | null; delta_percentage_points: number | null }>;
  duplicate_rate_change: { baseline_rate: number | null; current_rate: number | null; delta_percentage_points: number | null };
  schema_drift: { added_columns: string[]; missing_columns: string[]; type_changes: Array<{ column: string; baseline_type: string | null; current_type: string | null }>; changed: boolean };
  numeric_distribution_drift: Array<Record<string, unknown> & { column: string; status: string }>;
  value_shape_distribution_drift: Array<Record<string, unknown> & { column: string; status: string }>;
  freshness_changes: Array<Record<string, unknown> & { column: string }>;
  outlier_changes: Array<Record<string, unknown> & { column: string }>;
  validation_failure_changes: ValidationFailureChange[];
  anomaly_signals: Array<Record<string, unknown> & { type: string; confirmed_invalid_records: false }>;
  confirmed_invalid_records: false;
  limitations: string[];
}

export type QualityRunComparison = Omit<QualityBaselineComparison, "baseline_id" | "baseline_version" | "dataset_identity" | "target_run_id" | "target_attempt_id" | "target_source_file_id"> & {
  reference_run_id: string;
  reference_attempt_id: string;
  reference_pipeline_id: string;
  reference_source_file_id: string;
  reference_filename: string;
  comparison_run_id: string;
  comparison_attempt_id: string;
  comparison_source_file_id: string;
  comparison_filename: string;
};

export interface QualityBaselinePage {
  items: QualityBaseline[];
  total: number;
  page: number;
  page_size: number;
}

export interface ValidationAnalytics {
  days: number;
  from_date: string;
  through_date: string;
  pipeline_id: string | null;
  total_results: number;
  status_counts: Record<string, number>;
  critical_failures: number;
  requires_configuration: number;
  average_execution_time_ms: number | null;
  failures_by_category: Array<{ category: string; failures: number }>;
  most_failing_checks: Array<{ validation_id: string; name: string; category: string; failures: number }>;
  daily_trend: Array<{ date: string; executions: number; failures: number; warnings: number }>;
  quality_trend: Array<{ run_id: string; attempt_id: string; created_at: string; score: number; coverage_percent: number }>;
  quality_trend_insufficient_attempts: number;
  scope: string;
}

// PREVIEW_ONLY is used only by the Validation Center's generated UI preview rows;
// the backend catalog API never returns it.
export type ValidationImplementationStatus = "FULLY_IMPLEMENTED" | "PARTIALLY_IMPLEMENTED" | "CATALOG_ONLY" | "REQUIRES_INTEGRATION" | "NOT_IMPLEMENTED" | "DEPRECATED" | "PREVIEW_ONLY";

export interface ValidationCatalogItem {
  validation_id: string;
  catalog_number: number;
  name: string;
  description: string;
  category: string;
  severity: string;
  applicability_requirements: string[];
  required_columns: string[];
  required_metadata: string[];
  configuration_requirements: string[];
  implementation_status: ValidationImplementationStatus;
  implementation_version: string;
  test_status: string;
  limitations: string[];
  enabled: boolean;
  supported_file_types: string[];
  applicability_support: string;
  definition_source: string;
  last_executed_at: string | null;
}

export interface ValidationCatalog {
  source_status: "READY" | "PARTIAL" | "SOURCE_MISSING" | "NOT_IMPORTED";
  message: string | null;
  counts: Record<string, number>;
  filter_options: {
    categories: string[];
    severities: string[];
    applicabilities: string[];
    supported_file_types: string[];
  };
  items: ValidationCatalogItem[];
  total: number;
  page: number;
  page_size: number;
}

export function createRun(source_file_id: string, pipeline_id?: string): Promise<PipelineRun> {
  return apiRequest<PipelineRun>("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_file_id, ...(pipeline_id ? { pipeline_id } : {}) }),
  });
}

export function getRun(run_id: string): Promise<PipelineRun> {
  return apiRequest<PipelineRun>(`/runs/${encodeURIComponent(run_id)}`);
}

export function listRuns(page = 1, pageSize = 25): Promise<Page<PipelineRun>> {
  return apiRequest<Page<PipelineRun>>(`/runs?page=${page}&page_size=${pageSize}`);
}

export function getQuarantine(options: { runId?: string; page?: number; pageSize?: number } = {}): Promise<QuarantinePage> {
  return apiRequest<QuarantinePage>(`/quarantine${buildQuery({
    run_id: options.runId,
    page: options.page ?? 1,
    page_size: options.pageSize ?? 25,
  })}`);
}

export function getDuplicates(options: { runId?: string; page?: number; pageSize?: number } = {}): Promise<Page<DuplicateRecord>> {
  return apiRequest<Page<DuplicateRecord>>(`/duplicates${buildQuery({
    run_id: options.runId,
    page: options.page ?? 1,
    page_size: options.pageSize ?? 25,
  })}`);
}

export function getAudit(options: { runId?: string; page?: number; pageSize?: number } = {}): Promise<Page<AuditEvent>> {
  return apiRequest<Page<AuditEvent>>(`/audit${buildQuery({
    run_id: options.runId,
    page: options.page ?? 1,
    page_size: options.pageSize ?? 25,
  })}`);
}

export function getReconciliation(run_id: string): Promise<Reconciliation> {
  return apiRequest<Reconciliation>(`/reconciliation/${encodeURIComponent(run_id)}`);
}

export function getValidationRunResults(
  runId: string,
  options: { attemptId?: string; page?: number; pageSize?: number; status?: string; severity?: string; category?: string; validationId?: string; executionStage?: string } = {},
): Promise<ValidationRunResults> {
  return apiRequest<ValidationRunResults>(`/validation/runs/${encodeURIComponent(runId)}${buildQuery({
    attempt_id: options.attemptId,
    page: options.page ?? 1,
    page_size: options.pageSize ?? 25,
    status: options.status,
    severity: options.severity,
    category: options.category,
    validation_id: options.validationId,
    execution_stage: options.executionStage,
  })}`);
}

export function downloadValidationRunResults(
  runId: string,
  options: { attemptId?: string; status?: string; severity?: string; category?: string; validationId?: string; executionStage?: string } = {},
  format: "json" | "csv" = "json",
): Promise<Blob> {
  return apiDownload(`/validation/runs/${encodeURIComponent(runId)}/export${buildQuery({
    attempt_id: options.attemptId,
    status: options.status,
    severity: options.severity,
    category: options.category,
    validation_id: options.validationId,
    execution_stage: options.executionStage,
    format,
  })}`);
}

export function getValidationHistory(options: {
  page?: number;
  pageSize?: number;
  search?: string;
  validationId?: string;
  category?: string;
  status?: string;
  pipelineId?: string;
  sourceFileId?: string;
  createdFrom?: string;
  createdTo?: string;
} = {}): Promise<ValidationHistory> {
  return apiRequest<ValidationHistory>(`/validation/history${buildQuery({
    page: options.page ?? 1,
    page_size: options.pageSize ?? 25,
    search: options.search,
    validation_id: options.validationId,
    category: options.category,
    status: options.status,
    pipeline_id: options.pipelineId,
    source_file_id: options.sourceFileId,
    created_from: options.createdFrom,
    created_to: options.createdTo,
  })}`);
}

export function getRunQualityScore(runId: string, attemptId?: string): Promise<QualityScore> {
  return apiRequest<QualityScore>(`/quality/runs/${encodeURIComponent(runId)}/score${buildQuery({ attempt_id: attemptId })}`);
}

export function listQualityBaselines(options: { datasetIdentity?: string; pipelineId?: string; page?: number; pageSize?: number } = {}): Promise<QualityBaselinePage> {
  return apiRequest<QualityBaselinePage>(`/quality/baselines${buildQuery({
    dataset_identity: options.datasetIdentity,
    pipeline_id: options.pipelineId,
    page: options.page ?? 1,
    page_size: options.pageSize ?? 50,
  })}`);
}

export function createQualityBaseline(runId: string, datasetIdentity?: string, attemptId?: string): Promise<QualityBaseline> {
  return apiRequest<QualityBaseline>("/quality/baselines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, ...(datasetIdentity?.trim() ? { dataset_identity: datasetIdentity.trim() } : {}), ...(attemptId ? { attempt_id: attemptId } : {}) }),
  });
}

export function compareQualityBaseline(baselineId: string, runId: string, attemptId?: string): Promise<QualityBaselineComparison> {
  return apiRequest<QualityBaselineComparison>(`/quality/baselines/${encodeURIComponent(baselineId)}/compare${buildQuery({ run_id: runId, attempt_id: attemptId })}`);
}

export function compareQualityRuns(referenceRunId: string, comparisonRunId: string): Promise<QualityRunComparison> {
  return apiRequest<QualityRunComparison>(`/quality/runs/compare${buildQuery({ reference_run_id: referenceRunId, comparison_run_id: comparisonRunId })}`);
}

export function getValidationAnalytics(options: { days?: number; pipelineId?: string } = {}): Promise<ValidationAnalytics> {
  return apiRequest<ValidationAnalytics>(`/validation/analytics${buildQuery({ days: options.days ?? 30, pipeline_id: options.pipelineId })}`);
}

export function getValidationCatalog(options: {
  page?: number;
  pageSize?: number;
  search?: string;
  validationId?: string;
  name?: string;
  category?: string;
  severity?: string;
  implementationStatus?: string;
  enabled?: boolean;
  applicability?: string;
  supportedFileType?: string;
} = {}): Promise<ValidationCatalog> {
  return apiRequest<ValidationCatalog>(`/validation/catalog${buildQuery({
    page: options.page ?? 1,
    page_size: options.pageSize ?? 25,
    search: options.search,
    validation_id: options.validationId,
    name: options.name,
    category: options.category,
    severity: options.severity,
    implementation_status: options.implementationStatus,
    enabled: options.enabled,
    applicability: options.applicability,
    supported_file_type: options.supportedFileType,
  })}`);
}

export function retryRun(run_id: string): Promise<PipelineRun> {
  return apiRequest<PipelineRun>(`/runs/${encodeURIComponent(run_id)}/retry`, { method: "POST" });
}

function buildQuery(values: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}
