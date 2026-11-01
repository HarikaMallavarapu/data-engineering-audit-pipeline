import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { StatusBadge } from "../../components/common/StatusBadge";
import { getQuarantine, getRun, getRunQualityScore, listRuns } from "../../services/runService";
import { formatNumber, shortId } from "../../utils/format";

interface RunProfile {
  columns?: string[];
  row_count?: number;
  null_counts?: Record<string, number>;
  inferred_types?: Record<string, string>;
}

export function QualityPage() {
  const [selectedRunId, setSelectedRunId] = useState("");
  const runs = useQuery({ queryKey: ["runs", "quality", 100], queryFn: () => listRuns(1, 100) });
  const runId = selectedRunId || runs.data?.items[0]?.run_id || "";
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId), enabled: Boolean(runId) });
  const qualityScore = useQuery({ queryKey: ["quality-score", runId], queryFn: () => getRunQualityScore(runId), enabled: Boolean(runId && run.data && !["RUNNING", "PENDING"].includes(run.data.status)) });
  const rejected = useQuery({ queryKey: ["quarantine", runId, "quality"], queryFn: () => getQuarantine({ runId, page: 1, pageSize: 25 }), enabled: Boolean(runId && run.data && run.data.status !== "RUNNING" && run.data.status !== "PENDING") });
  const profile = run.data?.profile as RunProfile | undefined;
  const columns = profile?.columns ?? [];
  const rowCount = profile?.row_count ?? 0;
  const validationStages = run.data?.stages.filter((stage) => stage.stage_name === "validation") ?? [];

  return <div className="page-content">
    <PageHeader eyebrow="VALIDATION WORKSPACE" title="Data quality" description="Inspect persisted file profiles, validation-stage results and rejected row evidence." actions={runId ? <Link className="button button-secondary" to={`/runs/${encodeURIComponent(runId)}`}>Open selected run</Link> : undefined} />
    <section className="surface profile-surface" aria-labelledby="profile-heading">
      <div className="section-header"><div><p className="eyebrow">RUN SELECTION</p><h2 id="profile-heading">Profile and validation evidence</h2></div>
        <label className="select-field run-selector"><span>Pipeline run</span><select value={runId} onChange={(event) => setSelectedRunId(event.currentTarget.value)} disabled={!runs.data?.items.length}><option value="">Select a run</option>{runs.data?.items.map((item) => <option key={item.run_id} value={item.run_id}>{shortId(item.run_id)} · {item.status}</option>)}</select></label>
      </div>
      {runs.isPending ? <StatePanel tone="loading" title="Loading run choices" message="Fetching persisted runs from the backend." /> : null}
      {runs.isError ? <StatePanel tone="error" title="Run history unavailable" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} /> : null}
      {runs.data?.items.length === 0 ? <StatePanel tone="empty" title="No profile evidence yet" message="A CSV run creates a stored file profile and validation-stage results." action={<Link className="button button-secondary" to="/sources">Register a source</Link>} /> : null}
      {run.isPending && runId ? <StatePanel tone="loading" title="Loading profile" message="Reading persisted profiling and validation evidence." /> : null}
      {run.isError ? <StatePanel tone="error" title="Profile could not be loaded" message={run.error.message} /> : null}
      {run.data ? <>
        <div className="profile-run-banner"><span><strong>{shortId(run.data.run_id)}</strong><small>{formatNumber(rowCount)} source rows · profile from backend ingestion</small></span><StatusBadge status={run.data.status} size="small" /></div>
        {columns.length > 0 ? <div className="table-scroll" role="region" aria-label="Column profile" tabIndex={0}><table className="data-table"><caption className="visually-hidden">Column-level profile returned by the pipeline engine</caption><thead><tr><th scope="col">Column</th><th scope="col">Detected type</th><th scope="col">Null values</th><th scope="col">Completeness</th></tr></thead><tbody>{columns.map((column) => {
          const nullCount = profile?.null_counts?.[column] ?? 0;
          const completeness = rowCount > 0 ? Math.max(0, Math.min(100, 100 * (rowCount - nullCount) / rowCount)) : null;
          return <tr key={column}><td><strong>{column}</strong></td><td><span className="type-badge">{profile?.inferred_types?.[column] ?? "unknown"}</span></td><td className="numeric-cell">{formatNumber(nullCount)}</td><td><div className="completeness-cell"><span>{completeness === null ? "—" : `${completeness.toFixed(1)}%`}</span>{completeness !== null ? <span className="completeness-track" aria-hidden="true"><span style={{ width: `${completeness}%` }} /></span> : null}</div></td></tr>;
        })}</tbody></table></div> : <StatePanel tone="info" title="No column profile is available" message="The selected run does not contain stored profile columns." compact />}

        <div className="quality-evidence-grid">
          <div className="evidence-note"><p className="eyebrow">VALIDATION STAGE</p><h3>{validationStages.length ? `${validationStages.length} persisted stage record${validationStages.length === 1 ? "" : "s"}` : "No validation stage evidence"}</h3>{validationStages.map((stage) => <div className="validation-stage-row" key={stage.attempt_id}><StatusBadge status={stage.status} size="small" /><span>{formatNumber(stage.input_count)} in</span><span>{formatNumber(stage.output_count)} out</span><span>{formatNumber(stage.reject_count)} rejected</span></div>)}<Link className="text-link" to={`/runs/${encodeURIComponent(runId)}`}>Inspect stage timeline <span aria-hidden="true">→</span></Link></div>
          <div className="evidence-note quality-score-note"><p className="eyebrow">PERSISTED CHECK SCORE</p>{qualityScore.isPending ? <h3>Calculating from stored checks</h3> : qualityScore.isError ? <><h3>Score unavailable</h3><p>{qualityScore.error.message}</p></> : qualityScore.data ? <><h3>{qualityScore.data.score === null ? "Not enough validation evidence" : `${qualityScore.data.score.toFixed(2)} / 100`}</h3><p>{qualityScore.data.coverage_percent === null ? "No eligible checks were recorded." : `${qualityScore.data.coverage_percent.toFixed(1)}% execution coverage · ${qualityScore.data.executed_checks} of ${qualityScore.data.applicable_checks} eligible checks`}</p>{qualityScore.data.insufficiency_reasons.map((reason) => <p className="inline-note" key={reason}>{reason}</p>)}{qualityScore.data.catalog_coverage_percent === null ? <p className="inline-note">Catalog-wide coverage is unavailable. This score covers only the persisted runtime checks shown for this attempt.</p> : <p className="inline-note">Catalog coverage: {qualityScore.data.catalog_coverage_percent.toFixed(1)}% of {qualityScore.data.catalog_eligible_checks} enabled implemented definitions.</p>}<details><summary>Scoring method</summary><pre>{JSON.stringify(qualityScore.data.methodology, null, 2)}</pre></details></> : <h3>No score evidence</h3>}</div>
        </div>
        <div className="section-header quality-rejection-header"><div><p className="eyebrow">RULE OUTCOMES</p><h2>Rejected rows</h2></div><Link className="text-link" to={`/quarantine?run_id=${encodeURIComponent(runId)}`}>Investigate quarantine <span aria-hidden="true">→</span></Link></div>
        {rejected.isPending ? <StatePanel tone="loading" title="Loading rule outcomes" message="Reading rejected rows for this run." compact /> : null}
        {rejected.isError ? <StatePanel tone="error" title="Rejection evidence unavailable" message={rejected.error.message} compact /> : null}
        {rejected.data?.total === 0 ? <StatePanel tone="empty" title="No rejected rows" message="The latest attempt returned no rejected source rows." compact /> : null}
        {rejected.data && rejected.data.total > 0 ? <ul className="reason-list">{rejected.data.items.map((item) => <li key={`${item.attempt_id}-${item.source_row_number}`}><span><strong>{item.reason_code}</strong><small>Source row {item.source_row_number}</small></span><span>{item.rejection_reasons.join(", ")}</span></li>)}</ul> : null}
      </> : null}
    </section>
  </div>;
}
