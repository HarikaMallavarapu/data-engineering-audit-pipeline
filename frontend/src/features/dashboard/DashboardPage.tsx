import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Clock3, Database, Layers3, RefreshCw, Rows3, ShieldCheck, Timer, XCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { RunDispositionChart } from "../../components/charts/RunDispositionChart";
import { RunStatusDistribution } from "../../components/charts/RunStatusDistribution";
import { MetricCard } from "../../components/common/MetricCard";
import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { RunTable } from "../../components/tables/RunTable";
import { listPipelines } from "../../services/pipelineService";
import { getReconciliation, listRuns } from "../../services/runService";
import { listSources } from "../../services/sourceService";
import type { PipelineRun } from "../../services/runService";
import { formatNumber, formatBytes } from "../../utils/format";

const terminalStatuses = new Set(["SUCCESS", "PARTIAL", "FAILED", "CANCELLED"]);
const activeStatuses = new Set(["PENDING", "RUNNING"]);
const periods = [
  { value: 1, label: "24 hours" },
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
] as const;

function chartLabel(run: PipelineRun): string {
  const date = new Date(run.created_at);
  return Number.isNaN(date.getTime()) ? run.run_id.slice(-6) : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function chartAxisLabel(run: PipelineRun, periodDays: number): string {
  const date = new Date(run.created_at);
  if (Number.isNaN(date.getTime())) return run.run_id.slice(-6);
  return periodDays === 1
    ? new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date)
    : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

function averageRunDuration(runs: PipelineRun[]): string {
  const durations = runs.flatMap((run) => {
    if (!run.started_at || !run.completed_at) return [];
    const duration = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
    return Number.isFinite(duration) && duration >= 0 ? [duration] : [];
  });
  if (!durations.length) return "—";
  const average = durations.reduce((total, value) => total + value, 0) / durations.length;
  return average < 1000 ? `${Math.round(average)} ms` : `${(average / 1000).toFixed(2)} s`;
}

export function DashboardPage() {
  const queryClient = useQueryClient();
  const [periodDays, setPeriodDays] = useState<(typeof periods)[number]["value"]>(30);
  const pipelines = useQuery({ queryKey: ["pipelines"], queryFn: listPipelines });
  const sources = useQuery({ queryKey: ["sources"], queryFn: listSources });
  const runs = useQuery({ queryKey: ["runs", 1, 100], queryFn: () => listRuns(1, 100), refetchInterval: 15_000 });
  const recentRuns = runs.data?.items ?? [];
  const latestRun = recentRuns[0];
  const cutoff = Date.now() - periodDays * 24 * 60 * 60 * 1000;
  const periodRuns = recentRuns.filter((run) => {
    const created = new Date(run.created_at).getTime();
    return Number.isFinite(created) && created >= cutoff;
  });
  const chartRuns = [...periodRuns].reverse().map((run) => ({
    label: chartLabel(run),
    axisLabel: chartAxisLabel(run, periodDays),
    runId: run.run_id,
    accepted: run.counts.accepted,
    rejected: run.counts.rejected,
    duplicates: run.counts.duplicates,
  }));
  const succeededCount = periodRuns.filter((run) => run.status === "SUCCESS").length;
  const failedCount = periodRuns.filter((run) => run.status === "FAILED").length;
  const activeCount = recentRuns.filter((run) => activeStatuses.has(run.status)).length;
  const inputCount = periodRuns.reduce((total, run) => total + run.counts.input, 0);
  const rejectedCount = periodRuns.reduce((total, run) => total + run.counts.rejected, 0);
  const reconciliation = useQuery({
    queryKey: ["reconciliation", latestRun?.run_id],
    queryFn: () => getReconciliation(latestRun!.run_id),
    enabled: Boolean(latestRun && terminalStatuses.has(latestRun.status)),
  });
  const runScope = runs.data
    ? runs.data.total > recentRuns.length
      ? `Latest ${formatNumber(recentRuns.length)} of ${formatNumber(runs.data.total)} runs`
      : `${formatNumber(runs.data.total)} recorded runs`
    : "Awaiting API data";
  const activityScope = `${periods.find((period) => period.value === periodDays)?.label ?? "Selected period"} · ${runScope.toLowerCase()}`;
  const refreshing = pipelines.isFetching || sources.isFetching || runs.isFetching;

  async function refreshDashboard() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["pipelines"] }),
      queryClient.invalidateQueries({ queryKey: ["sources"] }),
      queryClient.invalidateQueries({ queryKey: ["runs", 1, 100] }),
    ]);
  }

  return (
    <div className="page-content">
      <PageHeader
        eyebrow="OPERATIONS OVERVIEW"
        title="Command center"
        description="A live view of saved pipeline activity, validation outcomes, and source files."
        actions={<><button className="button button-secondary" type="button" onClick={() => void refreshDashboard()} disabled={refreshing}><RefreshCw size={15} aria-hidden="true" className={refreshing ? "refresh-icon-spinning" : undefined} />Refresh data</button><Link className="button button-primary" to="/sources"><Database size={16} aria-hidden="true" />Register a source</Link></>}
      />

      <section className="metric-grid dashboard-metrics" aria-label="Operational metrics">
        <MetricCard label="Pipelines" value={pipelines.data?.length ?? "—"} note={pipelines.isError ? "Pipeline API unavailable" : "Registered with the API"} icon={<Layers3 size={16} />} tone="blue" />
        <MetricCard label="Successful runs" value={runs.data ? formatNumber(succeededCount) : "—"} note={activityScope} icon={<ShieldCheck size={16} />} tone="teal" />
        <MetricCard label="Failed runs" value={runs.data ? formatNumber(failedCount) : "—"} note={activityScope} icon={<XCircle size={16} />} tone="amber" />
        <MetricCard label="Active runs" value={runs.data ? formatNumber(activeCount) : "—"} note={`${runScope} · pending or running`} icon={<Clock3 size={16} />} tone="blue" />
        <MetricCard label="Records processed" value={runs.data ? formatNumber(inputCount) : "—"} note={`Source rows · ${formatNumber(periodRuns.length)} runs`} icon={<Rows3 size={16} />} tone="neutral" />
        <MetricCard label="Rejected records" value={runs.data ? formatNumber(rejectedCount) : "—"} note="Persisted validation outcomes" icon={<AlertTriangle size={16} />} tone="amber" />
        <MetricCard label="Avg. run duration" value={runs.data ? averageRunDuration(periodRuns) : "—"} note="Completed runs in selected window" icon={<Timer size={16} />} tone="violet" />
        <MetricCard label="Quality score" value="—" note="Not exposed by the current API" icon={<ShieldCheck size={16} />} tone="neutral" />
      </section>

      <div className="dashboard-grid dashboard-main-grid">
        <section className="surface chart-surface" aria-labelledby="trend-heading">
          <div className="section-header dashboard-chart-header">
            <div><p className="eyebrow">RECORD DISPOSITION</p><h2 id="trend-heading">Run volume</h2><p className="section-description">Accepted, rejected, and duplicate rows for executions created within the selected window.</p></div>
            <div className="range-picker" role="group" aria-label="Run volume time range">
              {periods.map((period) => <button key={period.value} type="button" className={`range-option${periodDays === period.value ? " range-option-active" : ""}`} aria-pressed={periodDays === period.value} onClick={() => setPeriodDays(period.value)}>{period.value === 1 ? "24h" : `${period.value}d`}</button>)}
            </div>
          </div>
          {runs.isPending ? <StatePanel tone="loading" title="Loading run history" message="Reading persisted run records from the API." compact /> : null}
          {runs.isError ? <StatePanel tone="error" title="Run history unavailable" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} compact /> : null}
          {runs.data && chartRuns.length === 0 ? <StatePanel tone="empty" title="No runs in this time range" message="Choose a longer window or start a CSV run to view real execution counts." action={<Link className="button button-secondary" to="/sources">Register a source</Link>} compact /> : null}
          {chartRuns.length > 0 ? <div className="chart-container"><RunDispositionChart data={chartRuns} /><p className="chart-footnote">{runScope} returned by the API; the time filter applies to those persisted records.</p></div> : null}
        </section>

        <div className="dashboard-side-stack">
          <section className="surface outcome-surface" aria-labelledby="outcomes-heading">
            <div className="section-header"><div><p className="eyebrow">EXECUTION MIX</p><h2 id="outcomes-heading">Outcomes by status</h2></div><span className="data-window-label">{formatNumber(periodRuns.length)} runs</span></div>
            <RunStatusDistribution runs={periodRuns} />
            <p className="chart-footnote">{activityScope}. Each segment represents a persisted run status.</p>
          </section>

          <section className="surface health-surface" aria-labelledby="health-heading">
            <div className="section-header"><div><p className="eyebrow">LATEST EXECUTION</p><h2 id="health-heading">Run health</h2></div></div>
            {!latestRun && runs.isPending ? <StatePanel tone="loading" title="Checking latest run" message="Waiting for run history." compact /> : null}
            {!latestRun && runs.data ? <StatePanel tone="empty" title="No runs recorded" message="A reconciliation result will appear after the first pipeline run." compact /> : null}
            {latestRun ? <div className="latest-run-card">
              <div className="latest-run-top"><span className="run-kicker">{latestRun.pipeline_id}</span><span className={`status-badge status-${latestRun.status.toLowerCase()}`}><span className="status-dot" aria-hidden="true" />{latestRun.status}</span></div>
              <Link className="latest-run-id" to={`/runs/${encodeURIComponent(latestRun.run_id)}`}>{latestRun.run_id}</Link>
              <div className="mini-counts"><span><strong>{formatNumber(latestRun.counts.input)}</strong> input</span><span><strong>{formatNumber(latestRun.counts.published)}</strong> published</span></div>
              {reconciliation.isPending && terminalStatuses.has(latestRun.status) ? <p className="inline-note">Checking persisted reconciliation…</p> : null}
              {reconciliation.data ? <p className={`reconciliation-callout ${reconciliation.data.balanced ? "callout-success" : "callout-error"}`}><span aria-hidden="true">{reconciliation.data.balanced ? "✓" : "!"}</span>{reconciliation.data.balanced ? "Reconciliation balanced" : "Reconciliation mismatch"}</p> : null}
              {reconciliation.isError ? <p className="inline-note">Reconciliation evidence is unavailable for this run.</p> : null}
              <Link className="text-link" to="/reconciliation">Open reconciliation workspace <span aria-hidden="true">→</span></Link>
            </div> : null}
          </section>
        </div>
      </div>

      <div className="dashboard-grid dashboard-lower-grid">
        <section className="surface table-surface" aria-labelledby="recent-runs-heading">
          <div className="section-header"><div><p className="eyebrow">PERSISTED HISTORY</p><h2 id="recent-runs-heading">Recent runs</h2></div><Link className="text-link" to="/runs">View all runs <span aria-hidden="true">→</span></Link></div>
          {runs.isPending ? <StatePanel tone="loading" title="Loading executions" message="The API is returning recent runs." compact /> : null}
          {runs.isError ? <StatePanel tone="error" title="Could not load runs" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} compact /> : null}
          {runs.data && recentRuns.length === 0 ? <StatePanel tone="empty" title="No execution history" message="Run a registered tabular source to populate the history." action={<Link className="button button-secondary" to="/sources">Register a source</Link>} compact /> : null}
          {runs.data && recentRuns.length > 0 ? <RunTable runs={recentRuns.slice(0, 6)} caption="Six most recent pipeline runs" /> : null}
        </section>
        <section className="surface source-activity" aria-labelledby="source-activity-heading">
          <div className="section-header"><div><p className="eyebrow">SOURCE REGISTRY</p><h2 id="source-activity-heading">Recent sources</h2></div><Link className="text-link" to="/sources">Open registry <span aria-hidden="true">→</span></Link></div>
          {sources.isPending ? <StatePanel tone="loading" title="Loading sources" message="Reading registered source files." compact /> : null}
          {sources.isError ? <StatePanel tone="error" title="Source registry unavailable" message={sources.error.message} action={<button className="button button-secondary" onClick={() => void sources.refetch()}>Retry</button>} compact /> : null}
          {sources.data?.items.length === 0 ? <StatePanel tone="empty" title="No source files" message="Registered CSV files will appear here." action={<Link className="button button-secondary" to="/sources">Register a source</Link>} compact /> : null}
          {sources.data?.items.length ? <ul className="source-activity-list">{sources.data.items.slice(0, 5).map((source) => <li key={source.source_file_id}><Database size={16} aria-hidden="true" /><span><strong>{source.original_filename}</strong><small>{source.columns.length} columns · {formatBytes(source.size_bytes)}</small></span><Link to="/sources" aria-label={`View ${source.original_filename} in source registry`}>View</Link></li>)}</ul> : null}
        </section>
      </div>
    </div>
  );
}
