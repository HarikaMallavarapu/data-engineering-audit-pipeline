# Data dictionary

Status: first-slice CSV contract. Values and nullability below are enforced by `backend/app/engine/pipeline.py` and persisted by the models in `backend/app/models/`.

## General tabular pipeline

`general-tabular` accepts any flat tabular column names without applying finance-specific required fields. CSV columns remain strings; JSON scalars are serialized to CSV-compatible values, nested object keys are flattened with dot-separated names, and arrays are stored as JSON text. The pipeline rejects malformed and fully empty rows, marks exact full-row duplicates after trimming surrounding whitespace, and preserves every accepted source column. It appends `_datatrace_record_id`, `_datatrace_source_file_id`, and `_datatrace_source_row_number` columns, adding numeric suffixes if those names already exist in the source. Generic reconciliation checks disposition counts and published row counts; currency totals are not inferred from arbitrary data.

LLM schema suggestions are stored under `pipeline_run.profile.schema_analysis`. They can identify possible semantics, sensitive fields, and key columns, but remain advisory. The local fallback is deterministic. Provider requests contain column names, inferred types, null/distinct counts, and shape labels, not source cell values.

## Transaction input

| Field | Requirement | Behavior |
|---|---|---|
| `transaction_id` | Required, non-empty | Trimmed; source identity component, case-folded for duplicate matching. |
| `source_system` | Required, non-empty | Trimmed and case-folded in published output; identity component. |
| `customer_id` | Required, non-empty | Must match `customer_id` in configured customer master CSV. |
| `merchant_id` | Required, non-empty | Must match `merchant_id` in configured merchant master CSV. |
| `amount` | Required decimal | Must be finite and greater than zero; output rounded to two decimal places using half-even rounding. |
| `currency` | Required | Case-normalized; supported values are USD, EUR and INR. Totals are always grouped by currency. |
| `transaction_status` | Required | Case-normalized; supported values are authorized, settled, refunded and declined. |
| `event_time` | Required ISO timestamp with timezone | Converted to UTC ISO-8601; out-of-order timestamps are flagged in stage evidence, not rejected. |
| `settlement_id` | Optional | Preserved as trimmed text in output. |
| Other columns | Optional | Recorded as additive drift and excluded from the standardized output. |
| `ingested_at` | Backend-generated | UTC timestamp distinct from business event time. |

Rows with a wrong CSV field count are retained as malformed rejections. Physical source line numbers are stored, including the starting line of records that contain quoted newlines.

## Persistence entities implemented

| Entity | Grain and key |
|---|---|
| `pipelines` | One logical pipeline, keyed by `pipeline_id`; points to its current version number. |
| `pipeline_versions` | One immutable configuration, keyed by `pipeline_version_id`, unique by pipeline and version. |
| `source_files` | One distinct file content checksum; source ID is derived from checksum. |
| `pipeline_runs` | One deterministic execution request; idempotency key unique by pipeline-version ID plus source checksum. |
| `run_attempts` | One attempt for a run, unique by run and attempt number. |
| `stage_executions` | One named stage per attempt; stores status, row counts, duration, timestamps and JSON details. |
| `rejected_records` | One rejected source row per run attempt, with source identity, original payload, primary rule code and all reasons. |
| `duplicate_records` | One duplicate row per run attempt, with duplicate key and first accepted row number. Original bytes remain available in the retained source file. |
| `published_artifacts` | One output or quarantine artifact per run and artifact type, with path, checksum and row count. |
| `reconciliation_results` | One reconciled run, with disposition counts, per-currency totals and boolean checks. |
| `audit_events` | One append-only event, tied to a run when applicable. |

## Counting and identity

- Every parsed data row belongs to exactly one application disposition: accepted, rejected or duplicate. Schema/domain rejection happens before deduplication. Unit tests verify the three row-number sets are disjoint and cover the input.
- `input = accepted + rejected + duplicates`.
- `published = accepted` when a compatible schema is published; a missing required column blocks publication and creates a failed run.
- Duplicate identity is case-folded `source_system + transaction_id`, within a single run. A duplicate points to the first accepted source row for that key.
- Run ID and idempotency key are stable for the pipeline version and exact file checksum. A repeated request reuses the existing run and does not publish again. Each retry's rejected and duplicate rows retain their attempt ID; default quarantine and duplicate queries return the latest attempt.
- Timestamps are normalized to UTC. SQLite stores timezone-naive values and the persistence type restores UTC-aware values when reading; databases with native timezone support use timezone-aware columns. FastAPI serializes ISO timestamps and the frontend formats them in the browser locale.
- The example master files and transaction fixtures are synthetic; no real customer or payment data is included.

## Dynamic profile and processing metadata

- `schema_fingerprint`: SHA-256 of ordered column names and locally inferred types.
- `profile_sample_size`: bounded number of input rows used for sampled type/distribution/pattern analysis; null and distinct counts are exact over the configured input size.
- `SchemaProfile`: versioned mapping suggestions/decisions and source profile; only approved/edit mappings are applied to a pipeline.
- `RuleVersion` / `TransformationVersion`: immutable definition versions keyed by stable component ID plus schema fingerprint. Draft/rejected definitions do not execute.
- `ProcessingPlan`: persisted dry-run or execution component plan, with schema profile, rule/transform versions and measured row counts.
- `AIUsage`: provider/model/task, token counts, estimated and reported cost, latency, request status and cache key. It never stores API credentials.
- `AIBudget`: local configured limit, used and reserved amount, and manual reset count. It is an estimated app-side guard, separate from provider billing.

