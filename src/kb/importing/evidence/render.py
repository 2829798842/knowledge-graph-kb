"""Excel 证据渲染辅助"""

from __future__ import annotations

from html import escape
from typing import Any

from src.kb.importing.excel import normalize_column_name

ROW_CONTEXT_RADIUS = 1
RENDER_KIND_TEXT = "text"
RENDER_KIND_ROW_RECORD = "row_record"
RENDER_KIND_SHEET_SUMMARY = "sheet_summary"


def build_paragraph_render_payload(
    *,
    paragraph: dict[str, Any],
    worksheet_rows: list[dict[str, Any]] | None = None,
    highlighted_columns: list[str] | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    """根据段落和工作表上下文生成证据渲染结果"""

    metadata = dict(paragraph.get("metadata") or {})
    paragraph_kind = str(metadata.get("paragraph_kind") or "")
    highlighted_column_keys = [
        normalize_column_name(str(value))
        for value in list(highlighted_columns or [])
        if normalize_column_name(str(value))
    ]

    if paragraph_kind == "row_record":
        return _build_row_record_payload(
            paragraph=paragraph,
            metadata=metadata,
            worksheet_rows=worksheet_rows or [],
            highlighted_columns=highlighted_column_keys,
            fallback_reason=fallback_reason,
        )
    if paragraph_kind == "sheet_summary":
        return _build_sheet_summary_payload(metadata=metadata)
    return _build_text_payload(fallback_reason=fallback_reason)


def _build_text_payload(*, fallback_reason: str | None = None) -> dict[str, Any]:
    return {
        "render_kind": RENDER_KIND_TEXT,
        "rendered_html": None,
        "render_metadata": {"fallback_reason": fallback_reason} if fallback_reason else {},
    }


def _build_row_record_payload(
    *,
    paragraph: dict[str, Any],
    metadata: dict[str, Any],
    worksheet_rows: list[dict[str, Any]],
    highlighted_columns: list[str],
    fallback_reason: str | None,
) -> dict[str, Any]:
    worksheet_name = str(metadata.get("worksheet_name") or "")
    row_index = int(metadata.get("row_index") or 0)
    record_key = str(metadata.get("record_key") or "")
    header_pairs = _resolve_header_pairs(
        headers=[str(value) for value in list(metadata.get("headers") or []) if str(value).strip()],
        header_keys=[
            normalize_column_name(str(value))
            for value in list(metadata.get("header_keys") or [])
            if normalize_column_name(str(value))
        ],
        fallback_cells=_display_cells_from_metadata(metadata),
    )
    if not header_pairs:
        return _build_text_payload(fallback_reason=fallback_reason or "missing_headers")

    render_rows = _normalize_render_rows(
        worksheet_rows=worksheet_rows,
        metadata=metadata,
        header_pairs=header_pairs,
        paragraph=paragraph,
        row_index=row_index,
    )
    if not render_rows:
        return _build_text_payload(fallback_reason=fallback_reason or "missing_rows")

    render_rows.sort(key=lambda item: (int(item.get("row_index") or 0), str(item.get("paragraph_id") or "")))
    selected_rows = [
        row
        for row in render_rows
        if abs(int(row.get("row_index") or 0) - row_index) <= ROW_CONTEXT_RADIUS
    ]
    if not selected_rows:
        selected_rows = [row for row in render_rows if int(row.get("row_index") or 0) == row_index] or render_rows[:1]

    column_order = [display_name for display_name, _ in header_pairs]
    header_key_map = {display_name: key for display_name, key in header_pairs}
    highlighted_row_indexes = [row_index] if row_index else []
    window_start = min(int(row.get("row_index") or 0) for row in selected_rows)
    window_end = max(int(row.get("row_index") or 0) for row in selected_rows)

    html_rows: list[str] = []
    for row in selected_rows:
        current_row_index = int(row.get("row_index") or 0)
        row_cells = dict(row.get("cells") or {})
        row_classes = ["kb-evidence-row"]
        if current_row_index == row_index:
            row_classes.append("is-highlighted-row")
        rendered_cells: list[str] = []
        for display_name in column_order:
            header_key = header_key_map.get(display_name, normalize_column_name(display_name))
            cell_classes = ["kb-evidence-cell"]
            if current_row_index == row_index and header_key in highlighted_columns:
                cell_classes.append("is-highlighted-cell")
            rendered_cells.append(
                f"<td class=\"{' '.join(cell_classes)}\">{escape(str(row_cells.get(display_name) or ''))}</td>"
            )
        html_rows.append(
            (
                f"<tr class=\"{' '.join(row_classes)}\">"
                f"<th scope=\"row\" class=\"kb-evidence-row-index\">{escape(str(current_row_index or '-'))}</th>"
                f"{''.join(rendered_cells)}"
                "</tr>"
            )
        )

    header_cells_html = "".join(f"<th scope=\"col\">{escape(display_name)}</th>" for display_name in column_order)
    record_key_html = f"<span class=\"kb-evidence-meta\">记录键 {escape(record_key)}</span>" if record_key else ""
    rendered_html = (
        "<div class=\"kb-evidence-html kb-evidence-row-record\">"
        "<div class=\"kb-evidence-meta-row\">"
        f"<strong>{escape(worksheet_name or '工作表')}</strong>"
        f"<span class=\"kb-evidence-meta\">命中行 {escape(str(row_index or '-'))}</span>"
        f"{record_key_html}"
        "<span class=\"kb-evidence-meta\">局部上下文 前后各 1 行</span>"
        "</div>"
        "<div class=\"kb-evidence-scroll\">"
        "<table class=\"kb-evidence-table\">"
        "<thead>"
        f"<tr><th scope=\"col\" class=\"kb-evidence-row-index\">行号</th>{header_cells_html}</tr>"
        "</thead>"
        f"<tbody>{''.join(html_rows)}</tbody>"
        "</table>"
        "</div>"
        "</div>"
    )
    return {
        "render_kind": RENDER_KIND_ROW_RECORD,
        "rendered_html": rendered_html,
        "render_metadata": {
            "worksheet_name": worksheet_name,
            "row_index": row_index,
            "record_key": record_key or None,
            "highlighted_row_indexes": highlighted_row_indexes,
            "highlighted_columns": highlighted_columns,
            "column_order": column_order,
            "window_start_row": window_start,
            "window_end_row": window_end,
            "fallback_reason": fallback_reason,
        },
    }


def _build_sheet_summary_payload(*, metadata: dict[str, Any]) -> dict[str, Any]:
    worksheet_name = str(metadata.get("worksheet_name") or "")
    row_count = int(metadata.get("row_count") or 0)
    primary_key = str(metadata.get("primary_key") or "")
    indexed_columns = [str(value) for value in list(metadata.get("indexed_columns") or []) if str(value).strip()]
    headers = [str(value) for value in list(metadata.get("headers") or []) if str(value).strip()]

    indexed_columns_html = "".join(f"<li>{escape(value)}</li>" for value in indexed_columns) or "<li>未配置</li>"
    headers_html = "".join(f"<li>{escape(value)}</li>" for value in headers) or "<li>未识别</li>"
    rendered_html = (
        "<div class=\"kb-evidence-html kb-evidence-summary-card\">"
        f"<strong>{escape(worksheet_name or '工作表摘要')}</strong>"
        "<dl class=\"kb-evidence-summary-grid\">"
        f"<div><dt>总行数</dt><dd>{escape(str(row_count))}</dd></div>"
        f"<div><dt>主键</dt><dd>{escape(primary_key or '未识别')}</dd></div>"
        "</dl>"
        "<div class=\"kb-evidence-summary-lists\">"
        "<div><span>索引列</span><ul>"
        f"{indexed_columns_html}"
        "</ul></div>"
        "<div><span>表头</span><ul>"
        f"{headers_html}"
        "</ul></div>"
        "</div>"
        "</div>"
    )
    return {
        "render_kind": RENDER_KIND_SHEET_SUMMARY,
        "rendered_html": rendered_html,
        "render_metadata": {
            "worksheet_name": worksheet_name,
            "row_count": row_count,
            "primary_key": primary_key or None,
            "indexed_columns": indexed_columns,
            "headers": headers,
        },
    }


def _resolve_header_pairs(
    *,
    headers: list[str],
    header_keys: list[str],
    fallback_cells: dict[str, str],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for index, display_name in enumerate(headers):
        header_key = header_keys[index] if index < len(header_keys) else normalize_column_name(display_name)
        if not display_name.strip() or not header_key or header_key in seen_keys:
            continue
        seen_keys.add(header_key)
        pairs.append((display_name, header_key))

    if pairs:
        return pairs

    for display_name in [str(key) for key in fallback_cells.keys() if str(key).strip()]:
        header_key = normalize_column_name(display_name)
        if not header_key or header_key in seen_keys:
            continue
        seen_keys.add(header_key)
        pairs.append((display_name, header_key))
    return pairs


def _normalize_render_rows(
    *,
    worksheet_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    header_pairs: list[tuple[str, str]],
    paragraph: dict[str, Any],
    row_index: int,
) -> list[dict[str, Any]]:
    if worksheet_rows:
        result: list[dict[str, Any]] = []
        for row in worksheet_rows:
            display_cells = _display_cells_from_row(row)
            normalized_cells = _normalized_cells_from_row(row)
            result.append(
                {
                    "paragraph_id": str(row.get("paragraph_id") or ""),
                    "row_index": int(row.get("row_index") or 0),
                    "record_key": str(row.get("record_key") or ""),
                    "cells": {
                        display_name: str(display_cells.get(display_name) or normalized_cells.get(header_key) or "")
                        for display_name, header_key in header_pairs
                    },
                }
            )
        return result

    display_cells = _display_cells_from_metadata(metadata)
    normalized_cells = _normalized_cells_from_metadata(metadata)
    if not display_cells and not normalized_cells:
        return []
    return [
        {
            "paragraph_id": str(paragraph.get("id") or ""),
            "row_index": row_index,
            "record_key": str(metadata.get("record_key") or ""),
            "cells": {
                display_name: str(display_cells.get(display_name) or normalized_cells.get(header_key) or "")
                for display_name, header_key in header_pairs
            },
        }
    ]


def _display_cells_from_row(row: dict[str, Any]) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in dict(row.get("cells") or {}).items()
        if str(key).strip()
    }


def _normalized_cells_from_row(row: dict[str, Any]) -> dict[str, str]:
    metadata = dict(row.get("metadata") or {})
    raw_value = metadata.get("normalized_cells")
    if isinstance(raw_value, dict):
        return {
            normalize_column_name(str(key)): str(value)
            for key, value in raw_value.items()
            if normalize_column_name(str(key))
        }
    return {}


def _display_cells_from_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    raw_value = metadata.get("cells")
    if not isinstance(raw_value, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw_value.items()
        if str(key).strip()
    }


def _normalized_cells_from_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    raw_value = metadata.get("normalized_cells")
    if not isinstance(raw_value, dict):
        return {}
    return {
        normalize_column_name(str(key)): str(value)
        for key, value in raw_value.items()
        if normalize_column_name(str(key))
    }
