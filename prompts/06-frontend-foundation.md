# Prompt 06 — Frontend foundation and design system

Read `/AGENTS.md` and `docs/api_reference.md`.

## Skill/agent routing
Use `a11y-architect` for accessible interaction review if available. Use `code-architect` for feature boundaries, `code-simplifier` after correctness, and `code-reviewer` for review if available. If `bun-runtime` exists, use it only if the repository actually uses Bun; otherwise use the package manager already configured.

## Files in scope
`frontend/package.json`, Vite/TypeScript config, `frontend/src/app/`, `frontend/src/components/layout/`, `components/charts/`, `components/tables/`, `components/common/`, `components/pipeline/`, `styles/`, `services/api.ts`, and `types/`.

## Task
Build the shared application shell:
- Hybrid enterprise design: dark navy sidebar, light content workspace, restrained teal accent.
- Responsive sidebar/header and page container.
- Reusable buttons, cards, badges, status indicators, tables, filters, dialogs, skeletons, empty states and error states.
- Typed API client with base URL from environment, request errors and response typing.
- TanStack Query provider and router.
- Accessible focus states, labels, keyboard navigation and semantic landmarks.

## Constraints
Do not build fake dashboard data here. Provide reusable components, not one giant page. Keep spacing, typography, colors and status meanings consistent. Use existing UI libraries if already installed rather than replacing the stack.

## Acceptance
Frontend builds cleanly, routes render, layout works at desktop and mobile widths, and accessibility basics are reviewed.
