import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../../components/common/PageHeader";
import { Pagination } from "../../components/common/Pagination";
import { StatePanel } from "../../components/common/StatePanel";
import { StatusBadge } from "../../components/common/StatusBadge";
import { getValidationCatalog } from "../../services/runService";
import { formatNumber } from "../../utils/format";

const PAGE_SIZE = 25;
const IMPLEMENTATION_STATUSES = ["FULLY_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "CATALOG_ONLY", "REQUIRES_INTEGRATION", "NOT_IMPLEMENTED", "DEPRECATED"];

export function ValidationCatalogPage() {
  const [search, setSearch] = useState("");
  const [validationId, setValidationId] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [enabled, setEnabled] = useState("");
  const [applicability, setApplicability] = useState("");
  const [supportedFileType, setSupportedFileType] = useState("");
  const [page, setPage] = useState(1);
  const [selectedValidationId, setSelectedValidationId] = useState<string | null>(null);
  const filters = { search, validationId, name, category, severity, status, enabled, applicability, supportedFileType };
  const catalog = useQuery({
    queryKey: ["validation-catalog", page, ...Object.values(filters)],
    queryFn: () => getValidationCatalog({
      page,
      pageSize: PAGE_SIZE,
      search,
      validationId,
      name,
      category,
      severity,
      implementationStatus: status,
      enabled: enabled === "" ? undefined : enabled === "true",
      applicability,
      supportedFileType,
    }),
  });
  const selectedDefinition = catalog.data?.items.find((item) => item.validation_id === selectedValidationId);
  const hasFilters = Object.values(filters).some(Boolean);
  const resetFilters = () => {
    setSearch("");
    setValidationId("");
    setName("");
    setCategory("");
    setSeverity("");
    setStatus("");
    setEnabled("");
    setApplicability("");
    setSupportedFileType("");
    setPage(1);
  };

  return <div className="page-content">
    <PageHeader eyebrow="VALIDATION CENTER" title="Validation catalog" description="The catalog defines available checks. An enabled definition is not evidence that a check ran." actions={<Link className="button button-secondary" to="/validation/results">Run validation results</Link>} />
    {catalog.isPending ? <StatePanel tone="loading" title="Loading validation catalog" message="Reading imported definitions from the backend." /> : null}
    {catalog.isError ? <StatePanel tone="error" title="Validation catalog unavailable" message={catalog.error.message} action={<button className="button button-secondary" onClick={() => void catalog.refetch()}>Retry</button>} /> : null}
    {catalog.data ? <section className="surface validation-catalog-surface" aria-labelledby="catalog-heading">
      <div className="section-header"><div><p className="eyebrow">SOURCE STATUS · {catalog.data.source_status.replaceAll("_", " ")}</p><h2 id="catalog-heading">Imported definitions</h2></div><span className="data-window-label">{catalog.data.source_status === "SOURCE_MISSING" || catalog.data.source_status === "NOT_IMPORTED" ? "Definition count unavailable" : `${formatNumber(catalog.data.total)} definitions match`}</span></div>
      {catalog.data.source_status === "SOURCE_MISSING" || catalog.data.source_status === "NOT_IMPORTED" ? <StatePanel tone="info" title={catalog.data.source_status === "SOURCE_MISSING" ? "Source catalogs are missing" : "Catalog has not been imported"} message={catalog.data.message ?? "No catalog data is available."} /> : <>
        {catalog.data.source_status === "PARTIAL" ? <StatePanel tone="info" title="Catalog is incomplete" message={catalog.data.message ?? "Only part of the source catalog is currently imported."} /> : null}
        <div className="validation-count-strip" aria-label="Implementation status counts">{IMPLEMENTATION_STATUSES.map((key) => <span key={key}><strong>{formatNumber(catalog.data.counts[key] ?? 0)}</strong>{key.toLowerCase().replaceAll("_", " ")}</span>)}</div>
        <div className="validation-filter-grid" aria-label="Validation catalog filters">
          <label className="search-field"><span className="visually-hidden">Search catalog</span><input value={search} onChange={(event) => { setSearch(event.currentTarget.value); setPage(1); }} placeholder="Search ID, name, description" /></label>
          <label className="catalog-text-filter"><span>Exact validation ID</span><input value={validationId} onChange={(event) => { setValidationId(event.currentTarget.value); setPage(1); }} placeholder="e.g. VAL-001" /></label>
          <label className="catalog-text-filter"><span>Name contains</span><input value={name} onChange={(event) => { setName(event.currentTarget.value); setPage(1); }} placeholder="Validation name" /></label>
          <label className="select-field"><span>Category</span><select value={category} onChange={(event) => { setCategory(event.currentTarget.value); setPage(1); }}><option value="">All categories</option>{catalog.data.filter_options.categories.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label className="select-field"><span>Severity</span><select value={severity} onChange={(event) => { setSeverity(event.currentTarget.value); setPage(1); }}><option value="">All severities</option>{catalog.data.filter_options.severities.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label className="select-field"><span>Implementation</span><select value={status} onChange={(event) => { setStatus(event.currentTarget.value); setPage(1); }}><option value="">All statuses</option>{IMPLEMENTATION_STATUSES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
          <label className="select-field"><span>Enabled state</span><select value={enabled} onChange={(event) => { setEnabled(event.currentTarget.value); setPage(1); }}><option value="">Enabled or disabled</option><option value="true">Enabled</option><option value="false">Disabled</option></select></label>
          <label className="select-field"><span>Applicability</span><select value={applicability} onChange={(event) => { setApplicability(event.currentTarget.value); setPage(1); }}><option value="">All applicability</option>{catalog.data.filter_options.applicabilities.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
          <label className="select-field"><span>Supported file type</span><select value={supportedFileType} onChange={(event) => { setSupportedFileType(event.currentTarget.value); setPage(1); }}><option value="">All file types</option>{catalog.data.filter_options.supported_file_types.map((value) => <option key={value} value={value}>{value.toUpperCase()}</option>)}</select></label>
          <button className="button button-secondary validation-filter-reset" type="button" onClick={resetFilters} disabled={!hasFilters}>Clear filters</button>
        </div>
        {catalog.data.total === 0 ? <StatePanel tone="empty" title="No definitions match this filter" message="Clear filters or import the source catalog definitions." /> : <>
          <div className="table-scroll" role="region" aria-label="Validation catalog definitions" tabIndex={0}><table className="data-table validation-results-table"><caption className="visually-hidden">Imported validation definitions</caption><thead><tr><th scope="col">ID</th><th scope="col">Validation</th><th scope="col">Category</th><th scope="col">Severity</th><th scope="col">Implementation</th><th scope="col">Applicability</th><th scope="col">Enabled</th><th scope="col">Last executed</th></tr></thead><tbody>{catalog.data.items.map((item) => <tr key={item.validation_id}><td><code>{item.validation_id}</code></td><td><button className="validation-definition-link" type="button" onClick={() => setSelectedValidationId(item.validation_id)}>{item.name}</button><small className="table-secondary">{item.description}</small></td><td>{item.category}</td><td>{item.severity}</td><td><StatusBadge status={item.implementation_status} size="small" /></td><td>{item.applicability_support.replaceAll("_", " ")}</td><td>{item.enabled ? "Enabled" : "Disabled"}</td><td>{item.last_executed_at ? new Date(item.last_executed_at).toLocaleString() : "Never"}</td></tr>)}</tbody></table></div>
          {selectedDefinition ? <section className="validation-result-detail" aria-labelledby="validation-definition-detail-heading"><div className="section-header"><div><p className="eyebrow">{selectedDefinition.validation_id} · DEFINITION DETAILS</p><h3 id="validation-definition-detail-heading">{selectedDefinition.name}</h3></div><button type="button" className="button button-secondary" onClick={() => setSelectedValidationId(null)}>Close details</button></div><p>{selectedDefinition.description}</p><dl className="validation-definition-fields"><div><dt>Required columns</dt><dd>{selectedDefinition.required_columns.join(", ") || "None specified"}</dd></div><div><dt>Required metadata</dt><dd>{selectedDefinition.required_metadata.join(", ") || "None specified"}</dd></div><div><dt>Supported file types</dt><dd>{selectedDefinition.supported_file_types.join(", ") || "None specified"}</dd></div><div><dt>Applicability requirements</dt><dd>{selectedDefinition.applicability_requirements.join("; ") || "None specified"}</dd></div><div><dt>Configuration requirements</dt><dd>{selectedDefinition.configuration_requirements.join("; ") || "None specified"}</dd></div><div><dt>Limitations</dt><dd>{selectedDefinition.limitations.join("; ") || "None recorded"}</dd></div><div><dt>Test status</dt><dd>{selectedDefinition.test_status}</dd></div><div><dt>Implementation version</dt><dd>{selectedDefinition.implementation_version}</dd></div></dl><Link className="text-link" to={`/validation/history?validation_id=${encodeURIComponent(selectedDefinition.validation_id)}`}>View historical results for this check <span aria-hidden="true">→</span></Link></section> : null}
          <Pagination page={catalog.data.page} pageSize={catalog.data.page_size} total={catalog.data.total} onPageChange={setPage} />
        </>}
      </>}
    </section> : null}
  </div>;
}
