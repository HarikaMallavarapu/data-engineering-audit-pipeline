from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_session
from app.core.exceptions import ApiError
from app.models import PipelineRun
from app.schemas import RunCreateRequest, RunListResponse, RunResponse
from app.services.execution_service import execute_pipeline

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
def create_run(
    payload: RunCreateRequest, request: Request, session: Session = Depends(get_session)
):
    run = execute_pipeline(
        session, request.app.state.settings, payload.source_file_id, payload.pipeline_id
    )
    return _load_run(session, run.run_id)


@router.get("", response_model=RunListResponse)
def list_runs(page: int = 1, page_size: int = 25, session: Session = Depends(get_session)):
    page, page_size = max(1, page), min(max(1, page_size), 100)
    total = session.scalar(select(func.count()).select_from(PipelineRun)) or 0
    items = session.scalars(
        select(PipelineRun)
        .options(selectinload(PipelineRun.stages))
        .order_by(PipelineRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": items, "total": total}


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, session: Session = Depends(get_session)):
    return _load_run(session, run_id)


@router.post("/{run_id}/retry", response_model=RunResponse)
def retry_run(run_id: str, request: Request, session: Session = Depends(get_session)):
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise ApiError(404, "run_not_found", "The requested pipeline run was not found.")
    retried = execute_pipeline(
        session,
        request.app.state.settings,
        run.source_file_id,
        run.pipeline_id,
        retry=True,
    )
    return _load_run(session, retried.run_id)


def _load_run(session: Session, run_id: str) -> PipelineRun:
    run = session.scalar(
        select(PipelineRun)
        .options(selectinload(PipelineRun.stages))
        .where(PipelineRun.run_id == run_id)
    )
    if run is None:
        raise ApiError(404, "run_not_found", "The requested pipeline run was not found.")
    run.stages.sort(key=lambda stage: stage.stage_execution_id)
    return run
