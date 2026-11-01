from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.exceptions import ApiError
from app.models import (
    AuditEvent,
    PipelineRun,
    QualityBaseline,
    RunAttempt,
    SourceFile,
    ValidationDefinition,
    ValidationExecution,
)
from app.schemas import (
    QualityBaselineComparisonResponse,
    QualityBaselineCreateRequest,
    QualityBaselineListResponse,
    QualityBaselineResponse,
    QualityRunComparisonResponse,
    QualityScoreResponse,
)
from app.services.baseline_service import (
    compare_observations,
    source_observation,
    statistical_configuration,
)
from app.services.quality_service import calculate_quality_score

router = APIRouter(prefix="/quality", tags=["quality"])


@router.post("/baselines", response_model=QualityBaselineResponse, status_code=201)
def create_quality_baseline(
    payload: QualityBaselineCreateRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    run, attempt = _resolve_terminal_attempt(session, payload.run_id, payload.attempt_id)
    source = session.get(SourceFile, run.source_file_id)
    if source is None:
        raise ApiError(409, "baseline_source_unavailable", "The run's source file is no longer available.")

    dataset_identity = payload.dataset_identity or (
        f"{run.pipeline_id}:{Path(source.original_filename).stem.casefold()}"
    )
    dataset_identity = dataset_identity[:255]
    try:
        profile, distributions, timestamps, observation_limitations = source_observation(
            source, sample_limit=request.app.state.settings.profile_sample_size
        )
    except (OSError, ValueError) as exc:
        raise ApiError(422, "baseline_source_unreadable", str(exc)) from exc

    previous_version = session.scalar(
        select(func.max(QualityBaseline.baseline_version)).where(
            QualityBaseline.dataset_identity == dataset_identity,
            QualityBaseline.pipeline_id == run.pipeline_id,
        )
    ) or 0
    started_at = attempt.started_at or run.started_at or run.created_at
    completed_at = attempt.completed_at or run.completed_at or started_at
    if completed_at < started_at:
        started_at = completed_at
    sample_size = int(profile.get("profile_sample_size", 0) or 0)
    if not sample_size:
        sample_size = min(int(profile.get("row_count", 0) or 0), request.app.state.settings.profile_sample_size)
    configuration = statistical_configuration()
    configuration["observation_limitations"] = observation_limitations
    baseline = QualityBaseline(
        baseline_id=f"baseline_{uuid4().hex}",
        dataset_identity=dataset_identity,
        pipeline_id=run.pipeline_id,
        source_file_id=source.source_file_id,
        run_id=run.run_id,
        attempt_id=attempt.attempt_id,
        schema_version=source.schema_fingerprint,
        baseline_version=previous_version + 1,
        sample_size=sample_size,
        reference_period_start=started_at,
        reference_period_end=completed_at,
        statistical_configuration=configuration,
        profile_snapshot=profile,
        distribution_snapshot={"numeric": distributions, "timestamps": timestamps},
        validation_snapshot=_validation_snapshot(
            session, run.run_id, attempt.attempt_id
        ),
    )
    session.add(baseline)
    session.add(
        AuditEvent(
            run_id=run.run_id,
            event_type="quality.baseline.created",
            event_data={
                "baseline_id": baseline.baseline_id,
                "dataset_identity": dataset_identity,
                "baseline_version": baseline.baseline_version,
                "sample_size": sample_size,
            },
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(
            409,
            "baseline_version_conflict",
            "Another baseline was created at the same time. Retry to create the next version.",
        ) from exc
    session.refresh(baseline)
    return baseline


@router.get("/baselines", response_model=QualityBaselineListResponse)
def list_quality_baselines(
    dataset_identity: str | None = Query(default=None, max_length=255),
    pipeline_id: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    filters = []
    if dataset_identity:
        filters.append(QualityBaseline.dataset_identity == dataset_identity)
    if pipeline_id:
        filters.append(QualityBaseline.pipeline_id == pipeline_id)
    total = session.scalar(
        select(func.count()).select_from(QualityBaseline).where(*filters)
    ) or 0
    items = session.scalars(
        select(QualityBaseline)
        .where(*filters)
        .order_by(QualityBaseline.created_at.desc(), QualityBaseline.baseline_version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get(
    "/baselines/{baseline_id}/compare",
    response_model=QualityBaselineComparisonResponse,
)
def compare_quality_baseline(
    baseline_id: str,
    request: Request,
    run_id: str = Query(min_length=1, max_length=80),
    attempt_id: str | None = Query(default=None, min_length=1, max_length=100),
    session: Session = Depends(get_session),
):
    baseline = session.get(QualityBaseline, baseline_id)
    if baseline is None:
        raise ApiError(404, "baseline_not_found", "The requested quality baseline was not found.")
    run, attempt = _resolve_terminal_attempt(session, run_id, attempt_id)
    if run.pipeline_id != baseline.pipeline_id:
        raise ApiError(409, "baseline_pipeline_mismatch", "A baseline can only be compared with a run from the same pipeline.")
    source = session.get(SourceFile, run.source_file_id)
    if source is None:
        raise ApiError(409, "comparison_source_unavailable", "The selected run's source file is no longer available.")

    baseline_distributions = baseline.distribution_snapshot or {}
    reference_edges = {
        column: distribution.get("edges", [])
        for column, distribution in baseline_distributions.get("numeric", {}).items()
    }
    try:
        profile, distributions, timestamps, target_limitations = source_observation(
            source,
            sample_limit=request.app.state.settings.profile_sample_size,
            numeric_reference_edges=reference_edges,
        )
    except (OSError, ValueError) as exc:
        raise ApiError(422, "comparison_source_unreadable", str(exc)) from exc
    validations = session.scalars(
        select(ValidationExecution)
        .where(
            ValidationExecution.run_id == run.run_id,
            ValidationExecution.attempt_id == attempt.attempt_id,
        )
        .order_by(ValidationExecution.validation_execution_id)
    ).all()
    configuration = baseline.statistical_configuration or statistical_configuration()
    return {
        "baseline_id": baseline.baseline_id,
        "baseline_version": baseline.baseline_version,
        "dataset_identity": baseline.dataset_identity,
        "target_run_id": run.run_id,
        "target_attempt_id": attempt.attempt_id,
        "target_source_file_id": source.source_file_id,
        **compare_observations(
            baseline.profile_snapshot or {},
            baseline_distributions.get("numeric", {}),
            baseline_distributions.get("timestamps", {}),
            profile,
            distributions,
            timestamps,
            baseline.validation_snapshot or [],
            validations,
            configuration=configuration,
            additional_limitations=(
                configuration.get("observation_limitations", []) + target_limitations
            ),
        ),
    }


@router.get("/runs/compare", response_model=QualityRunComparisonResponse)
def compare_quality_runs(
    request: Request,
    reference_run_id: str = Query(min_length=1, max_length=80),
    comparison_run_id: str = Query(min_length=1, max_length=80),
    reference_attempt_id: str | None = Query(default=None, min_length=1, max_length=100),
    comparison_attempt_id: str | None = Query(default=None, min_length=1, max_length=100),
    session: Session = Depends(get_session),
):
    """Compare two completed attempts without creating a persistent baseline."""
    reference_run, reference_attempt = _resolve_terminal_attempt(
        session, reference_run_id, reference_attempt_id
    )
    comparison_run, comparison_attempt = _resolve_terminal_attempt(
        session, comparison_run_id, comparison_attempt_id
    )
    if reference_run.pipeline_id != comparison_run.pipeline_id:
        raise ApiError(
            409,
            "comparison_pipeline_mismatch",
            "Run-to-run quality comparisons require runs from the same pipeline.",
        )
    reference_source = session.get(SourceFile, reference_run.source_file_id)
    comparison_source = session.get(SourceFile, comparison_run.source_file_id)
    if reference_source is None or comparison_source is None:
        raise ApiError(
            409,
            "comparison_source_unavailable",
            "Both selected runs must have registered source files available.",
        )

    sample_limit = request.app.state.settings.profile_sample_size
    try:
        reference_profile, reference_distributions, reference_timestamps, reference_limitations = (
            source_observation(reference_source, sample_limit=sample_limit)
        )
        reference_edges = {
            column: distribution.get("edges", [])
            for column, distribution in reference_distributions.items()
        }
        comparison_profile, comparison_distributions, comparison_timestamps, comparison_limitations = (
            source_observation(
                comparison_source,
                sample_limit=sample_limit,
                numeric_reference_edges=reference_edges,
            )
        )
    except (OSError, ValueError) as exc:
        raise ApiError(422, "comparison_source_unreadable", str(exc)) from exc

    reference_results = session.scalars(
        select(ValidationExecution)
        .where(
            ValidationExecution.run_id == reference_run.run_id,
            ValidationExecution.attempt_id == reference_attempt.attempt_id,
        )
        .order_by(ValidationExecution.validation_execution_id)
    ).all()
    comparison_results = session.scalars(
        select(ValidationExecution)
        .where(
            ValidationExecution.run_id == comparison_run.run_id,
            ValidationExecution.attempt_id == comparison_attempt.attempt_id,
        )
        .order_by(ValidationExecution.validation_execution_id)
    ).all()
    reference_validation = [
        {
            "validation_id": row.validation_id,
            "status": row.status,
            "severity": row.severity,
            "applicability": row.applicability,
            "checked_rows": row.checked_rows,
            "failed_rows": row.failed_rows,
            "rule_version": row.rule_version,
        }
        for row in reference_results
    ]
    configuration = statistical_configuration()
    return {
        "reference_run_id": reference_run.run_id,
        "reference_attempt_id": reference_attempt.attempt_id,
        "reference_pipeline_id": reference_run.pipeline_id,
        "reference_source_file_id": reference_source.source_file_id,
        "reference_filename": reference_source.original_filename,
        "comparison_run_id": comparison_run.run_id,
        "comparison_attempt_id": comparison_attempt.attempt_id,
        "comparison_source_file_id": comparison_source.source_file_id,
        "comparison_filename": comparison_source.original_filename,
        **compare_observations(
            reference_profile,
            reference_distributions,
            reference_timestamps,
            comparison_profile,
            comparison_distributions,
            comparison_timestamps,
            reference_validation,
            comparison_results,
            configuration=configuration,
            additional_limitations=reference_limitations + comparison_limitations,
        ),
    }
@router.get("/runs/{run_id}/score", response_model=QualityScoreResponse)
def get_run_quality_score(
    run_id: str,
    attempt_id: str | None = Query(default=None, min_length=1, max_length=100),
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

    rows = []
    if attempt_id:
        rows = session.scalars(
            select(ValidationExecution)
            .where(ValidationExecution.run_id == run_id, ValidationExecution.attempt_id == attempt_id)
            .order_by(ValidationExecution.validation_execution_id)
        ).all()
    catalog_definitions = session.scalars(select(ValidationDefinition)).all()
    catalog_total = len(catalog_definitions)
    eligible_catalog_ids = None
    if catalog_total == 200:
        eligible_catalog_ids = {
            definition.validation_id
            for definition in catalog_definitions
            if definition.enabled
            and definition.implementation_status in {"FULLY_IMPLEMENTED", "PARTIALLY_IMPLEMENTED"}
        }

    return {
        "run_id": run_id,
        "attempt_id": attempt_id,
        **calculate_quality_score(
            rows,
            catalog_total=catalog_total,
            eligible_catalog_ids=eligible_catalog_ids,
        ),
    }


def _resolve_terminal_attempt(
    session: Session, run_id: str, attempt_id: str | None
) -> tuple[PipelineRun, RunAttempt]:
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
    else:
        attempt = session.scalar(
            select(RunAttempt).where(
                RunAttempt.run_id == run_id,
                RunAttempt.attempt_id == attempt_id,
            )
        )
    if attempt is None:
        raise ApiError(404, "run_attempt_not_found", "The requested run attempt was not found.")
    if attempt.status not in {"SUCCESS", "PARTIAL", "FAILED", "CANCELLED"}:
        raise ApiError(409, "run_attempt_incomplete", "Quality baselines require a completed run attempt.")
    return run, attempt


def _validation_snapshot(
    session: Session, run_id: str, attempt_id: str
) -> list[dict]:
    rows = session.scalars(
        select(ValidationExecution)
        .where(
            ValidationExecution.run_id == run_id,
            ValidationExecution.attempt_id == attempt_id,
        )
        .order_by(ValidationExecution.validation_execution_id)
    ).all()
    return [
        {
            "validation_id": row.validation_id,
            "status": row.status,
            "severity": row.severity,
            "applicability": row.applicability,
            "checked_rows": row.checked_rows,
            "failed_rows": row.failed_rows,
            "rule_version": row.rule_version,
        }
        for row in rows
    ]
