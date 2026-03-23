"""应用配置与路径解析辅助工具。"""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR: Path = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """从环境变量加载的应用配置。"""

    app_name: str = "Knowledge Graph KB"
    database_url: str = "sqlite:///./data/app.db"
    model_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("MODEL_PROVIDER", "API_PROVIDER"),
    )
    model_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("MODEL_BASE_URL", "OPENAI_BASE_URL"),
    )
    vector_store_dir: str = Field(
        default="./data/faiss",
        validation_alias=AliasChoices("VECTOR_STORE_DIR", "FAISS_INDEX_DIR"),
    )
    model_config_secret_path: str = Field(
        default="./data/secrets/model_config.key",
        validation_alias=AliasChoices("MODEL_CONFIG_SECRET_PATH"),
    )
    upload_dir: str = "./data/uploads"
    frontend_dist_dir: str = "./frontend/dist"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "MODEL_API_KEY"),
    )
    openai_llm_model: str = Field(
        default="gpt-5.4-mini",
        validation_alias=AliasChoices("OPENAI_LLM_MODEL", "LLM_MODEL"),
    )
    openai_embed_model: str = Field(
        default="text-embedding-3-large",
        validation_alias=AliasChoices("OPENAI_EMBED_MODEL", "EMBEDDING_MODEL"),
    )
    chunk_size_tokens: int = 600
    chunk_overlap_tokens: int = 120
    query_seed_limit: int = 20
    query_context_chunks: int = 6
    graph_similarity_threshold: float = 0.78
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        populate_by_name=True,
    )

    @property
    def resolved_database_url(self) -> str:
        """当使用相对路径时，返回绝对的 SQLite 连接地址。"""

        prefix: str = "sqlite:///"
        if self.database_url.startswith(prefix) and not self.database_url.startswith(f"{prefix}/"):
            relative_path: str = self.database_url.replace(prefix, "", 1)
            absolute_path: Path = (ROOT_DIR / relative_path).resolve()
            return f"{prefix}{absolute_path.as_posix()}"
        return self.database_url

    @property
    def resolved_vector_store_dir(self) -> Path:
        """以绝对路径形式返回 FAISS 存储目录。"""

        return self._resolve_path(self.vector_store_dir)

    @property
    def resolved_upload_dir(self) -> Path:
        """以绝对路径形式返回上传目录。"""

        return self._resolve_path(self.upload_dir)

    @property
    def resolved_model_config_secret_path(self) -> Path:
        """返回持久化模型密钥所用的加密密钥文件路径。"""

        return self._resolve_path(self.model_config_secret_path)

    @property
    def resolved_frontend_dist_dir(self) -> Path:
        """以绝对路径形式返回前端构建产物目录。"""

        return self._resolve_path(self.frontend_dist_dir)

    def _resolve_path(self, value: str) -> Path:
        """基于项目根目录解析相对路径。"""

        path: Path = Path(value)
        if path.is_absolute():
            return path
        return (ROOT_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """返回当前进程缓存的配置对象。"""

    return Settings()


def ensure_app_dirs(settings: Settings | None = None) -> None:
    """在应用启动前确保运行期目录已创建。"""

    active_settings: Settings = settings or get_settings()
    active_settings.resolved_vector_store_dir.mkdir(parents=True, exist_ok=True)
    active_settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    active_settings.resolved_model_config_secret_path.parent.mkdir(parents=True, exist_ok=True)
    if active_settings.resolved_database_url.startswith("sqlite:///"):
        db_path: Path = Path(active_settings.resolved_database_url.replace("sqlite:///", "", 1))
        db_path.parent.mkdir(parents=True, exist_ok=True)
