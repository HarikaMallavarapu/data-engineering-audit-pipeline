# Prompt 03 — Core data engineering engine

Read `/AGENTS.md` and the data dictionary.

## Skill/agent routing
Use `code-architect` for module boundaries if available. Use `code-reviewer` after the vertical slice. Use `code-simplifier` only after behavior and tests are correct. Use `ai-regression-testing` if available to strengthen negative-case coverage.

## Files in scope
`backend/app/engine/ingestion/`, `schema_validation/`, `quality/`, `transformation/`, `publishing/`, `reconciliation/`; `scripts/generate_data.py`; `datasets/sample/`; tests under `backend/tests/`.

## Task
Implement a deterministic financial transaction pipeline:
1. Read CSV and JSON inputs safely.
2. Capture file checksum, source name, row number and ingestion timestamp.
3. Validate schema and detect added/removed/renamed/type-changed columns.
4. Apply required-field, type, amount, currency, duplicate, customer/merchant reference and settlement rules.
5. Split accepted and rejected records; rejected records retain original payload, source file, source row and rule/reason.
6. Normalize and enrich accepted records deterministically.
7. Publish output atomically where practical, using stable business keys.
8. Reconcile input = accepted + rejected + duplicates (define exact counting semantics); reconcile accepted vs published and financial aggregates.
9. Generate reproducible sample data and a configurable 100,000+ row generator using a fixed seed.

## Constraints
Keep pure transformation functions separate from I/O. Do not silently drop records. Do not invent missing references. Do not treat a duplicate as a valid newly published transaction. Do not overwrite historical run evidence.

## Tests
Happy path, empty input, malformed CSV/JSON, null required field, duplicate transaction, unsupported currency, negative/zero amount boundary, invalid customer/merchant reference, schema drift, late/out-of-order event, reconciliation mismatch, same input twice. Use deterministic fixtures.

## Acceptance
A single command runs a real pipeline and creates clean output, quarantine output and reconciliation report. Tests prove the counts and outcomes.
