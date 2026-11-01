import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { GitCompare } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { StatusBadge } from "../../components/common/StatusBadge";
import { compareQualityRuns, getValidationHistory, listRuns } from "../../services/runService";
import type { QualityRunComparison } from "../../services/runService";
import { formatNumber, shortId } from "../../utils/format";

const PAGE_SIZE = 25;
const RESULT_STATUSES = ["PASS", "FAIL", "WARNING", "ERROR", "SKIPPED", "NOT_APPLICABLE", "REQUIRES_CONFIGURATION", "BLOCKED"];

function dayStart(value: string): string | undefined {
  return value ? `${value}T00:00:00Z` : undefined;
}

function dayEnd(value: string): string | undefined {
  return value ? `${value}T23:59:59.999Z` : undefined;
}

function rateLabel(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "—";
}

function RunComparison({ result }: { result: QualityRunComparison }) {
  const rowCount = result.row_count_change;
  const duplicate = result.duplicate_rate_change;
  const schema = result.schema_drift;
  return <div className="validation-run-comparison-result">
    <div className="validation-run-comparison-meta"><strong>{result.reference_filename}</strong><span>{shortId(result.reference_run_id)} · {shortId(result.reference_attempt_id)}</span><span aria-hidden="true">→</span><strong>{result.comparison_filename}</strong><span>{shortId(result.comparison_run_id)} · {shortId(result.comparison_attempt_id)}</span></div>
    <div className="validation-run-comparison-metrics">
      <article><small>Source rows</small><strong>{formatNumber(rowCount.baseline)} → {formatNumber(rowCount.current)}</strong><span>{rowCount.delta > 0 ? "+" : ""}{formatNumber(rowCount.delta)} rows · {rowCount.delta_percent === null ? "change % unavailable" : `${rowCount.delta_percent > 0 ? "+" : ""}${rowCount.delta_percent.toFixed(2)}%`}</span></article>
      <article><small>Duplicate rate</small><strong>{rateLabel(duplicate.baseline_rate)} → {rateLabel(duplicate.current_rate)}</strong><span>{duplicate.delta_percentage_points === null ? "Change unavailable" : `${duplicate.delta_percentage_points > 0 ? "+" : ""}${duplicate.delta_percentage_points.toFixed(2)} percentage points`}</span></article>
      <article><small>Schema</small><strong>{schema.changed ? "Changed" : "Stable"}</strong><span>{schema.added_columns.length} added · {schema.missing_columns.length} missing · {schema.type_changes.length} type changes</span></article>
      <article><small>Drift signals</small><strong>{formatNumber(result.anomaly_signals.length)}</strong><span>Review signals; no records are declared invalid</span></article>
    </div>
    <div className="table-scroll" role="region" aria-label="Compared validation outcomes" tabIndex={0}><table className="data-table"><caption className="visually-hidden">Persisted validation outcomes across two selected runs</caption><thead><tr><th scope="col">Validation ID</th><th scope="col">Reference</th><th scope="col">Comparison</th><th scope="col">Failure rate</th><th scope="col">Change</th></tr></thead><tbody>{result.validation_failure_changes.map((item) => <tr key={item.validation_id}><td><code>{item.validation_id}</code></td><td>{item.baseline_status ?? "No result"} · {rateLabel(item.baseline_failure_rate)}</td><td>{item.current_status ?? "No result"} · {rateLabel(item.current_failure_rate)}</td><td>{item.delta_percentage_points === null ? "Not comparable" : `${item.delta_percentage_points > 0 ? "+" : ""}${item.delta_percentage_points.toFixed(2)} pp`}</td><td>{item.assessment.replaceAll("_", " ")}</td></tr>)}</tbody></table></div>
    <p className="inline-note">Comparison uses source profiles and persisted per-check records from each selected run. Checks that were skipped, not applicable, blocked, or awaiting configuration have no failure-rate value. Aggregate drift does not prove individual records invalid.</p>
    {result.limitations.length ? <details className="validation-run-comparison-limits"><summary>Comparison limitations</summary><ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul></details> : null}
  </div>;
}

