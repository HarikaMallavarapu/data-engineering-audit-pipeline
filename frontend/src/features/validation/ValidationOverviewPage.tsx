import { useQuery } from "@tanstack/react-query";
import { Activity, BookOpenCheck, CircleAlert, Timer } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { MetricCard } from "../../components/common/MetricCard";
import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { getValidationAnalytics, listRuns, getValidationCatalog, getValidationRunResults } from "../../services/runService";
import { formatNumber, shortId } from "../../utils/format";

export function ValidationOverviewPage() {
  const [days, setDays] = useState(30);
  const catalog = useQuery({ queryKey: ["validation-catalog", "summary"], queryFn: () => getValidationCatalog({ page: 1, pageSize: 1 }) });
  const runs = useQuery({ queryKey: ["runs", "validation-overview"], queryFn: () => listRuns(1, 1) });
  const analytics = useQuery({ queryKey: ["validation-analytics", days], queryFn: () => getValidationAnalytics({ days }) });
  const runId = runs.data?.items[0]?.run_id ?? "";
  const results = useQuery({ queryKey: ["validation-run-results", runId], queryFn: () => getValidationRunResults(runId), enabled: Boolean(runId) });
  const catalogLoaded = catalog.data?.source_status === "READY" || catalog.data?.source_status === "PARTIAL";
  const summary = results.data?.summary;
  const failureCount = (analytics.data?.status_counts.FAIL ?? 0) + (analytics.data?.status_counts.ERROR ?? 0);
  const maximumCategoryFailures = Math.max(1, ...(analytics.data?.failures_by_category.map((item) => item.failures) ?? []));

  return <div className="page-content">
    <PageHeader eyebrow="VALIDATION CENTER" title="Validation overview" description="Catalog definitions and saved run outcomes stay separate. Every number here comes from the validation API." actions={<Link className="button button-secondary" to="/validation/results">Open run results</Link>} />
    {catalog.isError ? <StatePanel tone="error" title="Catalog summary unavailable" message={catalog.error.message} action={<button className="button button-secondary" onClick={() => void catalog.refetch()}>Retry</button>} /> : null}
    <div className="metric-grid validation-metric-grid">
      <MetricCard label="Catalog definitions" value={catalogLoaded ? formatNumber(catalog.data?.total ?? 0) : "—"} note={catalog.data?.source_status === "PARTIAL" ? "Partial import" : catalogLoaded ? "Imported source definitions" : "Source catalog not available"} icon={<BookOpenCheck size={15} />} tone="blue" />
      <MetricCard label="Fully implemented" value={catalogLoaded ? formatNumber(catalog.data?.counts.FULLY_IMPLEMENTED ?? 0) : "—"} note="Status recorded in catalog" icon={<Activity size={15} />} tone="teal" />
      <MetricCard label="Latest run checks" value={summary ? formatNumber(summary.executed) : "—"} note={runId ? `Persisted for ${shortId(runId)}` : "No pipeline runs yet"} icon={<CircleAlert size={15} />} tone="amber" />
      <MetricCard label="Latest check duration" value={summary ? `${formatNumber(summary.execution_duration_ms)} ms` : "—"} note="Sum of saved validator timings" icon={<Timer size={15} />} tone="violet" />
    </div>
    {catalog.data?.source_status === "SOURCE_MISSING" ? <StatePanel tone="info" title="The 200-check source catalog is missing" message={catalog.data.message ?? "Add the two supplied reference catalogs to docs/reference before importing definitions."} action={<Link className="button button-secondary" to="/validation/catalog">View catalog status</Link>} /> : null}
    {runs.isPending ? <StatePanel tone="loading" title="Loading latest run" message="Reading recent persisted runs." /> : null}
    {runs.isError ? <StatePanel tone="error" title="Run history unavailable" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} /> : null}
    {runs.data?.items.length === 0 ? <StatePanel tone="empty" title="No pipeline runs yet" message="Individual validation results appear after a run executes checks that persist per-check evidence." action={<Link className="button button-secondary" to="/sources">Register a source</Link>} /> : null}
    {runId && results.isPending ? <StatePanel tone="loading" title="Loading run validation evidence" message="Reading saved check-level results from the latest run." /> : null}
    {results.isError ? <StatePanel tone="error" title="Validation evidence unavailable" message={results.error.message} action={<button className="button button-secondary" onClick={() => void results.refetch()}>Retry</button>} /> : null}
    {results.data && results.data.total === 0 ? <StatePanel tone="empty" title="No per-check results were persisted for this run" message="A successful pipeline stage does not mean every check passed. This run has stage and row evidence, but no individual validator results." action={<Link className="button button-secondary" to={`/runs/${encodeURIComponent(runId)}`}>Inspect run evidence</Link>} /> : null}
    {results.data && results.data.total > 0 ? <section className="surface validation-latest-surface" aria-labelledby="validation-latest-heading">
      <div className="section-header"><div><p className="eyebrow">LATEST EXECUTION</p><h2 id="validation-latest-heading">Saved check outcomes</h2><p className="section-description">Run <code>{runId}</code> · attempt <code>{results.data.attempt_id}</code></p></div><Link className="text-link" to="/validation/results">View all results <span aria-hidden="true">→</span></Link></div>
      <div className="validation-summary-strip"><span><strong>{formatNumber(summary?.passed ?? 0)}</strong> passed</span><span><strong>{formatNumber(summary?.failed ?? 0)}</strong> failed</span><span><strong>{formatNumber(summary?.warnings ?? 0)}</strong> warnings</span><span><strong>{formatNumber(summary?.errors ?? 0)}</strong> errors</span></div>
    </section> : null}
    <section className="surface validation-analytics-surface" aria-labelledby="validation-analytics-heading">
      <div className="section-header"><div><p className="eyebrow">PERSISTED HISTORY</p><h2 id="validation-analytics-heading">Validation trends</h2><p className="section-description">Aggregates use stored check results. Quality scores appear only for attempts that meet the documented evidence threshold.</p></div><label className="select-field"><span>Time window</span><select value={days} onChange={(event) => setDays(Number(event.currentTarget.value))}><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select></label></div>
      {analytics.isPending ? <StatePanel tone="loading" title="Loading validation trends" message="Aggregating persisted validation results." compact /> : null}
      {analytics.isError ? <StatePanel tone="error" title="Validation trends unavailable" message={analytics.error.message} action={<button className="button button-secondary" onClick={() => void analytics.refetch()}>Retry</button>} compact /> : null}
      {analytics.data ? analytics.data.total_results === 0 ? <StatePanel tone="empty" title="No persisted validation results in this window" message="Trend metrics appear after runs persist individual check outcomes." compact /> : <>
        <div className="validation-summary-strip"><span><strong>{formatNumber(analytics.data.total_results)}</strong> results</span><span><strong>{formatNumber(failureCount)}</strong> failures</span><span><strong>{formatNumber(analytics.data.status_counts.WARNING ?? 0)}</strong> warnings</span><span><strong>{formatNumber(analytics.data.requires_configuration)}</strong> need configuration</span><span><strong>{formatNumber(analytics.data.critical_failures)}</strong> critical failures</span><span><strong>{analytics.data.average_execution_time_ms === null ? "—" : `${formatNumber(analytics.data.average_execution_time_ms)} ms`}</strong> average check duration</span></div>
        <div className="validation-analytics-grid">
          <section className="validation-analytics-panel" aria-labelledby="failure-category-heading"><h3 id="failure-category-heading">Failures by category</h3>{analytics.data.failures_by_category.length ? <ul className="validation-bar-list">{analytics.data.failures_by_category.map((item) => <li key={item.category}><span>{item.category}</span><span className="validation-bar-track" aria-hidden="true"><span style={{ width: `${item.failures / maximumCategoryFailures * 100}%` }} /></span><strong>{formatNumber(item.failures)}</strong></li>)}</ul> : <p className="inline-note">No FAIL or ERROR results were recorded in this window.</p>}</section>
          <section className="validation-analytics-panel" aria-labelledby="frequent-failures-heading"><h3 id="frequent-failures-heading">Most frequently failing checks</h3>{analytics.data.most_failing_checks.length ? <ul className="validation-failure-list">{analytics.data.most_failing_checks.map((item) => <li key={item.validation_id}><span><code>{item.validation_id}</code><small>{item.name} · {item.category}</small></span><strong>{formatNumber(item.failures)}</strong></li>)}</ul> : <p className="inline-note">No FAIL or ERROR results were recorded in this window.</p>}</section>
          <section className="validation-analytics-panel" aria-labelledby="daily-validation-heading"><h3 id="daily-validation-heading">Daily execution trend</h3><div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Date (UTC)</th><th scope="col">Executions</th><th scope="col">Failures</th><th scope="col">Warnings</th></tr></thead><tbody>{analytics.data.daily_trend.map((item) => <tr key={item.date}><td>{item.date}</td><td className="numeric-cell">{formatNumber(item.executions)}</td><td className="numeric-cell">{formatNumber(item.failures)}</td><td className="numeric-cell">{formatNumber(item.warnings)}</td></tr>)}</tbody></table></div></section>
          <section className="validation-analytics-panel" aria-labelledby="quality-trend-heading"><h3 id="quality-trend-heading">Quality score trend</h3>{analytics.data.quality_trend.length ? <ul className="validation-failure-list">{analytics.data.quality_trend.map((item) => <li key={item.attempt_id}><span><Link to={`/validation/results?run_id=${encodeURIComponent(item.run_id)}&attempt_id=${encodeURIComponent(item.attempt_id)}`}>{shortId(item.run_id)}</Link><small>{new Date(item.created_at).toLocaleString()} · {item.coverage_percent.toFixed(1)}% check coverage</small></span><strong>{item.score.toFixed(2)}</strong></li>)}</ul> : <p className="inline-note">No attempts in this window met the scoring sufficiency threshold. {analytics.data.quality_trend_insufficient_attempts ? `${analytics.data.quality_trend_insufficient_attempts} attempt(s) had insufficient evidence.` : ""}</p>}<p className="inline-note">{analytics.data.scope}</p></section>
        </div>
      </> : null}
    </section>
  </div>;
}
