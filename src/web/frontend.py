"""集成式 FastAPI 应用的前端托管辅助工具。"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

FRONTEND_INDEX_FILE_NAME: str = "index.html"


def register_frontend_routes(app: FastAPI, frontend_dist_dir: Path) -> None:
    """注册前端静态资源路由与单页应用回退路由。"""

    resolved_frontend_dist_dir: Path = frontend_dist_dir.resolve()
    index_file: Path = resolved_frontend_dist_dir / FRONTEND_INDEX_FILE_NAME
    if not index_file.is_file():
        _register_missing_frontend_routes(app, resolved_frontend_dist_dir)
        return

    @app.get("/", include_in_schema=False)
    def serve_frontend_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_frontend_route(requested_path: str) -> FileResponse:
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
    """当前端构建产物不存在时，注册提示页面。"""

    guidance_html: str = _build_missing_frontend_html(frontend_dist_dir)

    @app.get("/", include_in_schema=False)
    def serve_missing_frontend() -> HTMLResponse:
        return HTMLResponse(content=guidance_html, status_code=503)

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_missing_frontend_fallback(requested_path: str) -> HTMLResponse:
        if requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return HTMLResponse(content=guidance_html, status_code=503)


def _build_missing_frontend_html(frontend_dist_dir: Path) -> str:
    """构建前端产物缺失时显示的提示页面 HTML。"""

    return f"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>Knowledge Graph KB</title>
  </head>
  <body>
    <main style="font-family: sans-serif; max-width: 720px; margin: 48px auto; line-height: 1.6;">
      <h1>前端静态资源尚未构建</h1>
      <p>当前后端已经按一体化方式启动，但在返回页面前，需要先准备好前端构建产物。</p>
      <p>请在项目根目录执行：</p>
      <pre style="background: #f5f5f5; padding: 16px; border-radius: 8px;">cd frontend
pnpm build</pre>
      <p>当前期望的前端目录为：<code>{frontend_dist_dir.as_posix()}</code></p>
    </main>
  </body>
</html>
""".strip()


def _resolve_frontend_file(frontend_dist_dir: Path, requested_path: str) -> Path | None:
    """解析前端构建目录中的静态资源路径。"""

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
