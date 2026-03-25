/**
 * Import-center workspace slice.
 */

import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';

export function use_import_center() {
  const workspace = use_knowledge_base_workspace_context();

  return {
    tasks: workspace.tasks,
    is_submitting_import: workspace.is_submitting_import,
    upload_files: workspace.upload_files,
    import_paste_text: workspace.import_paste_text,
    import_scan_path: workspace.import_scan_path,
    import_structured_payload: workspace.import_structured_payload,
    cancel_task: workspace.cancel_task,
    retry_task: workspace.retry_task,
  };
}
