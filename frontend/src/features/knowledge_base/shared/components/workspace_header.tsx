import { WORKSPACE_TABS } from '../config/ui_constants';
import { use_workspace_shell } from '../hooks/use_workspace_shell';

interface WorkspaceHeaderProps {
  sidebar_collapsed: boolean;
  on_toggle_sidebar: () => void;
}

export function WorkspaceHeader(props: WorkspaceHeaderProps) {
  const { sidebar_collapsed, on_toggle_sidebar } = props;
  const {
    active_workspace,
    document_count,
    active_task_count,
    node_count,
    edge_count,
    highlight_node_count,
    highlight_edge_count,
    focus_summary,
    message,
    error,
  } = use_workspace_shell();
  const active_tab = WORKSPACE_TABS.find((tab) => tab.id === active_workspace) ?? WORKSPACE_TABS[0];
  const status_text = error ?? message ?? '知识库已就绪。';

  return (
    <header className='kb-toolbar'>
      <div className='kb-toolbar-leading'>
        <button
          aria-label={sidebar_collapsed ? '展开侧栏' : '收起侧栏'}
          className='kb-sidebar-toggle kb-sidebar-toggle-main'
          onClick={on_toggle_sidebar}
          type='button'
        >
          <span>{sidebar_collapsed ? '>' : '<'}</span>
        </button>

        <div className='kb-toolbar-copy'>
          <span className='kb-context-label'>Workspace</span>
          <strong>{active_tab.label}</strong>
        </div>
      </div>

      <div className='kb-toolbar-status'>
        <div className='kb-toolbar-focus-row'>
          <span className='kb-context-label'>当前焦点</span>
          <strong>{focus_summary}</strong>
          <span className={`kb-toolbar-message ${error ? 'is-error' : ''}`}>{status_text}</span>
        </div>

        <div className='kb-meta-strip'>
          <span className='kb-meta-pill'>{`来源 ${document_count}`}</span>
          <span className='kb-meta-pill'>{`任务 ${active_task_count}`}</span>
          <span className='kb-meta-pill'>{`节点 ${node_count}`}</span>
          <span className='kb-meta-pill'>{`关系 ${edge_count}`}</span>
          <span className='kb-meta-pill'>{`高亮 ${highlight_node_count + highlight_edge_count}`}</span>
        </div>
      </div>
    </header>
  );
}
