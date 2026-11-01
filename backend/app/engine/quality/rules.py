"""Validated, allow-listed data quality rules with no generated-code execution."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.engine.validation.contracts import ApplicabilityAssessment, ValidationResult

RuleType = Literal[
    "required",
    "type",
    "regex",
    "date_range",
    "numeric_range",
    "email",
    "phone",
    "identifier",
    "unique",
    "referential",
    "cross_field",
    "conditional",
    "domain",
    "custom",
]

_ALLOWED_CONFIG_KEYS = {
    "required": {"allow_whitespace"},
    "type": {"expected"},
    "regex": {"pattern", "full_match"},
    "date_range": {"minimum", "maximum", "formats"},
    "numeric_range": {"minimum", "maximum", "inclusive"},
    "email": set(),
    "phone": {"minimum_digits", "maximum_digits"},
    "identifier": {"minimum_length", "maximum_length", "pattern"},
    "unique": set(),
    "referential": {"allowed_values"},
    "cross_field": {"other_field", "operator"},
    "conditional": {"when_field", "when_operator", "when_value", "then_rule", "then_config"},
    "domain": {"domain", "allowed_values"},
    "custom": {"operator", "value", "other_field"},
}


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1, max_length=80)
    field: str = Field(min_length=1, max_length=255)
    rule_type: RuleType
    config: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["error", "warning"] = "error"
    confidence: float = Field(default=1, ge=0, le=1)
    enabled: bool = True
    status: Literal["draft", "approved", "rejected"] = "draft"
    version: int = Field(default=1, ge=1)
    provenance: str = Field(default="user", max_length=80)

    @field_validator("rule_id", "field")
    @classmethod
    def trim_identity(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Rule IDs and field names cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_rule_configuration(self):
        unexpected = set(self.config) - _ALLOWED_CONFIG_KEYS[self.rule_type]
        if unexpected:
            raise ValueError(f"Unsupported {self.rule_type} config keys: {sorted(unexpected)}")
        if self.rule_type == "type" and self.config.get("expected") not in {
            "string", "integer", "decimal", "boolean", "date", "datetime"
        }:
            raise ValueError("type rules require an allow-listed expected type.")
        if self.rule_type == "regex":
            safe_compile(self.config.get("pattern", ""))
        if self.rule_type == "identifier" and self.config.get("pattern"):
            safe_compile(self.config["pattern"])
        if self.rule_type == "referential":
            values = self.config.get("allowed_values")
            if not isinstance(values, list) or len(values) > 10_000:
                raise ValueError("referential rules require up to 10,000 allowed_values.")
        if self.rule_type == "cross_field":
            if not isinstance(self.config.get("other_field"), str):
                raise ValueError("cross_field rules require other_field.")
            if self.config.get("operator") not in _COMPARISON_OPERATORS:
                raise ValueError("cross_field operator is not allow-listed.")
        if self.rule_type == "conditional":
            if self.config.get("when_operator") not in {"equals", "not_equals", "is_present", "is_missing"}:
                raise ValueError("conditional when_operator is not allow-listed.")
            if self.config.get("then_rule") not in {"required", "regex", "numeric_range", "type"}:
                raise ValueError("conditional then_rule is not allow-listed.")
            if not isinstance(self.config.get("when_field"), str):
                raise ValueError("conditional rules require when_field.")
        if self.rule_type == "domain" and self.config.get("domain") not in {
            "positive_number", "non_negative_number", "currency_code", "email_or_blank"
        }:
            raise ValueError("domain rule is not allow-listed.")
        if self.rule_type == "custom" and self.config.get("operator") not in _CUSTOM_OPERATORS:
            raise ValueError("custom operator is not allow-listed.")
        return self


_COMPARISON_OPERATORS = {"equals", "not_equals", "less_than", "less_than_or_equal", "greater_than", "greater_than_or_equal"}
_CUSTOM_OPERATORS = {"is_not_empty", "equals", "not_equals", "matches", "numeric_gt", "numeric_gte", "numeric_lt", "numeric_lte"}
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE = re.compile(r"^\+?[\d().\- ]{7,20}$")
_CURRENCY_CODES = {"USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD", "CHF", "CNY"}

RuleMatcher = Callable[[RuleDefinition, dict[str, Any], dict[str, set[str]]], bool]


class RuleTypeRegistry:
    """Dispatches allow-listed rule types to independently testable matchers."""

    def __init__(self) -> None:
        self._matchers: dict[RuleType, RuleMatcher] = {}

    def register(self, rule_type: RuleType, matcher: RuleMatcher) -> None:
        if rule_type in self._matchers:
            raise ValueError(f"Rule type {rule_type!r} is already registered.")
        self._matchers[rule_type] = matcher

    def get(self, rule_type: RuleType) -> RuleMatcher:
        try:
            return self._matchers[rule_type]
        except KeyError as exc:
            raise KeyError(f"Rule type {rule_type!r} is not registered.") from exc

    def list(self) -> list[str]:
        return sorted(self._matchers)


def safe_compile(pattern: Any) -> re.Pattern[str]:
    if not isinstance(pattern, str) or not pattern or len(pattern) > 256:
        raise ValueError("Regex patterns must contain 1 to 256 characters.")
    if re.search(r"\([^)]*[+*{][^)]*\)[+*{]", pattern):
        raise ValueError("Nested quantified groups are not allowed in regex rules.")
    if re.search(r"\([^)]*\|[^)]*\)[+*{]", pattern):
        raise ValueError("Repeated alternation groups are not allowed in regex rules.")
    if re.search(r"\\[1-9]|\(\?[=!<]", pattern) or "(?P=" in pattern:
        raise ValueError("Backreferences and lookarounds are not allowed in regex rules.")
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValueError("Regex pattern is invalid.") from exc


def evaluate_rules(
    columns: list[str], records: list[dict[str, Any]], rules: list[RuleDefinition | dict[str, Any]]
) -> dict[str, Any]:
    parsed_rules = [item if isinstance(item, RuleDefinition) else RuleDefinition.model_validate(item) for item in rules]
    active = [rule for rule in parsed_rules if rule.enabled and rule.status == "approved"]
    runnable_rules = []
    configuration_results = []
    for rule in active:
        missing_fields = sorted(set(_required_rule_fields(rule)) - set(columns))
        if not missing_fields:
            runnable_rules.append(rule)
            continue
        configuration_results.append(
            ValidationResult(
                validation_id=f"RULE:{rule.rule_id}",
                name=f"Approved rule {rule.rule_id}",
                category="Configured rule",
                status="REQUIRES_CONFIGURATION",
                severity="WARNING" if rule.severity == "warning" else "ERROR",
                applicability=ApplicabilityAssessment(
                    status="REQUIRES_CONFIGURATION",
                    reason="The approved rule references columns that are absent from the current schema.",
                    required_configuration=[f"column:{field}" for field in missing_fields],
                ),
                execution_stage="PRE_TRANSFORMATION",
                affected_columns=missing_fields,
                message=f"This rule requires missing columns: {', '.join(missing_fields)}.",
                recommendation="Update the schema mapping or revise the approved rule before relying on it.",
                rule_version=str(rule.version),
                configuration_snapshot=rule.model_dump(mode="json"),
            ).model_dump(mode="json")
        )

    dispositions = {"accepted": [], "rejected": [], "warning_count": 0}
    seen_values: dict[str, set[str]] = {
        rule.rule_id: set() for rule in runnable_rules if rule.rule_type == "unique"
    }
    rule_metrics = {
        rule.rule_id: {
            "checked_rows": 0,
            "passed_rows": 0,
            "failed_rows": 0,
            "execution_time_ns": 0,
            "failure_examples": [],
        }
        for rule in runnable_rules
    }
    for record in records:
        payload = record.get("payload", {})
        failures: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        for rule in runnable_rules:
            started_ns = time.perf_counter_ns()
            matched = _matches_rule(rule, payload, seen_values)
            metric = rule_metrics[rule.rule_id]
            metric["execution_time_ns"] += time.perf_counter_ns() - started_ns
            metric["checked_rows"] += 1
            if matched:
                metric["passed_rows"] += 1
                continue
            metric["failed_rows"] += 1
            if len(metric["failure_examples"]) < 5:
                metric["failure_examples"].append({"source_row_number": record.get("source_row_number")})
            entry = {"rule_id": rule.rule_id, "rule_type": rule.rule_type, "field": rule.field}
            (warnings if rule.severity == "warning" else failures).append(entry)
        if failures:
            dispositions["rejected"].append(
                {
                    **record,
                    "reason_code": "rule_violation",
                    "rejection_reasons": [f"rule_failed:{item['rule_id']}" for item in failures],
                    "failed_rules": failures,
                    "warnings": warnings,
                }
            )
        else:
            dispositions["accepted"].append({**record, "warnings": warnings})
            dispositions["warning_count"] += len(warnings)
    validation_results = list(configuration_results)
    for rule in runnable_rules:
        metric = rule_metrics[rule.rule_id]
        checked = metric["checked_rows"]
        failed = metric["failed_rows"]
        status = "WARNING" if failed and rule.severity == "warning" else ("FAIL" if failed else "PASS")
        result = ValidationResult(
            validation_id=f"RULE:{rule.rule_id}",
            name=f"Approved rule {rule.rule_id}",
            category="Configured rule",
            status=status,
            severity="WARNING" if rule.severity == "warning" else "ERROR",
            applicability=ApplicabilityAssessment(
                status="APPLICABLE",
                reason=f"Approved {rule.rule_type} rule targets the present field {rule.field!r}.",
            ),
            execution_stage="PRE_TRANSFORMATION",
            checked_rows=checked,
            passed_rows=metric["passed_rows"],
            failed_rows=failed,
            failure_percentage=(100 * failed / checked) if checked else 0,
            affected_columns=[rule.field]
            + ([rule.config["other_field"]] if rule.rule_type == "cross_field" else []),
            failure_examples=metric["failure_examples"],
            message=(
                f"{failed} of {checked} checked rows failed this rule."
                if failed
                else f"All {checked} checked rows passed this rule."
            ),
            recommendation="Review the affected source rows and the approved rule configuration." if failed else None,
            execution_time_ms=(metric["execution_time_ns"] + 999_999) // 1_000_000,
            rule_version=str(rule.version),
            configuration_snapshot=rule.model_dump(mode="json"),
        )
        validation_results.append(result.model_dump(mode="json"))
    return {
        **dispositions,
        "validation_results": validation_results,
        "requires_configuration_count": len(configuration_results),
        "executed_rule_ids": [rule.rule_id for rule in runnable_rules],
    }


def _required_rule_fields(rule: RuleDefinition) -> tuple[str, ...]:
    fields = [rule.field]
    if rule.rule_type == "cross_field":
        fields.append(rule.config["other_field"])
    elif rule.rule_type == "conditional":
        fields.append(rule.config["when_field"])
    elif rule.rule_type == "custom" and rule.config.get("other_field"):
        fields.append(rule.config["other_field"])
    return tuple(fields)


def _matches_rule(rule: RuleDefinition, payload: dict[str, Any], seen: dict[str, set[str]]) -> bool:
    return RULE_TYPE_REGISTRY.get(rule.rule_type)(rule, payload, seen)


def _rule_value(rule: RuleDefinition, payload: dict[str, Any]) -> tuple[Any, str]:
    value = payload.get(rule.field)
    text = "" if value is None else str(value).strip()
    return value, text


def _match_required(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    value, text = _rule_value(rule, payload)
    return bool(text) if rule.config.get("allow_whitespace", False) else value is not None and bool(text)


def _match_type(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    return _matches_type(text, rule.config["expected"])


def _match_regex(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    compiled = safe_compile(rule.config["pattern"])
    return bool(compiled.fullmatch(text) if rule.config.get("full_match", True) else compiled.search(text))


def _match_numeric_range(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    number = _decimal(text)
    return number is not None and _in_range(
        number,
        rule.config.get("minimum"),
        rule.config.get("maximum"),
        rule.config.get("inclusive", True),
    )


def _match_date_range(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    config = rule.config
    current = _parse_date(text, config.get("formats", []))
    if current is None:
        return False
    minimum = _parse_date(str(config["minimum"]), config.get("formats", [])) if config.get("minimum") else None
    maximum = _parse_date(str(config["maximum"]), config.get("formats", [])) if config.get("maximum") else None
    return (minimum is None or current >= minimum) and (maximum is None or current <= maximum)


def _match_email(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    return bool(_EMAIL.fullmatch(text))


def _match_phone(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    digits = sum(char.isdigit() for char in text)
    return bool(_PHONE.fullmatch(text)) and rule.config.get("minimum_digits", 7) <= digits <= rule.config.get("maximum_digits", 15)


def _match_identifier(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    config = rule.config
    if not config.get("minimum_length", 1) <= len(text) <= config.get("maximum_length", 255):
        return False
    return not config.get("pattern") or bool(safe_compile(config["pattern"]).fullmatch(text))


def _match_unique(rule: RuleDefinition, payload: dict[str, Any], seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    if text in seen[rule.rule_id]:
        return False
    seen[rule.rule_id].add(text)
    return bool(text)


def _match_referential(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    allowed = {str(item).casefold() for item in rule.config["allowed_values"]}
    return text.casefold() in allowed


def _match_cross_field(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    value, _text = _rule_value(rule, payload)
    return _compare(value, payload.get(rule.config["other_field"]), rule.config["operator"])


def _match_conditional(rule: RuleDefinition, payload: dict[str, Any], seen: dict[str, set[str]]) -> bool:
    when_value = payload.get(rule.config["when_field"])
    if not _condition_matches(when_value, rule.config):
        return True
    nested = RuleDefinition(
        rule_id=f"{rule.rule_id}:condition",
        field=rule.field,
        rule_type=rule.config["then_rule"],
        config=rule.config.get("then_config", {}),
        status="approved",
    )
    return _matches_rule(nested, payload, seen)


def _match_domain(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    domain = rule.config["domain"]
    number = _decimal(text)
    if domain == "positive_number":
        return number is not None and number > 0
    if domain == "non_negative_number":
        return number is not None and number >= 0
    if domain == "currency_code":
        return text.upper() in _CURRENCY_CODES
    if domain == "email_or_blank":
        return not text or bool(_EMAIL.fullmatch(text))
    return False


def _match_custom(rule: RuleDefinition, payload: dict[str, Any], _seen: dict[str, set[str]]) -> bool:
    _value, text = _rule_value(rule, payload)
    return _custom_operator(text, rule.config, payload)


RULE_TYPE_REGISTRY = RuleTypeRegistry()
for _rule_type, _matcher in (
    ("required", _match_required),
    ("type", _match_type),
    ("regex", _match_regex),
    ("date_range", _match_date_range),
    ("numeric_range", _match_numeric_range),
    ("email", _match_email),
    ("phone", _match_phone),
    ("identifier", _match_identifier),
    ("unique", _match_unique),
    ("referential", _match_referential),
    ("cross_field", _match_cross_field),
    ("conditional", _match_conditional),
    ("domain", _match_domain),
    ("custom", _match_custom),
):
    RULE_TYPE_REGISTRY.register(_rule_type, _matcher)


def _matches_type(value: str, expected: str) -> bool:
    if expected == "string":
        return bool(value)
    if expected == "integer":
        return bool(re.fullmatch(r"[+-]?\d+", value))
    if expected == "decimal":
        return _decimal(value) is not None
    if expected == "boolean":
        return value.casefold() in {"true", "false", "yes", "no", "0", "1"}
    return _parse_date(value, []) is not None if expected == "date" else _parse_datetime(value)


def _decimal(value: str) -> Decimal | None:
    try:
        number = Decimal(value.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _in_range(value: Decimal, minimum: Any, maximum: Any, inclusive: bool) -> bool:
    if minimum is not None:
        low = Decimal(str(minimum))
        if value < low or (not inclusive and value == low):
            return False
    if maximum is not None:
        high = Decimal(str(maximum))
        if value > high or (not inclusive and value == high):
            return False
    return True


def _parse_date(value: str, formats: list[str]):
    for fmt in [*formats, "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _compare(left: Any, right: Any, operator: str) -> bool:
    if operator in {"equals", "not_equals"}:
        equal = str(left).strip().casefold() == str(right).strip().casefold()
        return equal if operator == "equals" else not equal
    left_number, right_number = _decimal(str(left)), _decimal(str(right))
    if left_number is None or right_number is None:
        return False
    return {
        "less_than": left_number < right_number,
        "less_than_or_equal": left_number <= right_number,
        "greater_than": left_number > right_number,
        "greater_than_or_equal": left_number >= right_number,
    }[operator]


def _condition_matches(value: Any, config: dict[str, Any]) -> bool:
    operator = config["when_operator"]
    if operator == "is_present":
        return value is not None and bool(str(value).strip())
    if operator == "is_missing":
        return value is None or not str(value).strip()
    same = str(value).strip().casefold() == str(config.get("when_value", "")).strip().casefold()
    return same if operator == "equals" else not same


def _custom_operator(value: str, config: dict[str, Any], payload: dict[str, Any]) -> bool:
    operator = config["operator"]
    expected = str(config.get("value", ""))
    if operator == "is_not_empty":
        return bool(value)
    if operator == "equals":
        return value == expected
    if operator == "not_equals":
        return value != expected
    if operator == "matches":
        return bool(safe_compile(expected).fullmatch(value))
    number, bound = _decimal(value), _decimal(expected)
    if operator.startswith("numeric_"):
        if number is None or bound is None:
            return False
        return {
            "numeric_gt": number > bound,
            "numeric_gte": number >= bound,
            "numeric_lt": number < bound,
            "numeric_lte": number <= bound,
        }[operator]
    return False
