from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
from array import array
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.engine.validation.contracts import ApplicabilityAssessment, ValidationResult

REQUIRED_COLUMNS = (
    "transaction_id",
    "source_system",
    "customer_id",
    "merchant_id",
    "amount",
    "currency",
    "transaction_status",
    "event_time",
)
OPTIONAL_COLUMNS = ("settlement_id",)
SUPPORTED_CURRENCIES = {"USD", "EUR", "INR"}
SUPPORTED_STATUSES = {"authorized", "settled", "refunded", "declined"}


@dataclass(slots=True)
class _FinanceValidationMetric:
    name: str
    category: str
    affected_columns: list[str]
    outcomes: bytearray = field(default_factory=bytearray)
    execution_times_ns: array = field(default_factory=lambda: array("Q"))
    failure_examples: list[dict[str, int]] = field(default_factory=list)
OUTPUT_COLUMNS = (
    "record_id",
    "transaction_id",
    "source_system",
    "customer_id",
    "merchant_id",
    "amount",
    "currency",
    "transaction_status",
    "event_time",
    "ingested_at",
    "settlement_id",
    "is_out_of_order",
    "source_file_id",
    "source_row_number",
)


def parse_csv_bytes(content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader)
    except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise ValueError("The upload is not a readable UTF-8 CSV with a header row.") from exc
    columns = [name.strip() for name in header]
    if not columns or any(not column for column in columns) or len(set(columns)) != len(columns):
        raise ValueError("CSV column names must be non-empty and unique.")

    records: list[dict[str, Any]] = []
    last_physical_line = reader.line_num
    try:
        for values in reader:
            row_number = last_physical_line + 1
            last_physical_line = reader.line_num
            if len(values) == len(columns):
                payload = dict(zip(columns, values, strict=True))
            else:
                payload = {
                    column: values[index] if index < len(values) else None
                    for index, column in enumerate(columns)
                }
                if len(values) > len(columns):
                    payload["_extra_fields"] = values[len(columns) :]
                payload["_parser_error"] = "malformed_row"
            records.append(
                {
                    "source_row_number": row_number,
                    "payload": payload,
                    "parser_error": payload.get("_parser_error"),
                }
            )
    except csv.Error as exc:
        raise ValueError("The CSV contains malformed quoting or an invalid row.") from exc
    return columns, records


def parse_source_bytes(content: bytes, filename: str) -> tuple[list[str], list[dict[str, Any]]]:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".csv":
        return parse_csv_bytes(content)
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return parse_json_bytes(content, line_delimited=suffix in {".jsonl", ".ndjson"})
    if suffix in {".xlsx", ".xlsm"}:
        return parse_excel_bytes(content)
    raise ValueError("Supported tabular formats are UTF-8 CSV, JSON, JSON Lines, and Excel XLSX/XLSM.")


