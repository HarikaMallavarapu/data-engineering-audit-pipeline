# DataTrace architecture

Status: finance-specific execution and a dynamic general-tabular engine are implemented. Broader product modules in the scaffold remain future work.

## Product boundary

The backend is the operational source of truth. React submits an upload and run request, then renders source metadata, run/stage statuses, disposition counts, rejection evidence and reconciliation returned by FastAPI. The browser does not calculate pipeline results.

## Implemented first slice

- **Frontend:** React 19, TypeScript, Vite 8, React Router and TanStack Query. Accessible file upload, recent runs, run status, stage table, rejected-row table and reconciliation checks.
- **API:** FastAPI `/api/v1` routes with Pydantic request/response schemas, structured errors, loopback development CORS and request correlation IDs.
- **Engine:** bounded CSV/JSON/JSON Lines/XLSX/XLSM ingestion with source row tracking; local schema/profile inference; safe-regex and declarative rule registry; versioned, user-approved mapping and transformation registries; dry-run planning; strict finance validation; schema-independent tabular validation; deterministic duplicate classification; lineage-preserving transformation; atomic file replacement and reconciliation.
- **Persistence:** SQLAlchemy and SQLite. Alembic migrations define the schema. Pipeline versions and run attempts are persisted; run, stage and positive-number checks are enforced in the database; idempotency, source-row and pipeline-version relationships are constrained.
- **Evidence:** stage executions and rejected/duplicate rows are attempt-scoped; artifacts and reconciliation results are run-scoped; audit events are append-only.
- **AI boundary:** OpenRouter/Gemini provider adapter supplies opt-in semantic suggestions. It receives compact aggregate/abstracted profile metadata, never full datasets or row values. A persistent cache and atomic local budget ledger track provider calls. Only allow-listed Python operators process records; model-generated code is never executed.

## Execution flow

1. Upload validates the supported extension, bounded size, UTF-8 source structure and unique non-empty CSV header names. DataTrace hashes and stores the exact source bytes under a server-generated name.
2. `POST /api/v1/runs` derives `run_id` and the idempotency key from the immutable pipeline-version ID and source checksum. Identical requests reuse the existing run.
3. The engine records ingestion and profiling evidence, validates the selected pipeline's schema/domain rules and assigns each record exactly one disposition. Finance checks, general-tabular inferred-type and row-uniqueness checks, approved rules, and reconciliation persist attempt-scoped validation results. AI suggestions are an explicit operator action and never occur during ordinary run execution.
4. Invalid rows are rejected before duplicate detection. Valid duplicates use case-folded `source_system + transaction_id`; accepted rows receive deterministic record IDs and retain source-file and source-row provenance.
5. Candidate output and rejected-row JSONL are written to temporary files. Counts and, for the finance pipeline, per-currency totals are reconciled before candidate files are atomically moved into their final paths.
6. Run, attempt, stage, artifact, rejection, duplicate, reconciliation and audit records are committed. Row-level rejects or duplicates produce `PARTIAL`; a required-column schema break produces `FAILED` and blocks accepted output publication.
7. A runtime `FAILED` run can be retried. The stable run ID remains, a new attempt ID is created, and completed stages plus rejected/duplicate rows remain queryable by attempt. The default quarantine and duplicate views show the latest attempt.

## Main boundaries

- API handlers validate, delegate and serialize.
- `backend/app/engine/profiling/profiler.py` describes incoming data; `backend/app/engine/quality/rules.py` validates versioned rule definitions through `RuleTypeRegistry` and emits per-rule results; `backend/app/engine/validation/` defines shared typed contracts and a registration boundary; `backend/app/engine/reconciliation/engine.py` emits dataset-level reconciliation results; `backend/app/engine/transformation/registry.py` applies deterministic allow-listed operators; `execution_service.py` coordinates stages, persistence and file operations.
- `backend/app/copilot/provider.py` requests suggestions only; `backend/app/services/ai_service.py` handles caching, budget reservations and usage evidence. The LLM never executes code or processes individual rows.
- SQLAlchemy models define persistence constraints. Alembic migrations are the schema history.
- Frontend services own HTTP calls and TypeScript contracts. Feature components render API results and accessible states.

## Deliberate first-slice limits

- Execution is synchronous in the local API request; polling supports persisted `RUNNING` states if moved behind a worker later.
- The finance pipeline keeps a fixed transaction contract. The general tabular pipeline accepts unknown flat schemas, but business semantics require approved mappings/rules. It supports CSV, JSON/JSON Lines and XLSX/XLSM; Parquet and binary document ingestion are not implemented.
- Synthetic master-reference CSVs provide local customer/merchant integrity checks. Replace those paths through environment settings for a local dataset.
- Profiling loads the upload into memory within the configured upload and row bounds. Streaming multi-GB ingestion, Parquet, binary/unstructured documents, background workers, broad lineage browsing, incidents and conversational diagnostics are not implemented. AI suggestions are advisory; deterministic code performs all row dispositions and publication.
- SQLite uses connection-level foreign-key enforcement. PostgreSQL portability is intended, but the initial migration has only been exercised on SQLite.

