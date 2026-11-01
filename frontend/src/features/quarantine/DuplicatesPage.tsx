import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { getDuplicates } from "../../services/runService";
import { formatNumber, shortId } from "../../utils/format";

const PAGE_SIZE = 25;

export function DuplicatesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialRunId = searchParams.get("run_id") ?? "";
  const [runInput, setRunInput] = useState(initialRunId);
  const [runId, setRunId] = useState(initialRunId);
  const [page, setPage] = useState(1);
  const rows = useQuery({ queryKey: ["duplicates", runId, page, PAGE_SIZE], queryFn: () => getDuplicates({ runId: runId || undefined, page, pageSize: PAGE_SIZE }) });

  function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextRunId = runInput.trim();
    setRunId(nextRunId);
    setPage(1);
    setSearchParams(nextRunId ? { run_id: nextRunId } : {});
  }

  return <div className="page-content">
    <PageHeader eyebrow="ROW INVESTIGATION" title="Duplicate records" description="Inspect deduplication outcomes and the accepted source row that each duplicate matched." />
    <section className="surface table-surface" aria-labelledby="duplicates-table-heading">
      <div className="section-header"><div><p className="eyebrow">RECORDED OUTCOMES</p><h2 id="duplicates-table-heading">Duplicate evidence</h2></div><span className="data-window-label">{rows.data ? `${formatNumber(rows.data.total)} records` : "Latest attempt per run"}</span></div>
      <form className="table-toolbar filter-form" onSubmit={applyFilter}>
        <label className="search-field"><span className="visually-hidden">Filter by run ID</span><input value={runInput} onChange={(event) => setRunInput(event.currentTarget.value)} placeholder="Filter by run ID" /></label>
        <button className="button button-secondary" type="submit">Apply filter</button>
        {runId ? <button className="button button-quiet" type="button" onClick={() => { setRunInput(""); setRunId(""); setPage(1); setSearchParams({}); }}>Clear</button> : null}
        <span className="filter-scope">Unfiltered results use the latest attempt for each run</span>
      </form>
      {rows.isPending ? <StatePanel tone="loading" title="Loading duplicate records" message="Retrieving persisted duplicate classifications." /> : null}
      {rows.isError ? <StatePanel tone="error" title="Duplicates could not be loaded" message={rows.error.message} action={<button className="button button-secondary" onClick={() => void rows.refetch()}>Retry request</button>} /> : null}
      {rows.data?.total === 0 ? <StatePanel tone="empty" title="No duplicates found" message={runId ? "This run has no duplicate rows in the latest attempt." : "Duplicate outcomes will appear here when records match the pipeline's persisted deduplication rule."} /> : null}
      {rows.data && rows.data.items.length > 0 ? <>
        <div className="table-scroll" role="region" aria-label="Duplicate records" tabIndex={0}><table className="data-table"><caption className="visually-hidden">Persisted duplicate classifications</caption><thead><tr><th scope="col">Run</th><th scope="col">Source row</th><th scope="col">Accepted row</th><th scope="col">Duplicate key</th><th scope="col">Attempt</th></tr></thead><tbody>{rows.data.items.map((row) => <tr key={`${row.attempt_id}-${row.source_row_number}`}>
          <td><Link className="table-primary-link" to={`/runs/${encodeURIComponent(row.run_id)}`}>{shortId(row.run_id)}</Link></td><td className="numeric-cell">{row.source_row_number}</td><td className="numeric-cell">{row.duplicate_of_row_number}</td><td><code>{row.duplicate_key}</code></td><td>{row.attempt_id.split("_attempt_").at(-1)}</td>
        </tr>)}</tbody></table></div>
        <Pagination page={page} pageSize={PAGE_SIZE} total={rows.data.total} onPageChange={setPage} />
      </> : null}
    </section>
  </div>;
}
