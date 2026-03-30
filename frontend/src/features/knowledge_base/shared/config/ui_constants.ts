import type { ThemeMode } from '../../../../theme';
import type { GraphViewportMode, ImportMode, ModelProvider, QueryMode, WorkspaceTab } from '../types/knowledge_base_types';

type LabelMap = Record<string, string>;

export const WORKSPACE_TABS = [
  {
    id: 'chat',
    label: 'Chat',
    description: '围绕知识问答、文件导入、来源查看和模型设置的对话工作区。',
  },
  {
    id: 'graph',
    label: 'Knowledge Graph',
    description: '查看实体关系，编辑节点与边，并高亮关联内容。',
  },
] as const satisfies Array<{ id: WorkspaceTab; label: string; description: string }>;

export const WORKSPACE_LABELS: Record<WorkspaceTab, string> = {
  chat: 'Chat',
  graph: 'Knowledge Graph',
};

export const GRAPH_VIEWPORT_MODE_LABELS: Record<GraphViewportMode, string> = {
  'fit-all': '全图视角',
  'focus-selection': '聚焦选中',
};

export const MODEL_PROVIDER_OPTIONS: Array<{
  id: ModelProvider;
  label: string;
  description: string;
  base_url: string;
}> = [
  {
    id: 'openai',
    label: 'OpenAI',
    description: '官方接口，适合直接接入 OpenAI 服务。',
    base_url: 'https://api.openai.com/v1',
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    description: '统一接入多个模型提供商。',
    base_url: 'https://openrouter.ai/api/v1',
  },
  {
    id: 'siliconflow',
    label: 'SiliconFlow',
    description: '兼容 OpenAI 风格接口，适合国内链路。',
    base_url: 'https://api.siliconflow.cn/v1',
  },
  {
    id: 'custom',
    label: '自定义',
    description: '手动填写兼容 OpenAI 的接口地址。',
    base_url: '',
  },
];

export const MODEL_PROVIDER_BASE_URLS: Record<ModelProvider, string> = Object.fromEntries(
  MODEL_PROVIDER_OPTIONS.map((option) => [option.id, option.base_url]),
) as Record<ModelProvider, string>;

export const API_KEY_SOURCE_LABELS: LabelMap = {
  saved: '已保存',
  environment: '环境变量',
  request: '本次输入',
  none: '未配置',
};

export const QUERY_MODE_OPTIONS: Array<{
  id: QueryMode;
  label: string;
  description: string;
  examples: string[];
}> = [
  {
    id: 'answer',
    label: '问答',
    description: '直接提问，返回自然语言答案与来源引用。',
    examples: ['项目 Alpha 是什么？', '总结一下合规来源里的重点。'],
  },
  {
    id: 'record',
    label: '表格记录',
    description: '按关键词检索表格行记录。',
    examples: ['customer_id C001', '订单号 SO-1024', '华东 2026-03'],
  },
  {
    id: 'entity',
    label: '实体检索',
    description: '按名称或描述查找实体。',
    examples: ['项目 Alpha', '团队负责人', '主题 42'],
  },
  {
    id: 'relation',
    label: '关系检索',
    description: '检索实体之间的关系模式和上下文。',
    examples: ['依赖', '汇报给', '由谁负责'],
  },
  {
    id: 'source',
    label: '来源检索',
    description: '按来源名称、摘要或类型检索。',
    examples: ['年报', '风险提示', '合规制度'],
  },
];

export const QUERY_MODE_LABELS: Record<QueryMode, string> = Object.fromEntries(
  QUERY_MODE_OPTIONS.map((option) => [option.id, option.label]),
) as Record<QueryMode, string>;

export const NODE_TYPE_LABELS: Record<string, string> = {
  source: '来源',
  workbook: '工作簿',
  paragraph: '段落',
  worksheet: '工作表',
  record: '记录',
  entity: '实体',
};

export const PREDICATE_SUGGESTIONS: string[] = ['提及', '依赖', '支持', '引用', '归属', '影响'];

