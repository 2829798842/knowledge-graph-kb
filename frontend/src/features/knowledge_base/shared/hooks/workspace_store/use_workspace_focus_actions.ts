import type { Dispatch, SetStateAction } from 'react';

import type { WorkspaceTab } from '../../types/knowledge_base_types';

interface WorkspaceFocusActionsProps {
  default_graph_density: number;
  highlighted_node_ids: string[];
  selected_node_id: string | null;
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

interface CitationFocusOptions {
  preferred_anchor_node_id?: string | null;
  anchor_node_ids?: string[];
}

export function use_workspace_focus_actions(props: WorkspaceFocusActionsProps) {
  const {
    default_graph_density,
    highlighted_node_ids,
    selected_node_id,
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

  function unique_ids(values: string[]): string[] {
    return Array.from(new Set(values.filter(Boolean)));
  }

  function semantic_highlight_ids(): string[] {
    return highlighted_node_ids.filter((node_id) => node_id.startsWith('entity:'));
  }

  function preferred_semantic_anchor(): string | null {
    if (selected_node_id?.startsWith('entity:')) {
      return selected_node_id;
    }
    const semantic_ids = semantic_highlight_ids();
    if (semantic_ids.length === 1) {
      return semantic_ids[0];
    }
    return null;
  }

  function resolve_citation_anchor(options?: CitationFocusOptions): string | null {
    const preferred_anchor_node_id = String(options?.preferred_anchor_node_id ?? '').trim();
    if (preferred_anchor_node_id) {
      return preferred_anchor_node_id;
    }

    const anchor_node_ids = unique_ids(
      (options?.anchor_node_ids ?? []).filter((node_id) => node_id.startsWith('entity:')),
    );
    const current_anchor = preferred_semantic_anchor();
    if (current_anchor && anchor_node_ids.includes(current_anchor)) {
      return current_anchor;
    }
    return null;
  }

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

  function focus_citation(
    source_id: string,
    paragraph_id: string,
    options?: CitationFocusOptions,
  ): void {
    const semantic_ids = semantic_highlight_ids();
    const anchor_node_id = resolve_citation_anchor(options);

    set_active_workspace('graph');
    set_is_source_library_open(false);
    set_selected_source_browser_id(source_id);
    set_selected_source_ids([source_id]);
    set_include_paragraphs(true);
    set_selected_edge_id(null);
    set_selected_node_id(anchor_node_id);
    set_highlighted_node_ids(
      unique_ids([
        ...semantic_ids,
        `source:${source_id}`,
        `paragraph:${paragraph_id}`,
      ]),
    );
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
    focus_citation,
    clear_highlights,
    select_node,
    select_edge,
    clear_graph_selection,
    clear_source_filters,
    reset_graph_filters,
  };
}
