import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";

import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { RunTable } from "../../components/tables/RunTable";
import { listRuns } from "../../services/runService";

export function IncidentsPage() {
  const runs = useQuery({ queryKey: ["runs", "incident-evidence", 100], queryFn: () => listRuns(1, 100) });
  const outcomes = runs.data?.items.filter((run) => run.status === "FAILED" || run.status === "PARTIAL") ?? [];
  return <div className="page-content">
    <PageHeader eyebrow="OPERATIONAL EXCEPTIONS" title="Failure outcomes" description="Review persisted failed or partial run outcomes without inventing incident records or severity." />
    <StatePanel tone="info" title="Dedicated incident management is not configured" message="The backend currently exposes run outcomes but no incident entity, severity, assignment or resolution workflow. The list below contains only real FAILED and PARTIAL run records." />
    <section className="surface table-surface" aria-labelledby="failure-outcomes-heading">
      <div className="section-header"><div><p className="eyebrow">RUN EVIDENCE · LATEST 100</p><h2 id="failure-outcomes-heading">Failure and partial outcomes</h2></div><span className="section-icon section-icon-amber" aria-hidden="true"><AlertTriangle size={16} /></span></div>
      {runs.isPending ? <StatePanel tone="loading" title="Loading run outcomes" message="Checking persisted run statuses." /> : null}
      {runs.isError ? <StatePanel tone="error" title="Run outcomes unavailable" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry</button>} /> : null}
      {runs.data && outcomes.length === 0 ? <StatePanel tone="empty" title="No failure outcomes in this window" message="No FAILED or PARTIAL records were returned among the latest runs." /> : null}
      {runs.data && outcomes.length > 0 ? <RunTable runs={outcomes} caption="Latest failed and partial pipeline run records" /> : null}
    </section>
  </div>;
}
