"""Structured models and helpers for the Excel import pipeline."""

from dataclasses import dataclass
import re

EXCEL_FILE_TYPES: set[str] = {"xlsx", "xlsm", "xls"}
HEADER_VALUE_PATTERN = re.compile(r"^[A-Za-z_\-\u4e00-\u9fff][A-Za-z0-9_\-\s\u4e00-\u9fff/()%]*$")


@dataclass(frozen=True)
class SpreadsheetWorksheetData:
    name: str
    index: int
    rows: list[list[str]]


@dataclass(frozen=True)
class SpreadsheetDocumentData:
    file_type: str
    worksheets: list[SpreadsheetWorksheetData]

    def to_text(self) -> str:
        return "\n\n".join(
            _format_sheet_block(worksheet.name, worksheet.rows)
            for worksheet in self.worksheets
            if worksheet.rows
        ).strip()


@dataclass(frozen=True)
class ExcelImportRow:
    source_name: str
    worksheet_name: str
    worksheet_index: int
    worksheet_entity_name: str
    row_index: int
    record_key: str
    entity_name: str
    entity_label: str
    content: str
    display_cells: dict[str, str]
    normalized_cells: dict[str, str]


@dataclass(frozen=True)
class ExcelImportSheet:
    source_name: str
    worksheet_name: str
    worksheet_key: str
    worksheet_index: int
    entity_name: str
    primary_key: str | None
    display_headers: list[str]
    header_keys: list[str]
    indexed_columns: list[str]
    rows: list[ExcelImportRow]
    summary_content: str


def _format_sheet_block(sheet_name: str, rows: list[list[str]]) -> str:
    title = sheet_name.strip() or "Untitled worksheet"
    non_empty_rows = [row for row in rows if any(row)]
    if not non_empty_rows:
        return ""

    header_row = non_empty_rows[0]
    body_rows = non_empty_rows[1:]
    formatted_lines: list[str] = [f"Worksheet: {title}"]

    if body_rows and _looks_like_header_row(header_row):
        formatted_lines.append(f"Header: {_join_row_values(header_row)}")
        for row_index, row in enumerate(body_rows, start=2):
            record_parts: list[str] = []
            for column_index, header in enumerate(header_row):
                if column_index >= len(row):
                    continue
                value = row[column_index]
                if not value:
                    continue
                key = header or f"Column {column_index + 1}"
                record_parts.append(f"{key}={value}")
            extra_cells = row[len(header_row):]
            record_parts.extend(value for value in extra_cells if value)
            if record_parts:
                formatted_lines.append(f"Row {row_index}: {'; '.join(record_parts)}")
        return "\n".join(formatted_lines)

    for row_index, row in enumerate(non_empty_rows, start=1):
        formatted_lines.append(f"Row {row_index}: {_join_row_values(row)}")
    return "\n".join(formatted_lines)


def _looks_like_header_row(row: list[str]) -> bool:
    non_empty_cells = [cell.strip() for cell in row if cell.strip()]
    if len(non_empty_cells) < 2:
        return False
    lowered_cells = [cell.casefold() for cell in non_empty_cells]
    if len(set(lowered_cells)) != len(lowered_cells):
        return False
    return all(HEADER_VALUE_PATTERN.match(cell) for cell in non_empty_cells)


def _join_row_values(row: list[str]) -> str:
    return " | ".join(value for value in row if value)

