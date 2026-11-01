# AI validation intelligence

The existing OpenRouter/Gemini adapter provides opt-in advisory schema and processing suggestions from aggregate profile metadata. Ordinary row validation does not call an LLM. Model output does not execute code or determine whether rows pass; deterministic Python validators remain authoritative. Existing request budgets, token caps, cache, usage tracking and deterministic fallback are documented in [dynamic_engine.md](dynamic_engine.md).

This Validation Center slice does not add AI-generated validation catalogs, explanations, rule recommendations, or history summaries. Those functions remain unimplemented until the corresponding deterministic contracts, source catalog mapping, output validation and test cases are designed.
