"""Aggregate-only baselines and cautious run-to-run drift comparisons."""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.engine.pipeline import parse_source_bytes
from app.engine.profiling.profiler import _to_decimal
from app.models import SourceFile, ValidationExecution

MINIMUM_STATISTICAL_SAMPLE = 100
NUMERIC_BIN_COUNT = 10
PSI_SMOOTHING_COUNT = 0.5
PSI_MODERATE_THRESHOLD = 0.10
PSI_HIGH_THRESHOLD = 0.25


def statistical_configuration() -> dict[str, Any]:
    return {
        "minimum_sample_size": MINIMUM_STATISTICAL_SAMPLE,
        "numeric_bins": NUMERIC_BIN_COUNT,
        "psi_smoothing_count": PSI_SMOOTHING_COUNT,
        "psi_interpretation_thresholds": {
            "moderate": PSI_MODERATE_THRESHOLD,
            "high": PSI_HIGH_THRESHOLD,
        },
        "numeric_sample_method": "deterministic evenly-strided sample capped by the profile sample limit",
        "ks_method": "maximum distance between baseline and current binned empirical CDFs; no p-value is inferred",
        "category_method": "sampled value-shape distributions only; raw category values are not stored",
        "anomaly_thresholds": {"row_count_relative_change": 0.25, "rate_absolute_change": 0.05},
    }


