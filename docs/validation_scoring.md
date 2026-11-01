# Validation scoring

## Scope

`GET /api/v1/quality/runs/{run_id}/score` scores only persisted validation records for one run attempt. The response identifies this scope. The score is not a claim that every source-catalog check ran. Catalog coverage is reported separately and is `null` until all 200 definitions are imported; it then uses exact validation-ID matches for enabled definitions marked fully or partially implemented.

## Formula

Each executed, applicable check receives a severity weight: critical 4, error 3, warning 2, info 1. For row-level checks, failure rate is `failed_rows / checked_rows`. A dataset-level non-PASS result with zero checked rows counts as fully failed. The score is:

`100 × (1 − sum(weight × failure rate) / sum(weight))`

Not-applicable, disabled, and unsupported results are excluded. Skipped, blocked, configuration-dependent, and baseline-dependent checks do not contribute as passes and remain uncovered. Coverage is executed applicable checks divided by all eligible assessed results. It is presented separately from the score.

## Sufficiency gate

A score is available only when at least three checks executed and observed coverage is at least 80%. Otherwise the response returns `score: null`, `score_status: INSUFFICIENT_DATA`, and the reasons. The thresholds, severity weights, formula, counts, and coverage are included in every response so consumers can explain the calculation.

The score does not establish catalog completeness or business validity beyond executed checks. The analytics endpoint charts score trends only for the latest 30 attempts in the requested window that meet the same sufficiency gate. Historical aggregate comparisons are documented in [validation baselines](validation_baselines.md). They report qualified drift signals and suppress numeric PSI and binned KS below the minimum sample size; neither method proves that individual records are invalid.
