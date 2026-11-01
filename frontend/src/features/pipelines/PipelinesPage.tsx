import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Workflow } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { listPipelines } from "../../services/pipelineService";

export function PipelinesPage() {
  const pipelines = useQuery({ queryKey: ["pipelines"], queryFn: listPipelines });
  return (
    <div className="page-content">
      <PageHeader eyebrow="DATA OPERATIONS" title="Pipelines" description="Inspect the pipeline definitions the backend has registered." actions={<Link className="button button-primary" to="/sources">Register a source <ArrowRight size={15} aria-hidden="true" /></Link>} />
      <section className="surface table-surface" aria-labelledby="pipeline-list-heading">
        <div className="section-header"><div><p className="eyebrow">BACKEND REGISTRY</p><h2 id="pipeline-list-heading">Available pipelines</h2></div><span className="data-window-label">{pipelines.data ? `${pipelines.data.length} registered` : "Live API data"}</span></div>
        {pipelines.isPending ? <StatePanel tone="loading" title="Loading pipeline registry" message="Fetching definitions from the backend." /> : null}
        {pipelines.isError ? <StatePanel tone="error" title="Pipeline registry unavailable" message={pipelines.error.message} action={<button className="button button-secondary" onClick={() => void pipelines.refetch()}>Retry</button>} /> : null}
        {pipelines.data?.length === 0 ? <StatePanel tone="empty" title="No pipelines are registered" message="Pipeline definitions will appear when the backend registers them." /> : null}
        {pipelines.data?.map((pipeline) => <article className="pipeline-card" key={pipeline.pipeline_id}>
          <div className="pipeline-card-icon" aria-hidden="true"><Workflow size={19} /></div>
          <div className="pipeline-card-main"><div className="pipeline-name-row"><h3>{pipeline.name}</h3><span className="version-badge">Version {pipeline.version}</span></div><code>{pipeline.pipeline_id}</code><p>{pipeline.pipeline_id === "general-tabular" ? "Accepts user-defined CSV and JSON columns, preserves source values, detects malformed/empty/duplicate rows, and records provenance. Optional LLM schema suggestions are advisory." : "Applies finance-specific transaction, currency, status, timestamp, reference, and reconciliation rules."}</p></div>
          <Link className="button button-secondary" to="/runs">View runs <ArrowRight size={14} aria-hidden="true" /></Link>
        </article>)}
      </section>
      <StatePanel tone="info" title="Visual pipeline editing is not configured" message="The current API exposes pipeline metadata but does not expose graph configuration or an endpoint to save and execute custom nodes. DataTrace keeps execution server-managed until that contract exists." />
    </div>
  );
}
