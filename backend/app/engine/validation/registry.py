from typing import Any, Protocol, TypeVar

from app.engine.validation.contracts import ApplicabilityAssessment, ValidationResult


class Validator(Protocol):
    validation_id: str
    name: str
    category: str
    version: str

    def applicability(self, context: Any) -> ApplicabilityAssessment: ...

    def validate(self, context: Any, configuration: dict[str, Any]) -> ValidationResult: ...

    def explain(self, result: ValidationResult) -> str: ...


V = TypeVar("V", bound=Validator)


class ValidatorRegistry:
    """Small dependency-injection boundary for independently registered validators."""

    def __init__(self) -> None:
        self._validators: dict[str, Validator] = {}

    def register(self, validator: V) -> V:
        if validator.validation_id in self._validators:
            raise ValueError(f"Validator {validator.validation_id!r} is already registered.")
        self._validators[validator.validation_id] = validator
        return validator

    def get(self, validation_id: str) -> Validator:
        try:
            return self._validators[validation_id]
        except KeyError as exc:
            raise KeyError(f"No validator is registered for {validation_id!r}.") from exc

    def list(self) -> list[Validator]:
        return [self._validators[key] for key in sorted(self._validators)]

    def __len__(self) -> int:
        return len(self._validators)
