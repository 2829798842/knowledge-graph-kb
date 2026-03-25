"""OpenAI 兼容模型网关。"""

from collections.abc import Callable
import json
import re
from time import perf_counter
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
from src.kb.common import RuntimeModelConfiguration
from src.utils.logger import get_logger

EXTRACTION_TEXT_LIMIT = 12000
MIN_RELATION_WEIGHT = 0.5
MAX_RELATION_WEIGHT = 3.0
CONNECTION_TEST_INPUT = "ping"
ANSWER_SYSTEM_PROMPT = (
    "You answer questions for a knowledge-base UI using only the supplied context. "
    "Reply in concise, natural Simplified Chinese. "
    "Answer the user's actual question directly instead of describing the retrieval process or the provided material. "
    "Do not mention chunk ids, UUIDs, reference ids, or raw retrieval metadata. "
    "Do not use template-like lead-ins such as 'the provided content' or 'most directly corresponds to' "
    "unless the user explicitly asks for a comparison. "
    "If the user asks what a number, label, or short identifier refers to, map it directly to the matching "
    "title or concept when the context clearly supports it. "
    "If the context is insufficient or genuinely ambiguous, say so briefly instead of guessing. "
    "The UI shows citations separately, so do not output inline citations or raw identifiers."
)
ANSWER_USER_PROMPT_SUFFIX = (
    "\n\nWrite a direct answer first. Keep a normal explanatory tone and avoid template-like framing."
)
ANSWER_HISTORY_PREFIX = "Recent conversation turns:\n"

logger = get_logger(__name__)


class OpenAiConfigurationError(RuntimeError):
    """运行时模型配置不完整时抛出。"""


