from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.engine.pipeline import (
    OUTPUT_COLUMNS,
    parse_source_bytes,
    profile_records,
    read_master_ids,
    sha256_file,
    transform_records,
    transform_tabular_records,
    validate_and_classify,
    validate_tabular_records,
    write_csv,
)
from app.engine.quality.rules import evaluate_rules
from app.engine.reconciliation import reconcile_counts
from app.engine.transformation.registry import apply_transformations
from app.engine.validation.contracts import ValidationResult
from app.models import (
    AuditEvent,
    DuplicateRecord,
    Pipeline,
    PipelineRun,
    PipelineVersion,
    ProcessingPlan,
    PublishedArtifact,
    ReconciliationResult,
    RejectedRecord,
    RunAttempt,
    SourceFile,
    StageExecution,
    ValidationExecution,
    utc_now,
)
from app.services.engine_service import (
    approved_mapping_transformations,
    latest_approved_rules,
    latest_approved_transformations,
    latest_schema_profile,
)

logger = logging.getLogger(__name__)


def execute_pipeline(
    session: Session,
    settings: Settings,
    source_file_id: str,
    pipeline_id: str,
    *,
    retry: bool = False,
) -> PipelineRun:
    source = session.get(SourceFile, source_file_id)
    if source is None:
        from app.core.exceptions import ApiError

        raise ApiError(404, "source_not_found", "The requested source file was not found.")
    pipeline = session.get(Pipeline, pipeline_id)
    if pipeline is None:
        from app.core.exceptions import ApiError

        raise ApiError(404, "pipeline_not_found", "The requested pipeline was not found.")

    pipeline_version = session.scalar(
        select(PipelineVersion).where(
            PipelineVersion.pipeline_id == pipeline.pipeline_id,
            PipelineVersion.version == pipeline.version,
        )
    )
    if pipeline_version is None:
        from app.core.exceptions import ApiError

        raise ApiError(
            409, "pipeline_version_missing", "The pipeline has no persisted immutable version."
        )
    general_tabular = (pipeline_version.configuration or {}).get("mode") == "general_tabular"

    idempotency_material = f"{pipeline_version.pipeline_version_id}:{source.checksum}"
    idempotency_key = hashlib.sha256(idempotency_material.encode()).hexdigest()
    existing = session.scalar(
        select(PipelineRun).where(PipelineRun.idempotency_key == idempotency_key)
    )
    if existing is not None and not retry:
        return existing
    if retry and (
        existing is None
        or existing.status != "FAILED"
        or (existing.error or {}).get("code") != "pipeline_execution_failed"
    ):
        from app.core.exceptions import ApiError

        raise ApiError(409, "run_not_retryable", "Only failed runs can be retried.")

    if existing is None:
        run_id = f"run_{idempotency_key[:32]}"
        run = PipelineRun(
            run_id=run_id,
            idempotency_key=idempotency_key,
            pipeline_id=pipeline.pipeline_id,
            pipeline_version_id=pipeline_version.pipeline_version_id,
            source_file_id=source.source_file_id,
            status="RUNNING",
            counts={"input": 0, "accepted": 0, "rejected": 0, "duplicates": 0, "published": 0},
            profile={},
            started_at=utc_now(),
        )
        session.add(run)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            competing_run = session.scalar(
                select(PipelineRun).where(PipelineRun.idempotency_key == idempotency_key)
            )
            if competing_run is None or retry:
                raise
            logger.info(
                "Concurrent run request reused the persisted run",
                extra={"run_id": competing_run.run_id},
            )
            return competing_run
        attempt_number = 1
        audit_type = "run.created"
    else:
        run = existing
        run_id = run.run_id
        attempt_number = (
            session.scalar(
                select(func.max(RunAttempt.attempt_number)).where(RunAttempt.run_id == run_id)
            )
            or 0
        ) + 1
        run.status = "RUNNING"
        run.started_at = utc_now()
        run.completed_at = None
        run.error = None
        run.counts = {
            "input": 0,
            "accepted": 0,
            "rejected": 0,
            "duplicates": 0,
            "published": 0,
        }
        run.profile = {}
        session.commit()
        audit_type = "run.retry_started"

    attempt_id = f"{run_id}_attempt_{attempt_number}"
    attempt = RunAttempt(
        attempt_id=attempt_id,
        run_id=run_id,
        attempt_number=attempt_number,
        status="RUNNING",
        started_at=utc_now(),
    )
    session.add(attempt)
    session.commit()
    session.add(
        AuditEvent(
            run_id=run_id,
            event_type=audit_type,
            event_data={"source_file_id": source.source_file_id, "attempt_id": attempt_id},
        )
    )
    session.commit()

    temp_paths: list[Path] = []
    final_paths: list[Path] = []
    processing_plan: ProcessingPlan | None = None
    active_stage = "ingestion"
    active_timer = _start_stage_timer()
    try:
        raw_content = Path(source.storage_path).read_bytes()
        columns, records = parse_source_bytes(raw_content, source.original_filename)
        _add_stage(
            session,
            run_id,
            attempt_id,
            "ingestion",
            "SUCCESS",
            len(records),
            len(records),
            0,
            {"columns": columns},
            active_timer,
        )

        active_stage = "profiling"
        active_timer = _start_stage_timer()
        profile = profile_records(columns, records, sample_size=settings.profile_sample_size)
        if not source.schema_fingerprint:
            source.profile = profile
            source.schema_fingerprint = profile["schema_fingerprint"]
            session.commit()
        approved_schema = (
            latest_schema_profile(session, source.schema_fingerprint or profile["schema_fingerprint"], status="approved")
            if general_tabular
            else None
        )
        approved_rules = (
            latest_approved_rules(session, source.schema_fingerprint or profile["schema_fingerprint"])
            if general_tabular
            else []
        )
        approved_transforms = (
            latest_approved_transformations(session, source.schema_fingerprint or profile["schema_fingerprint"])
            if general_tabular
            else []
        )
        mapping_transforms = (
            approved_mapping_transformations(approved_schema, columns) if general_tabular else []
        )
        plan = {
            "source_checksum": source.checksum,
            "schema_fingerprint": source.schema_fingerprint or profile["schema_fingerprint"],
            "schema_profile_id": approved_schema.profile_id if approved_schema else None,
            "rule_versions": [rule.model_dump(mode="json") for rule in approved_rules],
            "mapping_transformations": [item.model_dump(mode="json") for item in mapping_transforms],
            "transformations": [item.model_dump(mode="json") for item in approved_transforms],
            "components": ["sampled_profiler", "approved_schema_mapping", "allowlisted_rules", "allowlisted_transformations", "atomic_csv_publisher"],
        }
        plan_id = f"plan_{hashlib.sha256(f'{run_id}:{attempt_number}'.encode()).hexdigest()[:32]}"
        plan_version = (
            session.scalar(
                select(func.max(ProcessingPlan.version)).where(
                    ProcessingPlan.source_file_id == source.source_file_id
                )
            )
            or 0
        ) + 1
        processing_plan = ProcessingPlan(
            plan_id=plan_id,
            source_file_id=source.source_file_id,
            schema_profile_id=approved_schema.profile_id if approved_schema else None,
            version=plan_version,
            plan=plan,
            status="running",
        )
        session.add(processing_plan)
        run.profile = {
            **profile,
            "source_checksum": source.checksum,
            **({"processing_plan_id": plan_id, "processing_plan": plan} if general_tabular else {}),
        }
        _add_stage(
            session,
            run_id,
            attempt_id,
            "profiling",
            "SUCCESS",
            len(records),
            len(records),
            0,
            {
                **profile,
                **({"processing_plan_id": plan_id, "processing_plan": plan} if general_tabular else {}),
            },
            active_timer,
        )

        active_stage = "validation"
        active_timer = _start_stage_timer()
        if general_tabular:
            mapped = apply_transformations(columns, records, mapping_transforms)
            processing_columns = mapped["columns"]
            source_column_by_output = {
                transformation.config["new_name"]: transformation.field
                for transformation in mapping_transforms
                if transformation.operator == "rename_column"
            }
            result = validate_tabular_records(
                processing_columns,
                mapped["records"],
                profile=profile,
                source_column_by_output=source_column_by_output,
            )
            rule_result = evaluate_rules(processing_columns, result["accepted"], approved_rules)
            result["validation_results"].extend(rule_result["validation_results"])
            result["requires_configuration_count"] = rule_result["requires_configuration_count"]
            result["accepted"] = rule_result["accepted"]
            result["rejected"].extend(mapped["rejected"])
            result["rejected"].extend(rule_result["rejected"])
            executed_rule_ids = set(rule_result["executed_rule_ids"])
            result["applied_rules"] = [
                rule.model_dump(mode="json")
                for rule in approved_rules
                if rule.rule_id in executed_rule_ids
            ]
            result["selected_rules"] = [rule.model_dump(mode="json") for rule in approved_rules]
            result["mapping_metrics"] = mapped["metrics"]
        else:
            processing_columns = columns
            customer_ids = read_master_ids(settings.customer_master_path, "customer_id")
            merchant_ids = read_master_ids(settings.merchant_master_path, "merchant_id")
            result = validate_and_classify(columns, records, customer_ids, merchant_ids)
        _persist_validation_results(session, run_id, attempt_id, result.get("validation_results", []))
        requires_configuration_count = sum(
            validation_result.get("status") == "REQUIRES_CONFIGURATION"
            for validation_result in result.get("validation_results", [])
        )
        validation_stage_status = (
            "FAILED"
            if result["missing_columns"]
            else ("PARTIAL" if requires_configuration_count else "SUCCESS")
        )
        accepted = result["accepted"]
        rejected = result["rejected"]
        duplicates = result["duplicates"]
        counts = {
            "input": len(records),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "duplicates": len(duplicates),
            "published": 0,
        }
        run.counts = dict(counts)
        for row in rejected:
            session.add(
                RejectedRecord(
                    run_id=run_id,
                    attempt_id=attempt_id,
                    source_file_id=source.source_file_id,
                    source_row_number=row["source_row_number"],
                    original_payload=row.get("original_payload", row["payload"]),
                    reason_code=row["reason_code"],
                    rejection_reasons=row["rejection_reasons"],
                )
            )
        for row in duplicates:
            session.add(
                DuplicateRecord(
                    run_id=run_id,
                    attempt_id=attempt_id,
                    source_row_number=row["source_row_number"],
                    duplicate_of_row_number=row["duplicate_of_row_number"],
                    duplicate_key=row["duplicate_key"],
                )
            )
        _add_stage(
            session,
            run_id,
            attempt_id,
            "validation",
            validation_stage_status,
            len(records),
            len(accepted),
            len(rejected),
            {
                "duplicate_count": len(duplicates),
                "missing_columns": result["missing_columns"],
                "added_columns": result["added_columns"],
                "schema_compatibility": result["compatibility"],
                "out_of_order_count": result["out_of_order_count"],
                "approved_rule_count": len(result.get("applied_rules", [])),
                "requires_configuration_count": requires_configuration_count,
                "rule_violations": sum(row.get("reason_code") == "rule_violation" for row in rejected),
                "quality_summary": result.get("quality_summary", {}),
                "duplicate_rule": result.get(
                    "duplicate_rule",
                    "source_system + transaction_id, case-insensitive; invalid rows are rejected before deduplication",
                ),
            },
            active_timer,
        )

        active_stage = "transformation"
        active_timer = _start_stage_timer()
        ingested_at = utc_now().replace(tzinfo=UTC)
        if general_tabular:
            transformation_result = apply_transformations(
                processing_columns, accepted, approved_transforms
            )
            accepted = transformation_result["records"]
            transform_rejections = transformation_result["rejected"]
            rejected.extend(transform_rejections)
            result["accepted"] = accepted
            result["rejected"] = rejected
            for row in transform_rejections:
                session.add(
                    RejectedRecord(
                        run_id=run_id,
                        attempt_id=attempt_id,
                        source_file_id=source.source_file_id,
                        source_row_number=row["source_row_number"],
                        original_payload=row.get("original_payload", row["payload"]),
                        reason_code=row["reason_code"],
                        rejection_reasons=row["rejection_reasons"],
                    )
                )
            counts["accepted"] = len(accepted)
            counts["rejected"] = len(rejected)
            run.counts = dict(counts)
            transformed, output_columns = transform_tabular_records(
                transformation_result["columns"], accepted, source.source_file_id
            )
            output_columns = tuple(output_columns)
        else:
            transformed = transform_records(accepted, source.source_file_id, ingested_at)
            output_columns = OUTPUT_COLUMNS
        _add_stage(
            session,
            run_id,
            attempt_id,
            "transformation",
            "SUCCESS",
            len(accepted),
            len(transformed),
            0,
            {
                "output_columns": list(output_columns),
                "transformation": "preserve_source_columns_with_lineage" if general_tabular else "financial_transaction_normalization",
                **(
                    {
                        "applied_transformations": transformation_result["applied_transformations"],
                        "metrics": transformation_result["metrics"],
                        "failed_rows": len(transformation_result["rejected"]),
                    }
                    if general_tabular
                    else {}
                ),
            },
            active_timer,
        )

        accepted_amounts = {} if general_tabular else _amount_totals(transformed)
        active_stage = "publishing"
        active_timer = _start_stage_timer()
        output_dir = settings.output_dir / run_id
        quarantine_dir = settings.quarantine_dir / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / ("records.csv" if general_tabular else "transactions.csv")
        final_quarantine = quarantine_dir / "rejected_records.jsonl"
        output_temp = _temporary_path(output_dir)
        quarantine_temp = _temporary_path(quarantine_dir)
        temp_paths.extend((output_temp, quarantine_temp))
        write_csv(output_temp, transformed, columns=output_columns)
        _write_jsonl(quarantine_temp, rejected)

        publish_blocked = not general_tabular and bool(result["missing_columns"])
        if general_tabular:
            candidate_rows, candidate_amounts = _count_output_rows(output_temp), {}
        else:
            candidate_rows, candidate_amounts = _read_output_totals(output_temp)
        published_amounts = candidate_amounts if not publish_blocked else {}
        preflight_counts = {
            **counts,
            "published": candidate_rows if not publish_blocked else 0,
        }

        preflight = reconcile_counts(
            preflight_counts,
            accepted_amounts,
            published_amounts,
            amounts_applicable=not general_tabular,
        )
        if not preflight["balanced"]:
            active_stage = "reconciliation"
            active_timer = _start_stage_timer()
            _persist_validation_results(
                session, run_id, attempt_id, preflight["validation_results"]
            )
            _add_stage(
                session,
                run_id,
                attempt_id,
                "reconciliation",
                "FAILED",
                len(records),
                preflight_counts["published"],
                0,
                {
                    "phase": "pre_publish_preflight",
                    "candidate_published_rows": candidate_rows,
                    "checks": preflight["checks"],
                },
                active_timer,
            )
            raise RuntimeError("Reconciliation checks did not balance; output was not published.")

        if not publish_blocked:
            os.replace(output_temp, final_output)
            final_paths.append(final_output)
            counts["published"] = candidate_rows
        else:
            output_temp.unlink(missing_ok=True)
        os.replace(quarantine_temp, final_quarantine)
        final_paths.append(final_quarantine)
        _add_stage(
            session,
            run_id,
            attempt_id,
            "publishing",
            "SKIPPED" if publish_blocked else "SUCCESS",
            len(accepted),
            counts["published"],
            0,
            {
                "reason": "incompatible_schema" if publish_blocked else None,
                "candidate_row_count": candidate_rows,
            },
            active_timer,
        )

        active_stage = "reconciliation"
        active_timer = _start_stage_timer()
        run.counts = dict(counts)
        reconciliation = reconcile_counts(
            counts,
            accepted_amounts,
            published_amounts,
            amounts_applicable=not general_tabular,
        )
        _persist_validation_results(
            session, run_id, attempt_id, reconciliation["validation_results"]
        )
        _add_stage(
            session,
            run_id,
            attempt_id,
            "reconciliation",
            "SUCCESS" if reconciliation["balanced"] else "FAILED",
            len(records),
            counts["published"],
            0,
            {"checks": reconciliation["checks"]},
            active_timer,
        )
        if not reconciliation["balanced"]:
            raise RuntimeError("Reconciliation checks did not balance after publication.")

        run.counts = counts
        run.completed_at = utc_now()
        run.status = (
            "FAILED"
            if publish_blocked
            else (
                "PARTIAL"
                if rejected or duplicates or requires_configuration_count
                else "SUCCESS"
            )
        )
        attempt.status = run.status
        attempt.completed_at = run.completed_at
        if processing_plan is not None:
            processing_plan.status = run.status
        run.error = (
            {
                "code": "schema_incompatible",
                "message": "Required input columns are missing; publication was blocked.",
            }
            if publish_blocked
            else None
        )

        if not publish_blocked:
            session.add(
                PublishedArtifact(
                    artifact_id=f"art_{idempotency_key[:32]}",
                    run_id=run_id,
                    artifact_type="tabular_data" if general_tabular else "transactions",
                    storage_path=str(final_output),
                    checksum=sha256_file(final_output),
                    row_count=counts["published"],
                )
            )
        if rejected:
            session.add(
                PublishedArtifact(
                    artifact_id=f"qtn_{idempotency_key[:32]}",
                    run_id=run_id,
                    artifact_type="quarantine",
                    storage_path=str(final_quarantine),
                    checksum=sha256_file(final_quarantine),
                    row_count=len(rejected),
                )
            )
        session.add(
            ReconciliationResult(
                run_id=run_id,
                counts=counts,
                accepted_amounts_by_currency={
                    key: format(value, ".2f") for key, value in accepted_amounts.items()
                },
                published_amounts_by_currency={
                    key: format(value, ".2f") for key, value in published_amounts.items()
                },
                balanced=reconciliation["balanced"],
                checks=reconciliation["checks"],
            )
        )
        session.add(
            AuditEvent(
                run_id=run_id,
                event_type="run.completed" if not publish_blocked else "run.failed",
                event_data={
                    "status": run.status,
                    "counts": counts,
                    "schema_compatibility": result["compatibility"],
                },
            )
        )
        session.commit()
        logger.info("Pipeline run completed", extra={"run_id": run_id})
        return run
    except Exception as exc:
        session.rollback()
        for path in temp_paths + final_paths:
            path.unlink(missing_ok=True)
        persisted = session.get(PipelineRun, run_id)
        if persisted is not None:
            persisted.status = "FAILED"
            persisted.completed_at = utc_now()
            persisted.error = {
                "code": "pipeline_execution_failed",
                "message": "The pipeline did not complete. See the failed stage and server logs.",
            }
            failed_attempt = session.get(RunAttempt, attempt_id)
            failed_attempt.status = "FAILED"
            failed_attempt.error = {"error_type": type(exc).__name__}
            failed_attempt.completed_at = persisted.completed_at
            if processing_plan is not None:
                persisted_plan = session.get(ProcessingPlan, processing_plan.plan_id)
                if persisted_plan is not None:
                    persisted_plan.status = "FAILED"
            if not session.scalar(
                select(StageExecution).where(
                    StageExecution.attempt_id == attempt_id,
                    StageExecution.stage_name == active_stage,
                )
            ):
                _add_stage(
                    session,
                    run_id,
                    attempt_id,
                    active_stage,
                    "FAILED",
                    0,
                    0,
                    0,
                    {"error_type": type(exc).__name__},
                    active_timer,
                )
            session.add(
                AuditEvent(
                    run_id=run_id,
                    event_type="run.failed",
                    event_data={"stage": active_stage, "error_type": type(exc).__name__},
                )
            )
            session.commit()
        logger.exception("Pipeline run failed", extra={"run_id": run_id})
        return persisted


