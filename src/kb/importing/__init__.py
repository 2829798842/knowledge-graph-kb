"""知识库导入辅助函数与导入类型说明。"""

from .excel import EXCEL_FILE_TYPES, build_excel_import_bundle, load_excel_document, supports_excel_file_type
from .payloads import build_structured_import_item, build_text_import_item
from .strategy import normalize_strategy, select_strategy, split_text_by_strategy

IMPORT_SOURCE_KIND_DESCRIPTIONS: dict[str, str] = {
    "upload": "用户上传的原始文件，先落盘，再走统一解析与导入流水线。",
    "paste": "用户直接粘贴的纯文本内容，不依赖本地文件路径。",
    "scan": "扫描允许目录下的文件并批量导入，适合已有资料库接入。",
    "openie": "外部 OpenIE 或抽取系统生成的结构化 JSON，直接复用实体和关系。",
    "convert": "其他系统转换后的结构化 JSON，可携带 paragraphs/entities/relations。",
}
IMPORT_INPUT_MODE_DESCRIPTIONS: dict[str, str] = {
    "file": "以文件为入口，支持 txt、pdf、docx、xlsx、xlsm、xls。",
    "text": "以纯文本为入口，适合临时录入或快速试验。",
    "json": "以结构化 JSON 为入口，适合 OpenIE、转换结果或外部管道对接。",
}
IMPORT_STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "auto": "根据文件扩展名和文本形态自动选择分块策略。",
    "narrative": "偏连续叙事文本，保留较长上下文和更宽的重叠窗口。",
    "factual": "偏事实、条目、表格与说明文本，使用标准分块参数。",
    "quote": "偏短句、引语、诗句或台词，优先按行聚合。",
}
EXCEL_IMPORT_OVERVIEW: dict[str, str] = {
    "workbook": "Excel 文件会先解析为工作簿/工作表/行数据，再生成段落、实体和关系。",
    "sidecar_schema": "可选同名侧车 schema 文件，命名为 <workbook>.schema.json，用于声明主键、列角色、关系模板等。",
    "fallback": "没有侧车 schema 时，系统仍会按表头和单元格内容构建基础记录与工作表节点。",
}

__all__ = [
    "EXCEL_FILE_TYPES",
    "EXCEL_IMPORT_OVERVIEW",
    "IMPORT_INPUT_MODE_DESCRIPTIONS",
    "IMPORT_SOURCE_KIND_DESCRIPTIONS",
    "IMPORT_STRATEGY_DESCRIPTIONS",
    "build_excel_import_bundle",
    "build_structured_import_item",
    "build_text_import_item",
    "load_excel_document",
    "normalize_strategy",
    "select_strategy",
    "split_text_by_strategy",
    "supports_excel_file_type",
]
