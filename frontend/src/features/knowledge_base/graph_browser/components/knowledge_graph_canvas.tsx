import { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape, { type Core, type ElementDefinition, type EventObject } from 'cytoscape';

import type { ResolvedTheme } from '../../../../theme';
import { get_input_mode_label, get_strategy_label } from '../../shared/config/ui_constants';
import type { GraphViewportMode, KnowledgeGraphEdgeRecord, KnowledgeGraphNodeRecord } from '../../shared/types/knowledge_base_types';
import type { ViewportCommand } from './graph_browser_utils';

interface KnowledgeGraphCanvasProps {
  nodes: KnowledgeGraphNodeRecord[];
  edges: KnowledgeGraphEdgeRecord[];
  layout_revision: number;
  viewport_mode: GraphViewportMode;
  viewport_command: ViewportCommand | null;
  selected_node_id: string | null;
  selected_edge_id: string | null;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
  resolved_theme: ResolvedTheme;
  on_select_node: (node_id: string) => void;
  on_select_edge: (edge_id: string) => void;
  on_clear_selection: () => void;
}

interface LayoutPoint {
  x: number;
  y: number;
}

interface HoverCardState {
  title: string;
  subtitle: string;
  metadata_lines: string[];
  x: number;
  y: number;
}

interface FocusState {
  selected_node_id: string | null;
  selected_edge_id: string | null;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
}

const layout_cache: Map<string, LayoutPoint> = new Map();

const NODE_COLOR_MAP: Record<string, string> = {
  source: '#d17d21',
  workbook: '#a85710',
  paragraph: '#1a8d80',
  worksheet: '#5a8f29',
  record: '#3f6bc4',
  entity: '#2b6ea4',
};

const EDGE_COLOR_MAP: Record<string, string> = {
  contains: '#c8a66c',
  contains_sheet: '#9a6f2f',
  contains_record: '#5f8b4c',
  mentions: '#3c7ca6',
  relation: '#268b71',
  manual: '#ce5378',
};

const NODE_SIZE_MAP: Record<string, number> = {
  source: 52,
  workbook: 58,
  paragraph: 18,
  worksheet: 36,
  record: 24,
  entity: 30,
};

function clamp(value: number, min_value: number, max_value: number): number {
  return Math.min(max_value, Math.max(min_value, value));
}

function hash_string(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0);
}

