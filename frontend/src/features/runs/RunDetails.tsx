import { Check, CircleAlert, Clock3, Rows3 } from "lucide-react";

import { MetricCard } from "../../components/common/MetricCard";
import { StatusBadge } from "../../components/common/StatusBadge";
import type { PipelineRun } from "../../services/runService";
import { formatDate, formatDuration, formatNumber } from "../../utils/format";

interface RunDetailsProps {
  run: PipelineRun;
  retrying: boolean;
  retryError: string | null;
  onRetry: () => void;
}

interface SchemaAnalysis {
  mode: "llm" | "local";
  provider: string | null;
  model: string | null;
  fallback_reason?: string;
  dataset_kind: string;
  summary: string;
  columns: Array<{ name: string; semantic_type: string; description: string; pii_risk: boolean }>;
  candidate_key_columns: string[];
  quality_notes: string[];
  input_sent: string;
}

const countDefinitions: Array<[keyof PipelineRun["counts"], string]> = [
  ["input", "Input"], ["accepted", "Accepted"], ["rejected", "Rejected"], ["duplicates", "Duplicates"], ["published", "Published"],
];

export function RunDetails({ run, retrying, retryError, onRetry }: RunDetailsProps) {
  const canRetry = run.status === "FAILED" && run.error?.code === "pipeline_execution_failed";
  const schemaAnalysis = run.profile.schema_analysis as SchemaAnalysis | undefined;
  return (
    <div className="run-detail-stack">
      <section className="surface run-overview" aria-labelledby="run-detail-heading">
        <div className="run-detail-top">
          <div><p className="eyebrow">EXECUTION EVIDENCE</p><h2 id="run-detail-heading">Run details</h2><p className="run-id-label">{run.run_id}</p></div>
          <div className="run-detail-actions"><StatusBadge status={run.status} />{canRetry ? <button type="button" className="button button-secondary" disabled={retrying} onClick={onRetry}>{retrying ? <span className="spinner" aria-hidden="true" /> : <Clock3 size={15} aria-hidden="true" />}{retrying ? "Retrying…" : "Retry run"}</button> : null}</div>
        </div>
        {run.error ? <div className={`run-error-callout${run.status === "FAILED" ? " run-error-failed" : ""}`}><CircleAlert size={16} aria-hidden="true" /><p><strong>{run.error.code.replaceAll("_", " ")}</strong><span>{run.error.message}</span></p></div> : null}
        {retryError ? <p className="form-error" role="alert">Retry was not started: {retryError}</p> : null}
        {run.status === "FAILED" && !canRetry ? <p className="inline-note">This failure cannot be retried with the same source. Correct the source file and create a new run.{run.error?.code === "schema_incompatible" ? " For non-financial columns, choose the General Tabular Data pipeline on the source registry." : ""}</p> : null}
        <div className="run-metadata"><span><small>Pipeline</small><strong>{run.pipeline_id}</strong></span><span><small>Created</small><strong>{formatDate(run.created_at)}</strong></span><span><small>Duration</small><strong>{formatDuration(run.started_at, run.completed_at)}</strong></span></div>
      </section>

      {run.pipeline_id === "general-tabular" && schemaAnalysis ? <section className="surface schema-analysis-surface" aria-labelledby="schema-analysis-heading">
        <div className="section-header"><div><p className="eyebrow">SCHEMA UNDERSTANDING</p><h2 id="schema-analysis-heading">{schemaAnalysis.mode === "llm" ? "AI schema suggestions" : "Local schema profile"}</h2></div><span className={`data-window-label ${schemaAnalysis.mode === "llm" ? "schema-ai-badge" : ""}`}>{schemaAnalysis.mode === "llm" ? `${schemaAnalysis.provider} · ${schemaAnalysis.model}` : "Deterministic fallback"}</span></div>
        <p className="schema-analysis-summary"><strong>{schemaAnalysis.dataset_kind}</strong> · {schemaAnalysis.summary}</p>
        {schemaAnalysis.mode === "local" ? <p className="inline-note">{schemaAnalysis.fallback_reason === "provider_key_not_configured" ? "Add an OpenRouter or Gemini key in the backend .env to enable AI schema suggestions." : "The configured AI provider was unavailable; this run continued with its local profile."} Source cell values are not sent to a provider.</p> : <p className="inline-note">The provider received column names and aggregate profile metadata only; source cell values were not sent. Suggestions do not change or discard data.</p>}
        {schemaAnalysis.columns.length ? <div className="schema-suggestion-list">{schemaAnalysis.columns.slice(0, 20).map((column) => <div className="schema-suggestion" key={column.name}><code>{column.name}</code><span>{column.semantic_type}</span><p>{column.description}{column.pii_risk ? " · Possible sensitive field" : ""}</p></div>)}</div> : null}
        {schemaAnalysis.columns.length > 20 ? <p className="inline-note">Showing 20 of {schemaAnalysis.columns.length} column suggestions.</p> : null}
        {schemaAnalysis.candidate_key_columns.length ? <p className="schema-key-note"><strong>Possible key fields:</strong> {schemaAnalysis.candidate_key_columns.join(", ")} <span>· suggestion only</span></p> : null}
        {schemaAnalysis.quality_notes.length ? <ul className="schema-quality-notes">{schemaAnalysis.quality_notes.map((note, index) => <li key={`${index}-${note}`}>{note}</li>)}</ul> : null}
      </section> : null}

      <div className="metric-grid run-count-grid" aria-label="Persisted run disposition counts">
        {countDefinitions.map(([key, label], index) => <MetricCard key={key} label={label} value={formatNumber(run.counts[key])} note={key === "input" ? "Source rows" : key === "published" ? "Output rows" : "Rows"} icon={index === 0 ? <Rows3 size={16} /> : index === 4 ? <Check size={16} /> : <CircleAlert size={16} />} tone={key === "rejected" ? "amber" : key === "published" ? "teal" : "neutral"} />)}
      </div>

      <section className="surface stage-surface" aria-labelledby="stage-heading">
        <div className="section-header"><div><p className="eyebrow">PERSISTED PROCESSING EVIDENCE</p><h2 id="stage-heading">Stage timeline</h2></div><span className="data-window-label">{run.stages.length} stages</span></div>
        {run.stages.length ? <ol className="stage-timeline">{run.stages.map((stage, index) => <li className="stage-item" key={`${stage.attempt_id}-${stage.stage_name}`}>
          <div className={`stage-marker stage-marker-${stage.status.toLowerCase()}`} aria-hidden="true">{stage.status === "SUCCESS" ? <Check size={12} /> : <span>{index + 1}</span>}</div>
          <div className="stage-content"><div className="stage-title-row"><h3>{stage.stage_name.replaceAll("_", " ")}</h3><StatusBadge status={stage.status} size="small" /></div><div className="stage-meta"><span>Attempt {stage.attempt_id.split("_attempt_").at(-1)}</span><span>{formatNumber(stage.input_count)} in</span><span>{formatNumber(stage.output_count)} out</span><span>{stage.reject_count} rejected</span><span>{stage.duration_ms} ms</span></div></div>
        </li>)}</ol> : <p className="table-empty">Stage evidence has not been recorded for this run.</p>}
      </section>
    </div>
  );
}
