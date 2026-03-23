"""模块名称：main

主要功能：提供包内 ASGI 应用导出对象与命令行启动入口。
"""

import uvicorn

from kb_graph.app_factory import create_app
from kb_graph.config import Settings, get_settings

app = create_app()


def cli() -> None:
    """以命令行方式启动应用服务。

    Returns:
        None
    """

    settings: Settings = get_settings()
    uvicorn.run(
        "kb_graph.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
