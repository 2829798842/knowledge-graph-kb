"""模块名称：tests.test_frontend_routes

主要功能：验证根路径入口、单页应用回退与前端构建缺失提示行为。
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_root_route_serves_frontend_index(client: TestClient):
    """验证根路径会返回前端首页文件。

    Args:
        client: FastAPI 测试客户端。
    """

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!doctype html>" in response.text.lower()


def test_spa_route_falls_back_to_frontend_index(client: TestClient):
    """验证单页应用路径会回退到前端首页。

    Args:
        client: FastAPI 测试客户端。
    """

    response = client.get("/documents/demo")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!doctype html>" in response.text.lower()


def test_missing_frontend_dist_returns_guidance(
    configured_env,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """验证缺少前端构建产物时会返回明确提示页面。

    Args:
        configured_env: 已配置完成的测试环境。
        monkeypatch: Pytest 提供的环境变量补丁工具。
        tmp_path: 当前测试专用的临时目录。
    """

    missing_frontend_dist_dir: Path = tmp_path / "missing-frontend-dist"
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(missing_frontend_dist_dir))

    from kb_graph.config import get_settings

    get_settings.cache_clear()

    from kb_graph.app_factory import create_app

    with TestClient(create_app()) as test_client:
        response = test_client.get("/")
        health_response = test_client.get("/health")

    assert response.status_code == 503
    assert "pnpm build" in response.text
    assert str(missing_frontend_dist_dir.as_posix()) in response.text
    assert health_response.status_code == 200

    get_settings.cache_clear()
