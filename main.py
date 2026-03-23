"""集成后端服务的项目入口。"""

import uvicorn

from src import create_app
from src.config import Settings, get_settings

app = create_app()


def cli() -> None:
    """按配置的主机和端口启动应用。"""

    settings: Settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )


def main() -> None:
    """运行命令行入口。"""

    cli()


if __name__ == "__main__":
    main()
