import {
  Application,
  Container,
  Graphics,
  Rectangle,
  Text,
  TextStyle,
  type FederatedPointerEvent,
} from 'pixi.js';
import { Viewport } from 'pixi-viewport';

import type { ResolvedTheme } from '../../../../theme';
import type {
  GraphViewMode,
  GraphViewportMode,
} from '../../shared/types/knowledge_base_types';
import { build_graph_layout } from './graph_layout_engine';
import {
  build_edge_hover_card_at,
  build_node_hover_card_at,
  type HoverCardState,
} from './graph_canvas_tooltip';
import {
  resolve_label_priority_node_ids,
  resolve_edge_alpha,
  resolve_edge_width,
  resolve_node_fill_alpha,
  resolve_node_halo_width,
  resolve_node_label_alpha,
  resolve_node_radius,
  should_show_edge_label,
  should_show_node_label,
} from './graph_readability';
import type { GraphLayoutMap, RenderEdge, RenderNode } from './graph_render_types';

interface GraphRuntimeSceneState {
  graph_view_mode: GraphViewMode;
  nodes: RenderNode[];
  edges: RenderEdge[];
  selected_node_id: string | null;
  selected_edge_id: string | null;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
}

type HoverTarget =
  | { type: 'node'; node: RenderNode; x: number; y: number }
  | { type: 'edge'; edge: RenderEdge; source_label: string; target_label: string; x: number; y: number }
  | null;

interface GraphRuntimeOptions {
  container: HTMLDivElement;
  resolved_theme: ResolvedTheme;
  on_select_node: (node_id: string) => void;
  on_select_edge: (edge_id: string) => void;
  on_clear_selection: () => void;
  on_hover_change: (hover_card: HoverCardState | null) => void;
}

function clamp(value: number, min_value: number, max_value: number): number {
  return Math.min(max_value, Math.max(min_value, value));
}

function to_alpha(value: number): number {
  return clamp(value, 0.08, 1);
}

function resolve_theme_palette(resolved_theme: ResolvedTheme) {
  const is_dark = resolved_theme === 'dark';
  return {
    background_label_fill: is_dark ? 0x0f1720 : 0xffffff,
    background_label_alpha: is_dark ? 0.76 : 0.84,
    node_text: is_dark ? 0xf8fafc : 0x163447,
    edge_text: is_dark ? 0xe2edf4 : 0x315061,
    halo: is_dark ? 0xf8fafc : 0x173f56,
  };
}

function make_text_style(color: number): TextStyle {
  return new TextStyle({
    fontFamily: 'Microsoft YaHei UI, PingFang SC, Noto Sans SC, sans-serif',
    fontSize: 11,
    fontWeight: '600',
    fill: color,
  });
}

function distance_to_segment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) {
    return Math.hypot(px - x1, py - y1);
  }
  const t = clamp(((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy), 0, 1);
  const cx = x1 + t * dx;
  const cy = y1 + t * dy;
  return Math.hypot(px - cx, py - cy);
}

function create_signature(nodes: RenderNode[], edges: RenderEdge[]): string {
  return `${nodes.map((node) => node.id).join('|')}::${edges.map((edge) => edge.id).join('|')}`;
}

export class GraphRuntime {
  private readonly container: HTMLDivElement;
  private readonly on_select_node: (node_id: string) => void;
  private readonly on_select_edge: (edge_id: string) => void;
  private readonly on_clear_selection: () => void;
  private readonly on_hover_change: (hover_card: HoverCardState | null) => void;

  private app: Application | null = null;
  private viewport: Viewport | null = null;
  private edge_layer = new Graphics();
  private node_layer = new Graphics();
  private overlay_layer = new Graphics();
  private label_layer = new Container();
  private scene_state: GraphRuntimeSceneState = {
    graph_view_mode: 'global',
    nodes: [],
    edges: [],
    selected_node_id: null,
    selected_edge_id: null,
    highlighted_node_ids: [],
    highlighted_edge_ids: [],
  };
  private layout_positions: GraphLayoutMap = new Map();
  private scene_signature = '';
  private layout_revision = 0;
  private resolved_theme: ResolvedTheme;
  private hover_target: HoverTarget = null;
  private last_viewport_mode: GraphViewportMode = 'fit-all';

