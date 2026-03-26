/**
 * Query studio panel.
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

function get_query_placeholder(query_mode: QueryMode): string {
  if (query_mode === 'answer') {
    return '输入你的问题，系统会自动完成检索、融合和回答。';
  }
  if (query_mode === 'record') {
    return '输入表格关键词、单号、客户名或行内关键信息。';
  }
  if (query_mode === 'entity') {
    return '输入实体名称、别名或描述关键词。';
  }
  if (query_mode === 'relation') {
    return '输入关系词，例如 依赖、负责、引用。';
  }
  return '输入来源名、摘要关键词或来源类型。';
}

function get_submit_label(query_mode: QueryMode, is_querying: boolean): string {
  if (is_querying) {
    return query_mode === 'answer' ? '发送中...' : '检索中...';
  }
  return query_mode === 'answer' ? '发送问题' : '开始检索';
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
    message: '发送问题后，这里会展示当前回合的检索与回答执行情况。',
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
      return '先创建一个会话，后续每轮问答的回答、引用和检索轨迹都会保存在这里。';
    }
    if (!active_answer_message) {
      return '输入问题后，系统会把当前回合的回答、证据和检索轨迹记录到会话里。';
    }
    const execution = resolve_answer_execution(active_answer_message);
    if (execution.model_invoked) {
      return `本轮命中 ${execution.matched_paragraph_count} 条证据，并已生成自然语言回答。`;
    }
    return execution.message;
  }
  if (query_mode === 'record') {
    return record_results.length ? `已找到 ${record_results.length} 条表格记录。` : '还没有表格记录结果。';
  }
  if (query_mode === 'entity') {
    return entity_results.length ? `已找到 ${entity_results.length} 个实体。` : '还没有实体结果。';
  }
  if (query_mode === 'relation') {
    return relation_results.length ? `已找到 ${relation_results.length} 条关系。` : '还没有关系结果。';
  }
  return source_results.length ? `已找到 ${source_results.length} 个来源。` : '还没有来源结果。';
}

function RetrievalLaneCard(props: { label: string; lane: RetrievalTraceLaneRecord | null | undefined }) {
  const { label, lane } = props;
  const paragraph_preview = lane?.top_paragraph_ids.slice(0, 3).join('、') || '无';

  return (
    <div className='kb-inline-card kb-retrieval-lane'>
      <strong>{label}</strong>
      <span>{lane?.executed ? '已执行' : `跳过：${lane?.skipped_reason ?? '未执行'}`}</span>
      <span>{`命中 ${lane?.hit_count ?? 0}`}</span>
      <span>{`耗时 ${format_latency(lane?.latency_ms ?? 0)}`}</span>
      <span>{`段落 ${paragraph_preview}`}</span>
    </div>
  );
}

function QueryResults(props: {
  query_mode: QueryMode;
  answer_messages: ChatMessageRecord[];
  active_answer_message: ChatMessageRecord | null;
  answer_execution: AnswerExecutionRecord;
  record_results: RecordSearchItemRecord[];
  entity_results: EntitySearchItemRecord[];
  relation_results: RelationSearchItemRecord[];
  source_results: SourceSearchItemRecord[];
  focus_entity: (entity_id: string) => void;
  focus_relation: (relation_id: string) => void;
  focus_source: (source_id: string) => void;
  focus_paragraph: (paragraph_id: string) => void;
}) {
  const {
    query_mode,
    answer_messages,
    active_answer_message,
    answer_execution,
    record_results,
    entity_results,
    relation_results,
    source_results,
    focus_entity,
    focus_relation,
    focus_source,
    focus_paragraph,
  } = props;

  if (query_mode === 'answer') {
    return (
      <>
        <div className='kb-detail-card kb-chat-thread-card'>
          <div className='kb-section-header'>
            <div>
              <span className='kb-context-label'>Conversation</span>
              <h3>消息记录</h3>
            </div>
          </div>

          <div className='kb-answer-thread'>
            {answer_messages.map((message) => (
              <div className={`kb-chat-message ${message.role === 'user' ? 'is-user' : 'is-assistant'}`} key={message.id}>
                <strong>{message.role === 'user' ? '你' : '助手'}</strong>
                <p>{message.content}</p>
              </div>
            ))}
            {!answer_messages.length ? <div className='kb-empty-card'>当前会话还没有消息，先发一个问题试试。</div> : null}
          </div>
        </div>

        <div className='kb-detail-card kb-query-results-section'>
          <div className='kb-section-header'>
            <div>
              <span className='kb-context-label'>Evidence</span>
              <h3>证据引用</h3>
            </div>
          </div>

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
                {answer_execution.model_invoked ? '本轮回答没有返回可展示的引用。' : '本轮没有命中可用证据，因此没有调用模型。'}
              </div>
            ) : null}
          </div>
        </div>
      </>
    );
  }

  if (query_mode === 'record') {
    return (
      <div className='kb-detail-card kb-query-results-section'>
        <div className='kb-section-header'>
          <div>
            <span className='kb-context-label'>Results</span>
            <h3>表格记录结果</h3>
          </div>
        </div>

        <div className='kb-result-grid'>
          {record_results.map((item) => (
            <div className='kb-inline-card' key={item.paragraph_id}>
              <strong>{`${item.source_name} / ${item.worksheet_name || '工作表'}`}</strong>
              <span>{`行号 ${item.row_index ?? '-'}`}</span>
              <span>{item.content}</span>
              <span>{`得分 ${item.score.toFixed(2)}${item.matched_cells.length ? ` ｜ 命中单元格 ${item.matched_cells.join(', ')}` : ''}`}</span>
              <button className='kb-secondary-button' onClick={() => focus_paragraph(item.paragraph_id)} type='button'>
                查看记录
              </button>
            </div>
          ))}
          {!record_results.length ? <div className='kb-empty-card'>暂时没有表格记录结果。</div> : null}
        </div>
      </div>
    );
  }

  if (query_mode === 'entity') {
    return (
      <div className='kb-detail-card kb-query-results-section'>
        <div className='kb-section-header'>
          <div>
            <span className='kb-context-label'>Results</span>
            <h3>实体结果</h3>
          </div>
        </div>

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
          {!entity_results.length ? <div className='kb-empty-card'>暂时没有实体结果。</div> : null}
        </div>
      </div>
    );
  }

  if (query_mode === 'relation') {
    return (
      <div className='kb-detail-card kb-query-results-section'>
        <div className='kb-section-header'>
          <div>
            <span className='kb-context-label'>Results</span>
            <h3>关系结果</h3>
          </div>
        </div>

        <div className='kb-result-grid'>
          {relation_results.map((item) => (
            <div className='kb-inline-card' key={item.id}>
              <strong>{`${item.subject_name} → ${item.predicate} → ${item.object_name}`}</strong>
              <span>{`置信度 ${item.confidence.toFixed(2)}`}</span>
              <button className='kb-secondary-button' onClick={() => focus_relation(item.id)} type='button'>
                定位关系
              </button>
            </div>
          ))}
          {!relation_results.length ? <div className='kb-empty-card'>暂时没有关系结果。</div> : null}
        </div>
      </div>
    );
  }

  return (
    <div className='kb-detail-card kb-query-results-section'>
      <div className='kb-section-header'>
        <div>
          <span className='kb-context-label'>Results</span>
          <h3>来源结果</h3>
        </div>
      </div>

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
        {!source_results.length ? <div className='kb-empty-card'>暂时没有来源结果。</div> : null}
      </div>
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
  const summary_text = result_summary(
    query_mode,
    active_answer_message,
    record_results,
    entity_results,
    relation_results,
    source_results,
    answer_sessions,
  );

  return (
    <section className='kb-panel kb-query-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>问答与检索工作台</h2>
          <p>把会话、检索输入和结果放到同一块主屏里，减少切换，让体验更接近 ChatGPT 的单任务工作区。</p>
        </div>
      </header>

      <div className='kb-query-shell'>
        <div className='kb-query-main'>
          <div className='kb-detail-card kb-chat-stage'>
            <div className='kb-query-stage-head'>
              <div className='kb-query-hero'>
                <span className='kb-context-label'>Active Mode</span>
                <h3>{mode_config.label}</h3>
                <p>{mode_config.description}</p>
              </div>

              {query_mode === 'answer' ? (
                <div className='kb-chat-session-strip'>
                  <button className='kb-primary-button' onClick={() => void create_answer_session()} type='button'>
                    新建会话
                  </button>
                  {answer_sessions.map((session) => (
                    <button
                      className={`kb-chat-session-pill ${active_answer_session_id === session.id ? 'is-active' : ''}`}
                      key={session.id}
                      onClick={() => void select_answer_session(session.id)}
                      type='button'
                    >
                      <strong>{session.title}</strong>
                      <span>{session.last_message_at ?? session.created_at}</span>
                    </button>
                  ))}
                  {!answer_sessions.length ? <div className='kb-empty-card'>还没有问答会话，先新建一个。</div> : null}
                </div>
              ) : null}
            </div>

            <QueryResults
              active_answer_message={active_answer_message}
              answer_execution={answer_execution}
              answer_messages={answer_messages}
              entity_results={entity_results}
              focus_entity={focus_entity}
              focus_paragraph={focus_paragraph}
              focus_relation={focus_relation}
              focus_source={focus_source}
              query_mode={query_mode}
              record_results={record_results}
              relation_results={relation_results}
              source_results={source_results}
            />

            <div className='kb-detail-card kb-chat-composer-card'>
              <label className='kb-form-field'>
                <span>输入内容</span>
                <textarea
                  onChange={(event) => set_query_text(event.target.value)}
                  placeholder={get_query_placeholder(query_mode)}
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

              <div className='kb-chat-composer-actions'>
                <span className='kb-helper-text'>{summary_text}</span>
                <button
                  className='kb-primary-button'
                  disabled={is_querying || !query_text.trim()}
                  onClick={() => void execute_query(query_text)}
                  type='button'
                >
                  {get_submit_label(query_mode, is_querying)}
                </button>
              </div>
            </div>
          </div>
        </div>

        <aside className='kb-query-rail'>
          <div className='kb-detail-card'>
            <span className='kb-context-label'>Search Controls</span>
            <h3>检索设置</h3>

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

            <div className='kb-query-note'>
              <strong>当前摘要</strong>
              <span>{summary_text}</span>
            </div>
          </div>

          {query_mode === 'answer' ? (
            <div className='kb-detail-card kb-answer-panel'>
              <span className='kb-context-label'>Execution Trace</span>
              <h3>回答执行情况</h3>
              <div className='kb-meta-strip'>
                <span className='kb-meta-pill'>{`状态：${get_answer_status_label(answer_execution.status)}`}</span>
                <span className='kb-meta-pill'>{answer_execution.model_invoked ? '已调用模型' : '未调用模型'}</span>
                <span className='kb-meta-pill'>{`检索方式：${get_retrieval_mode_label(answer_execution.retrieval_mode)}`}</span>
                <span className='kb-meta-pill'>{`命中段落 ${answer_execution.matched_paragraph_count}`}</span>
              </div>
              <p>{answer_execution.message}</p>

              <div className='kb-result-stack kb-retrieval-trace-stack'>
                <RetrievalLaneCard label='结构化检索' lane={active_answer_message?.retrieval_trace?.structured} />
                <RetrievalLaneCard label='向量检索' lane={active_answer_message?.retrieval_trace?.vector} />
                <RetrievalLaneCard label='融合重排' lane={active_answer_message?.retrieval_trace?.fusion} />
                <RetrievalLaneCard label='PPR 重排' lane={active_answer_message?.retrieval_trace?.ppr} />
              </div>

              <span className='kb-helper-text'>{`总耗时 ${format_latency(active_answer_message?.retrieval_trace?.total_ms ?? 0)}`}</span>
            </div>
          ) : (
            <div className='kb-detail-card'>
              <span className='kb-context-label'>Quick Start</span>
              <h3>使用建议</h3>
              <div className='kb-query-note'>
                <strong>{mode_config.label}</strong>
                <span>{mode_config.description}</span>
              </div>
              <div className='kb-result-stack'>
                {mode_config.examples.map((example) => (
                  <button className='kb-sidebar-link' key={example} onClick={() => set_query_text(example)} type='button'>
                    <strong>{example}</strong>
                    <span>点击后会把示例填入输入框</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
