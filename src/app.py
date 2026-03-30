"""FastAPI application factory and lifespan wiring."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import create_api_router
from src.api.errors import register_error_handlers
from src.config import Settings, get_settings
from src.kb import build_knowledge_base_container
from src.utils.logger import configure_logging, get_logger
from src.web import register_frontend_routes

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and release shared runtime resources."""

    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "Application startup: initializing knowledge-base container. data_dir=%s frontend_dist=%s",
        settings.resolved_kb_data_dir,
        settings.resolved_frontend_dist_dir,
    )
    app.state.kb_container = build_knowledge_base_container(settings)
    logger.info("Application startup complete.")
    try:
        yield
    finally:
        logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "Creating FastAPI app. name=%s host=%s port=%s",
        settings.app_name,
        settings.server_host,
        settings.server_port,
    )
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(create_api_router())
    register_frontend_routes(app, frontend_dist_dir=settings.resolved_frontend_dist_dir)
    logger.info("Routes registered successfully.")
    return app
