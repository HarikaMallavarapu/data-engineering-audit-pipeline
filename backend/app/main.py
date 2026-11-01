import logging
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as api_v1_router
from app.core.config import Settings
from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions import ApiError, api_error_handler, unexpected_error_handler
from app.core.logging_config import bind_request_id, configure_logging
from app.models import AIBudget, Pipeline, PipelineVersion

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    configure_logging(app_settings)
    engine = create_database_engine(app_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for directory in (
            app_settings.storage_dir,
            app_settings.output_dir,
            app_settings.quarantine_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(bind=engine)
        with session_factory() as session:
            budget = session.get(AIBudget, 1)
            if budget is None:
                session.add(
                    AIBudget(
                        budget_id=1,
                        limit_usd=Decimal(str(app_settings.ai_budget_usd)),
                        used_usd=Decimal("0"),
                        reserved_usd=Decimal("0"),
                    )
                )
            else:
                budget.limit_usd = Decimal(str(app_settings.ai_budget_usd))
            session.commit()
            if session.get(Pipeline, "financial-transactions") is None:
                session.add(
                    Pipeline(
                        pipeline_id="financial-transactions",
                        name="Financial Transactions",
                        version=1,
                    )
                )
                session.commit()
            if session.get(PipelineVersion, "financial-transactions:v1") is None:
                session.add(
                    PipelineVersion(
                        pipeline_version_id="financial-transactions:v1",
                        pipeline_id="financial-transactions",
                        version=1,
                        configuration={
                            "required_columns": [
                                "transaction_id",
                                "source_system",
                                "customer_id",
                                "merchant_id",
                                "amount",
                                "currency",
                                "transaction_status",
                                "event_time",
                            ],
                            "duplicate_key": ["source_system", "transaction_id"],
                            "supported_currencies": ["USD", "EUR", "INR"],
                            "reference_data": "datasets/sample/customer_master.csv and merchant_master.csv",
                        },
                    )
                )
                session.commit()
            if session.get(Pipeline, "general-tabular") is None:
                session.add(
                    Pipeline(
                        pipeline_id="general-tabular",
                        name="General Tabular Data",
                        version=1,
                    )
                )
                session.commit()
            if session.get(PipelineVersion, "general-tabular:v1") is None:
                session.add(
                    PipelineVersion(
                        pipeline_version_id="general-tabular:v1",
                        pipeline_id="general-tabular",
                        version=1,
                        configuration={
                            "mode": "general_tabular",
                            "required_columns": [],
                            "duplicate_key": "full normalized row",
                            "ai_schema_inference": "metadata_only_advisory",
                        },
                    )
                )
                session.commit()
        app.state.session_factory = session_factory
        app.state.settings = app_settings
        yield
        engine.dispose()

    app = FastAPI(
        title="DataTrace API",
        version="0.1.0",
        description="Local-first CSV pipeline execution, validation, publishing, and reconciliation.",
        openapi_tags=[
            {"name": "sources", "description": "Upload and inspect source files."},
            {"name": "pipelines", "description": "Available pipeline definitions."},
            {"name": "runs", "description": "Pipeline run execution and evidence."},
            {"name": "quarantine", "description": "Rejected source rows."},
            {"name": "reconciliation", "description": "Count and amount checks."},
            {"name": "audit", "description": "Append-only run audit events."},
        ],
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.session_factory = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_correlation(request: Request, call_next):
        supplied_id = request.headers.get("X-Request-ID", "")
        request_id = supplied_id[:100] if supplied_id else str(uuid.uuid4())
        with bind_request_id(request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return await api_error_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request did not match the required schema.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled API exception", exc_info=exc)
        return await unexpected_error_handler(request, exc)

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/version", tags=["health"])
    def version(request: Request) -> dict[str, str]:
        return {"name": request.app.title, "version": request.app.version}

    app.include_router(api_v1_router)
    return app


app = create_app()
