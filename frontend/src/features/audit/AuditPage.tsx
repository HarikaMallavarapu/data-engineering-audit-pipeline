import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { getAudit } from "../../services/runService";
import { formatDate, shortId } from "../../utils/format";

const PAGE_SIZE = 25;

export function AuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialRunId = searchParams.get("run_id") ?? "";
  const [runInput, setRunInput] = useState(initialRunId);
  const [runId, setRunId] = useState(initialRunId);
  const [page, setPage] = useState(1);
  const events = useQuery({ queryKey: ["audit", runId, page, PAGE_SIZE], queryFn: () => getAudit({ runId: runId || undefined, page, pageSize: PAGE_SIZE }) });

  function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextRunId = runInput.trim();
    setRunId(nextRunId);
    setPage(1);
    setSearchParams(nextRunId ? { run_id: nextRunId } : {});
  }

  return <div className="page-content">
    <PageHeader eyebrow="COMPLIANCE EVIDENCE" title="Audit log" description="Browse append-only backend events with their stored run and event evidence." />
    <section className="surface table-surface" aria-labelledby="audit-heading">
      <div className="section-header"><div><p className="eyebrow">SYSTEM HISTORY</p><h2 id="audit-heading">Audit events</h2></div><span className="data-window-label">{events.data ? `${events.data.total.toLocaleString()} total` : "Persisted API events"}</span></div>
      <form className="table-toolbar filter-form" onSubmit={applyFilter}>
        <label className="search-field"><span className="visually-hidden">Filter audit by run ID</span><input value={runInput} onChange={(event) => setRunInput(event.currentTarget.value)} placeholder="Filter by run ID" /></label>
        <button className="button button-secondary" type="submit">Apply filter</button>
        {runId ? <button className="button button-quiet" type="button" onClick={() => { setRunInput(""); setRunId(""); setPage(1); setSearchParams({}); }}>Clear</button> : null}
      </form>
      {events.isPending ? <StatePanel tone="loading" title="Loading audit events" message="Retrieving the selected page from the API." /> : null}
      {events.isError ? <StatePanel tone="error" title="Audit history unavailable" message={events.error.message} action={<button className="button button-secondary" onClick={() => void events.refetch()}>Retry request</button>} /> : null}
      {events.data?.total === 0 ? <StatePanel tone="empty" title="No audit events returned" message="Persisted pipeline events will appear here after a source or run action." /> : null}
      {events.data && events.data.items.length > 0 ? <>
        <div className="table-scroll" role="region" aria-label="Append-only audit events" tabIndex={0}><table className="data-table"><caption className="visually-hidden">Persisted audit events</caption><thead><tr><th scope="col">Event</th><th scope="col">Run</th><th scope="col">Timestamp</th><th scope="col">Evidence</th></tr></thead><tbody>{events.data.items.map((event) => <tr key={event.audit_event_id}>
          <td><strong className="event-name">{event.event_type}</strong><span className="table-secondary">Event #{event.audit_event_id}</span></td>
          <td>{event.run_id ? <Link className="table-primary-link" to={`/runs/${encodeURIComponent(event.run_id)}`}>{shortId(event.run_id)}</Link> : <span className="table-secondary">System</span>}</td>
          <td>{formatDate(event.created_at)}</td>
          <td><details className="payload-details"><summary>Inspect event data</summary><pre>{JSON.stringify(event.event_data, null, 2)}</pre></details></td>
        </tr>)}</tbody></table></div>
        <Pagination page={page} pageSize={PAGE_SIZE} total={events.data.total} onPageChange={setPage} />
      </> : null}
    </section>
  </div>;
}
