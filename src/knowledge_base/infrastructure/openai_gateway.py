"""OpenAI-compatible gateway for embeddings, extraction, and answering."""

from collections.abc import Callable
import json
import re
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from src.config import Settings
from src.knowledge_base.domain import RuntimeModelConfiguration

EXTRACTION_TEXT_LIMIT = 12000
MIN_RELATION_WEIGHT = 0.5
MAX_RELATION_WEIGHT = 3.0
CONNECTION_TEST_INPUT = "ping"


class OpenAiConfigurationError(RuntimeError):
    """Raised when the runtime model configuration is incomplete."""


class OpenAiRequestError(RuntimeError):
    """Raised when an upstream model provider request fails."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenAiGateway:
    """Call an OpenAI-compatible API using resolved runtime configuration."""

    def __init__(
        self,
        *,
        settings: Settings,
        runtime_config_provider: Callable[[], RuntimeModelConfiguration],
    ) -> None:
        self.settings = settings
        self.runtime_config_provider = runtime_config_provider
        self._client: OpenAI | None = None
        self._client_signature: tuple[str, str, str] | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        runtime_config = self.runtime_config_provider()
        client = self._client_for(runtime_config)
        batch_size = max(1, self.settings.embedding_batch_size)
        embeddings: list[list[float]] = []
        for start_index in range(0, len(texts), batch_size):
            batch_texts = texts[start_index : start_index + batch_size]
            try:
                response = client.embeddings.create(
                    model=runtime_config.embedding_model,
                    input=batch_texts,
                )
            except Exception as exc:  # noqa: BLE001
                raise self._translate_client_error(exc) from exc
            embeddings.extend([[float(value) for value in item.embedding] for item in response.data])
        return embeddings

    def extract_entities(
        self,
        *,
        document_name: str,
        text: str,
        window_label: str = "window",
    ) -> dict[str, Any]:
        runtime_config = self.runtime_config_provider()
        raw_output = self._chat_completion(
            runtime_config,
            system_prompt=(
                "You extract a concise knowledge graph from document text. "
                "Return only JSON with keys entities and relations. "
                "Each entity must have name and description. "
                "Each relation must have source, target, relation, and weight. "
                "Avoid duplicates, vague filler entities, and unsupported relations."
            ),
            user_prompt=(
                f"Document name: {document_name}\n"
                f"Window label: {window_label}\n\n"
                f"Document text:\n{text[:EXTRACTION_TEXT_LIMIT]}"
            ),
        )
        payload = self._load_json(raw_output)
        entities = [
            {
                "name": str(entity.get("name", "")).strip(),
                "description": str(entity.get("description", "")).strip(),
                "metadata": dict(entity.get("metadata", {})),
            }
            for entity in payload.get("entities", [])
            if str(entity.get("name", "")).strip()
        ]
        relations = [
            {
                "subject": str(relation.get("source", "")).strip(),
                "object": str(relation.get("target", "")).strip(),
                "predicate": str(relation.get("relation", "")).strip() or "related_to",
                "confidence": self._coerce_weight(relation.get("weight", 1.0)),
                "metadata": dict(relation.get("metadata", {})),
            }
            for relation in payload.get("relations", [])
            if str(relation.get("source", "")).strip() and str(relation.get("target", "")).strip()
        ]
        return {"entities": entities, "relations": relations}

    def answer_query(self, query: str, context_blocks: list[dict[str, str]]) -> str:
        context_text = "\n\n".join(
            f"[{block['chunk_id']}] {block['document_name']}\n{block['excerpt']}"
            for block in context_blocks
        )
        runtime_config = self.runtime_config_provider()
        return self._chat_completion(
            runtime_config,
            system_prompt="Answer using only the supplied context and cite chunk ids inline when used.",
            user_prompt=f"User query: {query}\n\nContext:\n{context_text}",
        ).strip()

    def test_connection(self, runtime_config: RuntimeModelConfiguration) -> tuple[bool, bool]:
        client = self._client_for(runtime_config)
        embedding_ok = False
        llm_ok = False
        try:
            response = client.embeddings.create(
                model=runtime_config.embedding_model,
                input=[CONNECTION_TEST_INPUT],
            )
            embedding_ok = bool(response.data)
        except Exception:  # noqa: BLE001
            embedding_ok = False
        try:
            llm_response = self._chat_completion(
                runtime_config,
                system_prompt="Reply with the single word ok.",
                user_prompt="Connection test.",
                max_tokens=8,
            )
            llm_ok = bool(llm_response.strip())
        except Exception:  # noqa: BLE001
            llm_ok = False
        return llm_ok, embedding_ok

    def _client_for(self, runtime_config: RuntimeModelConfiguration) -> OpenAI:
        if not runtime_config.api_key:
            raise OpenAiConfigurationError("当前没有可用的 API Key，请先在模型配置中保存可用密钥。")
        signature = (
            runtime_config.provider,
            runtime_config.base_url,
            runtime_config.api_key,
        )
        if self._client is None or self._client_signature != signature:
            if runtime_config.base_url:
                self._client = OpenAI(api_key=runtime_config.api_key, base_url=runtime_config.base_url)
            else:
                self._client = OpenAI(api_key=runtime_config.api_key)
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
        request_kwargs: dict[str, Any] = {
            "model": runtime_config.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens
        try:
            response = self._client_for(runtime_config).chat.completions.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_client_error(exc) from exc
        message_content: Any = response.choices[0].message.content if response.choices else ""
        return self._message_content_to_text(message_content)

    def _message_content_to_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        parts.append(text_value)
                        continue
                text_attr = getattr(item, "text", None)
                if isinstance(text_attr, str):
                    parts.append(text_attr)
            return "".join(parts)
        return str(content)

    def _coerce_weight(self, raw_weight: Any) -> float:
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            return 1.0
        return max(MIN_RELATION_WEIGHT, min(MAX_RELATION_WEIGHT, weight))

    def _load_json(self, raw_text: str) -> dict[str, Any]:
        fenced_match = re.search(r"```json\s*(\{.*\})\s*```", raw_text, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1))
        brace_match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group(1))
        return json.loads(raw_text)

    def _translate_client_error(self, exc: Exception) -> OpenAiRequestError:
        if isinstance(exc, OpenAiRequestError):
            return exc
        if isinstance(exc, OpenAiConfigurationError):
            return OpenAiRequestError(str(exc), status_code=503)
        if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
            return OpenAiRequestError(
                "模型服务认证失败，请检查 API Key、Base URL 和供应商配置是否正确。",
                status_code=503,
            )
        if isinstance(exc, RateLimitError):
            return OpenAiRequestError(
                "模型服务已触发限流或配额不足，请稍后重试并检查账户额度。",
                status_code=503,
            )
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return OpenAiRequestError(
                "无法连接到模型服务，请检查网络连通性和 Base URL 配置。",
                status_code=503,
            )
        if isinstance(exc, BadRequestError):
            return OpenAiRequestError(
                "模型服务拒绝了当前请求，请检查所选模型名称和供应商配置是否匹配。",
                status_code=502,
            )
        if isinstance(exc, APIStatusError):
            return OpenAiRequestError(
                "模型服务返回了异常响应，请稍后重试。",
                status_code=502,
            )
        return OpenAiRequestError("模型服务发生未知错误，请检查当前模型配置后重试。", status_code=502)
