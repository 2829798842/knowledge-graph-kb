/**
 * Derived shell state for the workspace layout.
 */

import { use_knowledge_base_workspace_context } from '../context/knowledge_base_workspace_context';

const ACTIVE_TASK_STATUSES: Set<string> = new Set(['queued', 'running']);

function preview_source_names(values: string[], max_count: number): string {
  if (!values.length) {
    return '未筛选来源';
  }
  if (values.length <= max_count) {
    return values.join('、');
  }
  return `${values.slice(0, max_count).join('、')} 等 ${values.length} 个`;
}

export function use_workspace_shell() {
  const workspace = use_knowledge_base_workspace_context();

  const active_task_count: number = workspace.tasks.filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length;
  const ready_source_count: number = workspace.sources.filter((source) => source.status === 'ready').length;
  const selected_source_names: string[] = workspace.sources
    .filter((source) => workspace.selected_source_ids.includes(source.id))
    .map((source) => source.name);
  const selected_source_summary: string = preview_source_names(selected_source_names, 3);
  const selected_node_label: string | null =
    workspace.graph.nodes.find((node) => node.id === workspace.selected_node_id)?.label ?? null;
  const selected_edge_label: string | null =
    workspace.graph.edges.find((edge) => edge.id === workspace.selected_edge_id)?.label ?? null;
  const focus_summary: string =
    selected_node_label ??
    selected_edge_label ??
    workspace.source_detail?.source.name ??
    (workspace.last_query_text ? `检索上下文：${workspace.last_query_text}` : '当前未聚焦对象');

  return {
    active_workspace: workspace.active_workspace,
    set_active_workspace: workspace.set_active_workspace,
    message: workspace.message,
    error: workspace.error,
    query_mode: workspace.query_mode,
    document_count: workspace.sources.length,
    task_count: workspace.tasks.length,
    active_task_count,
    ready_source_count,
    node_count: workspace.graph.nodes.length,
    edge_count: workspace.graph.edges.length,
    highlight_node_count: workspace.highlighted_node_ids.length,
    highlight_edge_count: workspace.highlighted_edge_ids.length,
    focus_summary,
    selected_source_summary,
    source_density: workspace.density,
    include_paragraphs: workspace.include_paragraphs,
    clear_source_filters: workspace.clear_source_filters,
    reset_graph_filters: workspace.reset_graph_filters,
    clear_highlights: workspace.clear_highlights,
    clear_graph_selection: workspace.clear_graph_selection,
    refresh_graph: workspace.refresh_graph,
  };
}
