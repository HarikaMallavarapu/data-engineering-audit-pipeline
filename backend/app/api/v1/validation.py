from collections import Counter, defaultdict
import csv
from datetime import UTC, datetime, timedelta
import io
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.exceptions import ApiError
from app.models import (
    PipelineRun,
    RunAttempt,
    SourceFile,
    ValidationDefinition,
    ValidationExecution,
)
from app.schemas import (
    ValidationAnalyticsResponse,
    ValidationCatalogItemResponse,
    ValidationCatalogResponse,
    ValidationHistoryResponse,
    ValidationRunResultsResponse,
    ValidationRunSummary,
)
from app.services.quality_service import calculate_quality_score

router = APIRouter(prefix="/validation", tags=["validation"])
_IMPLEMENTATION_STATUSES = (
    "FULLY_IMPLEMENTED",
    "PARTIALLY_IMPLEMENTED",
    "CATALOG_ONLY",
    "REQUIRES_INTEGRATION",
    "NOT_IMPLEMENTED",
    "DEPRECATED",
)
_EXECUTED_STATUSES = {"PASS", "FAIL", "WARNING", "ERROR"}


@router.get("/catalog", response_model=ValidationCatalogResponse)
def list_catalog(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    validation_id: str | None = Query(default=None, max_length=32),
    name: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=120),
    severity: str | None = Query(default=None, max_length=16),
    implementation_status: str | None = Query(default=None, max_length=32),
    applicability: str | None = Query(default=None, max_length=32),
    supported_file_type: str | None = Query(default=None, max_length=32),
    enabled: bool | None = None,
    session: Session = Depends(get_session),
):
    reference_root = Path(__file__).resolve().parents[4] / "docs" / "reference"
    source_paths = (
        reference_root / "validation_catalog_001_100.md",
        reference_root / "validation_catalog_101_200.md",
    )
    # The catalog is bounded to 200 definitions, so filtering its decoded rows keeps
    # JSON-array membership consistent across SQLite and server database dialects.
    definitions = session.scalars(
        select(ValidationDefinition).order_by(ValidationDefinition.catalog_number)
    ).all()
    counts = {status: 0 for status in _IMPLEMENTATION_STATUSES}
    counts.update({"enabled": 0, "disabled": 0})
    filter_options = {
        "categories": sorted({item.category for item in definitions}, key=str.casefold),
        "severities": sorted({item.severity for item in definitions}, key=str.casefold),
        "applicabilities": sorted({item.applicability_support for item in definitions}, key=str.casefold),
        "supported_file_types": sorted(
            {file_type.casefold().lstrip(".") for item in definitions for file_type in item.supported_file_types},
            key=str.casefold,
        ),
    }
    for definition in definitions:
        counts[definition.implementation_status] = counts.get(definition.implementation_status, 0) + 1
        counts["enabled" if definition.enabled else "disabled"] += 1

    filtered = definitions
    if search:
        term = search.strip().casefold()
        filtered = [
            item for item in filtered
            if term in item.validation_id.casefold()
            or term in item.name.casefold()
            or term in item.description.casefold()
            or term in item.category.casefold()
        ]
    if validation_id:
        exact_id = validation_id.strip().casefold()
        filtered = [item for item in filtered if item.validation_id.casefold() == exact_id]
    if name:
        name_term = name.strip().casefold()
        filtered = [item for item in filtered if name_term in item.name.casefold()]
    if category:
        normalized_category = category.strip().casefold()
        filtered = [item for item in filtered if item.category.casefold() == normalized_category]
    if severity:
        normalized_severity = severity.strip().upper()
        filtered = [item for item in filtered if item.severity.upper() == normalized_severity]
    if implementation_status:
        normalized_status = implementation_status.upper()
        if normalized_status not in _IMPLEMENTATION_STATUSES:
            raise ApiError(422, "invalid_implementation_status", "The implementation status is not supported.")
        filtered = [item for item in filtered if item.implementation_status == normalized_status]
    if applicability:
        normalized_applicability = applicability.strip().upper()
        filtered = [item for item in filtered if item.applicability_support.upper() == normalized_applicability]
    if supported_file_type:
        normalized_file_type = supported_file_type.strip().casefold().lstrip(".")
        filtered = [
            item for item in filtered
            if any(file_type.casefold().lstrip(".") == normalized_file_type for file_type in item.supported_file_types)
        ]
    if enabled is not None:
        filtered = [item for item in filtered if item.enabled is enabled]

    total = len(filtered)
    catalog_total = len(definitions)
    offset = (page - 1) * page_size
    page_definitions = filtered[offset:offset + page_size]
    page_ids = [item.validation_id for item in page_definitions]
    last_executions = {}
    if page_ids:
        last_executions = dict(
            session.execute(
                select(ValidationExecution.validation_id, func.max(ValidationExecution.created_at))
                .where(ValidationExecution.validation_id.in_(page_ids))
                .group_by(ValidationExecution.validation_id)
            ).all()
        )

    if catalog_total == 200:
        source_status = "READY"
    elif catalog_total:
        source_status = "PARTIAL"
    elif not all(path.is_file() for path in source_paths):
        source_status = "SOURCE_MISSING"
    else:
        source_status = "NOT_IMPORTED"
    message = {
        "READY": None,
        "PARTIAL": f"{catalog_total} of 200 catalog entries are imported; the catalog is incomplete.",
        "SOURCE_MISSING": "The source catalogs for checks 001–100 and 101–200 are missing. No catalog names or descriptions have been invented.",
        "NOT_IMPORTED": "The source catalog files exist, but their definitions have not been imported.",
    }[source_status]
    return {
        "source_status": source_status,
        "message": message,
        "counts": counts,
        "filter_options": filter_options,
        "items": [
            {
                **{column.name: getattr(definition, column.name) for column in definition.__table__.columns},
                "last_executed_at": last_executions.get(definition.validation_id),
            }
            for definition in page_definitions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/catalog/{validation_id}", response_model=ValidationCatalogItemResponse)
def get_catalog_item(validation_id: str, session: Session = Depends(get_session)):
    definition = session.get(ValidationDefinition, validation_id)
    if definition is None:
        raise ApiError(404, "validation_definition_not_found", "The validation definition was not found in the imported catalog.")
    last_executed = session.scalar(
        select(func.max(ValidationExecution.created_at)).where(
            ValidationExecution.validation_id == validation_id
        )
    )
    return {**{column.name: getattr(definition, column.name) for column in definition.__table__.columns}, "last_executed_at": last_executed}


@router.get("/catalog/export/download")
def export_catalog(
    export_format: Literal["json", "csv"] = Query(default="json", alias="format"),
    session: Session = Depends(get_session),
):
    """Export only the imported source definitions; never synthesize catalog rows."""
    definitions = session.scalars(
        select(ValidationDefinition).order_by(ValidationDefinition.catalog_number)
    ).all()
    reference_root = Path(__file__).resolve().parents[4] / "docs" / "reference"
    source_paths = (
        reference_root / "validation_catalog_001_100.md",
        reference_root / "validation_catalog_101_200.md",
    )
    source_status = (
        "READY" if len(definitions) == 200
        else "PARTIAL" if definitions
        else "SOURCE_MISSING" if not all(path.is_file() for path in source_paths)
        else "NOT_IMPORTED"
    )
    message = {
        "READY": None,
        "PARTIAL": f"{len(definitions)} of 200 catalog entries are imported; the catalog is incomplete.",
        "SOURCE_MISSING": "The source catalogs are missing. No catalog names or descriptions have been invented.",
        "NOT_IMPORTED": "The source catalog files exist, but their definitions have not been imported.",
    }[source_status]
    last_executions = dict(session.execute(
        select(ValidationExecution.validation_id, func.max(ValidationExecution.created_at))
        .group_by(ValidationExecution.validation_id)
    ).all())
    fields = [column.name for column in ValidationDefinition.__table__.columns]
    items = [
        {
            **{field: getattr(definition, field) for field in fields},
            "last_executed_at": last_executions.get(definition.validation_id),
        }
        for definition in definitions
    ]
    if export_format == "json":
        payload = jsonable_encoder({
            "source_status": source_status,
            "message": message,
            "total": len(items),
            "exported_at": datetime.now(UTC),
            "items": items,
        })
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="datatrace-validation-catalog.json"',
                "X-DataTrace-Catalog-Status": source_status,
            },
        )

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    columns = fields + ["last_executed_at"]
    writer.writerow(columns)
    for item in items:
        writer.writerow([
            json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (dict, list))
            else value.isoformat() if isinstance(value, datetime)
            else "" if value is None
            else value
            for value in (item[column] for column in columns)
        ])
    return Response(
        content=stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="datatrace-validation-catalog.csv"',
            "X-DataTrace-Catalog-Status": source_status,
        },
    )


