"""Local AI provider status, usage ledger, and application spend controls."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.copilot.provider import provider_status
from app.core.database import get_session
from app.core.exceptions import ApiError
from app.models import AIBudget, AICache, AIUsage, utc_now
from app.schemas import AIBudgetResetRequest

router = APIRouter(prefix="/ai", tags=["AI usage and budget"])


@router.get("/status")
def get_ai_status(request: Request, session: Session = Depends(get_session)):
    settings = request.app.state.settings
    status = provider_status(settings)
    budget = session.get(AIBudget, 1)
    return {
        **status,
        "budget": _budget_payload(budget),
        "limits": {
            "max_input_tokens": settings.ai_max_input_tokens,
            "max_output_tokens": settings.ai_max_output_tokens,
            "max_retries": settings.ai_max_retries,
            "cache_enabled": settings.ai_cache_enabled,
            "request_timeout_seconds": settings.ai_timeout_seconds,
        },
    }


@router.get("/usage")
def list_ai_usage(page: int = 1, page_size: int = 25, session: Session = Depends(get_session)):
    page, page_size = max(1, page), min(max(1, page_size), 100)
    total = session.scalar(select(func.count()).select_from(AIUsage)) or 0
    items = session.scalars(
        select(AIUsage)
        .order_by(AIUsage.created_at.desc(), AIUsage.usage_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_usage_payload(row) for row in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/budget")
def get_budget(session: Session = Depends(get_session)):
    return _budget_payload(session.get(AIBudget, 1))


@router.post("/budget/reset")
def reset_budget(payload: AIBudgetResetRequest, session: Session = Depends(get_session)):
    budget = session.get(AIBudget, 1)
    if budget is None:
        raise ApiError(503, "ai_budget_unavailable", "The AI budget ledger is not initialized.")
    if budget.reserved_usd > 0:
        raise ApiError(409, "ai_requests_in_flight", "Wait for active AI requests before resetting the test budget.")
    budget.used_usd = Decimal("0")
    budget.reset_count += 1
    budget.updated_at = utc_now()
    session.commit()
    return _budget_payload(budget)


@router.delete("/cache")
def clear_ai_cache(session: Session = Depends(get_session)):
    count = session.scalar(select(func.count()).select_from(AICache)) or 0
    session.query(AICache).delete(synchronize_session=False)
    session.commit()
    return {"cleared_entries": count}


def _budget_payload(budget: AIBudget | None):
    if budget is None:
        return {"limit_usd": "0", "used_usd": "0", "reserved_usd": "0", "remaining_usd": "0", "reset_count": 0}
    remaining = max(Decimal(0), budget.limit_usd - budget.used_usd - budget.reserved_usd)
    return {
        "limit_usd": f"{budget.limit_usd:.9f}",
        "used_usd": f"{budget.used_usd:.9f}",
        "reserved_usd": f"{budget.reserved_usd:.9f}",
        "remaining_usd": f"{remaining:.9f}",
        "reset_count": budget.reset_count,
        "updated_at": budget.updated_at,
    }


def _usage_payload(row: AIUsage):
    return {
        "usage_id": row.usage_id,
        "provider": row.provider,
        "model": row.model,
        "task_type": row.task_type,
        "status": row.status,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "estimated_cost_usd": f"{row.estimated_cost_usd:.9f}",
        "reported_cost_usd": f"{row.reported_cost_usd:.9f}" if row.reported_cost_usd is not None else None,
        "latency_ms": row.latency_ms,
        "cache_key": row.cache_key,
        "error_code": row.error_code,
        "created_at": row.created_at,
    }
