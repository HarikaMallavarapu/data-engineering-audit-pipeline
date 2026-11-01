# Prompt 00 — Orchestrator / repository owner

You are the principal engineer responsible for delivering DataTrace. Read `/AGENTS.md` fully before acting.

## Required skill/agent routing
Inspect the actual available skills and agent invocation mechanism. Use `codebase-onboarding` for read-only repository reconnaissance if available. Use `context-budget` only for explicit context-usage checks; it is not a general project-analysis skill. Use the `code-architect` agent for boundaries and file ownership if available. `agent-harness-construction`, `agentic-os`, and `continuous-agent-loop` are optional only when the task matches their descriptions. Never claim an unavailable skill or agent.

## Task
Inspect the current repository. Produce a concise implementation plan and dependency graph. Identify existing code worth preserving, missing pieces, risks and the smallest complete vertical slice. Do not create all files in one unreviewed blast.

## Deliverables
- `docs/architecture.md`
- `docs/design_decisions.md`
- A prioritized task checklist.
- A proposed file ownership map.
- A list of actual available skills/agents used and unavailable ones.

## Acceptance
The plan respects the architecture and challenge brief, avoids unnecessary infrastructure, identifies data contracts before UI integration, and schedules tests alongside implementation. Stop after the plan unless explicitly asked to implement the next slice.
