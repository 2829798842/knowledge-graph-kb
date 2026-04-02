import { NODE_TYPE_LABELS } from '../../shared/config/ui_constants';
import type {
  GraphLayerMode,
  GraphViewMode,
  KnowledgeGraphEdgeRecord,
  KnowledgeGraphNodeRecord,
  KnowledgeGraphRecord,
  LocalGraphState,
} from '../../shared/types/knowledge_base_types';
import type {
  ProjectedGraphRecord,
  RenderEdge,
  RenderNode,
} from './graph_render_types';

const NODE_COLOR_MAP: Record<string, number> = {
  source: 0xd17d21,
  workbook: 0xa85710,
  paragraph: 0x1a8d80,
  worksheet: 0x5a8f29,
  record: 0x3f6bc4,
  entity: 0x2b6ea4,
};

const EDGE_COLOR_MAP: Record<string, number> = {
  contains: 0xc8a66c,
  contains_sheet: 0x9a6f2f,
  contains_record: 0x5f8b4c,
  mentions: 0x3c7ca6,
  relation: 0x268b71,
  manual: 0xce5378,
};

function truncate_label(value: string, max_length = 24): string {
  const compact = value.trim();
  if (compact.length <= max_length) {
    return compact;
  }
  return `${compact.slice(0, max_length - 3)}...`;
}

function resolve_node_layer(node: KnowledgeGraphNodeRecord): GraphLayerMode {
  if (node.type === 'entity') {
    return 'semantic';
  }
  if (node.type === 'worksheet' || node.type === 'record') {
    return 'structure';
  }
  return 'evidence';
}

function resolve_edge_layer(edge: KnowledgeGraphEdgeRecord): GraphLayerMode {
  if (edge.type === 'relation' || edge.type === 'manual') {
    return 'semantic';
  }
  if (edge.type === 'contains_sheet' || edge.type === 'contains_record') {
    return 'structure';
  }
  return 'evidence';
}

function is_structural_edge(edge: KnowledgeGraphEdgeRecord): boolean {
  return (
    edge.is_structural ??
    ['contains', 'contains_sheet', 'contains_record', 'mentions'].includes(edge.type)
  );
}

function is_semantic_edge(edge: RenderEdge): boolean {
  return edge.layer_mode === 'semantic';
}

function is_semantic_node(node: RenderNode): boolean {
  return node.layer_mode === 'semantic' && node.type === 'entity';
}

function normalize_source_name(node: KnowledgeGraphNodeRecord): string | null {
  if (node.source_name) {
    return node.source_name;
  }
  if (node.type === 'source' || node.type === 'workbook') {
    return node.display_label ?? node.label;
  }
  const metadata = node.metadata || {};
  const value = metadata.source_name ?? metadata.name ?? null;
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function resolve_evidence_count(node: KnowledgeGraphNodeRecord): number | null {
  if (typeof node.evidence_count === 'number') {
    return node.evidence_count;
  }
  const metadata = node.metadata || {};
  const appearance_count = metadata.appearance_count;
  return typeof appearance_count === 'number' ? appearance_count : null;
}

function resolve_node_radius(node: KnowledgeGraphNodeRecord): number {
  if (node.type === 'source' || node.type === 'workbook') {
    return 16;
  }
  if (node.type === 'worksheet') {
    return 12;
  }
  if (node.type === 'record' || node.type === 'paragraph') {
    return 9;
  }
  const base_size = typeof node.size === 'number' ? node.size : 8;
  return Math.max(9, Math.min(26, 8 + base_size * 1.15));
}

function to_render_node(node: KnowledgeGraphNodeRecord): RenderNode {
  const display_label = node.display_label?.trim() || node.label;
  const kind_label = node.kind_label?.trim() || NODE_TYPE_LABELS[node.type] || node.type;
  const source_name = normalize_source_name(node);
  const evidence_count = resolve_evidence_count(node);

  return {
    ...node,
    display_label,
    short_label: truncate_label(display_label, 16),
    kind_label,
    source_name,
    evidence_count,
    layer_mode: resolve_node_layer(node),
    is_structural: node.type === 'worksheet' || node.type === 'record',
    radius: resolve_node_radius(node),
    color: NODE_COLOR_MAP[node.type] ?? 0x6b7280,
    searchable_text: [display_label, kind_label, source_name ?? '', node.id].join(' ').toLowerCase(),
  };
}

function to_render_edge(edge: KnowledgeGraphEdgeRecord): RenderEdge {
  const display_label = edge.display_label?.trim() || edge.label;
  const relation_kind_label =
    edge.relation_kind_label?.trim() ||
    (is_structural_edge(edge) ? '结构关系' : edge.type === 'manual' ? '手工关系' : '抽取关系');

  return {
    ...edge,
    display_label,
    short_label: truncate_label(display_label, 18),
    relation_kind_label,
    source_name: edge.source_name ?? null,
    evidence_paragraph_id: edge.evidence_paragraph_id ?? null,
    layer_mode: resolve_edge_layer(edge),
    is_structural: is_structural_edge(edge),
    color: EDGE_COLOR_MAP[edge.type] ?? 0x9ca3af,
  };
}

function include_node_by_layers(
  node: RenderNode,
  active_layer_modes: Set<GraphLayerMode>,
  include_paragraphs: boolean,
): boolean {
  if (!active_layer_modes.has(node.layer_mode)) {
    return false;
  }
  if (node.type === 'paragraph' && !include_paragraphs) {
    return false;
  }
  return true;
}

function include_edge_by_layers(
  edge: RenderEdge,
  active_layer_modes: Set<GraphLayerMode>,
  include_paragraphs: boolean,
): boolean {
  if (!active_layer_modes.has(edge.layer_mode)) {
    return false;
  }
  if ((edge.type === 'contains' || edge.type === 'mentions') && !include_paragraphs) {
    return false;
  }
  return true;
}

interface ProjectGraphOptions {
  active_layer_modes: GraphLayerMode[];
  include_paragraphs: boolean;
  selected_node_id: string | null;
  selected_edge_id: string | null;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
  graph_view_mode: GraphViewMode;
  local_graph_state: LocalGraphState;
}

function build_local_scope(
  nodes: RenderNode[],
  edges: RenderEdge[],
  local_graph_state: LocalGraphState,
): { node_ids: Set<string>; edge_ids: Set<string> } | null {
  const anchor_node_id = local_graph_state.anchor_node_id;
  if (!anchor_node_id) {
    return null;
  }

  const node_map = new Map(nodes.map((node) => [node.id, node]));
  const anchor_node = node_map.get(anchor_node_id) ?? null;
  if (!anchor_node || !is_semantic_node(anchor_node)) {
    return null;
  }

  const semantic_node_ids = new Set<string>([anchor_node_id]);
  const semantic_edge_ids = new Set<string>();

  for (const edge of edges) {
    if (!is_semantic_edge(edge)) {
      continue;
    }
    if (edge.source === anchor_node_id || edge.target === anchor_node_id) {
      semantic_edge_ids.add(edge.id);
      semantic_node_ids.add(edge.source);
      semantic_node_ids.add(edge.target);
    }
  }

  const scoped_node_ids = new Set<string>(semantic_node_ids);
  const scoped_edge_ids = new Set<string>(semantic_edge_ids);

  for (const edge of edges) {
    if (is_semantic_edge(edge)) {
      continue;
    }
    if (semantic_node_ids.has(edge.source) || semantic_node_ids.has(edge.target)) {
      scoped_node_ids.add(edge.source);
      scoped_node_ids.add(edge.target);
      scoped_edge_ids.add(edge.id);
    }
  }

  for (const edge of edges) {
    if (scoped_edge_ids.has(edge.id)) {
      continue;
    }
    if (scoped_node_ids.has(edge.source) && scoped_node_ids.has(edge.target)) {
      scoped_edge_ids.add(edge.id);
    }
  }

  return { node_ids: scoped_node_ids, edge_ids: scoped_edge_ids };
}

export function project_graph(
  graph: KnowledgeGraphRecord,
  options: ProjectGraphOptions,
): ProjectedGraphRecord {
  const active_layer_modes = new Set(options.active_layer_modes);
  const render_nodes = graph.nodes.map(to_render_node);
  const render_edges = graph.edges.map(to_render_edge);
  const render_node_map = new Map(render_nodes.map((node) => [node.id, node]));
  const render_edge_map = new Map(render_edges.map((edge) => [edge.id, edge]));

  const visible_node_ids = new Set(
    render_nodes
      .filter((node) => include_node_by_layers(node, active_layer_modes, options.include_paragraphs))
      .map((node) => node.id),
  );

  const visible_edge_ids = new Set(
    render_edges
      .filter((edge) => include_edge_by_layers(edge, active_layer_modes, options.include_paragraphs))
      .filter((edge) => visible_node_ids.has(edge.source) && visible_node_ids.has(edge.target))
      .map((edge) => edge.id),
  );

  const pinned_node_ids = new Set(
    [options.selected_node_id, ...options.highlighted_node_ids].filter(Boolean) as string[],
  );
  const pinned_edge_ids = new Set(
    [options.selected_edge_id, ...options.highlighted_edge_ids].filter(Boolean) as string[],
  );

  function include_visible_context(node_id: string): void {
    for (const edge of render_edges) {
      if (!visible_edge_ids.has(edge.id)) {
        continue;
      }
      if (edge.source !== node_id && edge.target !== node_id) {
        continue;
      }
      visible_node_ids.add(edge.source);
      visible_node_ids.add(edge.target);
    }
  }

  for (const node_id of pinned_node_ids) {
    if (visible_node_ids.has(node_id)) {
      include_visible_context(node_id);
      continue;
    }

    const pinned_node = render_node_map.get(node_id);
    if (!pinned_node) {
      continue;
    }

    visible_node_ids.add(node_id);
    for (const edge of render_edges) {
      if (edge.source !== node_id && edge.target !== node_id) {
        continue;
      }
      visible_edge_ids.add(edge.id);
      visible_node_ids.add(edge.source);
      visible_node_ids.add(edge.target);
    }
  }

  for (const edge_id of pinned_edge_ids) {
    const edge = render_edge_map.get(edge_id);
    if (!edge) {
      continue;
    }
    visible_edge_ids.add(edge_id);
    visible_node_ids.add(edge.source);
    visible_node_ids.add(edge.target);
  }

  let projected_edges = render_edges.filter(
    (edge) =>
      visible_edge_ids.has(edge.id) &&
      visible_node_ids.has(edge.source) &&
      visible_node_ids.has(edge.target),
  );

  let projected_nodes = render_nodes.filter((node) => visible_node_ids.has(node.id));

  if (options.graph_view_mode === 'local') {
    const local_scope = build_local_scope(projected_nodes, projected_edges, options.local_graph_state);
    if (local_scope) {
      projected_nodes = projected_nodes.filter((node) => local_scope.node_ids.has(node.id));
      projected_edges = projected_edges.filter(
        (edge) =>
          local_scope.edge_ids.has(edge.id) &&
          local_scope.node_ids.has(edge.source) &&
          local_scope.node_ids.has(edge.target),
      );
    }
  }

  return {
    nodes: projected_nodes,
    edges: projected_edges,
  };
}
