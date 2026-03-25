# Importing Package Guide

`src/kb/importing/` 负责把不同来源的输入统一整理成知识库导入项，再交给 `src/kb/application/imports/service.py` 执行入库、向量化和图谱写入。

## 导入来源

- `upload`: 前端上传的原始文件。文件会先写入上传目录，再进入统一解析流程。
- `paste`: 用户粘贴的纯文本。适合临时录入，不依赖文件系统。
- `scan`: 扫描允许目录下的文件并批量导入。适合接入现有资料库。
- `openie`: 外部 OpenIE 或抽取链路生成的结构化 JSON。实体和关系直接复用。
- `convert`: 其他系统转换后的结构化 JSON。可携带 `paragraphs`、`entities`、`relations`。

## 输入模式

- `file`: 文件入口，当前支持 `txt`、`pdf`、`docx`、`xlsx`、`xlsm`、`xls`。
- `text`: 纯文本入口。
- `json`: 结构化 JSON 入口。

## 分块策略

- `auto`: 根据文件类型和文本形态自动判断。
- `factual`: 面向事实、条目、表格、说明文。
- `narrative`: 面向连续叙事文本，保留更长上下文。
- `quote`: 面向短句、引用、台词或按行组织的文本。

## Excel 相关

- `excel/reader.py`: 负责把工作簿读成统一的工作表数据结构。
- `excel/models.py`: 定义工作簿、工作表、行对象的数据模型。
- `excel/schema.py`: 定义和校验侧车 schema，约定文件名为 `<workbook>.schema.json`。
- `excel/normalizer.py`: 归一化列名、工作表名、单元格文本。
- `excel/mapper.py`: 把工作簿映射成段落、实体、关系与元数据 bundle。

## 侧车 Schema 规则

- 侧车 schema 只对 Excel 文件生效。
- 上传模式下，schema 文件和工作簿一起上传，通过同名 stem 自动配对。
- 扫描模式下，schema 文件需要和工作簿位于同一目录，命名规则同样是 `<workbook>.schema.json`。
- 没有 schema 时，系统仍会导入 Excel，但只会依靠表头和行数据生成基础结构。
