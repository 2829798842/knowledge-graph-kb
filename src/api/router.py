"""聚合顶层 API 路由。"""

from fastapi import APIRouter

from src.api.routes import (
    chat_router,
    configuration_router,
    graph_router,
    imports_router,
    search_router,
    source_router,
    system_router,
)


def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(system_router)
    router.include_router(configuration_router)
    router.include_router(imports_router)
    router.include_router(chat_router)
    router.include_router(search_router)
    router.include_router(graph_router)
    router.include_router(source_router)
    return router
