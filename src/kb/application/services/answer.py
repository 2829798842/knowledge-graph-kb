"""Answer service."""

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

EMPTY_QUERY_MESSAGE = "请输入问题后再发起问答。"
NO_HIT_MESSAGE = "知识库中没有找到相关段落。"
STALE_INDEX_MESSAGE = "向量索引与当前嵌入模型不一致，请重新导入后再试。"
logger = get_logger(__name__)


class AnswerService:
    """Coordinate retrieval, evidence shaping, and answer generation."""

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
            "Answer request started: query_length=%s source_count=%s worksheet_count=%s top_k=%s history_turn_count=%s",
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
                execution_message="问题为空，系统已跳过检索和生成。",
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
                execution_message="向量索引已失效，系统已跳过模型生成。",
                retrieval_trace=self._empty_trace().to_dict(),
            )
        logger.debug(
            "Answer retrieval finished: retrieval_mode=%s hit_count=%s total_ms=%s structured_hits=%s vector_hits=%s ppr_hits=%s",
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
                execution_message="没有找到可用段落，系统已跳过模型生成。",
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
        logger.debug("Hydrating citations: citation_count=%s", len(citations))
        paragraph_ids = [
            str(item.get("paragraph_id") or "").strip()
            for item in citations
            if str(item.get("paragraph_id") or "").strip()
        ]
        if not paragraph_ids:
            return [self._with_render_defaults(dict(item)) for item in citations]

        paragraphs = self.answer_read_store.get_paragraphs_with_sources(paragraph_ids)
        paragraph_by_id = {str(row["id"]): row for row in paragraphs}
        entity_links = self.answer_read_store.list_entity_links_for_paragraphs(paragraph_ids)
        entity_links_by_paragraph: dict[str, list[dict[str, Any]]] = {}
        for link in entity_links:
            entity_links_by_paragraph.setdefault(str(link["paragraph_id"]), []).append(link)
        record_rows_by_paragraph, worksheet_rows_by_ref = self._load_render_context(paragraph_ids)
        logger.debug(
            "Citation hydration context loaded: citation_count=%s paragraph_count=%s entity_link_count=%s record_row_count=%s worksheet_window_count=%s",
            len(citations),
            len(paragraphs),
            len(entity_links),
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
            anchor_node_ids = self._normalize_anchor_node_ids(
                citation.get("anchor_node_ids"),
                fallback=self._citation_anchor_node_ids(entity_links_by_paragraph.get(paragraph_id, [])),
            )
            preferred_anchor_node_id = self._preferred_anchor_node_id(
                citation.get("preferred_anchor_node_id"),
                anchor_node_ids=anchor_node_ids,
            )
            render_payload = build_paragraph_render_payload(
                paragraph=paragraph,
                worksheet_rows=worksheet_rows,
                highlighted_columns=list(
                    dict(citation.get("render_metadata") or {}).get("highlighted_columns") or []
                ),
            )
            hydrated.append(
                {
                    **citation,
                    "source_id": str(paragraph.get("source_id") or citation.get("source_id") or ""),
                    "source_name": str(paragraph.get("source_name") or citation.get("source_name") or ""),
                    "source_kind": str(
                        paragraph.get("source_kind") or citation.get("source_kind") or ""
                    )
                    or None,
                    "worksheet_name": self._worksheet_name_from_payload(
                        paragraph,
                        render_payload,
                        citation,
                    ),
                    "page_number": self._optional_int(
                        dict(paragraph.get("metadata") or {}).get("page_number")
                        or dict(render_payload.get("render_metadata") or {}).get("page_number")
                        or citation.get("page_number")
                    ),
                    "paragraph_position": self._optional_int(
                        paragraph.get("position") or citation.get("paragraph_position")
                    ),
                    "winning_lane": str(citation.get("winning_lane") or "").strip() or None,
                    "anchor_node_ids": anchor_node_ids,
                    "preferred_anchor_node_id": preferred_anchor_node_id,
                    "matched_fields": self._normalize_string_list(
                        citation.get("matched_fields")
                        or dict(render_payload.get("render_metadata") or {}).get("highlighted_columns")
                    ),
                    "excerpt": excerpt or str(citation.get("excerpt") or ""),
                    **render_payload,
                }
            )
        logger.debug("Citation hydration finished: citation_count=%s", len(hydrated))
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
            "Shaping answer result: paragraph_id_count=%s paragraph_count=%s entity_link_count=%s relation_link_count=%s",
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
            anchor_node_ids = self._citation_anchor_node_ids(
                entity_links_by_paragraph.get(hit.paragraph_id, []),
            )
            logger.debug(
                "Processing answer hit paragraph: paragraph_id=%s score=%s retriever=%s match_type=%s matched_column_count=%s worksheet_window_row_count=%s",
                hit.paragraph_id,
                hit.score,
                hit.retriever,
                hit.match_type,
                len(matched_columns),
                len(worksheet_rows),
            )

            render_payload = build_paragraph_render_payload(
                paragraph=paragraph,
                worksheet_rows=worksheet_rows,
                highlighted_columns=matched_columns,
            )
            citations.append(
                {
                    "paragraph_id": hit.paragraph_id,
                    "source_id": source_id,
                    "source_name": source_name,
                    "excerpt": excerpt,
                    "score": float(hit.score),
                    "match_reason": self._citation_match_reason(
                        retriever=hit.retriever,
                        match_type=hit.match_type,
                    ),
                    "matched_fields": self._normalize_string_list(matched_columns),
                    "source_kind": str(paragraph.get("source_kind") or "").strip() or None,
                    "worksheet_name": self._worksheet_name_from_payload(paragraph, render_payload),
                    "page_number": self._optional_int(
                        dict(paragraph.get("metadata") or {}).get("page_number")
                        or dict(render_payload.get("render_metadata") or {}).get("page_number")
                    ),
                    "paragraph_position": self._optional_int(paragraph.get("position")),
                    "winning_lane": str(hit.retriever or "").strip() or None,
                    "anchor_node_ids": anchor_node_ids,
                    "preferred_anchor_node_id": self._preferred_anchor_node_id(
                        None,
                        anchor_node_ids=anchor_node_ids,
                    ),
                    **render_payload,
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
                execution_message="没有找到可用段落，系统已跳过模型生成。",
                retrieval_trace=retrieval_trace.to_dict(),
            )
        logger.debug(
            "Answer evidence shaped: citation_count=%s context_block_count=%s highlighted_node_count=%s highlighted_edge_count=%s",
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
            "Answer details: answer_length=%s highlighted_node_count=%s highlighted_edge_count=%s",
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
                message=f"系统已基于 {len(citations)} 条证据生成回答。",
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
            "Table render context loaded: paragraph_id_count=%s record_row_count=%s window_request_count=%s worksheet_window_count=%s",
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
            "match_reason": str(citation.get("match_reason") or "").strip() or None,
            "matched_fields": self._normalize_string_list(citation.get("matched_fields")),
            "source_kind": str(citation.get("source_kind") or "").strip() or None,
            "worksheet_name": str(citation.get("worksheet_name") or "").strip() or None,
            "page_number": self._optional_int(citation.get("page_number")),
            "paragraph_position": self._optional_int(citation.get("paragraph_position")),
            "winning_lane": str(citation.get("winning_lane") or "").strip() or None,
            "anchor_node_ids": self._normalize_anchor_node_ids(citation.get("anchor_node_ids")),
            "preferred_anchor_node_id": self._preferred_anchor_node_id(
                citation.get("preferred_anchor_node_id"),
                anchor_node_ids=self._normalize_anchor_node_ids(citation.get("anchor_node_ids")),
            ),
            "render_kind": render_kind,
            "rendered_html": citation.get("rendered_html"),
            "render_metadata": dict(citation.get("render_metadata") or {}),
        }

    def _citation_anchor_node_ids(self, entity_links: list[dict[str, Any]]) -> list[str]:
        anchors: list[str] = []
        seen: set[str] = set()
        for link in entity_links:
            entity_id = str(link.get("entity_id") or "").strip()
            if not entity_id:
                continue
            node_id = f"entity:{entity_id}"
            if node_id in seen:
                continue
            seen.add(node_id)
            anchors.append(node_id)
        return anchors

    def _normalize_anchor_node_ids(self, value: Any, *, fallback: list[str] | None = None) -> list[str]:
        anchors = [
            node_id
            for node_id in (str(item).strip() for item in list(value or []))
            if node_id.startswith("entity:")
        ]
        if anchors:
            return self._deduplicate(anchors)
        return list(fallback or [])

    def _preferred_anchor_node_id(
        self,
        value: Any,
        *,
        anchor_node_ids: list[str],
    ) -> str | None:
        preferred = str(value or "").strip()
        if preferred:
            return preferred
        if len(anchor_node_ids) == 1:
            return anchor_node_ids[0]
        return None

    def _normalize_string_list(self, value: Any) -> list[str]:
        return [
            text
            for text in (str(item).strip() for item in list(value or []))
            if text
        ]

    def _optional_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _worksheet_name_from_payload(
        self,
        paragraph: dict[str, Any],
        render_payload: dict[str, Any],
        citation: dict[str, Any] | None = None,
    ) -> str | None:
        metadata = dict(paragraph.get("metadata") or {})
        render_metadata = dict(render_payload.get("render_metadata") or {})
        fallback = dict(citation or {})
        worksheet_name = (
            str(render_metadata.get("worksheet_name") or "").strip()
            or str(metadata.get("worksheet_name") or "").strip()
            or str(fallback.get("worksheet_name") or "").strip()
        )
        return worksheet_name or None

    def _citation_match_reason(self, *, retriever: str, match_type: str) -> str:
        match_type_map = {
            "record_key_exact": "精确命中记录键",
            "cell_exact": "精确命中表格单元格",
            "cell_partial": "部分命中表格单元格",
            "token_overlap": "结构化字段词项重叠",
            "semantic": "语义向量命中",
        }
        if match_type in match_type_map:
            return match_type_map[match_type]

        retriever_map = {
            "structured": "结构化检索命中",
            "vector": "向量检索命中",
            "hybrid": "融合排序保留",
            "ppr": "图谱扩散命中",
        }
        return retriever_map.get(retriever, "检索命中")

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
