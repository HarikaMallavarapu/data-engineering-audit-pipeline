"""Cached, budget-reserved and auditable AI suggestions."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from decimal import Decimal
from typing import Any

from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.copilot import provider
from app.core.config import Settings
from app.models import AIBudget, AICache, AIUsage, utc_now

logger = logging.getLogger(__name__)
TASK_SCHEMA_INFERENCE = "schema_inference"
AI_PROMPT_VERSION = "schema-suggestions-v3"


def infer_schema_with_tracking(
    session: Session, profile: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    configured = provider.provider_status(settings)
    active_provider = configured["provider"] or "local"
    active_model = configured["model"] or "local"
    cache_material = {
        "task": TASK_SCHEMA_INFERENCE,
        "prompt_version": AI_PROMPT_VERSION,
        "provider": active_provider,
        "model": active_model,
        "profile": profile,
    }
    cache_key = hashlib.sha256(
        json.dumps(cache_material, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()

    if settings.ai_cache_enabled:
        cached = session.get(AICache, cache_key)
        if cached is not None:
            _record_nonbillable_usage(
                session,
                provider=cached.provider,
                model=cached.model,
                cache_key=cache_key,
                status="cache_hit",
                latency_ms=0,
            )
            result = dict(cached.response)
            result["usage"] = {
                "task_type": TASK_SCHEMA_INFERENCE,
                "provider": cached.provider,
                "model": cached.model,
                "status": "cache_hit",
                "cached": True,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost_usd": "0.000000000",
                "reported_cost_usd": None,
                "latency_ms": 0,
            }
            return result

    if not configured["configured"]:
        analysis, details = provider.infer_schema_with_usage(profile, settings)
        return _record_fallback(session, analysis, details, cache_key)

    reserved_cost = _maximum_request_cost(settings)
    if not _reserve_budget(session, reserved_cost):
        analysis = provider.infer_schema(
            profile, settings.model_copy(update={"ai_provider": "none"})
        )
        analysis["fallback_reason"] = "ai_budget_exhausted"
        _record_nonbillable_usage(
            session,
            provider=active_provider,
            model=active_model,
            cache_key=cache_key,
            status="budget_exhausted",
            latency_ms=0,
            estimated_cost=0,
        )
        analysis["usage"] = _usage_response(
            provider=active_provider,
            model=active_model,
            status="budget_exhausted",
            cached=False,
            estimated=Decimal(0),
            reported=None,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )
        return analysis

    usage_row = AIUsage(
        provider=active_provider,
        model=active_model,
        task_type=TASK_SCHEMA_INFERENCE,
        status="pending",
        estimated_cost_usd=reserved_cost,
        cache_key=cache_key,
    )
    session.add(usage_row)
    session.commit()
    started = time.perf_counter()
    try:
        analysis, details = provider.infer_schema_with_usage(profile, settings)
    except Exception as exc:  # a broken provider response must never break deterministic processing
        logger.warning(
            "AI schema suggestion failed; using local profile",
            extra={"provider": active_provider, "error_type": type(exc).__name__},
        )
        analysis = provider.infer_schema(
            profile, settings.model_copy(update={"ai_provider": "none"})
        )
        details = {
            "status": "provider_unavailable",
            "provider": active_provider,
            "model": active_model,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reported_cost_usd": None,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    prompt_tokens = max(0, int(details.get("prompt_tokens", 0)))
    completion_tokens = max(0, int(details.get("completion_tokens", 0)))
    estimated = _estimate_cost(prompt_tokens, completion_tokens, settings)
    reported = _decimal_cost(details.get("reported_cost_usd"))
    charged = reported if reported is not None else estimated
    status = str(details.get("status", "provider_unavailable"))
    latency_ms = int(details.get("latency_ms", int((time.perf_counter() - started) * 1000)))

    usage_row.status = status
    usage_row.prompt_tokens = prompt_tokens
    usage_row.completion_tokens = completion_tokens
    usage_row.estimated_cost_usd = estimated
    usage_row.reported_cost_usd = reported
    usage_row.latency_ms = latency_ms
    usage_row.error_code = None if status == "success" else status
    # The provider may bill a response that fails our structured-output validation.
    # Account for every reported/estimated token charge, not only usable suggestions.
    _settle_budget(session, reserved_cost, charged)
    session.commit()

    if status == "success" and settings.ai_cache_enabled:
        session.add(
            AICache(
                cache_key=cache_key,
                task_type=TASK_SCHEMA_INFERENCE,
                provider=active_provider,
                model=active_model,
                response=analysis,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=estimated,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()

    analysis["usage"] = _usage_response(
        provider=active_provider,
        model=active_model,
        status=status,
        cached=False,
        estimated=estimated,
        reported=reported,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
    )
    return analysis


def _reserve_budget(session: Session, amount: Decimal) -> bool:
    """Atomically reserve worst-case token cost before contacting the provider."""
    row = session.execute(
        update(AIBudget)
        .where(
            AIBudget.budget_id == 1,
            AIBudget.used_usd + AIBudget.reserved_usd + amount <= AIBudget.limit_usd,
        )
        .values(reserved_usd=AIBudget.reserved_usd + amount, updated_at=utc_now())
    )
    session.commit()
    return row.rowcount == 1


def _settle_budget(session: Session, reserved: Decimal, actual: Decimal) -> None:
    session.execute(
        update(AIBudget)
        .where(AIBudget.budget_id == 1)
        .values(
            reserved_usd=case(
                (AIBudget.reserved_usd >= reserved, AIBudget.reserved_usd - reserved),
                else_=Decimal(0),
            ),
            used_usd=AIBudget.used_usd + actual,
            updated_at=utc_now(),
        )
    )


def _record_fallback(
    session: Session, analysis: dict[str, Any], details: dict[str, Any], cache_key: str
) -> dict[str, Any]:
    status = str(details.get("status", "not_configured"))
    active_provider = str(details.get("provider") or "local")
    active_model = str(details.get("model") or "local")
    latency_ms = int(details.get("latency_ms", 0))
    _record_nonbillable_usage(
        session,
        provider=active_provider,
        model=active_model,
        cache_key=cache_key,
        status=status,
        latency_ms=latency_ms,
    )
    analysis["usage"] = _usage_response(
        provider=active_provider,
        model=active_model,
        status=status,
        cached=False,
        estimated=Decimal(0),
        reported=None,
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=latency_ms,
    )
    return analysis


def _record_nonbillable_usage(
    session: Session,
    *,
    provider: str,
    model: str,
    cache_key: str,
    status: str,
    latency_ms: int,
    estimated_cost: int | Decimal = 0,
) -> None:
    session.add(
        AIUsage(
            provider=provider,
            model=model,
            task_type=TASK_SCHEMA_INFERENCE,
            status=status,
            estimated_cost_usd=Decimal(str(estimated_cost)),
            latency_ms=latency_ms,
            cache_key=cache_key,
        )
    )
    session.commit()


def _maximum_request_cost(settings: Settings) -> Decimal:
    amount = (
        Decimal(settings.ai_max_input_tokens) * Decimal(str(settings.ai_input_cost_per_million_usd))
        + Decimal(settings.ai_max_output_tokens) * Decimal(str(settings.ai_output_cost_per_million_usd))
    ) / Decimal(1_000_000)
    return amount.quantize(Decimal("0.000000001"))


def _estimate_cost(prompt_tokens: int, completion_tokens: int, settings: Settings) -> Decimal:
    amount = (
        Decimal(prompt_tokens) * Decimal(str(settings.ai_input_cost_per_million_usd))
        + Decimal(completion_tokens) * Decimal(str(settings.ai_output_cost_per_million_usd))
    ) / Decimal(1_000_000)
    return amount.quantize(Decimal("0.000000001"))


def _decimal_cost(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except Exception:
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def _usage_response(
    *,
    provider: str,
    model: str,
    status: str,
    cached: bool,
    estimated: Decimal,
    reported: Decimal | None,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
) -> dict[str, Any]:
    return {
        "task_type": TASK_SCHEMA_INFERENCE,
        "provider": provider,
        "model": model,
        "status": status,
        "cached": cached,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": f"{estimated:.9f}",
        "reported_cost_usd": f"{reported:.9f}" if reported is not None else None,
        "latency_ms": latency_ms,
    }
