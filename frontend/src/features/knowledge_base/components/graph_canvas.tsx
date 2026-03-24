/**
 * 模块名称：features/knowledge_base/components/graph_canvas
 * features：使用 Sigma.js 渲染知识图谱画布，并处理节点高亮、选中与视口聚焦。
 */

import { useEffect, useRef, useState } from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';

import type { ResolvedTheme } from '../../../theme';
import type { GraphEdgeRecord, GraphNodeRecord } from '../types/knowledge_base';
import { get_edge_display_label, get_node_type_label } from '../utils/label_utils';

interface GraphCanvasProps {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
  selected_node_id: string | null;
  selected_edge_id: string | null;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
  resolved_theme: ResolvedTheme;
  on_node_select: (node: GraphNodeRecord) => void;
  on_edge_select: (edge: GraphEdgeRecord) => void;
  on_clear_selection: () => void;
}

interface SigmaNodeAttributes {
  x: number;
  y: number;
  size: number;
  label: string | null;
  color: string;
  type: string;
  hidden: boolean;
  forceLabel: boolean;
  highlighted: boolean;
  zIndex: number;
  node_type: string;
}

interface SigmaEdgeAttributes {
  size: number;
  label: string | null;
  color: string;
  type: string;
  hidden: boolean;
  forceLabel: boolean;
  zIndex: number;
}

interface Point2D {
  x: number;
  y: number;
}

interface HoverCardState {
  title: string;
  subtitle: string;
  x: number;
  y: number;
}

interface WebglCheckResult {
  is_available: boolean;
  reason: string | null;
}

interface GraphCanvasHandlers {
  on_node_select: (node: GraphNodeRecord) => void;
  on_edge_select: (edge: GraphEdgeRecord) => void;
  on_clear_selection: () => void;
}

const NODE_PALETTE: Record<string, string> = {
  document: '#c67c2f',
  chunk: '#0f766e',
  entity: '#154d71',
};

const EDGE_PALETTE: Record<string, string> = {
  contains: '#d6a160',
  semantic: '#1c9a84',
  mentions: '#3a7ca5',
  manual: '#d14d72',
};

const NODE_SIZE_BY_TYPE: Record<string, number> = {
  document: 18,
  chunk: 7,
  entity: 11,
};

let cached_webgl_check_result: WebglCheckResult | null = null;

function clamp(value: number, min_value: number, max_value: number): number {
  return Math.min(max_value, Math.max(min_value, value));
}

/**
 * 检查当前环境是否支持 WebGL，并在检测后主动释放测试用上下文。
 *
 * @returns WebGL 可用性检测结果
 */
function check_webgl_support(): WebglCheckResult {
  if (cached_webgl_check_result) {
    return cached_webgl_check_result;
  }

  if (typeof document === 'undefined') {
    cached_webgl_check_result = {
      is_available: false,
      reason: '当前环境暂时无法创建浏览器画布。',
    };
    return cached_webgl_check_result;
  }

  const canvas: HTMLCanvasElement = document.createElement('canvas');
  const context_options: WebGLContextAttributes = {
    antialias: false,
    preserveDrawingBuffer: false,
  };
  const webgl_context: WebGL2RenderingContext | WebGLRenderingContext | null =
    canvas.getContext('webgl2', context_options) ??
    canvas.getContext('webgl', context_options) ??
    (canvas.getContext('experimental-webgl', context_options) as WebGLRenderingContext | null);

  if (!webgl_context) {
    cached_webgl_check_result = {
      is_available: false,
      reason: '当前浏览器或图形环境未启用 WebGL，Sigma 图谱暂时不可用。',
    };
    return cached_webgl_check_result;
  }

  const lose_context_extension: WEBGL_lose_context | null =
    typeof webgl_context.getExtension === 'function' ? webgl_context.getExtension('WEBGL_lose_context') : null;
  lose_context_extension?.loseContext();

  cached_webgl_check_result = { is_available: true, reason: null };
  return cached_webgl_check_result;
}

function hash_string(value: string): number {
  let hash: number = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0);
}

