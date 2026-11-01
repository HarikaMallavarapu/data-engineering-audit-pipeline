import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Clock3, GitCompare, Plus, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../../components/common/MetricCard";
import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { compareQualityBaseline, createQualityBaseline, listQualityBaselines, listRuns } from "../../services/runService";
import type { QualityBaselineComparison } from "../../services/runService";
import { formatNumber, shortId } from "../../utils/format";

function percent(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(2)}%`;
}

function signedPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function signalLabel(value: unknown) {
  return typeof value === "string" ? value.replaceAll("_", " ") : "Not assessed";
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numberLabel(value: unknown) {
  const number = finiteNumber(value);
  return number === null ? "—" : formatNumber(number);
}

function secondsLabel(value: unknown) {
  const number = finiteNumber(value);
  return number === null ? "—" : formatNumber(Math.round(number));
}

function ComparisonDetails({ result }: { result: QualityBaselineComparison }) {
  const schema = result.schema_drift;
  return <>
    <div className="metric-grid validation-metric-grid">
      <MetricCard label="Row count" value={formatNumber(result.row_count_change.current)} note={`${signedPercent(result.row_count_change.delta_percent)} vs baseline`} icon={<Activity size={15} />} tone={Math.abs(result.row_count_change.delta_percent ?? 0) >= 25 ? "amber" : "blue"} />
      <MetricCard label="Duplicate rate" value={percent(result.duplicate_rate_change.current_rate)} note={`${result.duplicate_rate_change.delta_percentage_points === null ? "—" : `${result.duplicate_rate_change.delta_percentage_points > 0 ? "+" : ""}${result.duplicate_rate_change.delta_percentage_points.toFixed(2)} pp`} vs baseline`} icon={<GitCompare size={15} />} tone="violet" />
      <MetricCard label="Schema" value={schema.changed ? "Changed" : "Stable"} note={`${schema.added_columns.length} added · ${schema.missing_columns.length} missing · ${schema.type_changes.length} type changes`} icon={<AlertTriangle size={15} />} tone={schema.changed ? "amber" : "teal"} />
      <MetricCard label="Drift signals" value={formatNumber(result.anomaly_signals.length)} note="Signals do not confirm invalid records" icon={<Clock3 size={15} />} tone={result.anomaly_signals.length ? "amber" : "teal"} />
    </div>

    {result.anomaly_signals.length ? <section className="baseline-signal-list" aria-label="Anomaly signals"><h3>Signals to review</h3><ul>{result.anomaly_signals.map((signal, index) => <li key={`${signal.type}-${index}`}><strong>{signalLabel(signal.type)}</strong>{signal.column ? <code>{String(signal.column)}</code> : null}<span>Signal only · no record-level invalidity confirmed</span></li>)}</ul></section> : <p className="inline-note">No configured anomaly threshold was crossed in the available comparisons.</p>}

    <div className="baseline-comparison-grid">
      <section className="validation-analytics-panel"><h3>Null-rate changes</h3>{result.null_rate_changes.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Column</th><th scope="col">Baseline</th><th scope="col">Current</th><th scope="col">Change</th></tr></thead><tbody>{result.null_rate_changes.map((item) => <tr key={item.column}><th scope="row">{item.column}</th><td>{percent(item.baseline_rate)}</td><td>{percent(item.current_rate)}</td><td>{item.delta_percentage_points === null ? "—" : `${item.delta_percentage_points > 0 ? "+" : ""}${item.delta_percentage_points.toFixed(2)} pp`}</td></tr>)}</tbody></table></div> : <p className="inline-note">No common columns to compare.</p>}</section>
      <section className="validation-analytics-panel"><h3>Schema drift</h3>{schema.changed ? <ul className="baseline-detail-list">{schema.added_columns.map((column) => <li key={`added-${column}`}>Added column <code>{column}</code></li>)}{schema.missing_columns.map((column) => <li key={`missing-${column}`}>Missing column <code>{column}</code></li>)}{schema.type_changes.map((change) => <li key={`type-${change.column}`}>Type changed for <code>{change.column}</code>: {change.baseline_type ?? "unknown"} → {change.current_type ?? "unknown"}</li>)}</ul> : <p className="inline-note">Column set and inferred types match the baseline.</p>}</section>
      <section className="validation-analytics-panel"><h3>Numeric distribution drift</h3>{result.numeric_distribution_drift.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Column</th><th scope="col">Samples</th><th scope="col">PSI</th><th scope="col">Binned KS</th><th scope="col">Assessment</th></tr></thead><tbody>{result.numeric_distribution_drift.map((item) => <tr key={item.column}><th scope="row">{item.column}</th><td>{numberLabel(item.baseline_sample_size)} / {numberLabel(item.current_sample_size)}</td><td>{typeof item.psi === "number" ? item.psi.toFixed(4) : "—"}</td><td>{typeof item.binned_ks_distance === "number" ? item.binned_ks_distance.toFixed(4) : "—"}</td><td>{signalLabel(item.psi_signal ?? item.status)}</td></tr>)}</tbody></table></div> : <p className="inline-note">No numeric columns were available in both runs.</p>}<p className="inline-note">PSI uses the same baseline bins for both samples. Binned KS is a distance statistic; no p-value is inferred.</p></section>
      <section className="validation-analytics-panel"><h3>Value-shape distribution</h3>{result.value_shape_distribution_drift.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Column</th><th scope="col">PSI</th><th scope="col">Assessment</th></tr></thead><tbody>{result.value_shape_distribution_drift.map((item) => <tr key={item.column}><th scope="row">{item.column}</th><td>{typeof item.psi === "number" ? item.psi.toFixed(4) : "—"}</td><td>{signalLabel(item.psi_signal ?? item.status)}</td></tr>)}</tbody></table></div> : <p className="inline-note">No generalized shape distributions were available for comparison.</p>}<p className="inline-note">Raw category values are not stored. These shape buckets are not domain category frequencies.</p></section>
      <section className="validation-analytics-panel"><h3>Freshness and outliers</h3>{result.freshness_changes.length ? <ul className="baseline-detail-list">{result.freshness_changes.map((item) => <li key={`fresh-${item.column}`}><code>{item.column}</code> latest timestamp moved by {secondsLabel(item.delta_seconds)} seconds.</li>)}</ul> : <p className="inline-note">No shared timestamp columns were found.</p>}{result.outlier_changes.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Numeric column</th><th scope="col">Baseline outlier rate</th><th scope="col">Current</th><th scope="col">Change</th></tr></thead><tbody>{result.outlier_changes.map((item) => { const delta = finiteNumber(item.delta_percentage_points); return <tr key={`outlier-${item.column}`}><th scope="row">{item.column}</th><td>{percent(finiteNumber(item.baseline_rate))}</td><td>{percent(finiteNumber(item.current_rate))}</td><td>{delta === null ? "—" : `${delta > 0 ? "+" : ""}${delta.toFixed(2)} pp`}</td></tr>; })}</tbody></table></div> : null}</section>
      <section className="validation-analytics-panel"><h3>Validation failure trends</h3>{result.validation_failure_changes.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Validation ID</th><th scope="col">Baseline</th><th scope="col">Current</th><th scope="col">Assessment</th></tr></thead><tbody>{result.validation_failure_changes.map((item) => <tr key={item.validation_id}><th scope="row"><code>{item.validation_id}</code></th><td>{percent(finiteNumber(item.baseline_failure_rate))}</td><td>{percent(finiteNumber(item.current_failure_rate))}</td><td>{signalLabel(item.assessment)}</td></tr>)}</tbody></table></div> : <p className="inline-note">No persisted validation results are available in either attempt.</p>}<p className="inline-note">Results are matched by stored runtime validation ID. Catalog files are not imported yet.</p></section>
    </div>

    <section className="baseline-limitations"><h3>How to read this comparison</h3><p>Aggregate drift can guide review, but it does not prove individual records are invalid. Numeric PSI and binned KS are omitted when either sample has fewer than 100 numeric values. The binned KS result is not a statistical significance test.</p>{result.limitations.length ? <ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul> : null}</section>
  </>;
}

export function ValidationBaselinesPage() {
  const queryClient = useQueryClient();
  const [sourceRunId, setSourceRunId] = useState("");
  const [datasetIdentity, setDatasetIdentity] = useState("");
  const [selectedBaselineId, setSelectedBaselineId] = useState("");
  const [targetRunId, setTargetRunId] = useState("");
  const runs = useQuery({ queryKey: ["runs", "validation-baselines"], queryFn: () => listRuns(1, 100) });
  const baselines = useQuery({ queryKey: ["quality-baselines"], queryFn: () => listQualityBaselines({ page: 1, pageSize: 100 }) });
  const terminalRuns = useMemo(() => (runs.data?.items ?? []).filter((run) => ["SUCCESS", "PARTIAL", "FAILED", "CANCELLED"].includes(run.status)), [runs.data?.items]);
  const selectedBaseline = baselines.data?.items.find((baseline) => baseline.baseline_id === selectedBaselineId);
  const comparison = useQuery({
    queryKey: ["quality-baseline-comparison", selectedBaselineId, targetRunId],
    queryFn: () => compareQualityBaseline(selectedBaselineId, targetRunId),
    enabled: Boolean(selectedBaselineId && targetRunId),
  });
  const createBaseline = useMutation({
    mutationFn: () => createQualityBaseline(sourceRunId, datasetIdentity),
    onSuccess: async (baseline) => {
      setSelectedBaselineId(baseline.baseline_id);
      setTargetRunId(baseline.run_id);
      await queryClient.invalidateQueries({ queryKey: ["quality-baselines"] });
    },
  });

  useEffect(() => {
    if (!terminalRuns.length) return;
    setSourceRunId((current) => current || terminalRuns[0].run_id);
    setTargetRunId((current) => current || terminalRuns[0].run_id);
  }, [terminalRuns]);
  useEffect(() => {
    if (!selectedBaselineId && baselines.data?.items.length) setSelectedBaselineId(baselines.data.items[0].baseline_id);
  }, [baselines.data?.items, selectedBaselineId]);
  useEffect(() => {
    if (!selectedBaseline) return;
    const currentTarget = terminalRuns.find((run) => run.run_id === targetRunId);
    if (currentTarget?.pipeline_id === selectedBaseline.pipeline_id) return;
    setTargetRunId(terminalRuns.find((run) => run.pipeline_id === selectedBaseline.pipeline_id)?.run_id ?? "");
  }, [selectedBaseline, targetRunId, terminalRuns]);

  return <div className="page-content">
    <PageHeader eyebrow="VALIDATION CENTER" title="Baselines and drift" description="Save immutable aggregate baselines from completed pipeline attempts, then compare later runs with the same evidence and statistical settings." />

    <section className="surface baseline-create-surface" aria-labelledby="baseline-create-heading">
      <div className="section-header"><div><p className="eyebrow">VERSIONED REFERENCE</p><h2 id="baseline-create-heading">Create a quality baseline</h2><p className="section-description">The baseline stores schema, counts, rates, numeric histograms, generalized value shapes, freshness, and persisted check outcomes. Raw category values are excluded.</p></div></div>
      {runs.isError ? <StatePanel tone="error" title="Pipeline runs unavailable" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} compact /> : null}
      <form className="baseline-form" onSubmit={(event) => { event.preventDefault(); createBaseline.mutate(); }}>
        <label className="select-field"><span>Completed source run</span><select value={sourceRunId} onChange={(event) => setSourceRunId(event.currentTarget.value)} required disabled={!terminalRuns.length}><option value="">Choose a completed run</option>{terminalRuns.map((run) => <option key={run.run_id} value={run.run_id}>{shortId(run.run_id)} · {run.pipeline_id} · {run.status} · {new Date(run.created_at).toLocaleString()}</option>)}</select></label>
        <label className="select-field"><span>Dataset identity <small>Optional</small></span><input value={datasetIdentity} onChange={(event) => setDatasetIdentity(event.currentTarget.value)} maxLength={255} placeholder="Defaults to pipeline and source filename" /></label>
        <button className="button button-primary" type="submit" disabled={!sourceRunId || createBaseline.isPending}><Plus size={15} />{createBaseline.isPending ? "Saving baseline…" : "Create baseline"}</button>
      </form>
      {!runs.isPending && terminalRuns.length === 0 && !runs.isError ? <p className="inline-note">No completed pipeline attempts are available yet.</p> : null}
      {createBaseline.isError ? <p className="form-error" role="alert">{createBaseline.error.message}</p> : null}
      {createBaseline.data ? <p className="form-success" role="status">Saved baseline v{createBaseline.data.baseline_version} for <code>{createBaseline.data.dataset_identity}</code>.</p> : null}
    </section>

    <section className="surface baseline-compare-surface" aria-labelledby="baseline-compare-heading">
      <div className="section-header"><div><p className="eyebrow">HISTORICAL COMPARISON</p><h2 id="baseline-compare-heading">Compare a run to a baseline</h2></div><button className="button button-secondary button-small" type="button" onClick={() => { void baselines.refetch(); void runs.refetch(); }}><RefreshCw size={13} />Refresh</button></div>
      <div className="baseline-form baseline-compare-form">
        <label className="select-field"><span>Baseline</span><select value={selectedBaselineId} onChange={(event) => setSelectedBaselineId(event.currentTarget.value)}><option value="">Choose a baseline</option>{(baselines.data?.items ?? []).map((baseline) => <option key={baseline.baseline_id} value={baseline.baseline_id}>{baseline.dataset_identity} · v{baseline.baseline_version} · {formatNumber(baseline.sample_size)} sampled</option>)}</select></label>
        <label className="select-field"><span>Target run</span><select value={targetRunId} onChange={(event) => setTargetRunId(event.currentTarget.value)}><option value="">Choose a completed run</option>{terminalRuns.filter((run) => !selectedBaseline || run.pipeline_id === selectedBaseline.pipeline_id).map((run) => <option key={run.run_id} value={run.run_id}>{shortId(run.run_id)} · {run.pipeline_id} · {run.status} · {new Date(run.created_at).toLocaleString()}</option>)}</select></label>
      </div>
      {baselines.isPending ? <StatePanel tone="loading" title="Loading baselines" message="Reading saved versioned aggregate profiles." compact /> : null}
      {baselines.isError ? <StatePanel tone="error" title="Baselines unavailable" message={baselines.error.message} action={<button className="button button-secondary" onClick={() => void baselines.refetch()}>Retry</button>} compact /> : null}
      {baselines.data?.items.length === 0 ? <StatePanel tone="empty" title="No baselines yet" message="Create a baseline from a completed run to start tracking data and validation drift." compact /> : null}
      {selectedBaseline ? <div className="baseline-reference-note"><span><strong>{selectedBaseline.dataset_identity} · v{selectedBaseline.baseline_version}</strong><small>Schema {selectedBaseline.schema_version ?? "not recorded"} · {formatNumber(selectedBaseline.sample_size)} profile rows · reference {new Date(selectedBaseline.reference_period_start).toLocaleString()} to {new Date(selectedBaseline.reference_period_end).toLocaleString()}</small></span><code>{shortId(selectedBaseline.baseline_id)}</code></div> : null}
      {comparison.isPending && selectedBaselineId && targetRunId ? <StatePanel tone="loading" title="Comparing stored observations" message="Calculating count, schema, distribution, freshness and validation changes." compact /> : null}
      {comparison.isError ? <StatePanel tone="error" title="Comparison unavailable" message={comparison.error.message} action={<button className="button button-secondary" onClick={() => void comparison.refetch()}>Retry</button>} compact /> : null}
      {comparison.data ? <ComparisonDetails result={comparison.data} /> : null}
    </section>
  </div>;
}