export const IMPORT_MODES: Array<{ id: ImportMode; label: string; description: string }> = [
  { id: 'upload', label: '上传文件', description: '上传一个或多个本地文件。' },
  { id: 'paste', label: '粘贴文本', description: '直接粘贴纯文本并创建来源。' },
  { id: 'scan', label: '扫描目录', description: '按目录与匹配模式批量扫描文件。' },
  { id: 'openie', label: 'OpenIE / JSON', description: '导入 OpenIE 结构化实体与关系 JSON。' },
  { id: 'convert', label: '转换结果', description: '导入外部转换后的结构化 JSON。' },
];

export const STRATEGY_OPTIONS: string[] = ['auto', 'narrative', 'factual', 'quote'];

export const STRATEGY_LABELS: LabelMap = {
  auto: '自动',
  narrative: '叙述型',
  factual: '事实型',
  quote: '引述型',
};

export const KNOWLEDGE_TYPE_LABELS: LabelMap = {
  mixed: '混合型',
  narrative: '叙述型',
  factual: '事实型',
  quote: '引述型',
};

export const THEME_MODE_OPTIONS: Array<{ id: ThemeMode; label: string }> = [
  { id: 'system', label: '跟随系统' },
  { id: 'light', label: '浅色' },
  { id: 'dark', label: '深色' },
];

export const TASK_STATUS_LABELS: LabelMap = {
  queued: '排队中',
  running: '进行中',
  failed: '失败',
  partial: '部分完成',
  completed: '已完成',
  cancelled: '已取消',
  aborted: '已中止',
  ready: '就绪',
  pending: '待处理',
};

export const SOURCE_STATUS_LABELS: LabelMap = {
  ready: '就绪',
  pending: '待处理',
  running: '处理中',
  failed: '失败',
};

export const INPUT_MODE_LABELS: LabelMap = {
  file: '文件',
  text: '文本',
  json: 'JSON',
  upload: '上传',
  paste: '粘贴',
  scan: '扫描',
  openie: 'OpenIE',
  convert: '转换',
};

export const IMPORT_STEP_LABELS: LabelMap = {
  queued: '等待执行',
  preparing: '准备中',
  splitting: '切分文本',
  indexing: '写入索引',
  embedding: '向量化',
  writing: '写入结果',
  extracting: '抽取实体',
  completed: '已完成',
  cancelled: '已取消',
  failed: '失败',
  aborted: '已中止',
  running: '进行中',
};

export const VECTOR_STATE_LABELS: LabelMap = {
  pending: '待向量化',
  ready: '已向量化',
  none: '未向量化',
};

export const SUPPORTED_UPLOAD_ACCEPT = '.txt,.pdf,.docx,.xlsx,.xlsm,.xls,.json';
export const SUPPORTED_UPLOAD_HINT =
  '支持 TXT、PDF、DOCX、XLSX、XLSM、XLS，以及可选的同名 *.schema.json 配置文件。';
export const EXCEL_IMPORT_HINT = 'Excel 会按表格来源导入，并可搭配同名 .schema.json 配置文件。';

export const TASK_STATUS_ORDER: Record<string, number> = {
  running: 0,
  queued: 1,
  failed: 2,
  partial: 3,
  completed: 4,
  cancelled: 5,
  aborted: 6,
};

export function get_strategy_label(value: string): string {
  return STRATEGY_LABELS[value] ?? value;
}

export function get_knowledge_type_label(value: string): string {
  return KNOWLEDGE_TYPE_LABELS[value] ?? STRATEGY_LABELS[value] ?? value;
}

export function get_status_label(value: string): string {
  return TASK_STATUS_LABELS[value] ?? SOURCE_STATUS_LABELS[value] ?? value;
}

export function get_input_mode_label(value: string): string {
  return INPUT_MODE_LABELS[value] ?? value;
}

export function get_step_label(value: string): string {
  return IMPORT_STEP_LABELS[value] ?? value;
}

export function get_vector_state_label(value: string): string {
  return VECTOR_STATE_LABELS[value] ?? value;
}

export function get_api_key_source_label(value: string): string {
  return API_KEY_SOURCE_LABELS[value] ?? value;
}
