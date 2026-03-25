"""问答模式下的多轮会话服务。"""

from typing import Any

from src.config import Settings
from src.kb.storage import ConversationStore
from src.utils.logger import get_logger

from .answer import AnswerService

logger = get_logger(__name__)


class ConversationService:
    """管理持久化的问答会话与消息记录。"""

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
        """按最近更新时间返回问答会话列表。"""

        return self.store.list_sessions(limit=limit)

    def create_session(self, *, title: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """创建一个新的问答会话。"""

        normalized_title = str(title or "").strip() or self.DEFAULT_SESSION_TITLE
        session = self.store.create_session(title=normalized_title, metadata=metadata)
        logger.info("已创建问答会话：session_id=%s title=%s", str(session.get("id") or ""), normalized_title)
        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """读取会话详情并补全消息列表。"""

        session = self.store.get_session(session_id)
        if session is None:
            return None
        return self.store.hydrate_session(session)

    def post_user_message(
        self,
        *,
        session_id: str,
        content: str,
        source_ids: list[str] | None = None,
        worksheet_names: list[str] | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        """写入用户消息、执行问答，并返回更新后的完整会话。"""

        session = self.store.get_session(session_id)
        if session is None:
            raise ValueError("未找到问答会话。")

        normalized_content = str(content or "").strip()
        if not normalized_content:
            raise ValueError("消息内容不能为空。")

        existing_messages = self.store.list_messages(session_id)
        user_turn_count = sum(1 for message in existing_messages if str(message.get("role") or "") == "user")
        turn_index = user_turn_count + 1
        logger.info(
            "开始处理问答消息：session_id=%s turn_index=%s query_length=%s source_count=%s worksheet_count=%s top_k=%s",
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

        recent_history = self._history_context(existing_messages)
        answer_payload = self.answer_service.answer(
            query=normalized_content,
            source_ids=source_ids,
            worksheet_names=worksheet_names,
            top_k=top_k or self.settings.query_context_chunks,
            conversation_history=recent_history,
        )
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

        if not existing_messages and str(session.get("title") or "").strip() == self.DEFAULT_SESSION_TITLE:
            self.store.update_session(
                session_id,
                title=self._title_from_content(normalized_content),
                metadata={
                    **dict(session.get("metadata", {})),
                    "source_ids": list(source_ids or []),
                    "worksheet_names": list(worksheet_names or []),
                },
            )
        elif source_ids is not None or worksheet_names is not None:
            self.store.update_session(
                session_id,
                metadata={
                    **dict(session.get("metadata", {})),
                    "source_ids": list(source_ids or []),
                    "worksheet_names": list(worksheet_names or []),
                },
            )
        refreshed_session = self.store.get_session(session_id)
        if refreshed_session is None:
            raise ValueError("消息已写入，但重新读取问答会话失败。")
        hydrated_session = self.store.hydrate_session(refreshed_session)
        logger.info(
            "问答消息处理完成：session_id=%s turn_index=%s answer_status=%s retrieval_mode=%s citation_count=%s",
            session_id,
            turn_index,
            str(answer_payload.get("execution", {}).get("status") or "unknown"),
            str(answer_payload.get("execution", {}).get("retrieval_mode") or "none"),
            len(list(answer_payload.get("citations") or [])),
        )
        return hydrated_session

    def _history_context(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        """截取参与当前轮问答的最近历史上下文。"""

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
        """从首条用户消息中生成默认会话标题。"""

        compact = " ".join(content.split())
        if len(compact) <= 24:
            return compact
        return f"{compact[:24].rstrip()}..."
