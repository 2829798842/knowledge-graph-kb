"""聚合顶层 API 路由。"""

from fastapi import APIRouter

from src.api.routes import (
    kb_graph_router,
    kb_import_router,
    kb_search_router,
    kb_source_router,
    model_config_router,
    system_router,
)


def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(system_router)
    router.include_router(model_config_router)
    router.include_router(kb_import_router)
    router.include_router(kb_search_router)
    router.include_router(kb_graph_router)
    router.include_router(kb_source_router)
    return router
