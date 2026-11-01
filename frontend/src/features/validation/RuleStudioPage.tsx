import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Code2, History, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/common/PageHeader";
import { StatePanel } from "../../components/common/StatePanel";
import { listSources } from "../../services/sourceService";
import { getEngineRegistry, getEngineRuleHistory, listEngineRules, saveRule, testRegex } from "../../services/engineService";
import type { EngineRuleRecord } from "../../services/engineService";

const COMPARISON_OPERATORS = ["equals", "not_equals", "less_than", "less_than_or_equal", "greater_than", "greater_than_or_equal"];
const CONDITIONAL_OPERATORS = ["equals", "not_equals", "is_present", "is_missing"];
const CONDITIONAL_RULES = ["required", "regex", "numeric_range", "type"];
const CUSTOM_OPERATORS = ["is_not_empty", "equals", "not_equals", "matches", "numeric_gt", "numeric_gte", "numeric_lt", "numeric_lte"];

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function text(value: unknown) {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

export function RuleStudioPage() {
  const queryClient = useQueryClient();
  const [sourceId, setSourceId] = useState("");
  const [selectedRuleId, setSelectedRuleId] = useState("");
  const [field, setField] = useState("");
  const [ruleType, setRuleType] = useState("required");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [conditionalConfigText, setConditionalConfigText] = useState("{}");
  const [severity, setSeverity] = useState<"error" | "warning">("error");
  const [enabled, setEnabled] = useState(true);
  const [regexValues, setRegexValues] = useState("");
  const [editorError, setEditorError] = useState("");
  const [notice, setNotice] = useState("");

  const sources = useQuery({ queryKey: ["sources", "rule-studio"], queryFn: listSources });
  const source = sources.data?.items.find((item) => item.source_file_id === sourceId);
  const fingerprint = source?.schema_fingerprint ?? "";
  const registry = useQuery({ queryKey: ["engine", "registry"], queryFn: getEngineRegistry });
  const rules = useQuery({ queryKey: ["engine", "rules", fingerprint], queryFn: () => listEngineRules(fingerprint), enabled: Boolean(fingerprint) });
  const selectedRule = rules.data?.items.find((item) => item.rule_id === selectedRuleId);
  const history = useQuery({ queryKey: ["engine", "rule-history", selectedRuleId], queryFn: () => getEngineRuleHistory(selectedRuleId), enabled: Boolean(selectedRuleId) });
  const fields = useMemo(() => source?.columns ?? [], [source?.columns]);

  useEffect(() => {
    if (!selectedRule) return;
    const definition = selectedRule.definition;
    setField(text(definition.field));
    setRuleType(text(definition.rule_type) || "required");
    setConfig(record(definition.config));
    setConditionalConfigText(JSON.stringify(record(record(definition.config).then_config), null, 2));
    setSeverity(definition.severity === "warning" ? "warning" : "error");
    setEnabled(definition.enabled !== false);
    setEditorError("");
  }, [selectedRule?.rule_id, selectedRule?.version]);

  const saveDraft = useMutation({
    mutationFn: (definition: Record<string, unknown>) => saveRule(fingerprint, definition, "draft"),
    onSuccess: async (saved) => {
      setSelectedRuleId(saved.rule_id);
      setNotice(`Saved ${saved.rule_id} as draft v${saved.version}. It will not run until approved.`);
      await queryClient.invalidateQueries({ queryKey: ["engine", "rules", fingerprint] });
      await queryClient.invalidateQueries({ queryKey: ["engine", "rule-history", saved.rule_id] });
    },
  });
  const approveRule = useMutation({
    mutationFn: () => {
      if (!selectedRule) throw new Error("Select a saved draft before approving it.");
      return saveRule(fingerprint, selectedRule.definition, "approved");
    },
    onSuccess: async (saved) => {
      setNotice(`Approved ${saved.rule_id} v${saved.version}. Future runs may execute this version.`);
      await queryClient.invalidateQueries({ queryKey: ["engine", "rules", fingerprint] });
      await queryClient.invalidateQueries({ queryKey: ["engine", "rule-history", saved.rule_id] });
    },
  });
  const rejectRule = useMutation({
    mutationFn: () => {
      if (!selectedRule) throw new Error("Select a saved rule before rejecting it.");
      return saveRule(fingerprint, selectedRule.definition, "rejected");
    },
    onSuccess: async (saved) => {
      setNotice(`Saved ${saved.rule_id} as rejected v${saved.version}.`);
      await queryClient.invalidateQueries({ queryKey: ["engine", "rules", fingerprint] });
      await queryClient.invalidateQueries({ queryKey: ["engine", "rule-history", saved.rule_id] });
    },
  });
  const regexTest = useMutation({ mutationFn: () => testRegex(text(config.pattern), regexValues.split(/\r?\n/).filter((value) => value.length > 0).slice(0, 20)) });

  function createNewDraft() {
    setSelectedRuleId("");
    setField(fields[0] ?? "");
    setRuleType("required");
    setConfig({});
    setConditionalConfigText("{}");
    setSeverity("error");
    setEnabled(true);
    setEditorError("");
    setNotice("");
  }

  function updateConfig(key: string, value: unknown) {
    setConfig((current) => ({ ...current, [key]: value }));
  }

  function changeRuleType(value: string) {
    setRuleType(value);
    setConfig({});
    setConditionalConfigText("{}");
  }

  function makeDefinition() {
    if (!field.trim()) throw new Error("Choose a field for this rule.");
    let nextConfig = config;
    if (ruleType === "referential") {
      nextConfig = { ...config, allowed_values: text(config.allowed_values_text).split(/\r?\n/).map((value) => value.trim()).filter(Boolean) };
      delete nextConfig.allowed_values_text;
    }
    if (ruleType === "date_range") {
      nextConfig = { ...nextConfig, formats: text(config.formats_text).split(/\r?\n/).map((value) => value.trim()).filter(Boolean) };
      delete nextConfig.formats_text;
    }
    if (ruleType === "conditional") {
      let nested: unknown;
      try { nested = JSON.parse(conditionalConfigText); } catch { throw new Error("The nested conditional rule configuration must be valid JSON."); }
      if (!nested || typeof nested !== "object" || Array.isArray(nested)) throw new Error("The nested conditional configuration must be a JSON object.");
      nextConfig = { ...config, then_config: nested };
    }
    return {
      ...(selectedRuleId ? { rule_id: selectedRuleId } : {}),
      field: field.trim(),
      rule_type: ruleType,
      config: nextConfig,
      severity,
      enabled,
      provenance: "validation-center-rule-studio",
    };
  }

  function handleSaveDraft() {
    setEditorError("");
    try { saveDraft.mutate(makeDefinition()); } catch (error) { setEditorError(error instanceof Error ? error.message : "Rule configuration is invalid."); }
  }

  function handleApprove() {
    if (!selectedRule || selectedRule.status !== "draft") return;
    if (!window.confirm(`Approve ${selectedRule.rule_id} v${selectedRule.version}? This creates a new immutable version for future runs.`)) return;
    approveRule.mutate();
  }

  function handleReject() {
    if (!selectedRule) return;
    if (!window.confirm(`Create a rejected version of ${selectedRule.rule_id}? Existing run evidence will remain unchanged.`)) return;
    rejectRule.mutate();
  }

  return <div className="page-content">
    <PageHeader eyebrow="VALIDATION CENTER" title="Rule Studio" description="Create versioned declarative rules, test regex safely, and require explicit approval before a rule can run in future pipeline attempts." actions={<button className="button button-primary" type="button" onClick={createNewDraft}>New rule draft</button>} />
    {sources.isPending ? <StatePanel tone="loading" title="Loading source schemas" message="Rules are versioned against a registered schema fingerprint." /> : null}
    {sources.isError ? <StatePanel tone="error" title="Source schemas unavailable" message={sources.error.message} action={<button className="button button-secondary" onClick={() => void sources.refetch()}>Retry</button>} /> : null}
    {sources.data && sources.data.items.length === 0 ? <StatePanel tone="empty" title="Upload a dataset before configuring rules" message="Rule versions are scoped to an observed schema. Upload a source to discover its fields and fingerprint." action={<a className="button button-secondary" href="/sources">Open sources</a>} /> : null}
    {sources.data && sources.data.items.length > 0 ? <>
      <section className="surface rule-studio-source-bar"><label className="select-field"><span>Schema source</span><select value={sourceId} onChange={(event) => { setSourceId(event.currentTarget.value); setSelectedRuleId(""); setNotice(""); }}><option value="">Choose a source schema</option>{sources.data.items.filter((item) => item.schema_fingerprint).map((item) => <option key={item.source_file_id} value={item.source_file_id}>{item.original_filename} · {item.schema_fingerprint?.slice(0, 12)}</option>)}</select></label>{source ? <span className="data-window-label">{fields.length} fields · schema {fingerprint.slice(0, 12)}</span> : null}</section>
      {!fingerprint && !sources.isPending ? <StatePanel tone="info" title="Select a schema source" message="Choose an uploaded file to load its saved rules and available fields." /> : null}
      {fingerprint ? <>
        <section className="surface rule-studio-registry" aria-labelledby="rule-registry-title"><div className="section-header"><div><p className="eyebrow">VERSIONED RULE REGISTRY</p><h2 id="rule-registry-title">Saved rules</h2></div><span className="data-window-label">{rules.data?.total ?? 0} latest versions</span></div>
          {rules.isPending ? <StatePanel tone="loading" title="Loading rules" message="Reading the latest version for this schema." compact /> : rules.isError ? <StatePanel tone="error" title="Rules unavailable" message={rules.error.message} compact /> : rules.data?.items.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Rule</th><th scope="col">Field</th><th scope="col">Type</th><th scope="col">Version</th><th scope="col">State</th><th scope="col">Actions</th></tr></thead><tbody>{rules.data.items.map((rule) => <tr key={rule.rule_id}><td><code>{rule.rule_id}</code></td><td>{text(rule.definition.field)}</td><td>{text(rule.definition.rule_type)}</td><td>v{rule.version}</td><td><span className={`rule-studio-status rule-studio-status-${rule.status}`}>{rule.status}</span></td><td><button className="table-action" type="button" onClick={() => setSelectedRuleId(rule.rule_id)}>Inspect / edit</button></td></tr>)}</tbody></table></div> : <StatePanel tone="empty" title="No saved rules for this schema" message="Build a draft below. Draft and rejected versions do not execute." compact />}
        </section>

        <section className="surface rule-studio-editor" aria-labelledby="rule-editor-title"><div className="section-header"><div><p className="eyebrow">SAFE DECLARATIVE GRAMMAR</p><h2 id="rule-editor-title">{selectedRule ? `Rule editor · ${selectedRule.rule_id}` : "Create a rule draft"}</h2><p className="section-description">Each save creates an immutable rule version. Only registered operators execute; generated Python, SQL and shell code are never accepted.</p></div>{selectedRule ? <span className="data-window-label">Current v{selectedRule.version} · {selectedRule.status}</span> : null}</div>
          <div className="rule-studio-form">
            <label className="select-field"><span>Rule type</span><select value={ruleType} onChange={(event) => changeRuleType(event.currentTarget.value)}>{(registry.data?.rule_types ?? ["required", "type", "regex", "date_range", "numeric_range", "email", "phone", "identifier", "unique", "referential", "cross_field", "conditional", "domain", "custom"]).map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select></label>
            <label className="select-field"><span>Target field</span><select value={field} onChange={(event) => setField(event.currentTarget.value)}><option value="">Choose a source field</option>{fields.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
            <label className="select-field"><span>Severity</span><select value={severity} onChange={(event) => setSeverity(event.currentTarget.value as "error" | "warning")}><option value="error">Error</option><option value="warning">Warning</option></select></label>
            <label className="rule-studio-enabled"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.currentTarget.checked)} />Enabled in approved version</label>

            {ruleType === "required" ? <label className="rule-studio-config-field"><span>Allow whitespace-only values</span><input type="checkbox" checked={config.allow_whitespace === true} onChange={(event) => updateConfig("allow_whitespace", event.currentTarget.checked)} /></label> : null}
            {ruleType === "type" ? <label className="select-field"><span>Expected type</span><select value={text(config.expected)} onChange={(event) => updateConfig("expected", event.currentTarget.value)}><option value="">Choose expected type</option>{["string", "integer", "decimal", "boolean", "date", "datetime"].map((value) => <option key={value} value={value}>{value}</option>)}</select></label> : null}
            {ruleType === "regex" ? <><label className="rule-studio-config-field rule-studio-config-wide"><span>Safe regex pattern</span><input value={text(config.pattern)} onChange={(event) => updateConfig("pattern", event.currentTarget.value)} maxLength={256} placeholder="^[A-Z]{2,3}$" /></label><label className="rule-studio-enabled"><input type="checkbox" checked={config.full_match !== false} onChange={(event) => updateConfig("full_match", event.currentTarget.checked)} />Require full match</label></> : null}
            {ruleType === "numeric_range" ? <><label className="rule-studio-config-field"><span>Minimum</span><input type="number" value={text(config.minimum)} onChange={(event) => updateConfig("minimum", event.currentTarget.value)} /></label><label className="rule-studio-config-field"><span>Maximum</span><input type="number" value={text(config.maximum)} onChange={(event) => updateConfig("maximum", event.currentTarget.value)} /></label><label className="rule-studio-enabled"><input type="checkbox" checked={config.inclusive !== false} onChange={(event) => updateConfig("inclusive", event.currentTarget.checked)} />Inclusive bounds</label></> : null}
            {ruleType === "date_range" ? <><label className="rule-studio-config-field"><span>Minimum date/time</span><input type="text" value={text(config.minimum)} onChange={(event) => updateConfig("minimum", event.currentTarget.value)} placeholder="2026-01-01" /></label><label className="rule-studio-config-field"><span>Maximum date/time</span><input type="text" value={text(config.maximum)} onChange={(event) => updateConfig("maximum", event.currentTarget.value)} placeholder="2026-12-31" /></label><label className="rule-studio-config-field rule-studio-config-wide"><span>Accepted date formats · one per line</span><textarea rows={3} value={text(config.formats_text ?? (Array.isArray(config.formats) ? config.formats.join("\n") : ""))} onChange={(event) => updateConfig("formats_text", event.currentTarget.value)} /></label></> : null}
            {ruleType === "phone" ? <><label className="rule-studio-config-field"><span>Minimum digits</span><input type="number" value={text(config.minimum_digits)} onChange={(event) => updateConfig("minimum_digits", event.currentTarget.value)} /></label><label className="rule-studio-config-field"><span>Maximum digits</span><input type="number" value={text(config.maximum_digits)} onChange={(event) => updateConfig("maximum_digits", event.currentTarget.value)} /></label></> : null}
            {ruleType === "identifier" ? <><label className="rule-studio-config-field"><span>Minimum length</span><input type="number" value={text(config.minimum_length)} onChange={(event) => updateConfig("minimum_length", event.currentTarget.value)} /></label><label className="rule-studio-config-field"><span>Maximum length</span><input type="number" value={text(config.maximum_length)} onChange={(event) => updateConfig("maximum_length", event.currentTarget.value)} /></label><label className="rule-studio-config-field rule-studio-config-wide"><span>Optional safe pattern</span><input value={text(config.pattern)} onChange={(event) => updateConfig("pattern", event.currentTarget.value)} /></label></> : null}
            {ruleType === "referential" ? <label className="rule-studio-config-field rule-studio-config-wide"><span>Allowed reference values · one per line, up to 10,000</span><textarea rows={4} value={text(config.allowed_values_text ?? (Array.isArray(config.allowed_values) ? config.allowed_values.join("\n") : ""))} onChange={(event) => updateConfig("allowed_values_text", event.currentTarget.value)} /></label> : null}
            {ruleType === "cross_field" ? <><label className="select-field"><span>Compare with field</span><select value={text(config.other_field)} onChange={(event) => updateConfig("other_field", event.currentTarget.value)}><option value="">Choose another field</option>{fields.filter((name) => name !== field).map((name) => <option key={name} value={name}>{name}</option>)}</select></label><label className="select-field"><span>Comparison</span><select value={text(config.operator)} onChange={(event) => updateConfig("operator", event.currentTarget.value)}><option value="">Choose operator</option>{COMPARISON_OPERATORS.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label></> : null}
            {ruleType === "conditional" ? <><label className="select-field"><span>Condition field</span><select value={text(config.when_field)} onChange={(event) => updateConfig("when_field", event.currentTarget.value)}><option value="">Choose condition field</option>{fields.map((name) => <option key={name} value={name}>{name}</option>)}</select></label><label className="select-field"><span>Condition</span><select value={text(config.when_operator)} onChange={(event) => updateConfig("when_operator", event.currentTarget.value)}><option value="">Choose condition</option>{CONDITIONAL_OPERATORS.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label><label className="rule-studio-config-field"><span>Condition value</span><input value={text(config.when_value)} onChange={(event) => updateConfig("when_value", event.currentTarget.value)} /></label><label className="select-field"><span>Then apply</span><select value={text(config.then_rule)} onChange={(event) => updateConfig("then_rule", event.currentTarget.value)}><option value="">Choose rule</option>{CONDITIONAL_RULES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label><label className="rule-studio-config-field rule-studio-config-wide"><span>Nested rule config · JSON object</span><textarea rows={4} value={conditionalConfigText} onChange={(event) => setConditionalConfigText(event.currentTarget.value)} spellCheck={false} /></label></> : null}
            {ruleType === "domain" ? <label className="select-field"><span>Domain rule</span><select value={text(config.domain)} onChange={(event) => updateConfig("domain", event.currentTarget.value)}><option value="">Choose domain check</option>{["positive_number", "non_negative_number", "currency_code", "email_or_blank"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label> : null}
            {ruleType === "custom" ? <><label className="select-field"><span>Registered operator</span><select value={text(config.operator)} onChange={(event) => updateConfig("operator", event.currentTarget.value)}><option value="">Choose operator</option>{CUSTOM_OPERATORS.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label><label className="rule-studio-config-field"><span>Comparison value</span><input value={text(config.value)} onChange={(event) => updateConfig("value", event.currentTarget.value)} /></label><label className="select-field"><span>Other field · if required</span><select value={text(config.other_field)} onChange={(event) => updateConfig("other_field", event.currentTarget.value)}><option value="">None</option>{fields.filter((name) => name !== field).map((name) => <option key={name} value={name}>{name}</option>)}</select></label></> : null}

            {ruleType === "regex" ? <section className="rule-studio-regex-playground" aria-labelledby="rule-regex-playground-heading"><div><Code2 size={14} aria-hidden="true" /><h3 id="rule-regex-playground-heading">Pattern test playground</h3></div><label className="rule-studio-config-field"><span>Sample values · one per line, up to 20</span><textarea rows={3} value={regexValues} onChange={(event) => setRegexValues(event.currentTarget.value)} placeholder={"ABC\nXYZ\ninvalid value"} /></label><button className="button button-secondary button-small" type="button" disabled={!text(config.pattern) || regexTest.isPending} onClick={() => regexTest.mutate()}>{regexTest.isPending ? "Testing…" : "Test pattern safely"}</button>{regexTest.isError ? <p className="form-error" role="alert">{regexTest.error.message}</p> : null}{regexTest.data ? <ul className="rule-studio-regex-results">{regexTest.data.results.map((item, index) => <li key={`${item.value}-${index}`}><code>{item.value}</code><span className={item.matches ? "rule-match" : "rule-no-match"}>{item.matches ? "Matches" : "Does not match"}</span></li>)}</ul> : null}</section> : null}
          </div>
          <p className="engine-help"><ShieldCheck size={14} aria-hidden="true" />Rules execute in the registered pre-transformation stage when their required fields are present. Missing fields produce explicit configuration results.</p>
          {editorError ? <p className="form-error" role="alert">{editorError}</p> : null}
          {saveDraft.isError ? <p className="form-error" role="alert">{saveDraft.error.message}</p> : null}
          {approveRule.isError ? <p className="form-error" role="alert">{approveRule.error.message}</p> : null}
          {rejectRule.isError ? <p className="form-error" role="alert">{rejectRule.error.message}</p> : null}
          {notice ? <p className="form-success" role="status">{notice}</p> : null}
          <div className="rule-studio-actions"><button type="button" className="button button-primary" disabled={!fingerprint || saveDraft.isPending} onClick={handleSaveDraft}>{saveDraft.isPending ? "Saving…" : "Save new draft version"}</button><button type="button" className="button button-secondary" disabled={!selectedRule || selectedRule.status !== "draft" || approveRule.isPending} onClick={handleApprove}><Check size={14} aria-hidden="true" />Approve saved draft</button><button type="button" className="button button-quiet" disabled={!selectedRule || rejectRule.isPending} onClick={handleReject}>Reject as new version</button></div>
        </section>

        {selectedRuleId ? <section className="surface rule-studio-history" aria-labelledby="rule-history-title"><div className="section-header"><div><p className="eyebrow">IMMUTABLE CONFIGURATION HISTORY</p><h2 id="rule-history-title"><History size={15} aria-hidden="true" /> Rule versions · {selectedRuleId}</h2></div><span className="data-window-label">{history.data?.total ?? 0} versions</span></div>{history.isPending ? <StatePanel tone="loading" title="Loading rule history" message="Reading prior saved versions." compact /> : history.isError ? <StatePanel tone="error" title="Rule history unavailable" message={history.error.message} compact /> : <div className="table-scroll"><table className="data-table"><thead><tr><th scope="col">Version</th><th scope="col">State</th><th scope="col">Created</th><th scope="col">Configuration snapshot</th></tr></thead><tbody>{(history.data?.items ?? []).map((version: EngineRuleRecord) => <tr key={`${version.rule_id}-${version.version}`}><td>v{version.version}</td><td><span className={`rule-studio-status rule-studio-status-${version.status}`}>{version.status}</span></td><td>{version.created_at ? new Date(version.created_at).toLocaleString() : "Not recorded"}</td><td><details><summary>Inspect saved config</summary><pre>{JSON.stringify(version.definition, null, 2)}</pre></details></td></tr>)}</tbody></table></div>}</section> : null}
      </> : null}
    </> : null}
  </div>;
}
