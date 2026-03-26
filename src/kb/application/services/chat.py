"""问答会话服务"""

from typing import Any

from src.config import Settings
from src.kb.providers import OpenAiConfigurationError, OpenAiRequestError
from src.kb.storage import ConversationStore
from src.utils.logger import get_logger

from .answer import AnswerService

logger = get_logger(__name__)


class ConversationService:
    """管理持久化问答会话与消息"""

    DEFAULT_SESSION_TITLE = "新对话"

    def __init__(
        self,
        *,
        settings: Settings,
        store: ConversationStore,
        answer_service: AnswerService,
    ) -> None:
        self.settings = settings
        self.store = store
        self.answer_service = answer_service

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_sessions(limit=limit)

    def create_session(self, *, title: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_title = str(title or "").strip() or self.DEFAULT_SESSION_TITLE
        session = self.store.create_session(title=normalized_title, metadata=metadata)
        logger.info("Created chat session: session_id=%s title=%s", str(session.get("id") or ""), normalized_title)
        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self.store.get_session(session_id)
        if session is None:
            logger.debug("聊天会话不存在：session_id=%s", session_id)
            return None
        logger.debug("开始回读聊天会话：session_id=%s", session_id)
        return self._hydrate_session_with_rendering(session)

    def post_user_message(
        self,
        *,
        session_id: str,
        content: str,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        if session is None:
            raise ValueError("Chat session not found.")

        normalized_content = str(content or "").strip()
        if not normalized_content:
            raise ValueError("Message content cannot be empty.")

        existing_messages = self.store.list_messages(session_id)
        user_turn_count = sum(1 for message in existing_messages if str(message.get("role") or "") == "user")
        turn_index = user_turn_count + 1
        logger.info(
            "Processing chat message: session_id=%s turn_index=%s query_length=%s source_count=%s worksheet_count=%s top_k=%s",
            session_id,
            turn_index,
            len(normalized_content),
            len(source_ids or []),
            len(worksheet_names or []),
            top_k or self.settings.query_context_chunks,
        )
        self.store.create_message(
            session_id=session_id,
            role="user",
            content=normalized_content,
            turn_index=turn_index,
        )
        self._update_session_after_user_message(
            session=session,
            session_id=session_id,
            content=normalized_content,
            existing_messages=existing_messages,
            source_ids=source_ids,
            worksheet_names=worksheet_names,
        )

        recent_history = self._history_context(existing_messages)
        logger.debug(
            "聊天上下文已准备：session_id=%s turn_index=%s history_message_count=%s history_turn_count=%s",
            session_id,
            turn_index,
            len(existing_messages),
            len(recent_history),
        )
        try:
            answer_payload = self.answer_service.answer(
                query=normalized_content,
                source_ids=source_ids,
                worksheet_names=worksheet_names,
                top_k=top_k or self.settings.query_context_chunks,
                conversation_history=recent_history,
            )
        except Exception as exc:
            self._persist_failed_assistant_message(
                session_id=session_id,
                turn_index=turn_index,
                exc=exc,
            )
            raise
        self.store.create_message(
            session_id=session_id,
            role="assistant",
            content=str(answer_payload["answer"]),
            turn_index=turn_index,
            citations=list(answer_payload.get("citations") or []),
            execution=dict(answer_payload.get("execution") or {}),
            retrieval_trace=dict(answer_payload.get("retrieval_trace") or {}),
            highlighted_node_ids=list(answer_payload.get("highlighted_node_ids") or []),
            highlighted_edge_ids=list(answer_payload.get("highlighted_edge_ids") or []),
        )
        refreshed_session = self.store.get_session(session_id)
        if refreshed_session is None:
            raise ValueError("Chat session could not be reloaded after message persistence.")
        hydrated_session = self._hydrate_session_with_rendering(refreshed_session)
        logger.info(
            "Chat message processed: session_id=%s turn_index=%s answer_status=%s retrieval_mode=%s citation_count=%s",
            session_id,
            turn_index,
            str(answer_payload.get("execution", {}).get("status") or "unknown"),
            str(answer_payload.get("execution", {}).get("retrieval_mode") or "none"),
            len(list(answer_payload.get("citations") or [])),
        )
        return hydrated_session

    def _hydrate_session_with_rendering(self, session: dict[str, Any]) -> dict[str, Any]:
        hydrated_session = self.store.hydrate_session(session)
        hydrated_messages: list[dict[str, Any]] = []
        assistant_count = 0
        citation_count = 0
        for message in list(hydrated_session.get("messages") or []):
            normalized_message = dict(message)
            if str(normalized_message.get("role") or "") == "assistant":
                assistant_count += 1
                citation_count += len(list(normalized_message.get("citations") or []))
                normalized_message["citations"] = self.answer_service.hydrate_citations(
                    list(normalized_message.get("citations") or [])
                )
            hydrated_messages.append(normalized_message)
        logger.debug(
            "聊天会话渲染补全完成：session_id=%s message_count=%s assistant_count=%s citation_count=%s",
            str(hydrated_session.get("id") or ""),
            len(hydrated_messages),
            assistant_count,
            citation_count,
        )
        return {**hydrated_session, "messages": hydrated_messages}

    def _update_session_after_user_message(
        self,
        *,
        session: dict[str, Any],
        session_id: str,
        content: str,
        existing_messages: list[dict[str, Any]],
        source_ids: list[str] | None,
        worksheet_names: list[str] | None,
    ) -> None:
        should_update_title = not existing_messages and str(session.get("title") or "").strip() == self.DEFAULT_SESSION_TITLE
        should_update_metadata = source_ids is not None or worksheet_names is not None
        if not should_update_title and not should_update_metadata:
            return

        update_payload: dict[str, Any] = {}
        if should_update_title:
            update_payload["title"] = self._title_from_content(content)
        if should_update_metadata:
            next_metadata = dict(session.get("metadata", {}))
            if source_ids is not None:
                next_metadata["source_ids"] = list(source_ids)
            if worksheet_names is not None:
                next_metadata["worksheet_names"] = list(worksheet_names)
            update_payload["metadata"] = next_metadata
        self.store.update_session(session_id, **update_payload)

    def _persist_failed_assistant_message(
        self,
        *,
        session_id: str,
        turn_index: int,
        exc: Exception,
    ) -> None:
        error_message = self._error_message_from_exception(exc)
        try:
            self.store.create_message(
                session_id=session_id,
                role="assistant",
                content=error_message,
                turn_index=turn_index,
                execution={
                    "status": "failed",
                    "retrieval_mode": "none",
                    "model_invoked": False,
                    "matched_paragraph_count": 0,
                    "message": error_message,
                },
                error=error_message,
            )
            logger.warning(
                "已为失败的问答请求补写助手错误消息：session_id=%s turn_index=%s error_type=%s",
                session_id,
                turn_index,
                exc.__class__.__name__,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "问答失败后补写助手错误消息时再次失败：session_id=%s turn_index=%s",
                session_id,
                turn_index,
            )

    def _error_message_from_exception(self, exc: Exception) -> str:
        if isinstance(exc, (OpenAiConfigurationError, OpenAiRequestError, ValueError)):
            message = str(exc).strip()
            if message:
                return message
        return "系统处理当前消息时失败，请稍后重试。"

    def _history_context(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        if not messages:
            return []
        history_window = max(0, self.settings.query_history_turns) * 2
        if history_window <= 0:
            return []
        recent_messages = messages[-history_window:]
        return [
            {
                "role": str(message.get("role") or ""),
                "content": str(message.get("content") or ""),
            }
            for message in recent_messages
            if str(message.get("content") or "").strip()
        ]

    def _title_from_content(self, content: str) -> str:
        compact = " ".join(content.split())
        if len(compact) <= 24:
            return compact
        return f"{compact[:24].rstrip()}..."
