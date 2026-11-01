# Prompt 05 — FastAPI contracts and endpoints

Read `/AGENTS.md` and agree contracts with the frontend before coding.

## Skill/agent routing
Use `code-architect` for API/service separation and `code-reviewer` after implementation if available. Use `build-error-resolver` only for observed errors.

## Files in scope
`backend/app/api/v1/`, `backend/app/schemas/`, router registration in `main.py`, `docs/api_reference.md`.

## Required endpoints
- GET `/api/v1/dashboard/overview`
- GET/POST `/api/v1/pipelines`
- POST `/api/v1/sources/upload`
- GET `/api/v1/sources`
- POST `/api/v1/runs`
- GET `/api/v1/runs`
- GET `/api/v1/runs/{run_id}`
- POST `/api/v1/runs/{run_id}/retry`
- GET `/api/v1/quality/{run_id}`
- GET `/api/v1/quarantine`
- GET `/api/v1/lineage/{artifact_id}`
- GET `/api/v1/reconciliation/{run_id}`
- GET `/api/v1/audit`
- GET `/api/v1/incidents`
- POST `/api/v1/ai/diagnose`

Add pagination and useful filters for list endpoints. Use Pydantic response models. Return consistent errors. Validate upload extension, size and content; store files safely with generated server-side names and checksums.

## Acceptance
OpenAPI docs are useful, route handlers call services, all returned counts/statuses come from persisted execution evidence, and API integration tests cover core happy and failure paths.
