# Validation security

- Validator failures are distinct from validation failures; raised exceptions flow through the pipeline error path and are not converted to `PASS`.
- Validation failure examples store source row identifiers, not source values.
- Existing declarative rules use allow-listed operators; arbitrary Python, SQL, shell commands and model-generated code are not executed.
- Existing regex checks apply length and unsafe-pattern restrictions. They do not prove that every possible expression is free of denial-of-service risk.
- Upload limits, generated storage names, source-path handling, server-only AI keys and metadata-only provider inputs remain governed by the existing controls described in `AGENTS.md` and [dynamic_engine.md](dynamic_engine.md).
- This local app has no authentication/role authorization layer. Catalog/rule editing must not be exposed as a secured enterprise control until that boundary exists.
- Validation checks are not legal/compliance certification, payment authorization, or proof of secure application behavior.