  constructor(options: GraphRuntimeOptions) {
    this.container = options.container;
    this.resolved_theme = options.resolved_theme;
    this.on_select_node = options.on_select_node;
    this.on_select_edge = options.on_select_edge;
    this.on_clear_selection = options.on_clear_selection;
    this.on_hover_change = options.on_hover_change;
  }

  async init(): Promise<void> {
    if (this.app) {
      return;
    }

    const width = Math.max(1, this.container.clientWidth || 1);
    const height = Math.max(1, this.container.clientHeight || 1);
    const app = new Application();
    await app.init({
      width,
      height,
      antialias: true,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1,
      backgroundAlpha: 0,
      preference: 'webgl',
    });

    app.canvas.style.width = '100%';
    app.canvas.style.height = '100%';
    app.canvas.style.display = 'block';
    this.container.replaceChildren(app.canvas);

    const viewport = new Viewport({
      screenWidth: width,
      screenHeight: height,
      worldWidth: width,
      worldHeight: height,
      events: app.renderer.events,
      ticker: app.ticker,
      disableOnContextMenu: true,
    });
    viewport.eventMode = 'static';
    viewport.forceHitArea = new Rectangle(-50000, -50000, 100000, 100000);
    viewport.drag().pinch().wheel({ smooth: 3 }).decelerate().clampZoom({ minScale: 0.08, maxScale: 3.2 });

    viewport.addChild(this.edge_layer);
    viewport.addChild(this.overlay_layer);
    viewport.addChild(this.node_layer);
    viewport.addChild(this.label_layer);
    app.stage.addChild(viewport);

    viewport.on('pointermove', (event: FederatedPointerEvent) => this.handle_pointer_move(event));
    viewport.on('pointerleave', () => this.set_hover_target(null));
    viewport.on('pointertap', (event: FederatedPointerEvent) => this.handle_pointer_tap(event));

    this.app = app;
    this.viewport = viewport;
  }

  destroy(): void {
    this.on_hover_change(null);
    this.hover_target = null;
    this.viewport?.removeAllListeners();
    this.app?.destroy(true, { children: true });
    this.app = null;
    this.viewport = null;
    this.layout_positions = new Map();
    this.scene_signature = '';
  }

  resize(next_mode?: GraphViewportMode): void {
    if (!this.app || !this.viewport) {
      return;
    }
    const width = Math.max(1, this.container.clientWidth || 1);
    const height = Math.max(1, this.container.clientHeight || 1);
    this.app.renderer.resize(width, height);
    this.viewport.resize(width, height);
    this.restore_view(next_mode ?? this.last_viewport_mode);
  }

  set_theme(resolved_theme: ResolvedTheme): void {
    this.resolved_theme = resolved_theme;
    this.render_scene();
  }

  set_scene(scene_state: GraphRuntimeSceneState, layout_revision: number): void {
    this.scene_state = scene_state;
    const signature = create_signature(scene_state.nodes, scene_state.edges);
    if (signature !== this.scene_signature || layout_revision !== this.layout_revision) {
      this.layout_positions = build_graph_layout(scene_state.nodes, scene_state.edges, this.layout_positions);
      this.scene_signature = signature;
      this.layout_revision = layout_revision;
    }
    this.render_scene();
  }

  run_viewport_command(command_type: 'fit-all' | 'focus-selection' | 'zoom-in' | 'zoom-out' | 'relayout'): void {
    if (!this.viewport) {
      return;
    }

    if (command_type === 'fit-all') {
      this.last_viewport_mode = 'fit-all';
      this.fit_all();
      return;
    }

    if (command_type === 'focus-selection') {
      if (!this.has_focus_targets()) {
        return;
      }
      this.last_viewport_mode = 'focus-selection';
      this.focus_selection();
      return;
    }

    if (command_type === 'zoom-in') {
      this.viewport.setZoom(clamp(this.viewport.scaled * 1.14, 0.08, 3.2), true);
      return;
    }

    if (command_type === 'zoom-out') {
      this.viewport.setZoom(clamp(this.viewport.scaled / 1.14, 0.08, 3.2), true);
      return;
    }

    if (command_type === 'relayout') {
      this.layout_positions = build_graph_layout(this.scene_state.nodes, this.scene_state.edges);
      this.render_scene();
      this.last_viewport_mode = 'fit-all';
      this.fit_all();
    }
  }

