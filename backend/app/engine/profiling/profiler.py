"""Bounded, deterministic profiling for previously unseen tabular schemas."""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)
_PHONE = re.compile(r"^\+?[\d().\- ]{7,20}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,36}$", re.IGNORECASE)
_POSTAL = re.compile(r"^[A-Z0-9][A-Z0-9 -]{2,11}$", re.IGNORECASE)
_CURRENCY = re.compile(r"^\s*(?:[$€£₹]\s*)?-?\d[\d,]*(?:\.\d{1,4})?\s*(?:USD|EUR|GBP|INR|JPY)?\s*$", re.IGNORECASE)
_ALIAS_GROUPS = {
    "customer_id": {"customer_id", "client_id", "client_reference", "customer_reference", "buyer_id"},
    "transaction_date": {"transaction_date", "txn_date", "txn_dt", "event_date", "event_time", "created_at"},
    "amount": {"amount", "total_amount", "total_value", "value", "transaction_amount", "price"},
    "currency": {"currency", "currency_code", "ccy"},
    "email": {"email", "email_address", "contact_email"},
    "phone": {"phone", "phone_number", "mobile", "telephone"},
}


def profile_records(
    columns: list[str], records: list[dict[str, Any]], *, sample_size: int = 5000
) -> dict[str, Any]:
    """Profile exact counts and bounded value statistics without pandas-wide expansion."""
    row_count = len(records)
    stride = max(1, (row_count + max(1, sample_size) - 1) // max(1, sample_size))
    sampled = records[::stride][: max(1, sample_size)] if records else []
    column_profiles: list[dict[str, Any]] = []
    null_counts: dict[str, int] = {}
    inferred_types: dict[str, str] = {}
    distinct_counts: dict[str, int] = {}
    value_shapes: dict[str, dict[str, int]] = {}
    sample_patterns: dict[str, list[str]] = {}
    mapping_candidates: list[dict[str, Any]] = []
    fingerprint_items: list[dict[str, str]] = []

    for column in columns:
        distinct_values = set()
        null_count = 0
        for record in records:
            value = _cell_text(record.get("payload", {}).get(column))
            if value is None:
                null_count += 1
            else:
                distinct_values.add(value)
        values = [_cell_text(record.get("payload", {}).get(column)) for record in sampled]
        values = [value for value in values if value is not None]
        kinds = Counter(_kind(value) for value in values)
        inferred = _inferred_type(kinds)
        inferred_confidence = _inference_confidence(kinds, inferred)
        null_counts[column] = null_count
        inferred_types[column] = inferred
        distinct_counts[column] = len(distinct_values)
        shape_counts = Counter(_shape(value) for value in values)
        value_shapes[column] = dict(shape_counts)
        patterns = list(dict.fromkeys(_abstract_pattern(value) for value in values[:20]))[:5]
        sample_patterns[column] = patterns

        profile: dict[str, Any] = {
            "name": column,
            "inferred_type": inferred,
            "inferred_type_confidence": inferred_confidence,
            "observed_types": dict(kinds),
            "mixed_type": len(kinds) > 1 and not set(kinds) <= {"integer", "decimal"},
            "null_count": null_count,
            "null_percent": round((null_count / row_count * 100) if row_count else 0, 2),
            "distinct_count": distinct_counts[column],
            "distinct_ratio": round(distinct_counts[column] / max(1, row_count - null_count), 4),
            "sample_size": len(values),
            "value_shapes": dict(shape_counts),
            "sample_patterns": patterns,
        }
        if inferred in {"integer", "decimal", "currency"}:
            numeric = [_to_decimal(value) for value in values]
            numeric = [value for value in numeric if value is not None]
            if numeric:
                sorted_values = sorted(numeric)
                profile["numeric"] = {
                    "min": str(sorted_values[0]),
                    "max": str(sorted_values[-1]),
                    "mean": str(sum(numeric, Decimal(0)) / Decimal(len(numeric))),
                    "median": str(Decimal(str(statistics.median(sorted_values)))),
                    "sample_size": len(numeric),
                    "outlier_count_iqr": _iqr_outliers(sorted_values),
                }
        if values and inferred not in {"integer", "decimal", "currency", "boolean"}:
            lengths = [len(value) for value in values]
            profile["string"] = {
                "min_length": min(lengths),
                "max_length": max(lengths),
                "mean_length": round(sum(lengths) / len(lengths), 2),
                "max_length_sample": max(lengths),
            }
            profile["date_formats"] = sorted(_date_formats(values))
            regex_suggestion = suggest_regex(values)
            if regex_suggestion:
                profile["regex_suggestion"] = regex_suggestion

        alias = _alias_candidate(column, inferred, shape_counts, distinct_counts[column], row_count)
        if alias:
            mapping_candidates.append(alias)
        column_profiles.append(profile)
        fingerprint_items.append({"name": column, "type": inferred})

    duplicate_rows = _duplicate_row_count(columns, records)
    schema_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_items, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "columns": columns,
        "row_count": row_count,
        "profile_sample_size": len(sampled),
        "null_counts": null_counts,
        "inferred_types": inferred_types,
        "distinct_counts": distinct_counts,
        "value_shapes": value_shapes,
        "sample_patterns": sample_patterns,
        "column_profiles": column_profiles,
        "mapping_candidates": mapping_candidates,
        "duplicate_row_count": duplicate_rows,
        "schema_fingerprint": schema_fingerprint,
    }


