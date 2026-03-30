from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient

from src import create_app
from src.config import get_settings
from src.kb.application.imports.service import ImportExecutor
from src.kb.providers.openai import OpenAiGateway


def _fake_generate_embeddings(self: OpenAiGateway, texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for text in texts:
        normalized = str(text or "").strip()
        char_total = sum(ord(char) for char in normalized) or 1
        embeddings.append(
            [
                float(len(normalized) % 11 + 1),
                float(char_total % 17 + 1),
                float((char_total + len(normalized)) % 23 + 1),
            ]
        )
    return embeddings


def _fake_extract_document_graph(
    self: OpenAiGateway,
    *,
    document_name: str,
    text: str,
    window_label: str = "window",
) -> dict[str, object]:
    normalized = f"{document_name}\n{text}\n{window_label}".lower()
    entities: list[dict[str, object]] = []
    relations: list[dict[str, object]] = []
    if "alpha" in normalized:
        entities.append({"name": "Alpha", "description": "测试实体 Alpha", "metadata": {}})
    if "beta" in normalized:
        entities.append({"name": "Beta", "description": "测试实体 Beta", "metadata": {}})
    if "alpha" in normalized and "beta" in normalized:
        relations.append(
            {
                "subject": "Alpha",
                "object": "Beta",
                "predicate": "关联",
                "confidence": 0.9,
                "metadata": {},
            }
        )
    return {"entities": entities, "relations": relations}


def _fake_generate_answer(
    self: OpenAiGateway,
    query: str,
    context_blocks: list[dict[str, str]],
    *,
    conversation_turns: list[dict[str, str]] | None = None,
) -> str:
    _ = conversation_turns
    if context_blocks:
        return f"根据已导入内容，问题“{query}”的相关依据已找到。"
    return "当前没有足够证据支持回答。"


def _fake_test_connection(self: OpenAiGateway, runtime_config) -> tuple[bool, bool]:
    _ = runtime_config
    return True, True


def _sync_submit(self: ImportExecutor, *, job_id: str, items: list[dict[str, object]]) -> None:
    self._run_job(job_id=job_id, items=items, cancellation_event=Event())


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data_dir = tmp_path / "kb-data"
    frontend_dist_dir = tmp_path / "frontend-dist"
    frontend_dist_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dist_dir / "index.html").write_text("<!doctype html><html><body>test</body></html>", encoding="utf-8")

    monkeypatch.setenv("KB_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(frontend_dist_dir))
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    monkeypatch.setattr(OpenAiGateway, "generate_embeddings", _fake_generate_embeddings)
    monkeypatch.setattr(OpenAiGateway, "extract_document_graph", _fake_extract_document_graph)
    monkeypatch.setattr(OpenAiGateway, "generate_answer", _fake_generate_answer)
    monkeypatch.setattr(OpenAiGateway, "test_connection", _fake_test_connection)
    monkeypatch.setattr(ImportExecutor, "submit", _sync_submit)

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
