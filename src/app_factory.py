"""模块名称：app_factory

主要功能：按应用工厂模式创建 FastAPI 实例并组装 API、生命周期与前端静态资源。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import create_api_router
from src.config import Settings, ensure_app_dirs, get_settings
from src.data import init_db
from src.web import register_frontend_routes


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """定义应用生命周期。

    Args:
        _app: FastAPI 应用实例。

    Yields:
        None: 生命周期上下文。
    """

    settings: Settings = get_settings()
    ensure_app_dirs(settings)
    init_db()
    yield


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。

    Returns:
        FastAPI: 已挂载路由、中间件和前端静态资源的应用实例。
    """

    settings: Settings = get_settings()
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
