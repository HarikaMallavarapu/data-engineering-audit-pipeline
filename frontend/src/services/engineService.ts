import { apiRequest } from "./api";
import type { ApiPage } from "./api";

export interface ColumnProfile {
  name: string;
  inferred_type: string;
  observed_types: Record<string, number>;
  mixed_type: boolean;
  null_count: number;
  null_percent: number;
  distinct_count: number;
  distinct_ratio: number;
  sample_size: number;
  value_shapes: Record<string, number>;
  sample_patterns: string[];
  numeric?: { min: string; max: string; mean: string; median: string; outlier_count_iqr: number };
  string?: { min_length: number; max_length: number; mean_length: number };
  date_formats?: string[];
  regex_suggestion?: RegexSuggestion;
}

export interface RegexSuggestion {
  pattern: string;
  confidence: number;
  sample_count: number;
  matching_count: number;
  non_matching_count: number;
  matching_examples: string[];
  non_matching_examples: string[];
  review_required: boolean;
  note: string;
}

export interface DataProfile {
  columns: string[];
  row_count: number;
  profile_sample_size: number;
  null_counts: Record<string, number>;
  inferred_types: Record<string, string>;
  distinct_counts: Record<string, number>;
  schema_fingerprint: string;
  duplicate_row_count: number;
  column_profiles: ColumnProfile[];
  mapping_candidates: Array<{
    source_column: string;
    suggested_semantic_field: string;
    confidence: number;
    evidence: string[];
    status: string;
  }>;
}

export interface SourceProfileResponse {
  source_file_id: string;
  original_filename: string;
  checksum: string;
  schema_fingerprint: string;
  profile: DataProfile;
}

export interface RuleSuggestion {
  rule_id: string;
  field: string;
  rule_type: string;
  config: Record<string, unknown>;
  severity: "error" | "warning";
  confidence: number;
  enabled: boolean;
  status: string;
  version: number;
  provenance: string;
  explanation?: string;
  sample_evidence?: {
    matching_examples: string[];
    non_matching_examples: string[];
    sample_count: number;
    matching_count: number;
    non_matching_count: number;
  };
}

export interface TransformationSuggestion {
  transform_id: string;
  field: string;
  operator: string;
  config: Record<string, unknown>;
  status: string;
  confidence?: number;
  explanation?: string;
}

export interface SchemaAnalysis {
  mode: "local" | "llm";
  provider: string | null;
  model: string | null;
  fallback_reason?: string;
  dataset_kind: string;
  summary: string;
  columns: Array<{ name: string; semantic_type: string; description: string; pii_risk: boolean }>;
  candidate_key_columns: string[];
  mapping_suggestions: Array<{
    source_column: string;
    semantic_field: string;
    confidence: number;
    explanation: string;
    status: string;
  }>;
  rule_suggestions: RuleSuggestion[];
  transformation_suggestions: TransformationSuggestion[];
  quality_notes: string[];
  usage?: {
    task_type: string;
    provider: string;
    model: string;
    status: string;
    cached: boolean;
    prompt_tokens: number;
    completion_tokens: number;
    estimated_cost_usd: string;
    reported_cost_usd: string | null;
    latency_ms: number;
  };
}

export interface EngineSource {
  source_file_id: string;
  original_filename: string;
  columns: string[];
  checksum: string;
}

export interface SchemaProfileRecord {
  profile_id: string;
  source_file_id: string;
  schema_fingerprint: string;
  version: number;
  status: string;
  mappings: Array<{
    source_column: string;
    semantic_field: string;
    action: "approve" | "edit" | "reject";
    confidence: number;
    explanation: string;
  }>;
}

export interface EngineRuleRecord {
  rule_id: string;
  version: number;
  schema_fingerprint: string;
  status: string;
  definition: Record<string, unknown>;
  created_at?: string;
}

export interface EngineTransformationRecord {
  transform_id: string;
  version: number;
  status: string;
  definition: Record<string, unknown>;
}

export interface EngineRegistry {
  rule_types: string[];
  transformation_operators: string[];
  execution_safety: string;
}

export interface AIStatus {
  configured: boolean;
  provider: string | null;
  model: string | null;
  data_sent: string;
  budget: {
    limit_usd: string;
    used_usd: string;
    reserved_usd: string;
    remaining_usd: string;
    reset_count: number;
  };
  limits: {
    max_input_tokens: number;
    max_output_tokens: number;
    max_retries: number;
    cache_enabled: boolean;
    request_timeout_seconds: number;
  };
}

export interface AIUsageRecord {
  usage_id: number;
  provider: string;
  model: string;
  task_type: string;
  status: string;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: string;
  reported_cost_usd: string | null;
  latency_ms: number;
  created_at: string;
}

