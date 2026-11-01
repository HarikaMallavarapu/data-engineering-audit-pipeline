# Dynamic processing engine

## Responsibility boundaries

| Component | Responsibility |
|---|---|
| Python engine | Parses supported tabular files, validates and transforms actual records, records dispositions and publishes outputs. |
| Profiler | Learns each input's columns, types, nulls, distinct counts, sampled numeric/string/date statistics, value shapes and schema fingerprint. |
| Rule registry | Stores immutable, versioned, configurable rule definitions and their draft/approved/rejected state. |
| Transformation registry | Stores immutable, versioned definitions for deterministic, allow-listed operators. |
| OpenRouter/Gemini | Suggests semantic mappings, validators and processing operators from compact profile metadata. It never validates individual rows or executes generated code. |
| Operator | Reviews semantic decisions and approves, edits or rejects suggestions. |
| Database | Stores source checksums/profiles, versions, plans, usage, cache entries, runs and append-only execution evidence. |

The supported upload types are UTF-8 CSV, JSON object/array, JSON Lines/NDJSON, XLSX and XLSM. JSON nested objects are flattened to dotted column names. Parquet, binary documents, images and other unstructured data are not supported as tabular sources.

## Local profiling

The upload parser assigns stable source row numbers and stores the original bytes under their SHA-256 checksum. The profiler inspects arbitrary field names and values; it does not require the financial transaction schema. `PROFILE_SAMPLE_SIZE` bounds sampled type inference and distribution work. Null and distinct counts are exact within the configured upload/row bounds. Numeric profiles report min/max/mean/median and IQR outlier count; string profiles report length ranges and abstracted patterns. Recognizers identify email, URL, phone, postal-like, UUID/identifier, date/time and currency-like shapes where the values support that classification.

Profiles are observations, not business contracts. For example, a column named `total_value` can be suggested as an amount, but only an operator can approve that meaning. Schema fingerprints include column names and inferred types. The schema drift endpoint compares added/missing columns and shared-column inferred-type changes.

The general-tabular validator also checks each nonblank value against a dominant inferred type when at least 80% of the bounded profile agrees. It checks numeric, boolean, date/time, email, URL, phone and currency-like types. Type mismatches are rejected with the source row and field in quarantine before duplicate classification; the run stage and dry-run report show mismatch counts. Mixed or lower-confidence columns are reported for review and do not get a guessed strict type. Blank cells are counted and shown, but a field is required only after a required rule is approved.

## Rule registry

The API accepts versioned rules with the following types:

- `required`, `type`, and `regex`
- `date_range`, `numeric_range`, `email`, `phone`, and `identifier`
- `unique`, `referential`, and `cross_field`
- `conditional`, `domain`, and allow-listed `custom`

Rule configuration is validated with Pydantic and a per-rule allow-list of config keys/operators. Regexes are capped at 256 characters; backreferences, lookarounds and common nested/repeated quantifier patterns are rejected. The regex tester uses Python's safe-compiled registry path and caps sample values at 20 strings, 1,024 characters each. Only the latest approved rule version runs. Drafts and rejected rules are visible but inert.

## Transformation registry

Versioned transformations use only these operators: `rename_column`, `normalize_whitespace`, `standardize_case`, `cast_type`, `parse_date`, `normalize_currency`, `replace_null`, and `extract_regex`. Each operator validates a constrained configuration. The engine orders them deterministically, preserves original row payloads for quarantine, records changed-row metrics, and rejects rows whose transform fails. No Python, SQL, shell or arbitrary model-provided code is accepted.

## Suggestion and approval flow

1. Upload builds and persists a local profile.
2. The operator asks for suggestions from Data engine. A local deterministic suggestion path works without credentials; when configured, the selected LLM may infer field meanings and propose rules/transforms.
3. The UI labels model output and displays confidence/explanations. Mapping decisions start unapproved. The operator approves/edits/rejects mappings and explicitly approves any rule/transform that may run.
4. The operator builds a dry-run plan. It parses the original input and executes the approved mappings, base generic checks, approved rules and approved transforms against the real rows. The plan records a version, component sequence, dispositions and at most five accepted preview rows; it never publishes.
5. A normal general-tabular run uses the same saved/approved deterministic components and records its stage, output, rejection and lineage evidence. It does not call an LLM.

Schema profiles, rules, transformations and plans are versioned so a new operator decision does not rewrite earlier history. Rules and transforms attach to a schema fingerprint and are reusable for the same observed schema.

## OpenRouter selection and spend guard

The configured model is `z-ai/glm-5.3-flash`, configurable through `OPENROUTER_MODEL`. OpenRouter currently lists it at $0.075/M input and $0.25/M output and supports structured outputs on eligible provider routes ([model pricing and capabilities](https://openrouter.ai/z-ai/glm-5.3-flash), [structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)). In a live smoke request on 2026-11-01 it returned a response that passed the app's schema validation. The earlier Qwen 3.5 Flash candidate returned malformed structured content in this integration, so GLM Flash is the tested default. Pricing and route support can change; verify before changing configuration.

Secrets belong in ignored `backend/.env`; the key is server-only. The default request limits are 1,800 input tokens, 1,200 output tokens, a 12 second timeout and zero retries. A persistent SQLite budget starts at `$1.00` (configurable with `AI_BUDGET_USD`). Before a request, DataTrace atomically reserves the maximum cost implied by configured input/output token rates and token limits. It records estimated and provider-reported usage, latency, provider, model and task. Successful normalized responses are cached by provider/model/task/prompt version/profile hash; a cache hit makes no provider request. Ordinary validation runs do not call the model.

This reservation depends on the configured model's actual pricing and provider usage. When changing models, update `AI_INPUT_COST_PER_MILLION_USD` and `AI_OUTPUT_COST_PER_MILLION_USD` together; the application does not automatically substitute another model. The local guard is not a provider-side billing cap. Configure an OpenRouter account spend limit separately. The UI's reset control or `POST /api/v1/ai/budget/reset` resets only the local ledger; it does not change provider account billing.

On missing credentials, timeout, provider error, invalid structured response or exhausted budget, deterministic local suggestions are returned with an explicit fallback/status label. Row validation and publication continue locally. The app never silently labels fallback output as an LLM result.

## API and evidence

See [API reference](api_reference.md) for profile, suggestion, schema approval/drift, rule/transform registry, regex test, dry-run, usage, cache and budget endpoints. All API routes are under `/api/v1`. OpenAPI is available from FastAPI at `/docs`.

## Limits

- Ingestion remains bounded by configured file/row limits and loads records in memory; multi-gigabyte streaming is not implemented.
- Semantic mappings rely on LLM/local alias suggestions plus human review. The app cannot infer a domain contract from unfamiliar values with certainty.
- Profiling is sampled for value-pattern/numeric/type statistics; distinct and null counts scan the bounded full input.
- General-tabular processing supports flat tabular rows. Nested JSON objects are flattened, but arbitrary nested arrays and binary document structures are not general-purpose inputs.
- The budget is an app-side estimated-spend guard. Provider billing, provider-side discounts and account-level limits remain governed by OpenRouter.
