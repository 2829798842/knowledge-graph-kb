"""问答生成服务，负责串联检索、证据整理与模型回答。"""

from time import perf_counter
from typing import Any

from src.config import Settings
from src.kb.common import (
    build_contains_edge_id,
    build_mention_edge_id,
    build_paragraph_node_id,
    build_relation_edge_id,
    build_source_node_id,
)
from src.kb.providers import OpenAiGateway
from src.kb.storage import AnswerReadStore, StaleVectorIndexError
from src.utils.logger import get_logger

from ..retrieval.hybrid import HybridAnswerRetriever
from ..retrieval.types import ParagraphHit, RetrievalLaneTrace, RetrievalRequest, RetrievalTrace

EMPTY_QUERY_MESSAGE = "请输入问题后再查询。"
NO_HIT_MESSAGE = "当前知识库中没有命中相关段落。"
STALE_INDEX_MESSAGE = "当前向量索引与嵌入模型不匹配，请重新导入后再试。"

logger = get_logger(__name__)


class AnswerService:
    """处理问答模式下的检索、证据组织与自然语言生成。"""

    def __init__(
        self,
        *,
        settings: Settings,
        answer_read_store: AnswerReadStore,
        hybrid_answer_retriever: HybridAnswerRetriever,
        openai_gateway: OpenAiGateway,
    ) -> None:
        self.settings = settings
        self.answer_read_store = answer_read_store
        self.hybrid_answer_retriever = hybrid_answer_retriever
        self.gateway = openai_gateway

    def answer(
        self,
        *,
        query: str,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
        top_k: int = 6,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """执行问答主流程并返回回答、证据与检索轨迹。"""

        normalized_query = str(query or "").strip()
        if not normalized_query:
            logger.info("问答跳过：问题为空。")
            return self._empty_response(
                EMPTY_QUERY_MESSAGE,
                status="empty_query",
                execution_message="问题为空，系统未执行检索，也未调用模型。",
            )

        request = RetrievalRequest(
            query=normalized_query,
            source_ids=list(source_ids or []),
            worksheet_names=list(worksheet_names or []),
            top_k=max(1, min(top_k, self.settings.query_context_chunks)),
        )
        try:
            retrieval_result = self.hybrid_answer_retriever.retrieve(request)
        except StaleVectorIndexError:
            logger.warning("问答中止：向量索引与当前嵌入模型不匹配，query_length=%s", len(normalized_query))
            return self._empty_response(
                STALE_INDEX_MESSAGE,
                status="stale_index",
                retrieval_mode="vector",
                execution_message="向量索引失效，系统未调用模型。",
                retrieval_trace=self._empty_trace().to_dict(),
            )

        if not retrieval_result.hits:
            logger.info(
                "问答未命中证据：query_length=%s retrieval_mode=%s",
                len(normalized_query),
                retrieval_result.retrieval_mode,
            )
            return self._empty_response(
                NO_HIT_MESSAGE,
                retrieval_mode=retrieval_result.retrieval_mode,
                execution_message="知识库未命中可用段落，系统未调用模型。",
                retrieval_trace=retrieval_result.trace.to_dict(),
            )

        return self._build_answer_response(
            query=normalized_query,
            hits=retrieval_result.hits,
            retrieval_mode=retrieval_result.retrieval_mode,
            retrieval_trace=retrieval_result.trace,
            conversation_history=conversation_history,
            extra_highlighted_node_ids=retrieval_result.highlighted_node_ids,
            extra_highlighted_edge_ids=retrieval_result.highlighted_edge_ids,
        )

    def _build_answer_response(
        self,
        *,
        query: str,
        hits: list[ParagraphHit],
        retrieval_mode: str,
        retrieval_trace: RetrievalTrace,
        conversation_history: list[dict[str, str]] | None,
        extra_highlighted_node_ids: list[str],
        extra_highlighted_edge_ids: list[str],
    ) -> dict[str, Any]:
        """把检索命中组装成模型上下文，并生成最终回答。"""

        paragraph_ids = [hit.paragraph_id for hit in hits]
        paragraphs = self.answer_read_store.get_paragraphs_with_sources(paragraph_ids)
        paragraph_by_id = {str(row["id"]): row for row in paragraphs}
        entity_links = self.answer_read_store.list_entity_links_for_paragraphs(paragraph_ids)
        relation_links = self.answer_read_store.list_relation_links_for_paragraphs(paragraph_ids)

        entity_links_by_paragraph: dict[str, list[dict[str, Any]]] = {}
        relation_links_by_paragraph: dict[str, list[dict[str, Any]]] = {}
        for link in entity_links:
            entity_links_by_paragraph.setdefault(str(link["paragraph_id"]), []).append(link)
        for link in relation_links:
            relation_links_by_paragraph.setdefault(str(link["paragraph_id"]), []).append(link)

        citations: list[dict[str, Any]] = []
        context_blocks: list[dict[str, str]] = []
        highlighted_node_ids: list[str] = list(extra_highlighted_node_ids)
        highlighted_edge_ids: list[str] = list(extra_highlighted_edge_ids)

        for hit in hits:
            paragraph = paragraph_by_id.get(hit.paragraph_id)
            if paragraph is None:
                continue
            source_id = str(paragraph["source_id"])
            source_name = str(paragraph["source_name"])
            excerpt = str(paragraph["content"])[:420]

            citations.append(
                {
                    "paragraph_id": hit.paragraph_id,
                    "source_id": source_id,
                    "source_name": source_name,
                    "excerpt": excerpt,
                    "score": float(hit.score),
                }
            )
            context_blocks.append({"document_name": source_name, "excerpt": excerpt})

            highlighted_node_ids.extend([build_source_node_id(source_id), build_paragraph_node_id(hit.paragraph_id)])
            highlighted_edge_ids.append(build_contains_edge_id(source_id, hit.paragraph_id))

            for link in entity_links_by_paragraph.get(hit.paragraph_id, []):
                entity_id = str(link["entity_id"])
                highlighted_node_ids.append(f"entity:{entity_id}")
                highlighted_edge_ids.append(build_mention_edge_id(hit.paragraph_id, entity_id))

            for link in relation_links_by_paragraph.get(hit.paragraph_id, []):
                highlighted_edge_ids.append(build_relation_edge_id(str(link["relation_id"])))

        if not citations:
            logger.info("问答停止：检索命中缺少可引用段落，retrieval_mode=%s", retrieval_mode)
            return self._empty_response(
                NO_HIT_MESSAGE,
                retrieval_mode=retrieval_mode,
                execution_message="检索结果为空，系统未调用模型。",
                retrieval_trace=retrieval_trace.to_dict(),
            )

        logger.info(
            "开始生成问答结果：query_length=%s retrieval_mode=%s citation_count=%s history_turn_count=%s",
            len(query),
            retrieval_mode,
            len(citations),
            len(conversation_history or []),
        )
        llm_start = perf_counter()
        answer_text = self.gateway.generate_answer(
            query,
            context_blocks,
            conversation_turns=conversation_history or None,
        )
        llm_ms = round((perf_counter() - llm_start) * 1000.0, 2)
        total_ms = round(retrieval_trace.total_ms + llm_ms, 2)

        logger.info(
            "问答完成：retrieval_mode=%s citation_count=%s llm_ms=%s total_ms=%s",
            retrieval_mode,
            len(citations),
            llm_ms,
            total_ms,
        )

        return {
            "answer": answer_text,
            "citations": citations,
            "highlighted_node_ids": self._deduplicate(highlighted_node_ids),
            "highlighted_edge_ids": self._deduplicate(highlighted_edge_ids),
            "execution": self._build_execution(
                status="answered",
                retrieval_mode=retrieval_mode,
                model_invoked=True,
                matched_paragraph_count=len(citations),
                message=f"系统命中 {len(citations)} 条证据并已生成回答。",
            ),
            "retrieval_trace": retrieval_trace.to_dict(),
        }

    def _build_execution(
        self,
        *,
        status: str,
        retrieval_mode: str,
        model_invoked: bool,
        matched_paragraph_count: int,
        message: str,
    ) -> dict[str, Any]:
        """构造前端展示用的问答执行摘要。"""

        return {
            "status": status,
            "retrieval_mode": retrieval_mode,
            "model_invoked": model_invoked,
            "matched_paragraph_count": matched_paragraph_count,
            "message": message,
        }

    def _empty_response(
        self,
        message: str,
        *,
        status: str = "no_hit",
        retrieval_mode: str = "none",
        execution_message: str | None = None,
        retrieval_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构造未命中或未执行模型时的标准返回结构。"""

        return {
            "answer": message,
            "citations": [],
            "highlighted_node_ids": [],
            "highlighted_edge_ids": [],
            "execution": self._build_execution(
                status=status,
                retrieval_mode=retrieval_mode,
                model_invoked=False,
                matched_paragraph_count=0,
                message=execution_message or message,
            ),
            "retrieval_trace": retrieval_trace or self._empty_trace().to_dict(),
        }

    def _empty_trace(self) -> RetrievalTrace:
        """构造所有链路均未执行时的空检索轨迹。"""

        lane = RetrievalLaneTrace(
            executed=False,
            skipped_reason="not_executed",
            hit_count=0,
            latency_ms=0.0,
            top_paragraph_ids=[],
        )
        return RetrievalTrace(structured=lane, vector=lane, fusion=lane, ppr=lane, total_ms=0.0)

    def _deduplicate(self, values: list[str]) -> list[str]:
        """按首次出现顺序去重节点或边 ID。"""

        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
