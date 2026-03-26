/**
 * Workspace header for the active page.
 */

import { WORKSPACE_TABS } from '../config/ui_constants';
import { use_workspace_shell } from '../hooks/use_workspace_shell';

export function WorkspaceHeader() {
  const {
    active_workspace,
    document_count,
    task_count,
    node_count,
    edge_count,
    message,
    error,
  } = use_workspace_shell();

  const active_tab = WORKSPACE_TABS.find((tab) => tab.id === active_workspace) ?? WORKSPACE_TABS[0];
  const status_text = error ?? message ?? '工作区已就绪';

  return (
    <header className='kb-toolbar'>
      <div className='kb-toolbar-copy'>
        <span className='kb-context-label'>Current Workspace</span>
        <strong>{active_tab.label}</strong>
        <p>{active_tab.description}</p>
      </div>

      <div className='kb-toolbar-status'>
        <strong className={`kb-toolbar-message ${error ? 'is-error' : ''}`}>{status_text}</strong>

        <div className='kb-meta-strip'>
          <span className='kb-meta-pill'>{`来源 ${document_count}`}</span>
          <span className='kb-meta-pill'>{`任务 ${task_count}`}</span>
          <span className='kb-meta-pill'>{`节点 ${node_count}`}</span>
          <span className='kb-meta-pill'>{`关系 ${edge_count}`}</span>
        </div>
      </div>
    </header>
  );
}
