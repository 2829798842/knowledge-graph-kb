import type { RenderEdge, RenderNode } from './graph_render_types';

export interface HoverCardState {
  x: number;
  y: number;
  title: string;
  subtitle: string;
  metadata_lines: string[];
}

function compact_position(x: number, y: number) {
  return {
    x: x + 12,
    y: y + 12,
  };
}

export function build_node_hover_card_at(node: RenderNode, x: number, y: number): HoverCardState {
  const position = compact_position(x, y);
  const metadata_lines = [
    node.source_name ? `来源：${node.source_name}` : null,
    typeof node.evidence_count === 'number' ? `证据：${node.evidence_count} 条` : null,
  ].filter((item): item is string => Boolean(item));

  return {
    ...position,
    title: node.display_label,
    subtitle: node.kind_label,
    metadata_lines,
  };
}

export function build_edge_hover_card_at(
  edge: RenderEdge,
  source_label: string,
  target_label: string,
  x: number,
  y: number,
): HoverCardState {
  const position = compact_position(x, y);
  const metadata_lines = [
    `${source_label} -> ${target_label}`,
    edge.source_name ? `来源：${edge.source_name}` : null,
  ].filter((item): item is string => Boolean(item));

  return {
    ...position,
    title: edge.display_label,
    subtitle: edge.relation_kind_label,
    metadata_lines,
  };
}
