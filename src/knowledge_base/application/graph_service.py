"""Application service for graph projection and manual relations."""

from typing import Any

from src.knowledge_base.domain import (
    build_contains_edge_id,
    build_entity_node_id,
    build_manual_edge_id,
    build_mention_edge_id,
    build_paragraph_node_id,
    build_relation_edge_id,
    build_sheet_edge_id,
    build_source_node_id,
)
from src.knowledge_base.infrastructure import GraphRepository, SourceRepository

SPREADSHEET_FILE_TYPES: set[str] = {"xlsx", "xlsm", "xls"}


class GraphService:
    """Project graph nodes, edges, and details from repository data."""

    def __init__(self, *, graph_repository: GraphRepository, source_repository: SourceRepository) -> None:
        self.graph_repository = graph_repository
        self.source_repository = source_repository

    def build_graph(
        self,
        *,
        source_ids: list[str] | None = None,
        include_paragraphs: bool = True,
        density: int = 100,
    ) -> dict[str, list[dict[str, Any]]]:
        source_rows = self.graph_repository.list_graph_sources(source_ids)
        paragraph_rows = self.graph_repository.list_graph_paragraphs(source_ids)
        paragraph_ids = {str(row["id"]) for row in paragraph_rows}
        entity_rows = self.graph_repository.list_graph_entities(source_ids)
        relation_rows = self.graph_repository.list_graph_relations(source_ids)
        manual_rows = self.graph_repository.list_manual_relations()
        paragraph_entity_links = self.graph_repository.list_paragraph_entity_links(source_ids=source_ids)

        nodes: list[dict[str, Any]] = []
        structural_edges: list[dict[str, Any]] = []
        semantic_edges: list[dict[str, Any]] = []

        for source in source_rows:
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

        for relation in manual_rows:
            semantic_edges.append(
                {
                    "id": build_manual_edge_id(str(relation["id"])),
                    "source": str(relation["subject_node_id"]),
                    "target": str(relation["object_node_id"]),
                    "type": "manual",
                    "label": str(relation["predicate"]),
                    "weight": float(relation["weight"]),
                    "metadata": relation,
                }
            )

        return {"nodes": nodes, "edges": structural_edges + self._apply_density_filter(semantic_edges, density=density)}

    def get_node_detail(self, node_id: str) -> dict[str, Any]:
        if node_id.startswith("source:"):
            source_id = node_id.split(":", maxsplit=1)[1]
            source = self.source_repository.get_source(source_id)
            if source is None:
                raise KeyError(node_id)
            paragraphs = self.source_repository.list_source_paragraphs(source_id)[:12]
            relations = self.graph_repository.list_relations_for_source(source_id, limit=20)
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
            paragraph = self.source_repository.get_paragraph(paragraph_id)
            if paragraph is None:
                raise KeyError(node_id)
            source = self.source_repository.get_source(str(paragraph["source_id"]))
            relations = self.graph_repository.list_relations_for_paragraph(paragraph_id)
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
            entity = self.graph_repository.get_entity(entity_id)
            if entity is None:
                raise KeyError(node_id)
            paragraphs = self.graph_repository.list_paragraphs_for_entity(entity_id, limit=12)
            relations = self.graph_repository.list_relations_for_entity(entity_id, limit=24)
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
            relation = self.graph_repository.get_relation(relation_id)
            if relation is None:
                raise KeyError(edge_id)
            paragraph = None
            source = None
            if relation.get("source_paragraph_id"):
                paragraph = self.source_repository.get_paragraph(str(relation["source_paragraph_id"]))
                if paragraph is not None:
                    source = self.source_repository.get_source(str(paragraph["source_id"]))
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
            relation = self.graph_repository.get_manual_relation(relation_id)
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
            _, source_id, paragraph_id = edge_id.split(":", maxsplit=2)
            source = self.source_repository.get_source(source_id)
            paragraph = self.source_repository.get_paragraph(paragraph_id)
            if source is None or paragraph is None:
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
            _, source_id, entity_id = edge_id.split(":", maxsplit=2)
            source = self.source_repository.get_source(source_id)
            entity = self.graph_repository.get_entity(entity_id)
            if source is None or entity is None:
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
            _, paragraph_id, entity_id = edge_id.split(":", maxsplit=2)
            paragraph = self.source_repository.get_paragraph(paragraph_id)
            source = None
            if paragraph is not None:
                source = self.source_repository.get_source(str(paragraph["source_id"]))
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
        return self.graph_repository.list_manual_relations()

    def create_manual_relation(
        self,
        *,
        subject_node_id: str,
        predicate: str,
        object_node_id: str,
        weight: float,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return self.graph_repository.create_manual_relation(
            subject_node_id=subject_node_id,
            predicate=predicate,
            object_node_id=object_node_id,
            weight=weight,
            metadata=metadata,
        )

    def delete_manual_relation(self, relation_id: str) -> bool:
        return self.graph_repository.delete_manual_relation(relation_id)

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

    def _apply_density_filter(self, edges: list[dict[str, Any]], *, density: int) -> list[dict[str, Any]]:
        normalized_density = max(5, min(density, 100))
        if normalized_density >= 100 or len(edges) <= 1:
            return edges
        edge_limit = max(1, round(len(edges) * normalized_density / 100))
        return sorted(edges, key=lambda edge: edge["weight"], reverse=True)[:edge_limit]

    def _paragraph_label(self, content: str) -> str:
        compact = " ".join(content.split())
        return compact if len(compact) <= 28 else f"{compact[:28]}..."
