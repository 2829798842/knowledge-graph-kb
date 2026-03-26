"""应用配置与路径辅助函数。"""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """从环境变量加载的运行时配置。"""

    app_name: str = "Knowledge Graph KB"
    kb_data_dir: str = Field(
        default="./data/kb",
        validation_alias=AliasChoices("KB_DATA_DIR"),
    )
    kb_database_name: str = Field(
        default="kb.sqlite3",
        validation_alias=AliasChoices("KB_DATABASE_NAME"),
    )
    kb_vector_index_dir_name: str = Field(
        default="vector_index",
        validation_alias=AliasChoices("KB_VECTOR_INDEX_DIR_NAME"),
    )
    kb_upload_dir_name: str = Field(
        default="uploads",
        validation_alias=AliasChoices("KB_UPLOAD_DIR_NAME"),
    )
    kb_secret_dir_name: str = Field(
        default="secrets",
        validation_alias=AliasChoices("KB_SECRET_DIR_NAME"),
    )
    model_config_secret_name: str = Field(
        default="model_config.key",
        validation_alias=AliasChoices("MODEL_CONFIG_SECRET_NAME"),
    )
    kb_scan_roots: list[str] = Field(
        default_factory=lambda: ["./data/kb/uploads", "./"],
        validation_alias=AliasChoices("KB_SCAN_ROOTS"),
    )
    frontend_dist_dir: str = Field(
        default="./frontend/dist",
        validation_alias=AliasChoices("FRONTEND_DIST_DIR"),
    )
    server_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("SERVER_HOST"))
    server_port: int = Field(default=8000, validation_alias=AliasChoices("SERVER_PORT"))
    log_level: str = Field(default="DEBUG", validation_alias=AliasChoices("LOG_LEVEL"))
    model_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("MODEL_PROVIDER", "API_PROVIDER"),
    )
    model_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("MODEL_BASE_URL", "OPENAI_BASE_URL"),
    )
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
    embedding_batch_size: int = Field(
        default=32,
        validation_alias=AliasChoices("EMBEDDING_BATCH_SIZE"),
    )
    chunk_size_tokens: int = Field(default=600, validation_alias=AliasChoices("CHUNK_SIZE_TOKENS"))
    chunk_overlap_tokens: int = Field(default=120, validation_alias=AliasChoices("CHUNK_OVERLAP_TOKENS"))
    query_context_chunks: int = Field(default=6, validation_alias=AliasChoices("QUERY_CONTEXT_CHUNKS"))
    query_rrf_k: int = Field(default=60, validation_alias=AliasChoices("QUERY_RRF_K"))
    query_structured_short_circuit_hits: int = Field(
        default=3,
        validation_alias=AliasChoices("QUERY_STRUCTURED_SHORT_CIRCUIT_HITS"),
    )
    query_ppr_enabled: bool = Field(default=False, validation_alias=AliasChoices("QUERY_PPR_ENABLED"))
    query_ppr_min_hits: int = Field(default=5, validation_alias=AliasChoices("QUERY_PPR_MIN_HITS"))
    query_ppr_candidate_limit: int = Field(default=30, validation_alias=AliasChoices("QUERY_PPR_CANDIDATE_LIMIT"))
    query_history_turns: int = Field(default=3, validation_alias=AliasChoices("QUERY_HISTORY_TURNS"))
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        populate_by_name=True,
    )

    @property
    def resolved_kb_data_dir(self) -> Path:
        return self._resolve_path(self.kb_data_dir)

    @property
    def resolved_kb_db_path(self) -> Path:
        return self.resolved_kb_data_dir / self.kb_database_name

    @property
    def resolved_kb_vector_dir(self) -> Path:
        return self.resolved_kb_data_dir / self.kb_vector_index_dir_name

    @property
    def resolved_kb_upload_dir(self) -> Path:
        return self.resolved_kb_data_dir / self.kb_upload_dir_name

    @property
    def resolved_model_config_secret_path(self) -> Path:
        return self.resolved_kb_data_dir / self.kb_secret_dir_name / self.model_config_secret_name

    @property
    def resolved_kb_scan_roots(self) -> list[Path]:
        return [self._resolve_path(path) for path in self.kb_scan_roots]

    @property
    def resolved_frontend_dist_dir(self) -> Path:
        return self._resolve_path(self.frontend_dist_dir)

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (ROOT_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """返回带缓存的应用配置。"""

    return Settings()


def ensure_app_dirs(settings: Settings | None = None) -> None:
    """创建应用运行所需目录。"""

    active_settings = settings or get_settings()
    active_settings.resolved_kb_data_dir.mkdir(parents=True, exist_ok=True)
    active_settings.resolved_kb_vector_dir.mkdir(parents=True, exist_ok=True)
    active_settings.resolved_kb_upload_dir.mkdir(parents=True, exist_ok=True)
    active_settings.resolved_model_config_secret_path.parent.mkdir(parents=True, exist_ok=True)
