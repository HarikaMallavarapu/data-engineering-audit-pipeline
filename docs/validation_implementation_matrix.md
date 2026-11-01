# Validation implementation matrix

## Original catalog checks 001–200

The two required reference catalogs were absent. The individual names, descriptions, category assignments and intent are unknown, so the original `VAL-001` through `VAL-200` entries cannot yet be accurately mapped to code or tests. No rows with invented names or implementation claims are included here. The API currently reports the catalog source as `SOURCE_MISSING`.

## Runtime checks with persisted execution records

These are current DataTrace runtime checks, not mappings to original catalog IDs.

| Runtime ID | Name | Category | Implementation | Applicability | Tests | Limitations |
|---|---|---|---|---|---|---|
| `PROFILED_TYPE:{source_column}` | Inferred type consistency | Profiled type | Executed by general-tabular validation and persisted per run attempt; uncertain/empty cases are recorded as `NOT_APPLICABLE` | High-confidence inferred types (>=80%); nonblank values only | `test_dynamic_engine.py`, `test_validation_contracts.py` | Profile inference is observational; no business contract is implied; finance pipeline is not adapted |
| `RULE:{rule_id}` | Approved rule `{rule_id}` | Configured rule | Executed by the allow-listed declarative rule engine and persisted per run attempt with a configuration snapshot; missing dependencies are `REQUIRES_CONFIGURATION` | Approved enabled rules whose required columns exist | `test_dynamic_engine.py`, `test_validation.py`, `test_validation_contracts.py` | Test coverage is not yet exhaustive for every rule type; custom rules are not original catalog IDs |
| `FINANCE:SCHEMA` | Required finance schema | Structural | Executed and persisted; blocks dependent checks when required columns are missing | Finance pipeline | `test_pipeline_integration.py` | Internal runtime check; not mapped to the original catalog |
| `FINANCE:ROW_FORMAT` | Source row format | Structural | Executed and persisted for finance source rows | Finance pipeline | `test_pipeline_integration.py` | Does not cover every parser-level source-integrity condition |
| `FINANCE:REQUIRED:{field}` | Required field presence | Completeness | One executed and persisted check per required finance field | Finance pipeline | `test_pipeline_integration.py` | Required-field definitions are the fixed finance contract |
| `FINANCE:POSITIVE_AMOUNT` | Positive finite amount | Financial | Executed and persisted per finance run | Finance pipeline | `test_pipeline_integration.py` | Uses the fixed finance `amount` field |
| `FINANCE:SUPPORTED_CURRENCY` | Supported currency | Financial | Executed and persisted per finance run | Finance pipeline | `test_pipeline_integration.py` | Uses the configured supported-currency set |
| `FINANCE:TRANSACTION_STATUS` | Supported transaction status | Domain | Executed and persisted per finance run | Finance pipeline | `test_pipeline_integration.py` | Uses the fixed allowed status set |
| `FINANCE:EVENT_TIME` | UTC event timestamp | Temporal | Executed and persisted per finance run | Finance pipeline | `test_pipeline_integration.py` | Uses the fixed finance timestamp field and parser |
| `FINANCE:CUSTOMER_REFERENCE` / `FINANCE:MERCHANT_REFERENCE` | Customer / merchant reference integrity | Reference integrity | Executed and persisted per finance run | Finance pipeline | `test_pipeline_integration.py` | Depends on configured local reference files |
| `FINANCE:TRANSACTION_UNIQUENESS` | Transaction uniqueness | Uniqueness | Executed and persisted per finance run | Finance pipeline | `test_pipeline_integration.py` | Uses transaction identity within the finance input |
| `FINANCE:EVENT_ORDER` | Event order by source | Temporal | Executed and persisted per finance run; out-of-order rows are warnings | Finance pipeline | `test_pipeline_integration.py` | Warning evidence is not a rejection |
| `TABULAR:ROW_UNIQUENESS` | Row uniqueness | Uniqueness | Executed and persisted for eligible general-tabular rows | General-tabular pipeline | `test_dynamic_engine.py` | Full-row equality after trimming strings; not a business-key rule |
| `TABULAR:ROW_FORMAT` | Parsed row format | Parser integrity | Executed and persisted for every general-tabular source row | General-tabular pipeline | `test_dynamic_engine.py`, `test_ingestion.py` | File-level parse errors fail before a run exists |
| `TABULAR:NONEMPTY_ROW` | Non-empty source row | Completeness | Executed and persisted for parseable general-tabular rows | General-tabular pipeline | `test_dynamic_engine.py`, `test_pipeline_integration.py` | Checks that at least one source-column value is nonblank |
| `RECONCILIATION:INPUT_DISPOSITIONS` | Input rows equal final dispositions | Reconciliation | Executed and persisted per run attempt | All pipelines | `test_reconciliation.py`, `test_dynamic_engine.py` | Dataset-level check; counts only |
| `RECONCILIATION:PUBLISHED_COUNT` | Accepted rows equal published rows | Reconciliation | Executed and persisted per run attempt | All pipelines | `test_reconciliation.py`, `test_dynamic_engine.py` | Dataset-level check; counts only |
| `RECONCILIATION:AMOUNT_TOTALS` | Accepted and published amount totals match | Reconciliation | Executed and persisted for finance runs | Finance pipeline | `test_reconciliation.py` | Per-currency totals; not applicable to generic tabular data |

All `FINANCE:*`, `TABULAR:*`, `RECONCILIATION:*`, `PROFILED_TYPE:*`, and `RULE:*` identifiers are internal runtime IDs, not original catalog IDs. Rule types currently available in the dynamic engine are documented in [dynamic_engine.md](dynamic_engine.md). They must not be counted as a completed subset of the 200 until the original definitions are mapped and each corresponding test/applicability requirement is verified.

## Historical execution interface

`GET /api/v1/validation/history` queries persisted executions joined to their run, source file, and attempt records. The Validation History page exposes those records with validation, status, dataset, pipeline, and date filters. Each row links to the matching run and attempt in the run-results view. It does not infer a result from stage status or create a result when no execution row exists.

`GET /api/v1/validation/analytics` summarizes persisted results by status, critical failure, configuration need, category, check, day, execution duration, and eligible quality score. Score trends are capped to the latest 30 attempts in the selected period, and attempts below the scoring threshold are counted separately.
