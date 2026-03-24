/**
 * 模块名称：features/knowledge_base/utils/label_utils
 * 主要功能：提供前端界面使用的中文标签映射。
 */

const NODE_TYPE_LABELS: Record<string, string> = {
  document: '文档',
  chunk: '片段',
  entity: '实体',
};

const EDGE_TYPE_LABELS: Record<string, string> = {
  contains: '包含',
  semantic: '语义关联',
  mentions: '提及',
  manual: '手工连边',
};

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
};

const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  queued: '待抽取',
  processing: '抽取中',
  ready: '可查询',
  failed: '失败',
};

const JOB_STAGE_LABELS: Record<string, string> = {
  queued: '等待开始',
  parsing: '解析文档',
  chunking: '自然分段',
  embedding: '生成向量',
  extracting: 'LLM 抽取',
  graph: '更新图谱',
  completed: '处理完成',
  failed: '处理失败',
};

/**
 * 获取节点类型中文标签。
 *
 * @param node_type - 节点类型。
 * @returns 节点类型中文标签。
 */
export function get_node_type_label(node_type: string): string {
  return NODE_TYPE_LABELS[node_type] ?? node_type;
}

/**
 * 获取边类型中文标签。
 *
 * @param edge_type - 边类型。
 * @returns 边类型中文标签。
 */
export function get_edge_type_label(edge_type: string): string {
  return EDGE_TYPE_LABELS[edge_type] ?? edge_type;
}

/**
 * 获取任务状态中文标签。
 *
 * @param status - 任务状态。
 * @returns 任务状态中文标签。
 */
export function get_job_status_label(status: string): string {
  return JOB_STATUS_LABELS[status] ?? status;
}

/**
 * 获取文档状态中文标签。
 *
 * @param status - 文档状态。
 * @returns 文档状态中文标签。
 */
export function get_document_status_label(status: string): string {
  return DOCUMENT_STATUS_LABELS[status] ?? status;
}

/**
 * 获取任务阶段中文标签。
 *
 * @param stage - 任务阶段。
 * @returns 任务阶段中文标签。
 */
export function get_job_stage_label(stage: string): string {
  return JOB_STAGE_LABELS[stage] ?? stage;
}

/**
 * 获取文件类型中文说明。
 *
 * @param file_type - 文件类型后缀。
 * @returns 文件类型中文说明。
 */
export function get_file_type_label(file_type: string): string {
  const normalized_file_type: string = file_type.toLowerCase();
  if (normalized_file_type === 'txt') {
    return '文本文档';
  }
  if (normalized_file_type === 'pdf') {
    return 'PDF 文档';
  }
  if (normalized_file_type === 'docx') {
    return 'Word 文档';
  }
  return file_type.toUpperCase();
}
