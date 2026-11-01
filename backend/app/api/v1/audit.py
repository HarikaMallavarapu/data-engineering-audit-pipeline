from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models import AuditEvent
from app.schemas import AuditListResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditListResponse)
def list_audit(
    run_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(AuditEvent)
    count_query = select(func.count()).select_from(AuditEvent)
    if run_id:
        query = query.where(AuditEvent.run_id == run_id)
        count_query = count_query.where(AuditEvent.run_id == run_id)
    items = session.scalars(
        query.order_by(AuditEvent.audit_event_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": items,
        "total": session.scalar(count_query) or 0,
        "page": page,
        "page_size": page_size,
    }
