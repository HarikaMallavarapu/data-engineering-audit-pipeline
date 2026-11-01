import pytest
from app.engine.validation import ApplicabilityAssessment, ValidationResult, ValidatorRegistry
from pydantic import ValidationError


def test_validation_result_requires_row_accounting_and_explicit_applicability():
    result = ValidationResult(
        validation_id="RULE:amount_floor",
        name="Approved rule amount_floor",
        category="Configured rule",
        status="FAIL",
        severity="ERROR",
        applicability=ApplicabilityAssessment(status="APPLICABLE", reason="Approved rule targets amount."),
        execution_stage="PRE_TRANSFORMATION",
        checked_rows=2,
        passed_rows=1,
        failed_rows=1,
        failure_percentage=50,
        affected_columns=["amount"],
        failure_examples=[{"source_row_number": 3}],
        message="1 of 2 checked rows failed this rule.",
        configuration_snapshot={"minimum": 0},
    )
    assert result.model_dump(mode="json")["applicability"]["status"] == "APPLICABLE"

    payload = result.model_dump()
    payload["passed_rows"] = 2
    with pytest.raises(ValidationError):
        ValidationResult.model_validate(payload)


def test_validator_registry_rejects_duplicate_ids_and_lists_deterministically():
    class StubValidator:
        def __init__(self, validation_id):
            self.validation_id = validation_id
            self.name = validation_id
            self.category = "test"
            self.version = "1.0.0"

        def applicability(self, _context):
            return ApplicabilityAssessment(status="APPLICABLE", reason="Test validator.")

        def validate(self, _context, _configuration):
            raise NotImplementedError

        def explain(self, result):
            return result.message

    registry = ValidatorRegistry()
    registry.register(StubValidator("B"))
    registry.register(StubValidator("A"))
    assert [item.validation_id for item in registry.list()] == ["A", "B"]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(StubValidator("A"))
