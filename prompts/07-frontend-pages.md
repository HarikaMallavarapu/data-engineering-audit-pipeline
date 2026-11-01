# Prompt 07 — Frontend feature pages

Read `/AGENTS.md`, API contracts and the shared design system.

## Skill/agent routing
Use `a11y-architect` for accessibility and `code-reviewer` for review if available. Use `code-simplifier` after all pages work. Use `codebase-onboarding` if entering an existing frontend.

## Files in scope
`frontend/src/features/{dashboard,pipelines,sources,runs,data-quality,quarantine,lineage,reconciliation,incidents,copilot,audit}/`.

## Build in this order
1. Dashboard: actual KPIs, execution trend, quality trend, recent runs and incidents.
2. Sources: upload, preview, schema summary and file metadata.
3. Pipeline list/detail and a focused visual pipeline studio using React Flow. Nodes represent source, schema check, quality validation, transformation, publish and reconciliation. Save a valid backend pipeline configuration; do not imply arbitrary visual graphs execute if they do not.
4. Runs: searchable run table and detailed stage timeline with counts/errors.
5. Quality and quarantine: rule results, rejected row evidence, source references and reasons.
6. Reconciliation: source/target count and aggregate comparison.
7. Lineage: trace artifact/output record to run, source file and source row.
8. Incidents: failure evidence and retry action.
9. Copilot: question/diagnosis UI that cites backend evidence.
10. Audit: filterable immutable event history.

## Constraints
Every operational value must come from the API. Show loading, empty, error, partial and success states. Do not invent ratings, percentages or sample live activity. Clearly mark seeded demo data as demo data. Keep tables usable for large result sets with server-side pagination.

## Acceptance
A reviewer can complete the end-to-end demo from the UI without manually editing the database. Every action has a real API call and visible result/error.
