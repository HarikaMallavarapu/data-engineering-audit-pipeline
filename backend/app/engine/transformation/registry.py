"""Allow-listed, deterministic, reusable transformations for tabular records."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine.quality.rules import safe_compile


class TransformationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transform_id: str = Field(min_length=1, max_length=80)
    operator: Literal[
        "rename_column",
        "normalize_whitespace",
        "standardize_case",
        "cast_type",
        "parse_date",
        "normalize_currency",
        "replace_null",
        "extract_regex",
    ]
    field: str = Field(min_length=1, max_length=255)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    status: Literal["draft", "approved", "rejected"] = "draft"
    order: int = Field(default=100, ge=0, le=10_000)
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_config(self):
        allowed = {
            "rename_column": {"new_name"},
            "normalize_whitespace": {"collapse_internal"},
            "standardize_case": {"case"},
            "cast_type": {"target_type"},
            "parse_date": {"input_formats", "output_format", "assume_timezone"},
            "normalize_currency": {"strip_symbol", "symbol_map"},
            "replace_null": {"replacement"},
            "extract_regex": {"pattern", "group", "new_column"},
        }[self.operator]
        unexpected = set(self.config) - allowed
        if unexpected:
            raise ValueError(f"Unsupported {self.operator} config keys: {sorted(unexpected)}")
        if self.operator == "rename_column":
            name = self.config.get("new_name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("rename_column requires a non-empty new_name.")
        if self.operator == "standardize_case" and self.config.get("case") not in {"lower", "upper", "title"}:
            raise ValueError("standardize_case requires case=lower, upper, or title.")
        if self.operator == "cast_type" and self.config.get("target_type") not in {
            "string", "integer", "decimal", "boolean", "date"
        }:
            raise ValueError("cast_type target is not allow-listed.")
        if self.operator == "parse_date":
            output_format = self.config.get("output_format", "%Y-%m-%dT%H:%M:%S%z")
            if not isinstance(output_format, str) or len(output_format) > 80:
                raise ValueError("parse_date output_format is invalid.")
            formats = self.config.get("input_formats", [])
            if not isinstance(formats, list) or len(formats) > 20 or any(not isinstance(x, str) or len(x) > 80 for x in formats):
                raise ValueError("parse_date input_formats must be a bounded list of formats.")
        if self.operator == "extract_regex":
            safe_compile(self.config.get("pattern", ""))
            if not isinstance(self.config.get("new_column"), str) or not self.config["new_column"].strip():
                raise ValueError("extract_regex requires a new_column.")
        if self.operator == "normalize_currency":
            mapping = self.config.get("symbol_map", {})
            if not isinstance(mapping, dict) or len(mapping) > 40:
                raise ValueError("symbol_map must be a small object.")
        return self


def apply_transformations(
    columns: list[str],
    records: list[dict[str, Any]],
    transformations: list[TransformationDefinition | dict[str, Any]],
) -> dict[str, Any]:
    parsed = [item if isinstance(item, TransformationDefinition) else TransformationDefinition.model_validate(item) for item in transformations]
    active = sorted((item for item in parsed if item.enabled and item.status == "approved"), key=lambda item: item.order)
    output_columns = list(columns)
    output_records = [
        {
            **record,
            "original_payload": dict(record.get("original_payload", record.get("payload", {}))),
            "payload": dict(record.get("payload", {})),
        }
        for record in records
    ]
    metrics = []
    for transform in active:
        if transform.field not in output_columns and transform.operator != "extract_regex":
            raise ValueError(f"Transformation {transform.transform_id} refers to missing field {transform.field}.")
        if transform.operator == "rename_column":
            new_name = transform.config["new_name"].strip()
            if new_name in output_columns and new_name != transform.field:
                raise ValueError(f"Transformation would create duplicate column {new_name}.")
            output_columns[output_columns.index(transform.field)] = new_name
            for record in output_records:
                record["payload"][new_name] = record["payload"].pop(transform.field, None)
            metrics.append({"transform_id": transform.transform_id, "operator": transform.operator, "changed_rows": len(output_records)})
            continue

        changed = 0
        for record in output_records:
            payload = record["payload"]
            value = payload.get(transform.field)
            try:
                updated = _apply_one(transform, value)
                if transform.operator == "extract_regex":
                    new_column = transform.config["new_column"]
                    if new_column in output_columns:
                        raise ValueError(f"Extraction column already exists: {new_column}")
                    payload[new_column] = updated
                else:
                    payload[transform.field] = updated
                if updated != value:
                    changed += 1
            except (ValueError, TypeError, OverflowError) as exc:
                record["transform_error"] = {
                    "transform_id": transform.transform_id,
                    "operator": transform.operator,
                    "message": str(exc)[:200],
                }
        if transform.operator == "extract_regex":
            new_column = transform.config["new_column"]
            if new_column in output_columns:
                raise ValueError(f"Extraction column already exists: {new_column}")
            if new_column not in output_columns:
                output_columns.append(new_column)
        metrics.append({"transform_id": transform.transform_id, "operator": transform.operator, "changed_rows": changed})

    errors = []
    for record in output_records:
        error = record.get("transform_error")
        if error:
            errors.append(
                {
                    **record,
                    "reason_code": "transformation_failed",
                    "rejection_reasons": [f"transformation_failed:{error['transform_id']}"],
                }
            )
    successful = [record for record in output_records if not record.get("transform_error")]
    return {
        "columns": output_columns,
        "records": successful,
        "rejected": errors,
        "metrics": metrics,
        "applied_transformations": [item.model_dump(mode="json") for item in active],
    }


def _apply_one(transform: TransformationDefinition, value: Any) -> Any:
    config = transform.config
    if transform.operator == "normalize_whitespace":
        if value is None:
            return value
        text = str(value).strip()
        return re.sub(r"\s+", " ", text) if config.get("collapse_internal", True) else text
    if transform.operator == "standardize_case":
        if value is None:
            return value
        return {"lower": str(value).lower, "upper": str(value).upper, "title": str(value).title}[config["case"]]()
    if transform.operator == "cast_type":
        return _cast(value, config["target_type"])
    if transform.operator == "parse_date":
        if value is None or not str(value).strip():
            return value
        text = str(value).strip()
        parsed = None
        for fmt in config.get("input_formats", []):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        timezone = config.get("assume_timezone")
        if parsed.tzinfo is None and timezone == "UTC":
            from datetime import UTC

            parsed = parsed.replace(tzinfo=UTC)
        return parsed.strftime(config.get("output_format", "%Y-%m-%dT%H:%M:%S%z"))
    if transform.operator == "normalize_currency":
        if value is None:
            return value
        text = str(value).strip()
        for symbol, code in config.get("symbol_map", {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}).items():
            if text.startswith(symbol):
                text = f"{text[len(symbol):].strip()} {code}"
                break
        if config.get("strip_symbol"):
            text = re.sub(r"[$€£₹]", "", text)
        return text
    if transform.operator == "replace_null":
        return config.get("replacement") if value is None or not str(value).strip() else value
    if transform.operator == "extract_regex":
        if value is None:
            return None
        match = safe_compile(config["pattern"]).search(str(value)[:4096])
        if not match:
            return None
        group = config.get("group", 0)
        return match.group(group)
    return value


def _cast(value: Any, target: str):
    if value is None or not str(value).strip():
        return value
    text = str(value).strip()
    if target == "string":
        return text
    if target == "integer":
        number = float(text.replace(",", ""))
        if not number.is_integer():
            raise ValueError("Value is not an integer.")
        return str(int(number))
    if target == "decimal":
        from decimal import Decimal, InvalidOperation

        try:
            return str(Decimal(text.replace(",", "")))
        except InvalidOperation as exc:
            raise ValueError("Value is not a decimal.") from exc
    if target == "boolean":
        normalized = text.casefold()
        if normalized in {"true", "yes", "1"}:
            return "true"
        if normalized in {"false", "no", "0"}:
            return "false"
        raise ValueError("Value is not a recognized boolean.")
    if target == "date":
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    return value
