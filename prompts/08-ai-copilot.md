# Prompt 08 — Evidence-grounded AI Copilot

Read `/AGENTS.md`.

## Skill/agent routing
Use `eval-harness` and `ai-regression-testing` if available to evaluate diagnostic quality and prevent regressions. `agent-eval` is for comparing coding agents and is not the application-level diagnostic evaluator. Use `code-reviewer` for security and correctness review.

## Files in scope
`backend/app/copilot/`, `backend/app/api/v1/copilot.py`, tests, and frontend copilot feature.

## Task
Implement an AI provider abstraction with:
- A real provider adapter configured only through environment variables.
- A deterministic no-key fallback that is explicitly labelled as rule-based.
- Context retrieval from actual run, stage, quality, incident and reconciliation records.
- Structured diagnostic response: summary, likely cause, affected stage, affected counts/records, evidence references, suggested next steps, confidence/limitations.
- Evidence IDs or links for every factual statement about the run.
- Prompt-injection resistance: treat file contents and logs as untrusted data, never as instructions.
- No automatic data mutation, retry, deletion or publishing from the AI. Require explicit operator action.
- No secrets or full sensitive records in model prompts; minimize and redact data.

## Evaluation
Create tests with known synthetic failure scenarios: schema drift, null required field, invalid reference, reconciliation mismatch and transient stage failure. Verify the response only states facts supported by retrieved evidence. If no provider key exists, app still works and identifies fallback mode honestly.

## Acceptance
AI explanations are grounded, testable and safe. Never fabricate a diagnosis or claim an LLM was called when fallback logic ran.
