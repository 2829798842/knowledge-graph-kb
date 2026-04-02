import { useEffect, useRef, useState } from 'react';

import type { ResolvedTheme } from '../../../../theme';
import type {
  GraphViewMode,
  GraphViewportMode,
} from '../../shared/types/knowledge_base_types';
import type { ViewportCommand } from './graph_browser_utils';
import type { HoverCardState } from './graph_canvas_tooltip';
import type { RenderEdge, RenderNode } from './graph_render_types';
import { GraphRuntime } from './graph_runtime';

interface PixiKnowledgeGraphCanvasProps {
  nodes: RenderNode[];
  edges: RenderEdge[];
  layout_revision: number;
  graph_view_mode: GraphViewMode;
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

export function PixiKnowledgeGraphCanvas(props: PixiKnowledgeGraphCanvasProps) {
  const {
    nodes,
    edges,
    layout_revision,
    graph_view_mode,
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
  const runtime_ref = useRef<GraphRuntime | null>(null);
  const resize_observer_ref = useRef<ResizeObserver | null>(null);
  const last_viewport_command_id_ref = useRef<number | null>(null);
  const [hover_card, set_hover_card] = useState<HoverCardState | null>(null);
  const [render_error, set_render_error] = useState<string | null>(null);

  useEffect(() => {
    const container = container_ref.current;
    if (!container || runtime_ref.current) {
      return;
    }

    const runtime = new GraphRuntime({
      container,
      resolved_theme,
      on_select_node,
      on_select_edge,
      on_clear_selection,
      on_hover_change: set_hover_card,
    });
    runtime_ref.current = runtime;

    void runtime
      .init()
      .then(() => {
        set_render_error(null);
        runtime.set_scene(
          {
            graph_view_mode,
            nodes,
            edges,
            selected_node_id,
            selected_edge_id,
            highlighted_node_ids,
            highlighted_edge_ids,
          },
          layout_revision,
        );
        runtime.restore_view(viewport_mode);
      })
      .catch((current_error) => {
        set_render_error((current_error as Error).message || '图谱渲染失败。');
      });

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => {
        runtime_ref.current?.resize(viewport_mode);
      });
      observer.observe(container);
      resize_observer_ref.current = observer;
    }

    return () => {
      resize_observer_ref.current?.disconnect();
      resize_observer_ref.current = null;
      runtime_ref.current?.destroy();
      runtime_ref.current = null;
      set_hover_card(null);
    };
  }, []);

  useEffect(() => {
    runtime_ref.current?.set_theme(resolved_theme);
  }, [resolved_theme]);

  useEffect(() => {
    const runtime = runtime_ref.current;
    if (!runtime) {
      return;
    }
    runtime.set_scene(
      {
        graph_view_mode,
        nodes,
        edges,
        selected_node_id,
        selected_edge_id,
        highlighted_node_ids,
        highlighted_edge_ids,
      },
      layout_revision,
    );
  }, [
    edges,
    graph_view_mode,
    highlighted_edge_ids,
    highlighted_node_ids,
    layout_revision,
    nodes,
    selected_edge_id,
    selected_node_id,
  ]);

  useEffect(() => {
    const runtime = runtime_ref.current;
    if (!runtime) {
      return;
    }
    runtime.restore_view(viewport_mode);
  }, [
    highlighted_edge_ids,
    highlighted_node_ids,
    selected_edge_id,
    selected_node_id,
    viewport_mode,
  ]);

  useEffect(() => {
    const runtime = runtime_ref.current;
    if (!runtime || !viewport_command) {
      return;
    }
    if (last_viewport_command_id_ref.current === viewport_command.id) {
      return;
    }
    last_viewport_command_id_ref.current = viewport_command.id;
    runtime.run_viewport_command(viewport_command.type);
  }, [viewport_command]);

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
