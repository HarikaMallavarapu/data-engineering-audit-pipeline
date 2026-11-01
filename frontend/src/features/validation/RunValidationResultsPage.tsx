import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { MetricCard } from "../../components/common/MetricCard";
import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { StatusBadge } from "../../components/common/StatusBadge";
import { downloadValidationRunResults, getValidationRunResults, listRuns } from "../../services/runService";
import type { ValidationExecutionRecord } from "../../services/runService";
import { formatNumber, shortId } from "../../utils/format";

const PAGE_SIZE = 25;

export function RunValidationResultsPage() {
  const [searchParams] = useSearchParams();
  const [selectedRunId, setSelectedRunId] = useState(searchParams.get("run_id") ?? "");
  const [selectedAttemptId, setSelectedAttemptId] = useState(searchParams.get("attempt_id") ?? "");
  const [selectedResult, setSelectedResult] = useState<ValidationExecutionRecord | null>(null);
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [executionStage, setExecutionStage] = useState("");
  const [validationId, setValidationId] = useState("");
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState("");
  const [page, setPage] = useState(1);
  const runs = useQuery({ queryKey: ["runs", "validation-results", 100], queryFn: () => listRuns(1, 100) });
  const runId = selectedRunId || runs.data?.items[0]?.run_id || "";
  const results = useQuery({
    queryKey: ["validation-run-results", runId, selectedAttemptId, page, status, severity, category, executionStage, validationId],
    queryFn: () => getValidationRunResults(runId, {
      attemptId: selectedAttemptId || undefined,
      page,
      pageSize: PAGE_SIZE,
      status: status || undefined,
      severity: severity || undefined,
      category: category || undefined,
      executionStage: executionStage || undefined,
      validationId: validationId.trim() || undefined,
    }),
    enabled: Boolean(runId),
  });
  const summary = results.data?.summary;

  async function exportResults(format: "json" | "csv") {
    if (!runId) return;
    setExportBusy(true);
    setExportError("");
    try {
      const blob = await downloadValidationRunResults(runId, {
        attemptId: (results.data?.attempt_id ?? selectedAttemptId) || undefined,
        status: status || undefined,
        severity: severity || undefined,
        category: category || undefined,
        executionStage: executionStage || undefined,
        validationId: validationId.trim() || undefined,
      }, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `datatrace-validation-results.${format}`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Validation results export failed.");
    } finally {
      setExportBusy(false);
    }
  }

  return <div className="page-content">
    <PageHeader eyebrow="VALIDATION CENTER" title="Run validation results" description="This page shows only persisted check executions for the selected pipeline attempt." actions={<div className="validation-results-header-actions"><button className="button button-secondary button-small" type="button" disabled={!runId || exportBusy} onClick={() => void exportResults("json")}>Export JSON</button><button className="button button-secondary button-small" type="button" disabled={!runId || exportBusy} onClick={() => void exportResults("csv")}>CSV</button><Link className="button button-secondary" to="/validation/catalog">Open validation catalog</Link></div>} />
    {exportError ? <p className="form-error" role="alert">{exportError}</p> : null}
    {runs.isPending ? <StatePanel tone="loading" title="Loading pipeline runs" message="Fetching run choices from the backend." /> : null}
    {runs.isError ? <StatePanel tone="error" title="Run history unavailable" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} /> : null}
    {runs.data?.items.length === 0 ? <StatePanel tone="empty" title="No pipeline runs yet" message="Run a pipeline to create persisted execution evidence." action={<Link className="button button-secondary" to="/sources">Register a source</Link>} /> : null}
    {runs.data && runs.data.items.length > 0 ? <>
      <section className="surface validation-run-selector" aria-label="Select pipeline run">
        <label className="select-field"><span>Pipeline run</span><select value={runId} onChange={(event) => { setSelectedRunId(event.currentTarget.value); setSelectedAttemptId(""); setSelectedResult(null); setPage(1); }}><option value="">Select a run</option>{runs.data.items.map((run) => <option key={run.run_id} value={run.run_id}>{shortId(run.run_id)} · {run.pipeline_id} · {run.status}</option>)}</select></label>
        {runId ? <Link className="text-link" to={`/runs/${encodeURIComponent(runId)}`}>Open pipeline run <span aria-hidden="true">→</span></Link> : null}
      </section>
      {results.isPending ? <StatePanel tone="loading" title="Loading saved validation results" message="Reading the selected run attempt's persisted checks." /> : null}
      {results.isError ? <StatePanel tone="error" title="Validation results unavailable" message={results.error.message} action={<button className="button button-secondary" onClick={() => void results.refetch()}>Retry</button>} /> : null}
      {results.data ? <>
        {summary ? <div className="metric-grid validation-metric-grid">
          <MetricCard label="Executed checks" value={formatNumber(summary.executed)} note={`${formatNumber(summary.applicable)} persisted as applicable`} icon={<span aria-hidden="true">✓</span>} tone="blue" />
          <MetricCard label="Passed" value={formatNumber(summary.passed)} note="Status PASS" icon={<span aria-hidden="true">✓</span>} tone="teal" />
          <MetricCard label="Failed" value={formatNumber(summary.failed)} note={`${formatNumber(summary.failed_rows)} failed row-checks`} icon={<span aria-hidden="true">!</span>} tone="amber" />
          <MetricCard label="Warnings and errors" value={formatNumber(summary.warnings + summary.errors)} note={`${formatNumber(summary.warnings)} warnings · ${formatNumber(summary.errors)} errors`} icon={<span aria-hidden="true">!</span>} tone="violet" />
        </div> : null}
        {results.data.total === 0 ? <StatePanel tone="empty" title="No check results match this selection" message={status || severity || category || executionStage || validationId ? "Clear one or more filters to inspect the other saved outcomes." : "The pipeline may have persisted stage and row evidence without per-check results. A stage marked successful does not imply that every validation passed."} action={<Link className="button button-secondary" to={`/runs/${encodeURIComponent(runId)}`}>Inspect stage evidence</Link>} /> : <section className="surface validation-results-surface" aria-labelledby="run-validation-table-heading">
          <div className="section-header"><div><p className="eyebrow">ATTEMPT · {results.data.attempt_id}</p><h2 id="run-validation-table-heading">Persisted check outcomes</h2></div><span className="data-window-label">{formatNumber(results.data.total)} matching saved results</span></div>
          <div className="validation-run-results-filters" aria-label="Filter persisted validation results">
            <label className="select-field"><span>Result status</span><select value={status} onChange={(event) => { setStatus(event.currentTarget.value); setPage(1); }}><option value="">All results</option>{["PASS", "FAIL", "WARNING", "ERROR", "SKIPPED", "NOT_APPLICABLE", "REQUIRES_CONFIGURATION", "BLOCKED"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
            <label className="select-field"><span>Severity</span><select value={severity} onChange={(event) => { setSeverity(event.currentTarget.value); setPage(1); }}><option value="">All severities</option>{["CRITICAL", "ERROR", "WARNING", "INFO"].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
            <label className="catalog-text-filter"><span>Category</span><input value={category} onChange={(event) => { setCategory(event.currentTarget.value); setPage(1); }} placeholder="Exact category" /></label>
            <label className="catalog-text-filter"><span>Execution stage</span><input value={executionStage} onChange={(event) => { setExecutionStage(event.currentTarget.value); setPage(1); }} placeholder="Exact stage" /></label>
            <label className="catalog-text-filter"><span>Validation ID</span><input value={validationId} onChange={(event) => { setValidationId(event.currentTarget.value); setPage(1); }} placeholder="Exact ID" /></label>
          </div>
          <div className="table-scroll" role="region" aria-label="Persisted run validation results" tabIndex={0}><table className="data-table validation-results-table"><caption className="visually-hidden">Actual validator results for this run attempt</caption><thead><tr><th scope="col">Validation</th><th scope="col">Category / stage</th><th scope="col">Status</th><th scope="col">Rows checked</th><th scope="col">Rows failed</th><th scope="col">Failure</th><th scope="col">Duration</th><th scope="col">Details</th></tr></thead><tbody>{results.data.items.map((item) => <tr key={item.validation_execution_id}><td><code>{item.validation_id}</code><small className="table-secondary">{item.name}</small></td><td>{item.category}<small className="table-secondary">{item.execution_stage}</small></td><td><StatusBadge status={item.status} size="small" /></td><td className="numeric-cell">{formatNumber(item.checked_rows)}</td><td className="numeric-cell">{formatNumber(item.failed_rows)}</td><td className="numeric-cell">{item.failure_percentage.toFixed(2)}%</td><td className="numeric-cell">{formatNumber(item.execution_time_ms)} ms</td><td><button className="table-action" type="button" onClick={() => setSelectedResult(item)}>Inspect</button></td></tr>)}</tbody></table></div>
          <Pagination page={results.data.page} pageSize={results.data.page_size} total={results.data.total} onPageChange={setPage} />
          {selectedResult ? <div className="validation-result-detail" aria-labelledby="validation-detail-heading"><div className="section-header"><div><p className="eyebrow">{selectedResult.validation_id}</p><h3 id="validation-detail-heading">{selectedResult.name}</h3></div><button className="table-action" type="button" onClick={() => setSelectedResult(null)}>Close details</button></div><p>{selectedResult.message}</p><p><strong>Applicability:</strong> {selectedResult.applicability} · {selectedResult.applicability_reason}</p>{selectedResult.recommendation ? <p><strong>Recommendation:</strong> {selectedResult.recommendation}</p> : null}<p><strong>Columns:</strong> {selectedResult.affected_columns.join(", ") || "None recorded"} · <strong>Rule version:</strong> {selectedResult.rule_version}</p><p><strong>Failure examples:</strong> {selectedResult.failure_examples.length ? selectedResult.failure_examples.map((example) => `source row ${example.source_row_number ?? "unknown"}`).join(", ") : "None recorded"}</p><details><summary>Configuration snapshot used for this execution</summary><pre>{JSON.stringify(selectedResult.configuration_snapshot, null, 2)}</pre></details><p className="inline-note">Failure examples contain source row identifiers only; source values are not exposed here.</p></div> : null}
        </section>}
      </> : null}
    </> : null}
  </div>;
}
