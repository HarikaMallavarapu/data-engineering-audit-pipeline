import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { getQuarantine } from "../../services/runService";
import { formatNumber, shortId } from "../../utils/format";

const PAGE_SIZE = 25;

export function QuarantinePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialRunId = searchParams.get("run_id") ?? "";
  const [runInput, setRunInput] = useState(initialRunId);
  const [runId, setRunId] = useState(initialRunId);
  const [page, setPage] = useState(1);
  const rows = useQuery({ queryKey: ["quarantine", runId, page, PAGE_SIZE], queryFn: () => getQuarantine({ runId: runId || undefined, page, pageSize: PAGE_SIZE }) });

  function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextRunId = runInput.trim();
    setRunId(nextRunId);
    setPage(1);
    setSearchParams(nextRunId ? { run_id: nextRunId } : {});
  }

  return <div className="page-content">
    <PageHeader eyebrow="ROW INVESTIGATION" title="Quarantine" description="Review original rejected records, source row identity and persisted rule reasons." />
    <section className="surface table-surface" aria-labelledby="quarantine-table-heading">
      <div className="section-header"><div><p className="eyebrow">REJECTED ROWS</p><h2 id="quarantine-table-heading">Quarantine evidence</h2></div><span className="data-window-label">{rows.data ? `${formatNumber(rows.data.total)} records` : "Latest attempt per run"}</span></div>
      <form className="table-toolbar filter-form" onSubmit={applyFilter}>
        <label className="search-field"><span className="visually-hidden">Filter by run ID</span><input value={runInput} onChange={(event) => setRunInput(event.currentTarget.value)} placeholder="Filter by run ID" /></label>
        <button className="button button-secondary" type="submit">Apply filter</button>
        {runId ? <button className="button button-quiet" type="button" onClick={() => { setRunInput(""); setRunId(""); setPage(1); setSearchParams({}); }}>Clear</button> : null}
        <span className="filter-scope">Unfiltered results use the latest attempt for each run</span>
      </form>
      {rows.isPending ? <StatePanel tone="loading" title="Loading rejected records" message="Retrieving persisted quarantine rows." /> : null}
      {rows.isError ? <StatePanel tone="error" title="Quarantine could not be loaded" message={rows.error.message} action={<button className="button button-secondary" onClick={() => void rows.refetch()}>Retry request</button>} /> : null}
      {rows.data?.total === 0 ? <StatePanel tone="empty" title="No rejected rows found" message={runId ? "This run has no rejected rows in the latest attempt." : "Rejected records will appear here after a run records validation failures."} /> : null}
      {rows.data && rows.data.items.length > 0 ? <>
        <div className="table-scroll" role="region" aria-label="Quarantine records" tabIndex={0}><table className="data-table"><caption className="visually-hidden">Persisted rejected source records</caption><thead><tr><th scope="col">Run</th><th scope="col">Source row</th><th scope="col">Rule</th><th scope="col">Reason</th><th scope="col">Transaction</th><th scope="col">Original payload</th></tr></thead><tbody>{rows.data.items.map((row) => <tr key={`${row.attempt_id}-${row.source_row_number}`}>
          <td><Link className="table-primary-link" to={`/runs/${encodeURIComponent(row.attempt_id.split("_attempt_")[0])}`}>{shortId(row.attempt_id.split("_attempt_")[0])}</Link><span className="table-secondary">Attempt {row.attempt_id.split("_attempt_").at(-1)}</span></td>
          <td className="numeric-cell">{row.source_row_number}</td><td><code>{row.reason_code}</code></td><td>{row.rejection_reasons.join(", ")}</td><td>{String(row.original_payload.transaction_id ?? "—")}</td>
          <td><details className="payload-details"><summary>Inspect</summary><pre>{JSON.stringify(row.original_payload, null, 2)}</pre></details></td>
        </tr>)}</tbody></table></div>
        <Pagination page={page} pageSize={PAGE_SIZE} total={rows.data.total} onPageChange={setPage} />
      </> : null}
    </section>
  </div>;
}
