import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, CircleAlert } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { getAudit, getDuplicates, getQuarantine, getReconciliation, getRun, retryRun } from "../../services/runService";
import { ApiClientError } from "../../services/api";
import { formatDate, formatNumber, shortId } from "../../utils/format";
import { RunDetails } from "./RunDetails";

const PAGE_SIZE = 25;
const terminal = new Set(["SUCCESS", "PARTIAL", "FAILED", "CANCELLED"]);

function isCode(error: unknown, code: string): boolean {
  return error instanceof ApiClientError && error.code === code;
}

export function RunDetailsPage() {
  const { runId = "" } = useParams();
  const queryClient = useQueryClient();
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId), enabled: Boolean(runId), refetchInterval: (query) => query.state.data?.status === "RUNNING" ? 2_000 : false });
  const isTerminal = Boolean(run.data && terminal.has(run.data.status));
  const quarantine = useQuery({ queryKey: ["quarantine", runId, 1], queryFn: () => getQuarantine({ runId, page: 1, pageSize: PAGE_SIZE }), enabled: isTerminal });
  const duplicates = useQuery({ queryKey: ["duplicates", runId, 1], queryFn: () => getDuplicates({ runId, page: 1, pageSize: PAGE_SIZE }), enabled: isTerminal });
  const reconciliation = useQuery({ queryKey: ["reconciliation", runId], queryFn: () => getReconciliation(runId), enabled: isTerminal });
  const audit = useQuery({ queryKey: ["audit", runId, 1], queryFn: () => getAudit({ runId, page: 1, pageSize: PAGE_SIZE }), enabled: isTerminal });
  const retry = useMutation({
    mutationFn: () => retryRun(runId),
    onSuccess: async (updatedRun) => {
      queryClient.setQueryData(["run", runId], updatedRun);
      await queryClient.invalidateQueries({ queryKey: ["runs"] });
      await queryClient.invalidateQueries({ queryKey: ["run", runId] });
    },
  });

  return <div className="page-content">
    <PageHeader eyebrow="RUN INVESTIGATION" title="Persisted execution record" description="Inspect stage outcomes, row dispositions, reconciliation checks and append-only audit evidence." actions={<Link className="button button-secondary" to="/runs"><ArrowLeft size={15} aria-hidden="true" />Back to runs</Link>} />
    {run.isPending ? <StatePanel tone="loading" title="Loading run evidence" message="Retrieving the selected run from the API." /> : null}
    {run.isError ? <StatePanel tone="error" title="Run evidence unavailable" message={run.error.message} action={<button className="button button-secondary" onClick={() => void run.refetch()}>Retry request</button>} /> : null}
    {run.data ? <>
      <RunDetails run={run.data} retrying={retry.isPending} retryError={retry.error?.message ?? null} onRetry={() => retry.mutate()} />
      <div className="evidence-grid">
        <section className="surface evidence-surface" aria-labelledby="quarantine-heading">
          <div className="section-header"><div><p className="eyebrow">ROW DISPOSITION</p><h2 id="quarantine-heading">Rejected records</h2></div><Link className="text-link" to={`/quarantine?run_id=${encodeURIComponent(runId)}`}>Open quarantine <span aria-hidden="true">→</span></Link></div>
          {quarantine.isPending ? <StatePanel tone="loading" title="Loading rejected rows" message="Reading persisted quarantine records." compact /> : null}
          {quarantine.isError ? <StatePanel tone="error" title="Quarantine evidence unavailable" message={quarantine.error.message} compact /> : null}
          {quarantine.data?.total === 0 ? <StatePanel tone="empty" title="No rejected rows" message="All source rows passed the validation rules for this run." compact /> : null}
          {quarantine.data && quarantine.data.total > 0 ? <>
            <div className="table-scroll" role="region" aria-label="Rejected record evidence" tabIndex={0}><table className="data-table"><caption className="visually-hidden">Rejected rows for this run</caption><thead><tr><th scope="col">Source row</th><th scope="col">Transaction</th><th scope="col">Rule</th><th scope="col">Reason</th><th scope="col">Payload</th></tr></thead><tbody>{quarantine.data.items.map((row) => <tr key={`${row.attempt_id}-${row.source_row_number}`}><td>{row.source_row_number}</td><td>{String(row.original_payload.transaction_id ?? "—")}</td><td><code>{row.reason_code}</code></td><td>{row.rejection_reasons.join(", ")}</td><td><details className="payload-details"><summary>View</summary><pre>{JSON.stringify(row.original_payload, null, 2)}</pre></details></td></tr>)}</tbody></table></div>
            {quarantine.data.total > PAGE_SIZE ? <Link className="text-link evidence-more-link" to={`/quarantine?run_id=${encodeURIComponent(runId)}`}>View all {formatNumber(quarantine.data.total)} rejected rows</Link> : null}
          </> : null}
        </section>

        <section className="surface evidence-surface" aria-labelledby="duplicates-heading">
          <div className="section-header"><div><p className="eyebrow">DEDUPLICATION</p><h2 id="duplicates-heading">Duplicate records</h2></div><Link className="text-link" to={`/duplicates?run_id=${encodeURIComponent(runId)}`}>Open duplicates <span aria-hidden="true">→</span></Link></div>
          {duplicates.isPending ? <StatePanel tone="loading" title="Loading duplicates" message="Reading persisted duplicate classifications." compact /> : null}
          {duplicates.isError ? <StatePanel tone="error" title="Duplicate evidence unavailable" message={duplicates.error.message} compact /> : null}
          {duplicates.data?.total === 0 ? <StatePanel tone="empty" title="No duplicates detected" message="No valid records matched this run’s configured duplicate key." compact /> : null}
          {duplicates.data && duplicates.data.total > 0 ? <div className="table-scroll" role="region" aria-label="Duplicate record evidence" tabIndex={0}><table className="data-table"><caption className="visually-hidden">Duplicate rows for this run</caption><thead><tr><th scope="col">Source row</th><th scope="col">First accepted row</th><th scope="col">Duplicate key</th><th scope="col">Attempt</th></tr></thead><tbody>{duplicates.data.items.map((row) => <tr key={`${row.attempt_id}-${row.source_row_number}`}><td>{row.source_row_number}</td><td>{row.duplicate_of_row_number}</td><td><code>{row.duplicate_key}</code></td><td>{row.attempt_id.split("_attempt_").at(-1)}</td></tr>)}</tbody></table></div> : null}
        </section>
      </div>

      <div className="evidence-grid">
        <section className="surface evidence-surface" aria-labelledby="run-reconciliation-heading">
          <div className="section-header"><div><p className="eyebrow">{run.data?.pipeline_id === "general-tabular" ? "COUNT CHECKS" : "COUNT AND AMOUNT CHECKS"}</p><h2 id="run-reconciliation-heading">Reconciliation</h2></div>{reconciliation.data ? <span className={`reconciliation-status ${reconciliation.data.balanced ? "balanced" : "unbalanced"}`}>{reconciliation.data.balanced ? "Balanced" : "Mismatch"}</span> : null}</div>
          {reconciliation.isPending ? <StatePanel tone="loading" title="Loading reconciliation" message="Reading persisted reconciliation checks." compact /> : null}
          {reconciliation.isError && !isCode(reconciliation.error, "reconciliation_not_found") ? <StatePanel tone="error" title="Reconciliation unavailable" message={reconciliation.error.message} compact /> : null}
          {isCode(reconciliation.error, "reconciliation_not_found") ? <StatePanel tone="info" title="No reconciliation result" message="The API has no reconciliation record for this run." compact /> : null}
          {reconciliation.data ? <>
            <div className="reconciliation-counts">{Object.entries(reconciliation.data.counts).map(([name, count]) => <div key={name}><span>{name}</span><strong>{formatNumber(count)}</strong></div>)}</div>
            <div className="check-list">{Object.entries(reconciliation.data.checks).map(([name, passed]) => <div className="check-row" key={name}><span className={`check-icon ${passed ? "passed" : "failed"}`} aria-hidden="true">{passed ? <Check size={12} /> : <CircleAlert size={12} />}</span><span>{name.replaceAll("_", " ")}</span><strong>{passed ? "Pass" : "Fail"}</strong></div>)}</div>
            {run.data?.pipeline_id === "general-tabular" ? <p className="inline-note">Currency amount reconciliation is not configured for this generic dataset. Count balance and published row counts are checked.</p> : <div className="currency-comparison"><CurrencyAmounts title="Accepted totals" amounts={reconciliation.data.accepted_amounts_by_currency} /><CurrencyAmounts title="Published totals" amounts={reconciliation.data.published_amounts_by_currency} /></div>}
          </> : null}
        </section>

        <section className="surface evidence-surface" aria-labelledby="run-audit-heading">
          <div className="section-header"><div><p className="eyebrow">APPEND-ONLY HISTORY</p><h2 id="run-audit-heading">Audit events</h2></div><Link className="text-link" to={`/audit?run_id=${encodeURIComponent(runId)}`}>Open audit log <span aria-hidden="true">→</span></Link></div>
          {audit.isPending ? <StatePanel tone="loading" title="Loading audit events" message="Reading persisted audit records." compact /> : null}
          {audit.isError ? <StatePanel tone="error" title="Audit evidence unavailable" message={audit.error.message} compact /> : null}
          {audit.data?.items.length === 0 ? <StatePanel tone="empty" title="No audit events returned" message="The audit endpoint returned no event records for this run." compact /> : null}
          {audit.data && audit.data.items.length > 0 ? <ol className="audit-compact-list">{audit.data.items.slice(0, 6).map((event) => <li key={event.audit_event_id}><span className="audit-marker" aria-hidden="true" /><div><strong>{event.event_type.replaceAll(".", " · ")}</strong><small>{formatDate(event.created_at)}</small><code>{shortId(JSON.stringify(event.event_data), 64)}</code></div></li>)}</ol> : null}
        </section>
      </div>
    </> : null}
  </div>;
}

function CurrencyAmounts({ title, amounts }: { title: string; amounts: Record<string, string> }) {
  const entries = Object.entries(amounts);
  return <div className="currency-amounts"><h3>{title}</h3>{entries.length ? entries.map(([currency, amount]) => <p key={currency}><span>{currency}</span><strong>{amount}</strong></p>) : <p className="inline-note">No published totals recorded.</p>}</div>;
}
