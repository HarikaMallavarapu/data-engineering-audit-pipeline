# Database design

Status: the first CSV pipeline persistence slice is implemented. SQLAlchemy models and Alembic migrations are in `backend/app/models/` and `backend/migrations/`.

## Implemented tables

- pipelines and pipeline_versions
- source_files
- pipeline_runs, run_attempts, and stage_executions
- rejected_records and duplicate_records, each linked to a specific run attempt
- published_artifacts
- audit_events
- reconciliation_results
- schema_profiles (versioned mappings and suggestions)
- rule_versions and transformation_versions (immutable definitions and approval state)
- processing_plans (persisted dry-run/run plan versions)
- ai_budgets, ai_usage and ai_cache (application budget, spend/request ledger and profile-keyed response cache)
- validation_definitions (imported catalog definitions; currently empty because the source catalogs are missing)
- validation_executions (per-check result/configuration snapshots scoped to a run attempt)

## Remaining persistence gaps

Finance checks, approved rules, confident inferred-type checks, general-tabular row uniqueness, and reconciliation checks are persisted as attempt-scoped validation executions. The runtime IDs are internal and cannot be mapped to original catalog checks without the missing source documents. Parser integrity, record-level lineage edges, and incidents are not fully represented as individual persisted checks/entities.

## Implemented relationship chain

Pipeline → pipeline version → run → source file and attempts → stage executions. Each attempt may also have its own rejected and duplicate rows. Runs own published artifacts, reconciliation results and audit events.

## Key and constraint decisions

- Give every run a stable run_id and every retry a distinct attempt record.
- Keep configuration versions immutable after a run references them.
- Enforce idempotency with a database unique constraint on the deterministic execution key; frontend checks are not sufficient.
- Define stable record identity from source_system and business keys, and keep source row number as provenance rather than as the business key.
- Use foreign keys and deliberate cascade behavior. Do not cascade-delete append-only audit evidence.
- A run's pipeline version is protected by a composite foreign key so `pipeline_id` and `pipeline_version_id` must refer to the same pipeline.
- Rejected rows reference the same source file as their run through a composite foreign key.
- Rejected and duplicate rows reference the run and attempt together; uniqueness is scoped to attempt and source row so retry evidence is retained.
- Run and stage statuses have database check constraints.
- Keep audit_events append-only at the service boundary.
- Store timestamps in UTC and money values with decimal-safe types.
- Preserve prior attempts, including their stage and row-disposition evidence, when retrying.
- Publish in a transaction or through an atomic file replacement where practical; mark partial output explicitly if atomic publication is not possible.

## First-slice disposition and retry semantics

- Duplicate scope is one pipeline run. The identity is case-folded `source_system + transaction_id`.
- The engine rejects schema/domain-invalid rows before duplicate detection. Each row is classified exactly once in the tested application path. Rejected rows and duplicate rows are persisted separately; the validator tests that their source row numbers do not overlap.
- Added columns are recorded as additive schema drift and do not block the first pipeline; missing required columns are blocking, each source row is retained as rejected evidence, and publishing is skipped.
- Idempotency is unique for a pipeline version and exact source checksum for the lifetime of the local database. No configurable execution parameters exist in the first slice.
- Reconciliation stores row counts and decimal totals grouped by currency; totals across different currencies are never added together.
- A retry reuses the stable run ID and creates a new `run_attempts` row. Stage names and row dispositions are unique per attempt, preserving earlier stage evidence. Quarantine and duplicate queries default to the latest attempt and accept an `attempt_id` filter for historical evidence. Only runtime-failed attempts are retryable; a schema-incompatible source must be corrected and uploaded again.

## Migration approach

Use SQLAlchemy models and a migration tool. SQLite is the local database. Keep types and constraints portable where practical, and document any SQLite/PostgreSQL differences when a migration is added. Tests must use isolated temporary databases.

The local migrations target SQLite. SQLite enables foreign-key enforcement for application connections; the Alembic environment temporarily disables it during batch table rebuilds and re-enables it afterward. Existing disposition rows are attributed to the latest recorded attempt during migration. Earlier classifications already deleted by pre-migration retries cannot be reconstructed; retries after this migration retain their attempt-specific rows. The attempt-disposition migration refuses downgrade once the same source row has evidence in multiple attempts, because the older schema cannot retain both rows. JSON fields use SQLAlchemy's JSON type; keep future PostgreSQL migrations reviewed for provider-specific differences. Audit rows have no delete route and are append-only at the application service boundary.