def suggest_regex(values: list[str], *, minimum_samples: int = 3) -> dict[str, Any] | None:
    """Suggest and locally test a conservative pattern; never treat a few samples as proof."""
    candidates = [value[:256] for value in values if value and len(value) <= 256]
    if len(candidates) < minimum_samples:
        return None
    patterns = [_regex_template(value) for value in candidates]
    pattern, _count = Counter(patterns).most_common(1)[0]
    try:
        compiled = re.compile(pattern)
        matching = [value for value in candidates if compiled.fullmatch(value)]
    except re.error:
        return None
    if len(pattern) > 256 or _unsafe_regex(pattern):
        return None
    confidence = round((len(matching) / len(candidates)) * min(1.0, len(candidates) / 10), 3)
    return {
        "pattern": pattern,
        "confidence": confidence,
        "sample_count": len(candidates),
        "matching_count": len(matching),
        "non_matching_count": len(candidates) - len(matching),
        "matching_examples": matching[:3],
        "non_matching_examples": [value for value in candidates if value not in matching][:3],
        "review_required": True,
        "note": "A sample-derived pattern is a review suggestion, not a universal format guarantee.",
    }


def _cell_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _kind(value: str) -> str:
    lowered = value.casefold()
    if lowered in {"true", "false", "yes", "no"}:
        return "boolean"
    if _EMAIL.fullmatch(value):
        return "email"
    if _URL.fullmatch(value):
        return "url"
    if _UUID.fullmatch(value):
        return "identifier"
    if _CURRENCY.fullmatch(value) and any(char in value for char in "$€£₹"):
        return "currency"
    if _is_integer(value):
        return "integer"
    if _to_decimal(value) is not None:
        return "decimal"
    if _is_date(value):
        return "datetime"
    if _PHONE.fullmatch(value) and sum(char.isdigit() for char in value) >= 7:
        return "phone"
    if _POSTAL.fullmatch(value) and any(char.isdigit() for char in value):
        return "postal_code"
    if value.isalnum() and any(char.isdigit() for char in value) and len(value) >= 5:
        return "identifier"
    return "string"


def _inferred_type(kinds: Counter[str]) -> str:
    if not kinds:
        return "empty"
    if set(kinds) <= {"integer", "decimal"}:
        return "decimal" if "decimal" in kinds else "integer"
    kind, count = kinds.most_common(1)[0]
    if count / sum(kinds.values()) >= 0.8:
        return kind
    return kind if len(kinds) == 1 else "mixed"


def _inference_confidence(kinds: Counter[str], inferred: str) -> float:
    total = sum(kinds.values())
    if total == 0 or inferred in {"empty", "mixed"}:
        return 0.0
    if inferred == "decimal":
        agreeing = kinds.get("integer", 0) + kinds.get("decimal", 0)
    else:
        agreeing = kinds.get(inferred, 0)
    return round(agreeing / total, 3)


