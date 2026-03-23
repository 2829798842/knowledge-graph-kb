"""模块名称：web.frontend

主要功能：托管前端构建产物，并为单页应用提供静态文件与路由回退能力。
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

FRONTEND_INDEX_FILE_NAME: str = "index.html"


def register_frontend_routes(app: FastAPI, frontend_dist_dir: Path) -> None:
    """注册前端静态资源与单页应用路由。

    Args:
        app: 需要注册路由的 FastAPI 应用实例。
        frontend_dist_dir: 前端构建产物目录。
    """

    resolved_frontend_dist_dir: Path = frontend_dist_dir.resolve()
    index_file: Path = resolved_frontend_dist_dir / FRONTEND_INDEX_FILE_NAME
    if not index_file.is_file():
        _register_missing_frontend_routes(app, resolved_frontend_dist_dir)
        return

    @app.get("/", include_in_schema=False)
    def serve_frontend_index() -> FileResponse:
        """返回前端入口页面。

        Returns:
            FileResponse: 前端构建后的首页文件。
        """

        return FileResponse(index_file)

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_frontend_route(requested_path: str) -> FileResponse:
        """返回前端静态文件或单页应用入口。

        Args:
            requested_path: 当前请求的相对路径。

        Returns:
            FileResponse: 目标静态文件或前端入口文件。

        Raises:
            HTTPException: 当请求路径属于未知 API 地址时抛出。
        """

        if requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        resolved_file: Path | None = _resolve_frontend_file(
            frontend_dist_dir=resolved_frontend_dist_dir,
            requested_path=requested_path,
        )
        if resolved_file is not None:
            return FileResponse(resolved_file)
        return FileResponse(index_file)


def _register_missing_frontend_routes(app: FastAPI, frontend_dist_dir: Path) -> None:
    """注册前端缺失时的提示页面。

    Args:
        app: 需要注册路由的 FastAPI 应用实例。
        frontend_dist_dir: 预期的前端构建产物目录。
    """

    guidance_html: str = _build_missing_frontend_html(frontend_dist_dir)

    @app.get("/", include_in_schema=False)
    def serve_missing_frontend() -> HTMLResponse:
        """返回前端构建缺失提示。

        Returns:
            HTMLResponse: 包含前端构建引导说明的 HTML 响应。
        """

        return HTMLResponse(content=guidance_html, status_code=503)

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_missing_frontend_fallback(requested_path: str) -> HTMLResponse:
        """返回前端构建缺失提示或未知 API 的 404。

        Args:
            requested_path: 当前请求的相对路径。

        Returns:
            HTMLResponse: 包含前端构建引导说明的 HTML 响应。

        Raises:
            HTTPException: 当请求路径属于未知 API 地址时抛出。
        """

        if requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return HTMLResponse(content=guidance_html, status_code=503)


def _build_missing_frontend_html(frontend_dist_dir: Path) -> str:
    """构建前端静态资源缺失时的提示页面。

    Args:
        frontend_dist_dir: 预期的前端构建产物目录。

    Returns:
        str: 可直接返回给浏览器的提示 HTML。
    """

    return f"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>Knowledge Graph KB</title>
  </head>
  <body>
    <main style="font-family: sans-serif; max-width: 720px; margin: 48px auto; line-height: 1.6;">
      <h1>前端静态资源未构建</h1>
      <p>当前启动方式已改为 <code>uv run python main.py</code> 一体化启动。</p>
      <p>但在返回页面前，需要先准备好前端构建产物，请在项目根目录执行：</p>
      <pre style="background: #f5f5f5; padding: 16px; border-radius: 8px;">cd frontend
pnpm build</pre>
      <p>当前期望的前端目录为：<code>{frontend_dist_dir.as_posix()}</code></p>
    </main>
  </body>
</html>
""".strip()


def _resolve_frontend_file(frontend_dist_dir: Path, requested_path: str) -> Path | None:
    """解析单页应用请求对应的静态文件路径。

    Args:
        frontend_dist_dir: 前端构建产物目录。
        requested_path: 当前请求的相对路径。

    Returns:
        Path | None: 若命中真实静态文件则返回文件路径，否则返回 None。
    """

    if not requested_path or requested_path.endswith("/"):
        return None

    candidate: Path = (frontend_dist_dir / requested_path).resolve()
    try:
        candidate.relative_to(frontend_dist_dir)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate
    return None
