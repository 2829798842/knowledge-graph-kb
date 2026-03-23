"""模块名称：tests.test_chunking

主要功能：验证文本切块服务的 token 统计与重叠切块行为。
"""

from kb_graph.services.chunking_service import count_tokens, split_text


def test_split_text_creates_overlapping_chunks():
    """验证切块结果会保留重叠窗口并遵守最大 token 限制。"""

    text = " ".join(f"token-{index}" for index in range(500))

    chunks = split_text(text, max_tokens=80, overlap_tokens=20)

    assert len(chunks) > 1
    assert all(count_tokens(chunk) <= 80 for chunk in chunks)
    assert chunks[0] != chunks[1]
