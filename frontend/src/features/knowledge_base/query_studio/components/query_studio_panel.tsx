/**
 * 问答与检索工作台面板。
 */

import { useState } from 'react';

import { ParagraphEvidencePreview } from '../../shared/components/paragraph_evidence_preview';
import { QUERY_MODE_OPTIONS } from '../../shared/config/ui_constants';
import type {
  AnswerExecutionRecord,
  ChatMessageRecord,
  ChatSessionRecord,
  EntitySearchItemRecord,
  QueryMode,
  RecordSearchItemRecord,
  RelationSearchItemRecord,
  RetrievalTraceLaneRecord,
  SourceSearchItemRecord,
} from '../../shared/types/knowledge_base_types';
import { use_query_studio } from '../hooks/use_query_studio';
import '../styles/query_studio_panel.css';

function get_mode_config(query_mode: QueryMode) {
  return QUERY_MODE_OPTIONS.find((item) => item.id === query_mode) ?? QUERY_MODE_OPTIONS[0];
}

function get_answer_status_label(status: string): string {
  if (status === 'answered') {
    return '已生成回答';
  }
  if (status === 'no_hit') {
    return '未命中证据';
  }
  if (status === 'empty_query') {
    return '问题为空';
  }
  if (status === 'stale_index') {
    return '索引失效';
  }
  return '等待执行';
}

function get_retrieval_mode_label(mode: string): string {
  if (mode === 'structured') {
    return '结构化检索';
  }
  if (mode === 'vector') {
    return '向量检索';
  }
  if (mode === 'hybrid') {
    return '双路融合';
  }
  if (mode === 'hybrid_ppr') {
    return '双路融合 + PPR';
  }
  return '未执行';
}

function format_latency(value: number): string {
  return `${value.toFixed(1)} ms`;
}

function resolve_answer_execution(message: ChatMessageRecord | null): AnswerExecutionRecord {
  if (message?.execution) {
    return message.execution;
  }
  return {
    status: 'idle',
    retrieval_mode: 'none',
    model_invoked: false,
    matched_paragraph_count: 0,
    message: '发送问题后，这里会显示当前回合的执行情况。',
  };
}

function result_summary(
  query_mode: QueryMode,
  active_answer_message: ChatMessageRecord | null,
  record_results: RecordSearchItemRecord[],
  entity_results: EntitySearchItemRecord[],
  relation_results: RelationSearchItemRecord[],
  source_results: SourceSearchItemRecord[],
  answer_sessions: ChatSessionRecord[],
): string {
  if (query_mode === 'answer') {
    if (!answer_sessions.length) {
      return '创建一个会话后，系统会在每轮问答中自动执行结构化检索、向量检索、融合重排和可选的 PPR 重排。';
    }
    if (!active_answer_message) {
      return '输入问题后，系统会把当前回合的回答、证据和检索轨迹记录到会话里。';
    }
    const execution = resolve_answer_execution(active_answer_message);
    if (execution.model_invoked) {
      return `系统已在当前会话中命中 ${execution.matched_paragraph_count} 条证据，并生成自然语言回答。`;
    }
    return execution.message;
  }
  if (query_mode === 'record') {
    return record_results.length ? `已找到 ${record_results.length} 条表格记录。` : '当前还没有表格记录结果。';
  }
  if (query_mode === 'entity') {
    return entity_results.length ? `已找到 ${entity_results.length} 个实体。` : '当前还没有实体结果。';
  }
  if (query_mode === 'relation') {
    return relation_results.length ? `已找到 ${relation_results.length} 条关系。` : '当前还没有关系结果。';
  }
  return source_results.length ? `已找到 ${source_results.length} 个来源。` : '当前还没有来源结果。';
}

function RetrievalLaneCard(props: { label: string; lane: RetrievalTraceLaneRecord | null | undefined }) {
  const { label, lane } = props;
  return (
    <div className='kb-inline-card kb-retrieval-lane'>
      <strong>{label}</strong>
      <span>{lane?.executed ? '已执行' : `跳过：${lane?.skipped_reason ?? '未执行'}`}</span>
      <span>{`命中 ${lane?.hit_count ?? 0}`}</span>
      <span>{`耗时 ${format_latency(lane?.latency_ms ?? 0)}`}</span>
      <span>{`段落 ${lane?.top_paragraph_ids.slice(0, 3).join('、') || '无'}`}</span>
    </div>
  );
}