@router.get("/runs/{run_id}", response_model=ValidationRunResultsResponse)
def list_run_results(
    run_id: str,
    attempt_id: str | None = Query(default=None, min_length=1, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: str | None = Query(default=None, max_length=32),
    severity: str | None = Query(default=None, max_length=16),
    category: str | None = Query(default=None, max_length=100),
    validation_id: str | None = Query(default=None, max_length=120),
    execution_stage: str | None = Query(default=None, max_length=80),
    session: Session = Depends(get_session),
):
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise ApiError(404, "run_not_found", "The requested pipeline run was not found.")
    if attempt_id is None:
        latest_attempt = session.scalar(
            select(RunAttempt)
            .where(RunAttempt.run_id == run_id)
            .order_by(RunAttempt.attempt_number.desc())
            .limit(1)
        )
        attempt_id = latest_attempt.attempt_id if latest_attempt else None
    elif session.scalar(
        select(RunAttempt.attempt_id).where(
            RunAttempt.run_id == run_id, RunAttempt.attempt_id == attempt_id
        )
    ) is None:
        raise ApiError(404, "run_attempt_not_found", "The requested run attempt was not found.")

    all_rows = []
    if attempt_id:
        all_rows = session.scalars(
            select(ValidationExecution)
            .where(ValidationExecution.run_id == run_id, ValidationExecution.attempt_id == attempt_id)
            .order_by(ValidationExecution.validation_execution_id)
        ).all()
    status_counts = Counter(row.status for row in all_rows)
    summary = None if attempt_id is None else ValidationRunSummary(
        attempt_id=attempt_id,
        total_records=len(all_rows),
        executed=sum(status_counts.get(value, 0) for value in _EXECUTED_STATUSES),
        passed=status_counts.get("PASS", 0),
        failed=status_counts.get("FAIL", 0),
        warnings=status_counts.get("WARNING", 0),
        errors=status_counts.get("ERROR", 0),
        skipped=status_counts.get("SKIPPED", 0),
        not_applicable=status_counts.get("NOT_APPLICABLE", 0),
        requires_configuration=status_counts.get("REQUIRES_CONFIGURATION", 0),
        blocked=status_counts.get("BLOCKED", 0),
        applicable=sum(row.applicability == "APPLICABLE" for row in all_rows),
        checked_rows=sum(row.checked_rows for row in all_rows),
        failed_rows=sum(row.failed_rows for row in all_rows),
        execution_duration_ms=sum(row.execution_time_ms for row in all_rows),
    )

    query = select(ValidationExecution).where(ValidationExecution.run_id == run_id)
    if attempt_id:
        query = query.where(ValidationExecution.attempt_id == attempt_id)
    if status:
        query = query.where(ValidationExecution.status == status.upper())
    if severity:
        query = query.where(ValidationExecution.severity == severity.upper())
    if category:
        query = query.where(ValidationExecution.category == category)
    if validation_id:
        query = query.where(ValidationExecution.validation_id == validation_id)
    if execution_stage:
        query = query.where(ValidationExecution.execution_stage == execution_stage.upper())
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(ValidationExecution.validation_execution_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "run_id": run_id,
        "attempt_id": attempt_id,
        "summary": summary,
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{run_id}/export")
def export_run_results(
    run_id: str,
    attempt_id: str | None = Query(default=None, min_length=1, max_length=100),
    status: str | None = Query(default=None, max_length=32),
    severity: str | None = Query(default=None, max_length=16),
    category: str | None = Query(default=None, max_length=100),
    validation_id: str | None = Query(default=None, max_length=120),
    execution_stage: str | None = Query(default=None, max_length=80),
    export_format: Literal["json", "csv"] = Query(default="json", alias="format"),
    session: Session = Depends(get_session),
):
    """Export actual, persisted results for one run attempt, with optional filters."""
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise ApiError(404, "run_not_found", "The requested pipeline run was not found.")
    if attempt_id is None:
        attempt = session.scalar(
            select(RunAttempt)
            .where(RunAttempt.run_id == run_id)
            .order_by(RunAttempt.attempt_number.desc())
            .limit(1)
        )
        attempt_id = attempt.attempt_id if attempt else None
    elif session.scalar(
        select(RunAttempt.attempt_id).where(
            RunAttempt.run_id == run_id,
            RunAttempt.attempt_id == attempt_id,
        )
    ) is None:
        raise ApiError(404, "run_attempt_not_found", "The requested run attempt was not found.")

    all_query = select(ValidationExecution).where(ValidationExecution.run_id == run_id)
    if attempt_id:
        all_query = all_query.where(ValidationExecution.attempt_id == attempt_id)
    all_rows = session.scalars(all_query.order_by(ValidationExecution.validation_execution_id)).all()
    status_counts = Counter(row.status for row in all_rows)
    summary = None if attempt_id is None else ValidationRunSummary(
        attempt_id=attempt_id,
        total_records=len(all_rows),
        executed=sum(status_counts.get(value, 0) for value in _EXECUTED_STATUSES),
        passed=status_counts.get("PASS", 0),
        failed=status_counts.get("FAIL", 0),
        warnings=status_counts.get("WARNING", 0),
        errors=status_counts.get("ERROR", 0),
        skipped=status_counts.get("SKIPPED", 0),
        not_applicable=status_counts.get("NOT_APPLICABLE", 0),
        requires_configuration=status_counts.get("REQUIRES_CONFIGURATION", 0),
        blocked=status_counts.get("BLOCKED", 0),
        applicable=sum(row.applicability == "APPLICABLE" for row in all_rows),
        checked_rows=sum(row.checked_rows for row in all_rows),
        failed_rows=sum(row.failed_rows for row in all_rows),
        execution_duration_ms=sum(row.execution_time_ms for row in all_rows),
    )
    query = select(ValidationExecution).where(ValidationExecution.run_id == run_id)
    if attempt_id:
        query = query.where(ValidationExecution.attempt_id == attempt_id)
    if status:
        query = query.where(ValidationExecution.status == status.upper())
    if severity:
        query = query.where(ValidationExecution.severity == severity.upper())
    if category:
        query = query.where(ValidationExecution.category == category)
    if validation_id:
        query = query.where(ValidationExecution.validation_id == validation_id)
    if execution_stage:
        query = query.where(ValidationExecution.execution_stage == execution_stage.upper())
    rows = session.scalars(query.order_by(ValidationExecution.validation_execution_id)).all()
    if export_format == "json":
        payload = jsonable_encoder({
            "run_id": run_id,
            "attempt_id": attempt_id,
            "summary": summary,
            "total": len(rows),
            "items": rows,
        })
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="datatrace-validation-results.json"'},
        )

    fields = [column.name for column in ValidationExecution.__table__.columns]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(fields)
    for row in rows:
        writer.writerow([
            json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (dict, list))
            else value.isoformat() if isinstance(value, datetime)
            else "" if value is None
            else value
            for value in (getattr(row, field) for field in fields)
        ])
    return Response(
        content=stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="datatrace-validation-results.csv"'},
    )


