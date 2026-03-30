"""知识库运行时对象的依赖注入容器。"""

from dataclasses import dataclass

from src.config import Settings, ensure_app_dirs
from src.kb.application.imports import ImportExecutor, ImportPipeline, ImportService
from src.kb.application.retrieval import GraphReranker, HybridAnswerRetriever, StructuredParagraphRetriever, VectorParagraphRetriever
from src.kb.application.search import EntitySearchService, RecordSearchService, RelationSearchService, SourceSearchService
from src.kb.application.services import (
    AnswerService,
    ConversationService,
    GraphService,
    MaintenanceService,
    ModelConfigService,
    SourceService,
)
from src.kb.database import SQLiteGateway
from src.kb.providers import OpenAiGateway
from src.kb.storage import (
    AnswerReadStore,
    ConversationStore,
    EntitySearchStore,
    GraphStore,
    ImportJobStore,
    ModelConfigStore,
    RecordStore,
    RelationSearchStore,
    SourceSearchStore,
    SourceStore,
    VectorIndex,
)


@dataclass(slots=True)
class KnowledgeBaseContainer:
    """聚合知识库运行时依赖，供 FastAPI 与应用服务统一访问。"""

    settings: Settings
    gateway: SQLiteGateway
    model_config_store: ModelConfigStore
    import_job_store: ImportJobStore
    conversation_store: ConversationStore
    source_store: SourceStore
    graph_store: GraphStore
    record_store: RecordStore
    answer_read_store: AnswerReadStore
    entity_search_store: EntitySearchStore
    relation_search_store: RelationSearchStore
    source_search_store: SourceSearchStore
    vector_index: VectorIndex
    model_config_service: ModelConfigService
    openai_gateway: OpenAiGateway
    answer_service: AnswerService
    record_search_service: RecordSearchService
    entity_search_service: EntitySearchService
    relation_search_service: RelationSearchService
    source_search_service: SourceSearchService
    conversation_service: ConversationService
    graph_service: GraphService
    source_service: SourceService
    maintenance_service: MaintenanceService
    import_service: ImportService


def build_knowledge_base_container(settings: Settings) -> KnowledgeBaseContainer:
    """构建并返回知识库运行时依赖集合。"""

    ensure_app_dirs(settings)
    gateway = SQLiteGateway(settings.resolved_kb_db_path)
    gateway.initialize()

    model_config_store = ModelConfigStore(gateway)
    import_job_store = ImportJobStore(gateway)
    conversation_store = ConversationStore(gateway)
    source_store = SourceStore(gateway)
    graph_store = GraphStore(gateway)
    record_store = RecordStore(gateway)
    answer_read_store = AnswerReadStore(gateway)
    entity_search_store = EntitySearchStore(gateway)
    relation_search_store = RelationSearchStore(gateway)
    source_search_store = SourceSearchStore(gateway)
    vector_index = VectorIndex(settings.resolved_kb_vector_dir)

    model_config_service = ModelConfigService(
        settings=settings,
        store=model_config_store,
        vector_index=vector_index,
    )
    openai_gateway = OpenAiGateway(
        settings=settings,
        runtime_config_provider=model_config_service.resolve_runtime_configuration,
    )
    structured_retriever = StructuredParagraphRetriever(record_store=record_store)
    vector_retriever = VectorParagraphRetriever(
        model_config_service=model_config_service,
        vector_index=vector_index,
        openai_gateway=openai_gateway,
    )
    graph_reranker = GraphReranker(answer_read_store=answer_read_store)
    hybrid_answer_retriever = HybridAnswerRetriever(
        settings=settings,
        record_store=record_store,
        structured_retriever=structured_retriever,
        vector_retriever=vector_retriever,
        graph_reranker=graph_reranker,
    )
    answer_service = AnswerService(
        settings=settings,
        answer_read_store=answer_read_store,
        record_store=record_store,
        hybrid_answer_retriever=hybrid_answer_retriever,
        openai_gateway=openai_gateway,
    )
    record_search_service = RecordSearchService(
        record_store=record_store,
        structured_retriever=structured_retriever,
        vector_retriever=vector_retriever,
    )
    entity_search_service = EntitySearchService(entity_search_store=entity_search_store)
    relation_search_service = RelationSearchService(relation_search_store=relation_search_store)
    source_search_service = SourceSearchService(source_search_store=source_search_store)
    conversation_service = ConversationService(
        settings=settings,
        store=conversation_store,
        answer_service=answer_service,
    )
    graph_service = GraphService(
        graph_store=graph_store,
        source_store=source_store,
        vector_index=vector_index,
    )
    source_service = SourceService(source_store=source_store)
    maintenance_service = MaintenanceService(
        settings=settings,
        gateway=gateway,
        source_store=source_store,
        graph_store=graph_store,
        vector_index=vector_index,
        model_config_service=model_config_service,
        openai_gateway=openai_gateway,
    )
    pipeline = ImportPipeline(
        settings=settings,
        model_config_service=model_config_service,
        job_store=import_job_store,
        source_store=source_store,
        graph_store=graph_store,
        record_store=record_store,
        vector_index=vector_index,
        openai_gateway=openai_gateway,
    )
    executor = ImportExecutor(job_store=import_job_store, pipeline=pipeline)
    import_service = ImportService(
        settings=settings,
        job_store=import_job_store,
        executor=executor,
    )

    import_job_store.mark_incomplete_jobs_aborted()

    return KnowledgeBaseContainer(
        settings=settings,
        gateway=gateway,
        model_config_store=model_config_store,
        import_job_store=import_job_store,
        conversation_store=conversation_store,
        source_store=source_store,
        graph_store=graph_store,
        record_store=record_store,
        answer_read_store=answer_read_store,
        entity_search_store=entity_search_store,
        relation_search_store=relation_search_store,
        source_search_store=source_search_store,
        vector_index=vector_index,
        model_config_service=model_config_service,
        openai_gateway=openai_gateway,
        answer_service=answer_service,
        record_search_service=record_search_service,
        entity_search_service=entity_search_service,
        relation_search_service=relation_search_service,
        source_search_service=source_search_service,
        conversation_service=conversation_service,
        graph_service=graph_service,
        source_service=source_service,
        maintenance_service=maintenance_service,
        import_service=import_service,
    )
