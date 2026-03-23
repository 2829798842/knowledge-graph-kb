"""模块名称：services.openai_service

主要功能：封装 OpenAI 嵌入、实体关系抽取与最终问答生成能力。
"""

import json
import re
from typing import Any

from openai import OpenAI

from kb_graph.config import Settings
from kb_graph.contracts.extraction_contracts import ExtractionResult, ExtractedEntity, ExtractedRelation

EXTRACTION_TEXT_LIMIT: int = 12000
MIN_RELATION_WEIGHT: float = 0.5
MAX_RELATION_WEIGHT: float = 3.0
EXTRACTION_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "name": "knowledge_graph_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["name", "description"],
                    "additionalProperties": False,
                },
            },
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "relation": {"type": "string"},
                        "weight": {"type": "number"},
                    },
                    "required": ["source", "target", "relation", "weight"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["entities", "relations"],
        "additionalProperties": False,
    },
}


class OpenAiConfigurationError(RuntimeError):
    """OpenAI 配置异常。

    Attributes:
        args (tuple[object, ...]): 异常消息参数。
    """


class OpenAiService:
    """OpenAI 服务封装。

    Attributes:
        settings (Settings): 当前应用配置。
        _client (OpenAI | None): 延迟初始化的 OpenAI 客户端。
    """

    def __init__(self, settings: Settings) -> None:
        """初始化 OpenAI 服务。

        Args:
            settings: 当前应用配置。
        """

        self.settings: Settings = settings
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """获取 OpenAI 客户端。

        Returns:
            OpenAI: 已初始化的客户端实例。

        Raises:
            OpenAiConfigurationError: 当缺失 API 密钥时抛出。
        """

        if not self.settings.openai_api_key:
            raise OpenAiConfigurationError("OPENAI_API_KEY is required to run ingestion and query flows.")
        if self._client is None:
            self._client = OpenAI(api_key=self.settings.openai_api_key)
        return self._client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本嵌入。

        Args:
            texts: 待嵌入文本列表。

        Returns:
            list[list[float]]: 与输入文本对应的嵌入向量列表。
        """

        if not texts:
            return []
        response = self.client.embeddings.create(
            model=self.settings.openai_embed_model,
            input=texts,
        )
        return [[float(value) for value in item.embedding] for item in response.data]

    def extract_entities(
        self,
        document_name: str,
        text: str,
        *,
        window_label: str = "window",
    ) -> ExtractionResult:
        """从文档内容中抽取实体与关系。

        Args:
            document_name: 文档名称。
            text: 窗口内文本。
            window_label: 当前抽取窗口标识。

        Returns:
            ExtractionResult: 抽取结果对象。
        """

        prompt: str = (
            "Extract a concise knowledge graph from the document window below. "
            "Focus on reusable concepts, named entities, events, systems, organizations, and concrete relationships. "
            "Avoid duplicates, generic filler concepts, and relations that are implied but unsupported.\n\n"
            f"Document name: {document_name}\n"
            f"Window label: {window_label}\n\n"
            f"Document text:\n{text[:EXTRACTION_TEXT_LIMIT]}"
        )
        response = self.client.responses.create(
            model=self.settings.openai_llm_model,
            instructions=(
                "Return only structured JSON that matches the supplied schema. "
                "Prefer stable entity names and concise descriptions."
            ),
            input=prompt,
            text={"format": EXTRACTION_RESPONSE_FORMAT},
        )
        payload: dict[str, Any] = self._load_json(response.output_text)
        entities: list[ExtractedEntity] = [
            ExtractedEntity(
                name=str(entity.get("name", "")).strip(),
                description=str(entity.get("description", "")).strip(),
            )
            for entity in payload.get("entities", [])
            if str(entity.get("name", "")).strip()
        ]
        relations: list[ExtractedRelation] = [
            ExtractedRelation(
                source=str(relation.get("source", "")).strip(),
                target=str(relation.get("target", "")).strip(),
                relation=str(relation.get("relation", "")).strip() or "related_to",
                weight=self._coerce_weight(relation.get("weight", 1.0)),
            )
            for relation in payload.get("relations", [])
            if str(relation.get("source", "")).strip() and str(relation.get("target", "")).strip()
        ]
        return ExtractionResult(entities=entities, relations=relations)

    def answer_query(self, query: str, context_blocks: list[dict[str, str]]) -> str:
        """基于上下文片段生成最终回答。

        Args:
            query: 用户问题。
            context_blocks: 已排序的上下文片段列表。

        Returns:
            str: 模型生成的回答文本。
        """

        context_text: str = "\n\n".join(
            f"[{block['chunk_id']}] {block['document_name']}\n{block['excerpt']}" for block in context_blocks
        )
        prompt: str = (
            "Answer the user query using only the supplied context. "
            "When you rely on a chunk, cite it inline using its bracketed chunk id.\n\n"
            f"User query: {query}\n\nContext:\n{context_text}"
        )
        response = self.client.responses.create(
            model=self.settings.openai_llm_model,
            instructions="Be concise, accurate, and explicit when the context is incomplete.",
            input=prompt,
        )
        return response.output_text.strip()

    def _coerce_weight(self, raw_weight: Any) -> float:
        """将关系权重约束到安全范围内。

        Args:
            raw_weight: 模型返回的原始权重。

        Returns:
            float: 归一化后的关系权重。
        """

        try:
            weight: float = float(raw_weight)
        except (TypeError, ValueError):
            return 1.0
        return max(MIN_RELATION_WEIGHT, min(MAX_RELATION_WEIGHT, weight))

    def _load_json(self, raw_text: str) -> dict[str, Any]:
        """从模型文本中提取 JSON 结构。

        Args:
            raw_text: 模型输出原始文本。

        Returns:
            dict[str, Any]: 解析后的 JSON 对象。
        """

        fenced_match = re.search(r"```json\s*(\{.*\})\s*```", raw_text, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1))

        brace_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group(1))

        return json.loads(raw_text)