function polar_point(index: number, total: number, radius: number, angle_offset = 0): LayoutPoint {
  if (total <= 1) {
    return { x: 0, y: 0 };
  }
  const angle = angle_offset + (Math.PI * 2 * index) / total;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function resolve_layout_scale(node_count: number): number {
  if (node_count > 420) {
    return 34;
  }
  if (node_count > 320) {
    return 40;
  }
  if (node_count > 260) {
    return 46;
  }
  if (node_count > 200) {
    return 54;
  }
  if (node_count > 140) {
    return 68;
  }
  if (node_count > 80) {
    return 82;
  }
  return 96;
}

function build_layout(nodes: KnowledgeGraphNodeRecord[], edges: KnowledgeGraphEdgeRecord[]): Map<string, LayoutPoint> {
  const positions: Map<string, LayoutPoint> = new Map();
  const source_nodes = nodes.filter((node) => node.type === 'source' || node.type === 'workbook');
  const paragraph_nodes = nodes.filter((node) => node.type === 'paragraph');
  const entity_nodes = nodes.filter((node) => node.type !== 'source' && node.type !== 'workbook' && node.type !== 'paragraph');
  const source_ring_radius = nodes.length > 220 ? 2.1 : nodes.length > 140 ? 2.6 : 3.2;
  const paragraph_ring_radius = nodes.length > 220 ? 0.9 : 1.3;
  const entity_ring_radius = nodes.length > 220 ? 4.2 : nodes.length > 140 ? 5.2 : 6.2;
  const neighbor_map: Map<string, Set<string>> = new Map(nodes.map((node) => [node.id, new Set<string>()]));

  edges.forEach((edge) => {
    neighbor_map.get(edge.source)?.add(edge.target);
    neighbor_map.get(edge.target)?.add(edge.source);
  });

  source_nodes.forEach((node, index) => {
    positions.set(node.id, layout_cache.get(node.id) ?? polar_point(index, source_nodes.length, source_ring_radius, 0.18));
  });

  const paragraphs_by_source: Map<string, KnowledgeGraphNodeRecord[]> = new Map();
  paragraph_nodes.forEach((node) => {
    const source_id = String(node.metadata.source_id ?? '');
    const bucket_key = source_id ? `source:${source_id}` : '__orphan__';
    const bucket = paragraphs_by_source.get(bucket_key) ?? [];
    bucket.push(node);
    paragraphs_by_source.set(bucket_key, bucket);
  });

  paragraphs_by_source.forEach((paragraphs, source_node_id) => {
    const anchor = positions.get(source_node_id) ?? { x: 0, y: 0 };
    paragraphs.forEach((paragraph, index) => {
      const point = layout_cache.get(paragraph.id) ?? {
        x: anchor.x + Math.cos((Math.PI * 2 * index) / Math.max(paragraphs.length, 1)) * paragraph_ring_radius,
        y: anchor.y + Math.sin((Math.PI * 2 * index) / Math.max(paragraphs.length, 1)) * paragraph_ring_radius,
      };
      positions.set(paragraph.id, point);
    });
  });

  entity_nodes.forEach((node, index) => {
    const cached_point = layout_cache.get(node.id);
    if (cached_point) {
      positions.set(node.id, cached_point);
      return;
    }

    const neighbor_points = [...(neighbor_map.get(node.id) ?? [])]
      .map((node_id) => positions.get(node_id))
      .filter((point): point is LayoutPoint => Boolean(point));

    if (neighbor_points.length) {
      const average_x = neighbor_points.reduce((sum, point) => sum + point.x, 0) / neighbor_points.length;
      const average_y = neighbor_points.reduce((sum, point) => sum + point.y, 0) / neighbor_points.length;
      const seed_angle = (hash_string(node.id) % 360) * (Math.PI / 180);
      positions.set(node.id, {
        x: average_x + Math.cos(seed_angle) * 2.1,
        y: average_y + Math.sin(seed_angle) * 2.1,
      });
      return;
    }

    positions.set(node.id, polar_point(index, entity_nodes.length, entity_ring_radius, 0.4));
  });

  const iteration_count = nodes.length > 220 ? 12 : nodes.length > 160 ? 18 : nodes.length > 100 ? 24 : 30;
  for (let iteration = 0; iteration < iteration_count; iteration += 1) {
    const forces: Map<string, LayoutPoint> = new Map(nodes.map((node) => [node.id, { x: 0, y: 0 }]));

    for (let left_index = 0; left_index < nodes.length; left_index += 1) {
      for (let right_index = left_index + 1; right_index < nodes.length; right_index += 1) {
        const left_node = nodes[left_index];
        const right_node = nodes[right_index];
        const left_position = positions.get(left_node.id) ?? { x: 0, y: 0 };
        const right_position = positions.get(right_node.id) ?? { x: 0, y: 0 };
        const delta_x = right_position.x - left_position.x;
        const delta_y = right_position.y - left_position.y;
        const distance_squared = Math.max(delta_x * delta_x + delta_y * delta_y, 0.08);
        const distance = Math.sqrt(distance_squared);
        const repulsion_strength = 0.11 / distance_squared;
        const force_x = (delta_x / distance) * repulsion_strength;
        const force_y = (delta_y / distance) * repulsion_strength;
        forces.get(left_node.id)!.x -= force_x;
        forces.get(left_node.id)!.y -= force_y;
        forces.get(right_node.id)!.x += force_x;
        forces.get(right_node.id)!.y += force_y;
      }
    }

    edges.forEach((edge) => {
      const source_position = positions.get(edge.source) ?? { x: 0, y: 0 };
      const target_position = positions.get(edge.target) ?? { x: 0, y: 0 };
      const source_force = forces.get(edge.source);
      const target_force = forces.get(edge.target);

      if (!source_force || !target_force) {
        return;
      }

      const delta_x = target_position.x - source_position.x;
      const delta_y = target_position.y - source_position.y;
      const distance = Math.max(Math.sqrt(delta_x * delta_x + delta_y * delta_y), 0.001);
      const ideal_distance =
        edge.type === 'contains'
          ? 1.7
          : edge.type === 'contains_sheet'
            ? 1.9
            : edge.type === 'contains_record'
              ? 2.2
              : edge.type === 'mentions'
                ? 2.3
                : edge.type === 'manual'
                  ? 2.8
                  : 3.2;
      const attraction_strength = (distance - ideal_distance) * 0.03;
      const force_x = (delta_x / distance) * attraction_strength;
      const force_y = (delta_y / distance) * attraction_strength;
      source_force.x += force_x;
      source_force.y += force_y;
      target_force.x -= force_x;
      target_force.y -= force_y;
    });

    nodes.forEach((node) => {
      const position = positions.get(node.id) ?? { x: 0, y: 0 };
      const mobility =
        node.type === 'source' || node.type === 'workbook'
          ? 0.04
          : node.type === 'paragraph'
            ? 0.22
            : node.type === 'worksheet'
              ? 0.16
              : node.type === 'record'
                ? 0.36
                : 0.48;
      positions.set(node.id, {
        x: position.x + clamp(forces.get(node.id)!.x * mobility, -0.24, 0.24),
        y: position.y + clamp(forces.get(node.id)!.y * mobility, -0.24, 0.24),
      });
    });
  }

  const centered_positions = recenter_layout(positions);
  centered_positions.forEach((point, node_id) => layout_cache.set(node_id, point));
  return centered_positions;
}

function recenter_layout(positions: Map<string, LayoutPoint>): Map<string, LayoutPoint> {
  if (!positions.size) {
    return positions;
  }

  let min_x = Number.POSITIVE_INFINITY;
  let max_x = Number.NEGATIVE_INFINITY;
  let min_y = Number.POSITIVE_INFINITY;
  let max_y = Number.NEGATIVE_INFINITY;

  positions.forEach((point) => {
    min_x = Math.min(min_x, point.x);
    max_x = Math.max(max_x, point.x);
    min_y = Math.min(min_y, point.y);
    max_y = Math.max(max_y, point.y);
  });

  const center_x = (min_x + max_x) / 2;
  const center_y = (min_y + max_y) / 2;
  const centered_positions: Map<string, LayoutPoint> = new Map();

  positions.forEach((point, node_id) => {
    centered_positions.set(node_id, {
      x: point.x - center_x,
      y: point.y - center_y,
    });
  });

  return centered_positions;
}

function format_metadata_value(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(format_metadata_value).join(', ');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return '';
}

function collect_node_metadata_lines(node: KnowledgeGraphNodeRecord): string[] {
  const metadata = node.metadata || {};
  const nested =
    metadata.metadata && typeof metadata.metadata === 'object' && !Array.isArray(metadata.metadata)
      ? (metadata.metadata as Record<string, unknown>)
      : {};
  const file_type = format_metadata_value(metadata.source_file_type || metadata.file_type || nested.source_file_type);
  const strategy = format_metadata_value(metadata.detected_strategy || metadata.strategy || nested.detected_strategy || nested.strategy);
  const input_mode = format_metadata_value(metadata.input_mode || nested.input_mode);
  const worksheet_name = format_metadata_value(metadata.worksheet_name || nested.worksheet_name);
  const lines: string[] = [];

  if (file_type) {
    lines.push(`文件类型：${file_type}`);
  }
  if (strategy) {
    lines.push(`导入策略：${get_strategy_label(strategy)}`);
  }
  if (input_mode) {
    lines.push(`导入方式：${get_input_mode_label(input_mode)}`);
  }
  if (worksheet_name) {
    lines.push(`工作表：${worksheet_name}`);
  }

  return lines;
}

function collect_edge_metadata_lines(edge: KnowledgeGraphEdgeRecord): string[] {
  const metadata = edge.metadata || {};
  const lines: string[] = [];

  if (metadata.source_id) {
    lines.push(`来源：${format_metadata_value(metadata.source_id)}`);
  }
  if (metadata.paragraph_id) {
    lines.push(`段落：${format_metadata_value(metadata.paragraph_id)}`);
  }

  return lines;
}

function node_subtitle(node: KnowledgeGraphNodeRecord): string {
  if (node.type === 'source' || node.type === 'workbook') {
    return '来源节点';
  }
  if (node.type === 'paragraph') {
    return '段落节点';
  }
  if (node.type === 'worksheet') {
    return '工作表节点';
  }
  if (node.type === 'record') {
    return '记录节点';
  }
  return '实体节点';
}

function resolve_node_size(node: KnowledgeGraphNodeRecord, is_selected: boolean, is_highlighted: boolean): number {
  const base_size = NODE_SIZE_MAP[node.type] ?? 28;
  if (is_selected) {
    return Math.round(base_size * 1.24);
  }
  if (is_highlighted) {
    return Math.round(base_size * 1.12);
  }
  return base_size;
}

function resolve_edge_size(edge: KnowledgeGraphEdgeRecord, is_selected: boolean, is_highlighted: boolean): number {
  const base_size = clamp(1.1 + edge.weight * 0.75, 1.1, 5.3);
  if (is_selected) {
    return clamp(base_size * 1.2, 1.4, 6.4);
  }
  if (is_highlighted) {
    return clamp(base_size * 1.08, 1.2, 5.8);
  }
  return base_size;
}

function collect_selection_highlights(
  edges: KnowledgeGraphEdgeRecord[],
  selected_node_id: string | null,
  selected_edge_id: string | null,
) {
  const node_ids = new Set<string>();
  const edge_ids = new Set<string>();

  if (selected_node_id) {
    edges.forEach((edge) => {
      if (edge.source !== selected_node_id && edge.target !== selected_node_id) {
        return;
      }
      edge_ids.add(edge.id);
      node_ids.add(edge.source);
      node_ids.add(edge.target);
    });
    node_ids.delete(selected_node_id);
  }

  if (selected_edge_id) {
    const edge = edges.find((current_edge) => current_edge.id === selected_edge_id);
    if (edge) {
      node_ids.add(edge.source);
      node_ids.add(edge.target);
    }
  }

  return { node_ids: [...node_ids], edge_ids: [...edge_ids] };
}

function build_elements(
  nodes: KnowledgeGraphNodeRecord[],
  edges: KnowledgeGraphEdgeRecord[],
  layout: Map<string, LayoutPoint>,
  layout_scale: number,
  selected_node_id: string | null,
  selected_edge_id: string | null,
  highlighted_node_ids: string[],
  highlighted_edge_ids: string[],
): ElementDefinition[] {
  const visible_node_ids = new Set(nodes.map((node) => node.id));
  const selection_highlights = collect_selection_highlights(edges, selected_node_id, selected_edge_id);
  const highlighted_node_set = new Set([...highlighted_node_ids, ...selection_highlights.node_ids]);
  const highlighted_edge_set = new Set([...highlighted_edge_ids, ...selection_highlights.edge_ids]);
  const has_highlights = highlighted_node_set.size > 0 || highlighted_edge_set.size > 0 || Boolean(selected_node_id || selected_edge_id);

  const node_elements = nodes.map((node) => {
    const is_selected = node.id === selected_node_id;
    const is_highlighted = highlighted_node_set.has(node.id);
    const point = layout.get(node.id) ?? { x: 0, y: 0 };

    return {
      data: {
        id: node.id,
        type: node.type,
        color: NODE_COLOR_MAP[node.type] ?? '#6b7280',
        size: resolve_node_size(node, is_selected, is_highlighted),
        displayLabel: is_selected || is_highlighted || node.type === 'source' || node.type === 'workbook' ? node.label : '',
      },
      position: { x: point.x * layout_scale, y: point.y * layout_scale },
      classes: [
        node.type === 'source' || node.type === 'workbook' ? 'is-source' : '',
        is_selected ? 'is-selected' : '',
        is_highlighted ? 'is-highlighted' : '',
        has_highlights && !is_selected && !is_highlighted ? 'is-dimmed' : '',
      ]
        .filter(Boolean)
        .join(' '),
    } satisfies ElementDefinition;
  });

  const edge_elements = edges
    .filter((edge) => visible_node_ids.has(edge.source) && visible_node_ids.has(edge.target))
    .map((edge) => {
      const is_selected = edge.id === selected_edge_id;
      const is_highlighted = highlighted_edge_set.has(edge.id);

      return {
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: edge.type,
          color: EDGE_COLOR_MAP[edge.type] ?? '#9ca3af',
          size: resolve_edge_size(edge, is_selected, is_highlighted),
          displayLabel: is_selected || is_highlighted || edge.type === 'manual' ? edge.label : '',
        },
        classes: [
          edge.type === 'manual' ? 'is-manual' : '',
          is_selected ? 'is-selected' : '',
          is_highlighted ? 'is-highlighted' : '',
          has_highlights && !is_selected && !is_highlighted ? 'is-dimmed' : '',
        ]
          .filter(Boolean)
          .join(' '),
      } satisfies ElementDefinition;
    });

  return [...node_elements, ...edge_elements];
}

