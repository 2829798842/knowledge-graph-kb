"""会话存储。"""

import json
from typing import Any
from uuid import uuid4

from ..database.sqlite import SQLiteGateway
from .common import utc_now_iso


class ConversationStore:
    """持久化问答会话与消息。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def create_session(self, *, title: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        session_id = str(uuid4())
        now = utc_now_iso()
        payload = {
            "id": session_id,
            "title": title,
            "metadata": dict(metadata or {}),
            "created_at": now,
            "updated_at": now,
            "last_message_at": None,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO chat_sessions (
                    id, title, metadata, created_at, updated_at, last_message_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["title"],
                    self.gateway.dump_json(payload["metadata"]),
                    payload["created_at"],
                    payload["updated_at"],
                    payload["last_message_at"],
                ),
            )
            connection.commit()
        return payload

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.gateway.fetch_all(
            """
            SELECT *
            FROM chat_sessions
            ORDER BY COALESCE(last_message_at, created_at) DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self.gateway.fetch_one("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))

    def update_session(self, session_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_session(session_id)
        encoded_fields: dict[str, Any] = {}
        for field_name, value in fields.items():
            if field_name == "metadata" and isinstance(value, dict):
                encoded_fields[field_name] = self.gateway.dump_json(value)
            else:
                encoded_fields[field_name] = value
        encoded_fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{field_name} = ?" for field_name in encoded_fields)
        params = tuple(encoded_fields.values()) + (session_id,)
        with self.gateway.transaction() as connection:
            connection.execute(f"UPDATE chat_sessions SET {assignments} WHERE id = ?", params)
            connection.commit()
        return self.get_session(session_id)

    def create_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        turn_index: int,
        citations: list[dict[str, Any]] | None = None,
        execution: dict[str, Any] | None = None,
        retrieval_trace: dict[str, Any] | None = None,
        highlighted_node_ids: list[str] | None = None,
        highlighted_edge_ids: list[str] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        message_id = str(uuid4())
        now = utc_now_iso()
        payload = {
            "id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "turn_index": turn_index,
            "citations": list(citations or []),
            "execution": dict(execution or {}),
            "retrieval_trace": dict(retrieval_trace or {}),
            "highlighted_node_ids": list(highlighted_node_ids or []),
            "highlighted_edge_ids": list(highlighted_edge_ids or []),
            "error": error,
            "created_at": now,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO chat_messages (
                    id, session_id, role, content, turn_index, citations, execution, retrieval_trace,
                    highlighted_node_ids, highlighted_edge_ids, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["session_id"],
                    payload["role"],
                    payload["content"],
                    payload["turn_index"],
                    json.dumps(payload["citations"], ensure_ascii=False),
                    self.gateway.dump_json(payload["execution"]),
                    self.gateway.dump_json(payload["retrieval_trace"]),
                    json.dumps(payload["highlighted_node_ids"], ensure_ascii=False),
                    json.dumps(payload["highlighted_edge_ids"], ensure_ascii=False),
                    payload["error"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.execute(
                """
                UPDATE chat_sessions
                SET last_message_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, session_id),
            )
            connection.commit()
        return self.get_message(message_id) or payload

    def list_messages(self, session_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT *
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC
        """
        params: tuple[Any, ...]
        if limit is None:
            params = (session_id,)
        else:
            sql += " LIMIT ?"
            params = (session_id, limit)
        return [self._normalize_message_row(row) for row in self.gateway.fetch_all(sql, params)]

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        row = self.gateway.fetch_one("SELECT * FROM chat_messages WHERE id = ?", (message_id,))
        if row is None:
            return None
        return self._normalize_message_row(row)

    def count_messages(self, session_id: str) -> int:
        row = self.gateway.fetch_one(
            "SELECT COUNT(*) AS message_count FROM chat_messages WHERE session_id = ?",
            (session_id,),
        )
        return int(row.get("message_count") or 0) if row is not None else 0

    def hydrate_session(self, session: dict[str, Any]) -> dict[str, Any]:
        return {**session, "messages": self.list_messages(str(session["id"]))}

    def _normalize_message_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized_row = dict(row)
        execution = normalized_row.get("execution")
        retrieval_trace = normalized_row.get("retrieval_trace")
        if not isinstance(execution, dict) or not dict(execution):
            normalized_row["execution"] = None
        if not isinstance(retrieval_trace, dict) or not dict(retrieval_trace):
            normalized_row["retrieval_trace"] = None
        return normalized_row