def _shape(value: str) -> str:
    kind = _kind(value)
    return f"{kind}_like" if kind in {"email", "url", "phone", "postal_code", "identifier", "currency", "datetime"} else kind


def _abstract_pattern(value: str) -> str:
    result = re.sub(r"\d+", "<digits>", value)
    result = re.sub(r"[A-Za-z]+", "<letters>", result)
    return result[:120]


def _regex_template(value: str) -> str:
    pieces = []
    for part in re.findall(r"\d+|[A-Za-z]+|[^A-Za-z\d]+", value):
        if part.isdigit():
            pieces.append(r"\d{" + str(len(part)) + "}")
        elif part.isalpha():
            klass = "A-Z" if part.isupper() else "a-z" if part.islower() else "A-Za-z"
            pieces.append(f"[{klass}]" + ("{" + str(len(part)) + "}" if len(part) > 1 else "+"))
        else:
            pieces.append(re.escape(part))
    return "^" + "".join(pieces) + "$"


def _unsafe_regex(pattern: str) -> bool:
    return bool(
        re.search(r"\([^)]*[+*{][^)]*\)[+*{]", pattern)
        or re.search(r"\\[1-9]|\(\?[=!<]", pattern)
        or "(?P=" in pattern
    )


def _alias_candidate(name: str, inferred: str, shapes: Counter[str], unique: int, rows: int):
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    for semantic, aliases in _ALIAS_GROUPS.items():
        if normalized in aliases and inferred not in {"mixed", "empty"}:
            confidence = 0.92 if normalized == semantic else 0.78
            evidence = [f"column name alias matches {semantic}", f"inferred type is {inferred}"]
            if semantic == "email" and shapes.get("email_like"):
                confidence = 0.99
                evidence.append("sample values have email-like structure")
            elif semantic == "phone" and shapes.get("phone_like"):
                confidence = 0.97
                evidence.append("sample values have phone-like structure")
            elif semantic in {"customer_id", "transaction_date", "amount", "currency"}:
                confidence = min(confidence, 0.82)
                evidence.append("business meaning still requires confirmation")
            return {
                "source_column": name,
                "suggested_semantic_field": semantic,
                "confidence": confidence,
                "evidence": evidence,
                "status": "suggested",
            }
    return None


def _duplicate_row_count(columns: list[str], records: list[dict[str, Any]]) -> int:
    seen = set()
    duplicates = 0
    for record in records:
        values = [record.get("payload", {}).get(column) for column in columns]
        key = json.dumps(values, sort_keys=True, ensure_ascii=False, default=str)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return duplicates


def _is_integer(value: str) -> bool:
    return bool(re.fullmatch(r"[+-]?\d+", value))


def _to_decimal(value: str) -> Decimal | None:
    cleaned = re.sub(r"[,$€£₹\s]|USD|EUR|GBP|INR|JPY", "", value, flags=re.IGNORECASE)
    try:
        result = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _is_date(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def _date_formats(values: list[str]) -> set[str]:
    formats = {
        "%Y-%m-%d": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        "%Y-%m-%dT%H:%M:%S": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
        "%m/%d/%Y": re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
        "%d/%m/%Y": re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
        "%Y/%m/%d": re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$"),
    }
    found = set()
    for value in values:
        if not _is_date(value):
            continue
        for name, pattern in formats.items():
            if pattern.fullmatch(value):
                found.add(name)
                break
        if "T" in value:
            found.add("ISO-8601 timestamp")
    return found


def _iqr_outliers(values: list[Decimal]) -> int:
    if len(values) < 4:
        return 0
    q1 = Decimal(str(statistics.quantiles(values, n=4, method="inclusive")[0]))
    q3 = Decimal(str(statistics.quantiles(values, n=4, method="inclusive")[2]))
    spread = q3 - q1
    lower, upper = q1 - Decimal("1.5") * spread, q3 + Decimal("1.5") * spread
    return sum(value < lower or value > upper for value in values)
