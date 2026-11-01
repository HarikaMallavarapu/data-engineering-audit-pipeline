from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models import DuplicateRecord, RunAttempt
from app.schemas import DuplicateListResponse

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


@router.get("", response_model=DuplicateListResponse)
def list_duplicates(
    run_id: str | None = None,
    attempt_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(DuplicateRecord)
    count_query = select(func.count()).select_from(DuplicateRecord)
    if run_id:
        query = query.where(DuplicateRecord.run_id == run_id)
        count_query = count_query.where(DuplicateRecord.run_id == run_id)
    if attempt_id:
        query = query.where(DuplicateRecord.attempt_id == attempt_id)
        count_query = count_query.where(DuplicateRecord.attempt_id == attempt_id)
    else:
        latest_attempt_id = (
            select(RunAttempt.attempt_id)
            .where(RunAttempt.run_id == DuplicateRecord.run_id)
            .order_by(RunAttempt.attempt_number.desc())
            .limit(1)
            .scalar_subquery()
        )
        query = query.where(DuplicateRecord.attempt_id == latest_attempt_id)
        count_query = count_query.where(DuplicateRecord.attempt_id == latest_attempt_id)
    items = session.scalars(
        query.order_by(DuplicateRecord.run_id, DuplicateRecord.source_row_number)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": items,
        "total": session.scalar(count_query) or 0,
        "page": page,
        "page_size": page_size,
    }
