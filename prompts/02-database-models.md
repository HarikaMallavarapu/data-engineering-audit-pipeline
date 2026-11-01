# Prompt 02 — Database schema and persistence

Read `/AGENTS.md`, `docs/architecture.md`, and `docs/data_dictionary.md`.

## Skill/agent routing
Use the `database-reviewer` agent if available. Use `code-architect` for model boundaries and `code-reviewer` after implementation. If `ai-regression-testing` is available, use it to improve regression coverage, not as a substitute for ordinary tests.

## Files in scope
`backend/app/models/`, `backend/app/schemas/`, `backend/app/repositories/`, `backend/migrations/`, `backend/alembic.ini`, `docs/data_dictionary.md`.

## Task
Implement SQLAlchemy models and Pydantic schemas for:
- pipelines and pipeline_versions
- source_files and schema_versions
- pipeline_runs, run_attempts and stage_executions
- quality_rules and quality_results
- rejected_records
- published_artifacts
- lineage_edges / record_provenance
- audit_events
- incidents
- reconciliation_results

Define primary/foreign keys, uniqueness, indexes, nullability, timestamps, status enums and relationships. Keep audit events append-only at service level. Make source identity and idempotency enforceable with unique constraints. Avoid over-normalizing a 72-hour challenge solution.

## Acceptance
- Migrations create a clean database.
- Relationships and cascade behavior are deliberate.
- Duplicate/idempotency constraints are tested.
- Tests use isolated temporary databases.
- Data dictionary documents grain, keys, nullability and business meaning.
- Ask the database-reviewer agent for a review if available; address findings or document trade-offs.
