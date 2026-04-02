import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force';

import type { GraphLayoutMap, RenderEdge, RenderNode } from './graph_render_types';

interface LayoutNodeDatum extends SimulationNodeDatum {
  id: string;
  radius: number;
  layer_mode: RenderNode['layer_mode'];
}

interface LayoutEdgeDatum extends SimulationLinkDatum<LayoutNodeDatum> {
  id: string;
  kind: string;
}

function initial_position(index: number, total: number): { x: number; y: number } {
  const angle = (index / Math.max(total, 1)) * Math.PI * 2;
  const ring = Math.ceil((index + 1) / 18);
  const radius = 110 + ring * 42;
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
  };
}

function resolve_charge(node_count: number): number {
  if (node_count >= 1000) return -68;
  if (node_count >= 400) return -82;
  if (node_count >= 180) return -94;
  return -108;
}

function resolve_link_distance(edge: RenderEdge, node_count: number): number {
  const density_factor = node_count >= 500 ? 0.8 : node_count >= 180 ? 0.88 : 1;
  if (edge.layer_mode === 'structure') {
    return 48 * density_factor;
  }
  if (edge.layer_mode === 'evidence') {
    return 62 * density_factor;
  }
  if (edge.type === 'manual') {
    return 92 * density_factor;
  }
  return 78 * density_factor;
}

function center_positions(positions: GraphLayoutMap): GraphLayoutMap {
  if (!positions.size) {
    return positions;
  }
  let min_x = Number.POSITIVE_INFINITY;
  let min_y = Number.POSITIVE_INFINITY;
  let max_x = Number.NEGATIVE_INFINITY;
  let max_y = Number.NEGATIVE_INFINITY;

  for (const point of positions.values()) {
    min_x = Math.min(min_x, point.x);
    min_y = Math.min(min_y, point.y);
    max_x = Math.max(max_x, point.x);
    max_y = Math.max(max_y, point.y);
  }

  const center_x = (min_x + max_x) / 2;
  const center_y = (min_y + max_y) / 2;
  const centered = new Map<string, { x: number; y: number }>();
  for (const [node_id, point] of positions.entries()) {
    centered.set(node_id, {
      x: point.x - center_x,
      y: point.y - center_y,
    });
  }
  return centered;
}

export function build_graph_layout(
  nodes: RenderNode[],
  edges: RenderEdge[],
  previous_positions?: GraphLayoutMap,
): GraphLayoutMap {
  const connected_edges = edges.filter((edge) => nodes.some((node) => node.id === edge.source) && nodes.some((node) => node.id === edge.target));
  const layout_nodes: LayoutNodeDatum[] = nodes.map((node, index) => {
    const previous = previous_positions?.get(node.id);
    const seed = previous ?? initial_position(index, nodes.length);
    return {
      id: node.id,
      radius: node.radius,
      layer_mode: node.layer_mode,
      x: seed.x,
      y: seed.y,
    };
  });

  const simulation_links: LayoutEdgeDatum[] = connected_edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    kind: edge.type,
  }));

  if (!layout_nodes.length) {
    return new Map();
  }

  if (layout_nodes.length === 1) {
    return new Map([[layout_nodes[0].id, { x: 0, y: 0 }]]);
  }

  const simulation = forceSimulation(layout_nodes)
    .force('charge', forceManyBody<LayoutNodeDatum>().strength(resolve_charge(nodes.length)))
    .force(
      'link',
      forceLink<LayoutNodeDatum, LayoutEdgeDatum>(simulation_links)
        .id((node) => node.id)
        .distance((edge) => resolve_link_distance(connected_edges.find((item) => item.id === edge.id) ?? edges[0], nodes.length))
        .strength((edge) => ((edge.kind === 'manual' || edge.kind === 'relation') ? 0.24 : 0.12)),
    )
    .force('center', forceCenter(0, 0))
    .force('collide', forceCollide<LayoutNodeDatum>().radius((node) => node.radius + 8).iterations(2));

  simulation.stop();
  const total_ticks = nodes.length >= 700 ? 280 : nodes.length >= 320 ? 240 : 180;
  for (let tick = 0; tick < total_ticks; tick += 1) {
    simulation.tick();
  }
  simulation.stop();

  const positions = new Map<string, { x: number; y: number }>();
  for (const node of layout_nodes) {
    positions.set(node.id, { x: Number(node.x ?? 0), y: Number(node.y ?? 0) });
  }

  return center_positions(positions);
}
