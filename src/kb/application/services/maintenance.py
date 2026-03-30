"""Runtime maintenance helpers for local single-instance operations."""
from dataclasses import dataclass
from pathlib import Path
import json
import shutil
from typing import Any

from src.config import Settings, ensure_app_dirs
from src.kb.common import build_entity_node_id, build_paragraph_node_id, build_source_node_id, utc_now_iso
from src.kb.database import SQLiteGateway
from src.kb.providers import OpenAiGateway
from src.kb.storage import GraphStore, SourceStore, VectorIndex, VectorIndexRecord

from .model import ModelConfigService


@dataclass(slots=True)
class MaintenanceCheck:
    name: str
    ok: bool
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "message": self.message,
            "details": self.details,
        }


class MaintenanceService:
    """Readiness, doctor, backup, and rebuild operations."""

    def __init__(
        self,
        *,
        settings: Settings,
        gateway: SQLiteGateway,
        source_store: SourceStore,
        graph_store: GraphStore,
        vector_index: VectorIndex,
        model_config_service: ModelConfigService,
        openai_gateway: OpenAiGateway,
    ) -> None:
        self.settings = settings
        self.gateway = gateway
        self.source_store = source_store
        self.graph_store = graph_store
        self.vector_index = vector_index
        self.model_config_service = model_config_service
        self.openai_gateway = openai_gateway

    def ready(self) -> dict[str, Any]:
        checks = [
            self._database_check(),
            self._vector_index_check(),
            self._model_config_check(),
            self._frontend_check(),
        ]
        ok = all(check.ok for check in checks)
        return {
            "status": "ready" if ok else "degraded",
            "checks": [check.to_dict() for check in checks],
        }

    def doctor(self) -> dict[str, Any]:
        checks = [
            self._database_check(),
            self._vector_index_check(),
            self._model_config_check(),
            self._frontend_check(),
            self._graph_integrity_check(),
        ]
        ok = all(check.ok for check in checks)
        return {
            "status": "ok" if ok else "needs_attention",
            "checked_at": utc_now_iso(),
            "schema_version": self.gateway.get_schema_version(),
            "paths": {
                "data_dir": str(self.settings.resolved_kb_data_dir),
                "db_path": str(self.settings.resolved_kb_db_path),
                "vector_dir": str(self.settings.resolved_kb_vector_dir),
                "upload_dir": str(self.settings.resolved_kb_upload_dir),
                "frontend_dist_dir": str(self.settings.resolved_frontend_dist_dir),
            },
            "counts": {
                "sources": len(self.source_store.list_sources(limit=None)),
                "paragraphs": len(self.source_store.list_all_paragraphs()),
                "entities": len(self.graph_store.list_entities()),
                "manual_relations": len(self.graph_store.list_manual_relations()),
                "vector_records": self.vector_index.record_count,
            },
            "checks": [check.to_dict() for check in checks],
        }

    def backup(self, *, output_dir: Path | None = None) -> dict[str, Any]:
        ensure_app_dirs(self.settings)
        backup_dir = output_dir or self.settings.resolved_kb_data_dir.parent / "backups" / f"kb-backup-{self._timestamp_slug()}"
        backup_dir = backup_dir.resolve()
        if backup_dir.exists():
            raise ValueError("备份目录已存在，请使用新的输出目录。")

        backup_dir.mkdir(parents=True, exist_ok=False)
        self.gateway.backup_to(backup_dir / self.settings.kb_database_name)
        self._copy_tree_if_exists(self.settings.resolved_kb_vector_dir, backup_dir / self.settings.kb_vector_index_dir_name)
        self._copy_tree_if_exists(self.settings.resolved_kb_upload_dir, backup_dir / self.settings.kb_upload_dir_name)
        self._copy_tree_if_exists(
            self.settings.resolved_model_config_secret_path.parent,
            backup_dir / self.settings.kb_secret_dir_name,
        )

        manifest = {
            "created_at": utc_now_iso(),
            "schema_version": self.gateway.get_schema_version(),
            "app_name": self.settings.app_name,
            "db_file": self.settings.kb_database_name,
            "vector_dir": self.settings.kb_vector_index_dir_name,
            "upload_dir": self.settings.kb_upload_dir_name,
            "secret_dir": self.settings.kb_secret_dir_name,
        }
        (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "status": "ok",
            "backup_dir": str(backup_dir),
            "manifest": manifest,
        }

    def rebuild_vectors(self) -> dict[str, Any]:
        paragraphs = self.source_store.list_all_paragraphs()
        if not paragraphs:
            self.vector_index.reset()
            return {
                "status": "ok",
                "paragraph_count": 0,
                "source_count": 0,
                "model_signature": self.model_config_service.embedding_model_signature(),
            }

        records = [
            VectorIndexRecord(
                paragraph_id=str(paragraph["id"]),
                source_id=str(paragraph["source_id"]),
                node_id=build_paragraph_node_id(str(paragraph["id"])),
                text=str(paragraph["content"]),
                knowledge_type=str(paragraph["knowledge_type"]),
            )
            for paragraph in paragraphs
        ]
        embeddings = self.openai_gateway.generate_embeddings([record.text for record in records])
        self.vector_index.reset()
        self.vector_index.add_embeddings(
            model_signature=self.model_config_service.embedding_model_signature(),
            records=records,
            embeddings=embeddings,
        )
        for paragraph in paragraphs:
            self.source_store.update_paragraph(str(paragraph["id"]), vector_state="ready")

        return {
            "status": "ok",
            "paragraph_count": len(paragraphs),
            "source_count": len({str(paragraph["source_id"]) for paragraph in paragraphs}),
            "model_signature": self.model_config_service.embedding_model_signature(),
        }

    def rebuild_graph(self) -> dict[str, Any]:
        deleted_manual_relations = 0
        deleted_entities = 0
        updated_entities = 0

        for relation in self.graph_store.list_manual_relations():
            subject_node_id = str(relation["subject_node_id"])
            object_node_id = str(relation["object_node_id"])
            if self._node_exists(subject_node_id) and self._node_exists(object_node_id):
                continue
            if self.graph_store.delete_manual_relation(str(relation["id"])):
                deleted_manual_relations += 1

        for entity in self.graph_store.list_entities():
            entity_id = str(entity["id"])
            paragraph_link_count = self.graph_store.count_paragraph_links_for_entity(entity_id)
            relation_count = self.graph_store.count_relations_for_entity(entity_id)
            is_manual_entity = bool(dict(entity.get("metadata") or {}).get("manual_created"))
            if paragraph_link_count <= 0 and relation_count <= 0:
                if is_manual_entity:
                    if int(entity.get("appearance_count") or 0) != paragraph_link_count:
                        self.graph_store.set_entity_appearance_count(entity_id, paragraph_link_count)
                        updated_entities += 1
                    continue
                self.graph_store.delete_manual_relations_for_node(build_entity_node_id(entity_id))
                if self.graph_store.delete_entity(entity_id):
                    deleted_entities += 1
                continue
            if int(entity.get("appearance_count") or 0) != paragraph_link_count:
                self.graph_store.set_entity_appearance_count(entity_id, paragraph_link_count)
                updated_entities += 1

        return {
            "status": "ok",
            "deleted_manual_relations": deleted_manual_relations,
            "deleted_entities": deleted_entities,
            "updated_entities": updated_entities,
        }

    def _database_check(self) -> MaintenanceCheck:
        db_exists = self.settings.resolved_kb_db_path.exists()
        try:
            self.gateway.check_read_write()
            ok = True
            message = "SQLite database is readable and writable."
        except Exception as exc:  # noqa: BLE001
            ok = False
            message = str(exc)
        return MaintenanceCheck(
            name="database",
            ok=ok and db_exists,
            message=message if db_exists else "SQLite database file does not exist.",
            details={
                "db_path": str(self.settings.resolved_kb_db_path),
                "exists": db_exists,
                "schema_version": self.gateway.get_schema_version(),
            },
        )

    def _vector_index_check(self) -> MaintenanceCheck:
        try:
            self.vector_index.check_readable()
            ok = True
            message = "Vector index files are readable."
        except Exception as exc:  # noqa: BLE001
            ok = False
            message = str(exc)
        return MaintenanceCheck(
            name="vector_index",
            ok=ok,
            message=message,
            details=self.vector_index.describe(),
        )

    def _model_config_check(self) -> MaintenanceCheck:
        try:
            runtime_config = self.model_config_service.resolve_runtime_configuration()
            has_api_key = bool(runtime_config.api_key)
            return MaintenanceCheck(
                name="model_config",
                ok=has_api_key,
                message="Model configuration is available." if has_api_key else "Model configuration is missing an API key.",
                details={
                    "provider": runtime_config.provider,
                    "base_url": runtime_config.base_url,
                    "llm_model": runtime_config.llm_model,
                    "embedding_model": runtime_config.embedding_model,
                    "api_key_source": runtime_config.api_key_source,
                    "has_api_key": has_api_key,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return MaintenanceCheck(
                name="model_config",
                ok=False,
                message=str(exc),
                details={},
            )

    def _frontend_check(self) -> MaintenanceCheck:
        frontend_dir = self.settings.resolved_frontend_dist_dir
        index_file = frontend_dir / "index.html"
        ok = frontend_dir.exists() and index_file.exists()
        return MaintenanceCheck(
            name="frontend_dist",
            ok=ok,
            message="Frontend build artifacts are present." if ok else "Frontend dist directory is missing or incomplete.",
            details={
                "frontend_dist_dir": str(frontend_dir),
                "index_file": str(index_file),
                "exists": frontend_dir.exists(),
                "index_exists": index_file.exists(),
            },
        )

    def _graph_integrity_check(self) -> MaintenanceCheck:
        dangling_manual_relations = [
            str(relation["id"])
            for relation in self.graph_store.list_manual_relations()
            if not self._node_exists(str(relation["subject_node_id"])) or not self._node_exists(str(relation["object_node_id"]))
        ]
        orphan_entities = [
            str(entity["id"])
            for entity in self.graph_store.list_entities()
            if self.graph_store.count_paragraph_links_for_entity(str(entity["id"])) <= 0
            and self.graph_store.count_relations_for_entity(str(entity["id"])) <= 0
            and not bool(dict(entity.get("metadata") or {}).get("manual_created"))
        ]
        ok = not dangling_manual_relations and not orphan_entities
        return MaintenanceCheck(
            name="graph_integrity",
            ok=ok,
            message="Graph integrity looks clean." if ok else "Graph storage contains orphan records that can be repaired.",
            details={
                "dangling_manual_relation_ids": dangling_manual_relations,
                "orphan_entity_ids": orphan_entities,
            },
        )

    def _node_exists(self, node_id: str) -> bool:
        if node_id.startswith("source:"):
            return self.source_store.get_source(node_id.split(":", maxsplit=1)[1]) is not None
        if node_id.startswith("paragraph:"):
            return self.source_store.get_paragraph(node_id.split(":", maxsplit=1)[1]) is not None
        if node_id.startswith("entity:"):
            return self.graph_store.get_entity(node_id.split(":", maxsplit=1)[1]) is not None
        return False

    def _copy_tree_if_exists(self, source_path: Path, target_path: Path) -> None:
        if not source_path.exists():
            return
        shutil.copytree(source_path, target_path)

    def _timestamp_slug(self) -> str:
        return utc_now_iso().replace(":", "").replace("-", "").replace(".", "").replace("+", "_")


def restore_backup(*, settings: Settings, backup_dir: Path, force: bool = False) -> dict[str, Any]:
    ensure_app_dirs(settings)
    resolved_backup_dir = backup_dir.resolve()
    if not resolved_backup_dir.exists() or not resolved_backup_dir.is_dir():
        raise ValueError("备份目录不存在。")

    target_dir = settings.resolved_kb_data_dir
    if target_dir.exists() and any(target_dir.iterdir()):
        if not force:
            raise ValueError("当前数据目录非空，请使用 --force 进行恢复。")
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    for item in resolved_backup_dir.iterdir():
        if item.name == "manifest.json":
            shutil.copy2(item, target_dir / item.name)
            continue
        if item.is_dir():
            shutil.copytree(item, target_dir / item.name)
            continue
        shutil.copy2(item, target_dir / item.name)

    return {
        "status": "ok",
        "restored_from": str(resolved_backup_dir),
        "target_dir": str(target_dir),
    }
