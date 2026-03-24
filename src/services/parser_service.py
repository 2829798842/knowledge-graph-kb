"""模块名称：services.parser_service

主要功能：解析 TXT、PDF 与 DOCX 文件内容，并尽量还原自然段结构。
"""

import re
from pathlib import Path

from docx import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

SUPPORTED_EXTENSIONS: set[str] = {".txt", ".pdf", ".docx"}
LIST_PREFIX_PATTERN = re.compile(r"^([*\-\u2022]|(\d+[\.\)]|[一二三四五六七八九十]+[、\.]))\s+")
SENTENCE_ENDING_PATTERN = re.compile(r"[。！？!?：:]$")


class UnsupportedFileTypeError(ValueError):
    """不支持的文件类型异常。"""


def detect_file_type(path: Path) -> str:
    """根据扩展名识别文件类型。

    Args:
        path: 文件路径。

    Returns:
        str: 不带点号的文件类型字符串。

    Raises:
        UnsupportedFileTypeError: 当扩展名不在支持列表中时抛出。
    """

    suffix: str = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        display_suffix: str = suffix or "无扩展名"
        raise UnsupportedFileTypeError(f"暂不支持 {display_suffix}，目前仅支持 .txt、.pdf、.docx")
    return suffix.removeprefix(".")


def extract_text(path: Path) -> str:
    """从文件中抽取可索引文本。

    Args:
        path: 待解析文件路径。

    Returns:
        str: 经过段落清洗后的纯文本内容。

    Raises:
        UnsupportedFileTypeError: 当文件类型不被支持时抛出。
    """

    suffix: str = path.suffix.lower()
    if suffix == ".txt":
        return _cleanup_extracted_text(path.read_text(encoding="utf-8", errors="ignore"))

    if suffix == ".pdf":
        pdf_reader = PdfReader(str(path))
        page_texts: list[str] = [page.extract_text() or "" for page in pdf_reader.pages]
        cleaned_text: str = _cleanup_extracted_text("\n\n".join(page_texts))
        if cleaned_text:
            return cleaned_text
        raise ValueError("PDF 中未提取到可用文本，请确认文件不是扫描件或图片版。")

    if suffix == ".docx":
        docx_document = DocxDocument(str(path))
        block_texts: list[str] = _extract_docx_blocks(docx_document)
        cleaned_text = _cleanup_extracted_text("\n\n".join(block_texts))
        if cleaned_text:
            return cleaned_text
        raise ValueError("Word 文档中未提取到可用文本，请确认文件内容不是空白。")

    raise UnsupportedFileTypeError(f"暂不支持 {suffix or '无扩展名'}，目前仅支持 .txt、.pdf、.docx")


def _cleanup_extracted_text(text: str) -> str:
    """清洗抽取文本中的换行与断行噪声。

    Args:
        text: 原始抽取文本。

    Returns:
        str: 更接近自然段的文本内容。
    """

    normalized_text: str = text.replace("\u00a0", " ")
    normalized_text = re.sub(r"\r\n?", "\n", normalized_text)
    raw_blocks: list[str] = re.split(r"\n\s*\n+", normalized_text)
    cleaned_blocks: list[str] = []

    for raw_block in raw_blocks:
        lines: list[str] = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in raw_block.split("\n")
            if line.strip()
        ]
        if not lines:
            continue
        cleaned_blocks.extend(_merge_wrapped_lines(lines))

    return "\n\n".join(cleaned_blocks).strip()


def _extract_docx_blocks(document: DocxDocument) -> list[str]:
    """按文档顺序提取 DOCX 中的段落与表格文本。

    Args:
        document: 已打开的 DOCX 文档对象。

    Returns:
        list[str]: 便于后续清洗的文本块列表。
    """

    block_texts: list[str] = []

    for child in document.element.body.iterchildren():
        tag_name: str = child.tag.rsplit("}", maxsplit=1)[-1]
        if tag_name == "p":
            paragraph = Paragraph(child, document)
            paragraph_text: str = paragraph.text.strip()
            if paragraph_text:
                block_texts.append(paragraph_text)
            continue

        if tag_name == "tbl":
            table = Table(child, document)
            table_rows: list[str] = []
            for row in table.rows:
                row_cells: list[str] = []
                for cell in row.cells:
                    cell_text: str = " ".join(
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
    """合并同一自然段中被错误折行的文本行。

    Args:
        lines: 同一段落块中的文本行列表。

    Returns:
        list[str]: 合并后的段落或列表项文本。
    """

    merged_blocks: list[str] = []
    current_line: str = ""

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
