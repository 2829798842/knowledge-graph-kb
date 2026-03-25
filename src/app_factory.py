"""应用启动与 FastAPI 实例构建逻辑。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import create_api_router
from src.config import Settings, get_settings
from src.knowledge_base import build_knowledge_base_container
from src.utils.logging_utils import configure_logging, get_logger
from src.web import register_frontend_routes

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("应用启动：正在构建知识库运行时容器")
    app.state.kb_container = build_knowledge_base_container(settings)
    logger.info("应用启动完成")
    try:
        yield
    finally:
        logger.info("应用关闭完成")


def create_app() -> FastAPI:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_api_router())
    register_frontend_routes(app, frontend_dist_dir=settings.resolved_frontend_dist_dir)
    return app