  restore_view(mode: GraphViewportMode): void {
    if (!this.viewport) {
      return;
    }
    this.last_viewport_mode = mode;
    if (mode === 'focus-selection' && this.has_focus_targets()) {
      this.focus_selection();
      return;
    }
    this.fit_all();
  }

  private handle_pointer_move(event: FederatedPointerEvent): void {
    if (!this.viewport || !this.app) {
      return;
    }
    const point = this.viewport.toWorld(event.global);
    const next_hover_target = this.find_hover_target(point.x, point.y);
    if (!next_hover_target) {
      this.app.canvas.style.cursor = 'grab';
      this.set_hover_target(null);
      return;
    }

    this.app.canvas.style.cursor = 'pointer';
    this.set_hover_target(next_hover_target);
  }

  private handle_pointer_tap(event: FederatedPointerEvent): void {
    if (!this.viewport) {
      return;
    }
    const point = this.viewport.toWorld(event.global);
    const target = this.find_hover_target(point.x, point.y);
    if (!target) {
      this.on_clear_selection();
      return;
    }
    if (target.type === 'node') {
      this.on_select_node(target.node.id);
      return;
    }
    this.on_select_edge(target.edge.id);
  }

  private set_hover_target(target: HoverTarget): void {
    if (
      this.hover_target?.type === target?.type &&
      ((target?.type === 'node' && this.hover_target?.type === 'node' && this.hover_target.node.id === target.node.id) ||
        (target?.type === 'edge' && this.hover_target?.type === 'edge' && this.hover_target.edge.id === target.edge.id))
    ) {
      return;
    }

    this.hover_target = target;
    if (!target) {
      this.on_hover_change(null);
      return;
    }

    if (target.type === 'node') {
      this.on_hover_change(build_node_hover_card_at(target.node, target.x, target.y));
      return;
    }

    this.on_hover_change(
      build_edge_hover_card_at(target.edge, target.source_label, target.target_label, target.x, target.y),
    );
  }

