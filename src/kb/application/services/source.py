"""Source browsing and rendering service."""
from collections import defaultdict
from typing import Any

from src.kb.importing.evidence import build_paragraph_render_payload
from src.kb.importing.excel import normalize_sheet_name
from src.kb.storage import SourceStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SourceService:
    """Provide source list, detail, update, and paragraph rendering helpers."""

    def __init__(self, *, source_store: SourceStore) -> None:
        self.source_store = source_store

    def list_sources(self, *, keyword: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self.source_store.list_sources(limit=limit, keyword=keyword)

    def update_source(
        self,
        source_id: str,
        *,
        name: str | None = None,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        source = self.source_store.get_source(source_id)
        if source is None:
            return None

        next_name = None if name is None else str(name).strip()
        if next_name is not None and not next_name:
            raise ValueError("Source name cannot be empty.")

        merged_metadata = source.get("metadata", {}) if metadata is None else {**dict(source.get("metadata", {})), **metadata}
        updated = self.source_store.update_source(
            source_id,
            name=next_name,
            summary=summary,
            metadata=merged_metadata,
        )
        if updated is None:
            return None
        detail = self.get_source_detail(source_id)
        return detail["source"] if detail is not None else updated

    def get_source_detail(self, source_id: str) -> dict[str, Any] | None:
        detail = self.source_store.get_source_detail(source_id)
        if detail is None:
            return None
        source = detail["source"]
        return {
            "source": {
                "id": str(source["id"]),
                "name": str(source["name"]),
                "source_kind": str(source["source_kind"]),
                "input_mode": str(source["input_mode"]),
                "file_type": source.get("file_type"),
                "storage_path": source.get("storage_path"),
                "strategy": str(source["strategy"]),
                "status": str(source["status"]),
                "summary": str(source.get("summary") or "") or None,
                "metadata": source.get("metadata", {}),
                "created_at": str(source["created_at"]),
                "updated_at": str(source["updated_at"]),
            },
            "paragraph_count": int(detail.get("paragraph_count") or 0),
            "entity_count": int(detail.get("entity_count") or 0),
            "relation_count": int(detail.get("relation_count") or 0),
        }

    def list_source_paragraphs(self, source_id: str) -> list[dict[str, Any]] | None:
        source = self.source_store.get_source(source_id)
        if source is None:
            logger.debug("Unable to load source paragraphs because the source does not exist. source_id=%s", source_id)
            return None
        paragraphs = self.source_store.list_source_paragraphs(source_id)
        worksheet_rows_by_ref = self._collect_source_row_context(paragraphs)
        logger.debug(
            "Loaded source paragraph render context. source_id=%s paragraph_count=%s worksheet_context_count=%s",
            source_id,
            len(paragraphs),
            len(worksheet_rows_by_ref),
        )

        enriched: list[dict[str, Any]] = []
        for paragraph in paragraphs:
            metadata = dict(paragraph.get("metadata") or {})
            worksheet_key = normalize_sheet_name(str(metadata.get("worksheet_name") or ""))
            worksheet_rows = self._window_rows_for_paragraph(
                rows=worksheet_rows_by_ref.get((str(paragraph["source_id"]), worksheet_key), []),
                row_index=int(metadata.get("row_index") or 0),
            )
            render_payload = build_paragraph_render_payload(
                paragraph=paragraph,
                worksheet_rows=worksheet_rows,
            )
            enriched.append({**paragraph, **render_payload})
        logger.debug(
            "Finished rendering source paragraphs. source_id=%s paragraph_count=%s render_kinds=%s",
            source_id,
            len(enriched),
            [str(paragraph.get("render_kind") or "") for paragraph in enriched[:12]],
        )
        return enriched

    def _window_rows_for_paragraph(
        self,
        *,
        rows: list[dict[str, Any]],
        row_index: int,
    ) -> list[dict[str, Any]]:
        if row_index <= 0:
            return list(rows)
        return [row for row in rows if abs(int(row.get("row_index") or 0) - row_index) <= 1]

    def _collect_source_row_context(self, paragraphs: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for paragraph in paragraphs:
            metadata = dict(paragraph.get("metadata") or {})
            if str(metadata.get("paragraph_kind") or "") != "row_record":
                continue
            worksheet_key = normalize_sheet_name(str(metadata.get("worksheet_name") or ""))
            if not worksheet_key:
                continue
            grouped[(str(paragraph["source_id"]), worksheet_key)].append(
                {
                    "paragraph_id": str(paragraph["id"]),
                    "row_index": int(metadata.get("row_index") or 0),
                    "record_key": str(metadata.get("record_key") or ""),
                    "cells": dict(metadata.get("cells") or {}),
                    "metadata": metadata,
                }
            )
        return grouped