function apply_graph_state(
  cy: Core,
  nodes: KnowledgeGraphNodeRecord[],
  edges: KnowledgeGraphEdgeRecord[],
  selected_node_id: string | null,
  selected_edge_id: string | null,
  highlighted_node_ids: string[],
  highlighted_edge_ids: string[],
): void {
  const selection_highlights = collect_selection_highlights(edges, selected_node_id, selected_edge_id);
  const highlighted_node_set = new Set([...highlighted_node_ids, ...selection_highlights.node_ids]);
  const highlighted_edge_set = new Set([...highlighted_edge_ids, ...selection_highlights.edge_ids]);
  const has_highlights = highlighted_node_set.size > 0 || highlighted_edge_set.size > 0 || Boolean(selected_node_id || selected_edge_id);

  cy.batch(() => {
    nodes.forEach((node) => {
      const current_node = cy.$id(node.id);
      if (current_node.empty()) {
        return;
      }
      const is_selected = node.id === selected_node_id;
      const is_highlighted = highlighted_node_set.has(node.id);
      current_node.data({
        size: resolve_node_size(node, is_selected, is_highlighted),
        displayLabel: is_selected || is_highlighted || node.type === 'source' || node.type === 'workbook' ? node.label : '',
      });
      current_node.classes(
        [
          node.type === 'source' || node.type === 'workbook' ? 'is-source' : '',
          is_selected ? 'is-selected' : '',
          is_highlighted ? 'is-highlighted' : '',
          has_highlights && !is_selected && !is_highlighted ? 'is-dimmed' : '',
        ]
          .filter(Boolean)
          .join(' '),
      );
    });

    edges.forEach((edge) => {
      const current_edge = cy.$id(edge.id);
      if (current_edge.empty()) {
        return;
      }
      const is_selected = edge.id === selected_edge_id;
      const is_highlighted = highlighted_edge_set.has(edge.id);
      current_edge.data({
        size: resolve_edge_size(edge, is_selected, is_highlighted),
        displayLabel: is_selected || is_highlighted || edge.type === 'manual' ? edge.label : '',
      });
      current_edge.classes(
        [
          edge.type === 'manual' ? 'is-manual' : '',
          is_selected ? 'is-selected' : '',
          is_highlighted ? 'is-highlighted' : '',
          has_highlights && !is_selected && !is_highlighted ? 'is-dimmed' : '',
        ]
          .filter(Boolean)
          .join(' '),
      );
    });
  });
}

