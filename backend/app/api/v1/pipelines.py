from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models import Pipeline
from app.schemas import PipelineResponse

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.get("", response_model=list[PipelineResponse])
def list_pipelines(session: Session = Depends(get_session)):
    return session.scalars(select(Pipeline).order_by(Pipeline.pipeline_id)).all()
