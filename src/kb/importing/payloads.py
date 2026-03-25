"""知识库导入载荷归一化模块。

将上传文件、粘贴文本、目录扫描和结构化 JSON 输入统一整理成内部导入项。
"""

from typing import Any


def build_text_import_item(
    *,
    name: str,
    text: str,
    source_kind: str,
    input_mode: str,
    strategy: str,
    file_type: str | None = None,
    storage_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建文本导入项。"""

    return {
        "name": name,
        "text": text,
        "source_kind": source_kind,
        "input_mode": input_mode,
        "strategy": strategy,
        "file_type": file_type,
        "storage_path": storage_path,
        "metadata": metadata or {},
        "structured_entities": [],
        "structured_relations": [],
        "structured_paragraphs": [],
    }


def build_structured_import_item(
    *,
    name: str,
    payload: dict[str, Any],
    source_kind: str,
    input_mode: str,
    strategy: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建结构化导入项。"""

    paragraphs: list[dict[str, Any]] = normalize_structured_paragraphs(payload.get("paragraphs"))
    text: str = "\n\n".join(paragraph["content"] for paragraph in paragraphs)
    return {
        "name": name,
        "text": text,
        "source_kind": source_kind,
        "input_mode": input_mode,
        "strategy": strategy,
        "file_type": str(payload.get("file_type") or "json"),
        "storage_path": None,
        "metadata": {**(metadata or {}), "schema": str(payload.get("schema") or "structured")},
        "structured_entities": normalize_structured_entities(payload.get("entities")),
        "structured_relations": normalize_structured_relations(payload.get("relations")),
        "structured_paragraphs": paragraphs,
    }


def normalize_structured_paragraphs(raw_value: Any) -> list[dict[str, Any]]:
    """归一化结构化段落列表。"""

    if not isinstance(raw_value, list):
        return []
    normalized_rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if isinstance(item, dict):
            content: str = str(item.get("content") or "").strip()
            if not content:
                continue
            normalized_rows.append(
                {
                    "position": int(item.get("position", index)),
                    "content": content,
                    "knowledge_type": str(item.get("knowledge_type", "mixed")),
                    "metadata": dict(item.get("metadata", {})),
                }
            )
            continue
        content = str(item).strip()
        if content:
            normalized_rows.append(
                {
                    "position": index,
                    "content": content,
                    "knowledge_type": "mixed",
                    "metadata": {},
                }
            )
    return normalized_rows


def normalize_structured_entities(raw_value: Any) -> list[dict[str, Any]]:
    """归一化结构化实体列表。"""

    if not isinstance(raw_value, list):
        return []
    normalized_rows: list[dict[str, Any]] = []
    for item in raw_value:
        if not isinstance(item, dict):
            continue
        name: str = str(item.get("name") or item.get("display_name") or "").strip()
        if not name:
            continue
        normalized_rows.append(
            {
                "name": name,
                "description": str(item.get("description") or "").strip(),
                "metadata": dict(item.get("metadata", {})),
            }
        )
    return normalized_rows


def normalize_structured_relations(raw_value: Any) -> list[dict[str, Any]]:
    """归一化结构化关系列表。"""

    if not isinstance(raw_value, list):
        return []
    normalized_rows: list[dict[str, Any]] = []
    for item in raw_value:
        if not isinstance(item, dict):
            continue
        subject: str = str(item.get("subject") or item.get("source") or "").strip()
        object_name: str = str(item.get("object") or item.get("target") or "").strip()
        predicate: str = str(item.get("predicate") or item.get("relation") or "").strip()
        if not subject or not object_name or not predicate:
            continue
        normalized_rows.append(
            {
                "subject": subject,
                "predicate": predicate,
                "object": object_name,
                "confidence": float(item.get("confidence") or item.get("weight") or 1.0),
                "metadata": dict(item.get("metadata", {})),
            }
        )
    return normalized_rows