  private render_scene(): void {
    if (!this.viewport) {
      return;
    }

    const palette = resolve_theme_palette(this.resolved_theme);
    const node_style = make_text_style(palette.node_text);
    const edge_style = make_text_style(palette.edge_text);
    const node_lookup = new Map(this.scene_state.nodes.map((node) => [node.id, node]));
    const selected_related_edge_ids = new Set<string>();
    const selected_related_node_ids = new Set<string>();

    if (this.scene_state.selected_node_id) {
      for (const edge of this.scene_state.edges) {
        if (edge.source === this.scene_state.selected_node_id || edge.target === this.scene_state.selected_node_id) {
          selected_related_edge_ids.add(edge.id);
          selected_related_node_ids.add(edge.source);
          selected_related_node_ids.add(edge.target);
        }
      }
    }
    if (this.scene_state.selected_edge_id) {
      const selected_edge = this.scene_state.edges.find((edge) => edge.id === this.scene_state.selected_edge_id);
      if (selected_edge) {
        selected_related_node_ids.add(selected_edge.source);
        selected_related_node_ids.add(selected_edge.target);
      }
    }

    const highlighted_node_ids = new Set([...this.scene_state.highlighted_node_ids]);
    const highlighted_edge_ids = new Set([
      ...this.scene_state.highlighted_edge_ids,
      ...selected_related_edge_ids,
    ]);
    const label_priority_node_ids = resolve_label_priority_node_ids(
      this.scene_state.nodes,
      this.scene_state.edges,
    );
    const has_context =
      Boolean(this.scene_state.selected_node_id || this.scene_state.selected_edge_id) ||
      highlighted_node_ids.size > 0 ||
      highlighted_edge_ids.size > 0;
    const readability_context = {
      graph_view_mode: this.scene_state.graph_view_mode,
      total_node_count: this.scene_state.nodes.length,
      has_context,
      selected_node_id: this.scene_state.selected_node_id,
      selected_edge_id: this.scene_state.selected_edge_id,
      selected_related_node_ids,
      highlighted_node_ids,
      highlighted_edge_ids,
      highlighted_edge_count: highlighted_edge_ids.size,
      label_priority_node_ids,
    };

    this.edge_layer.clear();
    this.node_layer.clear();
    this.overlay_layer.clear();
    const children = this.label_layer.removeChildren();
    children.forEach((child) => child.destroy());

    for (const edge of this.scene_state.edges) {
      const source = this.layout_positions.get(edge.source);
      const target = this.layout_positions.get(edge.target);
      if (!source || !target) {
        continue;
      }
      this.edge_layer.lineStyle(
        resolve_edge_width(edge, readability_context),
        edge.color,
        to_alpha(resolve_edge_alpha(edge, readability_context)),
      );
      this.edge_layer.moveTo(source.x, source.y);
      this.edge_layer.lineTo(target.x, target.y);

      if (should_show_edge_label(edge, readability_context)) {
        const label = new Text(edge.short_label, edge_style);
        label.alpha = 0.92;
        label.x = (source.x + target.x) / 2 - label.width / 2;
        label.y = (source.y + target.y) / 2 - label.height / 2;
        const background = new Graphics();
        background.beginFill(palette.background_label_fill, palette.background_label_alpha);
        background.drawRoundedRect(label.x - 6, label.y - 4, label.width + 12, label.height + 8, 10);
        background.endFill();
        this.label_layer.addChild(background);
        this.label_layer.addChild(label);
      }
    }

    for (const node of this.scene_state.nodes) {
      const point = this.layout_positions.get(node.id);
      if (!point) {
        continue;
      }
      const radius = resolve_node_radius(node, readability_context);
      this.node_layer.beginFill(node.color, resolve_node_fill_alpha(node, readability_context));
      this.node_layer.lineStyle(resolve_node_halo_width(node, readability_context), palette.halo, 0.95);
      this.node_layer.drawCircle(point.x, point.y, radius);
      this.node_layer.endFill();

      if (node.id === this.scene_state.selected_node_id) {
        this.overlay_layer.lineStyle(1.5, palette.halo, 0.28);
        this.overlay_layer.drawCircle(point.x, point.y, radius + 9);
      }

      if (!should_show_node_label(node, readability_context)) {
        continue;
      }

      const label = new Text(
        node.id === this.scene_state.selected_node_id ? node.display_label : node.short_label,
        node_style,
      );
      label.alpha = resolve_node_label_alpha(node, readability_context);
      label.x = point.x - label.width / 2;
      label.y = point.y + radius + 8;
      const background = new Graphics();
      background.beginFill(palette.background_label_fill, palette.background_label_alpha);
      background.drawRoundedRect(label.x - 6, label.y - 4, label.width + 12, label.height + 8, 10);
      background.endFill();
      this.label_layer.addChild(background);
      this.label_layer.addChild(label);
    }
  }

  private has_focus_targets(): boolean {
    return Boolean(
      this.scene_state.selected_node_id ||
        this.scene_state.selected_edge_id ||
        this.scene_state.highlighted_node_ids.length ||
        this.scene_state.highlighted_edge_ids.length,
    );
  }

  private fit_all(): void {
    const bounds = this.resolve_bounds(this.scene_state.nodes.map((node) => node.id));
    if (!bounds || !this.viewport) {
      return;
    }
    this.apply_bounds(bounds, this.scene_state.nodes.length >= 320 ? 90 : 72);
  }

  private focus_selection(): void {
    if (!this.viewport) {
      return;
    }

    const focus_node_ids = new Set<string>();
    if (this.scene_state.selected_node_id) {
      focus_node_ids.add(this.scene_state.selected_node_id);
      for (const edge of this.scene_state.edges) {
        if (edge.source === this.scene_state.selected_node_id || edge.target === this.scene_state.selected_node_id) {
          focus_node_ids.add(edge.source);
          focus_node_ids.add(edge.target);
        }
      }
    }
    if (this.scene_state.selected_edge_id) {
      const edge = this.scene_state.edges.find((current_edge) => current_edge.id === this.scene_state.selected_edge_id);
      if (edge) {
        focus_node_ids.add(edge.source);
        focus_node_ids.add(edge.target);
      }
    }
    this.scene_state.highlighted_node_ids.forEach((node_id) => focus_node_ids.add(node_id));

    const bounds = this.resolve_bounds([...focus_node_ids]);
    if (!bounds) {
      this.fit_all();
      return;
    }
    this.apply_bounds(bounds, 110);
  }

