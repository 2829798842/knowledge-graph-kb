import type { ThemeMode } from '../../../../theme';
import { WORKSPACE_TABS } from '../config/ui_constants';
import { use_workspace_shell } from '../hooks/use_workspace_shell';

interface WorkspaceOverviewProps {
  collapsed: boolean;
  theme_mode: ThemeMode;
  set_theme_mode: (theme_mode: ThemeMode) => void;
}

const TAB_ICONS = {
  chat: '聊',
  graph: '图',
} as const;

export function WorkspaceOverview(props: WorkspaceOverviewProps) {
  const { collapsed } = props;
  const { active_workspace, set_active_workspace } = use_workspace_shell();

  if (collapsed) {
    return null;
  }

  return (
    <aside className='kb-overview-panel'>
      <div className='kb-sidebar-brand'>
        <div aria-hidden='true' className='kb-sidebar-mark'>
          KG
        </div>
        <div className='kb-sidebar-brand-copy'>
          <span className='kb-context-label'>Knowledge Graph KB</span>
          <strong>知识图谱工作区</strong>
          <p>在对话和图谱之间快速切换，主内容区保持满宽聚焦。</p>
        </div>
      </div>

      <nav aria-label='主导航' className='kb-sidebar-nav'>
        {WORKSPACE_TABS.map((tab) => {
          const is_active = tab.id === active_workspace;
          return (
            <button
              aria-label={tab.label}
              className={`kb-sidebar-link ${is_active ? 'is-active' : ''}`}
              key={tab.id}
              onClick={() => set_active_workspace(tab.id)}
              type='button'
            >
              <span className='kb-sidebar-link-icon'>{TAB_ICONS[tab.id]}</span>
              <span className='kb-sidebar-link-copy'>
                <strong>{tab.label}</strong>
                <span>{tab.description}</span>
              </span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