export interface DryRunPlan {
  plan_id: string;
  version: number;
  status: string;
  component_sequence: string[];
  selected_rules: unknown[];
  selected_transformations: unknown[];
  transformation_metrics: Array<{ transform_id: string; operator: string; changed_rows: number }>;
  dry_run: {
    counts: { input: number; accepted: number; rejected: number; duplicates: number; published: number };
    quality_summary: {
      columns_checked: number;
      type_mismatch_count: number;
      null_value_count: number;
      columns_with_nulls: Array<{ field: string; null_count: number }>;
      mixed_type_columns: string[];
      type_checks: Array<{
        field: string;
        source_field: string;
        inferred_type: string;
        confidence: number;
        checked_rows: number;
        null_count: number;
        mismatch_count: number;
      }>;
    };
    preview: Array<{ source_row_number: number; payload: Record<string, unknown> }>;
    rejection_reasons: string[];
  };
}

export function getSourceProfile(sourceId: string): Promise<SourceProfileResponse> {
  return apiRequest<SourceProfileResponse>(`/engine/sources/${encodeURIComponent(sourceId)}/profile`);
}

export function getEngineRegistry(): Promise<EngineRegistry> {
  return apiRequest<EngineRegistry>("/engine/registry");
}

export function listSchemaProfiles(sourceId: string): Promise<ApiPage<SchemaProfileRecord>> {
  return apiRequest<ApiPage<SchemaProfileRecord>>(`/engine/schema-profiles?source_file_id=${encodeURIComponent(sourceId)}`);
}

export function listEngineRules(schemaFingerprint: string): Promise<ApiPage<EngineRuleRecord>> {
  return apiRequest<ApiPage<EngineRuleRecord>>(`/engine/rules?schema_fingerprint=${encodeURIComponent(schemaFingerprint)}`);
}

export function getEngineRuleHistory(ruleId: string): Promise<ApiPage<EngineRuleRecord>> {
  return apiRequest<ApiPage<EngineRuleRecord>>(`/engine/rules/${encodeURIComponent(ruleId)}/history`);
}

export function listEngineTransformations(schemaFingerprint: string): Promise<ApiPage<EngineTransformationRecord>> {
  return apiRequest<ApiPage<EngineTransformationRecord>>(`/engine/transformations?schema_fingerprint=${encodeURIComponent(schemaFingerprint)}`);
}

export function compareSourceSchemas(leftId: string, rightId: string): Promise<{
  added_columns: string[];
  missing_columns: string[];
  type_conflicts: Array<{ column: string; left_type: string | null; right_type: string | null }>;
}> {
  return apiRequest(`/engine/schema-drift?left_source_file_id=${encodeURIComponent(leftId)}&right_source_file_id=${encodeURIComponent(rightId)}`);
}

export function requestSchemaSuggestions(sourceId: string): Promise<{
  schema_profile_id: string;
  version: number;
  status: string;
  analysis: SchemaAnalysis;
}> {
  return apiRequest(`/engine/sources/${encodeURIComponent(sourceId)}/suggestions`, { method: "POST" });
}

export function approveSchemaMappings(profileId: string, mappings: Array<{
  source_column: string;
  semantic_field: string;
  action: "approve" | "edit" | "reject";
  confidence: number;
  explanation: string;
}>): Promise<{ profile_id: string; status: string; version: number }> {
  return apiRequest(`/engine/schema-profiles/${encodeURIComponent(profileId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mappings }),
  });
}

export function saveRule(schemaFingerprint: string, definition: Record<string, unknown>, status: "draft" | "approved" | "rejected") {
  return apiRequest<{ rule_id: string; status: string; version: number }>("/engine/rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ schema_fingerprint: schemaFingerprint, definition, status }),
  });
}

export function saveTransformation(schemaFingerprint: string, definition: Record<string, unknown>, status: "draft" | "approved") {
  return apiRequest<{ transform_id: string; status: string; version: number }>("/engine/transformations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ schema_fingerprint: schemaFingerprint, definition, status }),
  });
}

export function testRegex(pattern: string, values: string[]): Promise<{
  sample_count: number;
  matching_count: number;
  non_matching_count: number;
  results: Array<{ value: string; matches: boolean }>;
}> {
  return apiRequest("/engine/rules/test-regex", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern, values }),
  });
}

export function createDryRun(sourceFileId: string, includeAiSuggestions = false): Promise<DryRunPlan> {
  return apiRequest<DryRunPlan>("/engine/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_file_id: sourceFileId, include_ai_suggestions: includeAiSuggestions, dry_run: true }),
  });
}

export function getAIStatus(): Promise<AIStatus> {
  return apiRequest<AIStatus>("/ai/status");
}

export function getAIUsage(): Promise<ApiPage<AIUsageRecord>> {
  return apiRequest<ApiPage<AIUsageRecord>>("/ai/usage?page=1&page_size=10");
}

export function resetAIBudget(): Promise<AIStatus["budget"]> {
  return apiRequest<AIStatus["budget"]>("/ai/budget/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmation: "RESET_AI_BUDGET" }),
  });
}
