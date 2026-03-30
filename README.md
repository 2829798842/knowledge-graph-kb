# 知识图谱知识库

一个本地优先、单实例的知识图谱 / 知识问答工作区。

后端基于 `FastAPI + SQLite + FAISS`，前端基于 `React`。系统支持把文本、文档、表格和结构化 JSON 导入到本地知识库中，再通过聊天问答、来源浏览和知识图谱完成检索、编辑与排障。

## 主要能力

- 导入 `txt`、`pdf`、`docx`、`xlsx`、`xlsm`、`xls`
- 支持上传、粘贴、目录扫描、OpenIE JSON、转换后 JSON 五类导入入口
- 支持聊天问答、来源展开、检索 trace 查看
- 支持知识图谱浏览、节点重命名、节点删除、边删除、手工实体创建、手工关系创建
- 支持统一模型配置读写与连通性测试
- 支持本地运维命令：`doctor`、`backup`、`restore`、`rebuild-vectors`、`rebuild-graph`

## 当前信息架构

- 前端主界面只保留两个核心页面：
  - `Chat`
  - `Knowledge Graph`
- `Chat` 页面负责问答、上传、来源查看、模型设置
- `Knowledge Graph` 页面负责图谱浏览、编辑、删除、高亮和手工补边

## 目录结构

```text
src/
├─ api/                    # HTTP 路由、依赖注入、统一错误响应、Pydantic schema
├─ config/                 # 运行时配置与路径解析
├─ kb/
│  ├─ application/         # 应用服务、检索、搜索、导入流水线
│  ├─ database/            # SQLite 网关与轻量 schema version
│  ├─ importing/           # 文档解析、切块、Excel 结构映射
│  ├─ providers/           # OpenAI 兼容模型网关
│  ├─ storage/             # SQLite 仓储与 FAISS 向量索引
│  └─ container.py         # 知识库运行时容器
├─ utils/                  # 日志、文件工具、密钥工具
└─ web/                    # 前端静态资源托管

frontend/
└─ src/
   └─ features/knowledge_base/
      ├─ query_studio/     # Chat 页面
      ├─ graph_browser/    # Knowledge Graph 页面
      ├─ model_config/     # 模型配置弹窗
      └─ shared/           # API、hooks、store、共享组件
```

## API 分组

- `/api/system/*`
  - 健康检查与 readiness
- `/api/kb/config/model`
  - 模型配置读取、更新、测试
- `/api/kb/imports/*`
  - 导入任务提交、查询、取消、重试
- `/api/kb/chat/*`
  - 会话与消息
- `/api/kb/search/*`
  - 记录、实体、关系、来源检索
- `/api/kb/graph/*`
  - 图谱浏览、节点创建、节点更新、边删除、手工关系
- `/api/kb/sources/*`
  - 来源列表、详情、更新、删除、段落

## 本地运行

### 后端

```bash
uv sync --all-extras
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

## CLI 运维命令

```bash
uv run python main.py doctor
uv run python main.py backup --output-dir ./data/backups/manual
uv run python main.py restore ./data/backups/manual --force
uv run python main.py rebuild-vectors
uv run python main.py rebuild-graph
```

说明：

- `doctor` 会检查数据库、向量索引、模型配置、前端构建产物和图谱完整性
- `backup` 会备份 SQLite、向量索引、上传文件和密钥目录
- `restore` 会把备份恢复到当前数据目录
- `rebuild-vectors` 会从已存段落重建向量索引
- `rebuild-graph` 会修复悬挂关系、刷新引用计数并清理可修复脏数据

## 质量门

后端：

```bash
uv run python -m compileall main.py src
uv run pytest -q
```

前端：

```bash
cd frontend
pnpm build
pnpm test -- --run
```

## 测试覆盖

当前仓库已包含最小回归测试，覆盖：

- `/api/system/health`
- `/api/system/ready`
- 导入任务提交与诊断字段
- 来源更新
- 手工实体创建
- 图谱读取
- 模型配置读取 / 更新 / 测试
- 聊天消息返回 citations / execution / retrieval trace
- 备份与恢复基础链路

## 已知说明

- `doctor` 如果报告 `graph_integrity` 有孤儿实体，说明历史数据里有可修复脏记录，可以在确认后执行 `rebuild-graph`
- 当前产品按本地优先单实例模式设计，不包含多租户与权限系统
- 前端保留最小双页工作区，不再提供旧的多入口导航
