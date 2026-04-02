import { describe, expect, it, vi } from 'vitest';

import { use_workspace_focus_actions } from './use_workspace_focus_actions';

describe('use_workspace_focus_actions', () => {
  it('focus_citation prefers the explicit anchor node when provided', () => {
    const set_active_workspace = vi.fn();
    const set_is_source_library_open = vi.fn();
    const set_include_paragraphs = vi.fn();
    const set_selected_edge_id = vi.fn();
    const set_selected_node_id = vi.fn();
    const set_highlighted_node_ids = vi.fn();
    const set_highlighted_edge_ids = vi.fn();
    const set_selected_source_browser_id = vi.fn();
    const set_selected_source_ids = vi.fn();
    const set_density = vi.fn();

    const focus = use_workspace_focus_actions({
      default_graph_density: 88,
      highlighted_node_ids: ['entity:fire-cat', 'source:source-0'],
      selected_node_id: 'entity:fire-cat',
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
    });

    focus.focus_citation('source-1', 'paragraph-2', {
      preferred_anchor_node_id: 'entity:fire-cat-canonical',
      anchor_node_ids: ['entity:fire-cat-canonical', 'entity:fire-cat-alias'],
    });

    expect(set_active_workspace).toHaveBeenCalledWith('graph');
    expect(set_is_source_library_open).toHaveBeenCalledWith(false);
    expect(set_selected_source_browser_id).toHaveBeenCalledWith('source-1');
    expect(set_selected_source_ids).toHaveBeenCalledWith(['source-1']);
    expect(set_include_paragraphs).toHaveBeenCalledWith(true);
    expect(set_selected_edge_id).toHaveBeenCalledWith(null);
    expect(set_selected_node_id).toHaveBeenCalledWith('entity:fire-cat-canonical');
    expect(set_highlighted_node_ids).toHaveBeenCalledWith([
      'entity:fire-cat',
      'source:source-1',
      'paragraph:paragraph-2',
    ]);
    expect(set_highlighted_edge_ids).toHaveBeenCalledWith([]);
    expect(set_density).not.toHaveBeenCalled();
  });

  it('focus_citation keeps graph in semantic context without guessing an anchor', () => {
    const set_active_workspace = vi.fn();
    const set_is_source_library_open = vi.fn();
    const set_include_paragraphs = vi.fn();
    const set_selected_edge_id = vi.fn();
    const set_selected_node_id = vi.fn();
    const set_highlighted_node_ids = vi.fn();
    const set_highlighted_edge_ids = vi.fn();
    const set_selected_source_browser_id = vi.fn();
    const set_selected_source_ids = vi.fn();
    const set_density = vi.fn();

    const focus = use_workspace_focus_actions({
      default_graph_density: 88,
      highlighted_node_ids: ['entity:fire-cat', 'entity:tiger'],
      selected_node_id: 'entity:fire-cat',
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
    });

    focus.focus_citation('source-7', 'paragraph-9', {
      anchor_node_ids: ['entity:lion', 'entity:panther'],
    });

    expect(set_selected_node_id).toHaveBeenCalledWith(null);
    expect(set_highlighted_node_ids).toHaveBeenCalledWith([
      'entity:fire-cat',
      'entity:tiger',
      'source:source-7',
      'paragraph:paragraph-9',
    ]);
  });
});
