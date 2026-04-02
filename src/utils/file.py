"""提供文件名清洗等轻量级文件工具函数。"""

import re

SAFE_FILENAME_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_.-]+")


def sanitize_filename(filename: str) -> str:
    """清洗文件名，避免特殊字符影响落盘。

    Args:
        filename: 原始文件名。

    Returns:
        str: 仅保留安全字符后的文件名。
    """

    return SAFE_FILENAME_PATTERN.sub("_", filename)
