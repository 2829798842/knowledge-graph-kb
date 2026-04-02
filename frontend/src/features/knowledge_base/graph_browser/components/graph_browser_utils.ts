import type {
  GraphEdgeDetailRecord,
  GraphNodeDetailRecord,
  KnowledgeGraphNodeRecord,
  KnowledgeGraphRecord,
  SourceRecord,
} from '../../shared/types/knowledge_base_types';

export const DEFAULT_PREDICATE = '提及';
export const DENSITY_PRESETS = [48, 72, 96] as const;

let viewport_command_id = 0;

export interface ViewportCommand {
  id: number;
  type: 'fit-all' | 'focus-selection' | 'zoom-in' | 'zoom-out' | 'relayout';
}

export interface GraphSearchCandidateRecord {
  id: string;
  label: string;
  kind_label: string;
  description: string;
}

type SourceLike = Pick<SourceRecord, 'id' | 'name'> &
  Partial<Pick<SourceRecord, 'summary' | 'source_kind'>>;

export const GRAPH_LAYER_LABELS = {
  semantic: '语义层',
  evidence: '证据层',
  structure: '结构层',
} as const;

function read_text(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function read_string_list(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => read_text(item)).filter((item): item is string => Boolean(item));
}

function short_source_id(source_id: string): string {
  return source_id.slice(0, 8);
}

function build_source_name_count_map(sources: SourceLike[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const source of sources) {
    counts.set(source.name, (counts.get(source.name) ?? 0) + 1);
  }
  return counts;
}

export function format_metadata_value(value: unknown): string | null {
  if (Array.isArray(value)) {
    const items = read_string_list(value);
    return items.length ? items.join('、') : null;
  }
  return read_text(value);
}

export function create_viewport_command(type: ViewportCommand['type']): ViewportCommand {
  viewport_command_id += 1;
  return {
    id: viewport_command_id,
    type,
  };
}

export function format_source_display_name(source: SourceLike, sources: SourceLike[]): string {
  const counts = build_source_name_count_map(sources);
  if ((counts.get(source.name) ?? 0) <= 1) {
    return source.name;
  }
  return `${source.name} · ${short_source_id(source.id)}`;
}

export function compact_selected_source_summary(
  selected_source_ids: string[],
  sources: SourceLike[],
  max_count = 2,
): string {
  if (!selected_source_ids.length) {
    return '全部来源';
  }

  const selected_id_set = new Set(selected_source_ids);
  const selected_sources = sources.filter((source) => selected_id_set.has(source.id));
  if (!selected_sources.length) {
    return '已选来源';
  }

  const labels = selected_sources.map((source) => format_source_display_name(source, sources));
  if (labels.length <= max_count) {
    return labels.join('、');
  }

  return `${labels.slice(0, max_count).join('、')} 等 ${labels.length} 个来源`;
}

export function selected_source_summary(
  selected_source_ids: string[],
  sources: SourceLike[],
): string {
  if (!selected_source_ids.length) {
    return '当前范围：全部来源';
  }

  const selected_id_set = new Set(selected_source_ids);
  const selected_sources = sources.filter((source) => selected_id_set.has(source.id));
  if (!selected_sources.length) {
    return '当前范围：已选来源';
  }

  const labels = selected_sources.map((source) => format_source_display_name(source, sources));
  if (labels.length <= 2) {
    return `当前范围：${labels.join('、')}`;
  }
  return `当前范围：${labels.slice(0, 2).join('、')} 等 ${labels.length} 个来源`;
}

export function node_option_label(node_id: string, graph: KnowledgeGraphRecord): string {
  const node = graph.nodes.find((item) => item.id === node_id);
  if (!node) {
    return node_id;
  }
  const label = node.display_label ?? node.label;
  const kind = node.kind_label ?? node.type;
  return `${label}（${kind}）`;
}

export function create_search_candidate(node: KnowledgeGraphNodeRecord): GraphSearchCandidateRecord {
  const label = node.display_label ?? node.label;
  const kind_label = node.kind_label ?? node.type;
  const description_parts = [
    node.source_name,
    typeof node.evidence_count === 'number' ? `证据 ${node.evidence_count}` : null,
    typeof node.metadata?.relation_count === 'number' ? `关系 ${node.metadata.relation_count}` : null,
  ].filter(Boolean);

  return {
    id: node.id,
    label,
    kind_label,
    description: description_parts.join(' · ') || '语义主图中的可见实体',
  };
}

function metadata_row(label: string, value: unknown): [string, string] | null {
  const formatted = format_metadata_value(value);
  return formatted ? [label, formatted] : null;
}

export function collect_node_import_rows(
  node_type: string,
  metadata: Record<string, unknown>,
): [string, string][] {
  const rows = [
    metadata_row('文件类型', metadata.file_type),
    metadata_row('文件名称', metadata.file_name),
    metadata_row('导入策略', metadata.strategy),
    metadata_row('来源类型', metadata.source_kind),
    metadata_row('导入方式', metadata.input_mode),
    metadata_row('工作表', metadata.worksheet_name),
    metadata_row('表格来源', metadata.workbook_name),
    metadata_row('来源 ID', metadata.source_id),
    metadata_row('段落 ID', metadata.paragraph_id),
    node_type === 'paragraph' ? metadata_row('知识类型', metadata.knowledge_type) : null,
  ];
  return rows.filter((item): item is [string, string] => Boolean(item));
}

export function collect_edge_import_rows(metadata: Record<string, unknown>): [string, string][] {
  const rows = [
    metadata_row('关系来源', metadata.relation_source),
    metadata_row('来源类型', metadata.source_kind),
    metadata_row('来源 ID', metadata.source_id),
    metadata_row('段落 ID', metadata.paragraph_id),
    metadata_row('工作表', metadata.worksheet_name),
  ];
  return rows.filter((item): item is [string, string] => Boolean(item));
}

export function node_action_copy(detail: GraphNodeDetailRecord) {
  const { node } = detail;
  const rename_allowed = node.type === 'entity' || node.type === 'source' || node.type === 'workbook';
  const relation_allowed = node.type === 'entity';
  const delete_allowed = node.type !== 'worksheet' && node.type !== 'record';

  return {
    rename_allowed,
    relation_allowed,
    delete_allowed,
    delete_label: node.type === 'paragraph' ? '删除段落' : '删除节点',
    delete_message: `确认删除“${node.display_label ?? node.label}”吗？`,
  };
}

export function edge_action_copy(detail: GraphEdgeDetailRecord) {
  const { edge } = detail;
  const delete_allowed = !(
    (edge.is_structural ?? false) ||
    ['contains', 'contains_sheet', 'contains_record', 'mentions'].includes(edge.type)
  );

  return {
    copy_allowed: edge.type === 'relation' || edge.type === 'manual',
    delete_allowed,
    delete_message: `确认删除关系“${edge.display_label ?? edge.label}”吗？`,
  };
}