@router.get("/history", response_model=ValidationHistoryResponse)
def list_validation_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    validation_id: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=32),
    pipeline_id: str | None = Query(default=None, max_length=80),
    source_file_id: str | None = Query(default=None, max_length=80),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    session: Session = Depends(get_session),
):
    if created_from and created_to and created_from > created_to:
        raise ApiError(422, "invalid_date_range", "The start of the date range must be before its end.")

    query = (
        select(ValidationExecution, PipelineRun, SourceFile, RunAttempt)
        .join(PipelineRun, PipelineRun.run_id == ValidationExecution.run_id)
        .join(SourceFile, SourceFile.source_file_id == PipelineRun.source_file_id)
        .join(
            RunAttempt,
            (RunAttempt.run_id == ValidationExecution.run_id)
            & (RunAttempt.attempt_id == ValidationExecution.attempt_id),
        )
    )
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ValidationExecution.validation_id.ilike(term),
                ValidationExecution.name.ilike(term),
                SourceFile.original_filename.ilike(term),
            )
        )
    if validation_id:
        query = query.where(ValidationExecution.validation_id == validation_id)
    if category:
        query = query.where(ValidationExecution.category == category)
    if status:
        query = query.where(ValidationExecution.status == status.upper())
    if pipeline_id:
        query = query.where(PipelineRun.pipeline_id == pipeline_id)
    if source_file_id:
        query = query.where(PipelineRun.source_file_id == source_file_id)
    if created_from:
        query = query.where(ValidationExecution.created_at >= created_from)
    if created_to:
        query = query.where(ValidationExecution.created_at <= created_to)

    total = session.scalar(
        select(func.count()).select_from(
            query.with_only_columns(ValidationExecution.validation_execution_id).subquery()
        )
    ) or 0
    rows = session.execute(
        query.order_by(ValidationExecution.created_at.desc(), ValidationExecution.validation_execution_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                **{column.name: getattr(execution, column.name) for column in execution.__table__.columns},
                "pipeline_id": run.pipeline_id,
                "source_file_id": source.source_file_id,
                "original_filename": source.original_filename,
                "attempt_number": attempt.attempt_number,
            }
            for execution, run, source, attempt in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/analytics", response_model=ValidationAnalyticsResponse)
def get_validation_analytics(
    days: int = Query(default=30, ge=1, le=365),
    pipeline_id: str | None = Query(default=None, max_length=80),
    session: Session = Depends(get_session),
):
    through_date = datetime.now(UTC)
    from_date = through_date - timedelta(days=days)
    query = (
        select(ValidationExecution)
        .join(PipelineRun, PipelineRun.run_id == ValidationExecution.run_id)
        .where(ValidationExecution.created_at >= from_date)
    )
    if pipeline_id:
        query = query.where(PipelineRun.pipeline_id == pipeline_id)

    total_results = session.scalar(
        select(func.count()).select_from(
            query.with_only_columns(ValidationExecution.validation_execution_id).subquery()
        )
    ) or 0
    status_counts = dict(
        session.execute(
            query.with_only_columns(ValidationExecution.status, func.count())
            .group_by(ValidationExecution.status)
        ).all()
    )
    critical_failures = session.scalar(
        select(func.count()).select_from(
            query.where(
                ValidationExecution.severity == "CRITICAL",
                ValidationExecution.status.in_({"FAIL", "ERROR", "BLOCKED"}),
            ).subquery()
        )
    ) or 0
    requires_configuration = status_counts.get("REQUIRES_CONFIGURATION", 0)
    executed_count = sum(status_counts.get(status, 0) for status in _EXECUTED_STATUSES)
    total_duration_ms = session.scalar(
        query.with_only_columns(func.sum(ValidationExecution.execution_time_ms))
        .where(ValidationExecution.status.in_(_EXECUTED_STATUSES))
    ) or 0

    failure_query = query.where(ValidationExecution.status.in_({"FAIL", "ERROR"}))
    failures_by_category = [
        {"category": category, "failures": count}
        for category, count in session.execute(
            failure_query.with_only_columns(ValidationExecution.category, func.count())
            .group_by(ValidationExecution.category)
            .order_by(func.count().desc(), ValidationExecution.category)
            .limit(10)
        )
    ]
    most_failing_checks = [
        {"validation_id": validation_id, "name": name, "category": category, "failures": count}
        for validation_id, name, category, count in session.execute(
            failure_query.with_only_columns(
                ValidationExecution.validation_id,
                ValidationExecution.name,
                ValidationExecution.category,
                func.count(),
            )
            .group_by(ValidationExecution.validation_id, ValidationExecution.name, ValidationExecution.category)
            .order_by(func.count().desc(), ValidationExecution.validation_id)
            .limit(10)
        )
    ]
    daily_trend = [
        {"date": day, "executions": total, "failures": failures, "warnings": warnings}
        for day, total, failures, warnings in session.execute(
            query.with_only_columns(
                func.date(ValidationExecution.created_at),
                func.count(),
                func.sum(case((ValidationExecution.status.in_({"FAIL", "ERROR"}), 1), else_=0)),
                func.sum(case((ValidationExecution.status == "WARNING", 1), else_=0)),
            )
            .group_by(func.date(ValidationExecution.created_at))
            .order_by(func.date(ValidationExecution.created_at))
        )
    ]

    attempt_dates = session.execute(
        query.with_only_columns(
            ValidationExecution.run_id,
            ValidationExecution.attempt_id,
            func.max(ValidationExecution.created_at).label("attempt_date"),
        )
        .group_by(ValidationExecution.run_id, ValidationExecution.attempt_id)
        .order_by(func.max(ValidationExecution.created_at).desc())
        .limit(30)
    ).all()
    attempt_rows: dict[tuple[str, str], list[ValidationExecution]] = defaultdict(list)
    if attempt_dates:
        attempt_filter = or_(
            *[
                and_(ValidationExecution.run_id == run_id, ValidationExecution.attempt_id == attempt_id)
                for run_id, attempt_id, _ in attempt_dates
            ]
        )
        for execution in session.scalars(select(ValidationExecution).where(attempt_filter)):
            attempt_rows[(execution.run_id, execution.attempt_id)].append(execution)

    catalog_definitions = session.scalars(select(ValidationDefinition)).all()
    catalog_total = len(catalog_definitions)
    eligible_catalog_ids = None
    if catalog_total == 200:
        eligible_catalog_ids = {
            item.validation_id
            for item in catalog_definitions
            if item.enabled
            and item.implementation_status in {"FULLY_IMPLEMENTED", "PARTIALLY_IMPLEMENTED"}
        }
    quality_trend = []
    quality_trend_insufficient_attempts = 0
    for run_id, attempt_id, attempt_date in reversed(attempt_dates):
        score = calculate_quality_score(
            attempt_rows[(run_id, attempt_id)],
            catalog_total=catalog_total,
            eligible_catalog_ids=eligible_catalog_ids,
        )
        if score["score"] is None:
            quality_trend_insufficient_attempts += 1
            continue
        quality_trend.append(
            {
                "run_id": run_id,
                "attempt_id": attempt_id,
                "created_at": attempt_date,
                "score": score["score"],
                "coverage_percent": score["coverage_percent"],
            }
        )

    return {
        "days": days,
        "from_date": from_date,
        "through_date": through_date,
        "pipeline_id": pipeline_id,
        "total_results": total_results,
        "status_counts": status_counts,
        "critical_failures": critical_failures,
        "requires_configuration": requires_configuration,
        "average_execution_time_ms": round(total_duration_ms / executed_count, 2) if executed_count else None,
        "failures_by_category": failures_by_category,
        "most_failing_checks": most_failing_checks,
        "daily_trend": daily_trend,
        "quality_trend": quality_trend,
        "quality_trend_insufficient_attempts": quality_trend_insufficient_attempts,
        "scope": "Persisted per-check results from the selected date window; only the latest 30 attempts contribute to score trend.",
    }
