"""Normalize workbook sheets and rows before mapping them into KG payloads."""

from typing import Any

from .models import ExcelImportRow, ExcelImportSheet, HEADER_VALUE_PATTERN, SpreadsheetWorksheetData
from .schema import normalize_column_name, normalize_sheet_name, render_cell_template, singularize_token


def normalize_excel_workbook(
    *,
    worksheets: list[SpreadsheetWorksheetData],
    source_name: str,
    sheet_rules: dict[str, dict[str, Any]],
) -> list[ExcelImportSheet]:
    prepared_sheets = [
        _prepare_sheet(
            worksheet=worksheet,
            source_name=source_name,
            rule=sheet_rules.get(normalize_sheet_name(worksheet.name)),
        )
        for worksheet in worksheets
        if worksheet.rows
    ]
    return [sheet for sheet in prepared_sheets if sheet is not None]


def prepare_schema_entities(
    *,
    prepared_sheets: list[ExcelImportSheet],
    entity_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    entity_names_seen: set[str] = set()
    for rule in entity_rules:
        sheet = find_prepared_sheet(prepared_sheets, worksheet_key=str(rule["worksheet_key"]))
        if sheet is None:
            continue
        for row in sheet.rows:
            value = row.normalized_cells.get(str(rule["column"]))
            if not value:
                continue
            display_value = row.display_cells.get(display_header_for_key(sheet, str(rule["column"])), value)
            template_cells = {**row.display_cells, "value": display_value, "record_key": row.record_key}
            entity_name = render_cell_template(
                str(rule["display_template"]),
                cells=template_cells,
                fallback=display_value,
            )
            entity_description = render_cell_template(
                str(rule["description_template"]),
                cells=template_cells,
                fallback=f"{row.worksheet_name}.{rule['column']}={display_value}",
            )
            append_entity(
                entities=entities,
                seen=entity_names_seen,
                name=entity_name,
                description=entity_description,
                metadata={
                    "entity_kind": str(rule["entity_type"]),
                    "source_name": row.source_name,
                    "worksheet_name": row.worksheet_name,
                    "worksheet_entity": row.worksheet_entity_name,
                    "worksheet_index": row.worksheet_index,
                    "row_index": row.row_index,
                    "record_key": row.record_key,
                    "source_column": str(rule["column"]),
                    "relation_source": "schema",
                },
            )
    return entities


def append_config_relations(
    *,
    relations: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    prepared_sheets: list[ExcelImportSheet],
    relation_rules: list[dict[str, Any]],
) -> None:
    for rule in relation_rules:
        source_sheet = find_prepared_sheet(prepared_sheets, worksheet_key=str(rule["source_worksheet_key"]))
        target_sheet = find_prepared_sheet(prepared_sheets, worksheet_key=str(rule["target_worksheet_key"]))
        if source_sheet is None or target_sheet is None:
            continue
        target_lookup = build_row_lookup(target_sheet, str(rule["target_match_column"]))
        if not target_lookup:
            continue
        for row in source_sheet.rows:
            join_value = row.normalized_cells.get(str(rule["source_match_column"]), "")
            target_entity = target_lookup.get(normalize_lookup_value(join_value))
            if not target_entity:
                continue
            subject = row.entity_name
            object_name = target_entity
            if str(rule["direction"]) == "reverse":
                subject, object_name = object_name, subject
            append_relation(
                relations=relations,
                seen=seen,
                subject=subject,
                predicate=str(rule["predicate"]),
                object_name=object_name,
                metadata={
                    "relation_source": "schema",
                    "source_name": source_sheet.source_name,
                    "source_worksheet_name": source_sheet.worksheet_name,
                    "target_worksheet_name": target_sheet.worksheet_name,
                    "source_match_column": str(rule["source_match_column"]),
                    "target_match_column": str(rule["target_match_column"]),
                },
            )


def append_heuristic_relations(
    *,
    relations: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    prepared_sheets: list[ExcelImportSheet],
    relation_predicate_prefix: str,
) -> None:
    primary_key_map: dict[str, ExcelImportSheet] = {}
    for sheet in prepared_sheets:
        if sheet.primary_key:
            primary_key_map[normalize_lookup_value(sheet.primary_key)] = sheet

    for source_sheet in prepared_sheets:
        for column in source_sheet.indexed_columns:
            if not looks_like_reference_column(column, primary_key=source_sheet.primary_key):
                continue
            target_sheet = resolve_target_sheet_for_reference(
                prepared_sheets=prepared_sheets,
                primary_key_map=primary_key_map,
                source_sheet=source_sheet,
                source_column=column,
            )
            if target_sheet is None:
                continue
            target_lookup = build_row_lookup(target_sheet, target_sheet.primary_key or "")
            if not target_lookup:
                continue
            for row in source_sheet.rows:
                join_value = row.normalized_cells.get(column, "")
                target_entity = target_lookup.get(normalize_lookup_value(join_value))
                if not target_entity or target_entity == row.entity_name:
                    continue
                append_relation(
                    relations=relations,
                    seen=seen,
                    subject=row.entity_name,
                    predicate=f"{relation_predicate_prefix}_{column}",
                    object_name=target_entity,
                    metadata={
                        "relation_source": "heuristic",
                        "source_name": source_sheet.source_name,
                        "source_worksheet_name": source_sheet.worksheet_name,
                        "target_worksheet_name": target_sheet.worksheet_name,
                        "source_match_column": column,
                        "target_match_column": target_sheet.primary_key,
                    },
                )


def append_entity(
    *,
    entities: list[dict[str, Any]],
    seen: set[str],
    name: str,
    description: str,
    metadata: dict[str, Any],
) -> None:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        return
    identity = normalized_name.casefold()
    if identity in seen:
        return
    seen.add(identity)
    entities.append(
        {
            "name": normalized_name,
            "description": str(description or "").strip(),
            "metadata": metadata,
        }
    )


def append_relation(
    *,
    relations: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    subject: str,
    predicate: str,
    object_name: str,
    metadata: dict[str, Any],
) -> None:
    relation_key = (subject.casefold(), predicate.casefold(), object_name.casefold())
    if relation_key in seen:
        return
    seen.add(relation_key)
    relation_source = str(metadata.get("relation_source") or "")
    confidence = 0.72
    if relation_source == "schema":
        confidence = 1.0
    elif relation_source == "spreadsheet_structure":
        confidence = 0.95
    relations.append(
        {
            "subject": subject,
            "predicate": predicate,
            "object": object_name,
            "confidence": confidence,
            "metadata": metadata,
        }
    )


def display_header_for_key(sheet: ExcelImportSheet, key: str) -> str:
    for display, header_key in zip(sheet.display_headers, sheet.header_keys, strict=True):
        if header_key == key:
            return display
    return key


def find_prepared_sheet(
    prepared_sheets: list[ExcelImportSheet],
    *,
    worksheet_key: str,
) -> ExcelImportSheet | None:
    for sheet in prepared_sheets:
        if sheet.worksheet_key == worksheet_key:
            return sheet
    return None


def build_row_lookup(sheet: ExcelImportSheet, column_key: str) -> dict[str, str]:
    if not column_key:
        return {}
    lookup: dict[str, str] = {}
    for row in sheet.rows:
        value = row.normalized_cells.get(column_key, "")
        normalized_value = normalize_lookup_value(value)
        if normalized_value and normalized_value not in lookup:
            lookup[normalized_value] = row.entity_name
    return lookup


def resolve_target_sheet_for_reference(
    *,
    prepared_sheets: list[ExcelImportSheet],
    primary_key_map: dict[str, ExcelImportSheet],
    source_sheet: ExcelImportSheet,
    source_column: str,
) -> ExcelImportSheet | None:
    normalized_column = normalize_lookup_value(source_column)
    direct_target = primary_key_map.get(normalized_column)
    if direct_target is not None and direct_target.worksheet_key != source_sheet.worksheet_key:
        return direct_target

    if normalized_column.endswith("id"):
        prefix = normalized_column[: -len("id")]
        if prefix:
            for target_sheet in prepared_sheets:
                if target_sheet.worksheet_key == source_sheet.worksheet_key or not target_sheet.primary_key:
                    continue
                target_name = singularize_token(target_sheet.worksheet_name)
                if prefix == target_name and normalize_lookup_value(target_sheet.primary_key) == "id":
                    return target_sheet
    return None


def looks_like_reference_column(column: str, *, primary_key: str | None) -> bool:
    normalized_column = normalize_lookup_value(column)
    normalized_primary_key = normalize_lookup_value(primary_key or "")
    if not normalized_column or normalized_column == normalized_primary_key:
        return False
    return normalized_column == "id" or normalized_column.endswith("id") or normalized_column.endswith("code")


def normalize_lookup_value(value: str) -> str:
    return normalize_column_name(str(value or ""))


def _prepare_sheet(
    *,
    worksheet: SpreadsheetWorksheetData,
    source_name: str,
    rule: dict[str, Any] | None,
) -> ExcelImportSheet | None:
    non_empty_rows = [row for row in worksheet.rows if any(str(cell or "").strip() for cell in row)]
    if not non_empty_rows:
        return None

    configured_header_row: int | None = None
    if rule:
        configured_header_row_raw = rule.get("header_row")
        if configured_header_row_raw is not None and str(configured_header_row_raw).strip() != "":
            configured_header_row = int(configured_header_row_raw)
    header_row_index = _resolve_header_row_index(non_empty_rows, configured_header_row)
    if header_row_index is None:
        raw_headers = [f"Column {index + 1}" for index in range(max(len(row) for row in non_empty_rows))]
        body_rows = non_empty_rows
        body_row_offset = 1
    else:
        raw_headers = non_empty_rows[header_row_index - 1]
        body_rows = non_empty_rows[header_row_index:]
        body_row_offset = header_row_index + 1

    header_pairs = _build_header_pairs(raw_headers)
    display_headers = [item["display"] for item in header_pairs]
    header_keys = [item["key"] for item in header_pairs]
    ignored_columns = set(rule.get("ignored_columns") or []) if rule else set()
    indexed_columns = [key for key in header_keys if key and key not in ignored_columns]
    if rule and rule.get("indexed_columns"):
        configured_columns = [key for key in list(rule["indexed_columns"]) if key in header_keys and key not in ignored_columns]
        if configured_columns:
            indexed_columns = configured_columns
    if not indexed_columns:
        indexed_columns = [key for key in header_keys if key]

    primary_key = str(rule.get("primary_key") or "").strip() if rule else ""
    if primary_key and primary_key not in header_keys:
        primary_key = ""
    if not primary_key:
        primary_key = _infer_primary_key(header_keys)
    normalized_primary_key = primary_key or None
    worksheet_entity_name = _build_worksheet_entity_name(source_name=source_name, worksheet_name=worksheet.name)

    rows: list[ExcelImportRow] = []
    for offset, raw_row in enumerate(body_rows, start=body_row_offset):
        padded_values = list(raw_row) + [""] * max(0, len(header_keys) - len(raw_row))
        display_cells: dict[str, str] = {}
        normalized_cells: dict[str, str] = {}
        for index, header_key in enumerate(header_keys):
            if not header_key or header_key in ignored_columns:
                continue
            value = str(padded_values[index]).strip()
            if not value:
                continue
            display_header = display_headers[index]
            display_cells[display_header] = value
            normalized_cells[header_key] = value
        if not normalized_cells:
            continue
        record_key_value = normalized_cells.get(normalized_primary_key or "", "")
        record_key = record_key_value or f"row-{offset}"
        entity_name = _build_record_entity_name(
            source_name=source_name,
            worksheet_name=worksheet.name,
            record_key=record_key,
        )
        entity_label = f"{worksheet.name}:{record_key}"
        content = _build_row_content(
            source_name=source_name,
            worksheet_name=worksheet.name,
            worksheet_entity_name=worksheet_entity_name,
            entity_name=entity_name,
            entity_label=entity_label,
            row_index=offset,
            header_pairs=header_pairs,
            normalized_cells=normalized_cells,
            indexed_columns=indexed_columns,
        )
        rows.append(
            ExcelImportRow(
                source_name=source_name,
                worksheet_name=worksheet.name,
                worksheet_index=worksheet.index,
                worksheet_entity_name=worksheet_entity_name,
                row_index=offset,
                record_key=record_key,
                entity_name=entity_name,
                entity_label=entity_label,
                content=content,
                display_cells=display_cells,
                normalized_cells=normalized_cells,
            )
        )

    summary_content = _build_sheet_summary_content(
        source_name=source_name,
        worksheet_name=worksheet.name,
        worksheet_entity_name=worksheet_entity_name,
        row_count=len(rows),
        display_headers=display_headers,
        indexed_columns=indexed_columns,
        primary_key=normalized_primary_key,
    )
    return ExcelImportSheet(
        source_name=source_name,
        worksheet_name=worksheet.name,
        worksheet_key=normalize_sheet_name(worksheet.name),
        worksheet_index=worksheet.index,
        entity_name=worksheet_entity_name,
        primary_key=normalized_primary_key,
        display_headers=display_headers,
        header_keys=header_keys,
        indexed_columns=indexed_columns,
        rows=rows,
        summary_content=summary_content,
    )


def _resolve_header_row_index(rows: list[list[str]], configured_header_row: int | None) -> int | None:
    if configured_header_row is not None and 1 <= configured_header_row <= len(rows):
        return configured_header_row
    if rows and _looks_like_header_row(rows[0]):
        return 1
    return None


def _build_header_pairs(raw_headers: list[str]) -> list[dict[str, str]]:
    header_pairs: list[dict[str, str]] = []
    seen_keys: dict[str, int] = {}
    width = max(len(raw_headers), 1)
    for index in range(width):
        raw_header = str(raw_headers[index]).strip() if index < len(raw_headers) else ""
        normalized_key = normalize_column_name(raw_header) or f"col_{index + 1}"
        seen_count = seen_keys.get(normalized_key, 0) + 1
        seen_keys[normalized_key] = seen_count
        key = normalized_key if seen_count == 1 else f"{normalized_key}_{seen_count}"
        display = raw_header or f"Column {index + 1}"
        if seen_count > 1:
            display = f"{display}_{seen_count}"
        header_pairs.append({"key": key, "display": display})
    return header_pairs


def _build_row_content(
    *,
    source_name: str,
    worksheet_name: str,
    worksheet_entity_name: str,
    entity_name: str,
    entity_label: str,
    row_index: int,
    header_pairs: list[dict[str, str]],
    normalized_cells: dict[str, str],
    indexed_columns: list[str],
) -> str:
    parts: list[str] = [
        f"workbook={source_name}",
        f"worksheet={worksheet_name}",
        f"worksheet_entity={worksheet_entity_name}",
        f"record_entity={entity_name}",
        f"record_label={entity_label}",
        f"row_index={row_index}",
    ]
    for pair in header_pairs:
        key = pair["key"]
        if key not in indexed_columns:
            continue
        value = normalized_cells.get(key)
        if not value:
            continue
        parts.append(f"{pair['display']}={value}")
    return "; ".join(parts)


def _build_sheet_summary_content(
    *,
    source_name: str,
    worksheet_name: str,
    worksheet_entity_name: str,
    row_count: int,
    display_headers: list[str],
    indexed_columns: list[str],
    primary_key: str | None,
) -> str:
    parts: list[str] = [
        f"workbook={source_name}",
        f"worksheet={worksheet_name}",
        f"worksheet_entity={worksheet_entity_name}",
        "summary_type=sheet_summary",
        f"row_count={row_count}",
        f"headers={' | '.join(display_headers)}" if display_headers else "headers=none",
    ]
    if indexed_columns:
        parts.append(f"indexed_columns={', '.join(indexed_columns)}")
    if primary_key:
        parts.append(f"primary_key={primary_key}")
    return "; ".join(parts)


def _build_worksheet_entity_name(*, source_name: str, worksheet_name: str) -> str:
    normalized_source_name = str(source_name or "").strip() or "workbook"
    return f"{normalized_source_name}::{worksheet_name}"


def _build_record_entity_name(*, source_name: str, worksheet_name: str, record_key: str) -> str:
    normalized_source_name = str(source_name or "").strip() or "workbook"
    return f"{normalized_source_name}::{worksheet_name}::{record_key}"


def _infer_primary_key(header_keys: list[str]) -> str:
    for candidate in header_keys:
        normalized_candidate = normalize_lookup_value(candidate)
        if normalized_candidate in {"id", "缂栧彿", "缂栫爜"} or normalized_candidate.endswith("id"):
            return candidate
    return header_keys[0] if header_keys else ""


def _looks_like_header_row(row: list[str]) -> bool:
    non_empty_cells = [cell.strip() for cell in row if str(cell or "").strip()]
    if len(non_empty_cells) < 2:
        return False
    lowered_cells = [cell.casefold() for cell in non_empty_cells]
    if len(set(lowered_cells)) != len(lowered_cells):
        return False
    return all(HEADER_VALUE_PATTERN.match(cell) for cell in non_empty_cells)

