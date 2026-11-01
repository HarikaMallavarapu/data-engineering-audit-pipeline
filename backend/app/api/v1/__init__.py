from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.audit import router as audit_router
from app.api.v1.duplicates import router as duplicates_router
from app.api.v1.engine import router as engine_router
from app.api.v1.pipelines import router as pipelines_router
from app.api.v1.quality import router as quality_router
from app.api.v1.quarantine import router as quarantine_router
from app.api.v1.reconciliation import router as reconciliation_router
from app.api.v1.runs import router as runs_router
from app.api.v1.sources import router as sources_router
from app.api.v1.validation import router as validation_router

router = APIRouter(prefix="/api/v1")
router.include_router(ai_router)
router.include_router(engine_router)
router.include_router(pipelines_router)
router.include_router(quality_router)
router.include_router(sources_router)
router.include_router(runs_router)
router.include_router(quarantine_router)
router.include_router(duplicates_router)
router.include_router(reconciliation_router)
router.include_router(audit_router)
router.include_router(validation_router)
