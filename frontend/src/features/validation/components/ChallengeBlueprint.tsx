import { Check, CircleAlert, GitBranch } from "lucide-react";

type BlueprintStatus = "DONE" | "PARTIAL" | "BLOCKED";

const stages = ["Ingestion", "Profiling", "Quarantine", "Idempotent load", "Audit and lineage"];

const steps: Array<{ title: string; status: BlueprintStatus; summary: string; artifacts: string[]; acceptance: string }> = [
  { title: "Source documents and requirements", status: "BLOCKED", summary: "The two original validation catalogs have not been supplied.", artifacts: ["docs/validation_catalog.md", "docs/validation_implementation_matrix.md"], acceptance: "Import exact names, descriptions, categories and IDs after the source files arrive; do not infer missing definitions." },
  { title: "Validation contracts and registries", status: "PARTIAL", summary: "Typed result/applicability contracts and duplicate-safe registries exist.", artifacts: ["backend/app/engine/validation/contracts.py", "backend/app/engine/validation/registry.py"], acceptance: "Adapt each implemented validator to the shared registry contract and preserve execution-error distinctions." },
  { title: "Foundational checks", status: "PARTIAL", summary: "Finance and general-tabular pipelines persist selected checks; original catalog mapping is unresolved.", artifacts: ["backend/app/services/execution_service.py", "backend/app/engine/quality/rules.py"], acceptance: "Add source-defined checks in small groups with applicability, error cases and tests." },
  { title: "Advanced checks and integrations", status: "PARTIAL", summary: "Baseline metrics are available; streaming, geospatial and model-feature integrations remain unavailable.", artifacts: ["backend/app/services/baseline_service.py", "docs/validation_architecture.md"], acceptance: "Keep unavailable integrations explicit and only claim evidence from real connected services." },
  { title: "Dynamic applicability", status: "PARTIAL", summary: "Profiling and schema inference guide generic checks, but the entire catalog is not yet wired through applicability assessments.", artifacts: ["backend/app/engine/profiling/profiler.py", "backend/app/engine/validation/contracts.py"], acceptance: "Persist APPLICABLE, NOT_APPLICABLE and configuration/integration prerequisites for each assessed check." },
  { title: "Rule and transformation engine", status: "PARTIAL", summary: "Versioned allow-listed rules and transformations are available; the Validation Center Rule Studio is being added.", artifacts: ["backend/app/engine/quality/rules.py", "backend/app/engine/transformation/registry.py", "frontend/src/features/engine/EnginePage.tsx"], acceptance: "Keep edits versioned, approvals explicit, and execution limited to registered declarative operators." },
  { title: "Pipeline execution evidence", status: "PARTIAL", summary: "Run-attempt validation records, reconciliation and audit events persist; not all catalog checks execute.", artifacts: ["backend/app/models/__init__.py", "backend/app/services/execution_service.py"], acceptance: "Never infer per-check results from stage success; retain immutable attempt snapshots." },
  { title: "Validation APIs and frontend", status: "PARTIAL", summary: "Catalog status, run results, history, analytics, scoring and baselines are connected to API data.", artifacts: ["backend/app/api/v1/validation.py", "frontend/src/features/validation/"], acceptance: "Keep library definitions separate from actual execution results and label unavailable data." },
  { title: "Historical quality intelligence", status: "PARTIAL", summary: "Versioned baselines, guarded numeric drift, quality scoring and history analytics are implemented.", artifacts: ["backend/app/services/baseline_service.py", "docs/validation_baselines.md", "docs/validation_scoring.md"], acceptance: "Suppress unsupported statistics and treat anomalies as signals, not confirmed invalid rows." },
  { title: "Verification and submission package", status: "PARTIAL", summary: "Backend/frontend suites, migration checks and a genuine benchmark are recorded; final 200-check coverage awaits source definitions.", artifacts: ["docs/testing.md", "docs/validation_benchmarks.md", "docs/autonomous_progress.md"], acceptance: "Report exact counts, commands, benchmark measurements, migration status and remaining limits." },
];

const objectives = [
  { name: "Mandatory run tracking", status: "DONE", detail: "PipelineRun and attempt-scoped execution records" },
  { name: "Input and disposition counts", status: "DONE", detail: "Persisted run counts and reconciliation checks" },
  { name: "Schema inference", status: "DONE", detail: "Profile-backed columns, inferred types and versioned mappings" },
  { name: "Source-to-target auditability", status: "PARTIAL", detail: "Audit and row provenance exist; broad lineage browsing is not complete" },
];

