# Validation API

All routes use the existing `/api/v1` router and standard application error envelope.

## Catalog

- `GET /api/v1/validation/catalog`: paginated catalog definitions with text search, exact validation ID, partial name, category, severity, implementation status, enabled state, applicability, and supported file type filters. JSON file-type membership is applied to the bounded imported catalog, so `total` and page results describe the complete combined filter. The response includes database-derived implementation counts and distinct category, severity, applicability, and file-type options for the UI.
- `GET /api/v1/validation/catalog/{validation_id}`: retrieve an imported definition and its latest execution timestamp. Unknown IDs return `404`.

## Run execution records

- `GET /api/v1/validation/runs/{run_id}`: paginated results for the latest run attempt by default. Supports `attempt_id`, `status`, `severity`, `category`, and `validation_id` filters. The summary is derived from persisted result rows for the selected attempt.
- `GET /api/v1/validation/history`: paginated persisted executions across runs and attempts. Supports text search, validation ID, category, status, pipeline, source file, and creation-date range filters; results include the run, dataset filename, pipeline, and attempt number.
- `GET /api/v1/quality/runs/{run_id}/score`: transparent score over the selected/latest attempt's persisted runtime checks. It returns insufficiency reasons instead of a score when fewer than three checks executed or eligible-result coverage is below 80%. Catalog-wide coverage remains `null` until all 200 definitions are imported and exact IDs are assessed.
- `POST /api/v1/quality/baselines`: create the next immutable baseline version for a completed run. Accepts `run_id`, optional `attempt_id`, and optional `dataset_identity`; the default identity combines pipeline ID and source filename stem.
- `GET /api/v1/quality/baselines`: list versioned baselines, optionally filtered by exact `dataset_identity` and `pipeline_id`.
- `GET /api/v1/quality/baselines/{baseline_id}/compare?run_id=...`: compare a completed attempt with a baseline from the same pipeline. Optional `attempt_id` selects a specific run attempt. Numeric PSI and binned KS are omitted below 100 sampled numeric values in either observation.
- `GET /api/v1/validation/analytics`: persisted status, critical failure, configuration, category, check-frequency, daily execution and quality-score trends for a 1–365 day window. Quality trends include up to the latest 30 attempts and omit attempts that fail the score sufficiency gate.
- The API does not compute coverage, quality scores, `NOT_APPLICABLE`, or missing-configuration counts from definitions that have no result record.

Baseline create and compare return `404` for unknown run, attempt, or baseline IDs; `409` for incomplete attempts, unavailable sources, concurrent version conflicts, or a pipeline mismatch; and `422` when a registered source file fails checksum or parsing checks. Baselines contain aggregate snapshots and no raw rows or raw category values. The `confirmed_invalid_records` comparison field is always `false`; anomalies are review signals.

Definitions and executions use distinct endpoints and response shapes. A configured rule execution ID such as `RULE:amount_floor` is not an original catalog ID.
