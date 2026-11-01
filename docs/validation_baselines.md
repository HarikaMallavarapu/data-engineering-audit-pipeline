# Quality baselines and drift

## Creating and versioning

`POST /api/v1/quality/baselines` accepts a completed run and optional attempt. The optional dataset identity labels a logical dataset across source files; when omitted, DataTrace uses `<pipeline_id>:<source filename stem>`. Each identity and pipeline pair receives a monotonically increasing baseline version. Baselines are append-only through the API. Creation writes an audit event with the baseline ID, identity, version, and sample size.

The baseline records its source/run/attempt, source schema fingerprint, reference timestamps, sample size, statistical configuration, and a privacy-limited aggregate snapshot. The snapshot includes column names and inferred types, exact row/null/duplicate counts from the registered profile, sampled numeric summary statistics, generalized value-shape counts, numeric histogram buckets, latest timestamps, and persisted validation result counts/statuses. It does not copy raw records, regex examples, or raw category values. Source bytes are checksum-verified before distribution and freshness sampling.

If the source bytes are unavailable but the registered profile remains, the baseline can still preserve that profile's row/schema/null/duplicate aggregates; numeric distribution and freshness snapshots are omitted with a recorded limitation. A checksum mismatch is rejected.

## Comparison method

- Row-count change is measured against the baseline count. A relative change of at least 25% emits a review signal.
- Null-rate and duplicate-rate increases are reported per column and overall. A change of 5 percentage points or more emits a review signal.
- Schema comparison lists added/missing columns and changed inferred types.
- Numeric PSI and a binned Kolmogorov–Smirnov distance use ten bins with the baseline's edges, plus underflow/overflow buckets. Both use the same deterministic, evenly-strided sample capped by the profile sample limit. PSI uses 0.5 count smoothing; PSI values at or above 0.10 are labeled moderate and at or above 0.25 high. PSI and binned KS are withheld unless each observation contains at least 100 numeric values. The KS value is the maximum distance between binned empirical CDFs; no p-value or significance claim is produced.
- Category privacy is preserved by comparing generalized value-shape bucket counts. These are not domain category frequencies and cannot answer questions such as a currency or status value's share.
- Freshness compares the latest parseable timestamp found in each stored source file. It is a timestamp delta, not a freshness SLA verdict.
- IQR outlier-rate changes use the profiler's deterministic sample statistics and are descriptive.
- Validation-failure trends match the persisted runtime validation ID and compare failed/checked row rates. Missing result rows are labeled as missing/new evidence, not as passes. IDs cannot be mapped to the original 200-check catalog until its source files are supplied.

The comparison response always has `confirmed_invalid_records: false`. Drift thresholds are review signals; they do not establish data defects or identify which individual records are invalid. Every comparison includes limitations and the statistical configuration used for its baseline.

## Routes and user interface

- `POST /api/v1/quality/baselines` creates the next version from a completed attempt.
- `GET /api/v1/quality/baselines` lists versions; exact identity and pipeline filters are available.
- `GET /api/v1/quality/baselines/{baseline_id}/compare?run_id=...` returns the aggregate comparison. The target must be a completed attempt from the same pipeline.
- The Validation Center's **Baselines and drift** page creates baselines, selects comparisons, and renders sample limits, signals, distribution summaries, check-result trends, and method limits from the API response.
