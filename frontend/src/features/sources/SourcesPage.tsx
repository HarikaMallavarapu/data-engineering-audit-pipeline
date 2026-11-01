import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Database, FileSearch, FileUp, Play, RefreshCw, Search } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { listPipelines } from "../../services/pipelineService";
import { createRun } from "../../services/runService";
import { listSources, uploadSource } from "../../services/sourceService";
import type { SourceFile } from "../../services/sourceService";
import { formatBytes, formatDate } from "../../utils/format";
import { UploadPanel } from "./UploadPanel";

const SOURCE_PAGE_SIZE = 10;
type SourceSort = "newest" | "name" | "largest";

export function SourcesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SourceSort>("newest");
  const [page, setPage] = useState(1);
  const [selectedPipelineId, setSelectedPipelineId] = useState("general-tabular");
  const [inspectedSourceId, setInspectedSourceId] = useState<string | null>(null);
  const [uploadSuccessVersion, setUploadSuccessVersion] = useState(0);
  const sources = useQuery({ queryKey: ["sources"], queryFn: listSources });
  const pipelines = useQuery({ queryKey: ["pipelines"], queryFn: listPipelines });
  const effectivePipelineId = pipelines.data?.some((pipeline) => pipeline.pipeline_id === selectedPipelineId)
    ? selectedPipelineId
    : pipelines.data?.find((pipeline) => pipeline.pipeline_id === "general-tabular")?.pipeline_id
      ?? pipelines.data?.[0]?.pipeline_id;
  const uploadMutation = useMutation({
    mutationFn: uploadSource,
    onSuccess: async () => {
      setUploadSuccessVersion((version) => version + 1);
      await queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });
  const runMutation = useMutation({
    mutationFn: (source: SourceFile) => createRun(source.source_file_id, effectivePipelineId),
    onSuccess: async (run) => {
      await queryClient.invalidateQueries({ queryKey: ["runs"] });
      navigate(`/runs/${encodeURIComponent(run.run_id)}`);
    },
  });
  const normalizedSearch = search.trim().toLocaleLowerCase();
  const filteredSources = sources.data?.items.filter((source) =>
    !normalizedSearch || [source.original_filename, source.source_file_id, source.checksum, ...source.columns]
      .some((value) => value.toLocaleLowerCase().includes(normalizedSearch)),
  ) ?? [];
  const sortedSources = [...filteredSources].sort((left, right) => {
    if (sort === "name") return left.original_filename.localeCompare(right.original_filename);
    if (sort === "largest") return right.size_bytes - left.size_bytes || left.original_filename.localeCompare(right.original_filename);
    return right.uploaded_at.localeCompare(left.uploaded_at);
  });
  const pageSources = sortedSources.slice((page - 1) * SOURCE_PAGE_SIZE, page * SOURCE_PAGE_SIZE);
  const inspectedSource = sources.data?.items.find((source) => source.source_file_id === inspectedSourceId);

  return (
    <div className="page-content">
      <PageHeader eyebrow="DATA OPERATIONS" title="Source registry" description="Register tabular CSV or JSON data, inspect its schema, and choose a server-managed pipeline." actions={<><label className="select-field source-pipeline-select"><span>Run with</span><select aria-label="Pipeline for source runs" value={effectivePipelineId ?? ""} disabled={!pipelines.data?.length} onChange={(event) => setSelectedPipelineId(event.currentTarget.value)}>{pipelines.data?.map((pipeline) => <option key={pipeline.pipeline_id} value={pipeline.pipeline_id}>{pipeline.name}</option>)}</select></label><Link className="button button-secondary" to="/pipelines">View pipelines <ArrowRight size={15} aria-hidden="true" /></Link></>} />
      <ol className="source-import-steps" aria-label="Source registration workflow">
        <li><span className="source-step-number">01</span><span><strong>Register tabular data</strong><small>Store the original file and get its checksum</small></span><FileUp size={15} aria-hidden="true" /></li>
        <li><span className="source-step-number">02</span><span><strong>Inspect inferred schema</strong><small>Review local profiling and AI suggestions</small></span><FileSearch size={15} aria-hidden="true" /></li>
        <li><span className="source-step-number">03</span><span><strong>Run the pipeline</strong><small>Inspect validation and publishing evidence</small></span><Play size={14} aria-hidden="true" /></li>
      </ol>
      {effectivePipelineId === "general-tabular" ? <p className="source-pipeline-note">General Tabular Data accepts user-defined columns and keeps values intact. AI schema suggestions are advisory; without a configured key, the backend uses its local profile.</p> : effectivePipelineId ? <p className="source-pipeline-note">Financial Transactions expects transaction, customer, merchant, amount, currency, status, and event-time fields.</p> : null}
      <div className="sources-layout">
        <div className="sources-main">
          <section className="surface table-surface source-registry-surface" aria-labelledby="sources-heading">
            <div className="section-header"><div><p className="eyebrow">REGISTERED INPUTS</p><h2 id="sources-heading">Source files</h2></div><span className="data-window-label">{sources.data ? `${sources.data.total} total` : "Live API data"}</span></div>
            {sources.data?.items.length ? <div className="table-toolbar source-toolbar">
              <label className="search-field"><Search size={15} aria-hidden="true" /><span className="visually-hidden">Search registered sources</span><input type="search" value={search} onChange={(event) => { setSearch(event.currentTarget.value); setPage(1); }} placeholder="Search files, columns or checksum" /></label>
              <label className="select-field"><span>Sort by</span><select aria-label="Sort registered sources" value={sort} onChange={(event) => { setSort(event.currentTarget.value as SourceSort); setPage(1); }}><option value="newest">Recently uploaded</option><option value="name">Name A to Z</option><option value="largest">Largest file</option></select></label>
              <span className="filter-scope">{filteredSources.length.toLocaleString()} matched · API registry</span>
            </div> : null}
            {sources.isPending ? <StatePanel tone="loading" title="Loading source registry" message="Reading registered sources from the API." /> : null}
            {sources.isError ? <StatePanel tone="error" title="Could not load source files" message={sources.error.message} action={<button className="button button-secondary" onClick={() => void sources.refetch()}><RefreshCw size={14} />Retry</button>} /> : null}
            {sources.data?.items.length === 0 ? <StatePanel tone="empty" title="No source files registered" message="Register a CSV or JSON file to create a content-addressed source record and inspect its detected columns." /> : null}
            {pipelines.data?.length === 0 ? <StatePanel tone="empty" title="No runnable pipeline is registered" message="The API returned no pipeline definitions, so a source run cannot start. Pipeline setup is managed by the backend." action={<Link className="button button-secondary" to="/pipelines">View pipeline registry</Link>} compact /> : null}
            {sources.data && sources.data.items.length > 0 && filteredSources.length === 0 ? <StatePanel tone="empty" title="No sources match this search" message="Try a filename, source ID, detected column or checksum fragment." compact /> : null}
            {sources.data && pageSources.length > 0 ? (
              <div className="table-scroll source-registry-scroll" role="region" aria-label="Registered source files" tabIndex={0}>
                <table className="data-table source-table">
                  <caption className="visually-hidden">Registered tabular source files. Search and sort apply to the API registry results.</caption>
                  <thead><tr><th scope="col">Source</th><th scope="col">Columns</th><th scope="col">Size</th><th scope="col">Uploaded</th><th scope="col">Checksum</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
                  <tbody>{pageSources.map((source) => <tr key={source.source_file_id}>
                    <td><span className="table-source-name"><Database size={15} aria-hidden="true" /><strong>{source.original_filename}</strong></span><code className="table-secondary">{source.source_file_id}</code></td>
                    <td><span className="column-count">{source.columns.length} detected</span><span className="table-secondary column-list" title={source.columns.join(", ")}>{source.columns.slice(0, 4).join(", ")}{source.columns.length > 4 ? ` +${source.columns.length - 4}` : ""}</span></td>
                    <td className="numeric-cell">{formatBytes(source.size_bytes)}</td>
                    <td>{formatDate(source.uploaded_at)}</td>
                    <td><code className="checksum" title={source.checksum}>{source.checksum.slice(0, 12)}…</code></td>
                    <td><div className="source-row-actions"><button className="button button-small button-secondary" type="button" aria-label={`${inspectedSourceId === source.source_file_id ? "Hide" : "Inspect"} detected columns for ${source.original_filename}`} aria-pressed={inspectedSourceId === source.source_file_id} onClick={() => setInspectedSourceId((current) => current === source.source_file_id ? null : source.source_file_id)}><FileSearch size={13} aria-hidden="true" />Inspect</button><button className="button button-small button-primary" type="button" aria-label={`Run pipeline for ${source.original_filename}`} disabled={runMutation.isPending || pipelines.isPending || pipelines.isError || !pipelines.data?.length} onClick={() => runMutation.mutate(source)}><Play size={13} aria-hidden="true" />Run</button></div></td>
                  </tr>)}</tbody>
                </table>
              </div>
            ) : null}
            {sources.data && filteredSources.length > SOURCE_PAGE_SIZE ? <Pagination page={page} pageSize={SOURCE_PAGE_SIZE} total={filteredSources.length} onPageChange={setPage} /> : null}
            {inspectedSource ? <section className="source-schema-inspector" aria-labelledby="source-schema-heading">
              <div className="source-schema-heading"><div><p className="eyebrow">SERVER-DETECTED STRUCTURE</p><h3 id="source-schema-heading">{inspectedSource.original_filename}</h3><p>Columns detected when this CSV was registered.</p></div><span className="data-window-label">{inspectedSource.columns.length} columns</span></div>
              <dl className="source-metadata-grid"><div><dt>Source ID</dt><dd><code>{inspectedSource.source_file_id}</code></dd></div><div><dt>File size</dt><dd>{formatBytes(inspectedSource.size_bytes)}</dd></div><div><dt>Registered</dt><dd>{formatDate(inspectedSource.uploaded_at)}</dd></div><div><dt>SHA-256 checksum</dt><dd><code>{inspectedSource.checksum}</code></dd></div></dl>
              <div className="source-column-list" aria-label="Detected columns">{inspectedSource.columns.map((column) => <code key={column}>{column}</code>)}</div>
              <p className="source-schema-note">The general tabular pipeline accepts user-defined columns. Its schema suggestions describe headers and aggregate statistics; it does not send source cell values to the LLM.</p>
            </section> : null}
            {pipelines.isError ? <StatePanel tone="error" title="Pipeline registry unavailable" message="A run cannot start until the backend returns an available pipeline." compact /> : null}
            {runMutation.isError ? <StatePanel tone="error" title="Run could not be started" message={runMutation.error.message} compact /> : null}
          </section>
          <section className="surface source-contract-panel" aria-labelledby="source-contract-heading">
            <div className="section-icon section-icon-blue" aria-hidden="true"><Database size={16} /></div>
            <div><h2 id="source-contract-heading">Server-verified source identity</h2><p>The backend validates the CSV structure, stores the original bytes by checksum and returns detected columns. Re-uploading identical file contents resolves to the same source record.</p></div>
          </section>
        </div>
        <aside className="sources-side"><UploadPanel busy={uploadMutation.isPending} error={uploadMutation.error?.message ?? null} resetVersion={uploadSuccessVersion} onSelectionChange={() => uploadMutation.reset()} onUpload={(file) => uploadMutation.mutate(file)} />
          {uploadMutation.data ? <div className="upload-result" role="status"><strong>Source registered</strong><span>{uploadMutation.data.original_filename}</span><code>{uploadMutation.data.source_file_id}</code><small>{uploadMutation.data.columns.length} columns · {uploadMutation.data.checksum.slice(0, 16)}…</small><button className="button button-secondary" type="button" disabled={runMutation.isPending || pipelines.isPending || pipelines.isError || !pipelines.data?.length} onClick={() => runMutation.mutate(uploadMutation.data!)}><Play size={14} aria-hidden="true" />Start pipeline run</button>{pipelines.data?.length === 0 ? <small>No pipeline is available. Setup is managed by the backend; view the pipeline registry for current status.</small> : null}{runMutation.isPending ? <small>Creating a persisted run…</small> : null}</div> : null}
        </aside>
      </div>
    </div>
  );
}
