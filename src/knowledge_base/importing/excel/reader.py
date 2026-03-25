"""Workbook readers for the Excel import pipeline."""

from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
from importlib import import_module
import re
from pathlib import Path
from typing import Any
import warnings

from .models import EXCEL_FILE_TYPES, SpreadsheetDocumentData, SpreadsheetWorksheetData


def supports_excel_file_type(file_type: str | None) -> bool:
    normalized_file_type = str(file_type or "").strip().lower().lstrip(".")
    return normalized_file_type in EXCEL_FILE_TYPES


def load_excel_document(path: Path, *, file_type: str | None = None) -> SpreadsheetDocumentData:
    normalized_file_type = str(file_type or path.suffix).strip().lower().lstrip(".")
    if normalized_file_type not in EXCEL_FILE_TYPES:
        raise ValueError(f"Unsupported Excel file type: {normalized_file_type or 'unknown'}")

    pandas_module = _import_pandas_module()
    if pandas_module is None:
        raise RuntimeError("pandas is required for Excel importing. Please install project dependencies first.")
    return _load_excel_document_with_pandas(path=path, file_type=normalized_file_type, pandas_module=pandas_module)


def _import_pandas_module():
    try:
        return import_module("pandas")
    except ImportError:
        return None


def _load_excel_document_with_pandas(*, path: Path, file_type: str, pandas_module: Any) -> SpreadsheetDocumentData:
    engine = _resolve_pandas_engine(file_type)
    with _suppress_openpyxl_data_validation_warning():
        excel_file = pandas_module.ExcelFile(path, engine=engine)
    try:
        workbook_sheet_names = list(excel_file.sheet_names)
        visible_sheet_names = _resolve_visible_sheet_names(
            path=path,
            file_type=file_type,
            workbook_sheet_names=workbook_sheet_names,
        )
        worksheets: list[SpreadsheetWorksheetData] = []
        for sheet_index, sheet_name in enumerate(workbook_sheet_names):
            if sheet_name not in visible_sheet_names:
                continue
            with _suppress_openpyxl_data_validation_warning():
                frame = excel_file.parse(sheet_name=sheet_name, header=None, dtype=object)
            rows = _dataframe_to_rows(frame)
            if rows:
                worksheets.append(
                    SpreadsheetWorksheetData(
                        name=str(sheet_name).strip() or f"Sheet{sheet_index + 1}",
                        index=sheet_index,
                        rows=rows,
                    )
                )
    finally:
        close = getattr(excel_file, "close", None)
        if callable(close):
            close()

    if not worksheets:
        raise ValueError("Excel workbook does not contain any readable non-empty worksheets.")
    return SpreadsheetDocumentData(file_type=file_type, worksheets=worksheets)


def _resolve_pandas_engine(file_type: str) -> str:
    if file_type in {"xlsx", "xlsm"}:
        return "openpyxl"
    return "xlrd"


def _resolve_visible_sheet_names(*, path: Path, file_type: str, workbook_sheet_names: list[str]) -> set[str]:
    if file_type not in {"xlsx", "xlsm"}:
        return set(workbook_sheet_names)
    try:
        from openpyxl import load_workbook
    except ImportError:
        return set(workbook_sheet_names)

    try:
        with _suppress_openpyxl_data_validation_warning():
            workbook = load_workbook(filename=str(path), data_only=True, read_only=True)
    except Exception:
        return set(workbook_sheet_names)

    try:
        return {
            str(worksheet.title).strip()
            for worksheet in workbook.worksheets
            if str(getattr(worksheet, "sheet_state", "visible")).lower() == "visible"
        } or set(workbook_sheet_names)
    finally:
        workbook.close()


def _dataframe_to_rows(frame: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    for _, row in frame.iterrows():
        row_values = row.tolist() if hasattr(row, "tolist") else list(row)
        normalized_row = [_normalize_cell_value(value) for value in row_values]
        if any(normalized_row):
            rows.append(normalized_row)
    return rows


def _normalize_cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return ""
        if value.is_integer():
            return str(int(value))
        return f"{value:.15g}"
    if isinstance(value, Decimal):
        normalized = format(value, "f").rstrip("0").rstrip(".")
        return normalized or "0"

    text = str(value).strip()
    if not text or text.casefold() == "nan":
        return ""
    text = text.replace("\u00a0", " ").replace("\ufeff", "").replace("\x00", "")
    return re.sub(r"[ \t]+", " ", text)


@contextmanager
def _suppress_openpyxl_data_validation_warning():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Data Validation extension is not supported and will be removed",
            category=UserWarning,
        )
        yield
