import type {
  GraphViewMode,
  GraphViewportMode,
  ImportMode,
  ModelProvider,
  QueryMode,
  WorkspaceTab,
} from '../types/knowledge_base_types';

export const WORKSPACE_TABS: Array<{ id: WorkspaceTab; label: string; description: string }> = [
  {
    id: 'chat',
    label: '知识问答',
    description: '查看回答、来源和检索诊断。',
  },
  {
    id: 'graph',
    label: '知识图谱',
    description: '阅读语义主图，并从属性面板下钻证据。',
  },
];

export const WORKSPACE_LABELS: Record<WorkspaceTab, string> = {
  chat: '知识问答',
  graph: '知识图谱',
};

export const QUERY_MODE_OPTIONS: Array<{ id: QueryMode; label: string; description: string }> = [
  { id: 'answer', label: '问答', description: '基于知识库生成回答。' },
  { id: 'record', label: '记录', description: '检索表格记录和结构化条目。' },
  { id: 'entity', label: '实体', description: '检索知识图谱中的实体节点。' },
  { id: 'relation', label: '关系', description: '检索实体之间的关系。' },
  { id: 'source', label: '来源', description: '检索来源文件和来源摘要。' },
];

export const QUERY_MODE_LABELS: Record<QueryMode, string> = {
  answer: '问答',
  record: '记录检索',
  entity: '实体检索',
  relation: '关系检索',
  source: '来源检索',
};

export const GRAPH_VIEW_MODE_LABELS: Record<GraphViewMode, string> = {
  global: '全局图',
  local: '局部图',
};

export const GRAPH_VIEWPORT_MODE_LABELS: Record<GraphViewportMode, string> = {
  'fit-all': '适配全图',
  'focus-selection': '聚焦选中',
};

export const NODE_TYPE_LABELS: Record<string, string> = {
  entity: '实体',
  source: '来源',
  workbook: '工作簿',
  paragraph: '段落',
  worksheet: '工作表',
  record: '记录',
};

export const PREDICATE_SUGGESTIONS = ['提及', '属于', '位于', '依赖', '影响', '支持', '关联', '包含'];

export const MODEL_PROVIDER_OPTIONS: Array<{
  id: ModelProvider;
  label: string;
  description: string;
  base_url: string;
}> = [
  {
    id: 'openai',
    label: 'OpenAI',
    description: '直接连接 OpenAI 官方接口。',
    base_url: 'https://api.openai.com/v1',
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    description: '通过 OpenRouter 访问多模型路由。',
    base_url: 'https://openrouter.ai/api/v1',
  },
  {
    id: 'siliconflow',
    label: 'SiliconFlow',
    description: '通过 SiliconFlow 调用兼容接口。',
    base_url: 'https://api.siliconflow.cn/v1',
  },
  {
    id: 'custom',
    label: '自定义',
    description: '使用自定义兼容 OpenAI 的接口地址。',
    base_url: '',
  },
];

export const MODEL_PROVIDER_BASE_URLS: Record<ModelProvider, string> = {
  openai: 'https://api.openai.com/v1',
  openrouter: 'https://openrouter.ai/api/v1',
  siliconflow: 'https://api.siliconflow.cn/v1',
  custom: '',
};

export const TASK_STATUS_ORDER: Record<string, number> = {
  running: 0,
  queued: 1,
  ready: 2,
  partial: 3,
  failed: 4,
};

const IMPORT_MODE_LABELS: Record<string, string> = {
  upload: '上传文件',
  paste: '粘贴文本',
  scan: '扫描目录',
  openie: '开放抽取',
  convert: '格式转换',
  text: '文本',
  file: '文件',
};

const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '处理中',
  ready: '已完成',
  partial: '部分完成',
  failed: '失败',
  idle: '未开始',
};

const STRATEGY_LABELS: Record<string, string> = {
  factual: '事实抽取',
  summary: '摘要抽取',
  semantic: '语义抽取',
  hybrid: '混合策略',
  auto: '自动策略',
};

const VECTOR_STATE_LABELS: Record<string, string> = {
  pending: '待向量化',
  ready: '已向量化',
  failed: '向量化失败',
  missing: '缺少向量',
};

const API_KEY_SOURCE_LABELS: Record<string, string> = {
  none: '未配置',
  env: '环境变量',
  config: '配置文件',
  request: '当前表单',
};

function label_from_map(value: string, mapping: Record<string, string>, fallback: string): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return fallback;
  }
  return mapping[normalized] ?? value;
}

export function get_input_mode_label(value: string): string {
  return label_from_map(value, IMPORT_MODE_LABELS, '未知输入');
}

export function get_status_label(value: string): string {
  return label_from_map(value, STATUS_LABELS, '未知状态');
}

export function get_strategy_label(value: string): string {
  return label_from_map(value, STRATEGY_LABELS, '默认策略');
}

export function get_vector_state_label(value: string): string {
  return label_from_map(value, VECTOR_STATE_LABELS, '未知状态');
}

export function get_api_key_source_label(value: string): string {
  return label_from_map(value, API_KEY_SOURCE_LABELS, '未知来源');
}

export function get_workspace_label(value: WorkspaceTab): string {
  return WORKSPACE_LABELS[value];
}

export function get_query_mode_label(value: QueryMode): string {
  return QUERY_MODE_LABELS[value];
}

export function get_graph_view_mode_label(value: GraphViewMode): string {
  return GRAPH_VIEW_MODE_LABELS[value];
}

export function get_graph_viewport_mode_label(value: GraphViewportMode): string {
  return GRAPH_VIEWPORT_MODE_LABELS[value];
}

export function get_node_type_label(value: string): string {
  return NODE_TYPE_LABELS[value] ?? value;
}

export function get_import_mode_options(): Array<{ id: ImportMode; label: string }> {
  return [
    { id: 'upload', label: get_input_mode_label('upload') },
    { id: 'paste', label: get_input_mode_label('paste') },
    { id: 'scan', label: get_input_mode_label('scan') },
    { id: 'openie', label: get_input_mode_label('openie') },
    { id: 'convert', label: get_input_mode_label('convert') },
  ];
}
