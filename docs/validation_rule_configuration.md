# Validation rule configuration

The existing dynamic engine stores versioned schema profiles, rules, transformations and processing plans. Declarative rules are validated by Pydantic and only approved enabled rules execute. `RuleTypeRegistry` dispatches each approved rule type to its deterministic matcher; supported types and constrained configuration keys are listed in `backend/app/engine/quality/rules.py` and [dynamic_engine.md](dynamic_engine.md).

Each per-rule run result snapshots the exact validated rule configuration and version used during execution. Updating a rule creates a later immutable rule version; stored run results are not rewritten. Regex patterns use the existing length and unsafe-construct checks and test endpoint bounds.

When an approved rule's target or referenced column is absent after the run's mappings, the engine stores a `REQUIRES_CONFIGURATION` result with the missing field names and rule snapshot. It does not mark that rule as passed, reject rows because of it, or fail the validation stage as an execution error. The run is marked partial while the configuration is unresolved.

The product does not yet provide role-based authorization, a rule approval workflow, or a complete Rule Studio/history UI. The current Data Engine rule workflow is local-development functionality and must not be treated as an enterprise authorization boundary.
