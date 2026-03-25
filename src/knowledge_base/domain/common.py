"""知识库运行时共享的领域辅助函数。"""

from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO-8601 字符串。"""

    return datetime.now(timezone.utc).isoformat()


def build_source_node_id(source_id: str) -> str:
    return f"source:{source_id}"


def build_paragraph_node_id(paragraph_id: str) -> str:
    return f"paragraph:{paragraph_id}"


def build_entity_node_id(entity_id: str) -> str:
    return f"entity:{entity_id}"


def build_contains_edge_id(source_id: str, paragraph_id: str) -> str:
    return f"contains:{source_id}:{paragraph_id}"


def build_sheet_edge_id(source_id: str, entity_id: str) -> str:
    return f"sheet:{source_id}:{entity_id}"


def build_relation_edge_id(relation_id: str) -> str:
    return f"relation:{relation_id}"


def build_manual_edge_id(relation_id: str) -> str:
    return f"manual:{relation_id}"


def build_mention_edge_id(paragraph_id: str, entity_id: str) -> str:
    return f"mention:{paragraph_id}:{entity_id}"


@dataclass(frozen=True, slots=True)
class RuntimeModelConfiguration:
    """用于 OpenAI 兼容调用的运行时配置。"""

    provider: str
    base_url: str
    api_key: str
    llm_model: str
    embedding_model: str
    api_key_source: str
