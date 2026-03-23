# Knowledge Graph KB

Knowledge Graph KB 是一个本地优先的知识库项目，使用 FastAPI 提供后端服务，使用 React + Cytoscape.js 提供图谱工作台。系统支持导入文档、抽取实体关系、构建知识图谱、执行向量检索，并基于图谱重排结果生成问答答案。

## 当前能力

- 文档导入：支持 `.txt`、`.pdf`、`.docx`
- 图谱浏览：查看文档、切块、实体与关系
- 手工连边：在前端直接创建和删除显式关系
- FAISS 检索：使用本地 FAISS 索引做向量召回
- 图谱问答：结合向量检索和个性化 PageRank 返回答案与引用
- 模型配置页：前端可配置 API 供应商、Base URL、通用模型、嵌入模型
- 连接测试：保存前可直接测试当前模型配置是否可用
- 本地密钥加密：已保存的 API Key 会先加密再写入本地数据库

## 快速开始

### 1. 准备环境变量

复制 `.env.example` 为 `.env`，然后按需修改：

- `MODEL_PROVIDER`
- `MODEL_BASE_URL`
- `MODEL_CONFIG_SECRET_PATH`
- `OPENAI_API_KEY`
- `OPENAI_LLM_MODEL`
- `OPENAI_EMBED_MODEL`
- `DATABASE_URL`
- `VECTOR_STORE_DIR`
- `UPLOAD_DIR`
- `FRONTEND_DIST_DIR`
- `SERVER_HOST`
- `SERVER_PORT`

默认模型配置：

- 通用模型：`gpt-5.4-mini`
- 嵌入模型：`text-embedding-3-large`

### 2. 安装后端依赖

```bash
uv sync
```

### 3. 安装前端依赖并构建

```bash
cd frontend
pnpm install
pnpm build
```

### 4. 启动服务

```bash
uv run python main.py
```

默认地址：`http://localhost:8000`

## 开发命令

后端测试：

```bash
uv run pytest -q
```

前端测试：

```bash
cd frontend
pnpm test
```

前端构建：

```bash
cd frontend
pnpm build
```

## 模型配置说明

前端工作台内置模型配置面板，支持：

- 选择 API 供应商：`OpenAI`、`OpenRouter`、`SiliconFlow`、自定义兼容供应商
- 配置 `Base URL`
- 分别配置通用模型与嵌入模型
- 保存或清除本地密钥
- 先测试连接，再决定是否保存

注意：

- 已保存的 API Key 会使用本地密钥文件加密后再落库
- 如果切换了嵌入模型，现有 FAISS 索引会被清空，需要重新导入文档

## 项目结构

```text
knowledge-graph-kb/
|-- frontend/
|   |-- src/
|   |   |-- features/knowledge_base/
|   |   |-- styles/
|   |   `-- theme/
|   |-- package.json
|   `-- vite.config.ts
|-- src/
|   |-- api/                  # FastAPI 路由与依赖注入
|   |-- config/               # 应用配置与路径解析
|   |-- schemas/              # 请求/响应模型与抽取模型
|   |-- data/                 # SQLModel 数据模型与数据库接入
|   |-- services/             # 导入、检索、图谱、模型配置等服务
|   |-- utils/                # 通用工具与本地加密工具
|   |-- web/                  # 前端静态资源托管
|   `-- app_factory.py
|-- tests/
|-- main.py
|-- pyproject.toml
`-- pnpm-workspace.yaml
```

## 检索与问答流程

1. 导入文档并解析正文
2. 将正文切块并生成嵌入向量
3. 把向量写入 FAISS，把实体关系写入图数据库表
4. 问答时先做向量召回
5. 再对图谱子图执行个性化 PageRank 重排
6. 最后用通用模型基于上下文生成答案与引用
