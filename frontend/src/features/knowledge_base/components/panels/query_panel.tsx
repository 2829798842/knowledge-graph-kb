/**
 * 模块名称：features/knowledge_base/components/panels/query_panel
 * 主要功能：渲染知识库问答表单、选中项详情与引用结果面板。
 */

import type { FormEvent } from 'react';

import type { GraphEdgeRecord, GraphNodeRecord, QueryResult } from '../../types/knowledge_base';
import { get_edge_display_label, get_node_type_label } from '../../utils/label_utils';

interface QueryPanelProps {
  query: string;
  selected_node: GraphNodeRecord | null;
  selected_edge: GraphEdgeRecord | null;
  query_result: QueryResult | null;
  is_querying: boolean;
  highlighted_node_count: number;
  highlighted_edge_count: number;
  set_query: (value: string) => void;
  submit_query: () => Promise<void>;
  remove_selected_edge: () => Promise<void>;
}

export function QueryPanel(props: QueryPanelProps) {
  const {
    query,
    selected_node,
    selected_edge,
    query_result,
    is_querying,
    highlighted_node_count,
    highlighted_edge_count,
    set_query,
    submit_query,
    remove_selected_edge,
  } = props;
  const can_submit_query: boolean = Boolean(query.trim()) && !is_querying;

  function handle_submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void submit_query();
  }

  return (
    <aside className='panel'>
      <header className='panel-header'>
        <h2>问答与详情</h2>
        <p>向当前知识库提问，并查看引用片段、排序结果与选中节点详情。</p>
      </header>

      <form className='query-form' onSubmit={handle_submit}>
        <textarea
          aria-label='知识库查询'
          placeholder='输入你想了解的问题，例如：这个项目里谁和向量检索关系最强？'
          rows={5}
          value={query}
          onChange={(event) => set_query(event.target.value)}
        />
        <div className='button-row'>
          <button className='primary-button' disabled={!can_submit_query} type='submit'>
            {is_querying ? '正在检索...' : '运行图谱问答'}
          </button>
          {selected_node ? (
            <button
              className='ghost-button'
              type='button'
              onClick={() => set_query(`请解释节点“${selected_node.label}”与当前知识库中其他内容的关系。`)}
            >
              基于选中节点提问
            </button>
          ) : null}
        </div>
      </form>

      <div className='panel-section'>
        <div className='section-title-row'>
          <h3>当前选中</h3>
          {selected_edge?.type === 'manual' ? (
            <button className='ghost-button' type='button' onClick={() => void remove_selected_edge()}>
              删除手工连边
            </button>
          ) : null}
        </div>

        {selected_node ? (
          <article className='detail-card'>
            <strong>{selected_node.label}</strong>
            <span>{get_node_type_label(selected_node.type)}</span>
            <pre>{JSON.stringify(selected_node.metadata, null, 2)}</pre>
          </article>
        ) : null}

        {selected_edge ? (
          <article className='detail-card'>
            <strong>{get_edge_display_label(selected_edge.type, selected_edge.metadata)}</strong>
            <span>
              {selected_edge.source} {'->'} {selected_edge.target}
            </span>
            <pre>{JSON.stringify(selected_edge.metadata, null, 2)}</pre>
          </article>
        ) : null}

        {!selected_node && !selected_edge ? <p className='muted-text'>请先在图谱中选择一个节点或一条边。</p> : null}
      </div>

      <div className='panel-section'>
        <div className='section-title-row'>
          <h3>问答结果</h3>
          {query_result ? (
            <span className='graph-stat-pill'>
              {highlighted_node_count} 个节点 / {highlighted_edge_count} 条边
            </span>
          ) : null}
        </div>
        {query_result ? (
          <>
            <article className='answer-card'>{query_result.answer}</article>
            <h4>引用片段</h4>
            <ul className='citation-list'>
              {query_result.citations.map((citation) => (
                <li key={citation.chunk_id}>
                  <strong>{citation.document_name}</strong>
                  <span>相关度 {citation.score.toFixed(3)}</span>
                  <p>{citation.excerpt}</p>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className='empty-state-card'>
            <strong>还没有问答结果</strong>
            <span>运行一次查询后，这里会显示答案、引用片段和高亮路径。</span>
          </div>
        )}
      </div>
    </aside>
  );
}
