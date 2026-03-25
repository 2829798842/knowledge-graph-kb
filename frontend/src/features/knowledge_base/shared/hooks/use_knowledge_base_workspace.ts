/**
 * Composes the feature-level workspace store modules into the app-facing store.
 */

import { use_graph_workspace_state } from './workspace_store/use_graph_workspace_state';
import { use_import_workspace_state } from './workspace_store/use_import_workspace_state';
import { use_model_config_workspace_state } from './workspace_store/use_model_config_workspace_state';
import { use_query_workspace_state } from './workspace_store/use_query_workspace_state';
import { use_source_workspace_state } from './workspace_store/use_source_workspace_state';
import { use_workspace_focus_actions } from './workspace_store/use_workspace_focus_actions';
import { use_workspace_ui_state } from './workspace_store/use_workspace_ui_state';

const DEFAULT_GRAPH_DENSITY: number = 88;

export function use_knowledge_base_workspace_store() {
  const ui = use_workspace_ui_state();
  const source = use_source_workspace_state({
    active_workspace: ui.active_workspace,
    set_error: ui.set_error,
  });
  const model_config = use_model_config_workspace_state({
    active_workspace: ui.active_workspace,
    set_message: ui.set_message,
    set_error: ui.set_error,
  });
  const graph = use_graph_workspace_state({
    default_graph_density: DEFAULT_GRAPH_DENSITY,
    set_message: ui.set_message,
    set_error: ui.set_error,
  });
  const imports = use_import_workspace_state({
    refresh_sources: source.refresh_sources,
    set_message: ui.set_message,
    set_error: ui.set_error,
  });
  const query = use_query_workspace_state({
    query_mode: ui.query_mode,
    selected_source_ids: graph.selected_source_ids,
    set_active_workspace: ui.set_active_workspace,
    set_last_query_text: ui.set_last_query_text,
    set_message: ui.set_message,
    set_error: ui.set_error,
    set_highlighted_node_ids: graph.set_highlighted_node_ids,
    set_highlighted_edge_ids: graph.set_highlighted_edge_ids,
  });
  const focus = use_workspace_focus_actions({
    default_graph_density: DEFAULT_GRAPH_DENSITY,
    set_active_workspace: ui.set_active_workspace,
    set_include_paragraphs: graph.set_include_paragraphs,
    set_selected_edge_id: graph.set_selected_edge_id,
    set_selected_node_id: graph.set_selected_node_id,
    set_highlighted_node_ids: graph.set_highlighted_node_ids,
    set_highlighted_edge_ids: graph.set_highlighted_edge_ids,
    set_selected_source_browser_id: source.set_selected_source_browser_id,
    set_selected_source_ids: graph.set_selected_source_ids,
    set_density: graph.set_density,
  });

  return {
    ...ui,
    ...imports,
    ...source,
    ...model_config,
    ...graph,
    ...query,
    ...focus,
  };
}

export type KnowledgeBaseWorkspaceStore = ReturnType<typeof use_knowledge_base_workspace_store>;
