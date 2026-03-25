"""选择导入分块策略的辅助函数。"""

from pathlib import Path
import re

from src.config import Settings
from src.knowledge_base.importing.chunking import count_tokens, split_text

VALID_IMPORT_STRATEGIES: set[str] = {"auto", "narrative", "factual", "quote"}
SPREADSHEET_EXTENSIONS: set[str] = {".xlsx", ".xlsm", ".xls"}
QUOTE_LINE_SPLIT_PATTERN = re.compile(r"\n+")
FACTUAL_HINT_PATTERN = re.compile(r"(^|\n)\s*(\d+[\.\)]|[-*]|\d+[.)]?\s+|[一二三四五六七八九十]\.)")
NARRATIVE_HINT_PATTERN = re.compile(r"(because|therefore|however|for example|conclusion|总结|首先|其次|最后|另外|另外)", re.IGNORECASE)


def normalize_strategy(value: str | None) -> str:
    """将策略归一化并限制在支持的范围内。"""

    strategy: str = str(value or "auto").strip().lower()
    if strategy not in VALID_IMPORT_STRATEGIES:
        return "auto"
    return strategy


def select_strategy(*, requested_strategy: str, text: str, file_name: str | None = None) -> str:
    """根据请求和输入特征选择策略。"""

    normalized_strategy: str = normalize_strategy(requested_strategy)
    if normalized_strategy != "auto":
        return normalized_strategy

    normalized_text: str = text.strip()
    normalized_file_name: str = str(file_name or "").strip()
    file_extension: str = Path(normalized_file_name).suffix.lower()
    if file_extension in SPREADSHEET_EXTENSIONS:
        return "factual"
    if not normalized_text:
        return "factual"

    lines: list[str] = [line.strip() for line in QUOTE_LINE_SPLIT_PATTERN.split(normalized_text) if line.strip()]
    short_line_count: int = len([line for line in lines if len(line) <= 24])
    average_line_length: float = sum(len(line) for line in lines) / max(len(lines), 1)
    lower_text: str = normalized_text.lower()

    if len(lines) >= 8 and short_line_count / max(len(lines), 1) >= 0.7 and average_line_length <= 26:
        return "quote"
    if len(lines) >= 2 and NARRATIVE_HINT_PATTERN.search(normalized_text):
        return "narrative"
    if FACTUAL_HINT_PATTERN.search(lower_text):
        return "factual"
    return "factual"


def split_text_by_strategy(
    *,
    text: str,
    strategy: str,
    settings: Settings,
) -> list[str]:
    """按指定策略切分内容。"""

    normalized_strategy: str = normalize_strategy(strategy)
    if normalized_strategy == "quote":
        return _split_quote_text(
            text=text,
            max_tokens=max(120, settings.chunk_size_tokens // 2),
        )
    if normalized_strategy == "narrative":
        return split_text(
            text,
            max_tokens=settings.chunk_size_tokens + 120,
            overlap_tokens=settings.chunk_overlap_tokens + 40,
        )
    return split_text(
        text,
        max_tokens=settings.chunk_size_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
    )


def _split_quote_text(*, text: str, max_tokens: int) -> list[str]:
    """按引语风格片段切分文本。"""

    lines: list[str] = [line.strip() for line in QUOTE_LINE_SPLIT_PATTERN.split(text) if line.strip()]
    chunks: list[str] = []
    current_lines: list[str] = []
    for line in lines:
        candidate: str = "\n".join([*current_lines, line])
        if current_lines and count_tokens(candidate) > max_tokens:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            continue
        current_lines.append(line)
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks
