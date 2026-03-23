"""模块名称：config.settings

主要功能：定义应用配置对象、缓存读取入口以及运行期目录解析逻辑。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR: Path = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """应用配置对象。

    Attributes:
        app_name (str): 应用展示名称。
        database_url (str): 元数据数据库连接字符串。
        lancedb_path (str): LanceDB 数据目录。
        upload_dir (str): 上传文件落盘目录。
        frontend_dist_dir (str): 前端构建产物目录。
        server_host (str): 应用监听地址。
        server_port (int): 应用监听端口。
        openai_api_key (str): OpenAI API 密钥。
        openai_llm_model (str): 用于抽取与问答的大语言模型名称。
        openai_embed_model (str): 用于向量化的嵌入模型名称。
        chunk_size_tokens (int): 文本切块的最大 token 数。
        chunk_overlap_tokens (int): 相邻切块的重叠 token 数。
        query_seed_limit (int): 向量检索阶段的种子块数量。
        query_context_chunks (int): 最终拼接到问答上下文中的块数量。
        graph_similarity_threshold (float): 语义边建立阈值。
        cors_origins (list[str]): 允许跨域访问的前端来源列表。
    """

    app_name: str = "Knowledge Graph KB"
    database_url: str = "sqlite:///./data/app.db"
    lancedb_path: str = "./data/lancedb"
    upload_dir: str = "./data/uploads"
    frontend_dist_dir: str = "./frontend/dist"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    openai_api_key: str = ""
    openai_llm_model: str = "gpt-5.4-mini"
    openai_embed_model: str = "text-embedding-3-large"
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
    )

    @property
    def resolved_database_url(self) -> str:
        """返回解析后的数据库连接字符串。

        Returns:
            str: 适合直接交给 SQLAlchemy 使用的数据库连接字符串。
        """

        prefix: str = "sqlite:///"
        if self.database_url.startswith(prefix) and not self.database_url.startswith(f"{prefix}/"):
            relative_path: str = self.database_url.replace(prefix, "", 1)
            absolute_path: Path = (ROOT_DIR / relative_path).resolve()
            return f"{prefix}{absolute_path.as_posix()}"
        return self.database_url

    @property
    def resolved_lancedb_path(self) -> Path:
        """返回解析后的 LanceDB 目录。

        Returns:
            Path: LanceDB 实际使用的数据目录。
        """

        return self._resolve_path(self.lancedb_path)

    @property
    def resolved_upload_dir(self) -> Path:
        """返回解析后的上传目录。

        Returns:
            Path: 上传文件实际落盘目录。
        """

        return self._resolve_path(self.upload_dir)

    @property
    def resolved_frontend_dist_dir(self) -> Path:
        """返回解析后的前端静态产物目录。

        Returns:
            Path: 前端构建产物所在目录。
        """

        return self._resolve_path(self.frontend_dist_dir)

    def _resolve_path(self, value: str) -> Path:
        """将相对路径解析到项目根目录。

        Args:
            value: 配置中声明的目录路径。

        Returns:
            Path: 解析后的绝对路径。
        """

        path: Path = Path(value)
        if path.is_absolute():
            return path
        return (ROOT_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """获取带缓存的配置对象。

    Returns:
        Settings: 当前进程共享的配置实例。
    """

    return Settings()


def ensure_app_dirs(settings: Settings | None = None) -> None:
    """确保运行期所需目录已存在。

    Args:
        settings: 可选的配置对象；未提供时使用全局缓存配置。
    """

    active_settings: Settings = settings or get_settings()
    active_settings.resolved_lancedb_path.mkdir(parents=True, exist_ok=True)
    active_settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    if active_settings.resolved_database_url.startswith("sqlite:///"):
        db_path: Path = Path(active_settings.resolved_database_url.replace("sqlite:///", "", 1))
        db_path.parent.mkdir(parents=True, exist_ok=True)
