"""问答生成与知识库检索的应用服务。"""

import re
from typing import Any

from src.config import Settings
from src.knowledge_base.domain import (
    build_contains_edge_id,
    build_mention_edge_id,
    build_paragraph_node_id,
    build_relation_edge_id,
    build_source_node_id,
)
from src.knowledge_base.importing.excel import normalize_column_name
from src.knowledge_base.infrastructure import (
    GraphRepository,
    OpenAiGateway,
    RecordRepository,
    SearchRepository,
    StaleVectorIndexError,
    VectorIndex,
)
from src.knowledge_base.application.model_config_service import ModelConfigService

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
EMPTY_QUERY_MESSAGE = "请输入问题后再查询。"
NO_HIT_MESSAGE = "当前知识库中还没有命中相关段落。"
STALE_INDEX_MESSAGE = "当前向量索引与嵌入模型不匹配，已清空失效索引，请重新导入内容后再试。"


class SearchService:
    """提供问答生成以及记录、实体、关系、来源检索。"""

    def __init__(
        self,
        *,
        settings: Settings,
        model_config_service: ModelConfigService,
        record_repository: RecordRepository,
        search_repository: SearchRepository,
        graph_repository: GraphRepository,
        vector_index: VectorIndex,
        openai_gateway: OpenAiGateway,
    ) -> None:
        self.settings = settings
        self.model_config_service = model_config_service
        self.record_repository = record_repository
        self.search_repository = search_repository
        self.graph_repository = graph_repository
        self.vector_index = vector_index
        self.openai_gateway = openai_gateway

    def search_records(
        self,
        *,
        query: str,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
        filters: dict[str, str] | None = None,
        limit: int = 20,
        mode: str = "exact_first",
    ) -> dict[str, list[dict[str, Any]]]:
        """检索结构化表格记录，支持精确优先与混合检索。"""

        normalized_query = str(query or "").strip()
        if not normalized_query:
            return {"items": []}
        normalized_mode = str(mode or "exact_first").strip().lower()
        if normalized_mode not in {"exact_first", "hybrid"}:
            normalized_mode = "exact_first"
        candidates = self.record_repository.list_candidate_rows(
            source_ids=source_ids,
            worksheet_names=worksheet_names,
            filters=filters,
        )
        if not candidates:
            return {"items": []}
        cell_map = self.record_repository.list_cells([str(row["id"]) for row in candidates])
        exact_items = self._score_exact_matches(query=normalized_query, rows=candidates, cell_map=cell_map)
        if normalized_mode == "exact_first" and len(exact_items) >= limit:
            return {"items": exact_items[:limit]}
        result_items = exact_items[:limit]
        if normalized_mode == "hybrid" or len(result_items) < limit:
            result_items = self._merge_vector_matches(
                query=normalized_query,
                rows=candidates,
                cell_map=cell_map,
                existing_items=result_items,
                limit=limit,
            )
        return {"items": result_items[:limit]}

    def answer(
        self,
        *,
        query: str,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
        exact_first: bool = False,
        top_k: int = 6,
    ) -> dict[str, Any]:
        """基于检索到的段落上下文生成问答结果。"""

        normalized_query = str(query or "").strip()
        if not normalized_query:
            return self._empty_response(EMPTY_QUERY_MESSAGE)
        candidate_paragraph_ids = self._resolve_candidate_paragraph_ids(
            source_ids=source_ids,
            worksheet_names=worksheet_names,
        )
        if worksheet_names and not candidate_paragraph_ids:
            return self._empty_response(NO_HIT_MESSAGE)
        if exact_first or worksheet_names:
            record_response = self.search_records(
                query=normalized_query,
                source_ids=source_ids,
                worksheet_names=worksheet_names,
                limit=max(1, min(top_k, self.settings.query_context_chunks)),
                mode="exact_first" if exact_first else "hybrid",
            )
            if record_response["items"]:
                return self._build_response_from_paragraph_ids(
                    query=normalized_query,
                    paragraph_ids=[item["paragraph_id"] for item in record_response["items"]],
                    score_map={item["paragraph_id"]: float(item["score"]) for item in record_response["items"]},
                )
        embedding_signature = self.model_config_service.embedding_model_signature()
        query_embedding = self.openai_gateway.embed_texts([normalized_query])[0]
        try:
            results = self.vector_index.search(
                model_signature=embedding_signature,
                query_embedding=query_embedding,
                limit=max(1, min(top_k, self.settings.query_context_chunks)),
                source_ids=source_ids,
                paragraph_ids=candidate_paragraph_ids,
            )
        except StaleVectorIndexError:
            return self._empty_response(STALE_INDEX_MESSAGE)
        if not results:
            return self._empty_response(NO_HIT_MESSAGE)
        return self._build_response_from_paragraph_ids(
            query=normalized_query,
            paragraph_ids=[result.paragraph_id for result in results],
            score_map={result.paragraph_id: float(result.similarity) for result in results},
        )

    def search_entities(self, *, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        """检索实体结果列表。"""

        rows = self.search_repository.search_entities(query=query, limit=limit)
        items: list[dict[str, Any]] = []
        for row in rows:
            paragraph_ids = [
                value
                for value in str(row.get("paragraph_ids") or "").split(",")
                if value
            ]
            items.append(
                {
                    "id": str(row["id"]),
                    "display_name": str(row["display_name"]),
                    "description": str(row.get("description") or "") or None,
                    "appearance_count": int(row.get("appearance_count") or 0),
                    "metadata": row.get("metadata", {}),
                    "paragraph_ids": paragraph_ids,
                }
            )
        return {"items": items}

    def search_relations(self, *, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        """检索关系结果列表。"""

        rows = self.search_repository.search_relations(query=query, limit=limit)
        return {
            "items": [
                {
                    "id": str(row["id"]),
                    "subject_id": str(row["subject_entity_id"]),
                    "subject_name": str(row["subject_name"]),
                    "predicate": str(row["predicate"]),
                    "object_id": str(row["object_entity_id"]),
                    "object_name": str(row["object_name"]),
                    "confidence": float(row.get("confidence") or 0.0),
                    "source_paragraph_id": str(row.get("source_paragraph_id") or "") or None,
                    "metadata": row.get("metadata", {}),
                }
                for row in rows
            ]
        }

    def search_sources(self, *, query: str, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        """检索来源结果列表。"""

        rows = self.search_repository.search_sources(query=query, limit=limit)
        return {
            "items": [
                {
                    "id": str(row["id"]),
                    "name": str(row["name"]),
                    "source_kind": str(row["source_kind"]),
                    "summary": str(row.get("summary") or "") or None,
                    "metadata": row.get("metadata", {}),
                    "paragraph_count": int(row.get("paragraph_count") or 0),
                }
                for row in rows
            ]
        }

    def _resolve_candidate_paragraph_ids(
        self,
        *,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
    ) -> list[str] | None:
        if not worksheet_names:
            return None
        rows = self.record_repository.list_candidate_rows(
            source_ids=source_ids,
            worksheet_names=worksheet_names,
        )
        if not rows:
            return []
        return self._deduplicate([str(row["paragraph_id"]) for row in rows if str(row.get("paragraph_id") or "").strip()])

    def _score_exact_matches(
        self,
        *,
        query: str,
        rows: list[dict[str, Any]],
        cell_map: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        normalized_query = normalize_column_name(query)
        query_tokens = {token.casefold() for token in TOKEN_PATTERN.findall(query) if token.strip()}
        scored_items: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            cells = cell_map.get(str(row["id"]), [])
            matched_cells: list[str] = []
            score = 0.0
            record_key = str(row.get("record_key") or "").strip()
            if record_key and normalize_column_name(record_key) == normalized_query:
                score += 12.0
            content = str(row.get("content") or "")
            if normalized_query and normalize_column_name(content).find(normalized_query) >= 0:
                score += 1.0
            normalized_display_cells = {
                str(cell["normalized_column_name"]): str(cell["normalized_value"])
                for cell in cells
                if str(cell.get("normalized_value") or "").strip()
            }
            for column_name, normalized_value in normalized_display_cells.items():
                if normalized_value == normalized_query:
                    matched_cells.append(column_name)
                    score += 8.0
                    continue
                if normalized_query and normalized_query in normalized_value:
                    matched_cells.append(column_name)
                    score += 4.0
            if query_tokens:
                content_tokens = {token.casefold() for token in TOKEN_PATTERN.findall(content) if token.strip()}
                score += len(query_tokens & content_tokens) * 0.35
            if score <= 0:
                continue
            scored_items.append((score, self._build_record_item(row=row, cells=cells, score=score, matched_cells=matched_cells)))
        scored_items.sort(key=lambda item: (-item[0], item[1]["worksheet_name"], item[1]["row_index"], item[1]["paragraph_id"]))
        return [item for _, item in scored_items]

    def _merge_vector_matches(
        self,
        *,
        query: str,
        rows: list[dict[str, Any]],
        cell_map: dict[str, list[dict[str, Any]]],
        existing_items: list[dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        existing_ids = {item["paragraph_id"] for item in existing_items}
        paragraph_id_set = {str(row["paragraph_id"]) for row in rows}
        if not paragraph_id_set:
            return existing_items
        embedding_signature = self.model_config_service.embedding_model_signature()
        query_embedding = self.openai_gateway.embed_texts([query])[0]
        try:
            vector_rows = self.vector_index.search(
                model_signature=embedding_signature,
                query_embedding=query_embedding,
                limit=max(limit * 4, 24),
                paragraph_ids=list(paragraph_id_set),
            )
        except StaleVectorIndexError:
            return existing_items
        rows_by_paragraph_id = {str(row["paragraph_id"]): row for row in rows}
        items = list(existing_items)
        for vector_row in vector_rows:
            if vector_row.paragraph_id in existing_ids:
                continue
            row = rows_by_paragraph_id.get(vector_row.paragraph_id)
            if row is None:
                continue
            cells = cell_map.get(str(row["id"]), [])
            matched_cells = [
                str(cell["normalized_column_name"])
                for cell in cells
                if normalize_column_name(query) in str(cell["normalized_value"])
            ]
            items.append(
                self._build_record_item(
                    row=row,
                    cells=cells,
                    score=float(vector_row.similarity),
                    matched_cells=matched_cells,
                )
            )
            existing_ids.add(vector_row.paragraph_id)
            if len(items) >= limit:
                break
        return items

    def _build_record_item(
        self,
        *,
        row: dict[str, Any],
        cells: list[dict[str, Any]],
        score: float,
        matched_cells: list[str],
    ) -> dict[str, Any]:
        metadata = {
            **dict(row.get("metadata", {})),
            "cells": {
                str(cell["normalized_column_name"]): str(cell["cell_value"])
                for cell in cells
            },
        }
        return {
            "paragraph_id": str(row["paragraph_id"]),
            "source_id": str(row["source_id"]),
            "source_name": str(row["source_name"]),
            "worksheet_name": str(row["worksheet_name"]),
            "row_index": int(row["row_index"]),
            "content": str(row["content"]),
            "matched_cells": matched_cells,
            "score": score,
            "metadata": metadata,
        }

    def _build_response_from_paragraph_ids(
        self,
        *,
        query: str,
        paragraph_ids: list[str],
        score_map: dict[str, float],
    ) -> dict[str, Any]:
        citations: list[dict[str, Any]] = []
        context_blocks: list[dict[str, str]] = []
        highlighted_node_ids: list[str] = []
        highlighted_edge_ids: list[str] = []
        paragraphs = self.search_repository.get_paragraphs_with_sources(paragraph_ids)
        paragraph_by_id = {str(row["id"]): row for row in paragraphs}
        entity_links = self.search_repository.list_entity_links_for_paragraphs(paragraph_ids)
        relation_links = self.search_repository.list_relation_links_for_paragraphs(paragraph_ids)
        entity_links_by_paragraph: dict[str, list[dict[str, Any]]] = {}
        relation_links_by_paragraph: dict[str, list[dict[str, Any]]] = {}
        for link in entity_links:
            entity_links_by_paragraph.setdefault(str(link["paragraph_id"]), []).append(link)
        for link in relation_links:
            relation_links_by_paragraph.setdefault(str(link["paragraph_id"]), []).append(link)
        for paragraph_id in paragraph_ids:
            paragraph = paragraph_by_id.get(paragraph_id)
            if paragraph is None:
                continue
            source_id = str(paragraph["source_id"])
            source_name = str(paragraph["source_name"])
            excerpt = str(paragraph["content"])[:420]
            citations.append(
                {
                    "paragraph_id": paragraph_id,
                    "source_id": source_id,
                    "source_name": source_name,
                    "excerpt": excerpt,
                    "score": float(score_map.get(paragraph_id, 0.0)),
                }
            )
            context_blocks.append(
                {
                    "chunk_id": paragraph_id,
                    "document_name": source_name,
                    "excerpt": excerpt,
                }
            )
            highlighted_node_ids.extend([build_source_node_id(source_id), build_paragraph_node_id(paragraph_id)])
            highlighted_edge_ids.append(build_contains_edge_id(source_id, paragraph_id))
            for link in entity_links_by_paragraph.get(paragraph_id, []):
                entity_id = str(link["entity_id"])
                highlighted_node_ids.append(f"entity:{entity_id}")
                highlighted_edge_ids.append(build_mention_edge_id(paragraph_id, entity_id))
            for link in relation_links_by_paragraph.get(paragraph_id, []):
                highlighted_edge_ids.append(build_relation_edge_id(str(link["relation_id"])))
        if not citations:
            return self._empty_response(NO_HIT_MESSAGE)
        answer_text = self.openai_gateway.answer_query(query, context_blocks)
        return {
            "answer": answer_text,
            "citations": citations,
            "highlighted_node_ids": self._deduplicate(highlighted_node_ids),
            "highlighted_edge_ids": self._deduplicate(highlighted_edge_ids),
        }

    def _deduplicate(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered_values: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered_values.append(value)
        return ordered_values

    def _empty_response(self, message: str) -> dict[str, Any]:
        return {
            "answer": message,
            "citations": [],
            "highlighted_node_ids": [],
            "highlighted_edge_ids": [],
        }
