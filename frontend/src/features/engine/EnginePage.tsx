import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Check, CircleHelp, FlaskConical, RefreshCw, Sparkles, WandSparkles } from "lucide-react";

import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { listSources } from "../../services/sourceService";
import {
  approveSchemaMappings,
  compareSourceSchemas,
  createDryRun,
  getAIStatus,
  getAIUsage,
  getEngineRegistry,
  getSourceProfile,
  listEngineRules,
  listEngineTransformations,
  listSchemaProfiles,
  requestSchemaSuggestions,
  resetAIBudget,
  saveRule,
  saveTransformation,
  testRegex,
} from "../../services/engineService";
import type { DataProfile, DryRunPlan, RegexSuggestion, SchemaAnalysis } from "../../services/engineService";

type MappingDraft = {
  source_column: string;
  semantic_field: string;
  action: "approve" | "edit" | "reject";
  confidence: number;
  explanation: string;
};

function formatMetric(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return String(value);
}

function formatMoney(value: string | undefined): string {
  const amount = Number(value ?? "0");
  return `$${amount.toFixed(6)}`;
}

function ProfileTable({ profile }: { profile: DataProfile }) {
  return (
    <div className="table-scroll engine-profile-scroll" role="region" aria-label="Profiled source columns" tabIndex={0}>
      <table className="data-table engine-profile-table">
        <caption className="visually-hidden">Server-generated profile statistics for each source column.</caption>
        <thead><tr><th scope="col">Column</th><th scope="col">Inferred type</th><th scope="col">Nulls</th><th scope="col">Distinct</th><th scope="col">Observed range</th><th scope="col">Patterns and signals</th></tr></thead>
        <tbody>{profile.column_profiles.map((column) => {
          const numeric = column.numeric;
          const string = column.string;
          const signals = Object.entries(column.value_shapes).filter(([, count]) => count > 0).map(([name]) => name);
          return <tr key={column.name}>
            <th scope="row"><code>{column.name}</code>{column.mixed_type ? <span className="engine-pill engine-pill-warning">Mixed</span> : null}</th>
            <td>{column.inferred_type}</td>
            <td>{formatMetric(column.null_count)} <span className="table-secondary">({formatMetric(column.null_percent)}%)</span></td>
            <td>{formatMetric(column.distinct_count)} <span className="table-secondary">({formatMetric(column.distinct_ratio)}%)</span></td>
            <td>{numeric ? <span>{numeric.min} … {numeric.max}<small>median {numeric.median} · {numeric.outlier_count_iqr} IQR outliers</small></span> : string ? <span>{string.min_length}–{string.max_length} chars<small>mean {formatMetric(string.mean_length)}</small></span> : <span>{column.date_formats?.join(", ") || "—"}</span>}</td>
            <td><div className="engine-signal-list">{signals.slice(0, 3).map((signal) => <span className="engine-pill" key={signal}>{signal}</span>)}{column.regex_suggestion ? <RegexBadge suggestion={column.regex_suggestion} /> : null}{!signals.length && !column.regex_suggestion ? <span className="table-secondary">No recognized pattern</span> : null}</div></td>
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}

function RegexBadge({ suggestion }: { suggestion: RegexSuggestion }) {
  return <span className="engine-regex-hint" title={`${suggestion.note} ${suggestion.matching_count}/${suggestion.sample_count} sampled values matched.`}>Regex candidate · {Math.round(suggestion.confidence * 100)}%</span>;
}

export function EnginePage() {
  const queryClient = useQueryClient();
  const sources = useQuery({ queryKey: ["sources"], queryFn: listSources });
  const registry = useQuery({ queryKey: ["engine", "registry"], queryFn: getEngineRegistry });
  const aiStatus = useQuery({ queryKey: ["ai", "status"], queryFn: getAIStatus });
  const aiUsage = useQuery({ queryKey: ["ai", "usage"], queryFn: getAIUsage });
  const [sourceId, setSourceId] = useState("");
  const [compareId, setCompareId] = useState("");
  const [analysis, setAnalysis] = useState<SchemaAnalysis | null>(null);
  const [schemaProfileId, setSchemaProfileId] = useState<string | null>(null);
  const [mappingDrafts, setMappingDrafts] = useState<MappingDraft[]>([]);
  const [activeTab, setActiveTab] = useState<"profile" | "rules" | "plans">("profile");
  const [manualRuleType, setManualRuleType] = useState("required");
  const [manualRuleField, setManualRuleField] = useState("");
  const [manualRuleConfig, setManualRuleConfig] = useState("{}");
  const [regexPattern, setRegexPattern] = useState("");
  const [regexValues, setRegexValues] = useState("");
  const [plan, setPlan] = useState<DryRunPlan | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const availableSources = sources.data?.items ?? [];
    if (!sourceId && availableSources.length) setSourceId(availableSources[0].source_file_id);
    if (!compareId && availableSources.length > 1) setCompareId(availableSources[1].source_file_id);
  }, [sources.data, sourceId, compareId]);

  const selectedSource = sources.data?.items.find((source) => source.source_file_id === sourceId);
  const sourceProfile = useQuery({ queryKey: ["engine", "profile", sourceId], queryFn: () => getSourceProfile(sourceId), enabled: Boolean(sourceId) });
  const schemaProfiles = useQuery({ queryKey: ["engine", "schema-profiles", sourceId], queryFn: () => listSchemaProfiles(sourceId), enabled: Boolean(sourceId) });
  const fingerprint = sourceProfile.data?.schema_fingerprint ?? "";
  const savedRules = useQuery({ queryKey: ["engine", "rules", fingerprint], queryFn: () => listEngineRules(fingerprint), enabled: Boolean(fingerprint) });
  const savedTransforms = useQuery({ queryKey: ["engine", "transformations", fingerprint], queryFn: () => listEngineTransformations(fingerprint), enabled: Boolean(fingerprint) });
  const drift = useQuery({ queryKey: ["engine", "drift", sourceId, compareId], queryFn: () => compareSourceSchemas(sourceId, compareId), enabled: Boolean(sourceId && compareId && sourceId !== compareId) });

  const suggest = useMutation({
    mutationFn: () => requestSchemaSuggestions(sourceId),
    onSuccess: (result) => {
      setAnalysis(result.analysis);
      setSchemaProfileId(result.schema_profile_id);
      setMappingDrafts(result.analysis.mapping_suggestions.map((item) => ({
        source_column: item.source_column,
        semantic_field: item.semantic_field,
        action: "reject",
        confidence: item.confidence,
        explanation: item.explanation,
      })));
      void queryClient.invalidateQueries({ queryKey: ["ai", "status"] });
      void queryClient.invalidateQueries({ queryKey: ["ai", "usage"] });
      void queryClient.invalidateQueries({ queryKey: ["engine", "schema-profiles", sourceId] });
      setNotice(`Suggestions saved for review using ${result.analysis.mode === "llm" ? result.analysis.model : "the local fallback"}.`);
    },
  });
  const approveMappings = useMutation({
    mutationFn: () => approveSchemaMappings(schemaProfileId!, mappingDrafts),
    onSuccess: async (result) => {
      setNotice(`Schema mapping profile v${result.version} saved as ${result.status}.`);
      await queryClient.invalidateQueries({ queryKey: ["engine", "schema-profiles", sourceId] });
      await queryClient.invalidateQueries({ queryKey: ["engine", "rules", fingerprint] });
      await queryClient.invalidateQueries({ queryKey: ["engine", "transformations", fingerprint] });
    },
  });
  const saveSuggestedRule = useMutation({
    mutationFn: ({ definition, status }: { definition: Record<string, unknown>; status: "draft" | "approved" }) => saveRule(fingerprint, definition, status),
    onSuccess: async (result) => {
      setNotice(`Rule ${result.rule_id} saved as ${result.status}.`);
      await queryClient.invalidateQueries({ queryKey: ["engine", "rules", fingerprint] });
    },
  });
  const saveSuggestedTransform = useMutation({
    mutationFn: ({ definition, status }: { definition: Record<string, unknown>; status: "draft" | "approved" }) => saveTransformation(fingerprint, definition, status),
    onSuccess: async (result) => {
      setNotice(`Transformation ${result.transform_id} saved as ${result.status}.`);
      await queryClient.invalidateQueries({ queryKey: ["engine", "transformations", fingerprint] });
    },
  });
  const saveManualRule = useMutation({
    mutationFn: async () => {
      let config: unknown;
      try { config = JSON.parse(manualRuleConfig); } catch { throw new Error("Rule configuration must be valid JSON."); }
      if (!config || typeof config !== "object" || Array.isArray(config)) throw new Error("Rule configuration must be a JSON object.");
      return saveRule(fingerprint, { field: manualRuleField, rule_type: manualRuleType, config, severity: "error", enabled: true }, "draft");
    },
    onSuccess: async (result) => {
      setNotice(`Rule ${result.rule_id} saved as a draft. Approve it from the rule registry before execution.`);
      await queryClient.invalidateQueries({ queryKey: ["engine", "rules", fingerprint] });
    },
  });
  const regexTest = useMutation({ mutationFn: () => testRegex(regexPattern, regexValues.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).slice(0, 20)) });
  const dryRun = useMutation({
    mutationFn: () => createDryRun(sourceId),
    onSuccess: (result) => {
      setPlan(result);
      setNotice(`Dry run ${result.plan_id} completed from the saved, approved rules and transformations.`);
      void queryClient.invalidateQueries({ queryKey: ["ai", "status"] });
      void queryClient.invalidateQueries({ queryKey: ["ai", "usage"] });
    },
  });
  const resetBudget = useMutation({
    mutationFn: resetAIBudget,
    onSuccess: async () => {
      setNotice("AI test budget reset to the configured limit.");
      await queryClient.invalidateQueries({ queryKey: ["ai"] });
    },
  });
  const profile = sourceProfile.data?.profile;
  const savedSchema = schemaProfiles.data?.items[0];
  const llmRules = analysis?.rule_suggestions ?? [];
  const llmTransforms = analysis?.transformation_suggestions ?? [];
  const approvedRuleCount = savedRules.data?.items.filter((rule) => rule.status === "approved").length ?? 0;
  const approvedTransformCount = savedTransforms.data?.items.filter((item) => item.status === "approved").length ?? 0;
  const mappingSuggestionByColumn = useMemo(() => new Map((profile?.mapping_candidates ?? []).map((item) => [item.source_column, item])), [profile]);

  function updateMapping(index: number, patch: Partial<MappingDraft>) {
    setMappingDrafts((current) => current.map((mapping, row) => row === index ? { ...mapping, ...patch } : mapping));
  }

  function suggestRuleDefinition(rule: SchemaAnalysis["rule_suggestions"][number]): Record<string, unknown> {
    return { rule_id: rule.rule_id, field: rule.field, rule_type: rule.rule_type, config: rule.config, severity: rule.severity, confidence: rule.confidence, enabled: rule.enabled, provenance: rule.provenance };
  }

  function suggestTransformDefinition(item: SchemaAnalysis["transformation_suggestions"][number]): Record<string, unknown> {
    return { transform_id: item.transform_id, field: item.field, operator: item.operator, config: item.config, enabled: true };
  }

  return <div className="page-content engine-page">
    <PageHeader eyebrow="ADAPTIVE PROCESSING" title="Data engine" description="Profile unfamiliar tabular data, review schema and rule suggestions, then preview the real backend pipeline before running it." actions={<button className="button button-primary" type="button" disabled={!sourceId || dryRun.isPending} onClick={() => { setActiveTab("plans"); dryRun.mutate(); }}><FlaskConical size={15} aria-hidden="true" />{dryRun.isPending ? "Building preview…" : "Run dry preview"}</button>} />

    <section className="engine-toolbar surface" aria-label="Engine source and AI budget">
      <label className="select-field engine-source-select"><span>Profiled source</span><select aria-label="Select a source to profile" value={sourceId} disabled={!sources.data?.items.length} onChange={(event) => { setSourceId(event.currentTarget.value); setAnalysis(null); setPlan(null); setNotice(""); }}>
        {sources.data?.items.length ? sources.data.items.map((source) => <option key={source.source_file_id} value={source.source_file_id}>{source.original_filename} · {source.columns.length} columns</option>) : <option value="">No source files registered</option>}
      </select></label>
      <div className="engine-budget-card">
        <div className="engine-budget-copy"><span>AI test budget</span><strong>{formatMoney(aiStatus.data?.budget.used_usd)} <small>/ {formatMoney(aiStatus.data?.budget.limit_usd)}</small></strong><span>{aiStatus.data?.configured ? `${aiStatus.data.provider} · ${aiStatus.data.model}` : "Deterministic local fallback"}</span></div>
        <div className="engine-budget-actions"><span className="engine-budget-remaining">{formatMoney(aiStatus.data?.budget.remaining_usd)} remaining</span><button className="button button-small button-secondary" type="button" disabled={resetBudget.isPending || !aiStatus.data} onClick={() => { if (window.confirm("Reset the local $1 AI test budget ledger? This does not change your OpenRouter account billing limit.")) resetBudget.mutate(); }}>Reset test budget</button></div>
      </div>
    </section>
    {sources.isPending ? <StatePanel tone="loading" title="Loading sources" message="Reading registered inputs from the backend." /> : null}
    {sources.isError ? <StatePanel tone="error" title="Source registry unavailable" message={sources.error.message} action={<button className="button button-secondary" type="button" onClick={() => void sources.refetch()}>Retry</button>} /> : null}
    {!sources.isPending && sources.data?.items.length === 0 ? <StatePanel tone="empty" title="No data to profile" message="Register a CSV, JSON, JSONL or Excel workbook from Sources to inspect it here." /> : null}
    {selectedSource && profile ? <>
      <section className="engine-source-summary surface" aria-label="Selected source profile summary">
        <div><p className="eyebrow">SERVER PROFILE</p><h2>{selectedSource.original_filename}</h2><p>{profile.row_count.toLocaleString()} source rows · {profile.columns.length} columns · sample of {profile.profile_sample_size.toLocaleString()} · {profile.duplicate_row_count.toLocaleString()} duplicate rows</p></div>
        <dl><div><dt>Schema fingerprint</dt><dd><code>{profile.schema_fingerprint.slice(0, 18)}…</code></dd></div><div><dt>Checksum</dt><dd><code>{selectedSource.checksum.slice(0, 18)}…</code></dd></div></dl>
      </section>
      <div className="engine-tabs" role="tablist" aria-label="Data engine tools">
        {([ ["profile", "Profile and schema"], ["rules", "Rules and transforms"], ["plans", "Dry-run plans"] ] as const).map(([key, label]) => <button key={key} className={`engine-tab${activeTab === key ? " engine-tab-active" : ""}`} id={`engine-tab-${key}`} role="tab" type="button" aria-selected={activeTab === key} aria-controls={`engine-panel-${key}`} onClick={() => setActiveTab(key)}>{label}</button>)}
      </div>

      {activeTab === "profile" ? <div id="engine-panel-profile" role="tabpanel" aria-labelledby="engine-tab-profile" className="engine-panel">
        <section className="surface table-surface" aria-labelledby="profile-heading">
          <div className="section-header"><div><p className="eyebrow">AUTOMATIC PROFILING</p><h2 id="profile-heading">Column characteristics</h2></div><span className="data-window-label">Fingerprint {profile.schema_fingerprint.slice(0, 10)}</span></div>
          <p className="section-description">Counts and statistics are computed locally from the uploaded file. Pattern samples are abstracted; source cell values are not sent to the model.</p>
          {sourceProfile.isError ? <StatePanel tone="error" title="Profile could not be loaded" message={sourceProfile.error.message} /> : <ProfileTable profile={profile} />}
        </section>

        <section className="surface schema-assist-surface" aria-labelledby="schema-assist-heading">
          <div className="section-header"><div><p className="eyebrow">REVIEW REQUIRED</p><h2 id="schema-assist-heading">Schema and processing suggestions</h2></div><button className="button button-secondary" type="button" disabled={suggest.isPending || !sourceId} onClick={() => suggest.mutate()}><Sparkles size={14} aria-hidden="true" />{suggest.isPending ? "Analyzing…" : "Suggest mappings and rules"}</button></div>
          <p className="section-description">The configured model may suggest semantic mappings, validation rules and transformations. The local fallback remains available; generated suggestions never execute as code.</p>
          {suggest.isError ? <StatePanel tone="error" title="Suggestions could not be generated" message={suggest.error.message} /> : null}
          {analysis ? <div className="engine-analysis-result">
            <div className="engine-analysis-meta"><span className={`engine-pill ${analysis.mode === "llm" ? "engine-pill-accent" : ""}`}>{analysis.mode === "llm" ? `LLM · ${analysis.model}` : "Local deterministic fallback"}</span><span>{analysis.dataset_kind}</span>{analysis.usage ? <span>{analysis.usage.prompt_tokens + analysis.usage.completion_tokens} tokens · {formatMoney(analysis.usage.reported_cost_usd ?? analysis.usage.estimated_cost_usd)} · {analysis.usage.latency_ms} ms</span> : null}</div>
            <p className="schema-analysis-summary">{analysis.summary}</p>
            {mappingDrafts.length ? <>
              <div className="table-scroll" role="region" aria-label="Editable mapping suggestions" tabIndex={0}><table className="data-table engine-mapping-table"><thead><tr><th scope="col">Source column</th><th scope="col">Suggested concept</th><th scope="col">Confidence / evidence</th><th scope="col">Your decision</th></tr></thead><tbody>{mappingDrafts.map((mapping, index) => {
                const suggestion = analysis.mapping_suggestions[index];
                const localCandidate = mappingSuggestionByColumn.get(mapping.source_column);
                return <tr key={mapping.source_column}><th scope="row"><code>{mapping.source_column}</code></th><td><input aria-label={`Semantic field for ${mapping.source_column}`} className="engine-inline-input" value={mapping.semantic_field} onChange={(event) => updateMapping(index, { semantic_field: event.currentTarget.value, action: "edit" })} /></td><td><span>{Math.round(mapping.confidence * 100)}%</span><small>{suggestion?.explanation || localCandidate?.evidence.join("; ") || "Based on the header name and local profile."}</small></td><td><select aria-label={`Decision for ${mapping.source_column}`} value={mapping.action} onChange={(event) => updateMapping(index, { action: event.currentTarget.value as MappingDraft["action"] })}><option value="reject">Reject / skip</option><option value="approve">Approve</option><option value="edit">Edit and approve</option></select></td></tr>;
              })}</tbody></table></div>
              <button className="button button-primary" type="button" disabled={approveMappings.isPending} onClick={() => approveMappings.mutate()}><Check size={14} aria-hidden="true" />Save mapping decisions</button>
              {approveMappings.isError ? <p className="engine-error" role="alert">{approveMappings.error.message}</p> : null}
            </> : <p className="engine-empty-note">No semantic mappings were suggested for this schema. Rules can still use the original column names.</p>}
            {(llmRules.length || llmTransforms.length) ? <div className="engine-suggestion-grid">
              {llmRules.map((rule) => <article className="engine-suggestion-card" key={rule.rule_id}><div><span className="engine-pill">Rule suggestion</span><span className="engine-confidence">{Math.round(rule.confidence * 100)}% confidence</span></div><h3>{rule.rule_type} · <code>{rule.field}</code></h3><p>{rule.explanation || "Review this configurable validator before use."}</p>{rule.sample_evidence ? <small>{rule.sample_evidence.matching_count}/{rule.sample_evidence.sample_count} samples passed; {rule.sample_evidence.non_matching_count} did not.</small> : null}<div><button className="button button-small button-secondary" type="button" disabled={saveSuggestedRule.isPending} onClick={() => saveSuggestedRule.mutate({ definition: suggestRuleDefinition(rule), status: "draft" })}>Save draft</button><button className="button button-small button-primary" type="button" disabled={saveSuggestedRule.isPending} onClick={() => saveSuggestedRule.mutate({ definition: suggestRuleDefinition(rule), status: "approved" })}>Approve rule</button></div></article>)}
              {llmTransforms.map((item) => <article className="engine-suggestion-card" key={item.transform_id}><div><span className="engine-pill">Transform suggestion</span>{item.confidence !== undefined ? <span className="engine-confidence">{Math.round(item.confidence * 100)}% confidence</span> : null}</div><h3>{item.operator} · <code>{item.field}</code></h3><p>{item.explanation || "Review the deterministic transformation parameters before applying."}</p><div><button className="button button-small button-secondary" type="button" disabled={saveSuggestedTransform.isPending} onClick={() => saveSuggestedTransform.mutate({ definition: suggestTransformDefinition(item), status: "draft" })}>Save draft</button><button className="button button-small button-primary" type="button" disabled={saveSuggestedTransform.isPending} onClick={() => saveSuggestedTransform.mutate({ definition: suggestTransformDefinition(item), status: "approved" })}>Approve transform</button></div></article>)}
            </div> : null}
          </div> : null}
          {schemaProfiles.data?.items.length ? <p className="engine-saved-note">Latest schema profile: v{schemaProfiles.data.items[0].version} · {schemaProfiles.data.items[0].status}</p> : savedSchema ? <p className="engine-saved-note">Profile status: {savedSchema.status}</p> : null}
          {approveMappings.isSuccess ? <p className="engine-saved-note">User decisions are versioned and stored for this schema fingerprint.</p> : null}
        </section>

        {sources.data && sources.data.items.length > 1 ? <section className="surface" aria-labelledby="schema-drift-heading"><div className="section-header"><div><p className="eyebrow">SCHEMA EVOLUTION</p><h2 id="schema-drift-heading">Compare with another source</h2></div><label className="select-field"><span>Comparison source</span><select aria-label="Schema comparison source" value={compareId} onChange={(event) => setCompareId(event.currentTarget.value)}>{sources.data.items.filter((source) => source.source_file_id !== sourceId).map((source) => <option key={source.source_file_id} value={source.source_file_id}>{source.original_filename}</option>)}</select></label></div>{drift.isPending ? <StatePanel tone="loading" title="Comparing schemas" message="Checking added, missing and type-conflicting columns." compact /> : drift.data ? <div className="engine-drift-grid"><div><strong>{drift.data.added_columns.length}</strong><span>Additional columns</span><small>{drift.data.added_columns.join(", ") || "None"}</small></div><div><strong>{drift.data.missing_columns.length}</strong><span>Missing columns</span><small>{drift.data.missing_columns.join(", ") || "None"}</small></div><div><strong>{drift.data.type_conflicts.length}</strong><span>Type conflicts</span><small>{drift.data.type_conflicts.map((item) => `${item.column}: ${item.left_type} → ${item.right_type}`).join("; ") || "None"}</small></div></div> : drift.isError ? <StatePanel tone="error" title="Schema comparison failed" message={drift.error.message} compact /> : null}</section> : null}
      </div> : null}

      {activeTab === "rules" ? <div id="engine-panel-rules" role="tabpanel" aria-labelledby="engine-tab-rules" className="engine-panel">
        <div className="engine-registry-grid">
          <section className="surface" aria-labelledby="rules-heading"><div className="section-header"><div><p className="eyebrow">VERSIONED REGISTRY</p><h2 id="rules-heading">Validation rules</h2></div><span className="engine-pill">{approvedRuleCount} approved</span></div>
            {savedRules.isPending ? <StatePanel tone="loading" title="Loading rules" message="Fetching saved rule versions." /> : savedRules.isError ? <StatePanel tone="error" title="Rules unavailable" message={savedRules.error.message} /> : savedRules.data?.items.length ? <ul className="engine-registry-list">{savedRules.data.items.map((item) => <li key={item.rule_id}><div><strong>{String(item.definition.rule_type)} · {String(item.definition.field)}</strong><small>{item.rule_id} · v{item.version}</small></div><span className={`engine-pill ${item.status === "approved" ? "engine-pill-good" : ""}`}>{item.status}</span></li>)}</ul> : <StatePanel tone="empty" title="No saved rules" message="Add a configurable rule or generate a suggestion from the Profile tab." compact />}
          </section>
          <section className="surface" aria-labelledby="transform-heading"><div className="section-header"><div><p className="eyebrow">ALLOW-LISTED OPERATORS</p><h2 id="transform-heading">Transformations</h2></div><span className="engine-pill">{approvedTransformCount} approved</span></div>
            {savedTransforms.isPending ? <StatePanel tone="loading" title="Loading transformations" message="Fetching saved transformation versions." /> : savedTransforms.isError ? <StatePanel tone="error" title="Transformations unavailable" message={savedTransforms.error.message} /> : savedTransforms.data?.items.length ? <ul className="engine-registry-list">{savedTransforms.data.items.map((item) => <li key={item.transform_id}><div><strong>{String(item.definition.operator)} · {String(item.definition.field)}</strong><small>{item.transform_id} · v{item.version}</small></div><span className={`engine-pill ${item.status === "approved" ? "engine-pill-good" : ""}`}>{item.status}</span></li>)}</ul> : <StatePanel tone="empty" title="No saved transformations" message="Approve a suggested transform or add one through the API registry." compact />}
          </section>
        </div>
        <section className="surface" aria-labelledby="manual-rule-heading"><div className="section-header"><div><p className="eyebrow">CONFIGURABLE VALIDATOR</p><h2 id="manual-rule-heading">Create a rule draft</h2></div><span className="data-window-label">Drafts never run</span></div>
          <div className="engine-rule-form"><label className="select-field"><span>Rule type</span><select value={manualRuleType} onChange={(event) => setManualRuleType(event.currentTarget.value)}>{(registry.data?.rule_types ?? []).map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select></label><label className="select-field"><span>Field</span><select value={manualRuleField} onChange={(event) => setManualRuleField(event.currentTarget.value)}><option value="">Choose a source field</option>{profile?.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label><label className="engine-json-field"><span>Rule config (JSON object)</span><textarea value={manualRuleConfig} onChange={(event) => setManualRuleConfig(event.currentTarget.value)} spellCheck={false} rows={4} aria-label="Rule configuration JSON" /></label><button className="button button-primary" type="button" disabled={!manualRuleField || saveManualRule.isPending} onClick={() => saveManualRule.mutate()}>{saveManualRule.isPending ? "Saving…" : "Save as draft"}</button></div>
          <p className="engine-help"><CircleHelp size={14} aria-hidden="true" />Examples: required → <code>{'{"allow_whitespace":false}'}</code>; regex → <code>{'{"pattern":"^[A-Z]{2,3}$"}'}</code>; numeric_range → <code>{'{"minimum":0,"maximum":100}'}</code>. Available types are validated by the Python rule registry.</p>
          {saveManualRule.isError ? <p className="engine-error" role="alert">{saveManualRule.error.message}</p> : null}
          <div className="engine-registry-callout"><WandSparkles size={15} aria-hidden="true" /><span>{registry.data?.execution_safety ?? "Registry-backed rules execute as validated declarative operators."}</span></div>
        </section>
        <section className="surface" aria-labelledby="regex-test-heading"><div className="section-header"><div><p className="eyebrow">SAFE REGEX SANDBOX</p><h2 id="regex-test-heading">Test a pattern against examples</h2></div><span className="data-window-label">Backend full-match</span></div>
          <div className="engine-regex-form"><label className="engine-json-field"><span>Regex pattern</span><input value={regexPattern} onChange={(event) => setRegexPattern(event.currentTarget.value)} placeholder="^[A-Z]{2,3}$" /></label><label className="engine-json-field"><span>Values to test (one per line, up to 20)</span><textarea value={regexValues} onChange={(event) => setRegexValues(event.currentTarget.value)} rows={4} placeholder={"USD\nINR\ninvalid value"} /></label><button className="button button-secondary" type="button" disabled={!regexPattern || regexTest.isPending} onClick={() => regexTest.mutate()}>{regexTest.isPending ? "Testing…" : "Test safely"}</button></div>
          {regexTest.isError ? <p className="engine-error" role="alert">{regexTest.error.message}</p> : null}{regexTest.data ? <div className="engine-regex-result" role="status"><strong>{regexTest.data.matching_count} matched · {regexTest.data.non_matching_count} did not</strong><div>{regexTest.data.results.map((item, index) => <span className={`engine-regex-chip${item.matches ? " engine-regex-chip-match" : ""}`} key={`${item.value}-${index}`}><code>{item.value}</code> {item.matches ? "match" : "no match"}</span>)}</div></div> : null}
        </section>
      </div> : null}

      {activeTab === "plans" ? <div id="engine-panel-plans" role="tabpanel" aria-labelledby="engine-tab-plans" className="engine-panel">
        <section className="surface" aria-labelledby="dryrun-heading"><div className="section-header"><div><p className="eyebrow">REAL PYTHON ENGINE · PREVIEW ONLY</p><h2 id="dryrun-heading">Dry-run processing plan</h2></div><button className="button button-primary" type="button" disabled={dryRun.isPending} onClick={() => dryRun.mutate()}><RefreshCw size={14} aria-hidden="true" />{dryRun.isPending ? "Processing…" : "Build new preview"}</button></div>
          <p className="section-description">This executes local parsing, approved mapping operators, base validation, approved rules and registered transformations against the selected source. It stores a versioned plan and does not publish output.</p>
          {dryRun.isError ? <StatePanel tone="error" title="Dry run failed" message={dryRun.error.message} /> : null}
          {plan ? <div className="engine-plan-result"><div className="engine-plan-heading"><div><strong>Plan v{plan.version}</strong><code>{plan.plan_id}</code></div><span className="engine-pill">{plan.status}</span></div><div className="engine-plan-counts">{Object.entries(plan.dry_run.counts).map(([label, count]) => <div key={label}><span>{label}</span><strong>{count.toLocaleString()}</strong></div>)}</div><section className="engine-quality-summary" aria-label="Automatic inferred data checks"><strong>Automatic schema checks</strong><div><span>{plan.dry_run.quality_summary.columns_checked} typed columns checked</span><span>{plan.dry_run.quality_summary.type_mismatch_count} type mismatches</span><span>{plan.dry_run.quality_summary.null_value_count.toLocaleString()} blank cells observed</span></div>{plan.dry_run.quality_summary.mixed_type_columns.length ? <small>Mixed-type columns: {plan.dry_run.quality_summary.mixed_type_columns.join(", ")}</small> : null}{plan.dry_run.quality_summary.columns_with_nulls.length ? <small>Columns with blanks: {plan.dry_run.quality_summary.columns_with_nulls.slice(0, 8).map((item) => `${item.field} (${item.null_count})`).join(", ")}</small> : null}<small>Blank cells are reported here; a field is required only when a required rule is approved.</small></section><div className="engine-plan-components"><strong>Executed components</strong><ol>{plan.component_sequence.map((component) => <li key={component}>{component.replaceAll("_", " ")}</li>)}</ol></div><div className="engine-preview-table"><h3>Accepted preview · {plan.dry_run.preview.length} rows</h3>{plan.dry_run.preview.length ? <div className="table-scroll" role="region" aria-label="Dry run accepted record preview" tabIndex={0}><table className="data-table"><thead><tr><th scope="col">Source row</th>{Object.keys(plan.dry_run.preview[0].payload).slice(0, 8).map((field) => <th scope="col" key={field}>{field}</th>)}</tr></thead><tbody>{plan.dry_run.preview.map((row) => <tr key={row.source_row_number}><th scope="row">{row.source_row_number}</th>{Object.keys(plan.dry_run.preview[0].payload).slice(0, 8).map((field) => <td key={field}>{formatMetric(row.payload[field])}</td>)}</tr>)}</tbody></table></div> : <p>No accepted rows in this preview.</p>}</div>{plan.dry_run.rejection_reasons.length ? <div className="engine-rejection-summary"><strong>Rejected sample reasons</strong><ul>{plan.dry_run.rejection_reasons.map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}</ul></div> : null}</div> : <StatePanel tone="info" title="No preview run yet" message="Build a dry run to see real row counts, applied components and a small accepted-record preview." />}
        </section>
      </div> : null}

      {notice ? <p className="engine-notice" role="status">{notice}</p> : null}
      <section className="surface engine-usage-surface" aria-labelledby="ai-usage-heading"><div className="section-header"><div><p className="eyebrow">APPLICATION SPEND GUARD</p><h2 id="ai-usage-heading">Recent AI requests</h2></div><span className="data-window-label">{aiUsage.data?.total ?? 0} recorded</span></div>
        {aiStatus.data ? <p className="engine-help"><Activity size={14} aria-hidden="true" />{aiStatus.data.limits.max_input_tokens.toLocaleString()} input / {aiStatus.data.limits.max_output_tokens.toLocaleString()} output token cap · {aiStatus.data.limits.max_retries} retries · {aiStatus.data.limits.request_timeout_seconds}s timeout · cache {aiStatus.data.limits.cache_enabled ? "on" : "off"}</p> : null}
        {aiUsage.isPending ? <StatePanel tone="loading" title="Loading AI usage" message="Reading the persistent request ledger." compact /> : aiUsage.isError ? <StatePanel tone="error" title="Usage ledger unavailable" message={aiUsage.error.message} compact /> : aiUsage.data?.items.length ? <div className="table-scroll"><table className="data-table engine-usage-table"><thead><tr><th scope="col">Task</th><th scope="col">Provider / model</th><th scope="col">Status</th><th scope="col">Tokens</th><th scope="col">Estimated cost</th><th scope="col">Latency</th></tr></thead><tbody>{aiUsage.data.items.map((item) => <tr key={item.usage_id}><th scope="row">{item.task_type}</th><td>{item.provider} · {item.model}</td><td>{item.status}</td><td>{item.prompt_tokens + item.completion_tokens}</td><td>{formatMoney(item.reported_cost_usd ?? item.estimated_cost_usd)}</td><td>{item.latency_ms} ms</td></tr>)}</tbody></table></div> : <StatePanel tone="empty" title="No AI requests recorded" message="Local profiling and rule checks do not call the model. A request is made only when you ask for suggestions." compact />}
        <p className="engine-budget-disclaimer">The app reserves worst-case estimated cost against this local budget. OpenRouter can report different usage, and this local guard does not cap account billing; configure an account/provider-side spend limit too.</p>
      </section>
    </> : null}
  </div>;
}