def _add_stage(
    session: Session,
    run_id: str,
    attempt_id: str,
    stage_name: str,
    status: str,
    input_count: int,
    output_count: int,
    reject_count: int,
    details: dict,
    stage_timer: tuple[datetime, float],
) -> None:
    started, monotonic_started = stage_timer
    completed = utc_now()
    session.add(
        StageExecution(
            run_id=run_id,
            attempt_id=attempt_id,
            stage_name=stage_name,
            status=status,
            input_count=input_count,
            output_count=output_count,
            reject_count=reject_count,
            details=details,
            started_at=started,
            completed_at=completed,
            duration_ms=max(0, int((time.perf_counter() - monotonic_started) * 1000)),
        )
    )
    # Each finished stage is durable evidence, even if a later stage fails and rolls back.
    session.commit()


def _persist_validation_results(
    session: Session,
    run_id: str,
    attempt_id: str,
    results: list[dict],
) -> None:
    for raw_result in results:
        result = ValidationResult.model_validate(raw_result)
        session.add(
            ValidationExecution(
                run_id=run_id,
                attempt_id=attempt_id,
                validation_id=result.validation_id,
                name=result.name,
                category=result.category,
                status=result.status,
                severity=result.severity,
                applicability=result.applicability.status,
                applicability_reason=result.applicability.reason,
                execution_stage=result.execution_stage,
                checked_rows=result.checked_rows,
                passed_rows=result.passed_rows,
                failed_rows=result.failed_rows,
                failure_percentage=result.failure_percentage,
                affected_columns=result.affected_columns,
                failure_examples=result.failure_examples,
                message=result.message,
                recommendation=result.recommendation,
                execution_time_ms=result.execution_time_ms,
                rule_version=result.rule_version,
                configuration_snapshot=result.configuration_snapshot,
            )
        )


def _temporary_path(directory: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        prefix=".datatrace-", suffix=".tmp", dir=directory, delete=False
    ) as stream:
        return Path(stream.name)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def _amount_totals(records: list[dict]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for row in records:
        currency = row["currency"]
        totals[currency] = totals.get(currency, Decimal("0.00")) + Decimal(row["amount"])
    return totals


def _read_output_totals(path: Path) -> tuple[int, dict[str, Decimal]]:
    totals: dict[str, Decimal] = {}
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            row_count += 1
            currency = row["currency"]
            totals[currency] = totals.get(currency, Decimal("0.00")) + Decimal(row["amount"])
    return row_count, totals


def _count_output_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def _start_stage_timer() -> tuple[datetime, float]:
    return utc_now(), time.perf_counter()
