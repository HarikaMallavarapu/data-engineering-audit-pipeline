# API reference

All implemented routes are under `/api/v1` except `/health`. FastAPI publishes OpenAPI at `/docs`. The application returns `{ "error": { "code": "...", "message": "..." } }` for application and request-validation errors. Unexpected errors return a generic message; stack traces remain server-side.

Validation Center catalog and run-result APIs are documented in [validation_api.md](validation_api.md). The catalog reports its source availability explicitly; the 200 definitions are not seeded until the two original reference catalogs are supplied.

## Implemented endpoints

| Method | Route | Contract |
|---|---|---|
| GET | `/health` | `{ "status": "ok" }` |
| GET | `/api/v1/version` | `{ "name": "DataTrace API", "version": "0.1.0" }`, derived from the running FastAPI application metadata. |
| GET | `/api/v1/pipelines` | Array of `{pipeline_id, name, version}`; `financial-transactions` and `general-tabular` are seeded at startup. |
| POST | `/api/v1/sources/upload` | Multipart field `file`; UTF-8 CSV, JSON object/array, JSON Lines (`.jsonl`), or NDJSON. Returns source ID, original filename, checksum, size, detected columns and upload time. |
| GET | `/api/v1/sources` | `{items, total}` source metadata. |
| POST | `/api/v1/runs` | JSON `{ "source_file_id": "src_…", "pipeline_id": "general-tabular" }`; `pipeline_id` defaults to `financial-transactions` for backward compatibility. Returns persisted run and stage results. |
| GET | `/api/v1/runs?page=1&page_size=25` | Paginated recent run records. Page size is capped at 100. |
| GET | `/api/v1/runs/{run_id}` | Run status, counts, profile, error and stage evidence. |
| POST | `/api/v1/runs/{run_id}/retry` | Starts a new attempt for a runtime-failed run. Schema-incompatible and non-failed runs return 409. |
| GET | `/api/v1/quarantine?run_id=…&attempt_id=…&page=1&page_size=25` | Rejected payload, source row, attempt ID, rule code and rejection reasons. Without `attempt_id`, returns the latest attempt per run. |
| GET | `/api/v1/duplicates?run_id=…&attempt_id=…&page=1&page_size=25` | Duplicate source row, attempt ID, first accepted row and normalized duplicate key. Without `attempt_id`, returns the latest attempt per run. |
| GET | `/api/v1/reconciliation/{run_id}` | Persisted disposition counts, per-currency accepted/published totals and checks. |
| GET | `/api/v1/audit?run_id=…&page=1&page_size=25` | Append-only run event history. |
| GET | `/api/v1/engine/sources/{source_file_id}/profile` | Persisted local data profile, schema fingerprint, exact null/distinct counts and sampled statistics/patterns. |
| POST | `/api/v1/engine/sources/{source_file_id}/suggestions` | Opt-in schema/rule/transform suggestions. Uses cached, budgeted provider inference or labeled local fallback; persists a draft schema profile. |
| GET | `/api/v1/engine/schema-profiles?source_file_id=…` | Versioned profile/mapping suggestions and approval states. |
| POST | `/api/v1/engine/schema-profiles/{profile_id}/approve` | Save an explicit approve/edit/reject decision as a new schema profile version. |
| GET | `/api/v1/engine/schema-drift?left_source_file_id=…&right_source_file_id=…` | Compare added/missing columns and type conflicts for two uploaded sources. |
| GET | `/api/v1/engine/registry` | Allow-listed rule types, transformation operators, and execution safety contract. |
| GET/POST/PUT | `/api/v1/engine/rules` | List or version configurable rule definitions by schema fingerprint. New rules default to drafts; only approved rules execute. |
| POST | `/api/v1/engine/rules/test-regex` | Validate a bounded regex against at most 20 strings (1,024 chars each); unsafe constructs are rejected. |
| GET/POST/PUT | `/api/v1/engine/transformations` | List or version allow-listed transformations by schema fingerprint. Only approved transformations execute. |
| POST | `/api/v1/engine/plans` | Build and persist a real local dry-run plan with disposition counts, inferred-type/null quality summary, component sequence, and a small preview. Never publishes output. Optional AI suggestions are budgeted. |
| GET | `/api/v1/ai/status`, `/api/v1/ai/usage?page=…`, `/api/v1/ai/budget` | Provider status without secrets, paginated usage ledger and local spend counters. |
| POST | `/api/v1/ai/budget/reset` | Reset the local ledger with `{ "confirmation": "RESET_AI_BUDGET" }`; it does not reset provider billing. |
| DELETE | `/api/v1/ai/cache` | Clear cached inference responses. |

The `attempt_id` filter on quarantine and duplicate endpoints allows inspection of earlier retry outcomes. Omitting it preserves the existing UI behavior by returning only the latest attempt for each run.

## Upload and run rules

- Maximum upload size defaults to 10 MiB and is configurable with `MAX_UPLOAD_BYTES`.
- `general-tabular` accepts user-defined columns and preserves source values. It supports CSV, JSON, JSON Lines/NDJSON and XLSX/XLSM; profiles exact null/distinct counts plus bounded sampled statistics/patterns; checks nonblank values against high-confidence inferred types; reports nulls/mixed types; quarantines malformed, empty and incompatible values; and records exact full-row duplicates after trimming text cells. Approved schema mappings, rules and transforms run through deterministic allow-listed Python operators. It adds deterministic `_datatrace_*` row lineage columns to published CSV. There are no assumed domain-specific required columns.
- `financial-transactions` keeps the strict transaction contract below. Select `general-tabular` for unrelated datasets; missing finance-specific columns correctly block the finance pipeline.
- AI requests are opt-in through suggestion/plan actions; normal execution does not contact an LLM. Configure provider keys in `backend/.env`. Only headers, inferred types, null/distinct counts, aggregate statistics, value-shape labels and abstracted sample patterns are sent; source cell values and file paths are not sent. The app reserves against `$1.00` by default using configured model pricing/token caps and records usage. Provider errors use deterministic local suggestions, and do not block validation. The local ledger does not limit account-level provider spending.
- Upload storage names derive from the full SHA-256 checksum; the client filename is retained as metadata and never used as a path.
- Required transaction columns: `transaction_id`, `source_system`, `customer_id`, `merchant_id`, `amount`, `currency`, `transaction_status`, `event_time`. `settlement_id` is optional; other extra columns are classified as additive drift.
- Amounts must be numeric and greater than zero. Currencies are limited to USD, EUR and INR. Status values are authorized, settled, refunded or declined. Event time must include a timezone. Customer and merchant references must exist in the configured master CSVs.
- Duplicate identity is case-insensitive `source_system + transaction_id`, scoped to one run. Validation rejects invalid rows before duplicate classification.
- Counts are mutually exclusive: `input = accepted + rejected + duplicates`; `published = accepted` when publication is not blocked. Amount totals are compared within each currency.
- Run idempotency is permanent for one pipeline version and exact source checksum in the local database. Generic schema-inference provider/model are included so enabling a provider after a local fallback can create a new run; the secret key value is not part of the key.

## Error codes

`unsupported_file_type`, `file_too_large`, `invalid_csv`, `invalid_json`, `source_not_found`, `pipeline_not_found`, `pipeline_version_missing`, `run_not_found`, `run_not_retryable`, `reconciliation_not_found`, `validation_error`, and `internal_error`.