export function QueryStudioPanel() {
  const {
    query_mode,
    answer_sessions,
    active_answer_session_id,
    answer_messages,
    active_answer_message,
    record_results,
    entity_results,
    relation_results,
    source_results,
    is_querying,
    set_query_mode,
    execute_query,
    select_answer_session,
    create_answer_session,
    focus_entity,
    focus_relation,
    focus_source,
    focus_paragraph,
  } = use_query_studio();

  const [query_text, set_query_text] = useState<string>('');
  const mode_config = get_mode_config(query_mode);
  const answer_execution = resolve_answer_execution(active_answer_message);

  return (
    <section className='kb-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>问答与检索工作台</h2>
          <p>问答模式已经完全切到会话流，系统会在每一轮内部完成双路检索、融合重排和可选的 PPR 增强，再生成回答。</p>
        </div>
      </header>

      <div className='kb-query-layout'>
        <div className='kb-detail-card kb-query-composer'>
          <label className='kb-form-field'>
            <span>检索模式</span>
            <select
              aria-label='选择检索模式'
              onChange={(event) => set_query_mode(event.target.value as QueryMode)}
              value={query_mode}
            >
              {QUERY_MODE_OPTIONS.map((mode) => (
                <option key={mode.id} value={mode.id}>
                  {mode.label}
                </option>
              ))}
            </select>
          </label>

          <div className='kb-query-hero'>
            <h3>{mode_config.label}</h3>
            <p>{mode_config.description}</p>
          </div>

          {query_mode === 'answer' ? (
            <div className='kb-detail-card kb-chat-session-panel'>
              <div className='kb-section-header'>
                <div>
                  <h3>问答会话</h3>
                  <p>切换不同会话时，会恢复对应的消息流、证据和图谱高亮。</p>
                </div>
                <button className='kb-secondary-button' onClick={() => void create_answer_session()} type='button'>
                  新建会话
                </button>
              </div>

              <div className='kb-chat-session-list'>
                {answer_sessions.map((session) => (
                  <button
                    className={`kb-chat-session-card ${active_answer_session_id === session.id ? 'is-active' : ''}`}
                    key={session.id}
                    onClick={() => void select_answer_session(session.id)}
                    type='button'
                  >
                    <strong>{session.title}</strong>
                    <span>{session.last_message_at ?? session.created_at}</span>
                  </button>
                ))}
                {!answer_sessions.length ? <div className='kb-empty-card'>还没有问答会话。</div> : null}
              </div>
            </div>
          ) : null}

          <label className='kb-form-field'>
            <span>输入内容</span>
            <textarea
              onChange={(event) => set_query_text(event.target.value)}
              placeholder='请输入问题、实体名称、关系模式或者来源关键词'
              value={query_text}
            />
          </label>

          <div className='kb-example-row'>
            {mode_config.examples.map((example) => (
              <button className='kb-chip' key={example} onClick={() => set_query_text(example)} type='button'>
                {example}
              </button>
            ))}
          </div>

          <div className='kb-button-row'>
            <button
              className='kb-primary-button'
              disabled={is_querying || !query_text.trim()}
              onClick={() => void execute_query(query_text)}
              type='button'
            >
              {is_querying ? (query_mode === 'answer' ? '发送中...' : '检索中...') : query_mode === 'answer' ? '发送问题' : '开始检索'}
            </button>
          </div>

          <div className='kb-query-note'>
            <strong>使用说明</strong>
            <span>问答模式会把每一轮的自然语言回答、证据引用、检索轨迹和图谱高亮一起保存到当前会话。</span>
          </div>
        </div>

        <div className='kb-result-stack kb-query-results'>
          <div className='kb-detail-card kb-answer-panel'>
            <span className='kb-context-label'>当前结果模式</span>
            <strong>{mode_config.label}</strong>
            <p>{result_summary(query_mode, active_answer_message, record_results, entity_results, relation_results, source_results, answer_sessions)}</p>
          </div>

          {query_mode === 'answer' ? (
            <>
              <div className='kb-detail-card'>
                <span className='kb-context-label'>当前会话消息流</span>
                <h3>消息记录</h3>
                <div className='kb-answer-thread'>
                  {answer_messages.map((message) => (
                    <div className={`kb-chat-message ${message.role === 'user' ? 'is-user' : 'is-assistant'}`} key={message.id}>
                      <strong>{message.role === 'user' ? '用户' : '助手'}</strong>
                      <p>{message.content}</p>
                    </div>
                  ))}
                  {!answer_messages.length ? <div className='kb-empty-card'>当前会话还没有消息。</div> : null}
                </div>
              </div>

              <div className='kb-detail-card kb-answer-panel'>
                <span className='kb-context-label'>当前回合回答</span>
                <h3>自然语言回答</h3>
                <p>{active_answer_message?.content ?? '发送问题后，这里会显示当前会话最新一轮的自然语言回答。'}</p>
              </div>

              <div className='kb-detail-card kb-answer-panel'>
                <span className='kb-context-label'>系统执行情况</span>
                <h3>知识库检索与模型调用</h3>
                <div className='kb-meta-strip'>
                  <span className='kb-meta-pill'>{`状态：${get_answer_status_label(answer_execution.status)}`}</span>
                  <span className='kb-meta-pill'>{answer_execution.model_invoked ? '已调用模型' : '未调用模型'}</span>
                  <span className='kb-meta-pill'>{`检索方式：${get_retrieval_mode_label(answer_execution.retrieval_mode)}`}</span>
                  <span className='kb-meta-pill'>{`命中段落 ${answer_execution.matched_paragraph_count}`}</span>
                </div>
                <p>{answer_execution.message}</p>

                <div className='kb-result-grid kb-retrieval-trace-grid'>
                  <RetrievalLaneCard label='结构化检索' lane={active_answer_message?.retrieval_trace?.structured} />
                  <RetrievalLaneCard label='向量检索' lane={active_answer_message?.retrieval_trace?.vector} />
                  <RetrievalLaneCard label='融合重排' lane={active_answer_message?.retrieval_trace?.fusion} />
                  <RetrievalLaneCard label='PPR 重排' lane={active_answer_message?.retrieval_trace?.ppr} />
                </div>
                <span className='kb-helper-text'>{`总耗时 ${format_latency(active_answer_message?.retrieval_trace?.total_ms ?? 0)}`}</span>
              </div>

              <div className='kb-detail-card'>
                <span className='kb-context-label'>当前回合证据</span>
                <h3>证据引用</h3>
                <div className='kb-result-stack'>
                  {active_answer_message?.citations.map((citation) => (
                    <div className='kb-inline-card' key={citation.paragraph_id}>
                      <strong>{citation.source_name}</strong>
                      <ParagraphEvidencePreview
                        render_kind={citation.render_kind}
                        rendered_html={citation.rendered_html}
                        text_content={citation.excerpt}
                      />
                      <span>{`得分 ${citation.score.toFixed(2)}`}</span>
                      <button className='kb-secondary-button' onClick={() => focus_paragraph(citation.paragraph_id)} type='button'>
                        查看段落
                      </button>
                    </div>
                  ))}
                  {!active_answer_message?.citations.length ? (
                    <div className='kb-empty-card'>
                      {answer_execution.model_invoked ? '本次回答没有返回可展示的引用。' : '本次没有命中可用证据，因此没有调用模型。'}
                    </div>
                  ) : null}
                </div>
              </div>
            </>
          ) : null}

          {query_mode === 'record' ? (
            <div className='kb-result-grid'>
              {record_results.map((item) => (
                <div className='kb-inline-card' key={item.paragraph_id}>
                  <strong>{`${item.source_name} / ${item.worksheet_name || '工作表'}`}</strong>
                  <span>{`行号 ${item.row_index ?? '-'}`}</span>
                  <span>{item.content}</span>
                  <span>{`得分 ${item.score.toFixed(2)}${item.matched_cells.length ? ` | 命中单元格 ${item.matched_cells.join(', ')}` : ''}`}</span>
                  <button className='kb-secondary-button' onClick={() => focus_paragraph(item.paragraph_id)} type='button'>
                    查看行记录
                  </button>
                </div>
              ))}
              {!record_results.length ? <div className='kb-empty-card'>暂无表格记录结果。</div> : null}
            </div>
          ) : null}

          {query_mode === 'entity' ? (
            <div className='kb-result-grid'>
              {entity_results.map((item) => (
                <div className='kb-inline-card' key={item.id}>
                  <strong>{item.display_name}</strong>
                  <span>{item.description || '暂无描述'}</span>
                  <span>{`出现次数 ${item.appearance_count}`}</span>
                  <button className='kb-secondary-button' onClick={() => focus_entity(item.id)} type='button'>
                    定位实体
                  </button>
                </div>
              ))}
              {!entity_results.length ? <div className='kb-empty-card'>暂无实体结果。</div> : null}
            </div>
          ) : null}

          {query_mode === 'relation' ? (
            <div className='kb-result-grid'>
              {relation_results.map((item) => (
                <div className='kb-inline-card' key={item.id}>
                  <strong>{`${item.subject_name} -> ${item.predicate} -> ${item.object_name}`}</strong>
                  <span>{`置信度 ${item.confidence.toFixed(2)}`}</span>
                  <button className='kb-secondary-button' onClick={() => focus_relation(item.id)} type='button'>
                    定位关系
                  </button>
                </div>
              ))}
              {!relation_results.length ? <div className='kb-empty-card'>暂无关系结果。</div> : null}
            </div>
          ) : null}

          {query_mode === 'source' ? (
            <div className='kb-result-grid'>
              {source_results.map((item) => (
                <div className='kb-inline-card' key={item.id}>
                  <strong>{item.name}</strong>
                  <span>{item.summary || '暂无摘要'}</span>
                  <span>{`段落数 ${item.paragraph_count}`}</span>
                  <button className='kb-secondary-button' onClick={() => focus_source(item.id)} type='button'>
                    打开来源
                  </button>
                </div>
              ))}
              {!source_results.length ? <div className='kb-empty-card'>暂无来源结果。</div> : null}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
