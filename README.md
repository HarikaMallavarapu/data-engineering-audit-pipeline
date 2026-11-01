# DataTrace

DataTrace is a local-first tabular data pipeline operations tool. FastAPI owns source registration, run execution, validation, output publishing, audit evidence and reconciliation. The React interface displays persisted API results.

## First vertical slice

The financial-transactions pipeline accepts tabular files and validates finance-specific fields and synthetic customer/merchant references. The general-tabular pipeline accepts arbitrary flat columns from CSV, JSON objects/arrays, JSON Lines, and Excel workbooks; it profiles schema and patterns locally, checks values against confident inferred types, reports nulls and mixed-type columns, and applies only user-approved schema mappings and versioned declarative rules/transforms. It preserves row provenance and supports a persisted dry-run preview. OpenRouter suggestions are opt-in and advisory. The Python engine never executes model-generated code, and ordinary validation runs do not call an LLM. Identical input and pipeline versions reuse the same run regardless of AI provider settings. Failed runtime attempts can be retried with a new attempt record.

The Validation Center records per-check run results and supports immutable quality baseline versions with aggregate drift comparisons. Numeric distribution metrics report their sample limits; generalized value-shape comparisons do not expose raw category values and are not domain category frequencies. See [validation architecture](docs/validation_architecture.md) and [baseline method](docs/validation_baselines.md).

`datasets/sample/transactions.csv` is synthetic demo input. The reference data in `datasets/sample/customer_master.csv` and `merchant_master.csv` is synthetic too. Update those files for local reference validation; never use them as real financial data.

## Requirements

- Python 3.14 or 3.15 (Python 3.14 is the previously benchmarked runtime; the current implementation was also verified on Python 3.15.2)
- Node.js 24 or a current supported LTS release
- PowerShell on Windows, or equivalent virtual-environment commands on other systems

## Local setup (PowerShell)

Run from the repository root:

```powershell
py -m venv backend\.venv-local
backend\.venv-local\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
$env:PYTHONPATH = "backend"
backend\.venv-local\Scripts\alembic.exe -c backend\alembic.ini upgrade head
backend\.venv-local\Scripts\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite address printed in the terminal (normally `http://127.0.0.1:5173`). The dev server proxies `/api` and `/health` to FastAPI on port 8000.

The backend loads `backend/.env`; `backend/.env.example` contains safe local defaults. Set `OPENROUTER_API_KEY` there to enable optional AI suggestions. The configured default is `z-ai/glm-5.3-flash`; change `OPENROUTER_MODEL` and its per-million token prices together if you choose another model. Without a key, DataTrace uses deterministic local suggestions. The app tracks a configurable `$1.00` local budget, reserves against request token caps, caches identical profiles, and exposes request usage and a manual reset on Data engine. OpenRouter account spend controls are separate and should also be set. Local defaults store SQLite data in `datasets/datatrace.db`, uploads in `datasets/generated/uploads`, published CSVs in `datasets/output`, and rejected JSONL evidence in `datasets/quarantine`.

## Verification

```powershell
$env:PYTHONPATH = "backend"
backend\.venv-local\Scripts\pytest.exe backend\tests -q
Set-Location frontend
npm test
npm run build
```

Run the measured 100,000-row benchmark from the repository root after installing backend requirements:

```powershell
$env:PYTHONPATH = "backend"
backend\.venv-local\Scripts\python.exe scripts\benchmark_pipeline.py --rows 100000 --seed 20261031
```

## API

FastAPI documentation is at `http://127.0.0.1:8000/docs`. Implemented endpoints and contracts are documented in [docs/api_reference.md](docs/api_reference.md).

## Repository guidance

- [AGENTS.md](AGENTS.md) contains permanent engineering rules.
- [prompts/](prompts/) contains implementation prompts.
- [docs/](docs/) describes the architecture, data contracts, migration choices, operations and tests.
- Keep runtime data and credentials out of source control. Operational values shown in the UI must come from the API.

## Scope and limitations

The current slice is synchronous and local-only, with a 10 MiB upload limit and a configurable row limit. It handles tabular CSV, JSON/JSON Lines and XLSX/XLSM; Parquet, binary documents, background workers, broad lineage browsing, incidents, and conversational AI diagnostics remain future work. Schema suggestions receive column names, aggregate statistics, abstracted value patterns and metadata only; row values and full datasets are not sent to the LLM. See [docs/dynamic_engine.md](docs/dynamic_engine.md) and [docs/design_decisions.md](docs/design_decisions.md) for the processing and budget contracts.

