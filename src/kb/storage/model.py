"""模型配置存储。"""

from typing import Any

from ..database.sqlite import SQLiteGateway
from .common import DEFAULT_MODEL_CONFIG_ID, utc_now_iso


class ModelConfigStore:
    """负责持久化运行时模型配置。"""

    def __init__(self, gateway: SQLiteGateway) -> None:
        self.gateway = gateway

    def get(self) -> dict[str, Any] | None:
        """读取当前唯一一份模型配置。"""

        return self.gateway.fetch_one("SELECT * FROM model_config WHERE id = ?", (DEFAULT_MODEL_CONFIG_ID,))

    def upsert(
        self,
        *,
        provider: str,
        base_url: str,
        llm_model: str,
        embedding_model: str,
        api_key: str | None,
    ) -> dict[str, Any]:
        """写入或更新模型配置。"""

        existing = self.get()
        now = utc_now_iso()
        payload = {
            "id": DEFAULT_MODEL_CONFIG_ID,
            "provider": provider,
            "base_url": base_url,
            "llm_model": llm_model,
            "embedding_model": embedding_model,
            "api_key": api_key,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        with self.gateway.transaction() as connection:
            connection.execute(
                """
                INSERT INTO model_config (
                    id, provider, base_url, llm_model, embedding_model, api_key, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    llm_model = excluded.llm_model,
                    embedding_model = excluded.embedding_model,
                    api_key = excluded.api_key,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["provider"],
                    payload["base_url"],
                    payload["llm_model"],
                    payload["embedding_model"],
                    payload["api_key"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return payload
