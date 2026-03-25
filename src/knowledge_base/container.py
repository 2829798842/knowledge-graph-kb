"""知识库应用服务的运行时容器。"""

from dataclasses import dataclass

from src.config import Settings, ensure_app_dirs
from src.knowledge_base.application.graph_service import GraphService
from src.knowledge_base.application.import_service import ImportExecutor, ImportPipeline, ImportService
from src.knowledge_base.application.model_config_service import ModelConfigService
from src.knowledge_base.application.search_service import SearchService
from src.knowledge_base.application.source_service import SourceService
from src.knowledge_base.infrastructure import (
    GraphRepository,
    ImportJobRepository,
    ModelConfigRepository,
    OpenAiGateway,
    RecordRepository,
    SearchRepository,
    SourceRepository,
    VectorIndex,
)
from src.knowledge_base.infrastructure.sqlite_gateway import SQLiteGateway


@dataclass(slots=True)
class KnowledgeBaseContainer:
    """供 FastAPI 依赖使用的共享运行时对象。"""

    settings: Settings
    gateway: SQLiteGateway
    model_config_repository: ModelConfigRepository
    import_job_repository: ImportJobRepository
    source_repository: SourceRepository
    graph_repository: GraphRepository
    record_repository: RecordRepository
    search_repository: SearchRepository
    vector_index: VectorIndex
    model_config_service: ModelConfigService
    openai_gateway: OpenAiGateway
    search_service: SearchService
    graph_service: GraphService
    source_service: SourceService
    import_service: ImportService


def build_knowledge_base_container(settings: Settings) -> KnowledgeBaseContainer:
    """构建知识库功能的完整运行时依赖图。"""

    ensure_app_dirs(settings)
    gateway = SQLiteGateway(settings.resolved_kb_db_path)
    gateway.initialize()

    model_config_repository = ModelConfigRepository(gateway)
    import_job_repository = ImportJobRepository(gateway)
    source_repository = SourceRepository(gateway)
    graph_repository = GraphRepository(gateway)
    record_repository = RecordRepository(gateway)
    search_repository = SearchRepository(gateway)
    vector_index = VectorIndex(settings.resolved_kb_vector_dir)

    model_config_service = ModelConfigService(
        settings=settings,
        repository=model_config_repository,
        vector_index=vector_index,
    )
    openai_gateway = OpenAiGateway(
        settings=settings,
        runtime_config_provider=model_config_service.resolve_runtime_configuration,
    )
    search_service = SearchService(
        settings=settings,
        model_config_service=model_config_service,
        record_repository=record_repository,
        search_repository=search_repository,
        graph_repository=graph_repository,
        vector_index=vector_index,
        openai_gateway=openai_gateway,
    )
    graph_service = GraphService(
        graph_repository=graph_repository,
        source_repository=source_repository,
    )
    source_service = SourceService(
        source_repository=source_repository,
        search_repository=search_repository,
    )
    pipeline = ImportPipeline(
        settings=settings,
        model_config_service=model_config_service,
        job_repository=import_job_repository,
        source_repository=source_repository,
        graph_repository=graph_repository,
        record_repository=record_repository,
        vector_index=vector_index,
        openai_gateway=openai_gateway,
    )
    executor = ImportExecutor(job_repository=import_job_repository, pipeline=pipeline)
    import_service = ImportService(
        settings=settings,
        job_repository=import_job_repository,
        executor=executor,
    )

    import_job_repository.mark_incomplete_jobs_aborted()

    return KnowledgeBaseContainer(
        settings=settings,
        gateway=gateway,
        model_config_repository=model_config_repository,
        import_job_repository=import_job_repository,
        source_repository=source_repository,
        graph_repository=graph_repository,
        record_repository=record_repository,
        search_repository=search_repository,
        vector_index=vector_index,
        model_config_service=model_config_service,
        openai_gateway=openai_gateway,
        search_service=search_service,
        graph_service=graph_service,
        source_service=source_service,
        import_service=import_service,
    )
