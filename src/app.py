"""应用启动入口与 FastAPI 实例构建逻辑。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import create_api_router
from src.config import Settings, get_settings
from src.kb import build_knowledge_base_container
from src.utils.logger import configure_logging, get_logger
from src.web import register_frontend_routes

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用启动与关闭时的共享资源生命周期。"""

    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "应用启动：开始初始化知识库运行时容器，数据目录=%s，前端目录=%s",
        settings.resolved_kb_data_dir,
        settings.resolved_frontend_dist_dir,
    )
    app.state.kb_container = build_knowledge_base_container(settings)
    logger.info("应用启动完成：知识库容器已就绪")
    try:
        yield
    finally:
        logger.info("应用关闭完成：知识库资源已释放")


def create_app() -> FastAPI:
    """创建并返回 FastAPI 应用实例。"""

    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "创建 FastAPI 应用：app_name=%s host=%s port=%s",
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
    app.include_router(create_api_router())
    register_frontend_routes(app, frontend_dist_dir=settings.resolved_frontend_dist_dir)
    logger.info("应用路由注册完成")
    return app
