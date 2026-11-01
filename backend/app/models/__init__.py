from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Store UTC timestamps portably and restore an explicit UTC offset on reads."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DateTime(timezone=dialect.name != "sqlite"))

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return normalized.replace(tzinfo=None) if dialect.name == "sqlite" else normalized

    def process_result_value(self, value: datetime | None, _dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_pipeline_version_positive"),)
    pipeline_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    runs: Mapped[list[PipelineRun]] = relationship(back_populates="pipeline")
    versions: Mapped[list[PipelineVersion]] = relationship(back_populates="pipeline")


class PipelineVersion(Base):
    __tablename__ = "pipeline_versions"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "version", name="uq_pipeline_version"),
        UniqueConstraint("pipeline_id", "pipeline_version_id", name="uq_pipeline_version_identity"),
        CheckConstraint("version >= 1", name="ck_pipeline_version_number_positive"),
    )

    pipeline_version_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(ForeignKey("pipelines.pipeline_id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    pipeline: Mapped[Pipeline] = relationship(back_populates="versions")


class SourceFile(Base):
    __tablename__ = "source_files"
    source_file_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    columns: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    runs: Mapped[list[PipelineRun]] = relationship(back_populates="source_file")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_pipeline_runs_idempotency_key"),
        UniqueConstraint("run_id", "source_file_id", name="uq_run_source_file"),
        ForeignKeyConstraint(
            ["pipeline_id", "pipeline_version_id"],
            ["pipeline_versions.pipeline_id", "pipeline_versions.pipeline_version_id"],
            name="fk_run_pipeline_version_matches_pipeline",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCESS','PARTIAL','FAILED','CANCELLED')",
            name="ck_pipeline_run_status",
        ),
    )
    run_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_id: Mapped[str] = mapped_column(ForeignKey("pipelines.pipeline_id"), nullable=False)
    pipeline_version_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_file_id: Mapped[str] = mapped_column(
        ForeignKey("source_files.source_file_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    pipeline: Mapped[Pipeline] = relationship(back_populates="runs")
    source_file: Mapped[SourceFile] = relationship(back_populates="runs")
    attempts: Mapped[list[RunAttempt]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    stages: Mapped[list[StageExecution]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    rejected_records: Mapped[list[RejectedRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    duplicate_records: Mapped[list[DuplicateRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[PublishedArtifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    reconciliation: Mapped[ReconciliationResult | None] = relationship(
        back_populates="run", uselist=False, cascade="all, delete-orphan"
    )


class RunAttempt(Base):
    __tablename__ = "run_attempts"
    __table_args__ = (
        UniqueConstraint("run_id", "attempt_number", name="uq_run_attempt_number"),
        UniqueConstraint("run_id", "attempt_id", name="uq_run_attempt_id"),
        CheckConstraint("attempt_number >= 1", name="ck_run_attempt_number_positive"),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCESS','PARTIAL','FAILED','CANCELLED')",
            name="ck_run_attempt_status",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline_runs.run_id"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    run: Mapped[PipelineRun] = relationship(back_populates="attempts")
    stages: Mapped[list[StageExecution]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", overlaps="run,stages"
    )


class StageExecution(Base):
    __tablename__ = "stage_executions"
    __table_args__ = (
        UniqueConstraint("attempt_id", "stage_name", name="uq_stage_attempt_name"),
        ForeignKeyConstraint(
            ["run_id", "attempt_id"],
            ["run_attempts.run_id", "run_attempts.attempt_id"],
            name="fk_stage_run_attempt",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCESS','PARTIAL','FAILED','SKIPPED')",
            name="ck_stage_status",
        ),
    )
    stage_execution_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline_runs.run_id"), nullable=False, index=True
    )
    attempt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reject_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    run: Mapped[PipelineRun] = relationship(back_populates="stages", overlaps="attempt,stages")
    attempt: Mapped[RunAttempt] = relationship(
        back_populates="stages", foreign_keys=[attempt_id], overlaps="run,stages"
    )


class ValidationExecution(Base):
    """Append-only per-check result snapshot scoped to one pipeline attempt."""

    __tablename__ = "validation_executions"
    __table_args__ = (
        UniqueConstraint("attempt_id", "validation_id", name="uq_validation_attempt_check"),
        ForeignKeyConstraint(
            ["run_id", "attempt_id"],
            ["run_attempts.run_id", "run_attempts.attempt_id"],
            name="fk_validation_run_attempt",
        ),
        CheckConstraint(
            "status IN ('PASS','FAIL','WARNING','ERROR','SKIPPED','NOT_APPLICABLE','REQUIRES_CONFIGURATION','BLOCKED')",
            name="ck_validation_execution_status",
        ),
        CheckConstraint(
            "applicability IN ('APPLICABLE','NOT_APPLICABLE','REQUIRES_CONFIGURATION','REQUIRES_BASELINE','REQUIRES_REFERENCE_DATA','UNSUPPORTED_INTEGRATION','DISABLED')",
            name="ck_validation_execution_applicability",
        ),
        CheckConstraint("checked_rows >= 0 AND passed_rows >= 0 AND failed_rows >= 0", name="ck_validation_row_counts_nonnegative"),
    )
    validation_execution_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    validation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    applicability: Mapped[str] = mapped_column(String(32), nullable=False)
    applicability_reason: Mapped[str] = mapped_column(Text, nullable=False)
    execution_stage: Mapped[str] = mapped_column(String(80), nullable=False)
    checked_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_percentage: Mapped[float] = mapped_column(nullable=False, default=0)
    affected_columns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    failure_examples: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    configuration_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, index=True)


class ValidationDefinition(Base):
    """Imported catalog definition. Definitions only exist after source material is supplied."""

    __tablename__ = "validation_definitions"
    __table_args__ = (
        UniqueConstraint("catalog_number", name="uq_validation_catalog_number"),
        CheckConstraint("catalog_number BETWEEN 1 AND 200", name="ck_validation_catalog_number_range"),
        CheckConstraint(
            "implementation_status IN ('FULLY_IMPLEMENTED','PARTIALLY_IMPLEMENTED','CATALOG_ONLY','REQUIRES_INTEGRATION','NOT_IMPLEMENTED','DEPRECATED')",
            name="ck_validation_implementation_status",
        ),
    )
    validation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    catalog_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    applicability_requirements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required_columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required_metadata: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    configuration_requirements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    implementation_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    implementation_version: Mapped[str] = mapped_column(String(40), nullable=False)
    test_status: Mapped[str] = mapped_column(String(32), nullable=False)
    limitations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    supported_file_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    applicability_support: Mapped[str] = mapped_column(String(32), nullable=False)
    definition_source: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class RejectedRecord(Base):
    __tablename__ = "rejected_records"
    __table_args__ = (
        UniqueConstraint("attempt_id", "source_row_number", name="uq_rejected_attempt_row"),
        ForeignKeyConstraint(
            ["run_id", "source_file_id"],
            ["pipeline_runs.run_id", "pipeline_runs.source_file_id"],
            name="fk_rejected_run_source",
        ),
        ForeignKeyConstraint(
            ["run_id", "attempt_id"],
            ["run_attempts.run_id", "run_attempts.attempt_id"],
            name="fk_rejected_run_attempt",
        ),
    )
    rejected_record_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_file_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    rejection_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    run: Mapped[PipelineRun] = relationship(back_populates="rejected_records")


class DuplicateRecord(Base):
    __tablename__ = "duplicate_records"
    __table_args__ = (
        UniqueConstraint("attempt_id", "source_row_number", name="uq_duplicate_attempt_row"),
        ForeignKeyConstraint(
            ["run_id", "attempt_id"],
            ["run_attempts.run_id", "run_attempts.attempt_id"],
            name="fk_duplicate_run_attempt",
        ),
    )
    duplicate_record_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline_runs.run_id"), nullable=False, index=True
    )
    attempt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_of_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_key: Mapped[str] = mapped_column(String(255), nullable=False)
    run: Mapped[PipelineRun] = relationship(back_populates="duplicate_records")


class PublishedArtifact(Base):
    __tablename__ = "published_artifacts"
    __table_args__ = (UniqueConstraint("run_id", "artifact_type", name="uq_artifact_run_type"),)
    artifact_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline_runs.run_id"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    run: Mapped[PipelineRun] = relationship(back_populates="artifacts")


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.run_id"), primary_key=True)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    accepted_amounts_by_currency: Mapped[dict] = mapped_column(JSON, nullable=False)
    published_amounts_by_currency: Mapped[dict] = mapped_column(JSON, nullable=False)
    balanced: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checks: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    run: Mapped[PipelineRun] = relationship(back_populates="reconciliation")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    audit_event_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("pipeline_runs.run_id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class QualityBaseline(Base):
    """Immutable aggregate snapshot used to compare later runs for one dataset identity."""

    __tablename__ = "quality_baselines"
    __table_args__ = (
        UniqueConstraint("dataset_identity", "pipeline_id", "baseline_version", name="uq_quality_baseline_version"),
        ForeignKeyConstraint(
            ["run_id", "attempt_id"],
            ["run_attempts.run_id", "run_attempts.attempt_id"],
            name="fk_quality_baseline_run_attempt",
        ),
        CheckConstraint("baseline_version >= 1", name="ck_quality_baseline_version_positive"),
        CheckConstraint("sample_size >= 0", name="ck_quality_baseline_sample_nonnegative"),
    )
    baseline_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    dataset_identity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pipeline_id: Mapped[str] = mapped_column(ForeignKey("pipelines.pipeline_id"), nullable=False, index=True)
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_files.source_file_id"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baseline_version: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_period_start: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    reference_period_end: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    statistical_configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    profile_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    distribution_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    validation_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, index=True)


class AIBudget(Base):
    __tablename__ = "ai_budgets"

    budget_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    limit_usd: Mapped[Decimal] = mapped_column(Numeric(14, 9), nullable=False)
    used_usd: Mapped[Decimal] = mapped_column(Numeric(14, 9), nullable=False, default=0)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(14, 9), nullable=False, default=0)
    reset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class AIUsage(Base):
    __tablename__ = "ai_usage"

    usage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 9), nullable=False, default=0)
    reported_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 9), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, index=True)


class AICache(Base):
    __tablename__ = "ai_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 9), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class SchemaProfile(Base):
    __tablename__ = "schema_profiles"
    __table_args__ = (
        UniqueConstraint("schema_fingerprint", "version", name="uq_schema_profile_fingerprint_version"),
        CheckConstraint("version >= 1", name="ck_schema_profile_version_positive"),
    )

    profile_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_files.source_file_id"), nullable=False, index=True)
    schema_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    profile_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    mappings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_id", "version", name="uq_rule_version"),
        CheckConstraint("version >= 1", name="ck_rule_version_positive"),
        CheckConstraint("status IN ('draft','approved','rejected','disabled')", name="ck_rule_version_status"),
    )

    rule_version_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    schema_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class TransformationVersion(Base):
    __tablename__ = "transformation_versions"
    __table_args__ = (
        UniqueConstraint("transform_id", "version", name="uq_transformation_version"),
        CheckConstraint("version >= 1", name="ck_transformation_version_positive"),
        CheckConstraint("status IN ('draft','approved','rejected','disabled')", name="ck_transformation_version_status"),
    )

    transform_version_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    transform_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    schema_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class ProcessingPlan(Base):
    __tablename__ = "processing_plans"
    __table_args__ = (
        UniqueConstraint("source_file_id", "version", name="uq_processing_plan_source_version"),
        CheckConstraint("version >= 1", name="ck_processing_plan_version_positive"),
    )

    plan_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_files.source_file_id"), nullable=False, index=True)
    schema_profile_id: Mapped[str | None] = mapped_column(ForeignKey("schema_profiles.profile_id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
