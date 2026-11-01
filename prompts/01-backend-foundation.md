# Prompt 01 — Backend foundation

Read `/AGENTS.md` and `docs/architecture.md`.

## Skill/agent routing
Discover available skills. Prefer `codebase-onboarding` for an existing backend, `context-budget` for focused context, and `code-architect` agent for boundaries. Use `build-error-resolver` only if real build errors occur. Do not claim unavailable skills.

## Files in scope
`backend/requirements.txt`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/core/logging_config.py`, `backend/app/core/exceptions.py`, `backend/app/__init__.py` and package initializers as needed.

## Task
Create a minimal, production-minded FastAPI foundation:
- Environment-based settings with safe defaults.
- SQLAlchemy engine/session lifecycle, SQLite local default, configurable DB URL.
- Health endpoint and versioned `/api/v1` router.
- CORS configured from environment, not wildcard in production.
- Structured logging with run/request correlation support.
- Consistent API error response shape.
- Startup/shutdown behavior that does not hide database errors.
- OpenAPI metadata and useful tags.

## Constraints
Do not implement business logic in `main.py`. Do not hardcode secrets. Do not add authentication complexity unless the project already requires it. Add a clear local setup path.

## Tests / acceptance
Add tests for health, app startup and error response. Run the backend test command and report actual output. Keep route handlers thin.
