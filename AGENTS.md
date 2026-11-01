# DataTrace — Repository Engineering Contract

## Mission
Build DataTrace: a working, locally runnable, enterprise-style data pipeline observability and audit platform. It ingests files, validates schemas and business rules, transforms accepted records, quarantines invalid records, publishes outputs, reconciles source and target results, records immutable execution evidence, exposes lineage, supports safe retry, and provides evidence-grounded AI diagnostics.

This is a data engineering challenge, not a dashboard-only exercise. The Python backend is the source of truth. Never fabricate KPIs, run states, row counts, lineage, audit events, AI evidence, or successful execution results.

## First action: inspect the environment and skills
Before implementing:
1. Inspect the existing repository and preserve useful work. Do not overwrite a working project blindly.
2. Read the project README and all existing `AGENTS.md` files.
3. Inspect the actual Codex skill catalogue and available agent/tool invocation mechanism in this environment.
4. Use exact skill names only when they are actually available. The user's ECC screenshot shows catalogue examples, not proof that they are installed in this session.
5. If available, use relevant skills/agents:
   - `codebase-onboarding` for understanding an existing repository.
   - `context-budget` only for explicit context-usage checks or installation audits; it is not a general project-analysis workflow.
   - `agentic-os`, `agent-harness-construction`, `continuous-agent-loop`, or `autonomous-loops` only when the specific task matches the installed skill description.
   - `ai-regression-testing` and `eval-harness` for AI diagnostic regression/evaluation; `benchmark-optimization-loop` for measured performance optimization, if present.
   - `code-architect` agent for architecture and module boundaries.
   - `database-reviewer` for schema, constraints, transactions and indexes.
   - `code-reviewer` for review after each vertical slice.
   - `build-error-resolver` for actual build/test failures.
   - `code-simplifier` to remove unnecessary complexity after correctness is established.
   - `a11y-architect` for accessible frontend review.
6. If a requested skill/agent is unavailable, state that internally in the task report and proceed using the requirements in this file. Do not invent skill capabilities or claim tool use that did not happen.
7. Do not delegate blindly. Give each specialist a bounded task, explicit files, acceptance criteria, and expected output. Integrate and verify all work yourself.

## Product scope
### Core vertical slice
A user can:
1. Register/upload a CSV or JSON source.
2. Inspect inferred/declared schema and file metadata.
3. Create or select a pipeline.
4. Execute a real Python pipeline and receive a stable `run_id`.
5. View stage-by-stage progress, counts, duration and errors.
6. Validate required fields, types, uniqueness, references and domain rules.
7. See invalid records in quarantine with original source file and row identity.
8. Transform accepted records deterministically.
9. Publish output safely.
10. Reconcile source, accepted, rejected, duplicate and published counts and relevant aggregates.
11. Trace output artifacts/records to their source and run.
12. Retry safely without unintended duplicate output.
13. Ask the AI diagnostic layer to explain a real failure using stored evidence.

### Domain example
Use synthetic financial transaction data:
- `stripe_payments.csv`
- `razorpay_transactions.csv`
- `bank_settlements.json`
- `customer_master.csv`
- `merchant_master.csv`

Example fields: `transaction_id`, `source_system`, `customer_id`, `merchant_id`, `amount`, `currency`, `transaction_status`, `event_time`, `ingested_at`, `settlement_id`.

Rules must be documented and configurable. Do not imply the sample data is real financial data.

## Architecture
Use a modular monolith:
- Frontend: React + TypeScript + Vite.
- UI: Tailwind CSS + shadcn/ui (or existing equivalent).
- Data fetching: TanStack Query.
- Workflow visualization: React Flow.
- Charts: Recharts.
- Backend: Python + FastAPI.
- Processing: Pandas; use PyArrow/Parquet where useful.
- Validation: Pydantic for API contracts and Pandera or explicit tested validators for tabular data.
- Persistence: SQLAlchemy + SQLite for the local challenge; keep PostgreSQL migration path clear.
- Tests: Pytest and Vitest.
- Live updates: SSE or WebSocket only if time allows; polling is an acceptable honest fallback.
- AI: provider abstraction; app must work without an API key using a clearly labelled deterministic diagnostic fallback. Never present fallback text as an LLM result.

