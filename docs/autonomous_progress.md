# DataTrace implementation progress

## Current dynamic-engine slice — 2026-11-01

Implemented the requested schema-adaptive processing layer on top of the existing app. The backend now profiles arbitrary tabular columns, stores versioned mappings/rules/transforms/plans, validates and transforms only through deterministic registries, and exposes dry-run and regex-preview workflows. AI remains optional, metadata-only, budget-guarded, cached, auditable and advisory; deterministic profile mappings and sampled regex patterns remain available when the model abstains. No generated code runs.

- Current configured model: `z-ai/glm-5.3-flash`; configured rates are $0.075/M input and $0.25/M output as listed on the [OpenRouter model page](https://openrouter.ai/z-ai/glm-5.3-flash). It passed a live structured-response smoke request. Qwen 3.5 Flash was tried first but returned malformed content for this app's schema contract.
- Live OpenRouter smoke usage (recorded by the app): the latest synthetic alias-schema request used 704 prompt and 1,067 completion tokens; estimated cost was $0.000319550 and OpenRouter reported $0.000404580. It returned three rule suggestions and the reviewable mappings `client_reference→customer_id`, `txn_dt→transaction_date`, `total_value→amount`, and `currency_code→currency`.
- The `$1.00` application budget is an estimate backed by configured model rates and token caps, not an account-level OpenRouter limit. Configure an OpenRouter spend cap separately. The key is in ignored `backend/.env` and is not included in source or logs.
- Supported tabular formats: CSV, JSON object/array, JSON Lines/NDJSON, XLSX and XLSM. This is not arbitrary binary or unstructured-file ingestion, and multi-gigabyte streaming remains out of scope.
- Implementation documentation: `docs/dynamic_engine.md`, `docs/api_reference.md`, `docs/operations.md`, `docs/architecture.md`, `docs/database_design.md`, `docs/data_dictionary.md`, `docs/design_decisions.md` and `docs/testing.md`.

### Verification for this dynamic-engine slice

- Backend: **60 passed** (`pytest backend/tests -q`; one Starlette/httpx deprecation warning). Ruff: **passed**. Alembic: **no new upgrade operations detected**.
- Frontend: **14 passed**; Vite production build passed (`tsc -b` plus Vite).
- Benchmark command `backend\.venv\Scripts\python.exe scripts\benchmark_pipeline.py --rows 100000 --seed 20261031`: **100,000 rows in 15.436 s**, 6,478 rows/s, 203.0 MiB peak traced Python memory; 100,000 accepted, 0 rejected and 0 duplicates.
- Safe configuration check confirmed the key exists in `backend/.env` (value not displayed), configured model is GLM 5.3 Flash, local budget is $1.00 with $0.002048430 used and no outstanding reservation at check time. The ledger includes live OpenRouter smoke calls; test/reset controls affect only the local app budget.

## Dynamic processing engine implementation plan — 2026-11-01

### Inspection findings

- Existing working slice: FastAPI and React app, stable run evidence, finance and general-tabular pipelines, CSV/JSON/JSONL ingestion, deterministic local profiling/validation/publication, and an advisory OpenRouter/Gemini schema inference adapter.
- Gaps for this request: no Excel reader, profile statistics/pattern suggestions are limited, validation and transforms remain centralized functions, no versioned schema/rule persistence or approval APIs, no dry-run plan, and no persisted LLM usage, caching, or application budget guard.
- Existing migration history is Alembic-backed; SQLite `create_all` also runs for isolated tests. Root `.gitignore` excludes `.env` patterns, but the requested `backend/.env` path will be added explicitly and loaded from an absolute backend path.
- Model check (OpenRouter, 2026-11-01): GLM 5.3 Flash (`z-ai/glm-5.3-flash`) is the tested default at the currently listed $0.075/M input and $0.25/M output. The live smoke response passed normalization; the previous Qwen candidate did not satisfy this integration's JSON contract. See the current model page in the section above.

### Implementation plan

1. Add an interchangeable backend core: bounded CSV/JSON/JSONL/XLSX readers, sampled profile statistics/patterns, safe regex proposal/test helpers, declarative allow-listed rule registry, and deterministic transformation registry.
2. Add persisted schema profiles, processing plans and AI usage/cache/budget ledgers with Alembic migration; expose profile, schema approval, rule, dry-run, usage and manual budget reset APIs.
3. Replace untracked LLM calls with the configurable OpenRouter adapter, GLM 5.3 Flash default, strict per-request token/cost caps, atomic budget reservation, cache, bounded retries, usage accounting and deterministic fallback. Never run model-generated code.
4. Connect the general pipeline to the registries and persisted profile/plan; keep finance behavior and existing audit/lineage/reconciliation stable.
5. Add frontend views for profile/schema suggestions, rules/regex preview and budget/usage; add tests across three synthetic schemas, failure/cache/budget/reset paths, and run the reproducible 100k benchmark.
6. Update setup/security/API/architecture docs, install only a necessary Excel reader dependency, run backend/frontend checks, and report measured results and remaining gaps.

### Phase status

- [x] Phase 1 — repository and provider/model inspection.
- [x] Phase 2 — component interfaces and registries.
- [x] Phase 3 — profiling and schema inference.
- [x] Phase 4 — declarative validation and safe regex.
- [x] Phase 5 — transformations and dry-run planning.
- [x] Phase 6 — OpenRouter budget/cache/usage.
- [x] Phase 7 — API and frontend integration.
- [x] Phase 8 — tests, benchmark, and documentation.


**Current phase:** complete — implementation, review, and verification finished.

## Validation Center master specification — 2026-11-01

### Current phase

Phase 1 audit complete. Phase 2 validation execution evidence is in progress.

### Audit findings

- The pasted brief and the repository/attachment search do not include the two source documents for checks 001–100 and 101–200. The brief supplies category groupings but not each original title, description, or intent. The 200 catalog entries and a per-check implementation matrix cannot be truthfully produced until those documents are provided; no names or mappings are being invented.
- The existing app already has FastAPI, SQLAlchemy/Alembic, bounded CSV/JSON/JSONL/XLSX ingestion, generic inferred-type checks, versioned approved declarative rules, safe regex checks, transformations, dry-run plans, persisted pipeline attempts/stages, quarantine, reconciliation, audit, and opt-in metadata-only AI suggestions with a spend guard.
- At initial audit, pipeline validation evidence consisted of stage summaries and rejected rows; this gap is addressed below by attempt-scoped results for finance checks, inferred types, and approved rules.
- The backend API and frontend use a modular route/service/feature structure. Existing `/quality` is profile and rejection evidence, not an individual-check result view.

### Implementation plan

1. Add typed validation result/applicability contracts and a registry boundary for actual executable checks; keep unknown catalog definitions unavailable until the supplied references arrive.
2. Record real per-check execution outcomes and configuration snapshots on the run attempt; never infer a check passed from a successful pipeline stage.
3. Add paginated run-result and catalog-source-status APIs with run summaries derived only from persisted results.
4. Add Validation Center navigation, a source-missing catalog state, and run-specific results using only persisted backend data.
5. Add focused backend/API/frontend tests, run the full existing suites and build, fix defects, and document measured results and remaining work.

### Work completed

- Read `AGENTS.md`, README, architecture/database/API/dynamic-engine/operations/design/testing documentation, and inspected models, migrations, routes, execution service, rule engine, frontend routing/navigation/services, and test fixtures.
- Searched the repository and supplied attachments for the two catalog reference documents; neither was present.
- Bounded read-only backend and frontend architecture reviews confirmed the audit findings; no specialist findings were assumed to change the source-of-truth constraint.

### Files changed

- This progress record.

### Tests executed

- None at the initial audit; implementation and verification followed as recorded below.

### Gaps at the initial audit

- Missing source catalogs block accurate catalog definitions, original titles/descriptions/categories, and a complete implementation matrix.
- Individual per-rule run results and Validation Center pages were not yet implemented at the initial audit; see the completed work below.
- The 200 checks, historical baselines, quality scoring, configurable policies, exports, and the full AI validation recommendations are not implemented by this slice.

### Phase update — validation evidence foundation

**Current phase:** Phase 2 foundation, Phase 7 pipeline integration, Phase 8 APIs, and initial Phase 9–10 frontend surfaces implemented. Phases 3–6 and 11–12 remain partial/unstarted for the full 200-check scope.

#### Completed work

- Added strict applicability and result schemas with explicit statuses, row-count invariants, and a duplicate-safe validator registry boundary.
- Added `validation_definitions` and attempt-scoped `validation_executions` tables and migration `f2a4b6c8d0e1`.
- General-tabular runs now persist separate inferred-type checks and approved-rule outcomes, including actual configuration snapshots, rule versions, source row identifiers only, row counts, stage, timing, applicability, and severity. Retries remain attempt-scoped.
- Uncertain or empty profiled types now persist as `NOT_APPLICABLE`; approved rules with absent target/reference columns persist as `REQUIRES_CONFIGURATION` and make the run partial rather than passing or crashing.
- General-tabular row uniqueness and dataset reconciliation checks now persist separate execution results. Pre-publish reconciliation failures are retained with a failed stage and zero published rows.
- Declarative rule-type matching now dispatches through a duplicate-safe `RuleTypeRegistry`; all current built-in rule types are registered.
- Finance runs now persist individual schema, row-format, required-field, amount, currency, status, event-time, customer/merchant reference, transaction-uniqueness, and event-order results with internal `FINANCE:*` IDs. These IDs do not represent original catalog checks.
- Added paginated catalog and run-result APIs. Catalog API reports `SOURCE_MISSING` instead of inventing entries; run summaries derive only from persisted records.
- Added Validation Center overview, catalog status/table, and run result pages with API-backed data, empty/error states, filters, detail snapshots, responsive tables, and navigation.
- Updated setup instructions to use the current local environment name and removed Uvicorn's optional standard extras to avoid an unnecessary PyYAML source build on Python 3.15.
- Created the requested validation documentation set. The implementation matrix explicitly says original checks 001–200 cannot be mapped until the two catalog references are provided.

#### Files changed

- Backend: `backend/app/engine/validation/`, `backend/app/engine/pipeline.py`, `backend/app/engine/quality/rules.py`, `backend/app/engine/reconciliation/engine.py`, `backend/app/models/__init__.py`, `backend/app/services/execution_service.py`, `backend/app/api/v1/validation.py`, `backend/app/api/v1/__init__.py`, `backend/app/schemas/__init__.py`, `backend/migrations/versions/f2a4b6c8d0e1_persist_validation_executions.py`, and validation, dynamic-engine, reconciliation, and pipeline integration tests.
- Frontend: `frontend/src/features/validation/`, `frontend/src/services/runService.ts`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/app/App.tsx`, `frontend/src/app/App.test.tsx`, and `frontend/src/styles.css`.
- Docs/setup: README, `backend/requirements.txt`, this progress record, architecture/database/API/testing docs, and the nine new `docs/validation_*.md` files.

#### Verification executed

- Backend: **69 passed**, 1 existing Starlette/httpx deprecation warning (`pytest backend/tests -q --tb=short` under the Python 3.15.2 local environment).
- Ruff: passed.
- Alembic upgrade: applied `e19c4a2b75f1 -> f2a4b6c8d0e1`; `alembic check`: no new upgrade operations detected.
- Frontend: **18 passed**; production build passed (`tsc -b` and Vite).
- Benchmark: 100,000 synthetic finance rows, seed `20261031`, Python 3.15.2/pandas 3.1.0, **119.724 s**, 835 rows/s, 202.9 MiB traced peak, 100,000 accepted / 0 rejected / 0 duplicates. This measures in-memory per-check outcomes and timings, not database persistence; older measurements are documented separately and are not controlled comparisons.

#### Remaining work / known limitations

- The supplied catalogs are missing. Therefore original titles/descriptions/categories, a 200-row implementation matrix, and accurate `VAL-001`–`VAL-200` mapping remain blocked on those files.
- Current run-level check results cover finance checks, inferred-type applicability, general row uniqueness, approved rules, and reconciliation. Parser integrity and other checks still have stage/row evidence without individual execution records.
- The common `ValidatorRegistry` remains a foundation; not all runtime checks are registered through it. The declarative rule-type dispatch itself now uses a separate rule-type registry.
- Catalog import and original `VAL-001`–`VAL-200` mapping, rule approval/authorization UI, catalog-wide applicability history, baselines/drift, quality scoring, validation policies, full validation exports, full AI validation recommendations, and database persistence performance benchmarking remain incomplete.

## Design contract

- **Surface:** local-first data operations and validation workspace.
- **Audience:** engineers and operators who register tabular CSV/JSON inputs, choose a compatible pipeline, and inspect persisted outcomes.
- **Tone:** calm, dense, and evidence-led; deep ink navigation, cool blue-gray workspace, vivid indigo controls, emerald success, amber warning, and coral failure.
- **Memorable detail:** layered, accessible run-disposition analytics tied to real execution rows, with a compact status distribution beside the latest run.
- **Primary workflow:** register tabular data, inspect server-detected columns and schema suggestions, choose the general or finance pipeline, then inspect run and reconciliation evidence.
- **Viewport targets:** 1920x1080, 1440x900, 1366x768, 1024x768, 768x1024, and 390x844.
- **Reference notes:** the Seedtrace page emphasizes column mapping and row validation; the SaaS review article emphasizes task, state, business-rule, and responsive review. The supplied analytics screenshot was referenced in the text prompt but was not present as a separate image file, so its written chart guidance is used.

## Checklist

- [x] Read README, root AGENTS.md, frontend routes, components, styles, services, and backend route contracts.
- [x] Inspect the running application and real persisted sample data.
- [x] Review installed `design-system`, `frontend-design-direction`, `frontend-patterns`, `react-patterns`, `frontend-a11y`, and `react-testing` skills.
- [x] Run independent read-only frontend product and accessibility reviews.
- [x] Refine navigation, route accessibility, and small-screen layout.
- [x] Redesign dashboard analytics using only returned run evidence.
- [x] Improve source registry discovery, schema inspection, and registration flow.
- [x] Run unit, production-build, browser, responsive, and accessibility checks; fix findings.
- [x] Update design documentation and record final results.

## Findings that guide implementation

- The API supports CSV/JSON/JSON Lines source metadata/upload, finance and general-tabular pipelines, persisted runs and retries, local/LLM schema profiles, quarantine, duplicates, reconciliation, and audit.
- Dashboard, quality-score, lineage, incident-entity, and Copilot-diagnosis endpoints are stubs or absent. Their UI must stay explicit and must not invent metrics or graphs.
- Existing React Query, React Router, Lucide, and the custom SVG chart cover this slice. No new UI package is justified for the current API contracts and local sample size.
- The workspace has no `.git` directory, so baseline and final `git status` cannot be collected from this checkout.

## Reviewers

- `frontend_product_audit` (read-only sub-agent): reviewed capability boundaries, failure outcomes, mobile navigation, empty pipeline guidance, stale upload feedback, dashboard metric scope, and medium-width layout. Findings were addressed and rechecked.
- `accessibility_audit` (read-only sub-agent): reviewed skip navigation, source action names, pagination landmarks, route focus, Escape behavior, chart data access, and contrast. Findings were addressed and rechecked; final spot check had no P1/P2 findings.

## Skills and tools used

- Applied the installed `design-system`, `frontend-design-direction`, `frontend-patterns`, `react-patterns`, `frontend-a11y`, and `react-testing` skills.
- Used Chrome DevTools viewport emulation, rendered screenshots, keyboard interaction, console/network checks, and Lighthouse snapshots. No dependency was installed.
- The requested named specialist-agent registry was not exposed in this session; two bounded read-only general sub-agents covered product workflow and accessibility review.

## Completed implementation

- Reorganized the sidebar into task groups, added a collapsible desktop rail with accessible labels/tooltips, and replaced the horizontal mobile strip with a grouped menu. Route changes focus the page heading; Escape closes the mobile menu and restores focus to its toggle.
- Added a skip link, named pagination landmark, row-specific source actions, theme-aware focus indicators, and improved light-theme primary and chart contrast.
- Built a command-center dashboard with eight API-derived metric cards, a 24h/7d/30d run-disposition area chart, exact values table, status ring, latest persisted run, and recent activity. Quality score remains “—” because the API does not expose one. Active-run scope is the latest 100 returned records, independent of the selected chart window.
- Improved the source registry with a workflow guide, API-backed search/sorting/pagination, CSV/JSON upload, schema inspector, pipeline selection, upload success recovery, and explicit empty/error states. The dynamic-engine slice now adds interactive mapping review, profile-backed row dry-run preview, and XLSX/XLSM support; Parquet and GIS geometry checks remain unsupported.
- Added responsive containment for dense table regions; table content remains horizontally scrollable inside its labeled region without expanding the document.
- Added no dependencies. Reused React Query, React Router, Lucide, existing CSS tokens, and a custom SVG chart.
- Refreshed the palette to modern indigo primary actions, emerald success, cobalt information, amber warnings, coral failures, and a cool blue-gray base, with matched dark-theme tokens and accessible contrast.

## Validation results

- `cd frontend && npm test`: **14 tests passed**.
- `cd frontend && npm run build`: **passed** (`tsc -b` and Vite production build; 401.01 kB JS / 116.55 kB gzip; 51.87 kB CSS / 10.12 kB gzip).
- `$env:PYTHONPATH = "backend"; backend\\.venv\\Scripts\\pytest.exe backend\\tests -q`: **47 tests passed** (one existing Starlette/httpx deprecation warning). `backend\\.venv\\Scripts\\ruff.exe check backend\\app backend\\tests`: passed.
- ESLint: not configured and not installed in this frontend package; `package.json` has no lint script.
- Browser review: six dashboard viewport targets captured; source registry captured at desktop and phone sizes; all 12 routes checked at 1440x900 and 390x844. At each checked viewport, document `scrollWidth` equaled `clientWidth`. The source table keeps its own horizontal scroll area.
- Browser interactions: collapsed/expanded sidebar, mobile menu route focus and Escape focus restoration, dashboard time filter, source search and name sort, source schema inspection, theme switching, persisted run details and reconciliation evidence were exercised.
- Browser diagnostics: no console warnings or errors were recorded; all inspected `/api/v1` and `/health` requests returned HTTP 200.
- Lighthouse snapshot: after the modern palette refresh, the dashboard and source registry each scored **100 Accessibility** and **100 Best Practices** in desktop and mobile modes in both light and dark themes. Lighthouse SEO score was 80 and agentic-browsing score was 50; those do not indicate application workflow failures and were not targets of this UI slice.
- The local API returned persisted run `run_e6c920066b9db83a421cb11bbb3718eb` as `PARTIAL`: 7 input, 4 accepted, 2 rejected, 1 duplicate, 4 published; 6 persisted stages; balanced reconciliation and stored audit events. The UI showed those values without adding a new run during review.
- The exact 10,000-row source from the reported schema failure was rerun with `general-tabular` as `run_789208377f64c90a17da1cadaea4a604`: **SUCCESS**, 10,000 accepted and published, zero rejected or duplicates, all six stages successful, and balanced count reconciliation. Run profile identified all seven source columns. The UI run screenshot is `artifacts/ui-qa/run-detail-general-tabular-10k.png`.
- The earlier UI slice used a local schema fallback. The current dynamic-engine slice is separately verified with live OpenRouter requests; their recorded usage and costs are summarized above.
- `backend\.venv\Scripts\python.exe scripts\benchmark_pipeline.py --rows 100000 --seed 20261031`: **passed** on Windows 11 / Python 3.14.2 / pandas 3.1.0; 100,000 rows in 15.436 s (6,478 rows/s), 203.0 MiB peak traced Python memory, 100,000 accepted, 0 rejected, 0 duplicates. Benchmark uses a hash set for expected O(1) identity checks.
- The first-party `frontend-design-direction` evidence checker passed for `artifacts/ui-qa/evidence.json`.

## Validation baselines implementation (2026-11-01)

- Added immutable, versioned `QualityBaseline` persistence and Alembic migration, aggregate-only baseline snapshots, audit records, paginated listing, and same-pipeline completed-attempt comparisons.
- Added count, null/duplicate rate, schema/type, numeric distribution, generalized value-shape distribution, freshness, outlier-rate, and persisted runtime validation-failure comparisons. Numeric PSI and binned KS share baseline histogram edges and are omitted when either sample has fewer than 100 values. All anomalies remain review signals (`confirmed_invalid_records: false`).
- Added the Validation Center's Baselines and drift page and updated API/method documentation. Raw category values are not stored; source catalog IDs remain unmapped because the user has not received the source catalogs yet.
- Verification with the available Python 3.15.2 virtual environment: **74 backend tests passed** (one existing Starlette/httpx deprecation warning), Ruff passed, **23 frontend tests passed**, and the TypeScript/Vite production build passed.

## Evidence and handoff

- Screenshots and responsive measurements are in `artifacts/ui-qa/`, including dashboard and source screenshots at each relevant target, a real persisted run detail, and a server-inspected source schema.
- Setup commands remain those in `README.md`: from the repository root, run `backend\\.venv\\Scripts\\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload`; in another terminal run `cd frontend` then `npm run dev`.
- Added the `general-tabular` backend pipeline and optional OpenRouter/Gemini schema-inference provider. No package dependencies were added.
- This checkout has no `.git` directory. `git status` reports “not a git repository”; commit state cannot be determined.
- Remaining limitations include Parquet/binary/unstructured-file ingestion, streaming for multi-gigabyte inputs, arbitrary nested-array processing, GIS geometry validation, a visual pipeline editor, and conversational AI diagnostics. AI suggestions work with a configured OpenRouter or Gemini key and fall back to deterministic local profiling when unavailable.
