"""模块名称：services.parser_service

主要功能：解析 TXT、PDF 与 DOCX 文件内容，并尽量还原自然段结构。
"""

import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED_EXTENSIONS: set[str] = {".txt", ".pdf", ".docx"}
LIST_PREFIX_PATTERN = re.compile(r"^([*\-•]|(\d+[\.\)]|[一二三四五六七八九十]+[、.]))\s+")
SENTENCE_ENDING_PATTERN = re.compile(r"[。！？!?；;：:]$")


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
        raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")
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
        return _cleanup_extracted_text("\n\n".join(page_texts))
    if suffix == ".docx":
        docx_document = DocxDocument(str(path))
        paragraph_texts: list[str] = [paragraph.text for paragraph in docx_document.paragraphs]
        return _cleanup_extracted_text("\n\n".join(paragraph_texts))
    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")


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
