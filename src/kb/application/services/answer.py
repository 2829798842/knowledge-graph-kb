"""问答服务"""

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
from src.kb.importing.evidence import (
    RENDER_KIND_ROW_RECORD,
    RENDER_KIND_SHEET_SUMMARY,
    RENDER_KIND_TEXT,
    build_paragraph_render_payload,
)
from src.kb.providers import OpenAiGateway
from src.kb.storage import AnswerReadStore, RecordStore, StaleVectorIndexError
from src.utils.logger import get_logger

from ..retrieval.hybrid import HybridAnswerRetriever
from ..retrieval.types import ParagraphHit, RetrievalLaneTrace, RetrievalRequest, RetrievalTrace

EMPTY_QUERY_MESSAGE = "请输入问题后再查询。"
NO_HIT_MESSAGE = "当前知识库中没有命中相关段落。"
STALE_INDEX_MESSAGE = "当前向量索引与嵌入模型不匹配，请重新导入后再试。"
logger = get_logger(__name__)


class AnswerService:
    """处理问答检索 证据整形 与模型回答"""

    def __init__(
        self,
        *,
        settings: Settings,
        answer_read_store: AnswerReadStore,
        record_store: RecordStore,
        hybrid_answer_retriever: HybridAnswerRetriever,
        openai_gateway: OpenAiGateway,
    ) -> None:
        self.settings = settings
        self.answer_read_store = answer_read_store
        self.record_store = record_store
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
        normalized_query = str(query or "").strip()
        logger.debug(
            "问答请求开始：query_length=%s source_count=%s worksheet_count=%s top_k=%s history_turn_count=%s",
            len(normalized_query),
            len(source_ids or []),
            len(worksheet_names or []),
            top_k,
            len(conversation_history or []),
        )
        if not normalized_query:
            logger.info("Answer skipped because query is empty.")
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
            logger.warning(
                "Answer aborted because the vector index is stale: query_length=%s",
                len(normalized_query),
            )
            return self._empty_response(
                STALE_INDEX_MESSAGE,
                status="stale_index",
                retrieval_mode="vector",
                execution_message="向量索引失效，系统未调用模型。",
                retrieval_trace=self._empty_trace().to_dict(),
            )
        logger.debug(
            "问答检索完成：retrieval_mode=%s hit_count=%s total_ms=%s structured_hits=%s vector_hits=%s ppr_hits=%s",
            retrieval_result.retrieval_mode,
            len(retrieval_result.hits),
            retrieval_result.trace.total_ms,
            retrieval_result.trace.structured.hit_count,
            retrieval_result.trace.vector.hit_count,
            retrieval_result.trace.ppr.hit_count,
        )

        if not retrieval_result.hits:
            logger.info(
                "Answer found no usable paragraphs: query_length=%s retrieval_mode=%s",
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

    def hydrate_citations(self, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not citations:
            return []
        logger.debug("开始补全问答引用渲染：citation_count=%s", len(citations))
        paragraph_ids = [
            str(item.get("paragraph_id") or "").strip()
            for item in citations
            if str(item.get("paragraph_id") or "").strip()
        ]
        if not paragraph_ids:
            return [self._with_render_defaults(dict(item)) for item in citations]

        paragraphs = self.answer_read_store.get_paragraphs_with_sources(paragraph_ids)
        paragraph_by_id = {str(row["id"]): row for row in paragraphs}
        record_rows_by_paragraph, worksheet_rows_by_ref = self._load_render_context(paragraph_ids)
        logger.debug(
            "问答引用渲染上下文已加载：citation_count=%s paragraph_count=%s record_row_count=%s worksheet_window_count=%s",
            len(citations),
            len(paragraphs),
            len(record_rows_by_paragraph),
            len(worksheet_rows_by_ref),
        )

        hydrated: list[dict[str, Any]] = []
        for item in citations:
            citation = dict(item)
            paragraph_id = str(citation.get("paragraph_id") or "").strip()
            paragraph = paragraph_by_id.get(paragraph_id)
            if paragraph is None:
                hydrated.append(self._with_render_defaults(citation))
                continue
            record_row = record_rows_by_paragraph.get(paragraph_id)
            worksheet_rows = self._worksheet_rows_for_record(record_row, worksheet_rows_by_ref)
            excerpt = str(paragraph.get("content") or "")[:420]
            hydrated.append(
                {
                    **citation,
                    "source_id": str(paragraph.get("source_id") or citation.get("source_id") or ""),
                    "source_name": str(paragraph.get("source_name") or citation.get("source_name") or ""),
                    "excerpt": excerpt or str(citation.get("excerpt") or ""),
                    **build_paragraph_render_payload(
                        paragraph=paragraph,
                        worksheet_rows=worksheet_rows,
                        highlighted_columns=list(
                            dict(citation.get("render_metadata") or {}).get("highlighted_columns") or []
                        ),
                    ),
                }
            )
        logger.debug("问答引用渲染补全完成：citation_count=%s", len(hydrated))
        return hydrated

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
        paragraph_ids = [hit.paragraph_id for hit in hits]
        paragraphs = self.answer_read_store.get_paragraphs_with_sources(paragraph_ids)
        paragraph_by_id = {str(row["id"]): row for row in paragraphs}
        entity_links = self.answer_read_store.list_entity_links_for_paragraphs(paragraph_ids)
        relation_links = self.answer_read_store.list_relation_links_for_paragraphs(paragraph_ids)
        logger.debug(
            "问答结果整形开始：paragraph_id_count=%s paragraph_count=%s entity_link_count=%s relation_link_count=%s",
            len(paragraph_ids),
            len(paragraphs),
            len(entity_links),
            len(relation_links),
        )
        entity_links_by_paragraph: dict[str, list[dict[str, Any]]] = {}
        relation_links_by_paragraph: dict[str, list[dict[str, Any]]] = {}
        for link in entity_links:
            entity_links_by_paragraph.setdefault(str(link["paragraph_id"]), []).append(link)
        for link in relation_links:
            relation_links_by_paragraph.setdefault(str(link["paragraph_id"]), []).append(link)

        record_rows_by_paragraph, worksheet_rows_by_ref = self._load_render_context(paragraph_ids)
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
            record_row = record_rows_by_paragraph.get(hit.paragraph_id)
            worksheet_rows = self._worksheet_rows_for_record(record_row, worksheet_rows_by_ref)
            matched_columns = [
                str(value)
                for value in list(hit.metadata.get("matched_cells") or [])
                if str(value).strip()
            ]
            logger.debug(
                "处理问答命中段落：paragraph_id=%s score=%s retriever=%s match_type=%s matched_column_count=%s worksheet_window_row_count=%s",
                hit.paragraph_id,
                hit.score,
                hit.retriever,
                hit.match_type,
                len(matched_columns),
                len(worksheet_rows),
            )

            citations.append(
                {
                    "paragraph_id": hit.paragraph_id,
                    "source_id": source_id,
                    "source_name": source_name,
                    "excerpt": excerpt,
                    "score": float(hit.score),
                    **build_paragraph_render_payload(
                        paragraph=paragraph,
                        worksheet_rows=worksheet_rows,
                        highlighted_columns=matched_columns,
                    ),
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
            logger.info(
                "Answer stopped because no paragraphs could be shaped into citations: retrieval_mode=%s",
                retrieval_mode,
            )
            return self._empty_response(
                NO_HIT_MESSAGE,
                retrieval_mode=retrieval_mode,
                execution_message="检索结果为空，系统未调用模型。",
                retrieval_trace=retrieval_trace.to_dict(),
            )
        logger.debug(
            "问答证据整形完成：citation_count=%s context_block_count=%s highlighted_node_count=%s highlighted_edge_count=%s",
            len(citations),
            len(context_blocks),
            len(highlighted_node_ids),
            len(highlighted_edge_ids),
        )

        logger.info(
            "Generating answer: query_length=%s retrieval_mode=%s citation_count=%s history_turn_count=%s",
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
            "Answer completed: retrieval_mode=%s citation_count=%s llm_ms=%s total_ms=%s",
            retrieval_mode,
            len(citations),
            llm_ms,
            total_ms,
        )
        logger.debug(
            "问答完成详情：answer_length=%s highlighted_node_count=%s highlighted_edge_count=%s",
            len(answer_text),
            len(highlighted_node_ids),
            len(highlighted_edge_ids),
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

    def _load_render_context(
        self,
        paragraph_ids: list[str],
    ) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, int], list[dict[str, Any]]]]:
        record_rows_by_paragraph = self.record_store.list_rows_by_paragraph_ids(paragraph_ids)
        row_windows = [
            (
                str(row.get("source_id") or ""),
                str(row.get("worksheet_key") or row.get("worksheet_name") or ""),
                int(row.get("row_index") or 0),
            )
            for row in record_rows_by_paragraph.values()
            if str(row.get("source_id") or "").strip()
            and str(row.get("worksheet_key") or row.get("worksheet_name") or "").strip()
            and int(row.get("row_index") or 0) > 0
        ]
        worksheet_rows_by_ref = self.record_store.list_rows_in_windows(row_windows, radius=1)
        logger.debug(
            "问答表格渲染上下文加载完成：paragraph_id_count=%s record_row_count=%s window_request_count=%s worksheet_window_count=%s",
            len(paragraph_ids),
            len(record_rows_by_paragraph),
            len(row_windows),
            len(worksheet_rows_by_ref),
        )
        return record_rows_by_paragraph, worksheet_rows_by_ref

    def _worksheet_rows_for_record(
        self,
        record_row: dict[str, Any] | None,
        worksheet_rows_by_ref: dict[tuple[str, str, int], list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if record_row is None:
            return []
        ref = (
            str(record_row.get("source_id") or ""),
            str(record_row.get("worksheet_key") or record_row.get("worksheet_name") or ""),
            int(record_row.get("row_index") or 0),
        )
        return list(worksheet_rows_by_ref.get(ref, []))

    def _with_render_defaults(self, citation: dict[str, Any]) -> dict[str, Any]:
        render_kind = str(citation.get("render_kind") or RENDER_KIND_TEXT)
        if render_kind not in {RENDER_KIND_TEXT, RENDER_KIND_ROW_RECORD, RENDER_KIND_SHEET_SUMMARY}:
            render_kind = RENDER_KIND_TEXT
        return {
            **citation,
            "render_kind": render_kind,
            "rendered_html": citation.get("rendered_html"),
            "render_metadata": dict(citation.get("render_metadata") or {}),
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
        lane = RetrievalLaneTrace(
            executed=False,
            skipped_reason="not_executed",
            hit_count=0,
            latency_ms=0.0,
            top_paragraph_ids=[],
        )
        return RetrievalTrace(structured=lane, vector=lane, fusion=lane, ppr=lane, total_ms=0.0)

    def _deduplicate(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