function apply_theme_styles(cy: Core, resolved_theme: ResolvedTheme): void {
  const is_dark = resolved_theme === 'dark';
  const node_text_color = is_dark ? '#f8fafc' : '#163447';
  const edge_text_color = is_dark ? '#dbe7ec' : '#315061';
  const text_bg = is_dark ? 'rgba(15, 23, 32, 0.78)' : 'rgba(255, 255, 255, 0.84)';

  cy.style()
    .selector('node')
    .style({
      'background-color': 'data(color)',
      width: 'data(size)',
      height: 'data(size)',
      label: 'data(displayLabel)',
      color: node_text_color,
      'font-family': 'Microsoft YaHei UI, PingFang SC, Noto Sans SC, sans-serif',
      'font-size': '11px',
      'font-weight': 600,
      'text-wrap': 'wrap',
      'text-max-width': '180px',
      'text-valign': 'bottom',
      'text-margin-y': 10,
      'text-background-color': text_bg,
      'text-background-opacity': 1,
      'text-background-padding': '3px',
      'background-opacity': 0.95,
      'overlay-opacity': 0,
      'border-width': '0',
    })
    .selector('node.is-selected')
    .style({ 'border-width': '3px', 'border-color': is_dark ? '#f8fafc' : '#173f56' })
    .selector('node.is-highlighted')
    .style({ 'border-width': '2px', 'border-color': is_dark ? '#36b4a7' : '#173f56' })
    .selector('node.is-dimmed')
    .style({ opacity: 0.22, 'text-opacity': 0.18 })
    .selector('edge')
    .style({
      width: 'data(size)',
      label: 'data(displayLabel)',
      'line-color': 'data(color)',
      'target-arrow-color': 'data(color)',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'font-family': 'Microsoft YaHei UI, PingFang SC, Noto Sans SC, sans-serif',
      color: edge_text_color,
      'font-size': '10px',
      'text-background-color': text_bg,
      'text-background-opacity': 1,
      'text-background-padding': '3px',
      'text-rotation': 'autorotate',
      opacity: 0.88,
      'overlay-opacity': 0,
    })
    .selector('edge[type = "contains"], edge[type = "contains_sheet"], edge[type = "contains_record"], edge[type = "mentions"]')
    .style({ 'target-arrow-shape': 'none' })
    .selector('edge.is-manual')
    .style({ 'line-style': 'dashed' })
    .selector('edge.is-dimmed')
    .style({ opacity: 0.16, 'text-opacity': 0.1 })
    .update();
}

