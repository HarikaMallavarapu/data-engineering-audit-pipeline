# Operations

## Environment and local startup

The backend reads `backend/.env` from an absolute path derived from the repository location. Copy `backend/.env.example` to `backend/.env` and edit values there. `.env` is ignored by Git. Relative data paths resolve from the repository root.

Run in PowerShell from the repository root:

```powershell
py -3.14 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
backend\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

In another terminal, start Vite:

```powershell
Set-Location frontend
npm install
npm run dev
```

The Vite development proxy forwards `/api` and `/health` to `127.0.0.1:8000`. Both servers bind to loopback for local development.

## Run and file behavior

- Upload limit defaults to 10 MiB (`MAX_UPLOAD_BYTES`); processing is bounded by `MAX_PROCESSING_ROWS`. Supported formats are CSV, JSON arrays/objects, JSON Lines/NDJSON, XLSX, and XLSM. The backend stores content under its checksum and retains the original filename only as metadata.
- Source upload is content-addressed. Re-uploading identical bytes returns the same source ID.
- Run IDs are deterministic for one immutable pipeline version and source checksum. Repeating the run request returns the persisted run.
- A runtime failure creates a `FAILED` attempt and failed-stage evidence. `POST /api/v1/runs/{run_id}/retry` creates a new attempt for runtime failures only.
- Schema incompatibility is not retried with the same file; upload a corrected source. A run with row rejects or duplicates publishes accepted rows and is `PARTIAL`.
- Candidate output and quarantine evidence are atomically moved from temporary files after count and amount checks. Published transaction output includes source file ID and source row number.
- SQLite foreign keys are enabled for every application connection. Alembic temporarily disables them during SQLite batch migrations that rebuild tables, then re-enables them. Alembic is the schema history; the local app also calls `create_all` at startup for a clean local setup.
- Completed stage and row-disposition records are committed with their attempt IDs, so later runtime failures preserve prior evidence. Quarantine and duplicate APIs default to the latest attempt and can query prior attempts explicitly.

## Storage and logging

- SQLite default: `datasets/datatrace.db`.
- Uploads: `datasets/generated/uploads/`.
- Published output: `datasets/output/<run_id>/transactions.csv`.
- Quarantine output: `datasets/quarantine/<run_id>/rejected_records.jsonl`.
- Logs are JSON with UTC timestamp, level and logger; run logs include `run_id`. API responses include an `X-Request-ID` correlation header.

## Optional LLM schema suggestions

Set `AI_PROVIDER=openrouter`, configure `OPENROUTER_API_KEY` in `backend/.env`, and restart the backend. `OPENROUTER_MODEL` defaults to `z-ai/glm-5.3-flash`; the model and its input/output price rates are configurable. Gemini remains an optional provider through `AI_PROVIDER=gemini` and `GEMINI_API_KEY`. In `auto` mode OpenRouter is preferred. Keys remain server-side and are never returned by the API or logged.

The model is called only after an operator requests suggestions or explicitly asks for AI suggestions in a dry-run plan; ordinary row validation never calls it. Requests are cached by schema/profile and model. The default local budget is `$1.00`, with 1,800 input tokens, 1,200 output tokens, and zero retries per request. Worst-case cost is reserved before a request, and token usage, reported/estimated cost, model, task and latency are stored in `ai_usage`. Use Data engine → Reset test budget or `POST /api/v1/ai/budget/reset` to reset the app's local ledger. The local guard uses configured token prices and cannot enforce account-level provider billing; configure an OpenRouter account spend limit separately. Do not change the model without updating both price rates. No provider/model fallback is attempted when a selected model fails; the deterministic local profiler supplies fallback suggestions.

Schema inference sends column names, inferred types, row/null/distinct counts, aggregate statistics, value shapes and abstracted patterns. It does not send row values, source files or file paths. AI suggestions remain drafts until an operator approves mappings, rules or transformations. Generated Python, SQL, shell commands or regular expressions are never executed without allow-list validation.
- Audit records have no delete API and are append-only through the application.

Delete generated local data only after stopping the backend and deciding whether the SQLite audit history should be retained. There is no automated retention or backup job in this local slice.

