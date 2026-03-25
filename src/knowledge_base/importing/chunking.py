"""提供文本清洗、token 统计与按自然段优先的分块能力。
"""

import re

import tiktoken

TOKEN_ENCODER_NAME: str = "cl100k_base"
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n{2,}")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？!?；;：:.])\s+")


def normalize_text(text: str) -> str:
    """清洗文本中的换行与空白。

    Args:
        text: 原始文本内容。

    Returns:
        str: 规整后的文本内容。
    """

    compact_text: str = re.sub(r"\r\n?", "\n", text)
    compact_text = re.sub(r"[ \t]+\n", "\n", compact_text)
    compact_text = re.sub(r"\n[ \t]+", "\n", compact_text)
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
    """按自然段优先将文本切分为可重叠的片段。

    Args:
        text: 原始文本内容。
        max_tokens: 单块允许的最大 token 数。
        overlap_tokens: 相邻两块之间保留的重叠 token 数。

    Returns:
        list[str]: 切分后的文本块列表。
    """

    normalized_text: str = normalize_text(text)
    if not normalized_text:
        return []
    if count_tokens(normalized_text) <= max_tokens:
        return [normalized_text]

    semantic_segments: list[str] = _build_semantic_segments(normalized_text, max_tokens=max_tokens)
    if not semantic_segments:
        return []

    chunks: list[str] = []
    current_segments: list[str] = []

    for segment in semantic_segments:
        candidate_segments: list[str] = [*current_segments, segment]
        if current_segments and count_tokens(_join_segments(candidate_segments)) > max_tokens:
            chunks.append(_join_segments(current_segments))
            current_segments = _tail_overlap_segments(current_segments, overlap_tokens=overlap_tokens)
            while current_segments and count_tokens(_join_segments([*current_segments, segment])) > max_tokens:
                current_segments = current_segments[1:]

        current_segments.append(segment)

    if current_segments:
        chunks.append(_join_segments(current_segments))
    return chunks


def _build_semantic_segments(text: str, *, max_tokens: int) -> list[str]:
    """构建优先遵循段落与句子边界的语义片段。

    Args:
        text: 规整后的文本。
        max_tokens: 单个片段允许的最大 token 数。

    Returns:
        list[str]: 语义片段列表。
    """

    paragraphs: list[str] = [paragraph.strip() for paragraph in PARAGRAPH_SPLIT_PATTERN.split(text) if paragraph.strip()]
    segments: list[str] = []

    for paragraph in paragraphs:
        if count_tokens(paragraph) <= max_tokens:
            segments.append(paragraph)
            continue
        segments.extend(_split_oversized_paragraph(paragraph, max_tokens=max_tokens))

    return segments


def _split_oversized_paragraph(paragraph: str, *, max_tokens: int) -> list[str]:
    """将超长段落进一步按句子或 token 窗口拆分。

    Args:
        paragraph: 超长段落文本。
        max_tokens: 单个片段允许的最大 token 数。

    Returns:
        list[str]: 拆分后的片段列表。
    """

    sentences: list[str] = [sentence.strip() for sentence in SENTENCE_SPLIT_PATTERN.split(paragraph) if sentence.strip()]
    if len(sentences) <= 1:
        return _split_with_token_window(paragraph, max_tokens=max_tokens, overlap_tokens=0)

    grouped_segments: list[str] = []
    current_sentences: list[str] = []

    for sentence in sentences:
        if count_tokens(sentence) > max_tokens:
            if current_sentences:
                grouped_segments.append(" ".join(current_sentences))
                current_sentences = []
            grouped_segments.extend(_split_with_token_window(sentence, max_tokens=max_tokens, overlap_tokens=0))
            continue

        candidate_text: str = " ".join([*current_sentences, sentence])
        if current_sentences and count_tokens(candidate_text) > max_tokens:
            grouped_segments.append(" ".join(current_sentences))
            current_sentences = [sentence]
            continue

        current_sentences.append(sentence)

    if current_sentences:
        grouped_segments.append(" ".join(current_sentences))
    return grouped_segments


def _split_with_token_window(text: str, *, max_tokens: int, overlap_tokens: int) -> list[str]:
    """退化为基于 token 窗口的切分方式。

    Args:
        text: 待切分文本。
        max_tokens: 单块允许的最大 token 数。
        overlap_tokens: 相邻两块之间保留的重叠 token 数。

    Returns:
        list[str]: 切分后的文本块列表。
    """

    encoder = token_encoder()
    token_ids: list[int] = encoder.encode(text)
    if len(token_ids) <= max_tokens:
        return [text.strip()]

    effective_overlap: int = min(max(overlap_tokens, 0), max_tokens - 1)
    step_tokens: int = max(1, max_tokens - effective_overlap)
    chunks: list[str] = []

    for start_index in range(0, len(token_ids), step_tokens):
        end_index: int = min(start_index + max_tokens, len(token_ids))
        chunk_text: str = encoder.decode(token_ids[start_index:end_index]).strip()
        if chunk_text:
            chunks.append(chunk_text)
        if end_index >= len(token_ids):
            break
    return chunks


def _tail_overlap_segments(segments: list[str], *, overlap_tokens: int) -> list[str]:
    """选取尾部语义片段作为下一块的重叠上下文。

    Args:
        segments: 当前块中的语义片段列表。
        overlap_tokens: 目标重叠 token 数。

    Returns:
        list[str]: 作为下一块前缀的尾部片段列表。
    """

    if overlap_tokens <= 0 or not segments:
        return []

    overlap_segments: list[str] = []
    for segment in reversed(segments):
        overlap_segments.insert(0, segment)
        if count_tokens(_join_segments(overlap_segments)) >= overlap_tokens:
            break
    return overlap_segments


def _join_segments(segments: list[str]) -> str:
    """使用双换行拼接语义片段。

    Args:
        segments: 待拼接片段列表。

    Returns:
        str: 拼接后的文本。
    """

    return "\n\n".join(segment.strip() for segment in segments if segment.strip())
