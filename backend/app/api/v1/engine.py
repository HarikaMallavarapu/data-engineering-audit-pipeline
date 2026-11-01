"""Schema, rule registry, transformation registry, and dry-run planning API."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session
from app.core.exceptions import ApiError
from app.engine.pipeline import parse_source_bytes, profile_records, validate_tabular_records
from app.engine.quality.rules import RuleDefinition, evaluate_rules, safe_compile
from app.engine.transformation.registry import TransformationDefinition, apply_transformations
from app.models import ProcessingPlan, RuleVersion, SchemaProfile, SourceFile, TransformationVersion
from app.schemas import (
    ProcessingPlanRequest,
    RegexTestRequest,
    RuleSaveRequest,
    SchemaProfileApprovalRequest,
    TransformationSaveRequest,
)
from app.services.ai_service import infer_schema_with_tracking
from app.services.engine_service import (
    approved_mapping_transformations,
    latest_approved_rules,
    latest_approved_transformations,
    latest_schema_profile,
    next_rule_version,
    next_transformation_version,
    now_utc,
    save_schema_suggestions,
)

router = APIRouter(prefix="/engine", tags=["dynamic engine"])


@router.get("/sources/{source_file_id}/profile")
def get_profile(source_file_id: str, session: Session = Depends(get_session)):
    source = _source(session, source_file_id)
    return {
        "source_file_id": source.source_file_id,
        "original_filename": source.original_filename,
        "checksum": source.checksum,
        "schema_fingerprint": source.schema_fingerprint,
        "profile": source.profile or {},
    }


@router.post("/sources/{source_file_id}/suggestions")
def suggest_processing(
    source_file_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    source = _source(session, source_file_id)
    settings: Settings = request.app.state.settings
    analysis = infer_schema_with_tracking(session, source.profile or {}, settings)
    analysis = _merge_local_profile_suggestions(analysis, source.profile or {})
    schema_profile = save_schema_suggestions(session, source, analysis)
    return {
        "schema_profile_id": schema_profile.profile_id,
        "version": schema_profile.version,
        "status": schema_profile.status,
        "schema_fingerprint": schema_profile.schema_fingerprint,
        "analysis": analysis,
    }


@router.get("/schema-profiles")
def list_schema_profiles(
    schema_fingerprint: str | None = None,
    source_file_id: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(SchemaProfile)
    if schema_fingerprint:
        query = query.where(SchemaProfile.schema_fingerprint == schema_fingerprint)
    if source_file_id:
        query = query.where(SchemaProfile.source_file_id == source_file_id)
    rows = session.scalars(query.order_by(SchemaProfile.created_at.desc()).limit(100)).all()
    return {"items": [_schema_profile_payload(row) for row in rows], "total": len(rows)}


@router.post("/schema-profiles/{profile_id}/approve")
def approve_schema_profile(
    profile_id: str,
    payload: SchemaProfileApprovalRequest,
    session: Session = Depends(get_session),
):
    previous = session.get(SchemaProfile, profile_id)
    if previous is None:
        raise ApiError(404, "schema_profile_not_found", "The schema profile was not found.")
    source = _source(session, previous.source_file_id)
    mappings = []
    for decision in payload.mappings:
        if decision.source_column not in source.columns:
            raise ApiError(422, "unknown_source_column", "A mapping refers to a column outside this source schema.")
        mappings.append(decision.model_dump())
    current = latest_schema_profile(session, previous.schema_fingerprint)
    version = (current.version if current else previous.version) + 1
    approved = SchemaProfile(
        profile_id=f"schema_{uuid4().hex}",
        source_file_id=source.source_file_id,
        schema_fingerprint=previous.schema_fingerprint,
        name=previous.name,
        version=version,
        status="approved" if any(item["action"] in {"approve", "edit"} for item in mappings) else "rejected",
        profile_data=previous.profile_data,
        mappings=mappings,
        approved_at=now_utc(),
    )
    session.add(approved)
    session.commit()
    session.refresh(approved)
    return _schema_profile_payload(approved)


@router.get("/schema-drift")
def compare_schemas(
    left_source_file_id: str,
    right_source_file_id: str,
    session: Session = Depends(get_session),
):
    left, right = _source(session, left_source_file_id), _source(session, right_source_file_id)
    left_types = (left.profile or {}).get("inferred_types", {})
    right_types = (right.profile or {}).get("inferred_types", {})
    left_columns, right_columns = set(left.columns), set(right.columns)
    shared = left_columns & right_columns
    return {
        "left": {"source_file_id": left.source_file_id, "filename": left.original_filename},
        "right": {"source_file_id": right.source_file_id, "filename": right.original_filename},
        "added_columns": sorted(right_columns - left_columns),
        "missing_columns": sorted(left_columns - right_columns),
        "type_conflicts": [
            {"column": column, "left_type": left_types.get(column), "right_type": right_types.get(column)}
            for column in sorted(shared)
            if left_types.get(column) != right_types.get(column)
        ],
        "left_fingerprint": left.schema_fingerprint,
        "right_fingerprint": right.schema_fingerprint,
    }


@router.get("/registry")
def get_registry():
    return {
        "rule_types": [
            "required", "type", "regex", "date_range", "numeric_range", "email", "phone",
            "identifier", "unique", "referential", "cross_field", "conditional", "domain", "custom",
        ],
        "transformation_operators": [
            "rename_column", "normalize_whitespace", "standardize_case", "cast_type", "parse_date",
            "normalize_currency", "replace_null", "extract_regex",
        ],
        "execution_safety": "Only registered declarative operators run; Python, SQL, shell, and model-generated code are never executed.",
    }


@router.post("/rules/test-regex")
def test_regex(payload: RegexTestRequest):
    try:
        pattern = safe_compile(payload.pattern)
    except ValueError as exc:
        raise ApiError(422, "unsafe_regex", str(exc)) from exc
    matches = [bool(pattern.fullmatch(value)) for value in payload.values]
    return {
        "pattern": payload.pattern,
        "sample_count": len(payload.values),
        "matching_count": sum(matches),
        "non_matching_count": len(matches) - sum(matches),
        "results": [
            {"value": value, "matches": matched}
            for value, matched in zip(payload.values, matches, strict=True)
        ],
    }


@router.get("/rules")
def list_rules(schema_fingerprint: str, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(RuleVersion)
        .where(RuleVersion.schema_fingerprint == schema_fingerprint)
        .order_by(RuleVersion.rule_id, RuleVersion.version.desc())
    ).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.rule_id, row)
    return {"items": [_rule_payload(row) for row in latest.values()], "total": len(latest)}


@router.get("/rules/{rule_id}/history")
def rule_history(rule_id: str, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(RuleVersion).where(RuleVersion.rule_id == rule_id).order_by(RuleVersion.version.desc())
    ).all()
    return {"items": [_rule_payload(row) for row in rows], "total": len(rows)}


@router.post("/rules")
def create_rule(payload: RuleSaveRequest, session: Session = Depends(get_session)):
    return _save_rule(session, payload)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, payload: RuleSaveRequest, session: Session = Depends(get_session)):
    definition = dict(payload.definition)
    definition["rule_id"] = rule_id
    payload = payload.model_copy(update={"definition": definition})
    return _save_rule(session, payload)


@router.get("/transformations")
def list_transformations(schema_fingerprint: str, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(TransformationVersion)
        .where(TransformationVersion.schema_fingerprint == schema_fingerprint)
        .order_by(TransformationVersion.transform_id, TransformationVersion.version.desc())
    ).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.transform_id, row)
    return {"items": [_transformation_payload(row) for row in latest.values()], "total": len(latest)}


@router.get("/transformations/{transform_id}/history")
def transformation_history(transform_id: str, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(TransformationVersion)
        .where(TransformationVersion.transform_id == transform_id)
        .order_by(TransformationVersion.version.desc())
    ).all()
    return {"items": [_transformation_payload(row) for row in rows], "total": len(rows)}


@router.post("/transformations")
def create_transformation(
    payload: TransformationSaveRequest, session: Session = Depends(get_session)
):
    return _save_transformation(session, payload)


@router.put("/transformations/{transform_id}")
def update_transformation(
    transform_id: str,
    payload: TransformationSaveRequest,
    session: Session = Depends(get_session),
):
    definition = dict(payload.definition)
    definition["transform_id"] = transform_id
    payload = payload.model_copy(update={"definition": definition})
    return _save_transformation(session, payload)


@router.post("/plans")
def create_processing_plan(
    payload: ProcessingPlanRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    settings: Settings = request.app.state.settings
    source = _source(session, payload.source_file_id)
    raw_content = _read_source(source)
    columns, records = parse_source_bytes(raw_content, source.original_filename)
    profile = profile_records(columns, records, sample_size=settings.profile_sample_size)
    schema_analysis = None
    if payload.include_ai_suggestions:
        schema_analysis = infer_schema_with_tracking(session, profile, settings)
        schema_analysis = _merge_local_profile_suggestions(schema_analysis, profile)
        saved_profile = save_schema_suggestions(session, source, schema_analysis)
    else:
        saved_profile = latest_schema_profile(session, source.schema_fingerprint or "", status="approved")

    mappings = approved_mapping_transformations(saved_profile, source.columns)
    rules = latest_approved_rules(session, source.schema_fingerprint or "")
    transformations = mappings + latest_approved_transformations(session, source.schema_fingerprint or "")
    transform_result = apply_transformations(columns, records, transformations)
    source_column_by_output = {
        transformation.config["new_name"]: transformation.field
        for transformation in mappings
        if transformation.operator == "rename_column"
    }
    validation = validate_tabular_records(
        transform_result["columns"],
        transform_result["records"],
        profile=profile,
        source_column_by_output=source_column_by_output,
    )
    rule_result = evaluate_rules(transform_result["columns"], validation["accepted"], rules)
    dry_run_validation_results = [
        *validation["validation_results"],
        *rule_result["validation_results"],
    ]
    accepted = rule_result["accepted"]
    rejected = validation["rejected"] + transform_result["rejected"] + rule_result["rejected"]
    counts = {
        "input": len(records),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "duplicates": len(validation["duplicates"]),
        "published": 0,
    }
    plan = {
        "source_checksum": source.checksum,
        "schema_fingerprint": source.schema_fingerprint,
        "schema_analysis": schema_analysis,
        "component_sequence": ["profile", "approved_mappings", "base_validation", "approved_rules", "approved_transformations", "publish"],
        "selected_rules": [rule.model_dump(mode="json") for rule in rules],
        "validation_results": dry_run_validation_results,
        "selected_transformations": [item.model_dump(mode="json") for item in transformations],
        "transformation_metrics": transform_result["metrics"],
        "quality_summary": validation["quality_summary"],
        "confidence_policy": {"high": "suggest only; policy may auto-apply deterministic rules", "medium": "user review", "low": "do not guess"},
        "dry_run": {
            "counts": counts,
            "validation_results": dry_run_validation_results,
            "requires_configuration_count": rule_result["requires_configuration_count"],
            "quality_summary": validation["quality_summary"],
            "preview": [
                {"source_row_number": record["source_row_number"], "payload": record["payload"]}
                for record in accepted[:5]
            ],
            "rejection_reasons": [item.get("reason_code", "transformation_error") for item in rejected[:20]],
        },
    }
    version = (session.scalar(select(func.max(ProcessingPlan.version)).where(ProcessingPlan.source_file_id == source.source_file_id)) or 0) + 1
    persisted = ProcessingPlan(
        plan_id=f"plan_{uuid4().hex}",
        source_file_id=source.source_file_id,
        schema_profile_id=saved_profile.profile_id if saved_profile else None,
        version=version,
        plan=plan,
        status="draft",
    )
    session.add(persisted)
    session.commit()
    return {"plan_id": persisted.plan_id, "version": version, "status": persisted.status, **plan}


@router.get("/plans")
def list_plans(source_file_id: str, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(ProcessingPlan)
        .where(ProcessingPlan.source_file_id == source_file_id)
        .order_by(ProcessingPlan.version.desc())
        .limit(50)
    ).all()
    return {"items": [{"plan_id": row.plan_id, "version": row.version, "status": row.status, "plan": row.plan, "created_at": row.created_at} for row in rows], "total": len(rows)}


def _source(session: Session, source_file_id: str) -> SourceFile:
    source = session.get(SourceFile, source_file_id)
    if source is None:
        raise ApiError(404, "source_not_found", "The requested source file was not found.")
    return source


def _merge_local_profile_suggestions(
    analysis: dict, profile: dict
) -> dict:
    """Keep deterministic, evidence-backed suggestions available beside LLM output."""
    result = dict(analysis)
    mappings = list(result.get("mapping_suggestions", []))
    known_columns = {item.get("source_column") for item in mappings if isinstance(item, dict)}
    for candidate in profile.get("mapping_candidates", []):
        if not isinstance(candidate, dict) or candidate.get("source_column") in known_columns:
            continue
        column = candidate.get("source_column")
        semantic = candidate.get("suggested_semantic_field")
        if not isinstance(column, str) or not isinstance(semantic, str):
            continue
        mappings.append(
            {
                "source_column": column,
                "semantic_field": semantic,
                "confidence": candidate.get("confidence", 0.0),
                "explanation": "; ".join(candidate.get("evidence", []))
                or "Local header and profile evidence; confirm the business meaning.",
                "status": "suggested",
            }
        )
    result["mapping_suggestions"] = mappings

    rules = list(result.get("rule_suggestions", []))
    known_rule_fields = {
        (item.get("field"), item.get("rule_type"))
        for item in rules
        if isinstance(item, dict)
    }
    for index, column in enumerate(profile.get("column_profiles", []), start=1):
        if not isinstance(column, dict):
            continue
        field = column.get("name")
        suggestion = column.get("regex_suggestion")
        if not isinstance(field, str) or not isinstance(suggestion, dict):
            continue
        if (field, "regex") in known_rule_fields:
            continue
        rules.append(
            {
                "rule_id": f"local_regex_{index}",
                "field": field,
                "rule_type": "regex",
                "config": {"pattern": suggestion["pattern"]},
                "severity": "warning",
                "confidence": suggestion["confidence"],
                "explanation": suggestion["note"],
                "status": "draft",
                "enabled": False,
                "sample_evidence": {
                    "sample_count": suggestion["sample_count"],
                    "matching_count": suggestion["matching_count"],
                    "non_matching_count": suggestion["non_matching_count"],
                    "matching_examples": suggestion["matching_examples"],
                    "non_matching_examples": suggestion["non_matching_examples"],
                },
            }
        )
    result["rule_suggestions"] = rules
    return result


def _save_rule(session: Session, payload: RuleSaveRequest):
    source = session.scalar(select(SourceFile).where(SourceFile.schema_fingerprint == payload.schema_fingerprint))
    if source is None:
        raise ApiError(404, "schema_not_found", "No uploaded source matches this schema fingerprint.")
    raw = dict(payload.definition)
    raw.pop("explanation", None)
    raw.pop("sample_evidence", None)
    rule_id = str(raw.get("rule_id") or f"rule_{uuid4().hex}")
    if rule_id.startswith(("ai_suggestion_", "local_regex_")):
        rule_id = f"rule_{uuid4().hex}"
    raw.update({"rule_id": rule_id, "status": payload.status})
    version = next_rule_version(session, rule_id)
    raw["version"] = version
    try:
        definition = RuleDefinition.model_validate(raw)
    except ValueError as exc:
        raise ApiError(422, "invalid_rule", str(exc)) from exc
    if definition.field not in _schema_fields(session, source):
        raise ApiError(422, "unknown_rule_field", "The rule field is not present in this schema.")
    row = RuleVersion(
        rule_version_id=f"{rule_id}:v{version}",
        rule_id=rule_id,
        schema_fingerprint=payload.schema_fingerprint,
        version=version,
        status=payload.status,
        definition=definition.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    return _rule_payload(row)


def _save_transformation(session: Session, payload: TransformationSaveRequest):
    source = session.scalar(select(SourceFile).where(SourceFile.schema_fingerprint == payload.schema_fingerprint))
    if source is None:
        raise ApiError(404, "schema_not_found", "No uploaded source matches this schema fingerprint.")
    raw = dict(payload.definition)
    raw.pop("confidence", None)
    raw.pop("explanation", None)
    transform_id = str(raw.get("transform_id") or f"transform_{uuid4().hex}")
    if transform_id.startswith("ai_suggestion_"):
        transform_id = f"transform_{uuid4().hex}"
    raw.update({"transform_id": transform_id, "status": payload.status})
    version = next_transformation_version(session, transform_id)
    raw["version"] = version
    try:
        definition = TransformationDefinition.model_validate(raw)
    except ValueError as exc:
        raise ApiError(422, "invalid_transformation", str(exc)) from exc
    if definition.field not in _schema_fields(session, source):
        raise ApiError(422, "unknown_transformation_field", "The transformation field is not present in this schema.")
    row = TransformationVersion(
        transform_version_id=f"{transform_id}:v{version}",
        transform_id=transform_id,
        schema_fingerprint=payload.schema_fingerprint,
        version=version,
        status=payload.status,
        definition=definition.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    return _transformation_payload(row)


def _read_source(source: SourceFile) -> bytes:
    from pathlib import Path

    return Path(source.storage_path).read_bytes()


def _schema_fields(session: Session, source: SourceFile) -> set[str]:
    fields = set(source.columns)
    profile = latest_schema_profile(session, source.schema_fingerprint or "", status="approved")
    if profile:
        for mapping in profile.mappings:
            if mapping.get("action") in {"approve", "edit"} and mapping.get("source_column") in source.columns:
                target = mapping.get("semantic_field")
                if isinstance(target, str) and target.strip():
                    fields.add(target.strip())
    return fields


def _schema_profile_payload(row: SchemaProfile):
    return {
        "profile_id": row.profile_id,
        "source_file_id": row.source_file_id,
        "schema_fingerprint": row.schema_fingerprint,
        "name": row.name,
        "version": row.version,
        "status": row.status,
        "profile_data": row.profile_data,
        "mappings": row.mappings,
        "created_at": row.created_at,
        "approved_at": row.approved_at,
    }


def _rule_payload(row: RuleVersion):
    return {"rule_id": row.rule_id, "version": row.version, "schema_fingerprint": row.schema_fingerprint, "status": row.status, "definition": row.definition, "created_at": row.created_at}


def _transformation_payload(row: TransformationVersion):
    return {"transform_id": row.transform_id, "version": row.version, "schema_fingerprint": row.schema_fingerprint, "status": row.status, "definition": row.definition, "created_at": row.created_at}