function collect_focus_elements(
  cy: Core,
  selected_node_id: string | null,
  selected_edge_id: string | null,
  highlighted_node_ids: string[],
  highlighted_edge_ids: string[],
) {
  let focus_elements = cy.collection();

  if (highlighted_node_ids.length || highlighted_edge_ids.length) {
    highlighted_node_ids.forEach((node_id) => {
      const node = cy.$id(node_id);
      focus_elements = focus_elements.union(node).union(node.connectedEdges()).union(node.connectedEdges().connectedNodes());
    });
    highlighted_edge_ids.forEach((edge_id) => {
      const edge = cy.$id(edge_id);
      focus_elements = focus_elements.union(edge).union(edge.connectedNodes());
    });
    return focus_elements;
  }

  if (selected_node_id) {
    const node = cy.$id(selected_node_id);
    return focus_elements.union(node).union(node.connectedEdges()).union(node.connectedEdges().connectedNodes());
  }

  if (selected_edge_id) {
    const edge = cy.$id(selected_edge_id);
    return focus_elements.union(edge).union(edge.connectedNodes());
  }

  return cy.elements();
}

function fit_all_view(cy: Core): void {
  if (!cy.elements().length || cy.width() <= 0 || cy.height() <= 0) {
    return;
  }
  cy.stop();
  cy.fit(cy.elements(), cy.elements().length > 140 ? 26 : 40);
}

