import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { RunTable } from "../../components/tables/RunTable";
import { listRuns } from "../../services/runService";

const PAGE_SIZE = 25;
const statuses = ["ALL", "PENDING", "RUNNING", "SUCCESS", "PARTIAL", "FAILED", "CANCELLED"] as const;
const dateWindows = [0, 1, 7, 30] as const;

export function RunsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<(typeof statuses)[number]>("ALL");
  const [dateWindow, setDateWindow] = useState<(typeof dateWindows)[number]>(0);
  const runs = useQuery({ queryKey: ["runs", page, PAGE_SIZE], queryFn: () => listRuns(page, PAGE_SIZE), refetchInterval: 15_000 });
  const normalizedSearch = search.trim().toLowerCase();
  const dateCutoff = dateWindow ? Date.now() - dateWindow * 24 * 60 * 60 * 1000 : null;
  const filteredRuns = runs.data?.items.filter((run) => {
    const matchesSearch = !normalizedSearch || run.run_id.toLowerCase().includes(normalizedSearch) || run.pipeline_id.toLowerCase().includes(normalizedSearch);
    const createdAt = new Date(run.created_at).getTime();
    const matchesDate = dateCutoff === null || (Number.isFinite(createdAt) && createdAt >= dateCutoff);
    return matchesSearch && matchesDate && (status === "ALL" || run.status === status);
  }) ?? [];

  return (
    <div className="page-content">
      <PageHeader eyebrow="EXECUTION EXPLORER" title="Pipeline runs" description="Search persisted run IDs, review dispositions and open stage evidence." actions={<Link className="button button-primary" to="/sources">Start a new run</Link>} />
      <section className="surface table-surface runs-surface" aria-labelledby="runs-table-heading">
        <div className="section-header"><div><p className="eyebrow">EXECUTION HISTORY</p><h2 id="runs-table-heading">Run records</h2></div><span className="data-window-label">{runs.data ? `${runs.data.total.toLocaleString()} total` : "Live API data"}</span></div>
        <div className="table-toolbar">
          <label className="search-field"><Search size={16} aria-hidden="true" /><span className="visually-hidden">Search current run page</span><input type="search" value={search} onChange={(event) => { setSearch(event.currentTarget.value); setPage(1); }} placeholder="Search this page by run or pipeline" /></label>
          <label className="select-field"><span>Status</span><select value={status} onChange={(event) => { setStatus(event.currentTarget.value as (typeof statuses)[number]); setPage(1); }}>{statuses.map((value) => <option key={value} value={value}>{value === "ALL" ? "All statuses" : value}</option>)}</select></label>
          <label className="select-field"><span>Created</span><select aria-label="Filter runs by date" value={dateWindow} onChange={(event) => { setDateWindow(Number(event.currentTarget.value) as (typeof dateWindows)[number]); setPage(1); }}><option value={0}>Any date</option><option value={1}>Last 24 hours</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option></select></label>
          <span className="filter-scope">Filters apply to this API page</span>
        </div>
        {runs.isPending ? <StatePanel tone="loading" title="Loading run records" message="The backend is returning the requested page." /> : null}
        {runs.isError ? <StatePanel tone="error" title="Run history could not be loaded" message={runs.error.message} action={<button className="button button-secondary" onClick={() => void runs.refetch()}>Retry request</button>} /> : null}
        {runs.data && runs.data.items.length === 0 ? <StatePanel tone="empty" title="No runs are recorded" message="Register tabular CSV or JSON data to create the first pipeline run." action={<Link className="button button-secondary" to="/sources">Open source registry</Link>} /> : null}
        {runs.data && runs.data.items.length > 0 && filteredRuns.length === 0 ? <StatePanel tone="empty" title="No runs match these filters" message="Clear the search or choose another status. Filters cover only this API page." compact /> : null}
        {runs.data && filteredRuns.length > 0 ? <RunTable runs={filteredRuns} caption="Filtered pipeline runs on the current API page" /> : null}
        {runs.data && runs.data.total > PAGE_SIZE ? <Pagination page={page} pageSize={PAGE_SIZE} total={runs.data.total} onPageChange={setPage} /> : null}
      </section>
    </div>
  );
}
