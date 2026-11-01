# Prompt 10 — Final engineering review and release

Read `/AGENTS.md` and all docs.

## Skill/agent routing
Use `code-reviewer`, `database-reviewer`, `a11y-architect`, `code-simplifier`, and `build-error-resolver` where available and relevant. Use only discoverable agents. Record unavailable tools without pretending.

## Task
Perform a release audit:
1. Verify clean install from documented commands.
2. Run backend tests, frontend tests, lint, type checks and production build.
3. Run sample pipeline end-to-end.
4. Run same input twice and verify idempotency.
5. Verify quarantine traceability and reconciliation.
6. Verify failure/retry and audit history.
7. Verify UI is connected to real API data.
8. Verify AI provider/fallback labelling and evidence citations.
9. Verify 100k benchmark and record actual results.
10. Search for secrets, fake KPIs, TODO placeholders, dead buttons, broken links and hardcoded local paths.
11. Check `.gitignore`; do not commit generated large data, databases, secrets or runtime output.
12. Complete README and docs: architecture, setup, run commands, sample data, data dictionary, tests, benchmark, limitations and trade-offs.

## Acceptance
Provide an honest final report with exact commands and outputs. Do not claim tests pass if they were not run. Do not claim complete features that are stubs. Do not submit until the public repository URL, README and required deliverables are verified.
