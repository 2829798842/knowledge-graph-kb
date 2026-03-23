"""模块名称：tests.conftest

主要功能：为后端测试提供环境变量、FastAPI 客户端与数据库会话等公共夹具。
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture
def configured_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """为测试用例准备隔离的运行环境。

    Args:
        monkeypatch: Pytest 提供的环境变量补丁工具。
        tmp_path: 当前测试专用的临时目录。

    Yields:
        Path: 当前测试用的临时目录路径。
    """

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    monkeypatch.setenv("LANCEDB_PATH", str((tmp_path / "lancedb").resolve()))
    monkeypatch.setenv("UPLOAD_DIR", str((tmp_path / "uploads").resolve()))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(
        "FRONTEND_DIST_DIR",
        str((Path(__file__).resolve().parents[1] / "frontend" / "dist").resolve()),
    )

    from kb_graph.config import get_settings
    from kb_graph.data.database import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def client(configured_env) -> Iterator[TestClient]:
    """创建测试使用的 FastAPI 客户端。

    Args:
        configured_env: 已配置完成的测试环境。

    Yields:
        Iterator[TestClient]: FastAPI 测试客户端。
    """

    from kb_graph.app_factory import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(configured_env) -> Iterator[Session]:
    """创建测试数据库会话。

    Args:
        configured_env: 已配置完成的测试环境。

    Yields:
        Iterator[Session]: 数据库会话对象。
    """

    from kb_graph.data.database import get_engine, init_db

    init_db()
    with Session(get_engine()) as db_session:
        yield db_session
