"""封装兼容 OpenAI 的嵌入、抽取、问答与连通性测试调用。"""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from sqlmodel import Session

from src.config import Settings
from src.data import get_engine
from src.schemas import ExtractionResult, ExtractedEntity, ExtractedRelation
from src.services.model_config_service import ModelConfigurationService, RuntimeModelConfiguration

EXTRACTION_TEXT_LIMIT: int = 12000
MIN_RELATION_WEIGHT: float = 0.5
MAX_RELATION_WEIGHT: float = 3.0
CONNECTION_TEST_INPUT: str = "ping"


class OpenAiConfigurationError(RuntimeError):
    """当运行期模型配置不完整时抛出。"""


class OpenAiService:
    """使用当前生效的运行期配置调用兼容 OpenAI 的接口。"""

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.model_config_service: ModelConfigurationService = ModelConfigurationService(settings)
        self._client: OpenAI | None = None
        self._client_signature: tuple[str, str, str] | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """返回给定文本的嵌入向量。"""

        if not texts:
            return []

        runtime_config: RuntimeModelConfiguration = self._runtime_configuration()
        response = self._client_for(runtime_config).embeddings.create(
            model=runtime_config.embedding_model,
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
        """从文档窗口中抽取实体与关系。"""

        system_prompt: str = (
            "You extract a concise knowledge graph from document text. "
            "Return only JSON with keys entities and relations. "
            "Each entity must have name and description. "
            "Each relation must have source, target, relation, and weight. "
            "Avoid duplicates, vague filler entities, and unsupported relations."
        )
        user_prompt: str = (
            f"Document name: {document_name}\n"
            f"Window label: {window_label}\n\n"
            f"Document text:\n{text[:EXTRACTION_TEXT_LIMIT]}"
        )
        runtime_config: RuntimeModelConfiguration = self._runtime_configuration()
        raw_output: str = self._chat_completion(
            runtime_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        payload: dict[str, Any] = self._load_json(raw_output)
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
        """基于检索到的上下文片段生成可溯源答案。"""

        context_text: str = "\n\n".join(
            f"[{block['chunk_id']}] {block['document_name']}\n{block['excerpt']}" for block in context_blocks
        )
        runtime_config: RuntimeModelConfiguration = self._runtime_configuration()
        return self._chat_completion(
            runtime_config,
            system_prompt="Answer using only the supplied context and cite chunk ids inline when used.",
            user_prompt=f"User query: {query}\n\nContext:\n{context_text}",
        ).strip()

    def test_connection(self, runtime_config: RuntimeModelConfiguration) -> tuple[bool, bool]:
        """验证当前配置是否可以同时访问嵌入模型与通用模型接口。"""

        client: OpenAI = self._client_for(runtime_config)
        embedding_ok: bool = False
        llm_ok: bool = False

        try:
            embedding_response = client.embeddings.create(
                model=runtime_config.embedding_model,
                input=[CONNECTION_TEST_INPUT],
            )
            embedding_ok = bool(embedding_response.data)
        except Exception:  # noqa: BLE001
            embedding_ok = False

        try:
            llm_response: str = self._chat_completion(
                runtime_config,
                system_prompt="Reply with the single word ok.",
                user_prompt="Connection test.",
                max_tokens=8,
            )
            llm_ok = bool(llm_response.strip())
        except Exception:  # noqa: BLE001
            llm_ok = False

        return llm_ok, embedding_ok

    def _runtime_configuration(self) -> RuntimeModelConfiguration:
        """从持久化配置中读取当前生效的运行期模型配置。"""

        with Session(get_engine()) as session:
            return self.model_config_service.resolve_runtime_configuration(session)

    def _client_for(self, runtime_config: RuntimeModelConfiguration) -> OpenAI:
        """为当前配置创建或复用兼容 OpenAI 的客户端。"""

        if not runtime_config.api_key:
            raise OpenAiConfigurationError("尚未配置可用的 API Key，请先在模型配置面板中保存或填写后测试。")

        signature: tuple[str, str, str] = (
            runtime_config.provider,
            runtime_config.base_url,
            runtime_config.api_key,
        )
        if self._client is None or self._client_signature != signature:
            client_kwargs: dict[str, str] = {"api_key": runtime_config.api_key}
            if runtime_config.base_url:
                client_kwargs["base_url"] = runtime_config.base_url
            self._client = OpenAI(**client_kwargs)
            self._client_signature = signature
        return self._client

    def _chat_completion(
        self,
        runtime_config: RuntimeModelConfiguration,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        """调用兼容 OpenAI 的聊天补全接口，并仅处理文本内容。"""

        request_kwargs: dict[str, Any] = {
            "model": runtime_config.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens

        response = self._client_for(runtime_config).chat.completions.create(**request_kwargs)
        message_content: Any = response.choices[0].message.content if response.choices else ""
        return self._message_content_to_text(message_content)

    def _message_content_to_text(self, content: Any) -> str:
        """将兼容 OpenAI 的消息内容规整为纯文本。"""

        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value: Any = item.get("text")
                    if isinstance(text_value, str):
                        parts.append(text_value)
                        continue
                text_attr: Any = getattr(item, "text", None)
                if isinstance(text_attr, str):
                    parts.append(text_attr)
            return "".join(parts)
        return str(content)

    def _coerce_weight(self, raw_weight: Any) -> float:
        """将关系权重限制在安全范围内。"""

        try:
            weight: float = float(raw_weight)
        except (TypeError, ValueError):
            return 1.0
        return max(MIN_RELATION_WEIGHT, min(MAX_RELATION_WEIGHT, weight))

    def _load_json(self, raw_text: str) -> dict[str, Any]:
        """从模型返回内容中提取 JSON 对象。"""

        fenced_match = re.search(r"```json\s*(\{.*\})\s*```", raw_text, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1))

        brace_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group(1))

        return json.loads(raw_text)
