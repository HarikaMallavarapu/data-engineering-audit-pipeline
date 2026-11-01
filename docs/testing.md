# Testing and verification

Backend tests use Pytest with an isolated SQLite database and temporary storage paths per API test. Frontend tests use Vitest, jsdom and Testing Library. Tests do not access the network or an AI provider.

## Covered behavior

- UTF-8 CSV parsing, malformed quoting, duplicate headers, field-count drift, multiline source line numbers and profiling.
- Nested JSON and JSON Lines parsing, arbitrary-column generic pipeline execution, deterministic row deduplication, lineage columns, and local LLM fallback.
- Required schema drift, additive schema drift, null/domain/reference validation, supported values and out-of-order event detection.
- Invalid-row-before-duplicate precedence and mutually exclusive accepted/rejected/duplicate dispositions.
- Deterministic normalization, source provenance, quarantine payloads and published-file contents.
- Empty input, upload type/size boundaries, status/error contract and source registration.
- Dynamic schema profiles across unfamiliar fields, dominant inferred-type validation and type-mismatch quarantine, abstract regex suggestions/safe-regex rejection, editable/approved mapping flow, rule and transform version persistence, XLSX upload and execution, persisted dry-run counts/previews, AI budget reservations/cache/fallback/exhaustion/reset, and the guarantee that ordinary pipeline runs do not call an LLM.
- Typed validation-result row accounting, duplicate-safe validator and rule-type registration, finance/general parser-format, non-empty-row, uniqueness and reconciliation per-check evidence, per-rule/per-inferred-type persistence and `NOT_APPLICABLE` handling, missing-rule configuration outcomes, exact/partial catalog filtering with file-type pagination, persisted validation history and analytics, severity-weighted score sufficiency gates, immutable baseline versioning and audit, same-pipeline comparisons, shared numeric histogram bins, minimum-sample suppression, and explicit missing catalog source behavior.
- Stable run ID, repeated and concurrent idempotency, retry attempt history, attempt-scoped rejection/duplicate evidence, failed-stage retention and persisted audit evidence.
- Row count and per-currency reconciliation, mismatches, positive version/attempt constraints, UTC timestamp round trips, source/run integrity and pipeline-version integrity.
- Frontend upload-and-run interaction, reconciliation visibility for schema-blocked runs, and visible quarantine/reconciliation request errors.

## Commands

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "backend"
backend\.venv-local\Scripts\pytest.exe backend\tests -q
backend\.venv-local\Scripts\ruff.exe check backend
Set-Location backend
.\.venv-local\Scripts\alembic.exe check
Set-Location ..\frontend
npm run test
npm run build
```

## Benchmark

`scripts/benchmark_pipeline.py` generates and processes at least 100,000 synthetic records with a fixed seed. It reports Python/OS, pandas version, elapsed time, throughput, peak traced Python memory and actual dispositions. Run:

```powershell
$env:PYTHONPATH = "backend"
backend\.venv-local\Scripts\python.exe scripts\benchmark_pipeline.py --rows 100000 --seed 20261031
```

The current Python 3.15.2 result is recorded in `docs/validation_benchmarks.md`. The 100k benchmark measures the core financial pipeline; it does not measure Excel ingestion, LLM requests, or database persistence of per-check results.

