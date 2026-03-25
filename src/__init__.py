"""后端应用代码的顶层包。"""

from fastapi import FastAPI
from src.app import create_app as _build_app


def create_app() -> FastAPI:
    """惰性创建 FastAPI 应用，避免导入包时触发额外副作用。"""
    return _build_app()

__all__ = ["create_app"]