Do not introduce Kafka, Spark, Kubernetes, Redis, microservices, or paid cloud services unless a demonstrated requirement justifies them. Keep setup reproducible.

## Suggested repository structure
```text
datatrace/
├── AGENTS.md
├── README.md
├── .gitignore
├── .env.example
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── app/                 # App, router, providers
│       ├── components/
│       │   ├── layout/          # Sidebar, header, page shell
│       │   ├── common/
│       │   ├── tables/
│       │   ├── charts/
│       │   └── pipeline/
│       ├── features/
│       │   ├── dashboard/
│       │   ├── pipelines/
│       │   ├── sources/
│       │   ├── runs/
│       │   ├── data-quality/
│       │   ├── quarantine/
│       │   ├── lineage/
│       │   ├── reconciliation/
│       │   ├── incidents/
│       │   ├── copilot/
│       │   └── audit/
│       ├── services/             # Typed API client
│       ├── hooks/
│       ├── types/
│       ├── utils/
│       └── styles/
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── migrations/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                 # config, DB, security, logging, errors
│   │   ├── api/v1/               # thin route handlers
│   │   ├── models/               # SQLAlchemy models
│   │   ├── schemas/              # Pydantic contracts
│   │   ├── repositories/         # DB access
│   │   ├── engine/
│   │   │   ├── ingestion/
│   │   │   ├── schema_validation/
│   │   │   ├── quality/
│   │   │   ├── transformation/
│   │   │   ├── profiling/
│   │   │   ├── publishing/
│   │   │   └── reconciliation/
│   │   ├── services/             # execution, retry, lineage, audit, incidents
│   │   ├── copilot/              # provider, diagnostics, prompts
│   │   └── workers/
│   └── tests/
│       ├── test_ingestion.py
│       ├── test_validation.py
│       ├── test_transformation.py
│       ├── test_quarantine.py
│       ├── test_idempotency.py
│       ├── test_reconciliation.py
│       └── test_pipeline_integration.py


├── datasets/
│   ├── sample/
│   ├── generated/
│   ├── output/
│   └── quarantine/
├── scripts/
│   └── generate_data.py
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── database_design.md
│   ├── api_reference.md
│   ├── testing.md
│   ├── design_decisions.md
│   └── operations.md
└── prompts/
    ├── 00-orchestrator.md
    ├── 01-backend-foundation.md
    ├── 02-database-models.md
    ├── 03-data-engine.md
    ├── 04-execution-audit-lineage.md
    ├── 05-api-layer.md
    ├── 06-frontend-foundation.md
    ├── 07-frontend-pages.md
    ├── 08-ai-copilot.md
    ├── 09-tests-and-performance.md
    └── 10-review-and-release.md
```

## Non-negotiable data engineering rules
- Stable deterministic IDs for source records; do not use random IDs as deduplication keys.
- Use `snake_case` for Python, database tables and columns.
- Store timestamps in UTC as ISO-8601; document timezone conversion at UI boundaries.
- Every execution has `run_id`; every input has `source_file_id` and checksum; retain original file and source row number.
- Preserve both business event time and ingestion time.
- Use append-only audit events. Never silently overwrite historical execution evidence.
- Enforce database constraints and unique indexes for idempotency, not only frontend checks.
- A retry creates an attempt record and preserves prior failure evidence.
- Never publish partial data as complete. Publish atomically where practical; otherwise mark output explicitly partial and explain it.
- Keep invalid rows traceable to source file, row number, run, rule ID and rejection reason.
- Separate source, accepted, rejected, duplicate, transformed and published counts. Explain count differences.
- Schema drift must be detected and classified. Incompatible changes block publication until handled.
- Do not silently drop duplicates. Record the deduplication rule and outcome.
- Keep expected-answer labels separate from input records.
- Use synthetic, reproducible data and a fixed random seed.
- Never commit secrets, API keys, personal data or large generated datasets.

