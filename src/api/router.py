"""聚合所有路由并向外提供统一的应用路由入口。
"""

from fastapi import APIRouter

from src.api.routes import document_router, graph_router, model_config_router, query_router, system_router


def create_api_router() -> APIRouter:
    """创建应用总路由。

    Returns:
        APIRouter: 已注册全部子路由的总路由对象。
    """

    router = APIRouter()
    router.include_router(system_router)
    router.include_router(document_router)
    router.include_router(graph_router)
    router.include_router(model_config_router)
    router.include_router(query_router)
    return router
