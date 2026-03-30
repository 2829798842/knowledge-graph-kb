import {
  get_input_mode_label,
  get_knowledge_type_label,
  get_strategy_label,
  NODE_TYPE_LABELS,
  PREDICATE_SUGGESTIONS,
} from '../../shared/config/ui_constants';
import type {
  GraphEdgeDetailRecord,
  GraphNodeDetailRecord,
  GraphViewportMode,
  KnowledgeGraphRecord,
  SourceRecord,
} from '../../shared/types/knowledge_base_types';

export type ViewportCommandType = GraphViewportMode | 'zoom-in' | 'zoom-out';

export interface ViewportCommand {
  id: number;
  type: ViewportCommandType;
}

export interface NodeActionCopyRecord {
  rename_allowed: boolean;
  delete_allowed: boolean;
  relation_allowed: boolean;
  delete_label: string;
  delete_message: string;
}

export interface EdgeActionCopyRecord {
  delete_allowed: boolean;
  delete_message: string;
  copy_allowed: boolean;
}

export const DENSITY_PRESETS = [28, 52, 76];
export const DEFAULT_PREDICATE = PREDICATE_SUGGESTIONS[0] ?? '提及';

function merge_node_metadata(metadata: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!metadata) {
    return {};
  }
  const nested =
    metadata.metadata && typeof metadata.metadata === 'object' && !Array.isArray(metadata.metadata)
      ? (metadata.metadata as Record<string, unknown>)
      : {};
  return { ...metadata, ...nested };
}

export function format_metadata_value(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => format_metadata_value(item)).filter(Boolean).join(', ');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return '';
}

export function node_option_label(node_id: string, graph: KnowledgeGraphRecord): string {
  const node = graph.nodes.find((current_node) => current_node.id === node_id);
  if (!node) {
    return node_id;
  }
  return `${NODE_TYPE_LABELS[node.type] ?? node.type} · ${node.label}`;
}

export function collect_node_import_rows(node_type: string, metadata: Record<string, unknown> | undefined): [string, string][] {
  const merged = merge_node_metadata(metadata);
  const rows: [string, string][] = [];
  const file_type = format_metadata_value(merged.source_file_type || merged.file_type);
  const file_name = format_metadata_value(merged.name);
  const source_kind = format_metadata_value(merged.source_kind);
  const input_mode = format_metadata_value(merged.input_mode);
  const strategy = format_metadata_value(
    merged.detected_strategy || merged.strategy || merged.source_strategy || merged.import_strategy,
  );

  if (file_type) {
    rows.push(['文件类型', file_type]);
  }
  if (file_name) {
    rows.push(['文件名称', file_name]);
  }
  if (strategy) {
    rows.push(['导入策略', get_strategy_label(strategy)]);
  }
  if (source_kind) {
    rows.push(['来源类型', get_input_mode_label(source_kind)]);
  }
  if (input_mode) {
    rows.push(['导入方式', get_input_mode_label(input_mode)]);
  }

  if (node_type === 'paragraph') {
    const knowledge_type = format_metadata_value(merged.knowledge_type);
    const worksheet_name = format_metadata_value(merged.worksheet_name);
    const is_spreadsheet = format_metadata_value(merged.is_spreadsheet).toLowerCase() === 'true';

    if (is_spreadsheet) {
      rows.push(['表格来源', '是']);
    }
    if (knowledge_type) {
      rows.push(['知识类型', get_knowledge_type_label(knowledge_type)]);
    }
    if (worksheet_name) {
      rows.push(['工作表', worksheet_name]);
    }
  }

  if (node_type === 'source' || node_type === 'workbook') {
    const spreadsheet_sheets = Array.isArray(merged.spreadsheet_sheets)
      ? merged.spreadsheet_sheets.map((sheet) => format_metadata_value(sheet)).filter(Boolean)
      : [];

    if (spreadsheet_sheets.length > 0) {
      rows.push(['工作表列表', spreadsheet_sheets.join(', ')]);
    }
  }

  const source_id = format_metadata_value(merged.source_id);
  if (source_id) {
    rows.push(['来源 ID', source_id]);
  }

  return rows;
}

export function collect_edge_import_rows(metadata: Record<string, unknown> | undefined): [string, string][] {
  const rows: [string, string][] = [];
  if (!metadata) {
    return rows;
  }

  const source_id = format_metadata_value(metadata.source_id);
  if (source_id) {
    rows.push(['来源 ID', source_id]);
  }

  const paragraph_id = format_metadata_value(metadata.paragraph_id);
  if (paragraph_id) {
    rows.push(['段落 ID', paragraph_id]);
  }

  const relation_source = format_metadata_value((metadata.metadata as Record<string, unknown> | undefined)?.relation_source);
  if (relation_source) {
    rows.push(['关系来源', relation_source]);
  }

  return rows;
}

export function selected_source_summary(selected_source_ids: string[], sources: SourceRecord[]): string {
  if (!selected_source_ids.length) {
    return '全部来源';
  }

  const selected_names = sources
    .filter((source) => selected_source_ids.includes(source.id))
    .map((source) => source.name);

  if (!selected_names.length) {
    return '已选来源';
  }

  if (selected_names.length <= 3) {
    return selected_names.join('、');
  }

  return `${selected_names.slice(0, 3).join('、')} 等 ${selected_names.length} 个来源`;
}

export function node_action_copy(node_detail: GraphNodeDetailRecord): NodeActionCopyRecord {
  const node_type = node_detail.node.type;

  if (node_type === 'source' || node_type === 'workbook') {
    return {
      rename_allowed: true,
      delete_allowed: true,
      relation_allowed: false,
      delete_label: '删除来源',
      delete_message: `确认删除来源“${node_detail.node.label}”吗？这会同步清理相关段落、关系和向量索引。`,
    };
  }

  if (node_type === 'entity') {
    return {
      rename_allowed: true,
      delete_allowed: true,
      relation_allowed: true,
      delete_label: '删除实体',
      delete_message: `确认删除实体“${node_detail.node.label}”吗？相关关系也会同步清理。`,
    };
  }

  if (node_type === 'paragraph') {
    return {
      rename_allowed: false,
      delete_allowed: true,
      relation_allowed: false,
      delete_label: '删除段落',
      delete_message: '确认删除当前段落吗？相关关系和向量索引也会一起清理。',
    };
  }

  return {
    rename_allowed: false,
    delete_allowed: false,
    relation_allowed: false,
    delete_label: '删除节点',
    delete_message: '',
  };
}

export function edge_action_copy(edge_detail: GraphEdgeDetailRecord): EdgeActionCopyRecord {
  if (edge_detail.edge.type === 'manual') {
    return {
      delete_allowed: true,
      delete_message: '确认删除这条手动关系吗？',
      copy_allowed: true,
    };
  }

  if (edge_detail.edge.type === 'relation') {
    return {
      delete_allowed: true,
      delete_message: '确认删除这条实体关系吗？',
      copy_allowed: true,
    };
  }

  return {
    delete_allowed: false,
    delete_message: '',
    copy_allowed: false,
  };
}

export function create_viewport_command(type: ViewportCommandType): ViewportCommand {
  return {
    id: Date.now() + Math.floor(Math.random() * 1000),
    type,
  };
}
