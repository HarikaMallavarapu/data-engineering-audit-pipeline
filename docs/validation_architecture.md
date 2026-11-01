# Validation architecture

## Scope and source of truth

The requested source catalogs for checks 001–100 and 101–200 were not present in the repository or supplied attachments when this slice was implemented. The user brief contains category ranges, not individual definitions. DataTrace therefore does not seed or display invented catalog definitions. The catalog API reports `SOURCE_MISSING` until the reference files are supplied and imported.

## Implemented boundaries

- `backend/app/engine/validation/contracts.py` defines strict applicability and result contracts, including the explicit execution statuses and row-accounting invariants.
- `backend/app/engine/validation/registry.py` provides a duplicate-safe registration and lookup boundary for validator implementations. Existing pipeline validators are not yet all adapted to this registry.
- `backend/app/engine/pipeline.py` emits per-column inferred-type results for high-confidence profile types; nulls are excluded. Uncertain, unsupported, or empty columns produce `NOT_APPLICABLE` evidence instead of a zero-row pass.
- The general-tabular pipeline emits a row-uniqueness result for eligible rows, with the normalized full-row identity configuration and source row numbers only.
- The general-tabular pipeline emits parser row-format and non-empty-row results; malformed rows are counted by parser status, and empty-row checks exclude parser failures.
- `backend/app/engine/quality/rules.py` dispatches the allow-listed rule types through `RuleTypeRegistry`, evaluates approved declarative rule versions, and emits a separate result per configured rule. Missing required columns produce `REQUIRES_CONFIGURATION` results without rejecting rows or crashing the run. Failures retain source row numbers only, never raw values.
- The finance pipeline emits separate results for schema readiness, row format, required fields, positive finite amounts, supported currencies and statuses, UTC timestamps, customer/merchant references, transaction uniqueness, and event ordering. These use internal `FINANCE:*` runtime IDs.
- `backend/app/engine/reconciliation/engine.py` emits separate results for input disposition balance, published-row balance, and finance amount-total balance.
- `backend/app/services/execution_service.py` persists those results under the current `run_id` and `attempt_id`, including status, counts, duration, rule version and configuration snapshot.
- `backend/app/api/v1/validation.py` separates catalog definitions from actual run execution records.
- `backend/app/services/quality_service.py` calculates a severity-weighted run score from persisted check rows and withholds it below documented check-count and coverage thresholds. Catalog coverage remains separate from the runtime score.
- `backend/app/services/baseline_service.py` creates privacy-limited aggregate snapshots and compares row/null/duplicate rates, schema, numeric distributions, generalized value shapes, freshness, IQR outlier rates, and persisted validation failures. Numeric PSI and binned KS share baseline bucket edges; small samples are marked insufficient.
- `backend/app/api/v1/quality.py` exposes immutable, versioned baseline creation/listing and completed-run comparison. Audit events record baseline creation without source values.
- `GET /api/v1/validation/analytics` aggregates persisted outcomes and uses the same score gate for historical trend points; it does not derive check outcomes from stage state.

## Status boundaries

`PASS`, `FAIL`, `WARNING`, `ERROR`, `SKIPPED`, `NOT_APPLICABLE`, `REQUIRES_CONFIGURATION`, and `BLOCKED` are distinct. Pipeline stage success describes whether the stage executed; it is not substituted for check-level success. No quality score or coverage percentage is computed from an incomplete set of definitions.

## Current limits

Individual results are currently persisted for finance checks, general-tabular inferred-type applicability, parser row format, non-empty rows, row uniqueness, approved configurable rules, and reconciliation. File-level parse failures that stop ingestion still return an upload/parse error before a run attempt exists. Runtime scoring and baseline validation-failure comparisons use persisted results only, with catalog coverage withheld until original definitions and exact IDs are available. `FINANCE:*`, `TABULAR:*`, `RULE:*`, `PROFILED_TYPE:*`, and `RECONCILIATION:*` are internal runtime IDs; original catalog IDs cannot be mapped without the missing reference documents.

Baselines intentionally exclude raw records and raw category labels. Categorical comparison currently uses generalized value-shape buckets, so it is not a comparison of domain categories. Numeric PSI uses a deterministic bounded sample and a 100-value minimum; the binned KS distance is descriptive and has no p-value. See [baseline method and limits](validation_baselines.md).
