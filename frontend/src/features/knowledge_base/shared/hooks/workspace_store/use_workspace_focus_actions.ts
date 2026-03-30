import type { Dispatch, SetStateAction } from 'react';

import type { WorkspaceTab } from '../../types/knowledge_base_types';

interface WorkspaceFocusActionsProps {
  default_graph_density: number;
  set_active_workspace: Dispatch<SetStateAction<WorkspaceTab>>;
  set_is_source_library_open: Dispatch<SetStateAction<boolean>>;
  set_include_paragraphs: Dispatch<SetStateAction<boolean>>;
  set_selected_edge_id: Dispatch<SetStateAction<string | null>>;
  set_selected_node_id: Dispatch<SetStateAction<string | null>>;
  set_highlighted_node_ids: Dispatch<SetStateAction<string[]>>;
  set_highlighted_edge_ids: Dispatch<SetStateAction<string[]>>;
  set_selected_source_browser_id: Dispatch<SetStateAction<string | null>>;
  set_selected_source_ids: Dispatch<SetStateAction<string[]>>;
  set_density: Dispatch<SetStateAction<number>>;
}

export function use_workspace_focus_actions(props: WorkspaceFocusActionsProps) {
  const {
    default_graph_density,
    set_active_workspace,
    set_is_source_library_open,
    set_include_paragraphs,
    set_selected_edge_id,
    set_selected_node_id,
    set_highlighted_node_ids,
    set_highlighted_edge_ids,
    set_selected_source_browser_id,
    set_selected_source_ids,
    set_density,
  } = props;

  function focus_entity(entity_id: string): void {
    set_active_workspace('graph');
    set_include_paragraphs(true);
    set_selected_edge_id(null);
    set_selected_node_id(`entity:${entity_id}`);
    set_highlighted_node_ids([`entity:${entity_id}`]);
    set_highlighted_edge_ids([]);
  }

  function focus_relation(relation_id: string): void {
    set_active_workspace('graph');
    set_selected_node_id(null);
    set_selected_edge_id(`relation:${relation_id}`);
    set_highlighted_node_ids([]);
    set_highlighted_edge_ids([`relation:${relation_id}`]);
  }

  function focus_source(source_id: string): void {
    set_active_workspace('chat');
    set_is_source_library_open(true);
    set_selected_source_browser_id(source_id);
    set_selected_source_ids([source_id]);
    set_highlighted_node_ids([`source:${source_id}`]);
    set_highlighted_edge_ids([]);
  }

  function focus_paragraph(paragraph_id: string): void {
    set_active_workspace('graph');
    set_include_paragraphs(true);
    set_selected_edge_id(null);
    set_selected_node_id(`paragraph:${paragraph_id}`);
    set_highlighted_node_ids([`paragraph:${paragraph_id}`]);
    set_highlighted_edge_ids([]);
  }

  function clear_highlights(): void {
    set_highlighted_node_ids([]);
    set_highlighted_edge_ids([]);
  }

  function select_node(node_id: string): void {
    set_selected_edge_id(null);
    set_selected_node_id(node_id);
  }

  function select_edge(edge_id: string): void {
    set_selected_node_id(null);
    set_selected_edge_id(edge_id);
  }

  function clear_graph_selection(): void {
    set_selected_node_id(null);
    set_selected_edge_id(null);
  }

  function clear_source_filters(): void {
    set_selected_source_ids([]);
  }

  function reset_graph_filters(): void {
    set_selected_source_ids([]);
    set_include_paragraphs(true);
    set_density(default_graph_density);
  }

  return {
    focus_entity,
    focus_relation,
    focus_source,
    focus_paragraph,
    clear_highlights,
    select_node,
    select_edge,
    clear_graph_selection,
    clear_source_filters,
    reset_graph_filters,
  };
}
