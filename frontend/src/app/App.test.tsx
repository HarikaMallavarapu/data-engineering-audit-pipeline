import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { ThemeProvider } from "./ThemeProvider";
import type { PipelineRun } from "../services/runService";
import type { SourceFile } from "../services/sourceService";

const mocks = vi.hoisted(() => ({
  checkHealth: vi.fn(),
  listPipelines: vi.fn(),
  listRuns: vi.fn(),
  getRun: vi.fn(),
  getQuarantine: vi.fn(),
  getDuplicates: vi.fn(),
  getAudit: vi.fn(),
  getReconciliation: vi.fn(),
  retryRun: vi.fn(),
  listSources: vi.fn(),
  uploadSource: vi.fn(),
  createRun: vi.fn(),
  getValidationCatalog: vi.fn(),
  getValidationAnalytics: vi.fn(),
  getValidationHistory: vi.fn(),
  getValidationRunResults: vi.fn(),
  getRunQualityScore: vi.fn(),
  listQualityBaselines: vi.fn(),
  createQualityBaseline: vi.fn(),
  compareQualityBaseline: vi.fn(),
  compareQualityRuns: vi.fn(),
  getEngineRegistry: vi.fn(),
  listEngineRules: vi.fn(),
  getEngineRuleHistory: vi.fn(),
  saveRule: vi.fn(),
  testRegex: vi.fn(),
}));

vi.mock("../services/api", () => ({
  checkHealth: mocks.checkHealth,
  ApiClientError: class ApiClientError extends Error {
    constructor(message: string, public code: string) { super(message); }
  },
}));
vi.mock("../services/pipelineService", () => ({ listPipelines: mocks.listPipelines }));
vi.mock("../services/runService", () => ({
  listRuns: mocks.listRuns,
  getRun: mocks.getRun,
  getQuarantine: mocks.getQuarantine,
  getDuplicates: mocks.getDuplicates,
  getAudit: mocks.getAudit,
  getReconciliation: mocks.getReconciliation,
  retryRun: mocks.retryRun,
  createRun: mocks.createRun,
  getValidationCatalog: mocks.getValidationCatalog,
  getValidationAnalytics: mocks.getValidationAnalytics,
  getValidationHistory: mocks.getValidationHistory,
  getValidationRunResults: mocks.getValidationRunResults,
  getRunQualityScore: mocks.getRunQualityScore,
  listQualityBaselines: mocks.listQualityBaselines,
  createQualityBaseline: mocks.createQualityBaseline,
  compareQualityBaseline: mocks.compareQualityBaseline,
  compareQualityRuns: mocks.compareQualityRuns,
}));
vi.mock("../services/sourceService", () => ({ listSources: mocks.listSources, uploadSource: mocks.uploadSource }));
vi.mock("../services/engineService", () => ({
  getEngineRegistry: mocks.getEngineRegistry,
  listEngineRules: mocks.listEngineRules,
  getEngineRuleHistory: mocks.getEngineRuleHistory,
  saveRule: mocks.saveRule,
  testRegex: mocks.testRegex,
}));

const run: PipelineRun = {
  run_id: "run_0123456789abcdef0123456789abcdef",
  pipeline_id: "financial-transactions",
  source_file_id: "src_0123456789abcdef0123456789abcdef",
  status: "PARTIAL",
  counts: { input: 4, accepted: 2, rejected: 1, duplicates: 1, published: 2 },
  profile: { row_count: 4 },
  error: null,
  created_at: "2026-10-31T12:00:00Z",
  started_at: "2026-10-31T12:00:00Z",
  completed_at: "2026-10-31T12:00:01Z",
  stages: [{
    stage_name: "validation",
    attempt_id: "run_0123456789abcdef0123456789abcdef_attempt_1",
    status: "SUCCESS",
    input_count: 4,
    output_count: 2,
    reject_count: 1,
    duration_ms: 2,
    details: {},
    started_at: "2026-10-31T12:00:00Z",
    completed_at: "2026-10-31T12:00:00Z",
  }],
};

const source: SourceFile = {
  source_file_id: run.source_file_id,
  original_filename: "transactions.csv",
  checksum: "a".repeat(64),
  size_bytes: 128,
  columns: ["transaction_id", "amount", "currency"],
  uploaded_at: "2026-10-31T12:00:00Z",
};

