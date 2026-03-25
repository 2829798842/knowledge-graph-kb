/**
 * Compact workspace toolbar.
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
    set_active_workspace,
  } = use_workspace_shell();

  const active_tab = WORKSPACE_TABS.find((tab) => tab.id === active_workspace) ?? WORKSPACE_TABS[0];

  return (
    <header className='kb-toolbar'>
      <div className='kb-toolbar-main'>
        <div className='kb-toolbar-title'>
          <span className='kb-context-label'>知识图谱工作台</span>
          <strong>知识库工作台</strong>
        </div>

        <label className='kb-form-field kb-toolbar-field'>
          <span>当前页面</span>
          <select
            aria-label='选择工作页面'
            onChange={(event) => set_active_workspace(event.target.value as typeof active_workspace)}
            value={active_workspace}
          >
            {WORKSPACE_TABS.map((tab) => (
              <option key={tab.id} value={tab.id}>
                {tab.label}
              </option>
            ))}
          </select>
        </label>

        <div className='kb-toolbar-copy'>
          <strong>{active_tab.label}</strong>
          <span>{active_tab.description}</span>
        </div>
      </div>

      <div className='kb-toolbar-status'>
        <strong className={`kb-toolbar-message ${error ? 'is-error' : ''}`}>{error ?? message}</strong>

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
