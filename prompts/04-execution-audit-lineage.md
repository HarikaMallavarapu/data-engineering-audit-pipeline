# Prompt 04 — Execution, audit, lineage, retries and incidents

Read `/AGENTS.md`.

## Skill/agent routing
Use `code-architect` for execution state boundaries, `database-reviewer` for transactional correctness, and `code-reviewer` for review if available. Use `continuous-agent-loop` or `autonomous-loops` only if actually installed and appropriate.

## Files in scope
`backend/app/services/execution_service.py`, `retry_service.py`, `audit_service.py`, `lineage_service.py`, `incident_service.py`, `metrics_service.py`, `backend/app/workers/pipeline_worker.py`, and related tests.

## Task
Implement:
- Explicit run state machine: PENDING, RUNNING, SUCCESS, PARTIAL, FAILED, CANCELLED.
- Stage-level status, timestamps, counts, duration and structured errors.
- Run ID, attempt ID, source checksum, pipeline version and output metadata.
- Append-only audit event creation.
- Dataset and record-level lineage sufficient to trace an output row to source file and row.
- Incident creation for blocking failures and reconciliation mismatches.
- Retry that creates a new attempt and preserves previous failure evidence.
- Idempotency based on pipeline/version + source checksum + relevant parameters and stable source business keys.
- No false SUCCESS when a stage failed or reconciliation failed.

## Acceptance
Integration tests prove same-input rerun does not create unintended duplicate output, retry is auditable, failed run evidence remains, and every published artifact points to its run and source inputs. Document restart/backfill limitations honestly.
