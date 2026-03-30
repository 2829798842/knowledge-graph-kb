"""Application service for graph projection and manual relations."""

from typing import Any

from src.kb.common import (
    build_contains_edge_id,
    build_entity_node_id,
    build_manual_edge_id,
    build_mention_edge_id,
    build_paragraph_node_id,
    build_relation_edge_id,
    build_sheet_edge_id,
    build_source_node_id,
)
from src.kb.storage import GraphStore, SourceStore, VectorIndex

SPREADSHEET_FILE_TYPES: set[str] = {"xlsx", "xlsm", "xls"}


class GraphService:
    """Project graph nodes, edges, and details from repository data."""

    def __init__(self, *, graph_store: GraphStore, source_store: SourceStore, vector_index: VectorIndex) -> None:
        self.graph_store = graph_store
        self.source_store = source_store
        self.vector_index = vector_index

    def build_graph(
        self,
        *,
        source_ids: list[str] | None = None,
        include_paragraphs: bool = True,
        density: int = 100,
    ) -> dict[str, list[dict[str, Any]]]:
        source_rows = self.graph_store.list_graph_sources(source_ids)
        visible_sources = [source for source in source_rows if self._is_graph_visible_source(source)]
        visible_source_ids = [str(source["id"]) for source in visible_sources]
        if not visible_source_ids:
            return {"nodes": [], "edges": []}

        paragraph_rows = self.graph_store.list_graph_paragraphs(visible_source_ids)
        paragraph_ids = {str(row["id"]) for row in paragraph_rows}
        entity_rows = self.graph_store.list_graph_entities(visible_source_ids)
        manual_entity_rows = [
            entity
            for entity in self.graph_store.list_entities()
            if bool(dict(entity.get("metadata") or {}).get("manual_created"))
        ]
        if manual_entity_rows:
            entity_rows = list(
                {
                    str(entity["id"]): entity
                    for entity in [*entity_rows, *manual_entity_rows]
                }.values()
            )
        relation_rows = self.graph_store.list_graph_relations(visible_source_ids)
        manual_rows = self.graph_store.list_manual_relations()
        paragraph_entity_links = self.graph_store.list_paragraph_entity_links(source_ids=visible_source_ids)

        nodes: list[dict[str, Any]] = []
        structural_edges: list[dict[str, Any]] = []
        semantic_edges: list[dict[str, Any]] = []

        for source in visible_sources:
            source_id = str(source["id"])
            nodes.append(
                {
                    "id": build_source_node_id(source_id),
                    "type": self._source_node_type(source),
                    "label": str(source["name"]),
                    "size": self._source_node_size(source),
                    "score": None,
                    "metadata": source,
                }
            )

        if include_paragraphs:
            for paragraph in paragraph_rows:
                paragraph_id = str(paragraph["id"])
                structural_edges.append(
                    {
                        "id": build_contains_edge_id(str(paragraph["source_id"]), paragraph_id),
                        "source": build_source_node_id(str(paragraph["source_id"])),
                        "target": build_paragraph_node_id(paragraph_id),
                        "type": "contains",
                        "label": "Contains paragraph",
                        "weight": 1.0,
                        "metadata": {"source_id": paragraph["source_id"], "paragraph_id": paragraph_id},
                    }
                )
                nodes.append(
                    {
                        "id": build_paragraph_node_id(paragraph_id),
                        "type": "paragraph",
                        "label": self._paragraph_label(str(paragraph["content"])),
                        "size": 3.0,
                        "score": None,
                        "metadata": paragraph,
                    }
                )

        for entity in entity_rows:
            entity_id = str(entity["id"])
            node_type = self._entity_node_type(entity)
            nodes.append(
                {
                    "id": build_entity_node_id(entity_id),
                    "type": node_type,
                    "label": self._entity_node_label(entity),
                    "size": self._entity_node_size(entity),
                    "score": None,
                    "metadata": entity,
                }
            )
            if node_type == "worksheet":
                source_id = self._metadata_value(entity, "source_id")
                if source_id:
                    structural_edges.append(
                        {
                            "id": build_sheet_edge_id(source_id, entity_id),
                            "source": build_source_node_id(source_id),
                            "target": build_entity_node_id(entity_id),
                            "type": "contains_sheet",
                            "label": "Contains worksheet",
                            "weight": 1.0,
                            "metadata": {
                                "source_id": source_id,
                                "entity_id": entity_id,
                                "worksheet_name": self._metadata_value(entity, "worksheet_name"),
                            },
                        }
                    )

        if include_paragraphs:
            for link in paragraph_entity_links:
                paragraph_id = str(link["paragraph_id"])
                if paragraph_id not in paragraph_ids:
                    continue
                semantic_edges.append(
                    {
                        "id": build_mention_edge_id(paragraph_id, str(link["entity_id"])),
                        "source": build_paragraph_node_id(paragraph_id),
                        "target": build_entity_node_id(str(link["entity_id"])),
                        "type": "mentions",
                        "label": "Mentions",
                        "weight": max(1.0, float(link.get("mention_count") or 1)),
                        "metadata": link,
                    }
                )

        for relation in relation_rows:
            semantic_edges.append(
                {
                    "id": build_relation_edge_id(str(relation["id"])),
                    "source": build_entity_node_id(str(relation["subject_entity_id"])),
                    "target": build_entity_node_id(str(relation["object_entity_id"])),
                    "type": self._relation_edge_type(relation),
                    "label": str(relation["predicate"]),
                    "weight": max(1.0, float(relation.get("confidence") or 1.0)),
                    "metadata": relation,
                }
            )

        visible_node_ids = {str(node["id"]) for node in nodes}
        for relation in manual_rows:
            subject_node_id = str(relation["subject_node_id"])
            object_node_id = str(relation["object_node_id"])
            if subject_node_id not in visible_node_ids or object_node_id not in visible_node_ids:
                continue
            semantic_edges.append(
                {
                    "id": build_manual_edge_id(str(relation["id"])),
                    "source": subject_node_id,
                    "target": object_node_id,
                    "type": "manual",
                    "label": str(relation["predicate"]),
                    "weight": float(relation["weight"]),
                    "metadata": relation,
                }
            )

        projected_edges = structural_edges + self._apply_density_filter(semantic_edges, density=density)
        return {
            "nodes": nodes,
            "edges": self._prune_dangling_edges(projected_edges, node_ids=visible_node_ids),
        }

    def _is_graph_visible_source(self, source: dict[str, Any]) -> bool:
        return str(source.get("status") or "").strip().lower() in {"ready", "partial"}

    def get_node_detail(self, node_id: str) -> dict[str, Any]:
        if node_id.startswith("source:"):
            source_id = node_id.split(":", maxsplit=1)[1]
            source = self.source_store.get_source(source_id)
            if source is None:
                raise KeyError(node_id)
            paragraphs = self.source_store.list_source_paragraphs(source_id)[:12]
            relations = self.graph_store.list_relations_for_source(source_id, limit=20)
            return {
                "node": {
                    "id": node_id,
                    "type": self._source_node_type(source),
                    "label": str(source["name"]),
                    "size": self._source_node_size(source),
                    "score": None,
                    "metadata": source,
                },
                "source": source,
                "paragraphs": paragraphs,
                "relations": relations,
            }
        if node_id.startswith("paragraph:"):
            paragraph_id = node_id.split(":", maxsplit=1)[1]
            paragraph = self.source_store.get_paragraph(paragraph_id)
            if paragraph is None:
                raise KeyError(node_id)
            source = self.source_store.get_source(str(paragraph["source_id"]))
            relations = self.graph_store.list_relations_for_paragraph(paragraph_id)
            return {
                "node": {
                    "id": node_id,
                    "type": "paragraph",
                    "label": self._paragraph_label(str(paragraph["content"])),
                    "size": 3.0,
                    "score": None,
                    "metadata": paragraph,
                },
                "source": source,
                "paragraphs": [paragraph],
                "relations": relations,
            }
        if node_id.startswith("entity:"):
            entity_id = node_id.split(":", maxsplit=1)[1]
            entity = self.graph_store.get_entity(entity_id)
            if entity is None:
                raise KeyError(node_id)
            paragraphs = self.graph_store.list_paragraphs_for_entity(entity_id, limit=12)
            relations = self.graph_store.list_relations_for_entity(entity_id, limit=24)
            return {
                "node": {
                    "id": node_id,
                    "type": self._entity_node_type(entity),
                    "label": self._entity_node_label(entity),
                    "size": self._entity_node_size(entity),
                    "score": None,
                    "metadata": entity,
                },
                "source": None,
                "paragraphs": paragraphs,
                "relations": relations,
            }
        raise KeyError(node_id)

    def get_edge_detail(self, edge_id: str) -> dict[str, Any]:
        if edge_id.startswith("relation:"):
            relation_id = edge_id.split(":", maxsplit=1)[1]
            relation = self.graph_store.get_relation(relation_id)
            if relation is None:
                raise KeyError(edge_id)
            paragraph = None
            source = None
            if relation.get("source_paragraph_id"):
                paragraph = self.source_store.get_paragraph(str(relation["source_paragraph_id"]))
                if paragraph is not None:
                    source = self.source_store.get_source(str(paragraph["source_id"]))
            return {
                "edge": {
                    "id": edge_id,
                    "source": build_entity_node_id(str(relation["subject_entity_id"])),
                    "target": build_entity_node_id(str(relation["object_entity_id"])),
                    "type": self._relation_edge_type(relation),
                    "label": str(relation["predicate"]),
                    "weight": float(relation["confidence"]),
                    "metadata": relation,
                },
                "source": source,
                "paragraph": paragraph,
            }
        if edge_id.startswith("manual:"):
            relation_id = edge_id.split(":", maxsplit=1)[1]
            relation = self.graph_store.get_manual_relation(relation_id)
            if relation is None:
                raise KeyError(edge_id)
            return {
                "edge": {
                    "id": edge_id,
                    "source": str(relation["subject_node_id"]),
                    "target": str(relation["object_node_id"]),
                    "type": "manual",
                    "label": str(relation["predicate"]),
                    "weight": float(relation["weight"]),
                    "metadata": relation,
                },
                "source": None,
                "paragraph": None,
            }
        if edge_id.startswith("contains:"):
            source_id, paragraph_id = self._parse_binary_edge_id(edge_id, prefix="contains")
            source = self.source_store.get_source(source_id)
            paragraph = self.source_store.get_paragraph(paragraph_id)
            if source is None or paragraph is None or str(paragraph.get("source_id") or "") != source_id:
                raise KeyError(edge_id)
            return {
                "edge": {
                    "id": edge_id,
                    "source": build_source_node_id(source_id),
                    "target": build_paragraph_node_id(paragraph_id),
                    "type": "contains",
                    "label": "Contains paragraph",
                    "weight": 1.0,
                    "metadata": {"source_id": source_id, "paragraph_id": paragraph_id},
                },
                "source": source,
                "paragraph": paragraph,
            }
        if edge_id.startswith("sheet:"):
            source_id, entity_id = self._parse_binary_edge_id(edge_id, prefix="sheet")
            source = self.source_store.get_source(source_id)
            entity = self.graph_store.get_entity(entity_id)
            if source is None or entity is None:
                raise KeyError(edge_id)
            if self._entity_node_type(entity) != "worksheet":
                raise KeyError(edge_id)
            if self._metadata_value(entity, "source_id") != source_id:
                raise KeyError(edge_id)
            return {
                "edge": {
                    "id": edge_id,
                    "source": build_source_node_id(source_id),
                    "target": build_entity_node_id(entity_id),
                    "type": "contains_sheet",
                    "label": "Contains worksheet",
                    "weight": 1.0,
                    "metadata": {
                        "source_id": source_id,
                        "entity_id": entity_id,
                        "worksheet_name": self._metadata_value(entity, "worksheet_name"),
                    },
                },
                "source": source,
                "paragraph": None,
            }
        if edge_id.startswith("mention:"):
            paragraph_id, entity_id = self._parse_binary_edge_id(edge_id, prefix="mention")
            paragraph = self.source_store.get_paragraph(paragraph_id)
            entity = self.graph_store.get_entity(entity_id)
            if paragraph is None or entity is None:
                raise KeyError(edge_id)
            links = self.graph_store.list_paragraph_entity_links(paragraph_ids=[paragraph_id], entity_id=entity_id)
            if not links:
                raise KeyError(edge_id)
            source = self.source_store.get_source(str(paragraph["source_id"]))
            return {
                "edge": {
                    "id": edge_id,
                    "source": build_paragraph_node_id(paragraph_id),
                    "target": build_entity_node_id(entity_id),
                    "type": "mentions",
                    "label": "Mentions",
                    "weight": 1.0,
                    "metadata": {"paragraph_id": paragraph_id, "entity_id": entity_id},
                },
                "source": source,
                "paragraph": paragraph,
            }
        raise KeyError(edge_id)

    def list_manual_relations(self) -> list[dict[str, Any]]:
        return self.graph_store.list_manual_relations()

    def create_manual_entity(
        self,
        *,
        label: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_label = " ".join(str(label or "").split()).strip()
        if not normalized_label:
            raise ValueError("实体名称不能为空。")

        entity = self.graph_store.create_entity(
            display_name=normalized_label,
            description=description,
            metadata={
                "entity_kind": "manual_entity",
                "manual_created": True,
                **dict(metadata or {}),
            },
            appearance_count=0,
        )
        return {
            "id": build_entity_node_id(str(entity["id"])),
            "type": "entity",
            "label": self._entity_node_label(entity),
            "size": self._entity_node_size(entity),
            "score": None,
            "metadata": entity,
        }

    def create_manual_relation(
        self,
        *,
        subject_node_id: str,
        predicate: str,
        object_node_id: str,
        weight: float,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_subject_node_id = str(subject_node_id or "").strip()
        normalized_object_node_id = str(object_node_id or "").strip()
        normalized_predicate = str(predicate or "").strip()
        if not normalized_subject_node_id or not normalized_object_node_id:
            raise ValueError("手工关系必须选择起点和终点节点。")
        if not normalized_predicate:
            raise ValueError("手工关系谓词不能为空。")
        if weight <= 0:
            raise ValueError("手工关系权重必须大于 0。")
        self._assert_node_exists(normalized_subject_node_id)
        self._assert_node_exists(normalized_object_node_id)
        return self.graph_store.create_manual_relation(
            subject_node_id=normalized_subject_node_id,
            predicate=normalized_predicate,
            object_node_id=normalized_object_node_id,
            weight=weight,
            metadata=metadata,
        )

    def delete_manual_relation(self, relation_id: str) -> bool:
        return self.graph_store.delete_manual_relation(relation_id)

    def update_node_label(self, node_id: str, label: str) -> None:
        normalized_label = " ".join(str(label or "").split()).strip()
        if not normalized_label:
            raise ValueError("节点名称不能为空。")

        if node_id.startswith("source:"):
            source_id = node_id.split(":", maxsplit=1)[1]
            updated_source = self.source_store.update_source(source_id, name=normalized_label)
            if updated_source is None:
                raise KeyError(node_id)
            return

        if node_id.startswith("entity:"):
            entity_id = node_id.split(":", maxsplit=1)[1]
            updated_entity = self.graph_store.update_entity(entity_id, display_name=normalized_label)
            if updated_entity is None:
                raise KeyError(node_id)
            return

        raise ValueError("当前节点类型不支持重命名。")

    def delete_node(self, node_id: str) -> None:
        if node_id.startswith("source:"):
            self.delete_source(node_id.split(":", maxsplit=1)[1])
            return

        if node_id.startswith("paragraph:"):
            self._delete_paragraph(node_id.split(":", maxsplit=1)[1])
            return

        if node_id.startswith("entity:"):
            self._delete_entity(node_id.split(":", maxsplit=1)[1])
            return

        raise KeyError(node_id)

    def delete_edge(self, edge_id: str) -> None:
        if edge_id.startswith("manual:"):
            relation_id = edge_id.split(":", maxsplit=1)[1]
            if not self.graph_store.delete_manual_relation(relation_id):
                raise KeyError(edge_id)
            return

        if edge_id.startswith("relation:"):
            relation_id = edge_id.split(":", maxsplit=1)[1]
            relation = self.graph_store.get_relation(relation_id)
            if relation is None:
                raise KeyError(edge_id)
            if not self.graph_store.delete_relation(relation_id):
                raise KeyError(edge_id)
            self._cleanup_entities(
                [
                    str(relation["subject_entity_id"]),
                    str(relation["object_entity_id"]),
                ]
            )
            return

        raise ValueError("当前边类型不支持删除。")

    def delete_source(self, source_id: str) -> None:
        source = self.source_store.get_source(source_id)
        if source is None:
            raise KeyError(source_id)

        paragraphs = self.source_store.list_paragraphs_for_source(source_id)
        paragraph_ids = [str(paragraph["id"]) for paragraph in paragraphs]
        source_relations = self.graph_store.list_relations_referencing_source(source_id)
        affected_entity_ids = [
            str(link["entity_id"])
            for link in self.graph_store.list_paragraph_entity_links(paragraph_ids=paragraph_ids)
        ]
        affected_entity_ids.extend(str(relation["subject_entity_id"]) for relation in source_relations)
        affected_entity_ids.extend(str(relation["object_entity_id"]) for relation in source_relations)

        self.graph_store.delete_relations_for_paragraphs(paragraph_ids)
        self.graph_store.delete_relations([str(relation["id"]) for relation in source_relations])
        self.graph_store.delete_manual_relations_for_nodes(
            [build_source_node_id(source_id)] + [build_paragraph_node_id(paragraph_id) for paragraph_id in paragraph_ids]
        )

        if not self.source_store.delete_source(source_id):
            raise KeyError(source_id)

        self.vector_index.remove_source(source_id)
        self._cleanup_entities(affected_entity_ids)

    def _delete_paragraph(self, paragraph_id: str) -> None:
        paragraph = self.source_store.get_paragraph(paragraph_id)
        if paragraph is None:
            raise KeyError(paragraph_id)

        affected_entity_ids = [
            str(link["entity_id"])
            for link in self.graph_store.list_paragraph_entity_links(paragraph_ids=[paragraph_id])
        ]
        paragraph_relations = self.graph_store.list_relations_for_paragraph(paragraph_id)
        affected_entity_ids.extend(str(relation["subject_entity_id"]) for relation in paragraph_relations)
        affected_entity_ids.extend(str(relation["object_entity_id"]) for relation in paragraph_relations)

        self.graph_store.delete_relations_for_paragraphs([paragraph_id])
        self.graph_store.delete_manual_relations_for_node(build_paragraph_node_id(paragraph_id))

        if not self.source_store.delete_paragraph(paragraph_id):
            raise KeyError(paragraph_id)

        self.vector_index.remove_paragraphs([paragraph_id])
        self._cleanup_entities(affected_entity_ids)

    def _delete_entity(self, entity_id: str) -> None:
        entity = self.graph_store.get_entity(entity_id)
        if entity is None:
            raise KeyError(entity_id)

        self.graph_store.delete_manual_relations_for_node(build_entity_node_id(entity_id))
        if not self.graph_store.delete_entity(entity_id):
            raise KeyError(entity_id)

    def _cleanup_entities(self, entity_ids: list[str]) -> None:
        for entity_id in {str(item).strip() for item in entity_ids if str(item).strip()}:
            entity = self.graph_store.get_entity(entity_id)
            if entity is None:
                continue

            paragraph_link_count = self.graph_store.count_paragraph_links_for_entity(entity_id)
            relation_count = self.graph_store.count_relations_for_entity(entity_id)
            is_manual_entity = bool(dict(entity.get("metadata") or {}).get("manual_created"))
            if paragraph_link_count <= 0 and relation_count <= 0:
                if is_manual_entity:
                    self.graph_store.set_entity_appearance_count(entity_id, paragraph_link_count)
                    continue
                self.graph_store.delete_manual_relations_for_node(build_entity_node_id(entity_id))
                self.graph_store.delete_entity(entity_id)
                continue

            self.graph_store.set_entity_appearance_count(entity_id, paragraph_link_count)

    def _source_node_type(self, source: dict[str, Any]) -> str:
        metadata = dict(source.get("metadata") or {})
        file_type = str(source.get("file_type") or "").strip().lower()
        if int(metadata.get("spreadsheet_sheet_count") or 0) > 0 or file_type in SPREADSHEET_FILE_TYPES:
            return "workbook"
        return "source"

    def _source_node_size(self, source: dict[str, Any]) -> float:
        return 10.0 if self._source_node_type(source) == "workbook" else 8.0

    def _entity_node_type(self, entity: dict[str, Any]) -> str:
        entity_kind = self._metadata_value(entity, "entity_kind")
        if entity_kind == "worksheet":
            return "worksheet"
        if entity_kind == "row_record":
            return "record"
        return "entity"

    def _entity_node_label(self, entity: dict[str, Any]) -> str:
        entity_kind = self._metadata_value(entity, "entity_kind")
        if entity_kind == "worksheet":
            return self._metadata_value(entity, "display_label") or self._metadata_value(entity, "worksheet_name") or str(
                entity["display_name"]
            )
        if entity_kind == "row_record":
            return self._metadata_value(entity, "display_label") or str(entity["display_name"])
        return str(entity["display_name"])

    def _entity_node_size(self, entity: dict[str, Any]) -> float:
        entity_kind = self._metadata_value(entity, "entity_kind")
        if entity_kind == "worksheet":
            return 13.0
        if entity_kind == "row_record":
            return 8.0
        return max(2.0, min(float(entity.get("appearance_count") or 1) / 2.0 + 2.0, 10.0))

    def _relation_edge_type(self, relation: dict[str, Any]) -> str:
        metadata = dict(relation.get("metadata") or {})
        relation_source = str(metadata.get("relation_source") or "")
        if relation_source == "spreadsheet_structure" or str(relation.get("predicate") or "") == "has_record":
            return "contains_record"
        return "relation"

    def _metadata_value(self, row: dict[str, Any], key: str) -> str:
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            return ""
        value = metadata.get(key)
        return str(value).strip() if value is not None else ""

    def _assert_node_exists(self, node_id: str) -> None:
        if node_id.startswith("source:"):
            source_id = node_id.split(":", maxsplit=1)[1]
            if self.source_store.get_source(source_id) is not None:
                return
        elif node_id.startswith("paragraph:"):
            paragraph_id = node_id.split(":", maxsplit=1)[1]
            if self.source_store.get_paragraph(paragraph_id) is not None:
                return
        elif node_id.startswith("entity:"):
            entity_id = node_id.split(":", maxsplit=1)[1]
            if self.graph_store.get_entity(entity_id) is not None:
                return
        raise ValueError("手工关系引用了不存在的图谱节点。")

    def _parse_binary_edge_id(self, edge_id: str, *, prefix: str) -> tuple[str, str]:
        parts = edge_id.split(":", maxsplit=2)
        if len(parts) != 3 or parts[0] != prefix:
            raise KeyError(edge_id)
        return parts[1], parts[2]

    def _apply_density_filter(self, edges: list[dict[str, Any]], *, density: int) -> list[dict[str, Any]]:
        normalized_density = max(5, min(density, 100))
        if normalized_density >= 100 or len(edges) <= 1:
            return edges
        edge_limit = max(1, round(len(edges) * normalized_density / 100))
        return sorted(edges, key=lambda edge: edge["weight"], reverse=True)[:edge_limit]

    def _prune_dangling_edges(self, edges: list[dict[str, Any]], *, node_ids: set[str]) -> list[dict[str, Any]]:
        return [
            edge
            for edge in edges
            if str(edge.get("source") or "") in node_ids and str(edge.get("target") or "") in node_ids
        ]

    def _paragraph_label(self, content: str) -> str:
        compact = " ".join(content.split())
        return compact if len(compact) <= 28 else f"{compact[:28]}..."