function dashboardRun(id: string, status: PipelineRun["status"], input: number, accepted: number, rejected: number, duplicates: number, durationMs: number): PipelineRun {
  const createdAt = new Date().toISOString();
  const startedAt = new Date(Date.now() - durationMs).toISOString();
  return {
    ...run,
    run_id: `run_${id.padEnd(32, "0").slice(0, 32)}`,
    status,
    counts: { input, accepted, rejected, duplicates, published: accepted },
    created_at: createdAt,
    started_at: startedAt,
    completed_at: status === "RUNNING" || status === "PENDING" ? null : createdAt,
  };
}

function renderApp(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("DataTrace API-backed frontend", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mocks.checkHealth.mockResolvedValue({ status: "ok" });
    mocks.listPipelines.mockResolvedValue([{ pipeline_id: "financial-transactions", name: "Financial Transactions", version: 1 }]);
    mocks.listRuns.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    mocks.listSources.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    mocks.getEngineRegistry.mockResolvedValue({ rule_types: ["required", "regex", "numeric_range"], transformation_operators: [], execution_safety: "Allow-listed operators only." });
    mocks.listEngineRules.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    mocks.getEngineRuleHistory.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    mocks.uploadSource.mockResolvedValue(source);
    mocks.createRun.mockResolvedValue(run);
    mocks.getValidationCatalog.mockResolvedValue({ source_status: "SOURCE_MISSING", message: "Source catalogs are missing.", counts: {}, items: [], total: 0, page: 1, page_size: 25 });
    mocks.getValidationAnalytics.mockResolvedValue({ days: 30, from_date: "2026-10-02T00:00:00Z", through_date: "2026-11-01T00:00:00Z", pipeline_id: null, total_results: 0, status_counts: {}, critical_failures: 0, requires_configuration: 0, average_execution_time_ms: null, failures_by_category: [], most_failing_checks: [], daily_trend: [], quality_trend: [], quality_trend_insufficient_attempts: 0, scope: "Persisted per-check results." });
    mocks.getValidationHistory.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    mocks.getRunQualityScore.mockResolvedValue({ run_id: run.run_id, attempt_id: "attempt_1", score: null, score_status: "INSUFFICIENT_DATA", coverage_percent: null, applicable_checks: 0, executed_checks: 0, passed_checks: 0, failed_checks: 0, warning_checks: 0, skipped_checks: 0, not_applicable_checks: 0, requires_configuration_checks: 0, blocked_checks: 0, dataset_level_failures: 0, catalog_total: 0, catalog_eligible_checks: 0, catalog_coverage_percent: null, insufficiency_reasons: ["No validation results were marked applicable for this attempt."], score_scope: "Persisted applicable runtime checks for the selected attempt.", methodology: {} });
    mocks.listQualityBaselines.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    mocks.createQualityBaseline.mockResolvedValue({ baseline_id: "baseline_example", dataset_identity: "transactions", pipeline_id: run.pipeline_id, source_file_id: run.source_file_id, run_id: run.run_id, attempt_id: "attempt_1", schema_version: null, baseline_version: 1, sample_size: 4, reference_period_start: run.created_at, reference_period_end: run.created_at, statistical_configuration: {}, created_at: run.created_at });
    mocks.compareQualityBaseline.mockResolvedValue({
      baseline_id: "baseline_example", baseline_version: 1, dataset_identity: "transactions", target_run_id: run.run_id, target_attempt_id: "attempt_1", target_source_file_id: run.source_file_id,
      row_count_change: { baseline: 4, current: 4, delta: 0, delta_percent: 0 }, null_rate_changes: [], duplicate_rate_change: { baseline_rate: 0, current_rate: 0, delta_percentage_points: 0 },
      schema_drift: { added_columns: [], missing_columns: [], type_changes: [], changed: false },
      numeric_distribution_drift: [{ column: "amount", status: "INSUFFICIENT_SAMPLE", baseline_sample_size: 4, current_sample_size: 4, psi: null, binned_ks_distance: null }],
      value_shape_distribution_drift: [], freshness_changes: [], outlier_changes: [], validation_failure_changes: [], anomaly_signals: [], confirmed_invalid_records: false,
      limitations: ["Drift signals do not prove individual records invalid."],
    });
    mocks.compareQualityRuns.mockResolvedValue({
      reference_run_id: run.run_id,
      reference_attempt_id: `${run.run_id}_attempt_1`,
      reference_pipeline_id: run.pipeline_id,
      reference_source_file_id: run.source_file_id,
      reference_filename: "reference.csv",
      comparison_run_id: `run_${"b".repeat(32)}`,
      comparison_attempt_id: `run_${"b".repeat(32)}_attempt_1`,
      comparison_source_file_id: `src_${"b".repeat(32)}`,
      comparison_filename: "comparison.csv",
      row_count_change: { baseline: 4, current: 6, delta: 2, delta_percent: 50 },
      null_rate_changes: [],
      duplicate_rate_change: { baseline_rate: 0, current_rate: 0.1, delta_percentage_points: 10 },
      schema_drift: { added_columns: [], missing_columns: [], type_changes: [], changed: false },
      numeric_distribution_drift: [],
      value_shape_distribution_drift: [],
      freshness_changes: [],
      outlier_changes: [],
      validation_failure_changes: [{ validation_id: "TABULAR:ROW_UNIQUENESS", baseline_status: "PASS", current_status: "FAIL", baseline_failure_rate: 0, current_failure_rate: 0.1, delta_percentage_points: 10, assessment: "COMPARED" }],
      anomaly_signals: [],
      confirmed_invalid_records: false,
      limitations: ["Drift signals do not prove individual records invalid."],
    });
    mocks.getValidationRunResults.mockResolvedValue({ run_id: run.run_id, attempt_id: "attempt_1", summary: { attempt_id: "attempt_1", total_records: 1, executed: 1, passed: 0, failed: 1, warnings: 0, errors: 0, skipped: 0, not_applicable: 0, requires_configuration: 0, blocked: 0, applicable: 1, checked_rows: 2, failed_rows: 1, execution_duration_ms: 1 }, items: [{ validation_execution_id: 1, run_id: run.run_id, attempt_id: "attempt_1", validation_id: "RULE:amount_floor", name: "Approved rule amount_floor", category: "Configured rule", status: "FAIL", severity: "ERROR", applicability: "APPLICABLE", applicability_reason: "Rule target exists.", execution_stage: "PRE_TRANSFORMATION", checked_rows: 2, passed_rows: 1, failed_rows: 1, failure_percentage: 50, affected_columns: ["amount"], failure_examples: [{ source_row_number: 3 }], message: "One row failed.", recommendation: "Review row 3.", execution_time_ms: 1, rule_version: "1", configuration_snapshot: { minimum: 0 }, created_at: "2026-11-01T00:00:00Z" }], total: 1, page: 1, page_size: 25 });
    mocks.getValidationCatalog.mockResolvedValue({ source_status: "SOURCE_MISSING", message: "Source catalogs are missing.", counts: {}, items: [], total: 0, page: 1, page_size: 25 });
    mocks.getValidationRunResults.mockResolvedValue({ run_id: run.run_id, attempt_id: "attempt_1", summary: { attempt_id: "attempt_1", total_records: 1, executed: 1, passed: 0, failed: 1, warnings: 0, errors: 0, skipped: 0, not_applicable: 0, requires_configuration: 0, blocked: 0, applicable: 1, checked_rows: 2, failed_rows: 1, execution_duration_ms: 1 }, items: [{ validation_execution_id: 1, run_id: run.run_id, attempt_id: "attempt_1", validation_id: "RULE:amount_floor", name: "Approved rule amount_floor", category: "Configured rule", status: "FAIL", severity: "ERROR", applicability: "APPLICABLE", applicability_reason: "Rule target exists.", execution_stage: "PRE_TRANSFORMATION", checked_rows: 2, passed_rows: 1, failed_rows: 1, failure_percentage: 50, affected_columns: ["amount"], failure_examples: [{ source_row_number: 3 }], message: "One row failed.", recommendation: "Review row 3.", execution_time_ms: 1, rule_version: "1", configuration_snapshot: { minimum: 0 }, created_at: "2026-11-01T00:00:00Z" }], total: 1, page: 1, page_size: 25 });
    mocks.getRun.mockResolvedValue(run);
    mocks.getQuarantine.mockResolvedValue({
      items: [{ attempt_id: `${run.run_id}_attempt_1`, source_file_id: run.source_file_id, source_row_number: 4, original_payload: { transaction_id: "TX-002" }, reason_code: "amount_not_positive", rejection_reasons: ["amount_not_positive"] }],
      total: 1,
      page: 1,
      page_size: 25,
    });
    mocks.getDuplicates.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    mocks.getAudit.mockResolvedValue({
      items: [{ audit_event_id: 1, run_id: run.run_id, event_type: "run.completed", event_data: { status: "PARTIAL" }, created_at: "2026-10-31T12:00:01Z" }],
      total: 1,
      page: 1,
      page_size: 25,
    });
    mocks.getReconciliation.mockResolvedValue({
      run_id: run.run_id,
      counts: run.counts,
      accepted_amounts_by_currency: { USD: "10.25" },
      published_amounts_by_currency: { USD: "10.25" },
      balanced: true,
      checks: { input_equals_dispositions: true, accepted_equals_published: true },
    });
  });

  it("registers a CSV, starts a backend run and displays persisted evidence", async () => {
    const user = userEvent.setup();
    mocks.listPipelines.mockResolvedValueOnce([
      { pipeline_id: "general-tabular", name: "General Tabular Data", version: 1 },
      { pipeline_id: "financial-transactions", name: "Financial Transactions", version: 1 },
    ]);
    renderApp("/sources");

    const csv = new File(["transaction_id,amount\nTX-002,-1\n"], "transactions.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText(/Drop CSV or JSON files here/i), csv);
    await user.click(screen.getByRole("button", { name: "Register source" }));
    expect(await screen.findByText("Source registered")).toBeInTheDocument();
    expect(mocks.uploadSource.mock.calls[0]?.[0]).toBe(csv);

    await user.click(screen.getByRole("button", { name: "Start pipeline run" }));
    await screen.findByRole("heading", { name: "Run details" });
    expect(mocks.createRun).toHaveBeenCalledWith(source.source_file_id, "general-tabular");
    expect(screen.getByText(run.run_id)).toBeInTheDocument();
    expect(screen.getByText("partial")).toBeInTheDocument();
    expect(await screen.findByText("TX-002")).toBeInTheDocument();
    expect(await screen.findByText("Balanced")).toBeInTheDocument();
    expect(await screen.findByText("run · completed")).toBeInTheDocument();
    await waitFor(() => expect(mocks.getReconciliation).toHaveBeenCalledWith(run.run_id));
  });

  it("makes missing catalog source explicit instead of displaying invented checks", async () => {
    renderApp("/validation/catalog");
    expect(await screen.findByRole("heading", { name: "Validation catalog" })).toBeInTheDocument();
    expect(await screen.findByText("Source catalogs are missing")).toBeInTheDocument();
    expect(screen.queryByText("VAL-001")).not.toBeInTheDocument();
  });

  it("filters the imported validation catalog and opens definition details", async () => {
    const user = userEvent.setup();
    mocks.getValidationCatalog.mockResolvedValueOnce({
      source_status: "PARTIAL",
      message: "1 of 200 definitions imported.",
      counts: { FULLY_IMPLEMENTED: 1 },
      filter_options: { categories: ["Finance"], severities: ["ERROR"], applicabilities: ["TRANSACTION"], supported_file_types: ["csv"] },
      items: [{
        validation_id: "VAL-001", catalog_number: 1, name: "Invoice amount check", description: "Checks invoice amounts.",
        category: "Finance", severity: "ERROR", applicability_requirements: ["amount column"], required_columns: ["amount"],
        required_metadata: [], configuration_requirements: [], implementation_status: "FULLY_IMPLEMENTED", implementation_version: "1.0",
        test_status: "TESTED", limitations: [], enabled: true, supported_file_types: ["csv"], applicability_support: "TRANSACTION",
        definition_source: "catalog fixture", last_executed_at: null,
      }],
      total: 1, page: 1, page_size: 25,
    });
    renderApp("/validation/catalog");
    await user.click(await screen.findByRole("button", { name: "Invoice amount check" }));
    expect(await screen.findByRole("heading", { name: "Invoice amount check" })).toBeInTheDocument();
    expect(screen.getByText("Required columns")).toBeInTheDocument();
    expect(screen.getByText("amount", { exact: true })).toBeInTheDocument();
  });

  it("shows actual persisted validation history with a run link", async () => {
    mocks.getValidationHistory.mockResolvedValueOnce({
      items: [{
        validation_execution_id: 9, run_id: run.run_id, attempt_id: `${run.run_id}_attempt_1`, validation_id: "RULE:amount_floor",
        name: "Approved rule amount_floor", category: "Configured rule", status: "FAIL", severity: "ERROR", applicability: "APPLICABLE",
        applicability_reason: "Rule target exists.", execution_stage: "PRE_TRANSFORMATION", checked_rows: 4, passed_rows: 3,
        failed_rows: 1, failure_percentage: 25, affected_columns: ["amount"], failure_examples: [{ source_row_number: 4 }],
        message: "One row failed.", recommendation: "Review source row 4.", execution_time_ms: 1, rule_version: "1",
        configuration_snapshot: { minimum: 0 }, created_at: "2026-11-01T00:00:00Z", pipeline_id: "general-tabular",
        source_file_id: source.source_file_id, original_filename: "transactions.csv", attempt_number: 1,
      }],
      total: 1, page: 1, page_size: 25,
    });
    renderApp("/validation/history?validation_id=RULE%3Aamount_floor");
    expect(await screen.findByText("transactions.csv")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /attempt 1/ })).toHaveAttribute("href", `/validation/results?run_id=${run.run_id}&attempt_id=${run.run_id}_attempt_1`);
    expect(mocks.getValidationHistory).toHaveBeenCalledWith(expect.objectContaining({ validationId: "RULE:amount_floor" }));
  });

  it("shows a scoped quality score from persisted run checks", async () => {
    mocks.listRuns.mockResolvedValue({ items: [run], total: 1, page: 1, page_size: 25 });
    mocks.getRunQualityScore.mockResolvedValueOnce({
      run_id: run.run_id, attempt_id: "attempt_1", score: 88.5, score_status: "AVAILABLE", coverage_percent: 100,
      applicable_checks: 4, executed_checks: 4, passed_checks: 3, failed_checks: 1, warning_checks: 0, skipped_checks: 0,
      not_applicable_checks: 2, requires_configuration_checks: 0, blocked_checks: 0, dataset_level_failures: 0,
      catalog_total: 0, catalog_eligible_checks: 0, catalog_coverage_percent: null, insufficiency_reasons: [],
      score_scope: "Persisted applicable runtime checks for the selected attempt.", methodology: { formula: "weighted" },
    });
    renderApp("/quality");
    expect(await screen.findByText("88.50 / 100")).toBeInTheDocument();
    expect(screen.getByText(/Catalog-wide coverage is unavailable/)).toBeInTheDocument();
    expect(mocks.getRunQualityScore).toHaveBeenCalledWith(run.run_id);
  });

  it("shows baseline comparison sample limits and signal caveat", async () => {
    mocks.listRuns.mockResolvedValue({ items: [run], total: 1, page: 1, page_size: 100 });
    mocks.listQualityBaselines.mockResolvedValue({
      items: [{ baseline_id: "baseline_example", dataset_identity: "transactions", pipeline_id: run.pipeline_id, source_file_id: run.source_file_id, run_id: run.run_id, attempt_id: "attempt_1", schema_version: null, baseline_version: 1, sample_size: 4, reference_period_start: run.created_at, reference_period_end: run.created_at, statistical_configuration: {}, created_at: run.created_at }],
      total: 1, page: 1, page_size: 100,
    });
    renderApp("/validation/baselines");
    expect(await screen.findByRole("heading", { name: "Baselines and drift" })).toBeInTheDocument();
    expect(await screen.findByText("INSUFFICIENT SAMPLE")).toBeInTheDocument();
    expect(screen.getByText(/does not prove individual records are invalid/i)).toBeInTheDocument();
    expect(mocks.compareQualityBaseline).toHaveBeenCalledWith("baseline_example", run.run_id);
  });

  it("shows validation trends from persisted executions", async () => {
    mocks.getValidationAnalytics.mockResolvedValueOnce({
      days: 30, from_date: "2026-10-02T00:00:00Z", through_date: "2026-11-01T00:00:00Z", pipeline_id: null,
      total_results: 3, status_counts: { PASS: 1, FAIL: 1, REQUIRES_CONFIGURATION: 1 }, critical_failures: 1,
      requires_configuration: 1, average_execution_time_ms: 1.5,
      failures_by_category: [{ category: "Financial", failures: 1 }],
      most_failing_checks: [{ validation_id: "FINANCE:POSITIVE_AMOUNT", name: "Positive finite amount", category: "Financial", failures: 1 }],
      daily_trend: [{ date: "2026-10-31", executions: 3, failures: 1, warnings: 0 }],
      quality_trend: [], quality_trend_insufficient_attempts: 1, scope: "Persisted results from the selected window.",
    });
    renderApp("/validation/overview");
    expect(await screen.findByRole("heading", { name: "Validation trends" })).toBeInTheDocument();
    expect(await screen.findByText("FINANCE:POSITIVE_AMOUNT")).toBeInTheDocument();
    expect(screen.getByText("2026-10-31")).toBeInTheDocument();
    expect(screen.getByText("critical failures", { exact: false })).toBeInTheDocument();
  });

  it("compares two completed runs from the same pipeline in validation history", async () => {
    const secondRun = dashboardRun("b", "SUCCESS", 6, 6, 0, 0, 4);
    mocks.listRuns.mockResolvedValue({ items: [run, secondRun], total: 2, page: 1, page_size: 100 });
    renderApp("/validation/history");
    expect(await screen.findByRole("heading", { name: /Compare two runs/ })).toBeInTheDocument();
    expect(await screen.findByText("reference.csv")).toBeInTheDocument();
    expect(screen.getByText("TABULAR:ROW_UNIQUENESS")).toBeInTheDocument();
    expect(screen.getByText(/50\.00%/)).toBeInTheDocument();
    expect(mocks.compareQualityRuns).toHaveBeenCalledWith(run.run_id, secondRun.run_id);
  });

  it("shows actual run-level validation rows and their saved configuration", async () => {
    mocks.listRuns.mockResolvedValue({ items: [run], total: 1, page: 1, page_size: 25 });
    renderApp("/validation/results");
    expect(await screen.findByText("Approved rule amount_floor")).toBeInTheDocument();
    expect(screen.getByText("RULE:amount_floor")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Inspect" }));
    expect(await screen.findByText(/Configuration snapshot used for this execution/)).toBeInTheDocument();
    expect(screen.getByText(/source row 3/)).toBeInTheDocument();
  });

  it("shows the Validation Center and explicitly labels synthetic fallback rows", async () => {
    renderApp("/validation");
    expect(await screen.findByRole("heading", { name: "Validation Center" })).toBeInTheDocument();
    expect(await screen.findByText("Synthetic preview data")).toBeInTheDocument();
    expect(screen.getByText(/not imported definitions, do not represent implementation coverage/i)).toBeInTheDocument();
    expect(screen.getByText("Synthetic preview check VAL-001")).toBeInTheDocument();
    expect(screen.getByText("200", { exact: true })).toBeInTheDocument();
  });

  it("opens the challenge blueprint and reads out its source-missing blocker", async () => {
    const user = userEvent.setup();
    renderApp("/validation");
    await user.click(await screen.findByRole("tab", { name: "Pipeline & Challenge Blueprint" }));
    expect(await screen.findByRole("heading", { name: "Pipeline and challenge blueprint" })).toBeInTheDocument();
    expect(screen.getByText("The two original validation catalogs have not been supplied.")).toBeInTheDocument();
  });

  it("shows schema requirements before opening Rule Studio editors", async () => {
    renderApp("/validation/rules");
    expect(await screen.findByText("Upload a dataset before configuring rules")).toBeInTheDocument();
  });

  it("makes missing catalog source explicit instead of displaying invented checks", async () => {
    renderApp("/validation/catalog");
    expect(await screen.findByRole("heading", { name: "Validation catalog" })).toBeInTheDocument();
    expect(await screen.findByText("Source catalogs are missing")).toBeInTheDocument();
    expect(screen.queryByText("VAL-001")).not.toBeInTheDocument();
  });

  it("shows actual run-level validation rows and their saved configuration", async () => {
    mocks.listRuns.mockResolvedValue({ items: [run], total: 1, page: 1, page_size: 25 });
    renderApp("/validation/results");
    expect(await screen.findByText("Approved rule amount_floor")).toBeInTheDocument();
    expect(screen.getByText("RULE:amount_floor")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Inspect" }));
    expect(await screen.findByText(/Configuration snapshot used for this execution/)).toBeInTheDocument();
    expect(screen.getByText(/source row 3/)).toBeInTheDocument();
  });

  it("clears a prior upload result when another CSV is selected", async () => {
    const user = userEvent.setup();
    renderApp("/sources");

    const fileInputLabel = screen.getByLabelText(/Drop CSV or JSON files here/i);
    await user.upload(fileInputLabel, new File(["transaction_id\nTX-1"], "first.csv", { type: "text/csv" }));
    await user.click(screen.getByRole("button", { name: "Register source" }));
    expect(await screen.findByText("Source registered")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start pipeline run" })).toBeInTheDocument();

    await user.upload(fileInputLabel, new File(["transaction_id\nTX-2"], "second.csv", { type: "text/csv" }));
    await waitFor(() => expect(screen.queryByText("Source registered")).not.toBeInTheDocument());
    expect(screen.getAllByText("second.csv")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Start pipeline run" })).not.toBeInTheDocument();
  });

  it("explains when no pipeline is available for a registered source", async () => {
    const user = userEvent.setup();
    mocks.listPipelines.mockResolvedValueOnce([]);
    mocks.listSources.mockResolvedValueOnce({ items: [source], total: 1, page: 1, page_size: 25 });
    renderApp("/sources");

    expect(await screen.findByText("No runnable pipeline is registered")).toBeInTheDocument();
    expect(screen.getByText(/Pipeline setup is managed by the backend/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View pipeline registry" })).toHaveAttribute("href", "/pipelines");
    expect(screen.getByRole("button", { name: "Run pipeline for transactions.csv" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Inspect detected columns for transactions.csv" }));
    expect(screen.getByRole("heading", { name: "transactions.csv" })).toBeInTheDocument();
  });

  it("filters the current server page and keeps pagination parameters explicit", async () => {
    const user = userEvent.setup();
    mocks.listRuns.mockResolvedValueOnce({ items: [run], total: 1, page: 1, page_size: 25 });
    renderApp("/runs");

    expect(await screen.findByText(run.pipeline_id)).toBeInTheDocument();
    expect(mocks.listRuns).toHaveBeenCalledWith(1, 25);
    await user.selectOptions(screen.getByRole("combobox", { name: "Status" }), "SUCCESS");
    expect(await screen.findByText("No runs match these filters")).toBeInTheDocument();
  });

  it("filters run history by creation date within the returned API page", async () => {
    const user = userEvent.setup();
    mocks.listRuns.mockResolvedValueOnce({ items: [dashboardRun("recent", "SUCCESS", 2, 2, 0, 0, 1000)], total: 1, page: 1, page_size: 25 });
    renderApp("/runs");

    expect(await screen.findByText(run.pipeline_id)).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter runs by date" }), "7");
    expect(screen.getByRole("link", { name: /run_recent/ })).toBeInTheDocument();
    expect(screen.getByText("Filters apply to this API page")).toBeInTheDocument();
  });

  it("rejects an unsupported file locally without calling the backend", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderApp("/sources");
    await user.upload(screen.getByLabelText(/Drop CSV or JSON files here/i), new File(["not parquet"], "transactions.parquet", { type: "application/octet-stream" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a UTF-8 CSV, JSON, or JSON Lines file");
    expect(mocks.uploadSource).not.toHaveBeenCalled();
  });

  it("shows a backend request error rather than leaving the source registry loading", async () => {
    mocks.listSources.mockRejectedValueOnce(new Error("source service unavailable"));
    renderApp("/sources");

    expect(await screen.findByText("source service unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("keeps stable loading states visible while dashboard APIs are pending", async () => {
    mocks.listPipelines.mockImplementationOnce(() => new Promise(() => {}));
    mocks.listRuns.mockImplementationOnce(() => new Promise(() => {}));
    mocks.listSources.mockImplementationOnce(() => new Promise(() => {}));
    renderApp("/");

    expect(await screen.findByText("Loading run history")).toBeInTheDocument();
    expect(screen.getByText("Checking latest run")).toBeInTheDocument();
    expect(screen.getByText("Loading sources")).toBeInTheDocument();
  });

  it("inspects registered source metadata and labels run actions with the filename", async () => {
    const user = userEvent.setup();
    mocks.listSources.mockResolvedValueOnce({ items: [source], total: 1, page: 1, page_size: 25 });
    renderApp("/sources");

    expect(await screen.findByText("transactions.csv")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Inspect detected columns for transactions.csv" }));
    expect(screen.getByRole("heading", { name: "transactions.csv" })).toBeInTheDocument();
    expect(screen.getByText("transaction_id")).toBeInTheDocument();
    expect(screen.getByText(/The general tabular pipeline accepts user-defined columns/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run pipeline for transactions.csv" })).toBeEnabled();
  });

  it("derives dashboard metrics and distribution from persisted run responses", async () => {
    const successful = dashboardRun("a", "SUCCESS", 5, 4, 0, 1, 2000);
    const failed = dashboardRun("b", "FAILED", 4, 1, 2, 1, 4000);
    const running = dashboardRun("c", "RUNNING", 3, 2, 0, 1, 0);
    mocks.listRuns.mockResolvedValueOnce({ items: [running, failed, successful], total: 3, page: 1, page_size: 100 });
    renderApp("/");

    expect(await screen.findByRole("group", { name: "Pipelines: 1" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Successful runs: 1" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Failed runs: 1" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Active runs: 1" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Records processed: 12" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Rejected records: 2" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Avg. run duration: 3.00 s" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Quality score: —" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Run counts by status" })).toHaveTextContent("Succeeded1Partial0Failed1Running1Pending0Cancelled0");
    expect(screen.getByRole("button", { name: "24h" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "30d" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.setup().click(screen.getByText("View chart data"));
    expect(screen.getByRole("table", { name: "Exact values plotted in the run volume chart" })).toBeInTheDocument();
  });

  it("counts active runs across the latest API page regardless of the dashboard time filter", async () => {
    const oldActiveRun = { ...dashboardRun("old-active", "RUNNING", 2, 1, 0, 1, 0), created_at: "2026-09-01T12:00:00Z" };
    mocks.listRuns.mockResolvedValueOnce({ items: [oldActiveRun], total: 105, page: 1, page_size: 100 });
    renderApp("/");

    expect(await screen.findByRole("group", { name: "Active runs: 1" })).toBeInTheDocument();
    expect(screen.getByText(/Latest 1 of 105 runs · pending or running/)).toBeInTheDocument();
    expect(screen.getByText("No runs in this time range")).toBeInTheDocument();
  });

  it("provides skip navigation and a grouped mobile navigation toggle", async () => {
    const user = userEvent.setup();
    renderApp("/");

    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("link", { name: "Failure outcomes" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open navigation menu" }));
    expect(screen.getByRole("button", { name: "Close navigation menu" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("navigation", { name: "Primary navigation" })).toHaveLength(2);
    const mobileSourcesLink = screen.getAllByRole("link", { name: "Sources" }).at(-1);
    expect(mobileSourcesLink).toBeDefined();
    await user.click(mobileSourcesLink!);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Source registry" })));

    await user.click(screen.getByRole("button", { name: "Open navigation menu" }));
    const mobileFirstLink = screen.getAllByRole("link", { name: "Command center" }).at(-1);
    mobileFirstLink?.focus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open navigation menu" })));
  });

  it("persists the selected color theme", async () => {
    const user = userEvent.setup();
    renderApp("/sources");
    await user.click(await screen.findByRole("button", { name: "Switch to dark theme" }));

    await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "dark"));
    expect(JSON.parse(localStorage.getItem("datatrace-theme-v1") ?? "{}").theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toHaveAttribute("aria-pressed", "true");
  });

  it("labels lineage as unavailable until the backend exposes a lineage contract", async () => {
    renderApp("/lineage");

    expect(await screen.findByText("Lineage API is not available yet")).toBeInTheDocument();
    expect(screen.getByText(/No lineage graph is inferred in the browser/)).toBeInTheDocument();
  });
});
