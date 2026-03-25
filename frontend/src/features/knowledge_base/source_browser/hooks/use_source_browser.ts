/**
 * Source-browser workspace slice.
 */

import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';

export function use_source_browser() {
  const workspace = use_knowledge_base_workspace_context();

  return {
    sources: workspace.sources,
    selected_source_browser_id: workspace.selected_source_browser_id,
    source_detail: workspace.source_detail,
    source_paragraphs: workspace.source_paragraphs,
    set_selected_source_browser_id: workspace.set_selected_source_browser_id,
    focus_paragraph: workspace.focus_paragraph,
  };
}
