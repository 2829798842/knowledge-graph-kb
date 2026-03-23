"""后端应用代码的顶层包。"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """惰性创建 FastAPI 应用，避免导入包时触发额外副作用。"""

    from src.app_factory import create_app as build_app

    return build_app()

__all__ = ["create_app"]