## Execution state model
Use explicit states such as `PENDING`, `RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`, `CANCELLED`. Define valid transitions in code. Record stage start/end, status, input/output/reject counts, duration and structured error details.

## Quality and domain rules
At minimum demonstrate:
- Required-field and null checks.
- Type and format validation.
- Duplicate transaction/event detection.
- Positive amount and supported currency checks.
- Customer and merchant reference integrity.
- Settlement/transaction reconciliation.
- Late/out-of-order event handling.
- Empty input, malformed input and schema drift.

## Idempotency and recovery
Define a deterministic idempotency key using pipeline/version + source checksum + relevant execution parameters. Define source record identity from stable business keys and source system. Reprocessing identical input must not create unintended duplicate published rows. Explain retry, restart and backfill semantics in docs and tests.

## API rules
- Version all routes under `/api/v1`.
- Keep route handlers thin; call services.
- Validate requests/responses with Pydantic.
- Return consistent error objects with a machine-readable code and human-readable message.
- Never expose stack traces or secrets to the browser.
- Add pagination/filtering for run, audit, quarantine and incident lists.
- Document endpoints in OpenAPI.

## Frontend rules
- Enterprise hybrid visual system: dark navy sidebar, light workspace, restrained teal accent, clear typography, compact data-dense tables, useful whitespace.
- Responsive and keyboard-accessible.
- Include loading, empty, error, success and partial states.
- Use real API data. No hardcoded fake KPI values once API integration exists.
- Avoid one giant component. Each feature owns its page, components, hooks and types where appropriate.
- Keep API calls in service modules, not scattered through UI components.
- Use a shared design system and consistent status semantics.
- AI outputs must be labelled as suggestions and cite run/stage/record evidence when available.

## Testing requirements
Automated tests must cover:
1. Happy path.
2. Empty input.
3. Malformed file/record.
4. Missing required field/null.
5. Duplicate key/event.
6. Unexpected schema change.
7. Invalid reference key.
8. Late/out-of-order data.
9. Partial failure and retry.
10. Same input rerun/idempotency.
11. Reconciliation mismatch.
12. At least two domain-specific edge cases.

Use temporary directories and isolated test databases. Tests must not depend on network access or external AI credentials.

## Performance requirement
Provide a reproducible benchmark for at least 100,000 synthetic records where practical. Record machine/runtime conditions, elapsed time, throughput, memory if feasible, and one optimization. Never invent benchmark numbers.

## Definition of done for every file
Before marking a file complete:
1. Confirm it belongs in the architecture and has a single clear responsibility.
2. Implement real behavior, not placeholder logic, unless explicitly marked as a stub.
3. Add types, validation, error handling and logging appropriate to its role.
4. Add or update tests for behavior.
5. Run formatter/linter/type checks/tests relevant to the file.
6. Check imports, naming, path configuration and secrets.
7. Update docs/contracts if behavior changed.
8. Review for unnecessary complexity.
9. Report exact files changed, commands run and actual results.

## Execution strategy
Work in vertical slices:
A. Repository inspection and plan.
B. Backend foundation + database.
C. Deterministic pipeline engine + fixtures.
D. Execution/audit/lineage/reconciliation/idempotency.
E. API integration.
F. Frontend foundation and pages.
G. AI diagnostics.
H. Tests, benchmark, docs and clean-start verification.

At each slice: implement -> run tests -> review -> fix -> summarize. Do not start a large new feature while the current slice is broken.

## Time-boxing
The challenge deadline is fixed. Prioritize a complete tested vertical slice over unfinished advanced features. If time is short, reduce visual extras and optional live updates before reducing correctness, tests, idempotency, reconciliation or documentation.

## Final handoff report
Include:
- What works end-to-end.
- Architecture and key trade-offs.
- Exact setup/run commands.
- Test command and actual pass/fail summary.
- Benchmark command and actual measured results.
- Known limitations.
- Features not implemented.
- Git status and commit state.
- Never claim deployment, tests, skill usage or success unless actually performed.
