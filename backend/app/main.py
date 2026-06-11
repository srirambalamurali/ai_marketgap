import time
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.utils.logging import setup_logging, get_logger
from app.api.health import router as health_router
from app.api.dashboard import router as dashboard_router
from app.api.collect import router as collect_router
from app.api.github import router as github_router
from app.api.signals import router as signals_router
from app.api.trends import router as trends_router
from app.api.opportunities import router as opportunities_router
from app.api.rag import router as rag_router
from app.api.workflow import router as workflow_router
from app.api.reports import router as reports_router
from app.api.reports import legacy_router as legacy_reports_router
from app.api.top_opportunities import router as top_opp_router
from app.api.collect_signals import router as collect_signals_router
from app.api.signal_stats import router as signal_stats_router
from app.api.monitoring import router as monitoring_router
from app.api.debug import router as debug_router
from app.api.auth import router as auth_router
from app.database.postgres import engine
from app.database.validation import (
    validate_postgres,
    validate_gemini_key,
    validate_github_token,
    validate_reddit_credentials,
    validate_chroma,
)
from app.database.repair import (
    ensure_collected_documents_schema,
    ensure_generated_reports_schema,
    ensure_market_signals_schema,
    ensure_startup_opportunities_schema,
)
from app.scheduler.jobs import start_scheduler, shutdown_scheduler
import app.models.collected_document  # noqa: F401
import app.models.user  # noqa: F401

import app.models.market_signal  # noqa: F401 — ensure model is registered
import app.models.generated_report  # noqa: F401 — ensure model is registered


async def _create_tables() -> None:
    from app.database.postgres import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging()
    logger = get_logger("app.main")
    logger.info("Starting %s (debug=%s)", settings.app_name, settings.debug)

    is_test_runtime = bool(os.getenv("PYTEST_CURRENT_TEST"))

    logger.info("Running startup validation ...")
    if settings.demo_mode:
        logger.warning("Demo mode enabled: skipping optional external-service validation")
    else:
        validate_gemini_key()
        validate_github_token()
    try:
        validate_reddit_credentials()
        app.state.reddit_oauth_configured = True
    except RuntimeError as exc:
        app.state.reddit_oauth_configured = False
        logger.warning("Reddit OAuth not configured: %s", exc)
    app.state.rag_health = await validate_chroma()
    if not is_test_runtime:
        await validate_postgres()
        await ensure_market_signals_schema()
        await ensure_collected_documents_schema()
        await ensure_generated_reports_schema()
        await ensure_startup_opportunities_schema()
        logger.info("All startup validations passed")

        logger.info("Ensuring database tables exist ...")
        await _create_tables()
        logger.info("Database tables ready")
    else:
        logger.info("Test runtime detected: skipping live schema repair and table creation")

    if not settings.demo_mode:
        start_scheduler()
        logger.info("Scheduler started")
    else:
        logger.info("Demo mode: scheduler not started")

    yield

    if not settings.demo_mode:
        shutdown_scheduler()
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def latency_middleware(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        latency_ms = (time.time() - start) * 1000
        try:
            from app.services.monitoring import api_tracker
            api_tracker.record(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency_ms,
            )
        except Exception:
            pass
        return response

    prefix = settings.api_v1_prefix
    app.include_router(health_router, prefix=prefix)
    app.include_router(dashboard_router, prefix=prefix)
    app.include_router(collect_router, prefix=prefix)
    app.include_router(github_router, prefix=prefix)
    app.include_router(signals_router, prefix=prefix)
    app.include_router(trends_router, prefix=prefix)
    app.include_router(opportunities_router, prefix=prefix)
    app.include_router(rag_router, prefix=prefix)
    app.include_router(workflow_router, prefix=prefix)
    app.include_router(reports_router, prefix=prefix)
    app.include_router(legacy_reports_router, prefix=prefix)
    app.include_router(top_opp_router, prefix=prefix)
    app.include_router(collect_signals_router, prefix=prefix)
    app.include_router(signal_stats_router, prefix=prefix)
    app.include_router(monitoring_router, prefix=prefix)
    app.include_router(debug_router, prefix=prefix)
    app.include_router(auth_router, prefix=prefix)

    return app


app = create_app()
