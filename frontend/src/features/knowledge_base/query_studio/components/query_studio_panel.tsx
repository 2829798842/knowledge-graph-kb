/**
 * Query studio panel.
 */

import { useState } from 'react';

import { QUERY_MODE_OPTIONS } from '../../shared/config/ui_constants';
import type {
  AnswerQueryResult,
  EntitySearchItemRecord,
  QueryMode,
  RecordSearchItemRecord,
  RelationSearchItemRecord,
  SourceSearchItemRecord,
} from '../../shared/types/knowledge_base_types';
import { use_query_studio } from '../hooks/use_query_studio';
import '../styles/query_studio_panel.css';

function get_mode_config(query_mode: QueryMode) {
  return QUERY_MODE_OPTIONS.find((item) => item.id === query_mode) ?? QUERY_MODE_OPTIONS[0];
}

function result_summary(
  query_mode: QueryMode,
  answer_result: AnswerQueryResult | null,
  record_results: RecordSearchItemRecord[],
  entity_results: EntitySearchItemRecord[],
  relation_results: RelationSearchItemRecord[],
  source_results: SourceSearchItemRecord[],
): string {
  if (query_mode === 'answer') {
    return answer_result?.citations.length
      ? `本次回答引用了 ${answer_result.citations.length} 条证据。`
      : '执行问答后，这里会显示答案和引用情况。';
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

export function QueryStudioPanel() {
  const {
    query_mode,
    answer_result,
    record_results,
    entity_results,
    relation_results,
    source_results,
    is_querying,
    set_query_mode,
    execute_query,
    focus_entity,
    focus_relation,
    focus_source,
    focus_paragraph,
  } = use_query_studio();

  const [query_text, set_query_text] = useState<string>('');
  const mode_config = get_mode_config(query_mode);

  return (
    <section className='kb-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>检索工作台</h2>
          <p>在当前图谱和来源内容上执行问答、实体、关系、来源与表格记录检索。</p>
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
              {is_querying ? '检索中...' : '开始检索'}
            </button>
          </div>

          <div className='kb-query-note'>
            <strong>使用说明</strong>
            <span>模式切换后结果会同步到图谱或来源视图，便于继续定位和查看上下文。</span>
          </div>
        </div>

        <div className='kb-result-stack kb-query-results'>
          <div className='kb-detail-card kb-answer-panel'>
            <span className='kb-context-label'>当前结果模式</span>
            <strong>{mode_config.label}</strong>
            <p>{result_summary(query_mode, answer_result, record_results, entity_results, relation_results, source_results)}</p>
          </div>

          {query_mode === 'answer' ? (
            <>
              <div className='kb-detail-card kb-answer-panel'>
                <h3>回答</h3>
                <p>{answer_result?.answer ?? '执行检索后，这里会显示生成答案。'}</p>
              </div>

              <div className='kb-detail-card'>
                <h3>证据引用</h3>
                <div className='kb-result-stack'>
                  {answer_result?.citations.map((citation) => (
                    <div className='kb-inline-card' key={citation.paragraph_id}>
                      <strong>{citation.source_name}</strong>
                      <span>{citation.excerpt}</span>
                      <span>{`得分 ${citation.score.toFixed(2)}`}</span>
                      <button className='kb-secondary-button' onClick={() => focus_paragraph(citation.paragraph_id)} type='button'>
                        查看段落
                      </button>
                    </div>
                  ))}
                  {!answer_result?.citations.length ? <div className='kb-empty-card'>暂无可显示的引用。</div> : null}
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
