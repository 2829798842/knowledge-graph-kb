"""模块名称：services.chunking_service

主要功能：提供文本清洗、token 统计与重叠切块能力。
"""

import re

import tiktoken

TOKEN_ENCODER_NAME: str = "cl100k_base"


def normalize_text(text: str) -> str:
    """清洗文本中的换行与空白。

    Args:
        text: 原始文本内容。

    Returns:
        str: 规整后的文本内容。
    """

    compact_text: str = re.sub(r"\r\n?", "\n", text)
    compact_text = re.sub(r"\n{3,}", "\n\n", compact_text)
    return compact_text.strip()


def token_encoder():
    """获取 token 编码器。

    Returns:
        Encoding: `tiktoken` 提供的编码器实例。
    """

    return tiktoken.get_encoding(TOKEN_ENCODER_NAME)


def count_tokens(text: str) -> int:
    """统计文本 token 数量。

    Args:
        text: 待统计文本。

    Returns:
        int: 文本对应的 token 数量。
    """

    return len(token_encoder().encode(text))


def split_text(text: str, max_tokens: int = 600, overlap_tokens: int = 120) -> list[str]:
    """按 token 窗口将文本切分为重叠块。

    Args:
        text: 原始文本内容。
        max_tokens: 单块允许的最大 token 数。
        overlap_tokens: 相邻两块之间的重叠 token 数。

    Returns:
        list[str]: 切分后的文本块列表。
    """

    normalized_text: str = normalize_text(text)
    if not normalized_text:
        return []

    encoder = token_encoder()
    token_ids: list[int] = encoder.encode(normalized_text)
    if len(token_ids) <= max_tokens:
        return [normalized_text]

    # 使用滑动窗口重叠切块，避免关键句子被边界截断。
    step_tokens: int = max_tokens - overlap_tokens
    chunks: list[str] = []
    for start_index in range(0, len(token_ids), step_tokens):
        end_index: int = min(start_index + max_tokens, len(token_ids))
        chunk_text: str = encoder.decode(token_ids[start_index:end_index]).strip()
        if chunk_text:
            chunks.append(chunk_text)
        if end_index >= len(token_ids):
            break
    return chunks
