import type { GraphViewMode } from '../../shared/types/knowledge_base_types';
import type { RenderEdge, RenderNode } from './graph_render_types';

interface GraphReadabilityContext {
  graph_view_mode: GraphViewMode;
  total_node_count: number;
  has_context: boolean;
  selected_node_id: string | null;
  selected_edge_id: string | null;
  selected_related_node_ids: Set<string>;
  highlighted_node_ids: Set<string>;
  highlighted_edge_ids: Set<string>;
  highlighted_edge_count: number;
  label_priority_node_ids: Set<string>;
}

function is_priority_node(node: RenderNode, context: GraphReadabilityContext): boolean {
  return context.label_priority_node_ids.has(node.id);
}

function is_emphasized_node(node: RenderNode, context: GraphReadabilityContext): boolean {
  return (
    node.id === context.selected_node_id ||
    context.highlighted_node_ids.has(node.id) ||
    context.selected_related_node_ids.has(node.id)
  );
}

export function should_show_node_label(
  node: RenderNode,
  context: GraphReadabilityContext,
): boolean {
  if (context.total_node_count <= 12) {
    return true;
  }
  if (context.graph_view_mode === 'local') {
    if (node.layer_mode !== 'semantic') {
      return is_emphasized_node(node, context);
    }
    return context.total_node_count <= 24 || is_emphasized_node(node, context) || is_priority_node(node, context);
  }
  if (is_emphasized_node(node, context)) {
    return true;
  }
  if (node.layer_mode !== 'semantic') {
    return false;
  }
  return !context.has_context && is_priority_node(node, context);
}

export function resolve_node_fill_alpha(
  node: RenderNode,
  context: GraphReadabilityContext,
): number {
  if (node.id === context.selected_node_id) {
    return 0.96;
  }
  if (context.highlighted_node_ids.has(node.id) || context.selected_related_node_ids.has(node.id)) {
    return 0.82;
  }
  if (context.graph_view_mode === 'local') {
    if (node.layer_mode !== 'semantic') {
      return context.has_context ? 0.08 : 0.16;
    }
    return context.has_context ? 0.24 : 0.52;
  }
  if (node.layer_mode !== 'semantic') {
    return context.has_context ? 0.05 : 0.14;
  }
  if (context.has_context) {
    return 0.05;
  }
  return is_priority_node(node, context) ? 0.7 : 0.46;
}

export function resolve_node_halo_width(
  node: RenderNode,
  context: GraphReadabilityContext,
): number {
  if (node.id === context.selected_node_id) {
    return 3;
  }
  if (context.highlighted_node_ids.has(node.id) || context.selected_related_node_ids.has(node.id)) {
    return 2;
  }
  return 0;
}

export function resolve_node_radius(
  node: RenderNode,
  context: GraphReadabilityContext,
): number {
  if (node.id === context.selected_node_id) {
    return node.radius * 1.18;
  }
  if (context.highlighted_node_ids.has(node.id) || context.selected_related_node_ids.has(node.id)) {
    return node.radius * 1.08;
  }
  return node.radius;
}

export function resolve_node_label_alpha(
  node: RenderNode,
  context: GraphReadabilityContext,
): number {
  if (node.id === context.selected_node_id) {
    return 0.98;
  }
  if (context.highlighted_node_ids.has(node.id) || context.selected_related_node_ids.has(node.id)) {
    return 0.9;
  }
  if (context.graph_view_mode === 'local') {
    if (node.layer_mode !== 'semantic') {
      return 0;
    }
    return 0.72;
  }
  if (node.layer_mode !== 'semantic') {
    return 0;
  }
  if (context.has_context) {
    return 0.18;
  }
  return 0.84;
}

export function should_show_edge_label(
  edge: RenderEdge,
  context: GraphReadabilityContext,
): boolean {
  if (edge.id === context.selected_edge_id) {
    return true;
  }
  if (edge.layer_mode !== 'semantic') {
    return false;
  }
  if (context.graph_view_mode === 'local') {
    return context.highlighted_edge_ids.has(edge.id) && context.highlighted_edge_count <= 4;
  }
  return Boolean(
    context.selected_node_id &&
      context.highlighted_edge_ids.has(edge.id) &&
      context.highlighted_edge_count <= 4,
  );
}

export function resolve_edge_alpha(
  edge: RenderEdge,
  context: GraphReadabilityContext,
): number {
  if (edge.id === context.selected_edge_id) {
    return 0.98;
  }
  if (edge.layer_mode !== 'semantic') {
    if (context.highlighted_edge_ids.has(edge.id)) {
      return 0.2;
    }
    return context.has_context ? 0.04 : 0.07;
  }
  if (context.graph_view_mode === 'local') {
    if (context.highlighted_edge_ids.has(edge.id)) {
      return 0.68;
    }
    return context.has_context ? 0.24 : 0.3;
  }
  if (context.highlighted_edge_ids.has(edge.id)) {
    return 0.56;
  }
  if (context.has_context) {
    return edge.is_structural ? 0.05 : 0.2;
  }
  return edge.is_structural ? 0.08 : 0.32;
}

export function resolve_edge_width(
  edge: RenderEdge,
  context: GraphReadabilityContext,
): number {
  if (edge.id === context.selected_edge_id) {
    return 3.4;
  }
  if (context.highlighted_edge_ids.has(edge.id)) {
    return 2.6;
  }
  return edge.is_structural ? 1 : 1.8;
}

export function resolve_label_priority_node_ids(
  nodes: RenderNode[],
  edges: RenderEdge[],
): Set<string> {
  const degree_map = new Map<string, number>();
  for (const edge of edges) {
    if (edge.layer_mode !== 'semantic') {
      continue;
    }
    degree_map.set(edge.source, (degree_map.get(edge.source) ?? 0) + 1);
    degree_map.set(edge.target, (degree_map.get(edge.target) ?? 0) + 1);
  }

  const limit = nodes.length > 220 ? 4 : nodes.length > 80 ? 6 : 8;
  return new Set(
    nodes
      .filter((node) => node.layer_mode === 'semantic')
      .map((node) => ({
        id: node.id,
        evidence_count: node.evidence_count ?? 0,
        degree: degree_map.get(node.id) ?? 0,
        radius: node.radius,
        label: node.display_label,
      }))
      .filter((node) => node.evidence_count > 0 || node.degree > 0)
      .sort((left, right) => {
        if (right.evidence_count !== left.evidence_count) {
          return right.evidence_count - left.evidence_count;
        }
        if (right.degree !== left.degree) {
          return right.degree - left.degree;
        }
        if (right.radius !== left.radius) {
          return right.radius - left.radius;
        }
        return left.label.localeCompare(right.label, 'zh-CN');
      })
      .slice(0, limit)
      .map((node) => node.id),
  );
}
