import { useEffect, useState } from "react";
import { Activity, BookOpenCheck, Command, Download, FlaskConical, ListChecks, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "../components/common/PageHeader";
import { checkHealth } from "../services/api";
import { getValidationAnalytics, getValidationCatalog } from "../services/runService";
import type { ValidationCatalog } from "../services/runService";
import { ChallengeBlueprint } from "../features/validation/components/ChallengeBlueprint";
import { TelemetryHeader } from "../features/validation/components/TelemetryHeader";
import { ValidationCatalogTable } from "../features/validation/components/ValidationCatalogTable";

type CenterView = "library" | "blueprint";
type DiagnosticLine = { label: string; status: "OK" | "INFO" | "ERROR"; detail: string };

function csvCell(value: unknown) {
  const text = Array.isArray(value) ? value.join("; ") : value === null || value === undefined ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

async function fetchCatalogPages() {
  const first = await getValidationCatalog({ page: 1, pageSize: 100 });
  const pageCount = Math.ceil(first.total / 100);
  const rest = await Promise.all(Array.from({ length: Math.max(0, pageCount - 1) }, (_, index) => getValidationCatalog({ page: index + 2, pageSize: 100 })));
  return { ...first, items: [...first.items, ...rest.flatMap((page) => page.items)] };
}

function downloadFile(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ValidationCenter() {
  const navigate = useNavigate();
  const [view, setView] = useState<CenterView>("library");
  const [forceDemoPreview, setForceDemoPreview] = useState(false);
  const [diagnostic, setDiagnostic] = useState<DiagnosticLine[] | null>(null);
  const [diagnosticBusy, setDiagnosticBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      const typing = target instanceof HTMLElement && target.matches("input, textarea, select, [contenteditable='true']");
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      } else if (event.key === "Escape") {
        setPaletteOpen(false);
        setShortcutsOpen(false);
      } else if (event.key === "?" && !typing) {
        event.preventDefault();
        setShortcutsOpen(true);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  async function exportCatalog(format: "json" | "csv") {
    setNotice("");
    try {
      const catalog = await fetchCatalogPages();
      if (format === "json") {
        const payload = {
          source_status: catalog.source_status,
          message: catalog.message,
          total: catalog.total,
          exported_at: new Date().toISOString(),
          items: catalog.items,
        } satisfies Pick<ValidationCatalog, "source_status" | "message" | "total" | "items"> & { exported_at: string };
        downloadFile("datatrace-validation-catalog.json", JSON.stringify(payload, null, 2), "application/json");
      } else {
        const columns: Array<keyof ValidationCatalog["items"][number]> = ["validation_id", "catalog_number", "name", "description", "category", "severity", "implementation_status", "implementation_version", "test_status", "enabled", "applicability_support", "definition_source"];
        const lines = [columns.join(","), ...catalog.items.map((item) => columns.map((column) => csvCell(item[column])).join(","))];
        downloadFile("datatrace-validation-catalog.csv", lines.join("\r\n"), "text/csv;charset=utf-8");
      }
      setNotice(catalog.total ? `Exported ${catalog.total} imported catalog definition(s).` : `Export contains no definitions. Catalog status: ${catalog.source_status}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Catalog export failed.");
    }
  }

  async function runSelfDiagnostic() {
    setDiagnosticBusy(true);
    setDiagnostic(null);
    const [healthResult, catalogResult, analyticsResult] = await Promise.allSettled([
      checkHealth(),
      getValidationCatalog({ page: 1, pageSize: 1 }),
      getValidationAnalytics({ days: 30 }),
    ]);
    const lines: DiagnosticLine[] = [];
    if (healthResult.status === "fulfilled") lines.push({ label: "API health", status: "OK", detail: healthResult.value.status });
    else lines.push({ label: "API health", status: "ERROR", detail: healthResult.reason instanceof Error ? healthResult.reason.message : "Health request failed." });
    if (catalogResult.status === "fulfilled") lines.push({ label: "Catalog source", status: catalogResult.value.source_status === "READY" ? "OK" : "INFO", detail: `${catalogResult.value.source_status} · ${catalogResult.value.total} imported definitions` });
    else lines.push({ label: "Catalog source", status: "ERROR", detail: catalogResult.reason instanceof Error ? catalogResult.reason.message : "Catalog request failed." });
    if (analyticsResult.status === "fulfilled") lines.push({ label: "Validation history", status: "OK", detail: `${analyticsResult.value.total_results} persisted result(s) in the last 30 days` });
    else lines.push({ label: "Validation history", status: "ERROR", detail: analyticsResult.reason instanceof Error ? analyticsResult.reason.message : "Analytics request failed." });
    setDiagnostic(lines);
    setDiagnosticBusy(false);
  }

  function go(path: string) {
    setPaletteOpen(false);
    navigate(path);
  }

  return <div className="page-content validation-center-page">
    <nav className="validation-center-breadcrumb" aria-label="Breadcrumb"><span>Platform</span><span aria-hidden="true">/</span><strong>Validation Center &amp; Engine Specs</strong></nav>
    <PageHeader eyebrow="DATATRACE ENTERPRISE PLATFORM" title="Validation Center" description="Inspect registered validation definitions, persisted execution evidence, historical quality and the implementation blueprint." actions={<div className="validation-center-actions">
      <div className="validation-export-actions" aria-label="Export master catalog"><button type="button" className="button button-secondary button-small" onClick={() => void exportCatalog("json")}><Download size={13} aria-hidden="true" />Export JSON</button><button type="button" className="button button-secondary button-small" onClick={() => void exportCatalog("csv")}>CSV</button></div>
      <button type="button" className="button button-secondary button-small" disabled={diagnosticBusy} onClick={() => void runSelfDiagnostic()}><FlaskConical size={13} aria-hidden="true" />{diagnosticBusy ? "Checking…" : "Run self-diagnostic"}</button>
      <button type="button" className="button button-quiet button-small" onClick={() => setShortcutsOpen(true)} aria-label="Keyboard shortcuts">?<span className="shortcut-button-label">Shortcuts</span></button>
      <button type="button" className="button button-quiet button-small" onClick={() => setPaletteOpen(true)} aria-label="Open command palette"><Command size={14} aria-hidden="true" /><kbd>Ctrl K</kbd></button>
    </div>} />

    <TelemetryHeader demoPreviewCount={200} />
    {notice ? <p className="validation-center-notice" role="status">{notice}</p> : null}
    {diagnostic ? <section className="validation-diagnostic-panel" aria-label="Self-diagnostic results"><div><strong>Read-only self-diagnostic</strong><button type="button" className="table-action" onClick={() => setDiagnostic(null)}>Dismiss</button></div><ul>{diagnostic.map((line) => <li key={line.label}><span className={`diagnostic-status diagnostic-status-${line.status.toLowerCase()}`}>{line.status}</span><strong>{line.label}</strong><small>{line.detail}</small></li>)}</ul></section> : null}

    <section className="validation-center-workspace" aria-label="Validation center workspace">
      <div className="validation-center-view-toggle" role="tablist" aria-label="Validation center views">
        <button type="button" role="tab" id="validation-tab-library" aria-controls="validation-panel-library" aria-selected={view === "library"} className={view === "library" ? "validation-center-tab validation-center-tab-active" : "validation-center-tab"} onClick={() => setView("library")}><BookOpenCheck size={15} aria-hidden="true" />Validation Checks Library</button>
        <button type="button" role="tab" id="validation-tab-blueprint" aria-controls="validation-panel-blueprint" aria-selected={view === "blueprint"} className={view === "blueprint" ? "validation-center-tab validation-center-tab-active" : "validation-center-tab"} onClick={() => setView("blueprint")}><ListChecks size={15} aria-hidden="true" />Pipeline &amp; Challenge Blueprint</button>
      </div>
      {view === "library" ? <section id="validation-panel-library" role="tabpanel" aria-labelledby="validation-tab-library" className="validation-center-panel">
        <div className="validation-center-panel-heading"><div><p className="eyebrow">ENGINE CAPABILITIES &amp; RULES MATRIX</p><h2>Checks library</h2><p>Imported definitions describe available checks; only persisted run results prove a check executed.</p></div><label className="validation-demo-control"><input type="checkbox" checked={forceDemoPreview} onChange={(event) => setForceDemoPreview(event.currentTarget.checked)} /><span>Preview synthetic catalog</span></label></div>
        <ValidationCatalogTable demoPreview={forceDemoPreview} />
        <div className="validation-center-links"><button type="button" className="text-link" onClick={() => go("/validation/catalog")}>Open catalog import status <span aria-hidden="true">→</span></button><button type="button" className="text-link" onClick={() => go("/validation/results")}>Inspect persisted run results <span aria-hidden="true">→</span></button><button type="button" className="text-link" onClick={() => go("/validation/rules")}>Open Rule Studio <span aria-hidden="true">→</span></button></div>
      </section> : <section id="validation-panel-blueprint" role="tabpanel" aria-labelledby="validation-tab-blueprint" className="validation-center-panel"><div className="validation-center-panel-heading"><div><p className="eyebrow">BUSINESS REQUIREMENTS &amp; SPECIFICATIONS</p><h2>Pipeline and challenge blueprint</h2><p>Acceptance states and artifacts are grounded in the current implementation notes.</p></div><button type="button" className="button button-secondary button-small" onClick={() => void runSelfDiagnostic()}><Activity size={13} aria-hidden="true" />Refresh evidence</button></div><ChallengeBlueprint /></section>}
    </section>

    {shortcutsOpen ? <div className="validation-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShortcutsOpen(false); }}><section role="dialog" aria-modal="true" aria-labelledby="validation-shortcuts-title" className="validation-shortcuts-dialog"><div><h2 id="validation-shortcuts-title">Keyboard shortcuts</h2><button type="button" className="button button-secondary button-small" onClick={() => setShortcutsOpen(false)}>Close</button></div><dl><dt><kbd>Ctrl</kbd> + <kbd>K</kbd></dt><dd>Open the command palette</dd><dt><kbd>?</kbd></dt><dd>Show keyboard shortcuts</dd><dt><kbd>Esc</kbd></dt><dd>Close the current dialog or palette</dd></dl></section></div> : null}
    {paletteOpen ? <div className="validation-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setPaletteOpen(false); }}><section role="dialog" aria-modal="true" aria-labelledby="validation-palette-title" className="validation-command-palette"><div className="validation-palette-search"><Search size={15} aria-hidden="true" /><h2 id="validation-palette-title">Command palette</h2></div><div role="list" aria-label="Validation Center commands"><button type="button" role="listitem" onClick={() => { setView("library"); setPaletteOpen(false); }}>Show validation checks library</button><button type="button" role="listitem" onClick={() => { setView("blueprint"); setPaletteOpen(false); }}>Show pipeline and challenge blueprint</button><button type="button" role="listitem" onClick={() => go("/validation/results")}>Open run validation results</button><button type="button" role="listitem" onClick={() => go("/validation/history")}>Open validation history</button><button type="button" role="listitem" onClick={() => go("/validation/rules")}>Open Rule Studio</button><button type="button" role="listitem" onClick={() => go("/validation/baselines")}>Open baselines and drift</button><button type="button" role="listitem" onClick={() => { setPaletteOpen(false); void runSelfDiagnostic(); }}>Run read-only self-diagnostic</button></div></section></div> : null}
  </div>;
}
