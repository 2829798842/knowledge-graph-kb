import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';

export function use_graph_browser() {
  const workspace = use_knowledge_base_workspace_context();

  return {
    graph: workspace.graph,
    sources: workspace.sources,
    manual_relations: workspace.manual_relations,
    selected_source_ids: workspace.selected_source_ids,
    include_paragraphs: workspace.include_paragraphs,
    density: workspace.density,
    selected_node_id: workspace.selected_node_id,
    selected_edge_id: workspace.selected_edge_id,
    node_detail: workspace.node_detail,
    edge_detail: workspace.edge_detail,
    graph_error_message: workspace.graph_error_message,
    highlighted_node_ids: workspace.highlighted_node_ids,
    highlighted_edge_ids: workspace.highlighted_edge_ids,
    is_graph_loading: workspace.is_graph_loading,
    is_creating_node: workspace.is_creating_node,
    is_creating_manual_relation: workspace.is_creating_manual_relation,
    is_renaming_node: workspace.is_renaming_node,
    is_deleting_node: workspace.is_deleting_node,
    is_deleting_edge: workspace.is_deleting_edge,
    set_selected_source_ids: workspace.set_selected_source_ids,
    set_include_paragraphs: workspace.set_include_paragraphs,
    set_density: workspace.set_density,
    select_node: workspace.select_node,
    select_edge: workspace.select_edge,
    clear_graph_selection: workspace.clear_graph_selection,
    create_entity: workspace.create_entity,
    create_relation: workspace.create_relation,
    remove_manual_relation: workspace.remove_manual_relation,
    rename_node: workspace.rename_node,
    delete_node: workspace.delete_node,
    delete_edge: workspace.delete_edge,
    clear_highlights: workspace.clear_highlights,
    refresh_graph: workspace.refresh_graph,
    reset_graph_filters: workspace.reset_graph_filters,
    clear_source_filters: workspace.clear_source_filters,
  };
}