class OpenAiRequestError(RuntimeError):
    """上游模型服务请求失败时抛出。"""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenAiGateway:
    """封装模型调用、向量生成与问答能力。

    Attributes:
        settings (Settings): 全局配置对象。
        runtime_config_provider (Callable[[], RuntimeModelConfiguration]): 运行时模型配置提供函数。
        _client (OpenAI | None): 缓存的 OpenAI 客户端。
        _client_signature (tuple[str, str, str] | None): 当前客户端签名，用于判断是否需要重建客户端。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        runtime_config_provider: Callable[[], RuntimeModelConfiguration],
    ) -> None:
        """初始化模型网关。

        Args:
            settings: 全局配置对象。
            runtime_config_provider: 运行时配置提供函数。
        """

        self.settings = settings
        self.runtime_config_provider = runtime_config_provider
        self._client: OpenAI | None = None
        self._client_signature: tuple[str, str, str] | None = None

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。

        Args:
            texts: 待生成向量的文本列表。

        Returns:
            list[list[float]]: 向量列表。
        """

        if not texts:
            return []
        runtime_config = self.runtime_config_provider()
        total_char_count = sum(len(text) for text in texts)
        max_char_count = max((len(text) for text in texts), default=0)
        logger.info(
            "开始请求文本向量：text_count=%s batch_size=%s provider=%s embedding_model=%s",
            len(texts),
            max(1, self.settings.embedding_batch_size),
            runtime_config.provider,
            runtime_config.embedding_model,
        )
        logger.debug(
            "文本向量请求参数：text_count=%s total_char_count=%s max_char_count=%s provider=%s embedding_model=%s",
            len(texts),
            total_char_count,
            max_char_count,
            runtime_config.provider,
            runtime_config.embedding_model,
        )
        client = self._client_for(runtime_config)
        batch_size = max(1, self.settings.embedding_batch_size)
        embeddings: list[list[float]] = []
        request_start = perf_counter()
        for start_index in range(0, len(texts), batch_size):
            batch_texts = texts[start_index : start_index + batch_size]
            batch_index = start_index // batch_size + 1
            batch_char_count = sum(len(text) for text in batch_texts)
            batch_start = perf_counter()
            logger.debug(
                "文本向量批次开始：batch_index=%s start_index=%s batch_text_count=%s batch_char_count=%s",
                batch_index,
                start_index,
                len(batch_texts),
                batch_char_count,
            )
            try:
                response = client.embeddings.create(
                    model=runtime_config.embedding_model,
                    input=batch_texts,
                )
            except Exception as exc:  # noqa: BLE001
                raise self._translate_client_error(exc) from exc
            batch_embeddings = [[float(value) for value in item.embedding] for item in response.data]
            embeddings.extend(batch_embeddings)
            logger.debug(
                "文本向量批次完成：batch_index=%s vector_count=%s dimension=%s elapsed_ms=%s",
                batch_index,
                len(batch_embeddings),
                len(batch_embeddings[0]) if batch_embeddings else 0,
                round((perf_counter() - batch_start) * 1000.0, 2),
            )
        logger.debug(
            "文本向量请求完成：text_count=%s vector_count=%s total_ms=%s",
            len(texts),
            len(embeddings),
            round((perf_counter() - request_start) * 1000.0, 2),
        )
        return embeddings

    def extract_document_graph(
        self,
        *,
        document_name: str,
        text: str,
        window_label: str = "window",
    ) -> dict[str, Any]:
        """抽取文档实体与关系图。

        Args:
            document_name: 文档名称。
            text: 待抽取文本。
            window_label: 抽取窗口标签。

        Returns:
            dict[str, Any]: 包含 entities 与 relations 的抽取结果。
        """

        runtime_config = self.runtime_config_provider()
        truncated_text = text[:EXTRACTION_TEXT_LIMIT]
        logger.info(
            "开始请求实体关系抽取：document_name=%s window_label=%s provider=%s llm_model=%s",
            document_name,
            window_label,
            runtime_config.provider,
            runtime_config.llm_model,
        )
        logger.debug(
            "实体关系抽取请求参数：document_name=%s window_label=%s text_length=%s truncated_length=%s provider=%s llm_model=%s",
            document_name,
            window_label,
            len(text),
            len(truncated_text),
            runtime_config.provider,
            runtime_config.llm_model,
        )
        request_start = perf_counter()
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
                f"Document text:\n{truncated_text}"
            ),
        )
        logger.debug(
            "实体关系抽取响应返回：document_name=%s window_label=%s raw_output_length=%s elapsed_ms=%s",
            document_name,
            window_label,
            len(raw_output),
            round((perf_counter() - request_start) * 1000.0, 2),
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
        logger.debug(
            "实体关系抽取结果整理完成：document_name=%s window_label=%s entity_count=%s relation_count=%s",
            document_name,
            window_label,
            len(entities),
            len(relations),
        )
        return {"entities": entities, "relations": relations}

    def generate_answer(
        self,
        query: str,
        context_blocks: list[dict[str, str]],
        *,
        conversation_turns: list[dict[str, str]] | None = None,
    ) -> str:
        """基于上下文片段生成问答结果。

        Args:
            query: 用户问题。
            context_blocks: 检索到的上下文片段。
            conversation_turns: 历史对话轮次。

        Returns:
            str: 生成的回答文本。
        """

        context_text = "\n\n".join(
            f"Snippet {index}\nSource: {block['document_name']}\nExcerpt: {block['excerpt']}"
            for index, block in enumerate(context_blocks, start=1)
        )
        history_text = ""
        if conversation_turns:
            serialized_turns = "\n".join(
                f"{turn['role']}: {turn['content']}"
                for turn in conversation_turns
                if str(turn.get("content") or "").strip()
            )
            if serialized_turns:
                history_text = f"{ANSWER_HISTORY_PREFIX}{serialized_turns}\n\n"
        runtime_config = self.runtime_config_provider()
        context_char_count = sum(len(block.get("excerpt", "")) for block in context_blocks)
        history_char_count = sum(len(turn.get("content", "")) for turn in (conversation_turns or []))
        logger.info(
            "开始请求问答生成：query_length=%s context_block_count=%s history_turn_count=%s provider=%s llm_model=%s",
            len(query),
            len(context_blocks),
            len(conversation_turns or []),
            runtime_config.provider,
            runtime_config.llm_model,
        )
        logger.debug(
            "问答生成请求参数：query_length=%s context_block_count=%s context_char_count=%s history_turn_count=%s history_char_count=%s provider=%s llm_model=%s",
            len(query),
            len(context_blocks),
            context_char_count,
            len(conversation_turns or []),
            history_char_count,
            runtime_config.provider,
            runtime_config.llm_model,
        )
        request_start = perf_counter()
        answer_text = self._chat_completion(
            runtime_config,
            system_prompt=ANSWER_SYSTEM_PROMPT,
            user_prompt=f"{history_text}User query: {query}\n\nContext snippets:\n{context_text}{ANSWER_USER_PROMPT_SUFFIX}",
        ).strip()
        logger.debug(
            "问答生成响应完成：query_length=%s answer_length=%s elapsed_ms=%s",
            len(query),
            len(answer_text),
            round((perf_counter() - request_start) * 1000.0, 2),
        )
        return answer_text

    def test_connection(self, runtime_config: RuntimeModelConfiguration) -> tuple[bool, bool]:
        """测试通用模型与嵌入模型连通性。

        Args:
            runtime_config: 待测试的运行时配置。

        Returns:
            tuple[bool, bool]: 第一个值表示通用模型是否可用，第二个值表示嵌入模型是否可用。
        """

        logger.info(
            "开始测试模型连通性：provider=%s base_url=%s llm_model=%s embedding_model=%s api_key_source=%s",
            runtime_config.provider,
            runtime_config.base_url,
            runtime_config.llm_model,
            runtime_config.embedding_model,
            runtime_config.api_key_source,
        )
        client = self._client_for(runtime_config)
        embedding_ok = False
        llm_ok = False
        try:
            embedding_start = perf_counter()
            logger.debug(
                "模型连通性嵌入测试开始：provider=%s embedding_model=%s base_url=%s",
                runtime_config.provider,
                runtime_config.embedding_model,
                runtime_config.base_url,
            )
            response = client.embeddings.create(
                model=runtime_config.embedding_model,
                input=[CONNECTION_TEST_INPUT],
            )
            embedding_ok = bool(response.data)
            logger.debug(
                "模型连通性嵌入测试完成：provider=%s embedding_ok=%s elapsed_ms=%s",
                runtime_config.provider,
                embedding_ok,
                round((perf_counter() - embedding_start) * 1000.0, 2),
            )
        except Exception:  # noqa: BLE001
            embedding_ok = False
        try:
            llm_start = perf_counter()
            logger.debug(
                "模型连通性通用模型测试开始：provider=%s llm_model=%s base_url=%s",
                runtime_config.provider,
                runtime_config.llm_model,
                runtime_config.base_url,
            )
            llm_response = self._chat_completion(
                runtime_config,
                system_prompt="Reply with the single word ok.",
                user_prompt="Connection test.",
                max_tokens=8,
            )
            llm_ok = bool(llm_response.strip())
            logger.debug(
                "模型连通性通用模型测试完成：provider=%s llm_ok=%s elapsed_ms=%s",
                runtime_config.provider,
                llm_ok,
                round((perf_counter() - llm_start) * 1000.0, 2),
            )
        except Exception:  # noqa: BLE001
            llm_ok = False
        logger.info(
            "模型连通性测试完成：provider=%s llm_ok=%s embedding_ok=%s",
            runtime_config.provider,
            llm_ok,
            embedding_ok,
        )
        return llm_ok, embedding_ok

    def _client_for(self, runtime_config: RuntimeModelConfiguration) -> OpenAI:
        """获取与当前配置匹配的客户端实例。

        Args:
            runtime_config: 运行时模型配置。

        Returns:
            OpenAI: 可复用的客户端实例。

        Raises:
            OpenAiConfigurationError: 当 API Key 缺失时抛出。
        """

        if not runtime_config.api_key:
            raise OpenAiConfigurationError("当前没有可用的 API Key，请先在模型配置中保存可用密钥。")
        signature = (
            runtime_config.provider,
            runtime_config.base_url,
            runtime_config.api_key,
        )
        if self._client is None or self._client_signature != signature:
            logger.info(
                "创建模型客户端：provider=%s base_url=%s api_key_source=%s",
                runtime_config.provider,
                runtime_config.base_url,
                runtime_config.api_key_source,
            )
            if runtime_config.base_url:
                self._client = OpenAI(api_key=runtime_config.api_key, base_url=runtime_config.base_url)
            else:
                self._client = OpenAI(api_key=runtime_config.api_key)
            self._client_signature = signature
        else:
            logger.debug(
                "复用模型客户端：provider=%s base_url=%s api_key_source=%s",
                runtime_config.provider,
                runtime_config.base_url,
                runtime_config.api_key_source,
            )
        return self._client

    def _chat_completion(
        self,
        runtime_config: RuntimeModelConfiguration,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        """执行一次聊天补全请求。

        Args:
            runtime_config: 运行时模型配置。
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。
            max_tokens: 最大输出 token 数。

        Returns:
            str: 模型返回文本。
        """

        request_kwargs: dict[str, Any] = {
            "model": runtime_config.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens
        logger.debug(
            "聊天补全请求开始：provider=%s llm_model=%s message_count=%s system_prompt_length=%s user_prompt_length=%s max_tokens=%s",
            runtime_config.provider,
            runtime_config.llm_model,
            len(request_kwargs["messages"]),
            len(system_prompt),
            len(user_prompt),
            max_tokens,
        )
        request_start = perf_counter()
        try:
            response = self._client_for(runtime_config).chat.completions.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_client_error(exc) from exc
        message_content: Any = response.choices[0].message.content if response.choices else ""
        response_text = self._message_content_to_text(message_content)
        logger.debug(
            "聊天补全请求完成：provider=%s llm_model=%s choice_count=%s output_length=%s elapsed_ms=%s",
            runtime_config.provider,
            runtime_config.llm_model,
            len(response.choices or []),
            len(response_text),
            round((perf_counter() - request_start) * 1000.0, 2),
        )
        return response_text

    def _message_content_to_text(self, content: Any) -> str:
        """将 SDK 消息内容统一转换为文本。

        Args:
            content: SDK 返回的消息内容对象。

        Returns:
            str: 归一化后的文本内容。
        """

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
        """将关系权重转换并钳制到合法范围。

        Args:
            raw_weight: 原始权重值。

        Returns:
            float: 归一化后的权重。
        """

        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            return 1.0
        return max(MIN_RELATION_WEIGHT, min(MAX_RELATION_WEIGHT, weight))

    def _load_json(self, raw_text: str) -> dict[str, Any]:
        """从模型文本中提取 JSON 结构。

        Args:
            raw_text: 模型原始输出文本。

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

    def _log_client_error(self, exc: Exception) -> None:
        """记录上游客户端错误日志。

        Args:
            exc: 异常对象。
        """

        status_code = getattr(exc, "status_code", None)
        logger.warning(
            "模型服务请求失败：error_type=%s status_code=%s",
            exc.__class__.__name__,
            status_code,
        )

    def _translate_client_error(self, exc: Exception) -> OpenAiRequestError:
        """将 SDK 异常映射为统一业务异常。

        Args:
            exc: 原始异常。

        Returns:
            OpenAiRequestError: 统一异常对象。
        """

        if isinstance(exc, OpenAiRequestError):
            logger.warning(
                "模型服务请求失败：error_type=%s status_code=%s",
                exc.__class__.__name__,
                exc.status_code,
            )
            return exc
        if isinstance(exc, OpenAiConfigurationError):
            logger.warning("模型服务请求失败：当前运行时配置不完整。")
            return OpenAiRequestError(str(exc), status_code=503)
        if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
            self._log_client_error(exc)
            return OpenAiRequestError(
                "模型鉴权失败，请检查 API Key、Base URL 和提供商配置。",
                status_code=503,
            )
        if isinstance(exc, RateLimitError):
            self._log_client_error(exc)
            return OpenAiRequestError(
                "模型请求触发限流或额度耗尽，请稍后重试。",
                status_code=503,
            )
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            self._log_client_error(exc)
            return OpenAiRequestError(
                "无法连接模型服务，请检查网络连通性和 Base URL。",
                status_code=503,
            )
        if isinstance(exc, BadRequestError):
            self._log_client_error(exc)
            return OpenAiRequestError(
                "模型服务拒绝了请求，请检查模型名称与提供商兼容性。",
                status_code=502,
            )
        if isinstance(exc, APIStatusError):
            self._log_client_error(exc)
            return OpenAiRequestError(
                "模型服务返回了异常状态，请稍后重试。",
                status_code=502,
            )
        return OpenAiRequestError("模型服务发生未知错误，请检查运行时模型配置后重试。", status_code=502)



