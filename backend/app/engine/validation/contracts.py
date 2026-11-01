from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ValidationStatus = Literal[
    "PASS",
    "FAIL",
    "WARNING",
    "ERROR",
    "SKIPPED",
    "NOT_APPLICABLE",
    "REQUIRES_CONFIGURATION",
    "BLOCKED",
]
ApplicabilityStatus = Literal[
    "APPLICABLE",
    "NOT_APPLICABLE",
    "REQUIRES_CONFIGURATION",
    "REQUIRES_BASELINE",
    "REQUIRES_REFERENCE_DATA",
    "UNSUPPORTED_INTEGRATION",
    "DISABLED",
]


class ApplicabilityAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicabilityStatus
    reason: str = Field(min_length=1, max_length=500)
    required_configuration: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Immutable-shaped output shared by validator implementations and APIs."""

    model_config = ConfigDict(extra="forbid")

    validation_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    status: ValidationStatus
    severity: Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
    applicability: ApplicabilityAssessment
    execution_stage: str = Field(min_length=1, max_length=80)
    checked_rows: int = Field(default=0, ge=0)
    passed_rows: int = Field(default=0, ge=0)
    failed_rows: int = Field(default=0, ge=0)
    failure_percentage: float = Field(default=0, ge=0, le=100)
    affected_columns: list[str] = Field(default_factory=list)
    failure_examples: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    message: str = Field(min_length=1, max_length=1000)
    recommendation: str | None = Field(default=None, max_length=1000)
    execution_time_ms: int = Field(default=0, ge=0)
    rule_version: str = Field(default="1.0.0", max_length=40)
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_row_counts(self):
        if self.passed_rows + self.failed_rows > self.checked_rows:
            raise ValueError("Passed and failed rows cannot exceed checked rows.")
        if self.status in {"PASS", "FAIL", "WARNING"} and self.passed_rows + self.failed_rows != self.checked_rows:
            raise ValueError("Executed row results must account for every checked row.")
        return self
