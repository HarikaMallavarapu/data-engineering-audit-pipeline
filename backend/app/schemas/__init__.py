from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiErrorDetail(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    error: ApiErrorDetail


class PipelineResponse(BaseModel):
    pipeline_id: str
    name: str
    version: int


class SourceUploadResponse(BaseModel):
    source_file_id: str
    original_filename: str
    checksum: str
    size_bytes: int
    columns: list[str]
    profile: dict[str, Any] | None = None
    schema_fingerprint: str | None = None
    uploaded_at: datetime


class SourceListResponse(BaseModel):
    items: list[SourceUploadResponse]
    total: int


class RunCreateRequest(BaseModel):
    source_file_id: str = Field(min_length=1, max_length=80)
    pipeline_id: str = "financial-transactions"


class StageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stage_name: str
    attempt_id: str
    status: str
    input_count: int
    output_count: int
    reject_count: int
    duration_ms: int
    details: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None


class RunResponse(BaseModel):
    run_id: str
    pipeline_id: str
    source_file_id: str
    status: Literal["PENDING", "RUNNING", "SUCCESS", "PARTIAL", "FAILED", "CANCELLED"]
    counts: dict[str, int]
    profile: dict[str, Any]
    error: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    stages: list[StageResponse] = []


class RunListResponse(BaseModel):
    items: list[RunResponse]
    total: int


class MappingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_column: str = Field(min_length=1, max_length=255)
    semantic_field: str = Field(min_length=1, max_length=255)
    action: Literal["approve", "edit", "reject"]
    confidence: float = Field(default=1, ge=0, le=1)
    explanation: str = Field(default="User-reviewed mapping.", max_length=300)


class SchemaProfileApprovalRequest(BaseModel):
    mappings: list[MappingDecision] = Field(max_length=300)


class RuleSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_fingerprint: str = Field(min_length=64, max_length=64)
    definition: dict[str, Any]
    status: Literal["draft", "approved", "rejected"] = "draft"


class TransformationSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_fingerprint: str = Field(min_length=64, max_length=64)
    definition: dict[str, Any]
    status: Literal["draft", "approved", "rejected"] = "draft"


class ProcessingPlanRequest(BaseModel):
    source_file_id: str = Field(min_length=1, max_length=80)
    include_ai_suggestions: bool = False
    dry_run: bool = True


class AIBudgetResetRequest(BaseModel):
    confirmation: Literal["RESET_AI_BUDGET"]


class RegexTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(min_length=1, max_length=256)
    values: list[str] = Field(max_length=20)

    @field_validator("values")
    @classmethod
    def bound_test_values(cls, values: list[str]) -> list[str]:
        if any(len(value) > 1024 for value in values):
            raise ValueError("Regex test values are limited to 1,024 characters each.")
        return values


class RejectedRecordResponse(BaseModel):
    attempt_id: str
    source_file_id: str
    source_row_number: int
    original_payload: dict[str, Any]
    reason_code: str
    rejection_reasons: list[str]


class QuarantineListResponse(BaseModel):
    items: list[RejectedRecordResponse]
    total: int
    page: int
    page_size: int


class DuplicateRecordResponse(BaseModel):
    run_id: str
    attempt_id: str
    source_row_number: int
    duplicate_of_row_number: int
    duplicate_key: str


class DuplicateListResponse(BaseModel):
    items: list[DuplicateRecordResponse]
    total: int
    page: int
    page_size: int


class ReconciliationResponse(BaseModel):
    run_id: str
    counts: dict[str, int]
    accepted_amounts_by_currency: dict[str, str]
    published_amounts_by_currency: dict[str, str]
    balanced: bool
    checks: dict[str, bool]


class AuditEventResponse(BaseModel):
    audit_event_id: int
    run_id: str | None
    event_type: str
    event_data: dict[str, Any]
    created_at: datetime


class AuditListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    page: int
    page_size: int


class ValidationExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    validation_execution_id: int
    run_id: str
    attempt_id: str
    validation_id: str
    name: str
    category: str
    status: str
    severity: str
    applicability: str
    applicability_reason: str
    execution_stage: str
    checked_rows: int
    passed_rows: int
    failed_rows: int
    failure_percentage: float
    affected_columns: list[str]
    failure_examples: list[dict[str, Any]]
    message: str
    recommendation: str | None
    execution_time_ms: int
    rule_version: str
    configuration_snapshot: dict[str, Any]
    created_at: datetime


class ValidationRunSummary(BaseModel):
    attempt_id: str
    total_records: int
    executed: int
    passed: int
    failed: int
    warnings: int
    errors: int
    skipped: int
    not_applicable: int
    requires_configuration: int
    blocked: int
    applicable: int
    checked_rows: int
    failed_rows: int
    execution_duration_ms: int


class ValidationRunResultsResponse(BaseModel):
    run_id: str
    attempt_id: str | None
    summary: ValidationRunSummary | None
    items: list[ValidationExecutionResponse]
    total: int
    page: int
    page_size: int


class ValidationHistoryItemResponse(ValidationExecutionResponse):
    pipeline_id: str
    source_file_id: str
    original_filename: str
    attempt_number: int


class ValidationHistoryResponse(BaseModel):
    items: list[ValidationHistoryItemResponse]
    total: int
    page: int
    page_size: int


class QualityScoreResponse(BaseModel):
    run_id: str
    attempt_id: str | None
    score: float | None
    score_status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    coverage_percent: float | None
    applicable_checks: int
    executed_checks: int
    passed_checks: int
    failed_checks: int
    warning_checks: int
    skipped_checks: int
    not_applicable_checks: int
    requires_configuration_checks: int
    blocked_checks: int
    dataset_level_failures: int
    catalog_total: int
    catalog_eligible_checks: int
    catalog_coverage_percent: float | None
    insufficiency_reasons: list[str]
    score_scope: str
    methodology: dict[str, Any]


class ValidationAnalyticsResponse(BaseModel):
    days: int
    from_date: datetime
    through_date: datetime
    pipeline_id: str | None
    total_results: int
    status_counts: dict[str, int]
    critical_failures: int
    requires_configuration: int
    average_execution_time_ms: float | None
    failures_by_category: list[dict[str, Any]]
    most_failing_checks: list[dict[str, Any]]
    daily_trend: list[dict[str, Any]]
    quality_trend: list[dict[str, Any]]
    quality_trend_insufficient_attempts: int
    scope: str


class QualityBaselineCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=80)
    attempt_id: str | None = Field(default=None, min_length=1, max_length=100)
    dataset_identity: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("dataset_identity")
    @classmethod
    def clean_dataset_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Dataset identity cannot be blank.")
        return value


class QualityBaselineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    baseline_id: str
    dataset_identity: str
    pipeline_id: str
    source_file_id: str
    run_id: str
    attempt_id: str
    schema_version: str | None
    baseline_version: int
    sample_size: int
    reference_period_start: datetime
    reference_period_end: datetime
    statistical_configuration: dict[str, Any]
    created_at: datetime


class QualityBaselineListResponse(BaseModel):
    items: list[QualityBaselineResponse]
    total: int
    page: int
    page_size: int


class QualityBaselineComparisonResponse(BaseModel):
    baseline_id: str
    baseline_version: int
    dataset_identity: str
    target_run_id: str
    target_attempt_id: str
    target_source_file_id: str
    row_count_change: dict[str, Any]
    null_rate_changes: list[dict[str, Any]]
    duplicate_rate_change: dict[str, Any]
    schema_drift: dict[str, Any]
    numeric_distribution_drift: list[dict[str, Any]]
    value_shape_distribution_drift: list[dict[str, Any]]
    freshness_changes: list[dict[str, Any]]
    outlier_changes: list[dict[str, Any]]
    validation_failure_changes: list[dict[str, Any]]
    anomaly_signals: list[dict[str, Any]]
    confirmed_invalid_records: bool
    limitations: list[str]


class QualityRunComparisonResponse(BaseModel):
    reference_run_id: str
    reference_attempt_id: str
    reference_pipeline_id: str
    reference_source_file_id: str
    reference_filename: str
    comparison_run_id: str
    comparison_attempt_id: str
    comparison_source_file_id: str
    comparison_filename: str
    row_count_change: dict[str, Any]
    null_rate_changes: list[dict[str, Any]]
    duplicate_rate_change: dict[str, Any]
    schema_drift: dict[str, Any]
    numeric_distribution_drift: list[dict[str, Any]]
    value_shape_distribution_drift: list[dict[str, Any]]
    freshness_changes: list[dict[str, Any]]
    outlier_changes: list[dict[str, Any]]
    validation_failure_changes: list[dict[str, Any]]
    anomaly_signals: list[dict[str, Any]]
    confirmed_invalid_records: bool
    limitations: list[str]


class ValidationCatalogItemResponse(BaseModel):
    validation_id: str
    catalog_number: int
    name: str
    description: str
    category: str
    severity: str
    applicability_requirements: list[str]
    required_columns: list[str]
    required_metadata: list[str]
    configuration_requirements: list[str]
    implementation_status: str
    implementation_version: str
    test_status: str
    limitations: list[str]
    enabled: bool
    supported_file_types: list[str]
    applicability_support: str
    definition_source: str
    last_executed_at: datetime | None = None


class ValidationCatalogResponse(BaseModel):
    source_status: Literal["READY", "PARTIAL", "SOURCE_MISSING", "NOT_IMPORTED"]
    message: str | None = None
    counts: dict[str, int]
    filter_options: dict[str, list[str]] = Field(default_factory=dict)
    items: list[ValidationCatalogItemResponse]
    total: int
    page: int
    page_size: int
