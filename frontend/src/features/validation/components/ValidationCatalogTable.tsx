import { useDeferredValue, useMemo, useState } from "react";
import { Copy, Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Pagination } from "../../../components/common/Pagination";
import { StatePanel } from "../../../components/common/StatePanel";
import { StatusBadge } from "../../../components/common/StatusBadge";
import { getValidationCatalog } from "../../../services/runService";
import type { ValidationCatalog, ValidationCatalogItem } from "../../../services/runService";
import { formatNumber } from "../../../utils/format";
import { RuleInspectionDrawer } from "./RuleInspectionDrawer";

const PAGE_SIZE = 50;
const STATUSES = ["FULLY_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "CATALOG_ONLY", "REQUIRES_INTEGRATION", "NOT_IMPLEMENTED", "DEPRECATED"] as const;

function syntheticCatalog(): ValidationCatalog {
  const items: ValidationCatalogItem[] = Array.from({ length: 200 }, (_, index) => {
    const catalogNumber = index + 1;
    const validationId = `VAL-${String(catalogNumber).padStart(3, "0")}`;
    return {
      validation_id: validationId,
      catalog_number: catalogNumber,
      name: `Synthetic preview check ${validationId}`,
      description: "Generated demo placeholder. The original validation definition is unavailable and this row is not executable.",
      category: "Preview only",
      severity: "Not supplied",
      applicability_requirements: [],
      required_columns: [],
      required_metadata: [],
      configuration_requirements: [],
      implementation_status: "PREVIEW_ONLY",
      implementation_version: "preview-only",
      test_status: "NOT_RUN",
      limitations: ["Synthetic placeholder. Not imported, not registered, and not executed."],
      enabled: false,
      supported_file_types: [],
      applicability_support: "NOT_ASSESSED",
      definition_source: "Synthetic preview only",
      last_executed_at: null,
    };
  });
  return {
    source_status: "SOURCE_MISSING",
    message: "Synthetic preview only. The source catalogs were not imported.",
    counts: {},
    filter_options: { categories: ["Preview only"], severities: ["Not supplied"], applicabilities: ["NOT_ASSESSED"], supported_file_types: [] },
    items,
    total: items.length,
    page: 1,
    page_size: PAGE_SIZE,
  };
}

async function getWholeCatalog(): Promise<ValidationCatalog> {
  const first = await getValidationCatalog({ page: 1, pageSize: 100 });
  if (first.total <= first.items.length) return first;
  const pageCount = Math.ceil(first.total / 100);
  const remaining = await Promise.all(Array.from({ length: pageCount - 1 }, (_, index) => getValidationCatalog({ page: index + 2, pageSize: 100 })));
  return { ...first, items: [...first.items, ...remaining.flatMap((page) => page.items)] };
}

function regexIsUnsafe(pattern: string) {
  return pattern.length > 128
    || /\\[1-9]|\(\?[=!<]/.test(pattern)
    || /\([^)]*[+*{][^)]*\)[+*{]/.test(pattern)
    || /\([^)]*\|[^)]*\)[+*{]/.test(pattern)
    // Keep free-form search bounded to a linear-time subset of JavaScript regex.
    || (pattern.match(/[*+?]|\{\d+(?:,\d*)?\}/g)?.length ?? 0) > 1;
}

function matchesSearch(item: ValidationCatalogItem, query: string) {
  const fields = [item.validation_id, item.name, item.description, item.category, item.severity, item.implementation_status].join(" ");
  const trimmed = query.trim();
  if (!trimmed) return true;
  if (trimmed.startsWith("/") && trimmed.endsWith("/") && trimmed.length > 2) {
    const source = trimmed.slice(1, -1);
    if (regexIsUnsafe(source)) return false;
    try { return new RegExp(source, "i").test(fields); } catch { return false; }
  }
  return trimmed.toLocaleLowerCase().split(/\s+/).every((token) => fields.toLocaleLowerCase().includes(token));
}

function MultiSelect({ label, values, selected, onChange }: { label: string; values: string[]; selected: string[]; onChange: (values: string[]) => void }) {
  return <label className="validation-library-filter"><span>{label}</span><select multiple value={selected} onChange={(event) => onChange(Array.from(event.currentTarget.selectedOptions, (option) => option.value))} aria-label={label}>{values.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>;
}

export function ValidationCatalogTable({ demoPreview = false }: { demoPreview?: boolean }) {
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [severities, setSeverities] = useState<string[]>([]);
  const [view, setView] = useState<"table" | "grid">("table");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ValidationCatalogItem | null>(null);
  const [copiedId, setCopiedId] = useState("");
  const deferredSearch = useDeferredValue(search);
  const catalog = useQuery({ queryKey: ["validation-catalog", "control-plane"], queryFn: getWholeCatalog, refetchInterval: 30_000 });
  const sourceMissing = catalog.data?.source_status === "SOURCE_MISSING" || catalog.data?.source_status === "NOT_IMPORTED";
  const usingDemo = demoPreview || (sourceMissing && !catalog.data?.items.length);
  const displayCatalog = useMemo(() => {
    if (demoPreview || (usingDemo && !catalog.data?.items.length)) return syntheticCatalog();
    return catalog.data;
  }, [catalog.data, demoPreview, usingDemo]);
  const availableCategories = displayCatalog?.filter_options.categories ?? [];
  const availableStatuses = Object.keys(displayCatalog?.counts ?? {}).filter((item) => STATUSES.includes(item as typeof STATUSES[number]));
  const availableSeverities = displayCatalog?.filter_options.severities ?? [];
  const filteredItems = useMemo(() => (displayCatalog?.items ?? []).filter((item) =>
    matchesSearch(item, deferredSearch)
      && (!categories.length || categories.includes(item.category))
      && (!statuses.length || statuses.includes(item.implementation_status))
      && (!severities.length || severities.includes(item.severity)),
  ), [categories, deferredSearch, displayCatalog, severities, statuses]);
  const pageItems = filteredItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const filtersApplied = Boolean(search || categories.length || statuses.length || severities.length);

  if (catalog.isPending) return <StatePanel tone="loading" title="Loading validation library" message="Fetching imported definitions and implementation states." />;
  if (catalog.isError) return <StatePanel tone="error" title="Validation library unavailable" message={catalog.error.message} action={<button className="button button-secondary" onClick={() => void catalog.refetch()}>Retry</button>} />;
  if (!displayCatalog) return null;

  return <div className="validation-library-workspace">
    {usingDemo ? <div className="validation-demo-banner" role="note"><strong>Synthetic preview data</strong><span>These 200 placeholder IDs are generated only to preview the interface. They are not imported definitions, do not represent implementation coverage, and cannot be executed.</span></div> : null}
    {displayCatalog.source_status === "PARTIAL" ? <StatePanel tone="info" title="Catalog import is partial" message={displayCatalog.message ?? "Only the imported database definitions are shown."} compact /> : null}
    {!usingDemo && sourceMissing ? <StatePanel tone="info" title="Source catalog is missing" message={displayCatalog.message ?? "No original definitions are loaded."} compact /> : null}

    <div className="validation-library-toolbar">
      <label className="validation-library-search"><Search size={15} aria-hidden="true" /><span className="visually-hidden">Search validation library</span><input value={search} onChange={(event) => { setSearch(event.currentTarget.value); setPage(1); }} placeholder="Search IDs, names, intent, tags · use /pattern/ for regex" /></label>
      <MultiSelect label="Categories" values={availableCategories} selected={categories} onChange={(value) => { setCategories(value); setPage(1); }} />
      <MultiSelect label="Implementation state" values={availableStatuses} selected={statuses} onChange={(value) => { setStatuses(value); setPage(1); }} />
      <MultiSelect label="Severity" values={availableSeverities} selected={severities} onChange={(value) => { setSeverities(value); setPage(1); }} />
      <div className="validation-view-toggle" role="group" aria-label="Catalog view mode"><button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>Table</button><button type="button" aria-pressed={view === "grid"} onClick={() => setView("grid")}>Cards</button></div>
    </div>
    <div className="validation-library-summary"><span><strong>{formatNumber(displayCatalog.total)}</strong> {usingDemo ? "preview rows" : "registered definitions"}</span><span>{formatNumber(filteredItems.length)} shown</span><span>{usingDemo ? "No execution evidence is attached to preview rows." : "Last execution and test evidence come from the catalog API."}</span></div>

    {filteredItems.length === 0 ? <StatePanel tone="empty" title={filtersApplied ? "No checks match these filters" : "No catalog definitions available"} message={filtersApplied ? "Clear a category, state, severity or search filter." : "Import the supplied source catalog to populate the live library."} /> : view === "table" ? <div className="table-scroll validation-matrix-scroll" role="region" aria-label="Validation check matrix" tabIndex={0}><table className="data-table validation-matrix-table"><caption className="visually-hidden">Validation checks and implementation metadata</caption><thead><tr><th scope="col">Check ID</th><th scope="col">Validation name and intent</th><th scope="col">Category</th><th scope="col">Severity</th><th scope="col">Execution stage</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead><tbody>{pageItems.map((item) => <tr key={item.validation_id}><td><button type="button" className="validation-id-copy" onClick={() => { void navigator.clipboard?.writeText(item.validation_id).catch(() => undefined); setCopiedId(item.validation_id); }} title="Copy validation ID"><code>{item.validation_id}</code><Copy size={12} aria-hidden="true" /><span className="visually-hidden">Copy {item.validation_id}</span></button>{copiedId === item.validation_id ? <small className="validation-copy-note">Copied</small> : null}</td><td><button type="button" className="validation-definition-link" onClick={() => setSelected(item)}>{item.name}</button><small className="table-secondary">{item.description}</small></td><td><span className="validation-taxonomy-pill">{item.category}</span></td><td><span className={`validation-severity validation-severity-${item.severity.toLowerCase()}`}>{item.severity}</span></td><td><span className="validation-stage-pill">{String((item as ValidationCatalogItem & { execution_stage?: string }).execution_stage ?? "Not supplied")}</span></td><td><StatusBadge status={item.implementation_status} size="small" /></td><td><button type="button" className="table-action" onClick={() => setSelected(item)}>Inspect</button></td></tr>)}</tbody></table></div> : <div className="validation-library-grid">{pageItems.map((item) => <article className="validation-library-card" key={item.validation_id}><div className="validation-library-card-head"><code>{item.validation_id}</code><span className={`validation-severity validation-severity-${item.severity.toLowerCase()}`}>{item.severity}</span></div><button type="button" className="validation-definition-link" onClick={() => setSelected(item)}>{item.name}</button><p>{item.description}</p><div><span className="validation-taxonomy-pill">{item.category}</span><StatusBadge status={item.implementation_status} size="small" /></div><button type="button" className="text-link" onClick={() => setSelected(item)}>Open inspection <span aria-hidden="true">→</span></button></article>)}</div>}

    {filteredItems.length ? <Pagination page={page} pageSize={PAGE_SIZE} total={filteredItems.length} onPageChange={setPage} /> : null}
    {selected ? <RuleInspectionDrawer definition={selected} synthetic={usingDemo} onClose={() => setSelected(null)} /> : null}
  </div>;
}
