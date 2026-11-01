# Design decisions

## First-slice decisions

1. **Backend owns operational truth.** The UI uses persisted API responses for run counts, status, stages, rejections and reconciliation.
2. **Local-first persistence.** SQLite and SQLAlchemy provide the local path; an initial Alembic migration records the schema.
3. **Deterministic source and run identities.** Source IDs derive from SHA-256; run IDs derive from the immutable pipeline-version ID and source checksum. Database uniqueness protects idempotency.
4. **Financial duplicate scope.** Within a run, case-folded `source_system + transaction_id` is the duplicate key. Invalid rows are rejected before duplicate lookup.
5. **Exclusive row dispositions.** Engine classification partitions source rows into accepted, rejected and duplicate sets. This is enforced in application code and tested; separate rejected/duplicate tables preserve disposition detail.
6. **Currency-safe reconciliation.** Count equations are checked for every run. Amount totals are compared separately for USD, EUR and INR rather than summing unlike currencies.
7. **Schema drift.** Additional input columns are recorded as additive and ignored by the standardized output. Missing required columns block publication.
8. **Safe local publication.** Candidate CSV and JSONL files are staged and replaced atomically after reconciliation. A failed persistence commit triggers cleanup of files created by that attempt.
9. **Synchronous local processing.** The API completes a run in the request for the smallest local slice. A separate worker and SSE are deferred; the UI can poll if execution later becomes asynchronous.
10. **Runtime retries preserve evidence.** A retry keeps the run ID but creates a new attempt; stage names are unique per attempt. Schema-incompatible failures require corrected input.
11. **Synthetic references.** The sample customer and merchant master files are explicitly synthetic and configurable by path.
12. **Environment file location.** `backend/.env.example` is the backend configuration template; settings load `backend/.env` from an absolute repository-relative path regardless of the process working directory. `.env` secrets are ignored by Git.
13. **Dynamic processing stays deterministic.** A local profiler describes incoming schemas; a versioned rule registry and transformation registry apply allow-listed Python operators; the AI adapter only proposes mappings, rules and plans; operators approve uncertain semantics. Ordinary validation does not call an LLM.
14. **Opt-in model spend.** OpenRouter uses a configurable model ID, per-request token limits, cache and an atomic SQLite budget reservation. The default $1 app budget is an estimate based on configured model pricing, so an account-level provider cap remains separate.
15. **Spreadsheet reader.** XLSX/XLSM ingestion uses the existing pandas reader plus `openpyxl`; it stays within upload/row limits. Parquet and binary documents remain unsupported.

## Frontend transformation decisions

1. **A data-operations workspace, not a generic analytics dashboard.** The shell uses a deep ink navigation rail, cool light/dark work surfaces, vivid indigo actions, emerald success states, and dense tables suited to run evidence. Operational metrics are read from the API and charted only when persisted runs exist.
2. **Expose backend capabilities honestly.** Source registration, finance and general-tabular runs, metadata-only AI schema suggestions, run history/details/retry, validation profile, quarantine, duplicates, reconciliation and audit use mounted API routes. Lineage traversal, incident entities, quality scoring and conversational Copilot diagnosis remain clearly marked unavailable because the current backend does not provide those contracts.
3. **Responsive navigation.** Desktop uses a persistent grouped sidebar that can collapse to an icon rail; narrow viewports use a labeled, expandable grouped navigation panel. Evidence tables scroll within named regions instead of shrinking columns beyond legibility.
4. **Themes use CSS variables.** Light and dark palettes share semantic tokens and persist the user's choice in versioned local storage. No remote font request is required; system font stacks keep first render independent of a third-party network.
5. **Icons use Lucide React.** The package provides tree-shakeable SVG icons with React and TypeScript support. React Flow was deferred because the backend has no saved graph/configuration contract; a visual editor would imply a capability the server cannot persist or execute.
6. **The run charts use local SVG components.** Recharts was evaluated and then removed after the production bundle grew to about 750 kB (218 kB gzip) and emitted a >500 kB chunk warning. The custom SVG area chart and status ring render actual returned run counts with a text equivalent while keeping the dependency set small. A time-window selector filters only the latest 100 returned runs. TanStack Table was not added: the current source list and run page size do not justify another table abstraction.
7. **No placeholder operations.** Routes without backend support explain which API contract is missing and link to available evidence. They do not return local sample activity or simulate requests.

The UI library evaluation referenced the official [Lucide React](https://lucide.dev/guide/react/), [React Flow](https://reactflow.dev/index), and [TanStack Table](https://tanstack.com/table/latest/docs/installation) documentation. Exact package compatibility was checked against npm metadata during implementation.

## Historical benchmark

An earlier run on 2026-11-01 used Windows 11, Python 3.14.2, pandas 3.1.0, seed `20261031`, and 100,000 generated rows:

- Elapsed: 15.436 seconds; throughput: 6,478 rows/second.
- Peak traced Python memory: 203.0 MiB. This is `tracemalloc` memory and does not include native allocations made by NumPy/Pandas.
- Dispositions: 100,000 accepted, 0 rejected, 0 duplicates.
- The engine uses a hash set for duplicate identity lookup, giving expected O(1) membership checks instead of comparing each row to all earlier rows. The benchmark reports the measured full pipeline pass; it does not claim a comparison to an unoptimized baseline.

The current Python 3.15.2 benchmark is recorded in [validation_benchmarks.md](validation_benchmarks.md); the measurements use different runtimes and are not a controlled comparison.

## Remaining product decisions

- Authentication and non-local deployment boundary.
- PostgreSQL migration validation.
- Source, audit and artifact retention/backup policy.
- Worker and progress transport if synchronous processing no longer fits local request limits.
- Parquet/binary inputs, asynchronous workers, richer lineage/incident screens and conversational AI diagnostics. JSON objects/arrays and JSON Lines use the general-tabular pipeline; spreadsheet inputs are supported. AI schema suggestions are advisory, metadata-only and opt-in.

