"""模块名称：services.entity_extraction_service

features：按窗口批量调用 LLM 做实体关系抽取，并对多批结果去重合并。
"""

from collections.abc import Callable

from src.data import normalize_entity_name
from src.schemas import ExtractionResult, ExtractedEntity, ExtractedRelation
from src.services.openai_service import OpenAiService
from src.utils.logging_utils import get_logger

MAX_EXTRACTION_WINDOW_CHARACTERS: int = 12000
MAX_EXTRACTION_WINDOW_CHUNKS: int = 6
ExtractionProgressCallback = Callable[[int, int, str], None]

logger = get_logger(__name__)


class ExtractionWindow:
    """抽取窗口。

    Attributes:
        index (int): 窗口序号。
        chunk_indexes (list[int]): 窗口包含的切块序号。
        text (str): 窗口拼接后的文本。
    """

    def __init__(self, index: int, chunk_indexes: list[int], text: str) -> None:
        """初始化抽取窗口。

        Args:
            index: 窗口序号。
            chunk_indexes: 窗口包含的切块序号。
            text: 窗口拼接后的文本。
        """

        self.index: int = index
        self.chunk_indexes: list[int] = chunk_indexes
        self.text: str = text


class EntityExtractionService:
    """实体抽取服务。

    Attributes:
        openai_service (OpenAiService): OpenAI 服务。
        max_window_characters (int): 单个抽取窗口允许的最大字符数。
        max_window_chunks (int): 单个抽取窗口允许的最大切块数。
    """

    def __init__(
        self,
        *,
        openai_service: OpenAiService,
        max_window_characters: int = MAX_EXTRACTION_WINDOW_CHARACTERS,
        max_window_chunks: int = MAX_EXTRACTION_WINDOW_CHUNKS,
    ) -> None:
        """初始化实体抽取服务。

        Args:
            openai_service: OpenAI 服务。
            max_window_characters: 单个抽取窗口允许的最大字符数。
            max_window_chunks: 单个抽取窗口允许的最大切块数。
        """

        self.openai_service: OpenAiService = openai_service
        self.max_window_characters: int = max_window_characters
        self.max_window_chunks: int = max_window_chunks

    def build_windows(self, chunk_texts: list[str]) -> list[ExtractionWindow]:
        """根据字符数和切块数量限制构建抽取窗口。

        Args:
            chunk_texts: 文档切块文本列表。

        Returns:
            list[ExtractionWindow]: 抽取窗口列表。
        """

        return self._build_windows(chunk_texts)

    def extract_document_graph(
        self,
        document_name: str,
        chunk_texts: list[str],
        *,
        windows: list[ExtractionWindow] | None = None,
        progress_callback: ExtractionProgressCallback | None = None,
    ) -> ExtractionResult:
        """对整篇文档执行分批实体关系抽取。

        Args:
            document_name: 文档名称。
            chunk_texts: 文档切块文本列表。
            windows: 已预构建的抽取窗口列表。
            progress_callback: 每个窗口开始或完成时触发的进度回调。

        Returns:
            ExtractionResult: 聚合去重后的抽取结果。
        """

        extraction_windows: list[ExtractionWindow] = [
            window for window in (windows or self.build_windows(chunk_texts)) if window.text.strip()
        ]
        partial_results: list[ExtractionResult] = []
        logger.info("实体抽取窗口已准备完成: document_name=%s window_count=%s", document_name, len(extraction_windows))

        for window_index, window in enumerate(extraction_windows, start=1):
            if progress_callback is not None:
                progress_callback(window_index, len(extraction_windows), "started")

            logger.info(
                "开始抽取窗口: document_name=%s window=%s/%s chunk_count=%s",
                document_name,
                window_index,
                len(extraction_windows),
                len(window.chunk_indexes),
            )
            partial_result: ExtractionResult = self.openai_service.extract_entities(
                document_name=document_name,
                text=window.text,
                window_label=f"window-{window.index}",
            )
            partial_results.append(partial_result)

            logger.info(
                "完成抽取窗口: document_name=%s window=%s/%s entity_count=%s relation_count=%s",
                document_name,
                window_index,
                len(extraction_windows),
                len(partial_result.entities),
                len(partial_result.relations),
            )
            if progress_callback is not None:
                progress_callback(window_index, len(extraction_windows), "completed")

        return self._merge_results(partial_results)

    def _build_windows(self, chunk_texts: list[str]) -> list[ExtractionWindow]:
        """根据字符数和切块数量限制构建抽取窗口。

        Args:
            chunk_texts: 文档切块文本列表。

        Returns:
            list[ExtractionWindow]: 抽取窗口列表。
        """

        windows: list[ExtractionWindow] = []
        current_texts: list[str] = []
        current_indexes: list[int] = []
        current_length: int = 0

        for chunk_index, chunk_text in enumerate(chunk_texts):
            normalized_text: str = chunk_text.strip()
            if not normalized_text:
                continue

            next_length: int = current_length + len(normalized_text)
            should_flush: bool = (
                bool(current_texts)
                and (
                    len(current_texts) >= self.max_window_chunks
                    or next_length > self.max_window_characters
                )
            )
            if should_flush:
                windows.append(
                    ExtractionWindow(
                        index=len(windows),
                        chunk_indexes=current_indexes.copy(),
                        text="\n\n".join(current_texts),
                    )
                )
                current_texts = []
                current_indexes = []
                current_length = 0

            current_texts.append(normalized_text[: self.max_window_characters])
            current_indexes.append(chunk_index)
            current_length += len(current_texts[-1])

        if current_texts:
            windows.append(
                ExtractionWindow(
                    index=len(windows),
                    chunk_indexes=current_indexes.copy(),
                    text="\n\n".join(current_texts),
                )
            )
        return windows

    def _merge_results(self, partial_results: list[ExtractionResult]) -> ExtractionResult:
        """合并多个抽取窗口返回的结果。

        Args:
            partial_results: 多个窗口返回的抽取结果。

        Returns:
            ExtractionResult: 合并去重后的结果。
        """

        entity_map: dict[str, ExtractedEntity] = {}
        relation_map: dict[tuple[str, str, str], ExtractedRelation] = {}

        for partial_result in partial_results:
            for entity in partial_result.entities:
                normalized_name: str = normalize_entity_name(entity.name)
                if not normalized_name:
                    continue
                existing_entity: ExtractedEntity | None = entity_map.get(normalized_name)
                if existing_entity is None:
                    entity_map[normalized_name] = ExtractedEntity(
                        name=entity.name.strip(),
                        description=entity.description.strip(),
                    )
                    continue
                if len(entity.description.strip()) > len(existing_entity.description):
                    existing_entity.description = entity.description.strip()

            for relation in partial_result.relations:
                source_name: str = normalize_entity_name(relation.source)
                target_name: str = normalize_entity_name(relation.target)
                relation_name: str = relation.relation.strip().lower()
                if not source_name or not target_name or not relation_name:
                    continue
                relation_key: tuple[str, str, str] = (source_name, target_name, relation_name)
                existing_relation: ExtractedRelation | None = relation_map.get(relation_key)
                if existing_relation is None:
                    relation_map[relation_key] = ExtractedRelation(
                        source=relation.source.strip(),
                        target=relation.target.strip(),
                        relation=relation.relation.strip(),
                        weight=relation.weight,
                    )
                    continue
                existing_relation.weight = max(existing_relation.weight, relation.weight)

        return ExtractionResult(
            entities=list(entity_map.values()),
            relations=list(relation_map.values()),
        )
