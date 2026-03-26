/**
 * Sidebar navigation and quick context.
 */

import type { ThemeMode } from '../../../../theme';
import { THEME_MODE_OPTIONS, WORKSPACE_TABS } from '../config/ui_constants';
import { use_workspace_shell } from '../hooks/use_workspace_shell';

function SidebarMetric(props: { label: string; value: string | number; note: string }) {
  const { label, value, note } = props;

  return (
    <article className='kb-signal-card'>
      <span className='kb-signal-label'>{label}</span>
      <strong className='kb-signal-value'>{value}</strong>
      <span className='kb-helper-text'>{note}</span>
    </article>
  );
}

interface WorkspaceOverviewProps {
  theme_mode: ThemeMode;
  set_theme_mode: (theme_mode: ThemeMode) => void;
}

export function WorkspaceOverview(props: WorkspaceOverviewProps) {
  const { theme_mode, set_theme_mode } = props;
  const {
    active_workspace,
    set_active_workspace,
    active_task_count,
    task_count,
    ready_source_count,
    document_count,
    node_count,
    edge_count,
    focus_summary,
    selected_source_summary,
    source_density,
    include_paragraphs,
    clear_source_filters,
    reset_graph_filters,
    clear_highlights,
    clear_graph_selection,
    refresh_graph,
  } = use_workspace_shell();

  return (
    <aside className='kb-overview-panel'>
      <div className='kb-sidebar-brand'>
        <span className='kb-context-label'>Knowledge Graph KB</span>
        <strong>知识图谱工作台</strong>
        <p>像 ChatGPT 一样把导航固定在左侧，把当前任务留在右边，让操作路径更短、界面更安静。</p>
      </div>

      <nav aria-label='工作区导航' className='kb-sidebar-nav'>
        {WORKSPACE_TABS.map((tab) => {
          const is_active = tab.id === active_workspace;

          return (
            <button
              className={`kb-sidebar-link ${is_active ? 'is-active' : ''}`}
              key={tab.id}
              onClick={() => set_active_workspace(tab.id)}
              type='button'
            >
              <strong>{tab.label}</strong>
              <span>{tab.description}</span>
            </button>
          );
        })}
      </nav>

      <section className='kb-sidebar-section'>
        <span className='kb-context-label'>工作区状态</span>
        <div className='kb-sidebar-stats'>
          <SidebarMetric label='可用来源' note='可用于检索和图谱' value={`${ready_source_count}/${document_count}`} />
          <SidebarMetric label='活跃任务' note='运行中或排队中' value={active_task_count} />
          <SidebarMetric label='图谱规模' note='节点 / 关系' value={`${node_count} / ${edge_count}`} />
        </div>
      </section>

      <section className='kb-sidebar-section'>
        <span className='kb-context-label'>当前上下文</span>
        <div className='kb-context-card'>
          <strong>{focus_summary}</strong>
          <span>{`来源筛选：${selected_source_summary}`}</span>
          <span>{`图谱密度 ${source_density}% ｜ ${include_paragraphs ? '显示段落节点' : '隐藏段落节点'}`}</span>
          <span>{`任务总数 ${task_count}`}</span>
        </div>
      </section>

      <section className='kb-sidebar-section'>
        <span className='kb-context-label'>快捷操作</span>
        <div className='kb-sidebar-actions'>
          <button className='kb-secondary-button' onClick={clear_source_filters} type='button'>
            清空来源筛选
          </button>
          <button className='kb-secondary-button' onClick={reset_graph_filters} type='button'>
            重置图谱过滤
          </button>
          <button className='kb-secondary-button' onClick={clear_highlights} type='button'>
            清空高亮
          </button>
          <button className='kb-secondary-button' onClick={clear_graph_selection} type='button'>
            清空选择
          </button>
          <button className='kb-secondary-button' onClick={() => void refresh_graph()} type='button'>
            刷新图谱
          </button>
        </div>
      </section>

      <section className='kb-sidebar-section kb-sidebar-footer'>
        <span className='kb-context-label'>显示设置</span>
        <div className='kb-theme-switcher'>
          {THEME_MODE_OPTIONS.map((option) => (
            <button
              className={`kb-pill-button ${theme_mode === option.id ? 'is-active' : ''}`}
              key={option.id}
              onClick={() => set_theme_mode(option.id)}
              type='button'
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
}
