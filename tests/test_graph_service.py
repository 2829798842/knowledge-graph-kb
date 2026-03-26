import pytest

from src.kb.application.services.graph import GraphService


class GraphStoreStub:
    def __init__(self) -> None:
        self.entities = {"entity-1": {"id": "entity-1", "display_name": "实体", "metadata": {}}}
        self.paragraph_entity_links = {("paragraph-1", "entity-1"): {"paragraph_id": "paragraph-1", "entity_id": "entity-1"}}
        self.created_manual_relation: dict | None = None

    def get_entity(self, entity_id: str):
        return self.entities.get(entity_id)

    def list_paragraph_entity_links(self, *, paragraph_ids=None, entity_id=None, source_ids=None):
        if paragraph_ids and entity_id:
            return [
                self.paragraph_entity_links[(paragraph_id, entity_id)]
                for paragraph_id in paragraph_ids
                if (paragraph_id, entity_id) in self.paragraph_entity_links
            ]
        return []

    def create_manual_relation(self, **payload):
        self.created_manual_relation = payload
        return payload

    def get_relation(self, relation_id: str):
        return None

    def get_manual_relation(self, relation_id: str):
        return None

    def list_manual_relations(self):
        return []


class SourceStoreStub:
    def __init__(self) -> None:
        self.sources = {"source-1": {"id": "source-1", "name": "来源", "metadata": {}, "file_type": "txt"}}
        self.paragraphs = {
            "paragraph-1": {"id": "paragraph-1", "source_id": "source-1", "content": "段落内容"},
            "paragraph-2": {"id": "paragraph-2", "source_id": "source-2", "content": "另一段内容"},
        }

    def get_source(self, source_id: str):
        return self.sources.get(source_id)

    def get_paragraph(self, paragraph_id: str):
        return self.paragraphs.get(paragraph_id)


def test_create_manual_relation_rejects_missing_nodes() -> None:
    service = GraphService(graph_store=GraphStoreStub(), source_store=SourceStoreStub())

    with pytest.raises(ValueError):
        service.create_manual_relation(
            subject_node_id="source:missing",
            predicate="相关",
            object_node_id="entity:entity-1",
            weight=1.0,
            metadata={},
        )


def test_get_edge_detail_rejects_mismatched_contains_edge() -> None:
    service = GraphService(graph_store=GraphStoreStub(), source_store=SourceStoreStub())

    with pytest.raises(KeyError):
        service.get_edge_detail("contains:source-1:paragraph-2")


def test_get_edge_detail_rejects_fabricated_mention_edge() -> None:
    service = GraphService(graph_store=GraphStoreStub(), source_store=SourceStoreStub())

    with pytest.raises(KeyError):
        service.get_edge_detail("mention:paragraph-2:entity-1")
