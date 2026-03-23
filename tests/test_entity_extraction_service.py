"""模块名称：tests.test_entity_extraction_service

主要功能：验证实体抽取服务会按窗口抽取并对多批结果进行去重聚合。
"""

from kb_graph.contracts.extraction_contracts import ExtractionResult, ExtractedEntity, ExtractedRelation
from kb_graph.services.entity_extraction_service import EntityExtractionService


class FakeOpenAiService:
    """用于测试的 OpenAI 服务替身。"""

    def __init__(self) -> None:
        """初始化测试替身。"""

        self.calls: list[tuple[str, str, str]] = []

    def extract_entities(
        self,
        document_name: str,
        text: str,
        *,
        window_label: str = "window",
    ) -> ExtractionResult:
        """根据窗口文本返回预设抽取结果。

        Args:
            document_name: 文档名称。
            text: 当前窗口文本。
            window_label: 当前窗口标识。

        Returns:
            ExtractionResult: 预设的抽取结果。
        """

        self.calls.append((document_name, window_label, text))
        if "Alice" in text:
            return ExtractionResult(
                entities=[
                    ExtractedEntity(name="Alice", description="Founder"),
                    ExtractedEntity(name="Acme", description="Company"),
                ],
                relations=[
                    ExtractedRelation(source="Alice", target="Acme", relation="founded", weight=1.1),
                ],
            )
        return ExtractionResult(
            entities=[
                ExtractedEntity(name="acme", description="A robotics startup"),
                ExtractedEntity(name="Bob", description="Engineer"),
            ],
            relations=[
                ExtractedRelation(source="Alice", target="ACME", relation="founded", weight=1.8),
                ExtractedRelation(source="Acme", target="Bob", relation="employs", weight=0.9),
            ],
        )


def test_entity_extraction_service_merges_results_from_multiple_windows():
    """验证多窗口抽取结果会按实体和关系去重聚合。"""

    fake_openai_service = FakeOpenAiService()
    service = EntityExtractionService(
        openai_service=fake_openai_service,
        max_window_characters=80,
        max_window_chunks=1,
    )

    result = service.extract_document_graph(
        document_name="acme-notes.txt",
        chunk_texts=["Alice founded Acme in 2024.", "Acme hired Bob to expand the robotics team."],
    )

    entity_names = {entity.name.lower() for entity in result.entities}
    relation_keys = {(relation.source.lower(), relation.target.lower(), relation.relation.lower()) for relation in result.relations}
    acme_entity = next(entity for entity in result.entities if entity.name.lower() == "acme")
    founded_relation = next(relation for relation in result.relations if relation.relation.lower() == "founded")

    assert len(fake_openai_service.calls) == 2
    assert entity_names == {"alice", "acme", "bob"}
    assert acme_entity.description == "A robotics startup"
    assert relation_keys == {
        ("alice", "acme", "founded"),
        ("acme", "bob", "employs"),
    }
    assert founded_relation.weight == 1.8


def test_entity_extraction_service_handles_empty_chunks():
    """验证空切块列表不会触发抽取请求。"""

    fake_openai_service = FakeOpenAiService()
    service = EntityExtractionService(openai_service=fake_openai_service)

    result = service.extract_document_graph(document_name="empty.txt", chunk_texts=[])

    assert result.entities == []
    assert result.relations == []
    assert fake_openai_service.calls == []
