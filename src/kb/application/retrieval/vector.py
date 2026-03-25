"""基于向量索引的段落检索器。"""

from time import perf_counter

from src.kb.providers import OpenAiGateway
from src.kb.storage import StaleVectorIndexError, VectorIndex
from src.utils.logger import get_logger

from ..services.model import ModelConfigService
from .types import ParagraphHit, RetrievalLaneTrace, RetrievalRequest

logger = get_logger(__name__)


class VectorParagraphRetriever:
    """从语义向量索引中返回段落级命中结果。"""

    def __init__(
        self,
        *,
        model_config_service: ModelConfigService,
        vector_index: VectorIndex,
        openai_gateway: OpenAiGateway,
    ) -> None:
        self.model_config_service = model_config_service
        self.vector = vector_index
        self.gateway = openai_gateway

    def retrieve(
        self,
        request: RetrievalRequest,
        *,
        paragraph_ids: list[str] | None = None,
    ) -> tuple[list[ParagraphHit], RetrievalLaneTrace]:
        """执行向量检索并返回段落命中和轨迹。"""

        start_time = perf_counter()
        normalized_query = str(request.query or "").strip()
        if not normalized_query:
            logger.info("向量检索跳过：问题为空。")
            return [], self._trace(executed=False, skipped_reason="empty_query", start_time=start_time, hits=[])

        embedding_start = perf_counter()
        query_embedding = self.gateway.generate_embeddings([normalized_query])[0]
        embedding_ms = round((perf_counter() - embedding_start) * 1000.0, 2)

        search_start = perf_counter()
        results = self.vector.search(
            model_signature=self.model_config_service.embedding_model_signature(),
            query_embedding=query_embedding,
            limit=max(1, request.top_k),
            source_ids=request.source_ids or None,
            paragraph_ids=paragraph_ids,
        )
        vector_ms = round((perf_counter() - search_start) * 1000.0, 2)

        hits = [
            ParagraphHit(
                paragraph_id=result.paragraph_id,
                source_id=result.source_id,
                score=float(result.similarity),
                rank=index,
                retriever="vector",
                match_type="semantic",
                metadata={
                    "node_id": result.node_id,
                    "knowledge_type": result.knowledge_type,
                    "text": result.text,
                    "distance": float(result.distance),
                },
            )
            for index, result in enumerate(results, start=1)
        ]
        logger.info(
            "向量检索完成：query_length=%s hit_count=%s embed_ms=%s vector_ms=%s source_scope_count=%s paragraph_scope_count=%s",
            len(normalized_query),
            len(hits),
            embedding_ms,
            vector_ms,
            len(request.source_ids or []),
            len(paragraph_ids or []),
        )
        return hits, self._trace(executed=True, skipped_reason=None, start_time=start_time, hits=hits)

    def _trace(
        self,
        *,
        executed: bool,
        skipped_reason: str | None,
        start_time: float,
        hits: list[ParagraphHit],
    ) -> RetrievalLaneTrace:
        """构造向量检索链路的执行轨迹。"""

        return RetrievalLaneTrace(
            executed=executed,
            skipped_reason=skipped_reason,
            hit_count=len(hits),
            latency_ms=round((perf_counter() - start_time) * 1000.0, 2),
            top_paragraph_ids=[hit.paragraph_id for hit in hits[:6]],
        )


__all__ = ["StaleVectorIndexError", "VectorParagraphRetriever"]