function focus_view(cy: Core, focus_state: FocusState): void {
  if (cy.width() <= 0 || cy.height() <= 0) {
    return;
  }
  const focus_elements = collect_focus_elements(
    cy,
    focus_state.selected_node_id,
    focus_state.selected_edge_id,
    focus_state.highlighted_node_ids,
    focus_state.highlighted_edge_ids,
  );
  if (!focus_elements.length) {
    return;
  }
  cy.stop();
  cy.animate({ fit: { eles: focus_elements, padding: focus_elements.length <= 2 ? 60 : 44 } }, { duration: 120 });
}

function has_focus_targets(focus_state: FocusState): boolean {
  return Boolean(
    focus_state.selected_node_id ||
      focus_state.selected_edge_id ||
      focus_state.highlighted_node_ids.length ||
      focus_state.highlighted_edge_ids.length,
  );
}

function schedule_viewport(callback: () => void): void {
  if (typeof window === 'undefined') {
    callback();
    return;
  }
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(callback);
  });
}

function restore_view(cy: Core, viewport_mode: GraphViewportMode, focus_state: FocusState): void {
  if (viewport_mode === 'focus-selection' && has_focus_targets(focus_state)) {
    focus_view(cy, focus_state);
    return;
  }
  fit_all_view(cy);
}

function hover_position(event: EventObject) {
  const rendered_position = event.renderedPosition ?? { x: 0, y: 0 };
  return { x: rendered_position.x + 12, y: rendered_position.y + 12 };
}