  private resolve_bounds(node_ids: string[]): { min_x: number; min_y: number; max_x: number; max_y: number } | null {
    const points = node_ids
      .map((node_id) => {
        const node = this.scene_state.nodes.find((current_node) => current_node.id === node_id);
        const point = this.layout_positions.get(node_id);
        if (!node || !point) {
          return null;
        }
        return {
          min_x: point.x - node.radius,
          min_y: point.y - node.radius,
          max_x: point.x + node.radius,
          max_y: point.y + node.radius,
        };
      })
      .filter(Boolean) as Array<{ min_x: number; min_y: number; max_x: number; max_y: number }>;

    if (!points.length) {
      return null;
    }

    return {
      min_x: Math.min(...points.map((point) => point.min_x)),
      min_y: Math.min(...points.map((point) => point.min_y)),
      max_x: Math.max(...points.map((point) => point.max_x)),
      max_y: Math.max(...points.map((point) => point.max_y)),
    };
  }

  private apply_bounds(
    bounds: { min_x: number; min_y: number; max_x: number; max_y: number },
    padding: number,
  ): void {
    if (!this.viewport) {
      return;
    }
    const width = Math.max(bounds.max_x - bounds.min_x, 1);
    const height = Math.max(bounds.max_y - bounds.min_y, 1);
    const scale = clamp(
      Math.min(
        this.viewport.screenWidth / (width + padding * 2),
        this.viewport.screenHeight / (height + padding * 2),
      ),
      0.08,
      3.2,
    );
    this.viewport.setZoom(scale, false);
    this.viewport.moveCenter((bounds.min_x + bounds.max_x) / 2, (bounds.min_y + bounds.max_y) / 2);
  }

  private find_hover_target(x: number, y: number): HoverTarget {
    const node_hit = this.find_hovered_node(x, y);
    if (node_hit) {
      return node_hit;
    }
    return this.find_hovered_edge(x, y);
  }

  private find_hovered_node(x: number, y: number): HoverTarget {
    let best: { node: RenderNode; distance: number } | null = null;
    for (const node of this.scene_state.nodes) {
      const point = this.layout_positions.get(node.id);
      if (!point) {
        continue;
      }
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance > node.radius + 8) {
        continue;
      }
      if (!best || distance < best.distance) {
        best = { node, distance };
      }
    }
    if (!best || !this.viewport) {
      return null;
    }
    const screen_point = this.viewport.toScreen({ x, y });
    return { type: 'node', node: best.node, x: screen_point.x + 16, y: screen_point.y + 16 };
  }

  private find_hovered_edge(x: number, y: number): HoverTarget {
    let best: { edge: RenderEdge; distance: number } | null = null;
    for (const edge of this.scene_state.edges) {
      const source = this.layout_positions.get(edge.source);
      const target = this.layout_positions.get(edge.target);
      if (!source || !target) {
        continue;
      }
      const distance = distance_to_segment(x, y, source.x, source.y, target.x, target.y);
      const threshold = edge.is_structural ? 8 : 10;
      if (distance > threshold) {
        continue;
      }
      if (!best || distance < best.distance) {
        best = { edge, distance };
      }
    }
    if (!best || !this.viewport) {
      return null;
    }
    const screen_point = this.viewport.toScreen({ x, y });
    const source_label = this.scene_state.nodes.find((node) => node.id === best.edge.source)?.display_label ?? best.edge.source;
    const target_label = this.scene_state.nodes.find((node) => node.id === best.edge.target)?.display_label ?? best.edge.target;
    return {
      type: 'edge',
      edge: best.edge,
      source_label,
      target_label,
      x: screen_point.x + 16,
      y: screen_point.y + 16,
    };
  }
}