def parse_excel_bytes(content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        frame = pd.read_excel(io.BytesIO(content), header=None, dtype=object, engine="openpyxl")
    except (ImportError, ValueError, OSError, KeyError) as exc:
        raise ValueError("The upload is not a readable Excel workbook with an active sheet.") from exc
    if frame.empty:
        raise ValueError("The Excel workbook must contain a header row.")
    columns = [str(value).strip() if value is not None else "" for value in frame.iloc[0].tolist()]
    if not columns or any(not column for column in columns) or len(set(columns)) != len(columns):
        raise ValueError("Excel column names must be non-empty and unique.")
    records = []
    for row_number, values in enumerate(frame.iloc[1:].itertuples(index=False, name=None), start=2):
        payload = {}
        for column, value in zip(columns, values, strict=False):
            if pd.isna(value):
                payload[column] = None
            elif hasattr(value, "isoformat"):
                payload[column] = value.isoformat()
            else:
                payload[column] = str(value)
        records.append({"source_row_number": row_number, "payload": payload, "parser_error": None})
    return columns, records


def parse_json_bytes(
    content: bytes, *, line_delimited: bool = False
) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("The upload is not valid UTF-8 JSON.") from exc

    values: list[tuple[int, Any, bool]] = []
    if line_delimited:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                values.append((line_number, json.loads(line), False))
            except json.JSONDecodeError:
                values.append((line_number, line, True))
    else:
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("The upload is not valid JSON.") from exc
        items = document if isinstance(document, list) else [document]
        values = [(index + 1, item, False) for index, item in enumerate(items)]

    flattened: list[tuple[int, dict[str, Any], bool]] = []
    columns: list[str] = []
    for row_number, value, parse_error in values:
        if parse_error:
            flattened.append((row_number, {"_raw_value": value}, True))
            continue
        if isinstance(value, dict):
            payload = _flatten_json_object(value)
        elif isinstance(value, list):
            payload = {"value": json.dumps(value, ensure_ascii=False, sort_keys=True)}
        else:
            payload = {"value": value}
        flattened.append((row_number, payload, False))
        for column in payload:
            if column not in columns:
                columns.append(column)

    records = []
    for row_number, payload, parse_error in flattened:
        record_payload = {column: payload.get(column) for column in columns}
        if parse_error:
            record_payload["_parser_error"] = "malformed_json_line"
            record_payload["_raw_value"] = payload.get("_raw_value")
        records.append(
            {
                "source_row_number": row_number,
                "payload": record_payload,
                "parser_error": "malformed_json_line" if parse_error else None,
            }
        )
    return columns, records


def _flatten_json_object(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, child in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, dict):
            if child:
                flattened.update(_flatten_json_object(child, name))
            else:
                flattened[name] = "{}"
        elif isinstance(child, list):
            flattened[name] = json.dumps(child, ensure_ascii=False, sort_keys=True)
        else:
            flattened[name] = child
    return flattened


def profile_records(
    columns: list[str], records: list[dict[str, Any]], *, sample_size: int = 5000
) -> dict[str, Any]:
    from app.engine.profiling.profiler import profile_records as build_profile

    return build_profile(columns, records, sample_size=sample_size)


def validate_tabular_records(
    columns: list[str],
    records: list[dict[str, Any]],
    *,
    profile: dict[str, Any] | None = None,
    source_column_by_output: dict[str, str] | None = None,
) -> dict[str, Any]:
    dispositions: dict[str, list[dict[str, Any]]] = {
        "accepted": [],
        "rejected": [],
        "duplicates": [],
    }
    identities: dict[str, int] = {}
    duplicate_check = {
        "checked_rows": 0,
        "failed_rows": 0,
        "execution_time_ns": 0,
        "failure_examples": [],
    }
    row_format_check = {
        "checked_rows": 0,
        "failed_rows": 0,
        "execution_times_ns": array("Q"),
        "failure_examples": [],
    }
    nonempty_row_check = {
        "checked_rows": 0,
        "failed_rows": 0,
        "execution_times_ns": array("Q"),
        "failure_examples": [],
    }
    profile = profile or {}
    source_column_by_output = source_column_by_output or {}
    null_counts = {
        column: sum(not _has_value(record["payload"].get(column)) for record in records)
        for column in columns
    }
    inferred_types = profile.get("inferred_types", {})
    profile_columns = {
        item.get("name"): item
        for item in profile.get("column_profiles", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    type_checks = []
    not_applicable_type_checks = []
    for column in columns:
        source_column = source_column_by_output.get(column, column)
        expected = inferred_types.get(source_column)
        confidence = profile_columns.get(source_column, {}).get("inferred_type_confidence", 1.0)
        if expected not in _PROFILE_VALIDATED_TYPES or confidence < 0.8:
            reason = (
                "No supported inferred type was available for this column."
                if expected not in _PROFILE_VALIDATED_TYPES
                else "The inferred type confidence is below the 80% threshold."
            )
            not_applicable_type_checks.append(
                {
                    "field": column,
                    "source_field": source_column,
                    "inferred_type": expected,
                    "confidence": confidence,
                    "null_count": null_counts[column],
                    "reason": reason,
                }
            )
            continue
        checked_values = [record["payload"].get(column) for record in records]
        null_count = sum(not _has_value(value) for value in checked_values)
        type_checks.append(
            {
                "field": column,
                "source_field": source_column,
                "inferred_type": expected,
                "confidence": confidence,
                "checked_rows": 0,
                "null_count": null_count,
                "mismatch_count": 0,
                "failure_examples": [],
                "execution_time_ns": 0,
            }
        )
    mixed_type_columns = [
        column
        for column in columns
        if inferred_types.get(source_column_by_output.get(column, column)) == "mixed"
        or profile_columns.get(source_column_by_output.get(column, column), {}).get("mixed_type") is True
    ]
    checks_by_field = {item["field"]: item for item in type_checks}
    null_value_count = sum(null_counts.values())
    type_mismatch_count = 0
    for record in records:
        payload = record["payload"]
        row_number = record["source_row_number"]
        parser_started_ns = time.perf_counter_ns()
        parser_error = record.get("parser_error") or (
            "_parser_error" not in columns and payload.get("_parser_error")
        )
        row_format_check["checked_rows"] += 1
        row_format_check["execution_times_ns"].append(time.perf_counter_ns() - parser_started_ns)
        if parser_error:
            row_format_check["failed_rows"] += 1
            if len(row_format_check["failure_examples"]) < 5:
                row_format_check["failure_examples"].append({"source_row_number": row_number})

        if parser_error:
            reasons = ["malformed_row"]
            dispositions["rejected"].append(
                {**record, "rejection_reasons": reasons, "reason_code": reasons[0]}
            )
            continue

        nonempty_started_ns = time.perf_counter_ns()
        row_has_value = any(_has_value(payload.get(column)) for column in columns)
        nonempty_row_check["checked_rows"] += 1
        nonempty_row_check["execution_times_ns"].append(time.perf_counter_ns() - nonempty_started_ns)
        if not row_has_value:
            nonempty_row_check["failed_rows"] += 1
            if len(nonempty_row_check["failure_examples"]) < 5:
                nonempty_row_check["failure_examples"].append({"source_row_number": row_number})
            reasons = ["empty_row"]
            dispositions["rejected"].append(
                {**record, "rejection_reasons": reasons, "reason_code": reasons[0]}
            )
            continue

        failed_type_checks = []
        for column, check in checks_by_field.items():
            if not _has_value(payload.get(column)):
                continue
            check["checked_rows"] += 1
            check_started_ns = time.perf_counter_ns()
            failed = not _matches_profiled_type(payload[column], check["inferred_type"])
            check["execution_time_ns"] += time.perf_counter_ns() - check_started_ns
            if failed:
                failed_type_checks.append({"field": column, "expected_type": check["inferred_type"]})
                if len(check["failure_examples"]) < 5:
                    check["failure_examples"].append({"source_row_number": row_number})
        if failed_type_checks:
            type_mismatch_count += len(failed_type_checks)
            for failure in failed_type_checks:
                checks_by_field[failure["field"]]["mismatch_count"] += 1
            reasons = [
                f"type_mismatch:{item['field']}:expected_{item['expected_type']}"
                for item in failed_type_checks
            ]
            dispositions["rejected"].append(
                {
                    **record,
                    "reason_code": "type_mismatch",
                    "rejection_reasons": reasons,
                    "failed_type_checks": failed_type_checks,
                }
            )
            continue

        uniqueness_started_ns = time.perf_counter_ns()
        normalized = [_normalize_cell(payload.get(column)) for column in columns]
        identity = hashlib.sha256(
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        duplicate_check["checked_rows"] += 1
        duplicate_check["execution_time_ns"] += time.perf_counter_ns() - uniqueness_started_ns
        if identity in identities:
            duplicate_check["failed_rows"] += 1
            if len(duplicate_check["failure_examples"]) < 5:
                duplicate_check["failure_examples"].append({"source_row_number": row_number})
            dispositions["duplicates"].append(
                {
                    **record,
                    "duplicate_key": f"row_sha256:{identity}",
                    "duplicate_of_row_number": identities[identity],
                }
            )
            continue
        identities[identity] = row_number
        dispositions["accepted"].append(record)

    validation_results = []
    for validation_id, name, category, metric, message_subject, version, configuration in (
        (
            "TABULAR:ROW_FORMAT",
            "Parsed row format",
            "Parser integrity",
            row_format_check,
            "source rows",
            "tabular-row-format-1",
            {"parser_error_fields": ["parser_error", "_parser_error"]},
        ),
        (
            "TABULAR:NONEMPTY_ROW",
            "Non-empty source row",
            "Completeness",
            nonempty_row_check,
            "parseable source rows",
            "tabular-nonempty-row-1",
            {"empty_row_definition": "no nonblank values in any source column", "parse_error_rows_excluded": True},
        ),
    ):
        checked = metric["checked_rows"]
        failed = metric["failed_rows"]
        applicable = checked > 0
        execution_time_ns = sum(metric["execution_times_ns"])
        validation_results.append(
            ValidationResult(
                validation_id=validation_id,
                name=name,
                category=category,
                status=("FAIL" if failed else "PASS") if applicable else "NOT_APPLICABLE",
                severity="ERROR" if failed or applicable else "INFO",
                applicability=ApplicabilityAssessment(
                    status="APPLICABLE" if applicable else "NOT_APPLICABLE",
                    reason=(
                        f"The check assessed {checked} {message_subject}."
                        if applicable
                        else "No eligible source rows were available for this check."
                    ),
                ),
                execution_stage="PRE_TRANSFORMATION",
                checked_rows=checked,
                passed_rows=checked - failed,
                failed_rows=failed,
                failure_percentage=(100 * failed / checked) if checked else 0,
                failure_examples=metric["failure_examples"],
                message=(
                    f"{failed} of {checked} {message_subject} failed this check."
                    if failed
                    else f"All {checked} {message_subject} passed this check."
                    if applicable
                    else "No eligible source rows were available for this check."
                ),
                recommendation="Inspect the listed source rows and correct the parser or source data." if failed else None,
                execution_time_ms=(execution_time_ns + 999_999) // 1_000_000,
                rule_version=version,
                configuration_snapshot=configuration,
            ).model_dump(mode="json")
        )

    for check in type_checks:
        checked = check["checked_rows"]
        failed = check["mismatch_count"]
        if not checked:
            not_applicable_type_checks.append(
                {
                    "field": check["field"],
                    "source_field": check["source_field"],
                    "inferred_type": check["inferred_type"],
                    "confidence": check["confidence"],
                    "null_count": check["null_count"],
                    "reason": "No eligible nonblank values were available for this check.",
                }
            )
            continue
        result = ValidationResult(
            validation_id=f"PROFILED_TYPE:{check['source_field']}",
            name=f"Inferred type consistency: {check['source_field']}",
            category="Profiled type",
            status="FAIL" if failed else "PASS",
            severity="ERROR",
            applicability=ApplicabilityAssessment(
                status="APPLICABLE",
                reason=(
                    f"The local profile inferred {check['inferred_type']} with "
                    f"{check['confidence']:.0%} confidence. This check covers nonblank values only."
                ),
            ),
            execution_stage="PRE_TRANSFORMATION",
            checked_rows=checked,
            passed_rows=checked - failed,
            failed_rows=failed,
            failure_percentage=(100 * failed / checked) if checked else 0,
            affected_columns=[check["field"]],
            failure_examples=check["failure_examples"],
            message=(
                f"{failed} of {checked} nonblank values differ from the inferred type."
                if failed
                else f"All {checked} nonblank values match the inferred type."
            ),
            recommendation="Review the mismatched source values or approve a different schema type." if failed else None,
            execution_time_ms=(check["execution_time_ns"] + 999_999) // 1_000_000,
            rule_version="profile-inference-1",
            configuration_snapshot={
                "inferred_type": check["inferred_type"],
                "confidence": check["confidence"],
                "minimum_confidence": 0.8,
                "null_count_excluded": check["null_count"],
            },
        )
        validation_results.append(result.model_dump(mode="json"))

    for check in not_applicable_type_checks:
        validation_results.append(
            ValidationResult(
                validation_id=f"PROFILED_TYPE:{check['source_field']}",
                name=f"Inferred type consistency: {check['source_field']}",
                category="Profiled type",
                status="NOT_APPLICABLE",
                severity="INFO",
                applicability=ApplicabilityAssessment(
                    status="NOT_APPLICABLE",
                    reason=check["reason"],
                ),
                execution_stage="PRE_TRANSFORMATION",
                affected_columns=[check["field"]],
                message="The inferred-type validator did not run for this column.",
                recommendation="Review or approve a schema type before enabling strict type validation.",
                rule_version="profile-inference-1",
                configuration_snapshot={
                    "inferred_type": check["inferred_type"],
                    "confidence": check["confidence"],
                    "minimum_confidence": 0.8,
                    "null_count_excluded": check["null_count"],
                },
            ).model_dump(mode="json")
        )

    if duplicate_check["checked_rows"]:
        checked = duplicate_check["checked_rows"]
        failed = duplicate_check["failed_rows"]
        validation_results.append(
            ValidationResult(
                validation_id="TABULAR:ROW_UNIQUENESS",
                name="Row uniqueness",
                category="Uniqueness",
                status="FAIL" if failed else "PASS",
                severity="ERROR",
                applicability=ApplicabilityAssessment(
                    status="APPLICABLE",
                    reason=(
                        "Eligible rows in the general-tabular input are compared by normalized full-row identity."
                    ),
                ),
                execution_stage="PRE_TRANSFORMATION",
                checked_rows=checked,
                passed_rows=checked - failed,
                failed_rows=failed,
                failure_percentage=(100 * failed / checked) if checked else 0,
                affected_columns=list(columns),
                failure_examples=duplicate_check["failure_examples"],
                message=(
                    f"{failed} of {checked} eligible rows duplicate an earlier row."
                    if failed
                    else f"All {checked} eligible rows are unique."
                ),
                recommendation="Review duplicate source rows and decide whether they should be retained." if failed else None,
                execution_time_ms=(duplicate_check["execution_time_ns"] + 999_999) // 1_000_000,
                rule_version="tabular-row-identity-1",
                configuration_snapshot={
                    "identity_method": "sha256 of ordered row values after trimming strings",
                    "columns": list(columns),
                    "ineligible_rows_excluded": True,
                },
            ).model_dump(mode="json")
        )

    return {
        "missing_columns": [],
        "added_columns": [],
        "compatibility": "DYNAMIC",
        "out_of_order_count": 0,
        "duplicate_rule": "Full row equality after trimming text cells; input columns remain user-defined.",
        "quality_summary": {
            "columns_checked": len(type_checks),
            "type_mismatch_count": type_mismatch_count,
            "null_value_count": null_value_count,
            "columns_with_nulls": [
                {"field": column, "null_count": count}
                for column, count in null_counts.items()
                if count
            ],
            "mixed_type_columns": mixed_type_columns,
            "type_checks": type_checks,
        },
        "validation_results": validation_results,
        **dispositions,
    }


_PROFILE_VALIDATED_TYPES = {
    "integer", "decimal", "boolean", "datetime", "email", "url", "phone", "currency"
}
_PROFILE_CURRENCY = re.compile(
    r"^\s*(?:[$€£₹]\s*)?-?\d[\d,]*(?:\.\d{1,4})?\s*(?:USD|EUR|GBP|INR|JPY)?\s*$",
    re.IGNORECASE,
)


def _matches_profiled_type(value: Any, expected: str) -> bool:
    text = str(value).strip()
    if expected == "integer":
        return bool(re.fullmatch(r"[+-]?\d+", text))
    if expected == "decimal":
        try:
            return Decimal(text.replace(",", "")).is_finite()
        except (InvalidOperation, ValueError):
            return False
    if expected == "boolean":
        return text.casefold() in {"true", "false", "yes", "no"}
    if expected == "datetime":
        try:
            datetime.fromisoformat(text.replace("Z", "+00:00"))
            return True
        except ValueError:
            return any(
                _matches_date_format(text, date_format)
                for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d")
            )
    if expected == "email":
        return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", text))
    if expected == "url":
        return bool(re.fullmatch(r"https?://\S+", text, re.IGNORECASE))
    if expected == "phone":
        digits = sum(character.isdigit() for character in text)
        return 7 <= digits <= 15 and bool(re.fullmatch(r"\+?[\d().\- ]{7,20}", text))
    if expected == "postal_code":
        return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9 -]{2,11}", text, re.IGNORECASE)) and any(
            character.isdigit() for character in text
        )
    if expected == "currency":
        return bool(_PROFILE_CURRENCY.fullmatch(text))
    return True


def _matches_date_format(value: str, date_format: str) -> bool:
    try:
        datetime.strptime(value, date_format)
        return True
    except ValueError:
        return False


def transform_tabular_records(
    columns: list[str],
    accepted: list[dict[str, Any]],
    source_file_id: str,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    metadata_names = _available_metadata_names(columns)
    output_columns = (*columns, *metadata_names)
    transformed = []
    for record in accepted:
        row_number = record["source_row_number"]
        payload = {column: record["payload"].get(column) for column in columns}
        record_id = hashlib.sha256(f"{source_file_id}:{row_number}".encode()).hexdigest()
        payload.update(
            {
                metadata_names[0]: record_id,
                metadata_names[1]: source_file_id,
                metadata_names[2]: row_number,
            }
        )
        transformed.append(payload)
    return transformed, output_columns


def _available_metadata_names(columns: list[str]) -> tuple[str, str, str]:
    result = []
    existing = set(columns)
    for base in (
        "_datatrace_record_id",
        "_datatrace_source_file_id",
        "_datatrace_source_row_number",
    ):
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        existing.add(candidate)
        result.append(candidate)
    return tuple(result)


def _normalize_cell(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _has_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _value_shape_counts(values: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", text):
            shape = "email_like"
        elif re.fullmatch(r"https?://\S+", text, re.IGNORECASE):
            shape = "url_like"
        elif re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{27,36}", text, re.IGNORECASE):
            shape = "uuid_like"
        elif _is_datetime(text):
            shape = "datetime_like"
        elif _is_integer(text):
            shape = "integer_like"
        elif _is_decimal(text):
            shape = "decimal_like"
        elif text.isalpha():
            shape = "alphabetic_text"
        elif text.isalnum():
            shape = "alphanumeric_text"
        else:
            shape = "mixed_text"
        counts[shape] = counts.get(shape, 0) + 1
    return dict(sorted(counts.items()))


def validate_and_classify(
    columns: list[str],
    records: list[dict[str, Any]],
    customer_ids: set[str],
    merchant_ids: set[str],
) -> dict[str, Any]:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    added_columns = [
        column
        for column in columns
        if column not in REQUIRED_COLUMNS and column not in OPTIONAL_COLUMNS
    ]
    dispositions: dict[str, list[dict[str, Any]]] = {
        "accepted": [],
        "rejected": [],
        "duplicates": [],
    }
    identities: dict[str, int] = {}
    previous_event_by_source: dict[str, datetime] = {}
    out_of_order_count = 0
    def new_validation_metric(
        name: str, category: str, affected_columns: list[str]
    ) -> _FinanceValidationMetric:
        return _FinanceValidationMetric(name, category, affected_columns)

    required_validation_ids = tuple(
        (field, f"FINANCE:REQUIRED:{field}") for field in REQUIRED_COLUMNS
    )
    validation_metrics = {
        "FINANCE:ROW_FORMAT": new_validation_metric("Source row format", "Structural", []),
        "FINANCE:POSITIVE_AMOUNT": new_validation_metric(
            "Positive finite amount", "Financial", ["amount"]
        ),
        "FINANCE:SUPPORTED_CURRENCY": new_validation_metric(
            "Supported currency", "Financial", ["currency"]
        ),
        "FINANCE:TRANSACTION_STATUS": new_validation_metric(
            "Supported transaction status", "Domain", ["transaction_status"]
        ),
        "FINANCE:EVENT_TIME": new_validation_metric(
            "UTC event timestamp", "Temporal", ["event_time"]
        ),
        "FINANCE:CUSTOMER_REFERENCE": new_validation_metric(
            "Customer reference integrity", "Reference integrity", ["customer_id"]
        ),
        "FINANCE:MERCHANT_REFERENCE": new_validation_metric(
            "Merchant reference integrity", "Reference integrity", ["merchant_id"]
        ),
        "FINANCE:TRANSACTION_UNIQUENESS": new_validation_metric(
            "Transaction uniqueness", "Uniqueness", ["source_system", "transaction_id"]
        ),
        "FINANCE:EVENT_ORDER": new_validation_metric(
            "Event order by source", "Temporal", ["source_system", "event_time"]
        ),
    }
    validation_metrics.update(
        {
            validation_id: new_validation_metric(
                f"Required field: {field}", "Completeness", [field]
            )
            for field, validation_id in required_validation_ids
        }
    )

    def record_validation(
        validation_id: str, passed: bool, row_number: int, execution_time_ns: int
    ) -> None:
        metric = validation_metrics[validation_id]
        metric.outcomes.append(passed)
        metric.execution_times_ns.append(execution_time_ns)
        if not passed and len(metric.failure_examples) < 5:
            metric.failure_examples.append({"source_row_number": row_number})

    for record in records:
        payload = record["payload"]
        row_number = record["source_row_number"]
        reasons: list[str] = []
        event_time = None
        row_format_started_ns = time.perf_counter_ns()
        malformed_row = record.get("parser_error") or (
            "_parser_error" not in columns and payload.get("_parser_error")
        )
        if missing_columns:
            reasons.append("missing_required_columns")
        elif malformed_row:
            record_validation(
                "FINANCE:ROW_FORMAT",
                False,
                row_number,
                time.perf_counter_ns() - row_format_started_ns,
            )
            reasons.append("malformed_row")
        else:
            record_validation(
                "FINANCE:ROW_FORMAT",
                True,
                row_number,
                time.perf_counter_ns() - row_format_started_ns,
            )
            for field, validation_id in required_validation_ids:
                check_started_ns = time.perf_counter_ns()
                present = payload.get(field) is not None and bool(str(payload[field]).strip())
                record_validation(
                    validation_id,
                    present,
                    row_number,
                    time.perf_counter_ns() - check_started_ns,
                )
                if not present:
                    reasons.append(f"missing_{field}")
            if not reasons:
                check_started_ns = time.perf_counter_ns()
                amount_positive = False
                try:
                    amount = Decimal(str(payload["amount"]).strip())
                except (InvalidOperation, ValueError):
                    reasons.append("amount_not_numeric")
                else:
                    if not amount.is_finite():
                        reasons.append("amount_not_finite")
                    elif amount <= 0:
                        reasons.append("amount_not_positive")
                    else:
                        amount_positive = True
                record_validation(
                    "FINANCE:POSITIVE_AMOUNT",
                    amount_positive,
                    row_number,
                    time.perf_counter_ns() - check_started_ns,
                )
                check_started_ns = time.perf_counter_ns()
                currency = str(payload["currency"]).strip().upper()
                currency_valid = currency in SUPPORTED_CURRENCIES
                record_validation(
                    "FINANCE:SUPPORTED_CURRENCY",
                    currency_valid,
                    row_number,
                    time.perf_counter_ns() - check_started_ns,
                )
                if not currency_valid:
                    reasons.append("unsupported_currency")
                check_started_ns = time.perf_counter_ns()
                status = str(payload["transaction_status"]).strip().lower()
                status_valid = status in SUPPORTED_STATUSES
                record_validation(
                    "FINANCE:TRANSACTION_STATUS",
                    status_valid,
                    row_number,
                    time.perf_counter_ns() - check_started_ns,
                )
                if not status_valid:
                    reasons.append("unsupported_transaction_status")
                check_started_ns = time.perf_counter_ns()
                event_time = _parse_utc(payload["event_time"])
                event_time_valid = event_time is not None
                record_validation(
                    "FINANCE:EVENT_TIME",
                    event_time_valid,
                    row_number,
                    time.perf_counter_ns() - check_started_ns,
                )
                if not event_time_valid:
                    reasons.append("invalid_event_time")
                check_started_ns = time.perf_counter_ns()
                customer_valid = str(payload["customer_id"]).strip() in customer_ids
                record_validation(
                    "FINANCE:CUSTOMER_REFERENCE",
                    customer_valid,
                    row_number,
                    time.perf_counter_ns() - check_started_ns,
                )
                if not customer_valid:
                    reasons.append("unknown_customer")
                check_started_ns = time.perf_counter_ns()
                merchant_valid = str(payload["merchant_id"]).strip() in merchant_ids
                record_validation(
                    "FINANCE:MERCHANT_REFERENCE",
                    merchant_valid,
                    row_number,
                    time.perf_counter_ns() - check_started_ns,
                )
                if not merchant_valid:
                    reasons.append("unknown_merchant")

        if reasons:
            dispositions["rejected"].append(
                {**record, "rejection_reasons": reasons, "reason_code": reasons[0]}
            )
            continue

        check_started_ns = time.perf_counter_ns()
        identity = f"{str(payload['source_system']).strip().casefold()}:{str(payload['transaction_id']).strip().casefold()}"
        unique = identity not in identities
        record_validation(
            "FINANCE:TRANSACTION_UNIQUENESS",
            unique,
            row_number,
            time.perf_counter_ns() - check_started_ns,
        )
        if not unique:
            dispositions["duplicates"].append(
                {
                    **record,
                    "duplicate_key": identity,
                    "duplicate_of_row_number": identities[identity],
                }
            )
            continue
        identities[identity] = row_number

        check_started_ns = time.perf_counter_ns()
        source = str(payload["source_system"]).strip().casefold()
        out_of_order = (
            source in previous_event_by_source and event_time < previous_event_by_source[source]
        )
        record_validation(
            "FINANCE:EVENT_ORDER",
            not out_of_order,
            row_number,
            time.perf_counter_ns() - check_started_ns,
        )
        if out_of_order:
            out_of_order_count += 1
        previous_event_by_source[source] = event_time
        dispositions["accepted"].append(
            {**record, "event_time_utc": event_time, "is_out_of_order": out_of_order}
        )

    validation_results = []
    if missing_columns:
        validation_results.append(
            ValidationResult(
                validation_id="FINANCE:SCHEMA",
                name="Required finance schema",
                category="Schema",
                status="BLOCKED",
                severity="CRITICAL",
                applicability=ApplicabilityAssessment(
                    status="APPLICABLE",
                    reason="The financial-transactions pipeline requires its declared source columns.",
                ),
                execution_stage="PRE_TRANSFORMATION",
                affected_columns=missing_columns,
                message=f"Validation was blocked because {len(missing_columns)} required columns are missing.",
                recommendation="Add the required fields and register the corrected source file.",
                rule_version="financial-schema-1",
                configuration_snapshot={"required_columns": list(REQUIRED_COLUMNS)},
            ).model_dump(mode="json")
        )
    for validation_id, metric in validation_metrics.items():
        checked = len(metric.outcomes)
        if not checked:
            continue
        failed = metric.outcomes.count(0)
        passed = checked - failed
        execution_time_ns = int(
            np.frombuffer(metric.execution_times_ns, dtype=np.uint64).sum()
        )
        is_warning = validation_id == "FINANCE:EVENT_ORDER" and failed > 0
        validation_results.append(
            ValidationResult(
                validation_id=validation_id,
                name=metric.name,
                category=metric.category,
                status="WARNING" if is_warning else ("FAIL" if failed else "PASS"),
                severity="WARNING" if validation_id == "FINANCE:EVENT_ORDER" else "ERROR",
                applicability=ApplicabilityAssessment(
                    status="APPLICABLE", reason="The finance pipeline ran this deterministic check."
                ),
                execution_stage="PRE_TRANSFORMATION",
                checked_rows=checked,
                passed_rows=passed,
                failed_rows=failed,
                failure_percentage=(100 * failed / checked) if checked else 0,
                affected_columns=metric.affected_columns,
                failure_examples=metric.failure_examples,
                message=(
                    f"{failed} of {checked} checked rows failed this check."
                    if failed
                    else f"All {checked} checked rows passed this check."
                ),
                recommendation="Review the identified source rows and the pipeline's configured rules." if failed else None,
                execution_time_ms=(execution_time_ns + 999_999) // 1_000_000,
                rule_version="financial-validation-1",
                configuration_snapshot={
                    "required_columns": list(REQUIRED_COLUMNS)
                    if validation_id.startswith("FINANCE:REQUIRED:")
                    else [],
                    "supported_currencies": sorted(SUPPORTED_CURRENCIES)
                    if validation_id == "FINANCE:SUPPORTED_CURRENCY"
                    else [],
                    "supported_statuses": sorted(SUPPORTED_STATUSES)
                    if validation_id == "FINANCE:TRANSACTION_STATUS"
                    else [],
                },
            ).model_dump(mode="json")
        )

    disposition_result = {
        "missing_columns": missing_columns,
        "added_columns": added_columns,
        "compatibility": "BLOCKING"
        if missing_columns
        else ("ADDITIVE" if added_columns else "COMPATIBLE"),
        "out_of_order_count": out_of_order_count,
        "validation_results": validation_results,
        **dispositions,
    }
    return disposition_result


def transform_records(
    accepted: list[dict[str, Any]], source_file_id: str, ingested_at: datetime
) -> list[dict[str, Any]]:
    transformed = []
    for record in accepted:
        payload = record["payload"]
        source_system = str(payload["source_system"]).strip().casefold()
        transaction_id = str(payload["transaction_id"]).strip()
        record_id = hashlib.sha256(
            f"{source_system}:{transaction_id.casefold()}".encode()
        ).hexdigest()
        amount = Decimal(str(payload["amount"]).strip()).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        transformed.append(
            {
                "record_id": record_id,
                "transaction_id": transaction_id,
                "source_system": source_system,
                "customer_id": str(payload["customer_id"]).strip(),
                "merchant_id": str(payload["merchant_id"]).strip(),
                "amount": format(amount, ".2f"),
                "currency": str(payload["currency"]).strip().upper(),
                "transaction_status": str(payload["transaction_status"]).strip().lower(),
                "event_time": record["event_time_utc"].isoformat().replace("+00:00", "Z"),
                "ingested_at": ingested_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "settlement_id": (payload.get("settlement_id") or "").strip(),
                "is_out_of_order": str(bool(record["is_out_of_order"])).lower(),
                "source_file_id": source_file_id,
                "source_row_number": record["source_row_number"],
            }
        )
    return transformed


def write_csv(
    path: Path, records: list[dict[str, Any]], columns: tuple[str, ...] = OUTPUT_COLUMNS
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def read_master_ids(path: Path, field_name: str) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if field_name not in (reader.fieldnames or []):
            raise ValueError(f"Reference file {path.name} must contain a {field_name} column.")
        return {str(row[field_name]).strip() for row in reader if row.get(field_name)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_integer(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def _is_decimal(value: str) -> bool:
    try:
        Decimal(value)
        return True
    except InvalidOperation:
        return False


def _is_datetime(value: str) -> bool:
    return _parse_utc(value) is not None


def _parse_utc(value: Any) -> datetime | None:
    try:
        normalized = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC)
    except TypeError, ValueError:
        return None
