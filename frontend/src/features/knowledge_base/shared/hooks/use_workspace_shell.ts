import { WORKSPACE_LABELS } from '../config/ui_constants';
import { use_knowledge_base_workspace_context } from '../context/knowledge_base_workspace_context';

const ACTIVE_TASK_STATUSES: Set<string> = new Set(['queued', 'running']);
const AVAILABLE_SOURCE_STATUSES: Set<string> = new Set(['ready', 'partial']);

function preview_source_names(values: string[], max_count: number): string {
  if (!values.length) {
    return '全部来源';
  }
  if (values.length <= max_count) {
    return values.join('、');
  }
  return `${values.slice(0, max_count).join('、')} 等 ${values.length} 个来源`;
}

export function use_workspace_shell() {
  const workspace = use_knowledge_base_workspace_context();

  const active_task_count = workspace.tasks.filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length;
  const available_source_count = workspace.sources.filter((source) => AVAILABLE_SOURCE_STATUSES.has(source.status)).length;
  const selected_source_names = workspace.sources
    .filter((source) => workspace.selected_source_ids.includes(source.id))
    .map((source) => source.name);
  const selected_node_label = workspace.graph.nodes.find((node) => node.id === workspace.selected_node_id)?.label ?? null;
  const selected_edge_label = workspace.graph.edges.find((edge) => edge.id === workspace.selected_edge_id)?.label ?? null;
  const focus_summary =
    selected_node_label ??
    selected_edge_label ??
    workspace.source_detail?.source.name ??
    (workspace.last_query_text ? `最近问题：${workspace.last_query_text}` : '准备开始新的知识问答');

  return {
    active_workspace: workspace.active_workspace,
    set_active_workspace: workspace.set_active_workspace,
    message: workspace.message,
    error: workspace.error,
    workspace_label: WORKSPACE_LABELS[workspace.active_workspace],
    query_mode: workspace.query_mode,
    document_count: available_source_count,
    task_count: workspace.tasks.length,
    active_task_count,
    ready_source_count: available_source_count,
    node_count: workspace.graph.nodes.length,
    edge_count: workspace.graph.edges.length,
    highlight_node_count: workspace.highlighted_node_ids.length,
    highlight_edge_count: workspace.highlighted_edge_ids.length,
    focus_summary,
    selected_source_summary: preview_source_names(selected_source_names, 3),
    source_density: workspace.density,
    include_paragraphs: workspace.include_paragraphs,
    sidebar_collapsed: workspace.sidebar_collapsed,
    set_sidebar_collapsed: workspace.set_sidebar_collapsed,
    sidebar_width: workspace.sidebar_width,
    set_sidebar_width: workspace.set_sidebar_width,
    clear_source_filters: workspace.clear_source_filters,
    reset_graph_filters: workspace.reset_graph_filters,
    clear_highlights: workspace.clear_highlights,
    clear_graph_selection: workspace.clear_graph_selection,
    refresh_graph: workspace.refresh_graph,
  };
}
