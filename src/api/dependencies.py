"""模块名称：api.dependencies

主要功能：统一封装 FastAPI 依赖注入所需的服务构造逻辑。
"""

from src.config import get_settings
from src.services import (
    EntityExtractionService,
    FaissVectorStore,
    IngestionService,
    ModelConfigurationService,
    OpenAiService,
    QueryService,
)


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
        vector_store=FaissVectorStore(settings),
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
        vector_store=FaissVectorStore(settings),
    )


def get_model_config_service() -> ModelConfigurationService:
    """Construct the model configuration service."""

    settings = get_settings()
    return ModelConfigurationService(settings)
