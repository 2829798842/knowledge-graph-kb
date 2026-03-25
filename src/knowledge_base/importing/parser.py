"""Text extraction helpers for supported document types."""

import re
from pathlib import Path

from docx import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from src.knowledge_base.importing.excel.models import EXCEL_FILE_TYPES

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".txt", ".pdf", ".docx", *(f".{file_type}" for file_type in sorted(EXCEL_FILE_TYPES)))
SUPPORTED_EXTENSION_SET: set[str] = set(SUPPORTED_EXTENSIONS)
SUPPORTED_EXTENSION_DISPLAY: str = ", ".join(SUPPORTED_EXTENSIONS)

TEXT_EXTENSIONS: set[str] = {".txt"}
WORD_EXTENSIONS: set[str] = {".docx"}
SPREADSHEET_EXTENSIONS: set[str] = {f".{file_type}" for file_type in EXCEL_FILE_TYPES}

LIST_PREFIX_PATTERN = re.compile(r"^([*\-\u2022]|(\d+[\.\)]|[一二三四五六七八九十]+[、\)]))\s+")
SENTENCE_ENDING_PATTERN = re.compile(r"[。！？?!:：；;]$")


class UnsupportedFileTypeError(ValueError):
    """Raised when a file suffix is not supported by the import pipeline."""


def detect_file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSION_SET:
        display_suffix = suffix or "no extension"
        raise UnsupportedFileTypeError(
            f"Unsupported file type {display_suffix}. Supported types: {SUPPORTED_EXTENSION_DISPLAY}"
        )
    return suffix.removeprefix(".")


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return _extract_text_file(path)
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix in WORD_EXTENSIONS:
        return _extract_docx_text(path)
    if suffix in SPREADSHEET_EXTENSIONS:
        return _extract_spreadsheet_text(path)

    display_suffix = suffix or "no extension"
    raise UnsupportedFileTypeError(
        f"Unsupported file type {display_suffix}. Supported types: {SUPPORTED_EXTENSION_DISPLAY}"
    )


def _extract_text_file(path: Path) -> str:
    raw_bytes = path.read_bytes()
    candidate_encodings = _text_file_candidate_encodings(raw_bytes)
    raw_text: str | None = None

    for encoding in candidate_encodings:
        try:
            raw_text = raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
        if raw_text:
            break

    if raw_text is None:
        raw_text = raw_bytes.decode(encoding="utf-8", errors="ignore")

    cleaned_text = _cleanup_extracted_text(raw_text)
    if cleaned_text:
        return cleaned_text
    raise ValueError("Text file does not contain readable content.")


def _extract_pdf_text(path: Path) -> str:
    try:
        pdf_reader = PdfReader(str(path))
        page_texts = [page.extract_text() or "" for page in pdf_reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Failed to parse PDF content.") from exc

    cleaned_text = _cleanup_extracted_text("\n\n".join(page_texts))
    if cleaned_text:
        return cleaned_text
    raise ValueError("PDF does not contain readable text.")


def _extract_docx_text(path: Path) -> str:
    try:
        document = DocxDocument(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Failed to parse DOCX content.") from exc

    block_texts = _extract_docx_blocks(document)
    cleaned_text = _cleanup_extracted_text("\n\n".join(block_texts))
    if cleaned_text:
        return cleaned_text
    raise ValueError("DOCX does not contain readable text.")


def _extract_spreadsheet_text(path: Path) -> str:
    from src.knowledge_base.importing.excel import load_excel_document

    document = load_excel_document(path, file_type=path.suffix.removeprefix("."))
    cleaned_text = _cleanup_extracted_text(document.to_text())
    if cleaned_text:
        return cleaned_text
    raise ValueError("Spreadsheet does not contain readable content.")


def _text_file_candidate_encodings(raw_bytes: bytes) -> tuple[str, ...]:
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return ("utf-8-sig", "utf-8", "gb18030", "gbk")
    if raw_bytes.startswith(b"\xff\xfe"):
        return ("utf-16", "utf-16-le", "utf-8-sig", "gb18030", "gbk")
    if raw_bytes.startswith(b"\xfe\xff"):
        return ("utf-16", "utf-16-be", "utf-8-sig", "gb18030", "gbk")

    nul_ratio = raw_bytes.count(b"\x00") / max(len(raw_bytes), 1)
    if nul_ratio >= 0.2:
        return ("utf-16-le", "utf-16-be", "utf-8-sig", "gb18030", "gbk")
    return ("utf-8-sig", "gb18030", "gbk", "utf-16", "utf-16-le", "utf-16-be")


def _cleanup_extracted_text(text: str) -> str:
    normalized_text = text.replace("\u00a0", " ").replace("\ufeff", "").replace("\x00", "")
    normalized_text = re.sub(r"\r\n?", "\n", normalized_text)
    raw_blocks = re.split(r"\n\s*\n+", normalized_text)
    cleaned_blocks: list[str] = []

    for raw_block in raw_blocks:
        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in raw_block.split("\n")
            if line.strip()
        ]
        if not lines:
            continue
        cleaned_blocks.extend(_merge_wrapped_lines(lines))

    return "\n\n".join(cleaned_blocks).strip()


def _extract_docx_blocks(document: DocxDocument) -> list[str]:
    block_texts: list[str] = []

    for child in document.element.body.iterchildren():
        tag_name = child.tag.rsplit("}", maxsplit=1)[-1]
        if tag_name == "p":
            paragraph = Paragraph(child, document)
            paragraph_text = paragraph.text.strip()
            if paragraph_text:
                block_texts.append(paragraph_text)
            continue

        if tag_name == "tbl":
            table = Table(child, document)
            table_rows: list[str] = []
            for row in table.rows:
                row_cells: list[str] = []
                for cell in row.cells:
                    cell_text = " ".join(
                        paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip()
                    ).strip()
                    if cell_text:
                        row_cells.append(cell_text)
                if row_cells:
                    table_rows.append(" | ".join(row_cells))
            if table_rows:
                block_texts.append("\n".join(table_rows))

    return block_texts


def _merge_wrapped_lines(lines: list[str]) -> list[str]:
    merged_blocks: list[str] = []
    current_line = ""

    for line in lines:
        if not current_line:
            current_line = line
            continue

        if LIST_PREFIX_PATTERN.match(line) or SENTENCE_ENDING_PATTERN.search(current_line):
            merged_blocks.append(current_line)
            current_line = line
            continue

        if current_line.endswith("-"):
            current_line = f"{current_line[:-1]}{line.lstrip()}"
            continue

        current_line = f"{current_line} {line}"

    if current_line:
        merged_blocks.append(current_line)
    return merged_blocks
