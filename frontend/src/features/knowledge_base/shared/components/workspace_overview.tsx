/**
 * Workspace overview cards and quick actions.
 */

import type { ReactNode } from 'react';

import { QUERY_MODE_LABELS, WORKSPACE_LABELS } from '../config/ui_constants';
import { use_workspace_shell } from '../hooks/use_workspace_shell';

interface WorkspaceOverviewCardProps {
  heading: string;
  value: string | number;
  note: string;
  children?: ReactNode;
}

function WorkspaceSummaryCard(props: WorkspaceOverviewCardProps) {
  const { heading, value, note, children } = props;
  return (
    <article className='kb-signal-card'>
      <span className='kb-signal-label'>{heading}</span>
      <strong className='kb-signal-value'>{value}</strong>
      <p className='kb-overview-note'>{note}</p>
      {children}
    </article>
  );
}

function ActionCard(props: {
  heading: string;
  value: string;
  note: string;
  children: React.ReactNode;
}) {
  const { heading, value, note, children } = props;
  return (
    <article className='kb-context-card'>
      <span className='kb-context-label'>{heading}</span>
      <strong>{value}</strong>
      <p>{note}</p>
      <div className='kb-context-actions'>{children}</div>
    </article>
  );
}

export function WorkspaceOverview() {
  const {
    active_workspace,
    query_mode,
    active_task_count,
    task_count,
    ready_source_count,
    document_count,
    node_count,
    edge_count,
    highlight_node_count,
    highlight_edge_count,
    focus_summary,
    selected_source_summary,
    source_density,
    include_paragraphs,
    set_active_workspace,
    clear_source_filters,
    reset_graph_filters,
    clear_highlights,
    clear_graph_selection,
    refresh_graph,
  } = use_workspace_shell();

  return (
    <aside className='kb-overview-panel'>
      <div className='kb-overview-heading'>
        <span className='kb-context-label'>工作台概览</span>
        <h2>左侧总览</h2>
        <p>把状态、筛选和快捷操作固定在侧栏里，主区域只专注当前页面，切换时不会再把内容都堆在一起。</p>
      </div>

      <div className='kb-overview-scroll'>
        <section className='kb-signal-strip'>
          <WorkspaceSummaryCard
            heading='当前页面'
            note={`当前检索模式：${QUERY_MODE_LABELS[query_mode]}`}
            value={WORKSPACE_LABELS[active_workspace]}
          />

          <WorkspaceSummaryCard
            heading='来源就绪度'
            note='已就绪来源可用于图谱构建和内容检索。'
            value={`${ready_source_count}/${document_count}`}
          />

          <WorkspaceSummaryCard
            heading='图谱规模'
            note={include_paragraphs ? '当前包含段落节点。' : '当前仅显示来源、实体与关系。'}
            value={`${node_count} 节点 / ${edge_count} 关系`}
          />

          <WorkspaceSummaryCard
            heading='当前焦点'
            note={`高亮节点 ${highlight_node_count} 个，高亮关系 ${highlight_edge_count} 条。`}
            value={focus_summary}
          />
        </section>

        <section className='kb-context-grid'>
          <ActionCard
            heading='快捷切换'
            note='在不同工作流之间快速切换。'
            value={active_task_count > 0 ? `${active_task_count} 个活跃任务` : '当前没有活跃任务'}
          >
            <button className='kb-secondary-button' onClick={() => set_active_workspace('import')} type='button'>
              打开导入
            </button>
            <button className='kb-secondary-button' onClick={() => set_active_workspace('config')} type='button'>
              打开模型配置
            </button>
            <button className='kb-secondary-button' onClick={() => set_active_workspace('query')} type='button'>
              打开检索
            </button>
            <button className='kb-secondary-button' onClick={() => set_active_workspace('graph')} type='button'>
              打开图谱
            </button>
            <button className='kb-secondary-button' onClick={() => set_active_workspace('source')} type='button'>
              打开来源
            </button>
          </ActionCard>

          <ActionCard
            heading='来源与过滤'
            note={`图谱密度 ${source_density}%；${include_paragraphs ? '已显示' : '未显示'}段落节点。`}
            value={selected_source_summary}
          >
            <button className='kb-secondary-button' onClick={clear_source_filters} type='button'>
              清空来源筛选
            </button>
            <button className='kb-secondary-button' onClick={reset_graph_filters} type='button'>
              重置图谱过滤
            </button>
          </ActionCard>

          <ActionCard heading='交互控制' note={`任务队列总数：${task_count}`} value={focus_summary}>
            <button className='kb-secondary-button' onClick={clear_highlights} type='button'>
              清空高亮
            </button>
            <button className='kb-secondary-button' onClick={clear_graph_selection} type='button'>
              清空选择
            </button>
            <button className='kb-secondary-button' onClick={() => void refresh_graph()} type='button'>
              刷新图谱
            </button>
          </ActionCard>
        </section>
      </div>
    </aside>
  );
}
