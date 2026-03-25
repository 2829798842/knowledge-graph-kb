"""面向结构化知识的段落检索器。"""

from collections.abc import Iterable
import re
from time import perf_counter
from typing import Any

from src.kb.importing.excel import normalize_column_name
from src.kb.storage import RecordStore
from src.utils.logger import get_logger

from .types import ParagraphHit, RetrievalLaneTrace, RetrievalRequest

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
logger = get_logger(__name__)


class StructuredParagraphRetriever:
    """从表格记录和结构化行内容中返回段落命中结果。"""

    def __init__(self, *, record_store: RecordStore) -> None:
        self.record_store = record_store

    def retrieve(self, request: RetrievalRequest) -> tuple[list[ParagraphHit], RetrievalLaneTrace]:
        """执行结构化检索并输出段落命中和检索轨迹。"""

        start_time = perf_counter()
        normalized_query = str(request.query or "").strip()
        if not normalized_query:
            logger.info("结构化检索跳过：问题为空。")
            return [], self._trace(executed=False, skipped_reason="empty_query", start_time=start_time, hits=[])

        rows = self.record_store.list_candidate_rows(
            source_ids=request.source_ids or None,
            worksheet_names=request.worksheet_names or None,
            filters=request.filters or None,
        )
        if not rows:
            logger.info("结构化检索未找到候选记录：query_length=%s", len(normalized_query))
            return [], self._trace(executed=True, skipped_reason=None, start_time=start_time, hits=[])

        cell_map = self.record_store.list_cells([str(row["id"]) for row in rows])
        hits: list[ParagraphHit] = []
        normalized_query_key = normalize_column_name(normalized_query)
        query_tokens = self._tokenize(normalized_query)
        for row in rows:
            cells = cell_map.get(str(row["id"]), [])
            score, match_type, matched_cells = self._score_row(
                query=normalized_query,
                normalized_query_key=normalized_query_key,
                query_tokens=query_tokens,
                row=row,
                cells=cells,
            )
            if score <= 0.0 or match_type is None:
                continue
            hits.append(
                ParagraphHit(
                    paragraph_id=str(row["paragraph_id"]),
                    source_id=str(row["source_id"]),
                    score=score,
                    rank=0,
                    retriever="structured",
                    match_type=match_type,
                    metadata={
                        "record_row_id": str(row["id"]),
                        "row_index": int(row.get("row_index") or 0),
                        "worksheet_name": str(row.get("worksheet_name") or ""),
                        "source_name": str(row.get("source_name") or ""),
                        "content": str(row.get("content") or ""),
                        "row_metadata": dict(row.get("metadata", {})),
                        "matched_cells": matched_cells,
                        "cells": {
                            str(cell["normalized_column_name"]): str(cell["cell_value"])
                            for cell in cells
                        },
                    },
                )
            )

        hits.sort(
            key=lambda item: (
                -item.score,
                str(item.metadata.get("worksheet_name") or ""),
                int(item.metadata.get("row_index") or 0),
                item.paragraph_id,
            )
        )
        for index, hit in enumerate(hits, start=1):
            hit.rank = index
        logger.info(
            "结构化检索完成：query_length=%s candidate_row_count=%s hit_count=%s worksheet_scope_count=%s",
            len(normalized_query),
            len(rows),
            len(hits),
            len(request.worksheet_names or []),
        )
        return hits, self._trace(executed=True, skipped_reason=None, start_time=start_time, hits=hits)

    def _score_row(
        self,
        *,
        query: str,
        normalized_query_key: str,
        query_tokens: set[str],
        row: dict[str, Any],
        cells: list[dict[str, Any]],
    ) -> tuple[float, str | None, list[str]]:
        """为单条记录计算结构化匹配分数。"""

        score = 0.0
        match_type: str | None = None
        matched_cells: list[str] = []

        record_key = str(row.get("record_key") or "").strip()
        if record_key and normalize_column_name(record_key) == normalized_query_key:
            score += 12.0
            match_type = "record_key_exact"

        content = str(row.get("content") or "")
        if normalized_query_key and normalized_query_key in normalize_column_name(content):
            score += 1.0

        normalized_display_cells = {
            str(cell["normalized_column_name"]): str(cell["normalized_value"])
            for cell in cells
            if str(cell.get("normalized_value") or "").strip()
        }
        for column_name, normalized_value in normalized_display_cells.items():
            if normalized_value == normalized_query_key:
                matched_cells.append(column_name)
                score += 8.0
                if match_type != "record_key_exact":
                    match_type = "cell_exact"
                continue
            if normalized_query_key and normalized_query_key in normalized_value:
                matched_cells.append(column_name)
                score += 4.0
                if match_type not in {"record_key_exact", "cell_exact"}:
                    match_type = "cell_partial"

        if query_tokens:
            content_tokens = self._tokenize(content)
            token_overlap = len(query_tokens & content_tokens)
            if token_overlap > 0:
                score += token_overlap * 0.35
                if match_type is None:
                    match_type = "token_overlap"
        return score, match_type, matched_cells

    def _trace(
        self,
        *,
        executed: bool,
        skipped_reason: str | None,
        start_time: float,
        hits: Iterable[ParagraphHit],
    ) -> RetrievalLaneTrace:
        """构造结构化检索链路的轨迹信息。"""

        hit_list = list(hits)
        return RetrievalLaneTrace(
            executed=executed,
            skipped_reason=skipped_reason,
            hit_count=len(hit_list),
            latency_ms=round((perf_counter() - start_time) * 1000.0, 2),
            top_paragraph_ids=[hit.paragraph_id for hit in hit_list[:6]],
        )

    def _tokenize(self, text: str) -> set[str]:
        """把文本拆成归一化后的检索词元集合。"""

        return {token.casefold() for token in TOKEN_PATTERN.findall(text) if token.strip()}