function with_alpha(hex_color: string, alpha: number): string {
  const normalized_color: string = hex_color.replace('#', '');
  const safe_alpha: number = clamp(alpha, 0, 1);
  const expanded_color: string =
    normalized_color.length === 3
      ? normalized_color
          .split('')
          .map((character) => `${character}${character}`)
          .join('')
      : normalized_color;
  const red: number = Number.parseInt(expanded_color.slice(0, 2), 16);
  const green: number = Number.parseInt(expanded_color.slice(2, 4), 16);
  const blue: number = Number.parseInt(expanded_color.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${safe_alpha})`;
}

function polar_point(index: number, total: number, radius: number, angle_offset = 0): Point2D {
  if (total <= 1) {
    return { x: 0, y: 0 };
  }

  const angle: number = angle_offset + (Math.PI * 2 * index) / total;
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function read_document_id_from_node(node: GraphNodeRecord): string | null {
  const raw_document_id: unknown = node.metadata.document_id;
  return typeof raw_document_id === 'string' && raw_document_id ? raw_document_id : null;
}

function should_show_node_label(
  node: GraphNodeRecord,
  total_nodes: number,
  selected_node_id: string | null,
  highlighted_node_ids: Set<string>,
): boolean {
  if (node.id === selected_node_id || highlighted_node_ids.has(node.id)) {
    return true;
  }
  if (node.type === 'document') {
    return true;
  }
  if (node.type === 'entity') {
    return total_nodes <= 120;
  }
  return total_nodes <= 36;
}

function build_sigma_layout(nodes: GraphNodeRecord[], edges: GraphEdgeRecord[]): Map<string, Point2D> {
  const positions: Map<string, Point2D> = new Map<string, Point2D>();
  const neighbor_map: Map<string, Set<string>> = new Map<string, Set<string>>();
  const document_nodes: GraphNodeRecord[] = nodes.filter((node) => node.type === 'document');
  const chunk_nodes: GraphNodeRecord[] = nodes.filter((node) => node.type === 'chunk');
  const entity_nodes: GraphNodeRecord[] = nodes.filter((node) => node.type === 'entity');

  nodes.forEach((node) => {
    neighbor_map.set(node.id, new Set<string>());
  });
  edges.forEach((edge) => {
    neighbor_map.get(edge.source)?.add(edge.target);
    neighbor_map.get(edge.target)?.add(edge.source);
  });

  document_nodes.forEach((node, index) => {
    positions.set(node.id, polar_point(index, document_nodes.length, document_nodes.length > 1 ? 3.6 : 0));
  });

  const chunks_by_document: Map<string, GraphNodeRecord[]> = new Map<string, GraphNodeRecord[]>();
  const orphan_chunks: GraphNodeRecord[] = [];
  chunk_nodes.forEach((chunk) => {
    const document_id: string | null = read_document_id_from_node(chunk);
    if (!document_id) {
      orphan_chunks.push(chunk);
      return;
    }

    const bucket_key: string = `document:${document_id}`;
    const current_chunks: GraphNodeRecord[] = chunks_by_document.get(bucket_key) ?? [];
    current_chunks.push(chunk);
    chunks_by_document.set(bucket_key, current_chunks);
  });

  chunks_by_document.forEach((chunks, document_node_id) => {
    const anchor: Point2D = positions.get(document_node_id) ?? { x: 0, y: 0 };
    const base_angle: number = (hash_string(document_node_id) % 360) * (Math.PI / 180);
    chunks.forEach((chunk, index) => {
      const ring_radius: number = 1.9 + (index % 3) * 0.45;
      const angle: number = base_angle + (Math.PI * 2 * index) / Math.max(chunks.length, 1);
      positions.set(chunk.id, {
        x: anchor.x + Math.cos(angle) * ring_radius,
        y: anchor.y + Math.sin(angle) * ring_radius,
      });
    });
  });

  orphan_chunks.forEach((chunk, index) => {
    positions.set(chunk.id, polar_point(index, Math.max(orphan_chunks.length, 1), 6.8, 0.6));
  });

  let orphan_entity_index: number = 0;
  entity_nodes.forEach((entity) => {
    const anchor_points: Point2D[] = [...(neighbor_map.get(entity.id) ?? [])]
      .map((neighbor_id) => positions.get(neighbor_id))
      .filter((point): point is Point2D => Boolean(point));

    if (anchor_points.length) {
      const centroid: Point2D = anchor_points.reduce<Point2D>(
        (accumulator, point) => ({
          x: accumulator.x + point.x / anchor_points.length,
          y: accumulator.y + point.y / anchor_points.length,
        }),
        { x: 0, y: 0 },
      );
      const seed_angle: number = ((hash_string(entity.id) % 360) * Math.PI) / 180;
      const radius: number = 2.5 + Math.min(anchor_points.length, 4) * 0.35 + (hash_string(entity.label) % 3) * 0.2;
      positions.set(entity.id, {
        x: centroid.x + Math.cos(seed_angle) * radius,
        y: centroid.y + Math.sin(seed_angle) * radius,
      });
      return;
    }

    positions.set(entity.id, polar_point(orphan_entity_index, Math.max(entity_nodes.length, 1), 9.4, 0.4));
    orphan_entity_index += 1;
  });

  for (let iteration = 0; iteration < 60; iteration += 1) {
    const forces: Map<string, Point2D> = new Map(nodes.map((node) => [node.id, { x: 0, y: 0 }]));

    for (let left_index = 0; left_index < nodes.length; left_index += 1) {
      for (let right_index = left_index + 1; right_index < nodes.length; right_index += 1) {
        const left_node: GraphNodeRecord = nodes[left_index];
        const right_node: GraphNodeRecord = nodes[right_index];
        const left_position: Point2D = positions.get(left_node.id) ?? { x: 0, y: 0 };
        const right_position: Point2D = positions.get(right_node.id) ?? { x: 0, y: 0 };
        const delta_x: number = right_position.x - left_position.x;
        const delta_y: number = right_position.y - left_position.y;
        const distance_squared: number = Math.max(delta_x * delta_x + delta_y * delta_y, 0.05);
        const distance: number = Math.sqrt(distance_squared);
        const repulsion_strength: number = 0.14 / distance_squared;
        const force_x: number = (delta_x / distance) * repulsion_strength;
        const force_y: number = (delta_y / distance) * repulsion_strength;

        forces.get(left_node.id)!.x -= force_x;
        forces.get(left_node.id)!.y -= force_y;
        forces.get(right_node.id)!.x += force_x;
        forces.get(right_node.id)!.y += force_y;
      }
    }

    edges.forEach((edge) => {
      const source_position: Point2D = positions.get(edge.source) ?? { x: 0, y: 0 };
      const target_position: Point2D = positions.get(edge.target) ?? { x: 0, y: 0 };
      const delta_x: number = target_position.x - source_position.x;
      const delta_y: number = target_position.y - source_position.y;
      const distance: number = Math.max(Math.sqrt(delta_x * delta_x + delta_y * delta_y), 0.001);
      const ideal_distance: number =
        edge.type === 'contains' ? 1.65 : edge.type === 'mentions' ? 2.25 : edge.type === 'manual' ? 2.7 : 3.0;
      const attraction_strength: number = (distance - ideal_distance) * 0.03;
      const force_x: number = (delta_x / distance) * attraction_strength;
      const force_y: number = (delta_y / distance) * attraction_strength;

      forces.get(edge.source)!.x += force_x;
      forces.get(edge.source)!.y += force_y;
      forces.get(edge.target)!.x -= force_x;
      forces.get(edge.target)!.y -= force_y;
    });

    nodes.forEach((node) => {
      const position: Point2D = positions.get(node.id) ?? { x: 0, y: 0 };
      const mobility: number = node.type === 'document' ? 0 : node.type === 'chunk' ? 0.3 : 0.75;
      if (mobility <= 0) {
        return;
      }

      if (node.type === 'chunk') {
        const document_id: string | null = read_document_id_from_node(node);
        const anchor: Point2D | undefined = document_id ? positions.get(`document:${document_id}`) : undefined;
        if (anchor) {
          forces.get(node.id)!.x += (anchor.x - position.x) * 0.08;
          forces.get(node.id)!.y += (anchor.y - position.y) * 0.08;
        }
      } else if (node.type === 'entity') {
        const radius: number = Math.max(Math.sqrt(position.x * position.x + position.y * position.y), 0.001);
        const target_radius: number = 7.4;
        const radial_force: number = (target_radius - radius) * 0.02;
        forces.get(node.id)!.x += (position.x / radius) * radial_force;
        forces.get(node.id)!.y += (position.y / radius) * radial_force;
      }

      positions.set(node.id, {
        x: position.x + clamp(forces.get(node.id)!.x * mobility, -0.35, 0.35),
        y: position.y + clamp(forces.get(node.id)!.y * mobility, -0.35, 0.35),
      });
    });
  }

  const all_points: Point2D[] = [...positions.values()];
  const min_x: number = Math.min(...all_points.map((point) => point.x), -1);
  const max_x: number = Math.max(...all_points.map((point) => point.x), 1);
  const min_y: number = Math.min(...all_points.map((point) => point.y), -1);
  const max_y: number = Math.max(...all_points.map((point) => point.y), 1);
  const center_x: number = (min_x + max_x) / 2;
  const center_y: number = (min_y + max_y) / 2;
  const half_extent: number = Math.max(max_x - min_x, max_y - min_y, 1) / 2;
  const scale: number = 10 / half_extent;

  positions.forEach((point, node_id) => {
    positions.set(node_id, {
      x: (point.x - center_x) * scale,
      y: (point.y - center_y) * scale,
    });
  });

  return positions;
}

function collect_focus_node_ids(
  nodes: GraphNodeRecord[],
  edges: GraphEdgeRecord[],
  selected_node_id: string | null,
  selected_edge_id: string | null,
  highlighted_node_ids: string[],
  highlighted_edge_ids: string[],
): string[] {
  if (highlighted_node_ids.length || highlighted_edge_ids.length) {
    const focus_node_ids: Set<string> = new Set(highlighted_node_ids);
    highlighted_edge_ids.forEach((edge_id) => {
      const edge: GraphEdgeRecord | undefined = edges.find((candidate_edge) => candidate_edge.id === edge_id);
      if (!edge) {
        return;
      }
      focus_node_ids.add(edge.source);
      focus_node_ids.add(edge.target);
    });
    return [...focus_node_ids];
  }

  if (selected_node_id) {
    const focus_node_ids: Set<string> = new Set([selected_node_id]);
    edges.forEach((edge) => {
      if (edge.source === selected_node_id) {
        focus_node_ids.add(edge.target);
      }
      if (edge.target === selected_node_id) {
        focus_node_ids.add(edge.source);
      }
    });
    return [...focus_node_ids];
  }

  if (selected_edge_id) {
    const selected_edge: GraphEdgeRecord | undefined = edges.find((edge) => edge.id === selected_edge_id);
    if (selected_edge) {
      return [selected_edge.source, selected_edge.target];
    }
  }

  return nodes.map((node) => node.id);
}

function focus_camera(renderer: Sigma, layout: Map<string, Point2D>, node_ids: string[]): void {
  const focus_points: Point2D[] = node_ids
    .map((node_id) => layout.get(node_id))
    .filter((point): point is Point2D => Boolean(point));
  if (!focus_points.length) {
    return;
  }

  const min_x: number = Math.min(...focus_points.map((point) => point.x));
  const max_x: number = Math.max(...focus_points.map((point) => point.x));
  const min_y: number = Math.min(...focus_points.map((point) => point.y));
  const max_y: number = Math.max(...focus_points.map((point) => point.y));
  const center_x: number = (min_x + max_x) / 2;
  const center_y: number = (min_y + max_y) / 2;
  const span: number = Math.max(max_x - min_x, max_y - min_y, 1.5);
  const ratio: number = clamp(span / 16, 0.08, 1.6);

  renderer.getCamera().animate(
    {
      x: center_x,
      y: center_y,
      ratio,
    },
    { duration: 260 },
  );
}

function create_sigma_graph(
  nodes: GraphNodeRecord[],
  edges: GraphEdgeRecord[],
): {
  graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>;
  layout: Map<string, Point2D>;
} {
  const graph = new Graph<SigmaNodeAttributes, SigmaEdgeAttributes>();
  const layout: Map<string, Point2D> = build_sigma_layout(nodes, edges);

  nodes.forEach((node) => {
    const point: Point2D = layout.get(node.id) ?? { x: 0, y: 0 };
    graph.addNode(node.id, {
      x: point.x,
      y: point.y,
      size: NODE_SIZE_BY_TYPE[node.type] ?? 10,
      label: node.label,
      color: NODE_PALETTE[node.type] ?? '#607d8b',
      type: 'circle',
      hidden: false,
      forceLabel: should_show_node_label(node, nodes.length, null, new Set<string>()),
      highlighted: false,
      zIndex: node.type === 'document' ? 8 : node.type === 'entity' ? 6 : 3,
      node_type: node.type,
    });
  });

  edges.forEach((edge) => {
    if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) {
      return;
    }
    graph.addEdgeWithKey(edge.id, edge.source, edge.target, {
      size: clamp(1.2 + edge.weight * 1.4, 1.2, 6),
      label: get_edge_display_label(edge.type, edge.metadata),
      color: EDGE_PALETTE[edge.type] ?? '#7c7c7c',
      type: edge.type === 'contains' ? 'line' : 'arrow',
      hidden: false,
      forceLabel: edge.type === 'manual',
      zIndex: edge.type === 'manual' ? 9 : edge.type === 'mentions' ? 6 : 4,
    });
  });

  return { graph, layout };
}

export function GraphCanvas(props: GraphCanvasProps) {
  const {
    nodes,
    edges,
    selected_node_id,
    selected_edge_id,
    highlighted_node_ids,
    highlighted_edge_ids,
    resolved_theme,
    on_node_select,
    on_edge_select,
    on_clear_selection,
  } = props;
  const stage_ref = useRef<HTMLDivElement | null>(null);
  const renderer_ref = useRef<Sigma | null>(null);
  const layout_ref = useRef<Map<string, Point2D>>(new Map<string, Point2D>());
  const node_map_ref = useRef<Map<string, GraphNodeRecord>>(new Map<string, GraphNodeRecord>());
  const edge_map_ref = useRef<Map<string, GraphEdgeRecord>>(new Map<string, GraphEdgeRecord>());
  const handlers_ref = useRef<GraphCanvasHandlers>({
    on_node_select,
    on_edge_select,
    on_clear_selection,
  });
  const [hover_card, set_hover_card] = useState<HoverCardState | null>(null);
  const [render_error, set_render_error] = useState<string | null>(null);
  const highlighted_node_signature: string = highlighted_node_ids.join('|');
  const highlighted_edge_signature: string = highlighted_edge_ids.join('|');

  useEffect(() => {
    node_map_ref.current = new Map(nodes.map((node) => [node.id, node]));
    edge_map_ref.current = new Map(edges.map((edge) => [edge.id, edge]));
  }, [edges, nodes]);

  useEffect(() => {
    handlers_ref.current = {
      on_node_select,
      on_edge_select,
      on_clear_selection,
    };
  }, [on_clear_selection, on_edge_select, on_node_select]);

  useEffect(() => {
    const container = stage_ref.current;
    if (!container) {
      return;
    }

    if (renderer_ref.current) {
      renderer_ref.current.kill();
      renderer_ref.current = null;
    }
    container.replaceChildren();
    set_hover_card(null);
    set_render_error(null);

    if (!nodes.length) {
      layout_ref.current = new Map<string, Point2D>();
      return;
    }

    const webgl_check_result: WebglCheckResult = check_webgl_support();
    if (!webgl_check_result.is_available) {
      layout_ref.current = new Map<string, Point2D>();
      set_render_error(webgl_check_result.reason);
      return;
    }

    const { graph, layout } = create_sigma_graph(nodes, edges);
    layout_ref.current = layout;

    try {
      const renderer = new Sigma(graph, container, {
        hideEdgesOnMove: false,
        hideLabelsOnMove: false,
        renderLabels: true,
        renderEdgeLabels: true,
        enableEdgeClickEvents: true,
        enableEdgeHoverEvents: true,
        labelRenderedSizeThreshold: 6,
        labelDensity: 1,
        labelGridCellSize: 140,
        defaultNodeColor: resolved_theme === 'dark' ? '#edf6f4' : '#154d71',
        defaultEdgeColor: resolved_theme === 'dark' ? '#8ba8b9' : '#8a7f65',
        labelColor: { color: resolved_theme === 'dark' ? '#edf6f4' : '#173240' },
        edgeLabelColor: { color: resolved_theme === 'dark' ? '#d7e5ea' : '#5f5847' },
        labelFont: 'Avenir Next, Trebuchet MS, sans-serif',
        edgeLabelFont: 'Avenir Next, Trebuchet MS, sans-serif',
        labelSize: 16,
        edgeLabelSize: 13,
        zIndex: true,
        minCameraRatio: 0.05,
        maxCameraRatio: 4,
      });

      renderer.on('clickNode', ({ node }) => {
        const selected_node: GraphNodeRecord | undefined = node_map_ref.current.get(node);
        if (selected_node) {
          handlers_ref.current.on_node_select(selected_node);
        }
      });
      renderer.on('clickEdge', ({ edge }) => {
        const selected_edge: GraphEdgeRecord | undefined = edge_map_ref.current.get(edge);
        if (selected_edge) {
          handlers_ref.current.on_edge_select(selected_edge);
        }
      });
      renderer.on('clickStage', () => {
        handlers_ref.current.on_clear_selection();
      });
      renderer.on('enterNode', ({ node, event }) => {
        const hovered_node: GraphNodeRecord | undefined = node_map_ref.current.get(node);
        if (!hovered_node || !stage_ref.current) {
          return;
        }
        const bounds = stage_ref.current.getBoundingClientRect();
        set_hover_card({
          title: hovered_node.label,
          subtitle: get_node_type_label(hovered_node.type),
          x: event.original.clientX - bounds.left + 12,
          y: event.original.clientY - bounds.top + 12,
        });
      });
      renderer.on('leaveNode', () => {
        set_hover_card(null);
      });
      renderer.on('enterEdge', ({ edge, event }) => {
        const hovered_edge: GraphEdgeRecord | undefined = edge_map_ref.current.get(edge);
        if (!hovered_edge || !stage_ref.current) {
          return;
        }
        const bounds = stage_ref.current.getBoundingClientRect();
        set_hover_card({
          title: get_edge_display_label(hovered_edge.type, hovered_edge.metadata),
          subtitle: `${hovered_edge.source} -> ${hovered_edge.target}`,
          x: event.original.clientX - bounds.left + 12,
          y: event.original.clientY - bounds.top + 12,
        });
      });
      renderer.on('leaveEdge', () => {
        set_hover_card(null);
      });

      renderer_ref.current = renderer;
      const animation_frame_id: number = requestAnimationFrame(() => {
        if (renderer_ref.current !== renderer) {
          return;
        }
        focus_camera(
          renderer,
          layout,
          collect_focus_node_ids(
            nodes,
            edges,
            selected_node_id,
            selected_edge_id,
            highlighted_node_ids,
            highlighted_edge_ids,
          ),
        );
      });

      return () => {
        cancelAnimationFrame(animation_frame_id);
        renderer.kill();
        if (renderer_ref.current === renderer) {
          renderer_ref.current = null;
        }
      };
    } catch (error) {
      layout_ref.current = new Map<string, Point2D>();
      set_render_error((error as Error).message || 'Sigma 图谱初始化失败。');
      return;
    }
  }, [edges, nodes, resolved_theme]);

  useEffect(() => {
    const renderer = renderer_ref.current;
    if (!renderer) {
      return;
    }

    const highlighted_node_set: Set<string> = new Set(highlighted_node_ids);
    const highlighted_edge_set: Set<string> = new Set(highlighted_edge_ids);
    const has_highlights: boolean = Boolean(highlighted_node_set.size || highlighted_edge_set.size);

    renderer.setSetting('nodeReducer', (node_id, data) => {
      const node: GraphNodeRecord | undefined = node_map_ref.current.get(node_id);
      if (!node) {
        return data;
      }

      const is_selected: boolean = node_id === selected_node_id;
      const is_highlighted: boolean = highlighted_node_set.has(node_id);
      const force_label: boolean =
        should_show_node_label(node, nodes.length, selected_node_id, highlighted_node_set) || is_selected;

      return {
        ...data,
        color:
          has_highlights && !is_highlighted && !is_selected
            ? with_alpha(NODE_PALETTE[node.type] ?? '#607d8b', 0.18)
            : NODE_PALETTE[node.type] ?? '#607d8b',
        size: is_selected ? data.size * 1.35 : is_highlighted ? data.size * 1.18 : data.size,
        forceLabel: force_label,
        highlighted: is_highlighted || is_selected,
        label: force_label ? data.label : null,
        zIndex: is_selected ? 20 : is_highlighted ? 14 : data.zIndex,
      };
    });

    renderer.setSetting('edgeReducer', (edge_id, data) => {
      const edge: GraphEdgeRecord | undefined = edge_map_ref.current.get(edge_id);
      if (!edge) {
        return data;
      }

      const is_selected: boolean = edge_id === selected_edge_id;
      const is_highlighted: boolean = highlighted_edge_set.has(edge_id);
      const touches_selected_node: boolean =
        Boolean(selected_node_id) && (edge.source === selected_node_id || edge.target === selected_node_id);
      const display_label: string = get_edge_display_label(edge.type, edge.metadata);
      const should_show_label: boolean = is_selected || is_highlighted || edge.type === 'manual' || touches_selected_node;

      return {
        ...data,
        color:
          has_highlights && !is_highlighted
            ? with_alpha(EDGE_PALETTE[edge.type] ?? '#7c7c7c', 0.12)
            : EDGE_PALETTE[edge.type] ?? '#7c7c7c',
        size: is_selected ? data.size * 1.35 : is_highlighted ? data.size * 1.12 : data.size,
        label: should_show_label ? display_label : null,
        forceLabel: should_show_label,
        zIndex: is_selected ? 18 : is_highlighted ? 12 : data.zIndex,
      };
    });

    renderer.refresh();
    focus_camera(
      renderer,
      layout_ref.current,
      collect_focus_node_ids(
        nodes,
        edges,
        selected_node_id,
        selected_edge_id,
        highlighted_node_ids,
        highlighted_edge_ids,
      ),
    );
  }, [
    edges,
    highlighted_edge_signature,
    highlighted_node_signature,
    nodes,
    selected_edge_id,
    selected_node_id,
  ]);

  return (
    <div className='graph-canvas graph-canvas-sigma'>
      <div className='graph-stage-surface' ref={stage_ref} />
      {!nodes.length ? <div className='graph-canvas-placeholder'>当前没有可展示的图谱数据</div> : null}
      {render_error ? (
        <div className='graph-canvas-placeholder graph-canvas-error'>
          <div className='graph-fallback-card'>
            <strong>图谱画布暂时不可用</strong>
            <span>{render_error}</span>
          </div>
        </div>
      ) : null}
      <div className='graph-legend'>
        <span className='graph-legend-item'>文档</span>
        <span className='graph-legend-item'>片段</span>
        <span className='graph-legend-item'>实体</span>
      </div>
      {hover_card ? (
        <div
          className='graph-tooltip'
          style={{
            left: `${hover_card.x}px`,
            top: `${hover_card.y}px`,
          }}
        >
          <strong>{hover_card.title}</strong>
          <span>{hover_card.subtitle}</span>
        </div>
      ) : null}
    </div>
  );
}
