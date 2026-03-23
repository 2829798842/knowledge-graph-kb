# 项目名称

Knowledge Graph KB

## 项目简介

Knowledge Graph KB 是一个基于 `uv`、FastAPI、React 与 Cytoscape.js 的本地优先知识库项目。系统支持导入个人文档，使用 `text-embedding-3-large` 生成向量，结合大语言模型抽取实体与关系，再通过个性化 PageRank 对图谱子图进行重排，最终返回带引用来源的问答结果。

当前项目包含以下核心能力：

- 文档导入：支持 `.txt`、`.pdf`、`.docx` 文件上传与索引。
- 图谱浏览：在前端查看文档、切块、实体及其连接关系。
- 手工连边：支持在前端手动创建与删除连接，并参与后续排序。
- 检索问答：先走向量召回，再执行个性化 PageRank，最后交给大语言模型生成答案。
- 实体抽取：按多窗口分批抽取实体关系，聚合去重后写入图谱。
- 一体化启动：后端可直接托管前端静态文件，使用 `uv run python main.py` 即可启动服务。

## 快速开始

### 1. 准备环境变量

复制 `.env.example` 为 `.env`，并按需调整以下变量：

- `OPENAI_API_KEY`
- `OPENAI_LLM_MODEL`
- `OPENAI_EMBED_MODEL`
- `DATABASE_URL`
- `LANCEDB_PATH`
- `UPLOAD_DIR`
- `FRONTEND_DIST_DIR`
- `SERVER_HOST`
- `SERVER_PORT`

默认模型配置如下：

- 大语言模型：`gpt-5.4-mini`
- 嵌入模型：`text-embedding-3-large`

### 2. 安装后端依赖

```bash
uv sync --all-extras
```

### 3. 安装前端依赖并构建静态文件

```bash
cd frontend
pnpm install
pnpm build
```

### 4. 一体化启动服务

```bash
uv run python main.py
```

默认地址：`http://localhost:8000`

启动后：

- `GET /api/*` 由 FastAPI 提供接口能力。
- `/` 与其他前端路由由后端直接托管 `frontend/dist` 中的静态文件。

### 5. 前端独立开发模式

如果需要单独调试前端，可继续使用：

```bash
cd frontend
pnpm dev
```

默认地址：`http://localhost:5173`

当修改了前端代码并希望通过 `uv run python main.py` 查看最新页面时，需要重新执行一次 `pnpm build`。

## 项目结构

```text
knowledge-graph-kb/
|-- frontend/
|   |-- dist/                   # 前端构建后的静态资源
|   `-- src/
|       |-- app.tsx
|       |-- main.tsx
|       |-- styles/
|       `-- features/
|           `-- knowledge_base/
|               |-- api/        # 前端 API 封装
|               |-- components/ # 工作区、图谱、面板组件
|               |-- constants/  # 常量配置
|               |-- hooks/      # 状态与行为管理
|               |-- types/      # 前端类型定义
|               `-- utils/      # 任务与轮询辅助函数
|-- src/
|   `-- kb_graph/
|       |-- api/                # FastAPI 路由与依赖
|       |-- config/             # 应用配置与路径解析
|       |-- contracts/          # API 契约与内部抽取契约
|       |-- data/               # 数据模型与数据库会话
|       |-- services/           # 解析、嵌入、抽取、建图、查询服务
|       |-- utils/              # 通用工具函数
|       `-- web/                # 前端静态资源托管与 Web 入口
|-- tests/                      # 后端测试
|-- main.py                     # 根目录统一启动入口
|-- pyproject.toml
|-- requirements.txt
`-- pnpm-workspace.yaml
```

## 常用命令

```bash
uv run pytest
cd frontend && pnpm test
cd frontend && pnpm build
uv run python main.py
```

## 主要接口

- `POST /api/files/import`
- `GET /api/jobs/{job_id}`
- `GET /api/documents`
- `GET /api/documents/{document_id}`
- `GET /api/graph`
- `POST /api/edges`
- `DELETE /api/edges/{edge_id}`
- `POST /api/query`
- `GET /health`

## 检索与排序说明

系统查询流程分为四步：

1. 使用嵌入模型对用户问题向量化。
2. 在 LanceDB 中召回最相关的切块节点。
3. 以召回结果为种子构造局部子图，并执行个性化 PageRank。
4. 选取高分上下文交给大语言模型生成最终答案，同时返回引用与高亮路径。

手工创建的 `manual` 边会直接参与第 3 步的排序计算，因此能够显式影响知识点之间的关联强度。

## 实体抽取说明

实体关系抽取流程分为两层：

1. `OpenAiService` 使用 Responses API 的结构化输出模式生成标准 JSON。
2. `EntityExtractionService` 将长文档按窗口分批抽取，再按实体名和关系键去重聚合。

图谱落边阶段会再次执行实体命中校验，避免短实体名称误匹配到无关单词内部。
