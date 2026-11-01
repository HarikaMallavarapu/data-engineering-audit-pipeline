from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.exceptions import ApiError
from app.models import ReconciliationResult
from app.schemas import ReconciliationResponse

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.get("/{run_id}", response_model=ReconciliationResponse)
def get_reconciliation(run_id: str, session: Session = Depends(get_session)):
    result = session.get(ReconciliationResult, run_id)
    if result is None:
        raise ApiError(
            404, "reconciliation_not_found", "No reconciliation result exists for this run."
        )
    return {
        "run_id": result.run_id,
        "counts": result.counts,
        "accepted_amounts_by_currency": result.accepted_amounts_by_currency,
        "published_amounts_by_currency": result.published_amounts_by_currency,
        "balanced": result.balanced,
        "checks": result.checks,
    }
