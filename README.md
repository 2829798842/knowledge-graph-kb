# 知识图谱知识库工作台

这是一个本地优先的知识库工作台项目，后端基于 FastAPI，前端基于 React。系统使用 SQLite 持久化业务数据，使用 FAISS 保存段落向量索引，并通过统一导入流水线把文本、文档、表格和结构化 JSON 写入知识库。

## 主要能力

- 导入 `txt`、`pdf`、`docx`、`xlsx`、`xlsm`、`xls`
- 支持上传、粘贴、目录扫描、OpenIE JSON、转换后 JSON 五类导入入口
- 执行结构化检索、向量检索、融合检索和图谱重排
- 浏览来源、段落、实体、关系和手工关系
- 配置模型提供商、通用模型、嵌入模型和加密保存 API Key
- 提供聊天问答、记录检索、实体检索、关系检索、来源检索

## 当前后端结构

```text
src/
|-- api/                       # HTTP 路由、依赖注入、请求响应模型
|-- config/                    # 环境变量与路径解析
|-- kb/
|   |-- common.py              # 公共时间、运行时配置、图谱 ID 构造
|   |-- container.py           # 知识库运行时容器
|   |-- application/
|   |   |-- services/          # 对话、图谱、来源、模型配置等应用服务
|   |   |-- search/            # 记录、实体、关系、来源检索服务
|   |   |-- retrieval/         # 结构化检索、向量检索、融合与 PPR 重排
|   |   `-- imports/           # 导入任务、执行器、导入流水线
|   |-- database/              # SQLite 网关
|   |-- providers/             # 外部模型提供商适配
|   |-- storage/               # 向量索引与 SQLite 仓储实现
|   `-- importing/             # 导入解析、分块、Excel 映射与说明文档
|-- utils/                     # logger、文件名清洗、密钥工具
`-- web/                       # 前端静态资源托管
```

## API 分组

- `/api/system/*`: 系统健康检查
- `/api/kb/config/model`: 模型配置读取、更新、连通性测试
- `/api/kb/imports/*`: 导入任务提交、查询、取消、重试
- `/api/kb/chat/*`: 会话和问答消息
- `/api/kb/search/*`: 记录、实体、关系、来源检索
- `/api/kb/graph/*`: 图谱浏览和手工关系
- `/api/kb/sources/*`: 来源列表、详情、段落

## 导入说明

- 导入来源分为 `upload`、`paste`、`scan`、`openie`、`convert`
- 输入模式分为 `file`、`text`、`json`
- 分块策略分为 `auto`、`factual`、`narrative`、`quote`
- Excel 支持同名侧车 schema，命名为 `<workbook>.schema.json`
- 更详细的导入说明见 [src/kb/importing/README.md](/d:/code/AI/new_project/knowledge-graph-kb/src/kb/importing/README.md)

## 运行方式

### 后端

```bash
uv sync
uv run python main.py
```

默认地址：

```text
http://localhost:8000
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

## 常用检查

```bash
uv run python -m compileall main.py src
uv run pytest -q
cd frontend && pnpm build
```
