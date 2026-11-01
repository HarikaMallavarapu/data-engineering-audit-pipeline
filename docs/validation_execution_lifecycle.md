# Validation execution lifecycle

1. The existing pipeline ingests and profiles a source, resolves approved schema mappings/rules/transforms, then performs deterministic validation.
2. Finance checks, general-tabular parser row-format, non-empty-row, inferred-type and row-uniqueness checks, and approved rules emit separate typed results during validation. Uncertain or empty inferred types are `NOT_APPLICABLE`; missing rule dependencies are `REQUIRES_CONFIGURATION`. Finance and generic-tabular checks use internal IDs, not original catalog IDs.
3. Failure examples retain source row numbers only. Raw values are not copied into validation execution records.
4. The reconciliation engine emits separate results for input dispositions, published row counts, and finance amount totals where applicable. A failed pre-publish reconciliation is persisted with its failed stage before the run exits.
5. Each result stores its run and attempt IDs, applicability, status/severity, execution stage, counts, affected columns, configuration snapshot, rule version, timestamp and measured duration.
6. The result rows commit with their stage and remain scoped to the attempt. A retry creates a new attempt and does not overwrite prior results.
7. `GET /api/v1/validation/runs/{run_id}` returns the latest attempt by default. It accepts an explicit `attempt_id` for historical inspection.
8. `GET /api/v1/validation/history` provides a paginated cross-run view joined to the source file, pipeline, and attempt number. The history page links each row back to the exact persisted attempt.

A successful pipeline stage is not reported as a collection of passed checks. File-level parse errors that prevent creation of a run are returned as ingestion errors and do not have run-scoped validation records.
