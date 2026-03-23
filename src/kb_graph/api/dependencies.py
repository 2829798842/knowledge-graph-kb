"""模块名称：api.dependencies

主要功能：统一封装 FastAPI 依赖注入所需的服务构造逻辑。
"""

from kb_graph.config import get_settings
from kb_graph.services.entity_extraction_service import EntityExtractionService
from kb_graph.services.ingestion_service import IngestionService
from kb_graph.services.openai_service import OpenAiService
from kb_graph.services.query_service import QueryService
from kb_graph.services.vector_store_service import LanceDbVectorStore


def get_ingestion_service() -> IngestionService:
    """构造文档导入服务。

    Returns:
        IngestionService: 已注入配置与依赖的导入服务实例。
    """

    settings = get_settings()
    openai_service = OpenAiService(settings)
    return IngestionService(
        settings=settings,
        openai_service=openai_service,
        entity_extraction_service=EntityExtractionService(openai_service=openai_service),
        vector_store=LanceDbVectorStore(settings),
    )


def get_query_service() -> QueryService:
    """构造问答检索服务。

    Returns:
        QueryService: 已注入配置与依赖的问答检索服务实例。
    """

    settings = get_settings()
    return QueryService(
        settings=settings,
        openai_service=OpenAiService(settings),
        vector_store=LanceDbVectorStore(settings),
    )
