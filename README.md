# 知识图谱知识库工作台

这是一个本地优先的知识库工作台项目，后端基于 FastAPI，前端基于 React，使用 SQLite 持久化业务数据，使用 FAISS 保存向量索引。项目支持文档导入、知识图谱浏览、问答检索、来源回溯，以及模型配置管理。

## 主要能力

- 导入 TXT、PDF、DOCX、XLSX、XLS、JSON 等数据源
- 将内容切分、向量化，并写入统一知识库
- 浏览实体、段落、来源和关系组成的知识图谱
- 执行问答、实体检索、关系检索、来源检索、表格记录检索
- 在前端保存模型配置，并对 API 连通性进行测试
- 使用本地密钥文件加密保存模型 API Key

## 当前架构

- 后端接口统一挂在 `/api/system/*` 和 `/api/kb/*`
- 运行时依赖装配入口位于 `src/knowledge_base/container.py`
- 知识库运行数据统一存放在 `data/kb/`
- 元数据、导入任务、图谱数据、来源数据、模型配置统一存放在 `data/kb/kb.sqlite3`
- 向量索引统一存放在 `data/kb/vector_index/`
- 已保存的模型 API Key 会先加密，再写入数据库
- 用于加解密 API Key 的本地密钥文件位于 `data/kb/secrets/model_config.key`

## 主要接口分组

- `/api/system/health`
- `/api/kb/config/model`
- `/api/kb/imports/*`
- `/api/kb/search/*`
- `/api/kb/graph/*`
- `/api/kb/sources/*`

## 技术栈

### 后端

- FastAPI
- SQLite
- FAISS
- OpenAI Python SDK
- Pydantic Settings

### 前端

- React 18
- Vite
- TypeScript
- TanStack Query
- Cytoscape.js

## 快速开始

### 1. 安装后端依赖

```bash
uv sync
```

### 2. 启动后端

```bash
uv run python main.py
```

默认地址：

```text
http://localhost:8000
```

### 3. 安装前端依赖

```bash
cd frontend
pnpm install
```

### 4. 前端开发或构建

开发模式：

```bash
cd frontend
pnpm dev
```

生产构建：

```bash
cd frontend
pnpm build
```

## 环境变量

项目实际读取的是根目录下的 `.env` 文件，`.env.example` 仅作为示例模板。

当前核心配置项如下：

- `KB_DATA_DIR`：知识库运行数据根目录
- `KB_DATABASE_NAME`：SQLite 数据库文件名
- `KB_VECTOR_INDEX_DIR_NAME`：向量索引目录名
- `KB_UPLOAD_DIR_NAME`：上传文件目录名
- `KB_SECRET_DIR_NAME`：本地密钥目录名
- `MODEL_CONFIG_SECRET_NAME`：模型配置加密密钥文件名
- `KB_SCAN_ROOTS`：允许扫描导入的根目录列表
- `FRONTEND_DIST_DIR`：前端构建产物目录
- `MODEL_PROVIDER`：默认模型提供商
- `MODEL_BASE_URL`：默认模型 Base URL
- `OPENAI_API_KEY`：默认 API Key
- `OPENAI_LLM_MODEL`：默认通用模型
- `OPENAI_EMBED_MODEL`：默认嵌入模型
- `SERVER_HOST`：服务监听地址
- `SERVER_PORT`：服务端口
- `LOG_LEVEL`：日志级别

## 数据与密钥存储

当前真实使用的存储结构如下：

```text
data/kb/
|-- kb.sqlite3                 # 主数据库
|-- vector_index/              # 向量索引目录
|-- uploads/                   # 导入文件目录
`-- secrets/
    `-- model_config.key       # API Key 加解密密钥文件
```

模型 API Key 的优先级如下：

1. 如果前端“模型配置”里保存了 API Key，则优先使用数据库中的已保存配置
2. 否则回退到 `.env` 中的 `OPENAI_API_KEY`

## 验证命令

### 后端测试

```bash
uv run pytest -q
```

### 前端测试

```bash
cd frontend
pnpm test
```

### 前端构建检查

```bash
cd frontend
pnpm build
```

## 目录结构

```text
knowledge-graph-kb/
|-- frontend/
|   `-- src/features/knowledge_base/
|-- src/
|   |-- api/                   # HTTP 路由、依赖注入、请求响应模型
|   |-- config/                # 环境变量与路径解析
|   |-- knowledge_base/
|   |   |-- container.py       # 运行时依赖装配入口
|   |   |-- application/       # 应用服务层
|   |   |-- domain/            # 领域模型与公共定义
|   |   |-- importing/         # 导入、解析、投影、规范化逻辑
|   |   `-- infrastructure/    # SQLite、FAISS、模型网关实现
|   |-- utils/                 # 通用工具
|   `-- web/                   # 前端静态资源托管
|-- tests/
|-- data/kb/
|-- .env.example
|-- main.py
`-- pyproject.toml
```