const edgeCases = [
  { name: "Malformed input", status: "COVERED", evidence: "test_ingestion.py; test_pipeline_integration.py" },
  { name: "Late or out-of-order data", status: "COVERED", evidence: "test_validation.py" },
  { name: "Key collisions and duplicates", status: "COVERED", evidence: "test_validation.py; test_dynamic_engine.py" },
  { name: "Partial failures", status: "COVERED", evidence: "test_pipeline_integration.py" },
  { name: "Idempotent retries", status: "COVERED", evidence: "test_idempotency.py; test_pipeline_integration.py" },
];

const evaluation = [
  { label: "Data quality", weight: 30 },
  { label: "Architecture", weight: 20 },
  { label: "Testing", weight: 20 },
  { label: "Idempotency", weight: 15 },
  { label: "Performance", weight: 10 },
  { label: "Documentation", weight: 5 },
];

export function ChallengeBlueprint() {
  return <div className="challenge-blueprint">
    <section className="surface blueprint-flow-surface" aria-labelledby="blueprint-flow-title">
      <div className="section-header"><div><p className="eyebrow">FORWARD DEPLOYED ENGINEER CHALLENGE</p><h2 id="blueprint-flow-title">Architecture flow</h2><p className="section-description">The current local-first path from uploaded source to traceable output.</p></div><GitBranch size={18} aria-hidden="true" /></div>
      <ol className="blueprint-flow">{stages.map((stage, index) => <li key={stage}><span>{stage}</span>{index < stages.length - 1 ? <i aria-hidden="true">→</i> : null}</li>)}</ol>
      <div className="blueprint-objectives">{objectives.map((item) => <article key={item.name}><div><strong>{item.name}</strong><span className={`blueprint-state blueprint-state-${item.status.toLowerCase()}`}>{item.status}</span></div><p>{item.detail}</p></article>)}</div>
    </section>

    <section className="surface" aria-labelledby="blueprint-steps-title">
      <div className="section-header"><div><p className="eyebrow">10-STEP IMPLEMENTATION MATRIX</p><h2 id="blueprint-steps-title">Acceptance and code artifacts</h2></div><span className="data-window-label">Source-backed status</span></div>
      <div className="blueprint-step-list">{steps.map((step, index) => <details className="blueprint-step" key={step.title}><summary><span className="blueprint-step-number">{String(index + 1).padStart(2, "0")}</span><span className="blueprint-step-copy"><strong>{step.title}</strong><small>{step.summary}</small></span><span className={`blueprint-state blueprint-state-${step.status.toLowerCase()}`}>{step.status}</span></summary><div className="blueprint-step-detail"><p><strong>Acceptance:</strong> {step.acceptance}</p><div><strong>Code artifacts</strong><ul>{step.artifacts.map((artifact) => <li key={artifact}><code>{artifact}</code></li>)}</ul></div></div></details>)}</div>
    </section>

    <div className="blueprint-bottom-grid">
      <section className="surface" aria-labelledby="blueprint-edges-title"><div className="section-header"><div><p className="eyebrow">TEST EVIDENCE</p><h2 id="blueprint-edges-title">Edge-case coverage</h2></div><Check size={16} aria-hidden="true" /></div><ul className="blueprint-edge-list">{edgeCases.map((item) => <li key={item.name}><span><strong>{item.name}</strong><small>{item.evidence}</small></span><span className="blueprint-state blueprint-state-done">{item.status}</span></li>)}</ul><p className="inline-note">Coverage labels point to named tests; this is not a code-coverage percentage.</p></section>
      <section className="surface" aria-labelledby="blueprint-evaluation-title"><div className="section-header"><div><p className="eyebrow">CHALLENGE EVALUATION</p><h2 id="blueprint-evaluation-title">Scoring weights</h2></div><CircleAlert size={16} aria-hidden="true" /></div><ul className="blueprint-evaluation-list">{evaluation.map((item) => <li key={item.label}><span>{item.label}</span><span className="blueprint-weight-track" aria-hidden="true"><i style={{ width: `${item.weight / 30 * 100}%` }} /></span><strong>{item.weight}%</strong></li>)}</ul><p className="inline-note">These are the challenge weights from the supplied brief, not a DataTrace quality score.</p></section>
    </div>
  </div>;
}