export function KnowledgeGraphCanvas(props: KnowledgeGraphCanvasProps) {
  const {
    nodes,
    edges,
    layout_revision,
    viewport_mode,
    viewport_command,
    selected_node_id,
    selected_edge_id,
    highlighted_node_ids,
    highlighted_edge_ids,
    resolved_theme,
    on_select_node,
    on_select_edge,
    on_clear_selection,
  } = props;

  const container_ref = useRef<HTMLDivElement | null>(null);
  const cy_ref = useRef<Core | null>(null);
  const resize_observer_ref = useRef<ResizeObserver | null>(null);
  const node_map_ref = useRef<Map<string, KnowledgeGraphNodeRecord>>(new Map());
  const edge_map_ref = useRef<Map<string, KnowledgeGraphEdgeRecord>>(new Map());
  const on_select_node_ref = useRef(on_select_node);
  const on_select_edge_ref = useRef(on_select_edge);
  const on_clear_selection_ref = useRef(on_clear_selection);
  const viewport_mode_ref = useRef<GraphViewportMode>(viewport_mode);
  const focus_state_ref = useRef<FocusState>({
    selected_node_id,
    selected_edge_id,
    highlighted_node_ids,
    highlighted_edge_ids,
  });
  const last_viewport_command_id_ref = useRef<number | null>(null);
  const layout = useMemo(() => {
    if (layout_revision > 0) {
      layout_cache.clear();
    }
    return nodes.length ? build_layout(nodes, edges) : new Map<string, LayoutPoint>();
  }, [edges, layout_revision, nodes]);
  const layout_scale = useMemo(() => resolve_layout_scale(nodes.length), [nodes.length]);
  const [hover_card, set_hover_card] = useState<HoverCardState | null>(null);
  const [render_error, set_render_error] = useState<string | null>(null);

  useEffect(() => {
    focus_state_ref.current = { selected_node_id, selected_edge_id, highlighted_node_ids, highlighted_edge_ids };
    node_map_ref.current = new Map(nodes.map((node) => [node.id, node]));
    edge_map_ref.current = new Map(edges.map((edge) => [edge.id, edge]));
    on_select_node_ref.current = on_select_node;
    on_select_edge_ref.current = on_select_edge;
    on_clear_selection_ref.current = on_clear_selection;
    viewport_mode_ref.current = viewport_mode;
  }, [
    edges,
    highlighted_edge_ids,
    highlighted_node_ids,
    nodes,
    on_clear_selection,
    on_select_edge,
    on_select_node,
    selected_edge_id,
    selected_node_id,
    viewport_mode,
  ]);

  useEffect(() => {
    const container = container_ref.current;
    if (!container || cy_ref.current) {
      return;
    }

    try {
      const cy = cytoscape({
        container,
        elements: [],
        minZoom: 0.18,
        maxZoom: 2.8,
        wheelSensitivity: 0.16,
        autoungrabify: true,
        boxSelectionEnabled: false,
        textureOnViewport: true,
      });

      cy.on('tap', 'node', (event: EventObject) => on_select_node_ref.current(event.target.id()));
      cy.on('tap', 'edge', (event: EventObject) => on_select_edge_ref.current(event.target.id()));
      cy.on('tap', (event: EventObject) => {
        if (event.target === cy) {
          on_clear_selection_ref.current();
        }
      });

      cy.on('mouseover', 'node', (event: EventObject) => {
        const hovered_node = node_map_ref.current.get(event.target.id());
        if (!hovered_node) {
          return;
        }
        const position = hover_position(event);
        set_hover_card({
          title: hovered_node.label,
          subtitle: node_subtitle(hovered_node),
          metadata_lines: collect_node_metadata_lines(hovered_node),
          x: position.x,
          y: position.y,
        });
      });

      cy.on('mouseover', 'edge', (event: EventObject) => {
        const hovered_edge = edge_map_ref.current.get(event.target.id());
        if (!hovered_edge) {
          return;
        }
        const source_label = node_map_ref.current.get(hovered_edge.source)?.label ?? hovered_edge.source;
        const target_label = node_map_ref.current.get(hovered_edge.target)?.label ?? hovered_edge.target;
        const position = hover_position(event);
        set_hover_card({
          title: hovered_edge.label,
          subtitle: `${source_label} -> ${target_label}`,
          metadata_lines: collect_edge_metadata_lines(hovered_edge),
          x: position.x,
          y: position.y,
        });
      });

      cy.on('mouseout', 'node', () => set_hover_card(null));
      cy.on('mouseout', 'edge', () => set_hover_card(null));
      cy_ref.current = cy;

      if (typeof ResizeObserver !== 'undefined') {
        const observer = new ResizeObserver(() => {
          cy.resize();
          schedule_viewport(() => {
            restore_view(cy, viewport_mode_ref.current, focus_state_ref.current);
          });
        });
        observer.observe(container);
        resize_observer_ref.current = observer;
      }
    } catch (current_error) {
      set_render_error((current_error as Error).message || '图谱渲染失败。');
    }

    return () => {
      resize_observer_ref.current?.disconnect();
      cy_ref.current?.destroy();
      cy_ref.current = null;
      set_hover_card(null);
    };
  }, []);

  useEffect(() => {
    const cy = cy_ref.current;
    if (cy) {
      apply_theme_styles(cy, resolved_theme);
    }
  }, [resolved_theme]);

  useEffect(() => {
    const cy = cy_ref.current;
    if (!cy) {
      return;
    }

    set_hover_card(null);
    set_render_error(null);

    if (!nodes.length) {
      cy.elements().remove();
      return;
    }

    

    try {
      const elements = build_elements(
        nodes,
        edges,
        layout,
        layout_scale,
        selected_node_id,
        selected_edge_id,
        highlighted_node_ids,
        highlighted_edge_ids,
      );
      cy.batch(() => {
        cy.elements().remove();
        cy.add(elements);
      });
      apply_theme_styles(cy, resolved_theme);
      schedule_viewport(() => {
        restore_view(cy, viewport_mode_ref.current, focus_state_ref.current);
      });
    } catch (current_error) {
      set_render_error((current_error as Error).message || '图谱渲染失败。');
    }
  }, [edges, layout, layout_scale, nodes, resolved_theme]);

  useEffect(() => {
    const cy = cy_ref.current;
    if (!cy || !cy.elements().length) {
      return;
    }
    apply_graph_state(
      cy,
      nodes,
      edges,
      selected_node_id,
      selected_edge_id,
      highlighted_node_ids,
      highlighted_edge_ids,
    );
  }, [edges, highlighted_edge_ids.join('|'), highlighted_node_ids.join('|'), nodes, selected_edge_id, selected_node_id]);

  useEffect(() => {
    const cy = cy_ref.current;
    if (!cy || !cy.elements().length || !viewport_command) {
      return;
    }
    if (last_viewport_command_id_ref.current === viewport_command.id) {
      return;
    }
    last_viewport_command_id_ref.current = viewport_command.id;

    if (viewport_command.type === 'fit-all') {
      schedule_viewport(() => {
        fit_all_view(cy);
      });
      return;
    }
    if (viewport_command.type === 'focus-selection') {
      if (!has_focus_targets(focus_state_ref.current)) {
        return;
      }
      schedule_viewport(() => {
        focus_view(cy, focus_state_ref.current);
      });
      return;
    }
    if (viewport_command.type === 'zoom-in') {
      schedule_viewport(() => {
        cy.zoom({ level: clamp(cy.zoom() * 1.14, 0.18, 2.8), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
      });
      return;
    }
    if (viewport_command.type === 'zoom-out') {
      schedule_viewport(() => {
        cy.zoom({ level: clamp(cy.zoom() / 1.14, 0.18, 2.8), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
      });
    }
  }, [viewport_command]);

  useEffect(() => {
    const cy = cy_ref.current;
    if (!cy || !cy.elements().length || viewport_mode !== 'focus-selection') {
      return;
    }
    if (!has_focus_targets(focus_state_ref.current)) {
      return;
    }
    schedule_viewport(() => {
      focus_view(cy, focus_state_ref.current);
    });
  }, [highlighted_edge_ids.join('|'), highlighted_node_ids.join('|'), selected_edge_id, selected_node_id, viewport_mode]);

  return (
    <div className='kb-graph-canvas'>
      <div className='kb-graph-surface' ref={container_ref} />
      {!nodes.length ? <div className='kb-graph-empty'>当前图谱还没有可展示的数据。</div> : null}
      {render_error ? <div className='kb-graph-empty kb-graph-empty-error'>{render_error}</div> : null}
      {hover_card ? (
        <div className='kb-graph-tooltip' style={{ left: `${hover_card.x}px`, top: `${hover_card.y}px` }}>
          <strong>{hover_card.title}</strong>
          <span>{hover_card.subtitle}</span>
          {hover_card.metadata_lines.length ? (
            <div className='kb-graph-tooltip-metadata'>
              {hover_card.metadata_lines.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
