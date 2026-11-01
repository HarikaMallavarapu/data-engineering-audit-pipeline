import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { ValidationCatalogItem } from "../../../services/runService";

type DrawerTab = "overview" | "configuration" | "applicability" | "evidence";

export function RuleInspectionDrawer({
  definition,
  synthetic = false,
  onClose,
}: {
  definition: ValidationCatalogItem;
  synthetic?: boolean;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<DrawerTab>("overview");
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key === "Tab") {
        const focusable = Array.from(document.querySelectorAll<HTMLElement>(
          ".rule-inspection-drawer button:not([disabled]), .rule-inspection-drawer a[href], .rule-inspection-drawer input:not([disabled]), .rule-inspection-drawer select:not([disabled]), .rule-inspection-drawer textarea:not([disabled]), .rule-inspection-drawer [tabindex]:not([tabindex='-1'])",
        ));
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus();
    };
  }, []);

  const tabs: Array<{ id: DrawerTab; label: string }> = [
    { id: "overview", label: "Overview" },
    { id: "configuration", label: "Configuration" },
    { id: "applicability", label: "Applicability" },
    { id: "evidence", label: "Test evidence" },
  ];

  return <div className="rule-drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="rule-inspection-drawer" role="dialog" aria-modal="true" aria-labelledby="rule-drawer-title">
      <header className="rule-drawer-header">
        <div><p className="eyebrow">{synthetic ? "SYNTHETIC PREVIEW" : "CATALOG DEFINITION"} · {definition.validation_id}</p><h2 id="rule-drawer-title">{definition.name}</h2><p>{definition.category} · {definition.severity}</p></div>
        <button ref={closeRef} type="button" className="button button-secondary" onClick={onClose}>Close</button>
      </header>
      <div className="rule-drawer-tabs" role="tablist" aria-label="Validation definition detail">
        {tabs.map((item) => <button key={item.id} id={`rule-drawer-tab-${item.id}`} type="button" role="tab" aria-selected={tab === item.id} aria-controls="rule-drawer-panel" className={tab === item.id ? "rule-drawer-tab rule-drawer-tab-active" : "rule-drawer-tab"} onClick={() => setTab(item.id)}>{item.label}</button>)}
      </div>
      <section id="rule-drawer-panel" role="tabpanel" aria-labelledby={`rule-drawer-tab-${tab}`} className="rule-drawer-content">
        {synthetic ? <div className="rule-drawer-demo-warning" role="note">This is a generated preview row. It is not an imported definition, executable check, or evidence of implementation.</div> : null}
        {tab === "overview" ? <>
          <div><h3>Intent</h3><p>{definition.description}</p></div>
          <div className="rule-drawer-unavailable"><h3>Detection logic and business impact</h3><p>{synthetic ? "Unavailable for synthetic rows." : "The imported catalog entry does not supply separate detection-logic or business-impact fields. No interpretation is inferred here."}</p></div>
          <dl className="validation-definition-fields"><div><dt>Category</dt><dd>{definition.category}</dd></div><div><dt>Severity</dt><dd>{definition.severity}</dd></div><div><dt>State</dt><dd>{definition.implementation_status.replaceAll("_", " ")}</dd></div><div><dt>Definition source</dt><dd>{definition.definition_source}</dd></div></dl>
        </> : null}
        {tab === "configuration" ? <>
          <div><h3>Configuration requirements</h3><ul className="rule-drawer-list">{definition.configuration_requirements.length ? definition.configuration_requirements.map((value) => <li key={value}>{value}</li>) : <li>No configuration requirements supplied.</li>}</ul></div>
          <div className="rule-drawer-code"><div><h3>Configuration schema</h3><span>Source-defined fields only</span></div><pre>{JSON.stringify({ required_columns: definition.required_columns, required_metadata: definition.required_metadata, configuration_requirements: definition.configuration_requirements }, null, 2)}</pre></div>
          <p className="inline-note">The catalog API does not provide a default configuration object or custom override schema for this definition.</p>
        </> : null}
        {tab === "applicability" ? <>
          <div><h3>Applicability conditions</h3><ul className="rule-drawer-list">{definition.applicability_requirements.length ? definition.applicability_requirements.map((value) => <li key={value}>{value}</li>) : <li>No source-defined applicability conditions supplied.</li>}</ul></div>
          <dl className="validation-definition-fields"><div><dt>Required columns</dt><dd>{definition.required_columns.join(", ") || "None supplied"}</dd></div><div><dt>Required metadata</dt><dd>{definition.required_metadata.join(", ") || "None supplied"}</dd></div><div><dt>Supported file types</dt><dd>{definition.supported_file_types.join(", ") || "None supplied"}</dd></div><div><dt>Applicability support</dt><dd>{definition.applicability_support.replaceAll("_", " ")}</dd></div></dl>
        </> : null}
        {tab === "evidence" ? <>
          <dl className="validation-definition-fields"><div><dt>Implementation version</dt><dd>{definition.implementation_version}</dd></div><div><dt>Test status</dt><dd>{definition.test_status}</dd></div><div><dt>Last execution</dt><dd>{definition.last_executed_at ? new Date(definition.last_executed_at).toLocaleString() : "No execution recorded"}</dd></div></dl>
          <div><h3>Known limitations</h3><ul className="rule-drawer-list">{definition.limitations.length ? definition.limitations.map((value) => <li key={value}>{value}</li>) : <li>No limitations supplied.</li>}</ul></div>
          {!synthetic ? <Link className="text-link" to={`/validation/history?validation_id=${encodeURIComponent(definition.validation_id)}`} onClick={onClose}>Open historical results for this check <span aria-hidden="true">→</span></Link> : <p className="inline-note">Synthetic preview rows have no historical execution records.</p>}
        </> : null}
      </section>
    </aside>
  </div>;
}