def source_observation(
    source: SourceFile,
    *,
    sample_limit: int,
    numeric_reference_edges: dict[str, list[str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], list[str]]:
    """Return a privacy-limited profile, baseline numeric histograms, and timestamp samples."""
    profile = source.profile or {}
    column_profiles = {
        item.get("name"): item
        for item in profile.get("column_profiles", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    safe_columns = {}
    for name, item in column_profiles.items():
        safe_columns[name] = {
            "inferred_type": item.get("inferred_type"),
            "sample_size": item.get("sample_size", 0),
            "value_shapes": item.get("value_shapes", {}),
            "numeric": {
                key: item["numeric"][key]
                for key in ("min", "max", "mean", "median", "sample_size", "outlier_count_iqr")
                if key in item.get("numeric", {})
            }
            if isinstance(item.get("numeric"), dict)
            else None,
        }

    snapshot = {
        "columns": list(profile.get("columns", source.columns)),
        "row_count": int(profile.get("row_count", 0)),
        "profile_sample_size": int(profile.get("profile_sample_size", 0)),
        "null_counts": dict(profile.get("null_counts", {})),
        "inferred_types": dict(profile.get("inferred_types", {})),
        "duplicate_row_count": int(profile.get("duplicate_row_count", 0)),
        "column_profiles": safe_columns,
    }
    if not Path(source.storage_path).is_file():
        return snapshot, {}, {}, ["The source file is unavailable; distribution and freshness comparisons are omitted."]

    content = Path(source.storage_path).read_bytes()
    if hashlib.sha256(content).hexdigest() != source.checksum:
        raise ValueError("The stored source checksum no longer matches its registered checksum.")
    columns, records = parse_source_bytes(content, source.original_filename)
    row_count = len(records)
    stride = max(1, (row_count + max(1, sample_limit) - 1) // max(1, sample_limit))
    sampled_records = records[::stride][:max(1, sample_limit)] if records else []
    numeric_samples: dict[str, list[Any]] = {}
    latest_timestamps: dict[str, str] = {}
    inferred_types = snapshot["inferred_types"]
    for column in columns:
        expected_type = inferred_types.get(column)
        values = [record.get("payload", {}).get(column) for record in sampled_records]
        if expected_type in {"integer", "decimal", "currency"}:
            parsed = [_to_decimal(str(value).strip()) for value in values if value is not None and str(value).strip()]
            numeric_samples[column] = [value for value in parsed if value is not None]
        if expected_type == "datetime":
            all_values = [record.get("payload", {}).get(column) for record in records]
            parsed_dates = [_parse_datetime(value) for value in all_values if value is not None]
            dates = [value for value in parsed_dates if value is not None]
            if dates:
                latest_timestamps[column] = max(dates).isoformat().replace("+00:00", "Z")

    numeric_distributions = {}
    for column, values in numeric_samples.items():
        if values:
            numeric_distributions[column] = _histogram(
                values,
                NUMERIC_BIN_COUNT,
                (numeric_reference_edges or {}).get(column),
            )
    return snapshot, numeric_distributions, latest_timestamps, []


def compare_observations(
    baseline_profile: dict[str, Any],
    baseline_distributions: dict[str, Any],
    baseline_timestamps: dict[str, str],
    target_profile: dict[str, Any],
    target_distributions: dict[str, Any],
    target_timestamps: dict[str, str],
    baseline_validation: list[dict[str, Any]],
    target_validation: list[ValidationExecution],
    *,
    configuration: dict[str, Any],
    additional_limitations: list[str] | None = None,
) -> dict[str, Any]:
    baseline_rows = int(baseline_profile.get("row_count", 0))
    target_rows = int(target_profile.get("row_count", 0))
    row_delta = target_rows - baseline_rows
    row_delta_ratio = row_delta / baseline_rows if baseline_rows else None
    signals: list[dict[str, Any]] = []
    limitations = list(additional_limitations or [])
    if baseline_rows and row_delta_ratio is not None and abs(row_delta_ratio) >= configuration["anomaly_thresholds"]["row_count_relative_change"]:
        signals.append({"type": "ROW_COUNT_CHANGE", "value": round(row_delta_ratio * 100, 2), "threshold": configuration["anomaly_thresholds"]["row_count_relative_change"] * 100, "confirmed_invalid_records": False})

    base_columns = set(baseline_profile.get("columns", []))
    target_columns = set(target_profile.get("columns", []))
    base_types = baseline_profile.get("inferred_types", {})
    target_types = target_profile.get("inferred_types", {})
    schema_drift = {
        "added_columns": sorted(target_columns - base_columns),
        "missing_columns": sorted(base_columns - target_columns),
        "type_changes": [
            {"column": column, "baseline_type": base_types.get(column), "current_type": target_types.get(column)}
            for column in sorted(base_columns & target_columns)
            if base_types.get(column) != target_types.get(column)
        ],
        "changed": base_columns != target_columns or any(base_types.get(column) != target_types.get(column) for column in base_columns & target_columns),
    }
    if schema_drift["changed"]:
        signals.append({"type": "SCHEMA_DRIFT", "severity": "WARNING", "confirmed_invalid_records": False})

    base_nulls = baseline_profile.get("null_counts", {})
    target_nulls = target_profile.get("null_counts", {})
    common_columns = sorted(base_columns & target_columns)
    null_changes = []
    for column in common_columns:
        base_rate = base_nulls.get(column, 0) / baseline_rows if baseline_rows else None
        target_rate = target_nulls.get(column, 0) / target_rows if target_rows else None
        delta = target_rate - base_rate if base_rate is not None and target_rate is not None else None
        null_changes.append({"column": column, "baseline_rate": base_rate, "current_rate": target_rate, "delta_percentage_points": round(delta * 100, 2) if delta is not None else None})
        if delta is not None and abs(delta) >= configuration["anomaly_thresholds"]["rate_absolute_change"]:
            signals.append({"type": "NULL_RATE_CHANGE", "column": column, "value": round(delta * 100, 2), "threshold": configuration["anomaly_thresholds"]["rate_absolute_change"] * 100, "confirmed_invalid_records": False})

    base_duplicate_rate = baseline_profile.get("duplicate_row_count", 0) / baseline_rows if baseline_rows else None
    target_duplicate_rate = target_profile.get("duplicate_row_count", 0) / target_rows if target_rows else None
    duplicate_delta = target_duplicate_rate - base_duplicate_rate if base_duplicate_rate is not None and target_duplicate_rate is not None else None
    duplicate_change = {"baseline_rate": base_duplicate_rate, "current_rate": target_duplicate_rate, "delta_percentage_points": round(duplicate_delta * 100, 2) if duplicate_delta is not None else None}
    if duplicate_delta is not None and duplicate_delta >= configuration["anomaly_thresholds"]["rate_absolute_change"]:
        signals.append({"type": "DUPLICATE_RATE_INCREASE", "value": round(duplicate_delta * 100, 2), "threshold": configuration["anomaly_thresholds"]["rate_absolute_change"] * 100, "confirmed_invalid_records": False})

    numeric_drift = []
    outlier_changes = []
    for column, base_distribution in baseline_distributions.items():
        target_distribution = target_distributions.get(column)
        base_numeric = baseline_profile.get("column_profiles", {}).get(column, {}).get("numeric") or {}
        target_numeric = target_profile.get("column_profiles", {}).get(column, {}).get("numeric") or {}
        if target_distribution is None:
            numeric_drift.append({"column": column, "status": "NOT_COMPARABLE", "reason": "The current run has no sampled numeric values for this column."})
            continue
        base_n, target_n = base_distribution["sample_size"], target_distribution["sample_size"]
        if min(base_n, target_n) < configuration["minimum_sample_size"]:
            numeric_drift.append({"column": column, "status": "INSUFFICIENT_SAMPLE", "baseline_sample_size": base_n, "current_sample_size": target_n, "psi": None, "binned_ks_distance": None})
        else:
            psi = _population_stability_index(base_distribution["counts"], target_distribution["counts"])
            ks_distance = _binned_ks_distance(base_distribution["counts"], target_distribution["counts"])
            level = "HIGH_SHIFT" if psi >= configuration["psi_interpretation_thresholds"]["high"] else "MODERATE_SHIFT" if psi >= configuration["psi_interpretation_thresholds"]["moderate"] else "LOW_SHIFT"
            numeric_drift.append({"column": column, "status": "ASSESSED", "baseline_sample_size": base_n, "current_sample_size": target_n, "psi": round(psi, 6), "binned_ks_distance": round(ks_distance, 6), "psi_signal": level, "ks_method": configuration["ks_method"], "confirmed_invalid_records": False})
            if level == "HIGH_SHIFT":
                signals.append({"type": "NUMERIC_DISTRIBUTION_SHIFT", "column": column, "psi": round(psi, 6), "confirmed_invalid_records": False})
        if base_numeric and target_numeric:
            base_rate = base_numeric.get("outlier_count_iqr", 0) / max(1, base_numeric.get("sample_size", 0))
            target_rate = target_numeric.get("outlier_count_iqr", 0) / max(1, target_numeric.get("sample_size", 0))
            outlier_changes.append({"column": column, "baseline_rate": base_rate, "current_rate": target_rate, "delta_percentage_points": round((target_rate - base_rate) * 100, 2)})
            if target_rate > base_rate:
                signals.append({"type": "OUTLIER_RATE_INCREASE", "column": column, "confirmed_invalid_records": False})

    value_shape_drift = _compare_value_shapes(baseline_profile, target_profile, configuration)
    for drift in value_shape_drift:
        if drift.get("psi_signal") == "HIGH_SHIFT":
            signals.append({"type": "VALUE_SHAPE_DISTRIBUTION_SHIFT", "column": drift["column"], "psi": drift["psi"], "confirmed_invalid_records": False})
    freshness_changes = _compare_freshness(baseline_timestamps, target_timestamps)
    failure_changes = _compare_validation_failures(baseline_validation, target_validation)
    return {
        "row_count_change": {"baseline": baseline_rows, "current": target_rows, "delta": row_delta, "delta_percent": round(row_delta_ratio * 100, 2) if row_delta_ratio is not None else None},
        "null_rate_changes": null_changes,
        "duplicate_rate_change": duplicate_change,
        "schema_drift": schema_drift,
        "numeric_distribution_drift": numeric_drift,
        "value_shape_distribution_drift": value_shape_drift,
        "freshness_changes": freshness_changes,
        "outlier_changes": outlier_changes,
        "validation_failure_changes": failure_changes,
        "anomaly_signals": signals,
        "confirmed_invalid_records": False,
        "limitations": limitations + [
            "Drift signals compare aggregate profiles; they do not prove individual records invalid.",
            "Numeric PSI and binned KS are omitted below the configured minimum sample size; the KS output is a statistic without a p-value.",
            "Category values are not stored; categorical comparisons use generalized value-shape counts.",
            "Freshness uses the latest timestamp available in each stored source file; malformed or unavailable source files omit timestamp comparisons.",
            "Validation failure comparisons use runtime IDs until original catalog definitions are mapped.",
        ],
    }


def _histogram(values: list[Any], bin_count: int, reference_edges: list[str] | None = None) -> dict[str, Any]:
    if reference_edges:
        edges = reference_edges
    else:
        low, high = min(values), max(values)
        if low == high:
            padding = abs(low) * Decimal("0.05") or Decimal("1")
            low, high = low - padding, high + padding
        edges = [str(low + (high - low) * index / bin_count) for index in range(bin_count + 1)]
    return {"edges": edges, "counts": _histogram_counts(values, edges, bin_count), "sample_size": len(values)}


def _histogram_counts(values: list[Any], edge_values: list[str], bin_count: int) -> list[int]:
    edges = [_to_decimal(value) for value in edge_values]
    counts = [0] * (bin_count + 2)
    for value in values:
        number = _to_decimal(str(value))
        if number is None:
            continue
        if number < edges[0]:
            counts[0] += 1
        elif number > edges[-1]:
            counts[-1] += 1
        elif number == edges[-1]:
            counts[bin_count] += 1
        else:
            index = 1
            while index < bin_count and number >= edges[index]:
                index += 1
            counts[index] += 1
    return counts


def _population_stability_index(expected_counts: list[int], actual_counts: list[int]) -> float:
    bins = max(len(expected_counts), len(actual_counts))
    expected = expected_counts + [0] * (bins - len(expected_counts))
    actual = actual_counts + [0] * (bins - len(actual_counts))
    expected_total, actual_total = sum(expected), sum(actual)
    expected_denominator = expected_total + PSI_SMOOTHING_COUNT * bins
    actual_denominator = actual_total + PSI_SMOOTHING_COUNT * bins
    result = 0.0
    for expected_count, actual_count in zip(expected, actual, strict=True):
        expected_rate = (expected_count + PSI_SMOOTHING_COUNT) / expected_denominator
        actual_rate = (actual_count + PSI_SMOOTHING_COUNT) / actual_denominator
        result += (actual_rate - expected_rate) * math.log(actual_rate / expected_rate)
    return result


def _binned_ks_distance(expected_counts: list[int], actual_counts: list[int]) -> float:
    expected_total, actual_total = sum(expected_counts), sum(actual_counts)
    expected_cumulative = actual_cumulative = 0
    maximum_distance = 0.0
    bins = max(len(expected_counts), len(actual_counts))
    for index in range(bins):
        expected_cumulative += expected_counts[index] if index < len(expected_counts) else 0
        actual_cumulative += actual_counts[index] if index < len(actual_counts) else 0
        expected_rate = expected_cumulative / max(1, expected_total)
        actual_rate = actual_cumulative / max(1, actual_total)
        maximum_distance = max(maximum_distance, abs(expected_rate - actual_rate))
    return maximum_distance


def _compare_value_shapes(base: dict[str, Any], target: dict[str, Any], configuration: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    base_profiles = base.get("column_profiles", {})
    target_profiles = target.get("column_profiles", {})
    for column in sorted(set(base_profiles) & set(target_profiles)):
        base_shapes = base_profiles[column].get("value_shapes", {})
        target_shapes = target_profiles[column].get("value_shapes", {})
        base_n = sum(base_shapes.values())
        target_n = sum(target_shapes.values())
        if min(base_n, target_n) < configuration["minimum_sample_size"]:
            changes.append({"column": column, "status": "INSUFFICIENT_SAMPLE", "baseline_sample_size": base_n, "current_sample_size": target_n})
            continue
        psi = _population_stability_index(
            [base_shapes.get(key, 0) for key in sorted(set(base_shapes) | set(target_shapes))],
            [target_shapes.get(key, 0) for key in sorted(set(base_shapes) | set(target_shapes))],
        )
        thresholds = configuration["psi_interpretation_thresholds"]
        level = "HIGH_SHIFT" if psi >= thresholds["high"] else "MODERATE_SHIFT" if psi >= thresholds["moderate"] else "LOW_SHIFT"
        changes.append({"column": column, "status": "ASSESSED", "psi": round(psi, 6), "psi_signal": level, "measure": "value-shape distribution; not domain category values", "confirmed_invalid_records": False})
    return changes


def _compare_freshness(base: dict[str, str], target: dict[str, str]) -> list[dict[str, Any]]:
    changes = []
    for column in sorted(set(base) & set(target)):
        base_time, target_time = _parse_datetime(base[column]), _parse_datetime(target[column])
        if base_time and target_time:
            changes.append({"column": column, "baseline_latest_sampled_timestamp": base[column], "current_latest_sampled_timestamp": target[column], "delta_seconds": (target_time - base_time).total_seconds()})
    return changes


def _compare_validation_failures(base: list[dict[str, Any]], target: list[ValidationExecution]) -> list[dict[str, Any]]:
    baseline_by_id = {item["validation_id"]: item for item in base}
    target_by_id = {item.validation_id: item for item in target}
    changes = []
    for validation_id in sorted(set(baseline_by_id) | set(target_by_id)):
        before = baseline_by_id.get(validation_id)
        after = target_by_id.get(validation_id)
        before_rate = _failure_rate(before["status"], before["checked_rows"], before["failed_rows"]) if before else None
        after_rate = _failure_rate(after.status, after.checked_rows, after.failed_rows) if after else None
        changes.append({
            "validation_id": validation_id,
            "baseline_status": before.get("status") if before else None,
            "current_status": after.status if after else None,
            "baseline_failure_rate": before_rate,
            "current_failure_rate": after_rate,
            "delta_percentage_points": round((after_rate - before_rate) * 100, 2) if before_rate is not None and after_rate is not None else None,
            "assessment": "MISSING_CURRENT_RESULT" if after is None else "NEW_CURRENT_RESULT" if before is None else "COMPARED",
        })
    return changes


def _failure_rate(status: str, checked_rows: int, failed_rows: int) -> float | None:
    if status not in {"PASS", "FAIL", "WARNING"}:
        return None
    if checked_rows:
        return min(1.0, max(0.0, failed_rows / checked_rows))
    return 0.0 if status == "PASS" else 1.0


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
