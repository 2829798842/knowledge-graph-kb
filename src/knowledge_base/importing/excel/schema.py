"""Excel schema helpers and normalization utilities."""

import json
import re
from pathlib import Path
from string import Formatter
from typing import Any

SPREADSHEET_SCHEMA_SUFFIX: str = ".schema.json"
DEFAULT_RELATION_PREDICATE: str = "references"
VALID_RELATION_DIRECTIONS: set[str] = {"forward", "reverse"}


def normalize_sheet_name(value: str) -> str:
    normalized: str = re.sub(r"\s+", " ", str(value or "").strip())
    return normalized.casefold()


def normalize_column_name(value: str) -> str:
    text: str = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\u3000", " ")
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.casefold()


def is_spreadsheet_schema_name(file_name: str) -> bool:
    return str(file_name or "").strip().lower().endswith(SPREADSHEET_SCHEMA_SUFFIX)


def workbook_stem_from_sidecar(file_name: str) -> str:
    normalized_name: str = Path(str(file_name or "").strip()).name
    if not is_spreadsheet_schema_name(normalized_name):
        return ""
    return normalized_name[: -len(SPREADSHEET_SCHEMA_SUFFIX)]


def load_spreadsheet_schema_bytes(contents: bytes, *, file_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(contents.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"{file_name} is not valid UTF-8 JSON.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{file_name} JSON parse failed: {exc.msg}") from exc
    return normalize_spreadsheet_schema(payload, file_name=file_name)


def load_spreadsheet_schema_path(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} is not valid UTF-8 JSON.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} JSON parse failed: {exc.msg}") from exc
    return normalize_spreadsheet_schema(payload, file_name=path.name)


def normalize_spreadsheet_schema(raw_value: Any, *, file_name: str = "schema") -> dict[str, Any]:
    if not isinstance(raw_value, dict):
        raise ValueError(f"{file_name} top level must be an object.")

    sheet_rules: dict[str, dict[str, Any]] = {}
    for worksheet_name, raw_rule in dict(raw_value.get("sheet_rules") or {}).items():
        if not isinstance(raw_rule, dict):
            continue
        normalized_sheet_key: str = normalize_sheet_name(str(worksheet_name))
        if not normalized_sheet_key:
            continue
        header_row = raw_rule.get("header_row")
        try:
            normalized_header_row = int(header_row) if header_row is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{file_name} sheet_rules.{worksheet_name}.header_row must be an integer.") from exc
        sheet_rules[normalized_sheet_key] = {
            "worksheet_name": str(worksheet_name).strip(),
            "header_row": normalized_header_row,
            "primary_key": normalize_column_name(str(raw_rule.get("primary_key") or "")) or None,
            "indexed_columns": _normalize_string_list(raw_rule.get("indexed_columns")),
            "ignored_columns": _normalize_string_list(raw_rule.get("ignored_columns")),
        }

    entity_rules: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(list(raw_value.get("entity_rules") or [])):
        if not isinstance(raw_rule, dict):
            continue
        worksheet_name: str = str(raw_rule.get("worksheet") or raw_rule.get("sheet") or "").strip()
        column_name: str = normalize_column_name(str(raw_rule.get("column") or ""))
        if not worksheet_name or not column_name:
            continue
        entity_rules.append(
            {
                "worksheet_name": worksheet_name,
                "worksheet_key": normalize_sheet_name(worksheet_name),
                "column": column_name,
                "display_template": str(raw_rule.get("display_template") or "").strip(),
                "description_template": str(raw_rule.get("description_template") or "").strip(),
                "entity_type": str(raw_rule.get("entity_type") or "cell_value").strip() or "cell_value",
                "rule_index": index,
            }
        )

    relation_rules: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(list(raw_value.get("relation_rules") or [])):
        if not isinstance(raw_rule, dict):
            continue
        source_sheet: str = str(raw_rule.get("source_sheet") or raw_rule.get("subject_sheet") or "").strip()
        target_sheet: str = str(raw_rule.get("target_sheet") or raw_rule.get("object_sheet") or "").strip()
        source_column: str = normalize_column_name(
            str(raw_rule.get("source_match_column") or raw_rule.get("foreign_key") or raw_rule.get("source_column") or "")
        )
        target_column: str = normalize_column_name(
            str(raw_rule.get("target_match_column") or raw_rule.get("primary_key") or raw_rule.get("target_column") or "")
        )
        predicate: str = str(raw_rule.get("predicate") or DEFAULT_RELATION_PREDICATE).strip() or DEFAULT_RELATION_PREDICATE
        direction: str = str(raw_rule.get("direction") or "forward").strip().lower()
        if not source_sheet or not target_sheet or not source_column or not target_column:
            continue
        if direction not in VALID_RELATION_DIRECTIONS:
            raise ValueError(f"{file_name} relation_rules[{index}].direction only supports forward/reverse.")
        relation_rules.append(
            {
                "source_worksheet_name": source_sheet,
                "source_worksheet_key": normalize_sheet_name(source_sheet),
                "target_worksheet_name": target_sheet,
                "target_worksheet_key": normalize_sheet_name(target_sheet),
                "source_match_column": source_column,
                "target_match_column": target_column,
                "predicate": predicate,
                "direction": direction,
                "rule_index": index,
            }
        )

    return {
        "sheet_rules": sheet_rules,
        "entity_rules": entity_rules,
        "relation_rules": relation_rules,
    }


def render_cell_template(template: str, *, cells: dict[str, str], fallback: str) -> str:
    normalized_template: str = str(template or "").strip()
    if not normalized_template:
        return fallback
    safe_cells: dict[str, str] = {normalize_column_name(key): str(value) for key, value in cells.items()}
    try:
        return normalized_template.format_map(_TemplateDict(safe_cells)).strip() or fallback
    except Exception:
        tokens = []
        for _, field_name, _, _ in Formatter().parse(normalized_template):
            if not field_name:
                continue
            value = safe_cells.get(normalize_column_name(field_name))
            if value:
                tokens.append(value)
        return " ".join(tokens).strip() or fallback


def singularize_token(value: str) -> str:
    token: str = normalize_column_name(value)
    if token.endswith("ies") and len(token) > 3:
        return f"{token[:-3]}y"
    if token.endswith("ses") and len(token) > 3:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 2:
        return token[:-1]
    return token


def _normalize_string_list(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        raw_items = [item.strip() for item in raw_value.split(",")]
    elif isinstance(raw_value, list):
        raw_items = [str(item).strip() for item in raw_value]
    else:
        raise ValueError("Sheet rule column configs must be a list or comma-delimited string.")
    normalized_items: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = normalize_column_name(raw_item)
        if not item or item in seen:
            continue
        normalized_items.append(item)
        seen.add(item)
    return normalized_items


class _TemplateDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""
