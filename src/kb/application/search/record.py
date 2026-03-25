"""面向表格记录模式的检索服务。"""

from typing import Any

from src.kb.storage import RecordStore, StaleVectorIndexError
from src.utils.logger import get_logger

from ..retrieval.structured import StructuredParagraphRetriever
from ..retrieval.types import ParagraphHit, RetrievalRequest
from ..retrieval.vector import VectorParagraphRetriever

logger = get_logger(__name__)


class RecordSearchService:
    """组合结构化检索与向量检索，输出记录模式结果。"""

    def __init__(
        self,
        *,
        record_store: RecordStore,
        structured_retriever: StructuredParagraphRetriever,
        vector_retriever: VectorParagraphRetriever,
    ) -> None:
        self.record_store = record_store
        self.structured_retriever = structured_retriever
        self.vector_retriever = vector_retriever

    def search_records(
        self,
        *,
        query: str,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
        filters: dict[str, str] | None = None,
        limit: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        """执行记录检索并返回前端消费的结果结构。"""

        normalized_query = str(query or "").strip()
        if not normalized_query:
            logger.info("记录检索跳过：问题为空。")
            return {"items": []}

        request = RetrievalRequest(
            query=normalized_query,
            source_ids=list(source_ids or []),
            worksheet_names=list(worksheet_names or []),
            filters=dict(filters or {}),
            top_k=limit,
        )
        structured_hits, _ = self.structured_retriever.retrieve(request)
        rows = self.record_store.list_candidate_rows(
            source_ids=source_ids,
            worksheet_names=worksheet_names,
            filters=filters,
        )
        if not rows:
            logger.info("记录检索未找到候选行：query_length=%s", len(normalized_query))
            return {"items": []}
        record_row_ids = [str(row["id"]) for row in rows if str(row.get("id") or "").strip()]
        cell_map_by_record_row = self.record_store.list_cells(record_row_ids)
        rows_by_paragraph_id = {str(row["paragraph_id"]): row for row in rows}

        if len(structured_hits) >= limit:
            logger.info(
                "记录检索完成：结构化结果已满足数量，query_length=%s result_count=%s",
                len(normalized_query),
                len(structured_hits[:limit]),
            )
            return {"items": [self._record_item_from_hit(hit) for hit in structured_hits[:limit]]}

        result_items = [self._record_item_from_hit(hit) for hit in structured_hits[:limit]]
        if len(result_items) < limit:
            candidate_paragraph_ids = [str(row["paragraph_id"]) for row in rows if str(row.get("paragraph_id") or "").strip()]
            if not candidate_paragraph_ids:
                return {"items": result_items[:limit]}
            try:
                vector_hits, _ = self.vector_retriever.retrieve(
                    RetrievalRequest(
                        query=normalized_query,
                        source_ids=list(source_ids or []),
                        worksheet_names=list(worksheet_names or []),
                        filters=dict(filters or {}),
                        top_k=max(limit * 4, 24),
                    ),
                    paragraph_ids=candidate_paragraph_ids,
                )
            except StaleVectorIndexError:
                logger.warning("记录检索跳过向量补召回：向量索引已失效。")
                vector_hits = []
            existing_ids = {item["paragraph_id"] for item in result_items}
            for hit in vector_hits:
                if hit.paragraph_id in existing_ids:
                    continue
                row = rows_by_paragraph_id.get(hit.paragraph_id)
                if row is None:
                    continue
                result_items.append(
                    self._build_record_item(
                        row=row,
                        cells=cell_map_by_record_row.get(str(row.get("id") or ""), []),
                        score=hit.score,
                        matched_cells=[],
                    )
                )
                existing_ids.add(hit.paragraph_id)
                if len(result_items) >= limit:
                    break

        logger.info(
            "记录检索完成：query_length=%s result_count=%s source_scope_count=%s worksheet_scope_count=%s",
            len(normalized_query),
            len(result_items[:limit]),
            len(source_ids or []),
            len(worksheet_names or []),
        )
        return {"items": result_items[:limit]}

    def _record_item_from_hit(self, hit: ParagraphHit) -> dict[str, Any]:
        """把段落命中结果转换成记录模式返回结构。"""

        return {
            "paragraph_id": hit.paragraph_id,
            "source_id": hit.source_id,
            "source_name": str(hit.metadata.get("source_name") or ""),
            "worksheet_name": str(hit.metadata.get("worksheet_name") or ""),
            "row_index": int(hit.metadata.get("row_index") or 0),
            "content": str(hit.metadata.get("content") or ""),
            "matched_cells": list(hit.metadata.get("matched_cells") or []),
            "score": float(hit.score),
            "metadata": {
                **dict(hit.metadata.get("row_metadata") or {}),
                "record_row_id": hit.metadata.get("record_row_id"),
                "cells": dict(hit.metadata.get("cells") or {}),
                "match_type": hit.match_type,
            },
        }

    def _build_record_item(
        self,
        *,
        row: dict[str, Any],
        cells: list[dict[str, Any]],
        score: float,
        matched_cells: list[str],
    ) -> dict[str, Any]:
        """基于原始记录行和单元格内容构造结果项。"""

        return {
            "paragraph_id": str(row["paragraph_id"]),
            "source_id": str(row["source_id"]),
            "source_name": str(row["source_name"]),
            "worksheet_name": str(row["worksheet_name"]),
            "row_index": int(row["row_index"]),
            "content": str(row["content"]),
            "matched_cells": matched_cells,
            "score": float(score),
            "metadata": {
                **dict(row.get("metadata", {})),
                "cells": {
                    str(cell["normalized_column_name"]): str(cell["cell_value"])
                    for cell in cells
                },
            },
        }
