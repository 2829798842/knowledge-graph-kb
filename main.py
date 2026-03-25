"""作为后端服务启动入口，负责初始化日志并启动 FastAPI 应用。
"""

import uvicorn

from src import create_app
from src.config import Settings, get_settings
from src.utils.logger import configure_logging, get_logger

settings: Settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)
app = create_app()


def cli() -> None:
    """按当前配置启动后端服务。"""

    runtime_settings: Settings = get_settings()
    logger.info(
        "启动服务: host=%s port=%s log_level=%s",
        runtime_settings.server_host,
        runtime_settings.server_port,
        runtime_settings.log_level,
    )
    uvicorn.run(
        "main:app",
        host=runtime_settings.server_host,
        port=runtime_settings.server_port,
        reload=False,
        log_config=None,
        access_log=False,
    )


def main() -> None:
    """运行命令行入口。"""

    cli()


if __name__ == "__main__":
    main()
