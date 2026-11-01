"""Persistence helpers for versioned schemas, rules, and transformations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.engine.quality.rules import RuleDefinition
from app.engine.transformation.registry import TransformationDefinition
from app.models import RuleVersion, SchemaProfile, SourceFile, TransformationVersion


def save_schema_suggestions(
    session: Session, source: SourceFile, analysis: dict
) -> SchemaProfile:
    fingerprint = source.schema_fingerprint or (source.profile or {}).get("schema_fingerprint")
    if not fingerprint:
        raise ValueError("The source does not have a persisted schema fingerprint.")
    latest = session.scalar(
        select(SchemaProfile)
        .where(SchemaProfile.schema_fingerprint == fingerprint)
        .order_by(SchemaProfile.version.desc())
        .limit(1)
    )
    profile_data = {"schema_profile": source.profile or {}, "analysis": analysis}
    if latest and latest.profile_data.get("analysis") == analysis:
        return latest
    version = (latest.version if latest else 0) + 1
    profile = SchemaProfile(
        profile_id=f"schema_{uuid4().hex}",
        source_file_id=source.source_file_id,
        schema_fingerprint=fingerprint,
        name=source.original_filename[:200],
        version=version,
        status="draft",
        profile_data=profile_data,
        mappings=analysis.get("mapping_suggestions", []),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def latest_schema_profile(
    session: Session, schema_fingerprint: str, *, status: str | None = None
) -> SchemaProfile | None:
    query = select(SchemaProfile).where(SchemaProfile.schema_fingerprint == schema_fingerprint)
    if status:
        query = query.where(SchemaProfile.status == status)
    return session.scalar(query.order_by(SchemaProfile.version.desc()).limit(1))


def approved_mapping_transformations(
    profile: SchemaProfile | None, source_columns: list[str]
) -> list[TransformationDefinition]:
    if profile is None:
        return []
    used = set(source_columns)
    transformations = []
    for index, mapping in enumerate(profile.mappings):
        if mapping.get("action") not in {"approve", "edit"}:
            continue
        source_column = mapping.get("source_column")
        semantic_field = mapping.get("semantic_field")
        if source_column not in used or not isinstance(semantic_field, str) or not semantic_field.strip():
            continue
        target = semantic_field.strip()
        if target == source_column or target in used:
            continue
        try:
            transformations.append(
                TransformationDefinition.model_validate(
                    {
                        "transform_id": f"approved_mapping_{index + 1}",
                        "operator": "rename_column",
                        "field": source_column,
                        "config": {"new_name": target},
                        "status": "approved",
                        "order": index,
                    }
                )
            )
        except ValueError:
            continue
        used.remove(source_column)
        used.add(target)
    return transformations


def latest_approved_rules(session: Session, schema_fingerprint: str) -> list[RuleDefinition]:
    rows = session.scalars(
        select(RuleVersion)
        .where(RuleVersion.schema_fingerprint == schema_fingerprint)
        .order_by(RuleVersion.rule_id, RuleVersion.version.desc())
    ).all()
    latest: dict[str, RuleVersion] = {}
    for row in rows:
        latest.setdefault(row.rule_id, row)
    rules = []
    for row in latest.values():
        if row.status != "approved":
            continue
        definition = {**row.definition, "status": "approved", "version": row.version}
        rules.append(RuleDefinition.model_validate(definition))
    return rules


def latest_approved_transformations(
    session: Session, schema_fingerprint: str
) -> list[TransformationDefinition]:
    rows = session.scalars(
        select(TransformationVersion)
        .where(TransformationVersion.schema_fingerprint == schema_fingerprint)
        .order_by(TransformationVersion.transform_id, TransformationVersion.version.desc())
    ).all()
    latest: dict[str, TransformationVersion] = {}
    for row in rows:
        latest.setdefault(row.transform_id, row)
    transformations = []
    for row in latest.values():
        if row.status != "approved":
            continue
        definition = {**row.definition, "status": "approved", "version": row.version}
        transformations.append(TransformationDefinition.model_validate(definition))
    return sorted(transformations, key=lambda item: item.order)


def next_rule_version(session: Session, rule_id: str) -> int:
    return (session.scalar(select(func.max(RuleVersion.version)).where(RuleVersion.rule_id == rule_id)) or 0) + 1


def next_transformation_version(session: Session, transform_id: str) -> int:
    return (
        session.scalar(
            select(func.max(TransformationVersion.version)).where(
                TransformationVersion.transform_id == transform_id
            )
        )
        or 0
    ) + 1


def now_utc() -> datetime:
    return datetime.now(UTC)
