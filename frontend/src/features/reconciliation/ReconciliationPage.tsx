import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, CircleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { getReconciliation, listRuns } from "../../services/runService";
import { ApiClientError } from "../../services/api";
import { formatNumber, shortId } from "../../utils/format";

export function ReconciliationPage() {
  const [selectedRunId, setSelectedRunId] = useState("");
  const runs = useQuery({ queryKey: ["runs", "reconciliation", 100], queryFn: () => listRuns(1, 100) });
  const runId = selectedRunId || runs.data?.items[0]?.run_id || "";
  const run = runs.data?.items.find((item) => item.run_id === runId);
  const result = useQuery({ queryKey: ["reconciliation", runId], queryFn: () => getReconciliation(runId), enabled: Boolean(runId && run && ["SUCCESS", "PARTIAL", "FAILED", "CANCELLED"].includes(run.status)) });
  const isMissing = result.error instanceof ApiClientError && result.error.code === "reconciliation_not_found";

  return <div className="page-content">
    <PageHeader eyebrow="COUNT AND AMOUNT CONTROL" title="Reconciliation" description="Compare persisted input dispositions, published rows and per-currency aggregates." />
    <section className="surface reconciliation-surface" aria-labelledby="reconciliation-heading">
      <div className="section-header"><div><p className="eyebrow">RUN RECONCILIATION</p><h2 id="reconciliation-heading">Select an execution</h2></div>
        <label className="select-field run-selector"><span>Pipeline run</span><select value={runId} onChange={(event) => setSelectedRunId(event.currentTarget.value)} disabled={!runs.data?.items.length}><option value="">Select a run</option>{runs.data?.items.map((item) => <option key={item.run_id} value={item.run_id}>{shortId(item.run_id)} · {item.status}</option>)}</select></label>
      </div>
      {runs.isPending ? <StatePanel tone="loading" title="Loading runs" message="Retrieving executions that can be reconciled." /> : null}
      {runs.isError ? <StatePanel tone="error" title="Run list unavailable" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} /> : null}
      {runs.data?.items.length === 0 ? <StatePanel tone="empty" title="No executions to reconcile" message="Reconciliation becomes available after the first persisted pipeline run." action={<Link className="button button-secondary" to="/sources">Register a source</Link>} /> : null}
      {run && ["PENDING", "RUNNING"].includes(run.status) ? <StatePanel tone="loading" title="Run is still processing" message="Reconciliation is loaded after the backend records a terminal run result." /> : null}
      {result.isPending && run && !["PENDING", "RUNNING"].includes(run.status) ? <StatePanel tone="loading" title="Loading reconciliation" message="Reading persisted count and amount checks." /> : null}
      {result.isError && !isMissing ? <StatePanel tone="error" title="Reconciliation could not be loaded" message={result.error.message} action={<button className="button button-secondary" onClick={() => void result.refetch()}>Retry request</button>} /> : null}
      {isMissing ? <StatePanel tone="info" title="No reconciliation record" message="The API returned no saved reconciliation for this execution." /> : null}
      {result.data ? <>
        <div className={`reconciliation-banner ${result.data.balanced ? "balanced" : "unbalanced"}`}><span className="reconciliation-banner-icon" aria-hidden="true">{result.data.balanced ? <Check size={19} /> : <CircleAlert size={19} />}</span><div><strong>{result.data.balanced ? "All reconciliation checks passed" : "Reconciliation mismatch detected"}</strong><small>Run <Link to={`/runs/${encodeURIComponent(runId)}`}>{runId}</Link></small></div></div>
        <div className="reconciliation-count-grid">{Object.entries(result.data.counts).map(([label, value]) => <div className="reconciliation-count" key={label}><span>{label}</span><strong>{formatNumber(value)}</strong></div>)}</div>
        <div className="reconciliation-detail-grid">
          <section className="reconciliation-subsection" aria-labelledby="check-heading"><h3 id="check-heading">Invariant checks</h3><ul className="check-list">{Object.entries(result.data.checks).map(([name, passed]) => <li className="check-row" key={name}><span className={`check-icon ${passed ? "passed" : "failed"}`} aria-hidden="true">{passed ? <Check size={12} /> : <CircleAlert size={12} />}</span><span>{name.replaceAll("_", " ")}</span><strong>{passed ? "Pass" : "Fail"}</strong></li>)}</ul></section>
          <section className="reconciliation-subsection" aria-labelledby="amount-heading"><h3 id="amount-heading">Currency totals</h3><div className="currency-table-wrap"><table className="data-table"><caption className="visually-hidden">Accepted and published amounts grouped by currency</caption><thead><tr><th scope="col">Currency</th><th scope="col">Accepted</th><th scope="col">Published</th><th scope="col">Variance</th></tr></thead><tbody>{[...new Set([...Object.keys(result.data.accepted_amounts_by_currency), ...Object.keys(result.data.published_amounts_by_currency)])].map((currency) => {
            const accepted = Number(result.data!.accepted_amounts_by_currency[currency] ?? 0);
            const published = Number(result.data!.published_amounts_by_currency[currency] ?? 0);
            const variance = published - accepted;
            return <tr key={currency}><td><strong>{currency}</strong></td><td className="numeric-cell">{result.data!.accepted_amounts_by_currency[currency] ?? "0.00"}</td><td className="numeric-cell">{result.data!.published_amounts_by_currency[currency] ?? "0.00"}</td><td className={`numeric-cell ${variance === 0 ? "variance-zero" : "variance-nonzero"}`}>{variance.toFixed(2)}</td></tr>;
          })}</tbody></table></div></section>
        </div>
        <div className="reconciliation-footnote"><ArrowRight size={14} aria-hidden="true" /><p>Counts and currency totals are read from the persisted reconciliation response. Variance is displayed as published minus accepted from those response totals.</p></div>
      </> : null}
    </section>
  </div>;
}
