"""Map normalized Excel workbook structures into import payloads."""

from typing import Any

from src.kb.importing.chunking import count_tokens

from .models import SpreadsheetDocumentData
from .normalizer import (
    append_config_relations,
    append_entity,
    append_heuristic_relations,
    append_relation,
    normalize_excel_workbook,
    prepare_schema_entities,
)
from .schema import DEFAULT_RELATION_PREDICATE, normalize_spreadsheet_schema


def build_excel_import_bundle(
    *,
    document: SpreadsheetDocumentData,
    strategy: str,
    source_file_type: str,
    source_name: str,
    schema_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build workbook paragraphs plus structured entities and relations."""

    normalized_schema = normalize_spreadsheet_schema(schema_payload or {}, file_name="spreadsheet schema")
    prepared_sheets = normalize_excel_workbook(
        worksheets=document.worksheets,
        source_name=source_name,
        sheet_rules=normalized_schema["sheet_rules"],
    )

    paragraph_payloads: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    entity_names_seen: set[str] = set()
    relation_keys_seen: set[tuple[str, str, str]] = set()

    for sheet in prepared_sheets:
        append_entity(
            entities=entities,
            seen=entity_names_seen,
            name=sheet.entity_name,
            description=f"Worksheet {sheet.worksheet_name} in workbook {sheet.source_name}",
            metadata={
                "entity_kind": "worksheet",
                "source_name": sheet.source_name,
                "worksheet_name": sheet.worksheet_name,
                "worksheet_index": sheet.worksheet_index,
                "display_label": sheet.worksheet_name,
            },
        )
        paragraph_payloads.append(
            {
                "content": sheet.summary_content,
                "knowledge_type": strategy if strategy != "auto" else "factual",
                "token_count": count_tokens(sheet.summary_content),
                "vector_state": "pending",
                "metadata": {
                    "strategy": strategy,
                    "source_file_type": source_file_type,
                    "is_spreadsheet": True,
                    "paragraph_kind": "sheet_summary",
                    "source_name": sheet.source_name,
                    "worksheet_name": sheet.worksheet_name,
                    "worksheet_entity": sheet.entity_name,
                    "worksheet_index": sheet.worksheet_index,
                    "row_count": len(sheet.rows),
                    "primary_key": sheet.primary_key,
                    "headers": sheet.display_headers,
                    "header_keys": sheet.header_keys,
                    "indexed_columns": sheet.indexed_columns,
                },
            }
        )
        for row in sheet.rows:
            paragraph_payloads.append(
                {
                    "content": row.content,
                    "knowledge_type": strategy if strategy != "auto" else "factual",
                    "token_count": count_tokens(row.content),
                    "vector_state": "pending",
                    "metadata": {
                        "strategy": strategy,
                        "source_file_type": source_file_type,
                        "is_spreadsheet": True,
                        "paragraph_kind": "row_record",
                        "source_name": row.source_name,
                        "worksheet_name": row.worksheet_name,
                        "worksheet_entity": row.worksheet_entity_name,
                        "worksheet_index": row.worksheet_index,
                        "row_index": row.row_index,
                        "record_key": row.record_key,
                        "record_entity": row.entity_name,
                        "record_label": row.entity_label,
                        "cells": row.display_cells,
                        "normalized_cells": row.normalized_cells,
                        "headers": sheet.display_headers,
                        "header_keys": sheet.header_keys,
                        "indexed_columns": sheet.indexed_columns,
                        "primary_key": sheet.primary_key,
                    },
                }
            )
            append_entity(
                entities=entities,
                seen=entity_names_seen,
                name=row.entity_name,
                description=f"{row.worksheet_name} row {row.row_index} ({row.record_key})",
                metadata={
                    "entity_kind": "row_record",
                    "source_name": row.source_name,
                    "worksheet_name": row.worksheet_name,
                    "worksheet_entity": row.worksheet_entity_name,
                    "worksheet_index": row.worksheet_index,
                    "row_index": row.row_index,
                    "record_key": row.record_key,
                    "display_label": row.entity_label,
                    "relation_source": "row_record",
                },
            )
            append_relation(
                relations=relations,
                seen=relation_keys_seen,
                subject=row.worksheet_entity_name,
                predicate="has_record",
                object_name=row.entity_name,
                metadata={
                    "relation_source": "spreadsheet_structure",
                    "source_name": row.source_name,
                    "source_worksheet_name": row.worksheet_name,
                    "target_worksheet_name": row.worksheet_name,
                    "worksheet_entity": row.worksheet_entity_name,
                    "record_key": row.record_key,
                },
            )

    for entity in prepare_schema_entities(
        prepared_sheets=prepared_sheets,
        entity_rules=normalized_schema["entity_rules"],
    ):
        append_entity(
            entities=entities,
            seen=entity_names_seen,
            name=str(entity["name"]),
            description=str(entity.get("description") or ""),
            metadata=dict(entity.get("metadata", {})),
        )

    append_config_relations(
        relations=relations,
        seen=relation_keys_seen,
        prepared_sheets=prepared_sheets,
        relation_rules=normalized_schema["relation_rules"],
    )
    append_heuristic_relations(
        relations=relations,
        seen=relation_keys_seen,
        prepared_sheets=prepared_sheets,
        relation_predicate_prefix=DEFAULT_RELATION_PREDICATE,
    )

    return {
        "paragraphs": paragraph_payloads,
        "entities": entities,
        "relations": relations,
        "worksheet_names": [sheet.worksheet_name for sheet in prepared_sheets],
        "metadata": {
            "spreadsheet_schema_present": bool(schema_payload),
            "spreadsheet_row_count": sum(len(sheet.rows) for sheet in prepared_sheets),
            "spreadsheet_sheet_count": len(prepared_sheets),
        },
    }