export function ValidationHistoryPage() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [validationId, setValidationId] = useState(searchParams.get("validation_id") ?? "");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [pipelineId, setPipelineId] = useState("");
  const [sourceFileId, setSourceFileId] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [page, setPage] = useState(1);
  const [referenceRunId, setReferenceRunId] = useState("");
  const [comparisonRunId, setComparisonRunId] = useState("");
  const runs = useQuery({ queryKey: ["runs", "validation-history-compare"], queryFn: () => listRuns(1, 100) });
  const terminalRuns = useMemo(() => (runs.data?.items ?? []).filter((run) => ["SUCCESS", "PARTIAL", "FAILED", "CANCELLED"].includes(run.status)), [runs.data?.items]);
  const referenceRun = terminalRuns.find((run) => run.run_id === referenceRunId);
  const compatibleRuns = terminalRuns.filter((run) => run.pipeline_id === referenceRun?.pipeline_id && run.run_id !== referenceRunId);
  const comparison = useQuery({
    queryKey: ["validation-run-comparison", referenceRunId, comparisonRunId],
    queryFn: () => compareQualityRuns(referenceRunId, comparisonRunId),
    enabled: Boolean(referenceRunId && comparisonRunId && referenceRunId !== comparisonRunId),
  });
  useEffect(() => {
    if (!terminalRuns.length) return;
    setReferenceRunId((current) => terminalRuns.some((run) => run.run_id === current) ? current : terminalRuns[0].run_id);
  }, [terminalRuns]);
  useEffect(() => {
    if (!referenceRun) return;
    setComparisonRunId((current) => compatibleRuns.some((run) => run.run_id === current) ? current : compatibleRuns[0]?.run_id ?? "");
  }, [compatibleRuns, referenceRun]);
  const filters = [search, validationId, category, status, pipelineId, sourceFileId, createdFrom, createdTo];
  const history = useQuery({
    queryKey: ["validation-history", page, ...filters],
    enabled: !(createdFrom && createdTo && createdFrom > createdTo),
    queryFn: () => getValidationHistory({
      page,
      pageSize: PAGE_SIZE,
      search,
      validationId: validationId || undefined,
      category: category || undefined,
      status: status || undefined,
      pipelineId: pipelineId || undefined,
      sourceFileId: sourceFileId || undefined,
      createdFrom: dayStart(createdFrom),
      createdTo: dayEnd(createdTo),
    }),
  });
  const hasFilters = filters.some(Boolean);
  const clearFilters = () => {
    setSearch("");
    setValidationId("");
    setCategory("");
    setStatus("");
    setPipelineId("");
    setSourceFileId("");
    setCreatedFrom("");
    setCreatedTo("");
    setPage(1);
  };

  return <div className="page-content">
    <PageHeader eyebrow="VALIDATION CENTER" title="Validation history" description="Search persisted check executions across runs and attempts. No history is inferred from pipeline stages." actions={<Link className="button button-secondary" to="/validation/results">Open run results</Link>} />
    <section className="surface validation-run-compare-surface" aria-labelledby="validation-run-compare-heading">
      <div className="section-header"><div><p className="eyebrow">READ-ONLY HISTORICAL COMPARISON</p><h2 id="validation-run-compare-heading"><GitCompare size={16} aria-hidden="true" /> Compare two runs</h2><p className="section-description">Compare source quality profiles and saved check outcomes without creating a baseline or changing run history.</p></div><span className="data-window-label">Same pipeline required</span></div>
      <div className="validation-run-compare-form">
        <label className="select-field"><span>Reference run</span><select value={referenceRunId} onChange={(event) => { const nextId = event.currentTarget.value; const nextReference = terminalRuns.find((run) => run.run_id === nextId); setReferenceRunId(nextId); setComparisonRunId(terminalRuns.find((run) => run.pipeline_id === nextReference?.pipeline_id && run.run_id !== nextId)?.run_id ?? ""); }}><option value="">Choose a completed run</option>{terminalRuns.map((run) => <option key={run.run_id} value={run.run_id}>{shortId(run.run_id)} · {run.pipeline_id} · {run.status}</option>)}</select></label>
        <label className="select-field"><span>Run to compare</span><select value={comparisonRunId} disabled={!compatibleRuns.length} onChange={(event) => setComparisonRunId(event.currentTarget.value)}><option value="">Choose another run</option>{compatibleRuns.map((run) => <option key={run.run_id} value={run.run_id}>{shortId(run.run_id)} · {run.pipeline_id} · {run.status}</option>)}</select></label>
      </div>
      {runs.isError ? <StatePanel tone="error" title="Pipeline runs unavailable" message={runs.error.message} action={<button className="button button-secondary" type="button" onClick={() => void runs.refetch()}>Retry</button>} compact /> : null}
      {!runs.isPending && !runs.isError && !terminalRuns.length ? <StatePanel tone="empty" title="No completed runs to compare" message="Completed pipeline attempts appear here when available." compact /> : null}
      {referenceRun && !compatibleRuns.length ? <p className="inline-note">No second completed run is available for pipeline <code>{referenceRun.pipeline_id}</code>.</p> : null}
      {comparison.isPending && referenceRunId && comparisonRunId ? <StatePanel tone="loading" title="Comparing selected runs" message="Reading saved profiles and validation execution snapshots." compact /> : null}
      {comparison.isError ? <StatePanel tone="error" title="Run comparison unavailable" message={comparison.error.message} action={<button className="button button-secondary" type="button" onClick={() => void comparison.refetch()}>Retry</button>} compact /> : null}
      {comparison.data ? <RunComparison result={comparison.data} /> : null}
    </section>
    {history.isPending ? <StatePanel tone="loading" title="Loading validation history" message="Reading saved validation executions from the backend." /> : null}
    {history.isError ? <StatePanel tone="error" title="Validation history unavailable" message={history.error.message} action={<button className="button button-secondary" onClick={() => void history.refetch()}>Retry</button>} /> : null}
    {history.data ? <section className="surface validation-history-surface" aria-labelledby="validation-history-heading">
      <div className="section-header"><div><p className="eyebrow">PERSISTED EXECUTIONS</p><h2 id="validation-history-heading">Historical check outcomes</h2></div><span className="data-window-label">{formatNumber(history.data.total)} matching results</span></div>
      <div className="validation-filter-grid validation-history-filters" aria-label="Validation history filters">
        <label className="search-field"><span className="visually-hidden">Search validation history</span><input value={search} onChange={(event) => { setSearch(event.currentTarget.value); setPage(1); }} placeholder="Search check or dataset name" /></label>
        <label className="catalog-text-filter"><span>Validation ID</span><input value={validationId} onChange={(event) => { setValidationId(event.currentTarget.value); setPage(1); }} placeholder="Exact check ID" /></label>
        <label className="catalog-text-filter"><span>Pipeline ID</span><input value={pipelineId} onChange={(event) => { setPipelineId(event.currentTarget.value); setPage(1); }} placeholder="Any pipeline" /></label>
        <label className="catalog-text-filter"><span>Source file ID</span><input value={sourceFileId} onChange={(event) => { setSourceFileId(event.currentTarget.value); setPage(1); }} placeholder="Any dataset" /></label>
        <label className="catalog-text-filter"><span>Category</span><input value={category} onChange={(event) => { setCategory(event.currentTarget.value); setPage(1); }} placeholder="Any category" /></label>
        <label className="select-field"><span>Result status</span><select value={status} onChange={(event) => { setStatus(event.currentTarget.value); setPage(1); }}><option value="">All statuses</option>{RESULT_STATUSES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
        <label className="catalog-text-filter"><span>From date</span><input type="date" value={createdFrom} onChange={(event) => { setCreatedFrom(event.currentTarget.value); setPage(1); }} /></label>
        <label className="catalog-text-filter"><span>To date</span><input type="date" value={createdTo} onChange={(event) => { setCreatedTo(event.currentTarget.value); setPage(1); }} /></label>
        <button className="button button-secondary validation-filter-reset" type="button" onClick={clearFilters} disabled={!hasFilters}>Clear filters</button>
      </div>
      {createdFrom && createdTo && createdFrom > createdTo ? <p className="form-error" role="alert">The start date must be before the end date.</p> : null}
      {history.data.total === 0 ? <StatePanel tone="empty" title={hasFilters ? "No saved results match these filters" : "No validation history yet"} message={hasFilters ? "Clear a filter or adjust the date range." : "Completed pipeline runs will appear here when they contain persisted check results."} /> : <>
        <div className="table-scroll" role="region" aria-label="Historical validation results" tabIndex={0}><table className="data-table validation-results-table"><caption className="visually-hidden">Persisted validation results across pipeline attempts</caption><thead><tr><th scope="col">Check</th><th scope="col">Status</th><th scope="col">Category</th><th scope="col">Dataset</th><th scope="col">Pipeline</th><th scope="col">Run / attempt</th><th scope="col">Rows failed</th><th scope="col">Duration</th><th scope="col">Executed</th></tr></thead><tbody>{history.data.items.map((item) => <tr key={item.validation_execution_id}><td><code>{item.validation_id}</code><small className="table-secondary">{item.name}</small></td><td><StatusBadge status={item.status} size="small" /></td><td>{item.category}</td><td><strong>{item.original_filename}</strong><small className="table-secondary">{shortId(item.source_file_id)}</small></td><td>{item.pipeline_id}</td><td><Link className="validation-history-run-link" to={`/validation/results?run_id=${encodeURIComponent(item.run_id)}&attempt_id=${encodeURIComponent(item.attempt_id)}`}>{shortId(item.run_id)} · attempt {item.attempt_number}</Link></td><td className="numeric-cell">{formatNumber(item.failed_rows)} / {formatNumber(item.checked_rows)}</td><td className="numeric-cell">{formatNumber(item.execution_time_ms)} ms</td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>
        <Pagination page={history.data.page} pageSize={history.data.page_size} total={history.data.total} onPageChange={setPage} />
      </>}
    </section> : null}
  </div>;
}
