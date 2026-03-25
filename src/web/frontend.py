"""注册前端静态资源路由，并在缺少构建产物时返回中文提示页。"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

FRONTEND_INDEX_FILE_NAME: str = "index.html"


def register_frontend_routes(app: FastAPI, frontend_dist_dir: Path) -> None:
    """为单页前端应用注册入口路由与静态资源回退逻辑。"""

    resolved_frontend_dist_dir: Path = frontend_dist_dir.resolve()
    index_file: Path = resolved_frontend_dist_dir / FRONTEND_INDEX_FILE_NAME
    if not index_file.is_file():
        _register_missing_frontend_routes(app, resolved_frontend_dist_dir)
        return

    @app.get("/", include_in_schema=False)
    def serve_frontend_index() -> FileResponse:
        """返回前端入口页面。"""

        return FileResponse(index_file)

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_frontend_route(requested_path: str) -> FileResponse:
        """优先返回静态资源，找不到时回退到单页应用入口。"""

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
    """当前端构建产物缺失时，注册中文引导页面。"""

    guidance_html: str = _build_missing_frontend_html(frontend_dist_dir)

    @app.get("/", include_in_schema=False)
    def serve_missing_frontend() -> HTMLResponse:
        """返回前端缺失提示页。"""

        return HTMLResponse(content=guidance_html, status_code=503)

    @app.get("/{requested_path:path}", include_in_schema=False)
    def serve_missing_frontend_fallback(requested_path: str) -> HTMLResponse:
        """在任意非 API 路径下返回前端缺失提示页。"""

        if requested_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return HTMLResponse(content=guidance_html, status_code=503)


def _build_missing_frontend_html(frontend_dist_dir: Path) -> str:
    """构建缺失前端产物时展示的中文 HTML 提示。"""

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
      <p>后端已经启动，但在展示页面之前，还需要先生成前端构建产物。</p>
      <p>请在项目根目录执行：</p>
      <pre style="background: #f5f5f5; padding: 16px; border-radius: 8px;">cd frontend
pnpm build</pre>
      <p>当前期望的前端构建目录为：<code>{frontend_dist_dir.as_posix()}</code></p>
    </main>
  </body>
</html>
""".strip()


def _resolve_frontend_file(frontend_dist_dir: Path, requested_path: str) -> Path | None:
    """解析并校验前端静态资源路径，防止越权访问。"""

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
