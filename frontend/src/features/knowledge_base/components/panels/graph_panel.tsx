/**
 * 模块名称：features/knowledge_base/components/panels/graph_panel
 * 主要功能：渲染图谱主视图、手工连边区域和图谱摘要信息。
 */

import { Suspense, lazy } from 'react';

import type { ResolvedTheme } from '../../../../theme';
import type { GraphEdgeRecord, GraphNodeRecord, GraphPayload } from '../../types/knowledge_base';

const GraphCanvas = lazy(async () => {
  const module = await import('../graph_canvas');
  return { default: module.GraphCanvas };
});

interface GraphPanelProps {
  graph: GraphPayload;
  is_graph_loading: boolean;
  selected_node: GraphNodeRecord | null;
  selected_edge: GraphEdgeRecord | null;
  source_node_id: string;
  target_node_id: string;
  highlighted_node_ids: string[];
  highlighted_edge_ids: string[];
  resolved_theme: ResolvedTheme;
  set_source_node_id: (node_id: string) => void;
  set_target_node_id: (node_id: string) => void;
  select_node: (node: GraphNodeRecord) => void;
  select_edge: (edge: GraphEdgeRecord) => void;
  clear_selection: () => void;
  create_edge: () => Promise<void>;
}

export function GraphPanel(props: GraphPanelProps) {
  const {
    graph,
    is_graph_loading,
    selected_node,
    selected_edge,
    source_node_id,
    target_node_id,
    highlighted_node_ids,
    highlighted_edge_ids,
    resolved_theme,
    set_source_node_id,
    set_target_node_id,
    select_node,
    select_edge,
    clear_selection,
    create_edge,
  } = props;
  const can_create_edge: boolean =
    Boolean(source_node_id) && Boolean(target_node_id) && source_node_id !== target_node_id;

  return (
    <section className='panel panel-wide'>
      <header className='panel-header'>
        <div className='section-title-row'>
          <div>
            <h2>知识图谱</h2>
            <p>浏览文档、片段和实体节点。问答结果会高亮对应路径，并自动聚焦相关子图。</p>
          </div>
          <div className='graph-stat-grid'>
            <span className='graph-stat-pill'>节点 {graph.nodes.length}</span>
            <span className='graph-stat-pill'>边 {graph.edges.length}</span>
            <span className='graph-stat-pill'>高亮 {highlighted_node_ids.length}</span>
          </div>
        </div>
      </header>

      <div className='graph-stage'>
        {is_graph_loading ? <div className='graph-overlay'>正在刷新图谱...</div> : null}
        <Suspense fallback={<div className='graph-canvas graph-canvas-placeholder'>正在加载图谱画布...</div>}>
          <GraphCanvas
            nodes={graph.nodes}
            edges={graph.edges}
            selected_node_id={selected_node?.id ?? null}
            selected_edge_id={selected_edge?.id ?? null}
            highlighted_node_ids={highlighted_node_ids}
            highlighted_edge_ids={highlighted_edge_ids}
            resolved_theme={resolved_theme}
            on_node_select={select_node}
            on_edge_select={select_edge}
            on_clear_selection={clear_selection}
          />
        </Suspense>
      </div>

      <div className='graph-toolbar'>
        <div className='connection-builder'>
          <div className='section-title-row'>
            <div>
              <h3>手工连边</h3>
              <p className='muted-text'>你手动建立的连接会参与后续排序，用来强化真正重要的业务关系。</p>
            </div>
            <button className='ghost-button' type='button' onClick={clear_selection}>
              清空选中
            </button>
          </div>
          <div className='field-grid'>
            <label>
              起点节点
              <select value={source_node_id} onChange={(event) => set_source_node_id(event.target.value)}>
                <option value=''>选择起点节点</option>
                {graph.nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              终点节点
              <select value={target_node_id} onChange={(event) => set_target_node_id(event.target.value)}>
                <option value=''>选择终点节点</option>
                {graph.nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className='button-row'>
            <button
              className='ghost-button'
              type='button'
              onClick={() => set_source_node_id(selected_node?.id ?? '')}
            >
              选中节点设为起点
            </button>
            <button
              className='ghost-button'
              type='button'
              onClick={() => set_target_node_id(selected_node?.id ?? '')}
            >
              选中节点设为终点
            </button>
            <button
              className='primary-button'
              disabled={!can_create_edge}
              type='button'
              onClick={() => void create_edge()}
            >
              创建连边
            </button>
          </div>
          <p className='muted-text'>
            {can_create_edge
              ? `已就绪：${source_node_id.slice(0, 8)} -> ${target_node_id.slice(0, 8)}`
              : '请选择两个不同的节点后再创建手工连边。'}
          </p>
          {highlighted_edge_ids.length ? (
            <p className='highlight-summary'>
              最近一次问答高亮了 {highlighted_node_ids.length} 个节点和 {highlighted_edge_ids.length} 条边。
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
