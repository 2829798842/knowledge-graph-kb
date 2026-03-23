"""模块名称：tests.test_graph_service

主要功能：验证图谱服务中的实体命中规则能避免短词误匹配。
"""

from src.services.graph_service import chunk_mentions_entity


def test_chunk_mentions_entity_respects_word_boundaries():
    """验证实体匹配会尊重词边界而不是简单子串包含。"""

    assert chunk_mentions_entity("Alice founded Acme Robotics.", "Acme")
    assert chunk_mentions_entity("The AI system improved search.", "AI")
    assert not chunk_mentions_entity("The team said the rollout was stable.", "AI")
    assert not chunk_mentions_entity("Acmeology is not the same company.", "Acme")
