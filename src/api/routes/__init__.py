"""导出 API 路由对象。"""

from src.api.routes.configuration import configuration_router
from src.api.routes.explore import graph_router, source_router
from src.api.routes.imports import router as imports_router
from src.api.routes.query import chat_router, search_router
from src.api.routes.system import router as system_router

__all__ = [
    "chat_router",
    "configuration_router",
    "graph_router",
    "imports_router",
    "search_router",
    "source_router",
    "system_router",
]
