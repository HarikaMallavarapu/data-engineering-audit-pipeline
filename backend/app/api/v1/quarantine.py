from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models import RejectedRecord, RunAttempt
from app.schemas import QuarantineListResponse

router = APIRouter(prefix="/quarantine", tags=["quarantine"])


@router.get("", response_model=QuarantineListResponse)
def list_rejected(
    run_id: str | None = None,
    attempt_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(RejectedRecord)
    count_query = select(func.count()).select_from(RejectedRecord)
    if run_id:
        query = query.where(RejectedRecord.run_id == run_id)
        count_query = count_query.where(RejectedRecord.run_id == run_id)
    if attempt_id:
        query = query.where(RejectedRecord.attempt_id == attempt_id)
        count_query = count_query.where(RejectedRecord.attempt_id == attempt_id)
    else:
        latest_attempt_id = (
            select(RunAttempt.attempt_id)
            .where(RunAttempt.run_id == RejectedRecord.run_id)
            .order_by(RunAttempt.attempt_number.desc())
            .limit(1)
            .scalar_subquery()
        )
        query = query.where(RejectedRecord.attempt_id == latest_attempt_id)
        count_query = count_query.where(RejectedRecord.attempt_id == latest_attempt_id)
    items = session.scalars(
        query.order_by(RejectedRecord.run_id, RejectedRecord.source_row_number)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": items,
        "total": session.scalar(count_query) or 0,
        "page": page,
        "page_size": page_size,
    }
