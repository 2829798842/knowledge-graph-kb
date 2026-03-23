"""模块名称：services.parser_service

主要功能：解析文本、PDF 与 DOCX 文件内容并抽取纯文本。
"""

from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED_EXTENSIONS: set[str] = {".txt", ".pdf", ".docx"}


class UnsupportedFileTypeError(ValueError):
    """不支持文件类型异常。

    Attributes:
        args (tuple[object, ...]): 异常消息参数。
    """


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
        str: 抽取出的纯文本内容。

    Raises:
        UnsupportedFileTypeError: 当文件类型不被支持时抛出。
    """

    suffix: str = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        pdf_reader = PdfReader(str(path))
        page_texts: list[str] = [page.extract_text() or "" for page in pdf_reader.pages]
        return "\n".join(page_texts)
    if suffix == ".docx":
        docx_document = DocxDocument(str(path))
        paragraph_texts: list[str] = [paragraph.text for paragraph in docx_document.paragraphs]
        return "\n".join(paragraph_texts)
    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")
