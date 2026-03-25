/**
 * 来源浏览面板。
 */

import { useDeferredValue, useEffect, useState } from 'react';

import {
  get_input_mode_label,
  get_knowledge_type_label,
  get_status_label,
  get_strategy_label,
  get_vector_state_label,
} from '../../shared/config/ui_constants';
import type { ParagraphRecord, SourceRecord } from '../../shared/types/knowledge_base_types';
import { use_source_browser } from '../hooks/use_source_browser';
import '../styles/source_browser_panel.css';

function source_summary(source: SourceRecord): string {
  return source.summary || get_input_mode_label(source.source_kind) || '暂无摘要';
}

export function SourceBrowserPanel() {
  const {
    sources,
    selected_source_browser_id,
    source_detail,
    source_paragraphs,
    set_selected_source_browser_id,
    focus_paragraph,
  } = use_source_browser();

  const [source_keyword, set_source_keyword] = useState<string>('');
  const [paragraph_keyword, set_paragraph_keyword] = useState<string>('');
  const deferred_source_keyword: string = useDeferredValue(source_keyword.trim().toLowerCase());
  const deferred_paragraph_keyword: string = useDeferredValue(paragraph_keyword.trim().toLowerCase());

  useEffect(() => {
    if (!selected_source_browser_id && sources.length) {
      set_selected_source_browser_id(sources[0].id);
    }
  }, [selected_source_browser_id, set_selected_source_browser_id, sources]);

  const filtered_sources: SourceRecord[] = sources.filter((source) => {
    if (!deferred_source_keyword) {
      return true;
    }
    const haystack: string = `${source.name} ${source.summary ?? ''} ${source.source_kind} ${source.input_mode}`.toLowerCase();
    return haystack.includes(deferred_source_keyword);
  });

  const filtered_paragraphs: ParagraphRecord[] = source_paragraphs.filter((paragraph) => {
    if (!deferred_paragraph_keyword) {
      return true;
    }
    return paragraph.content.toLowerCase().includes(deferred_paragraph_keyword);
  });

  return (
    <section className='kb-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>来源浏览</h2>
          <p>从图谱反查原始来源、元数据和段落证据。</p>
        </div>
      </header>

      <div className='kb-panel-split kb-panel-split-source'>
        <aside className='kb-sidebar kb-source-sidebar'>
          <div className='kb-filter-card'>
            <h3>来源目录</h3>
            <p>{`${filtered_sources.length} 个来源符合当前筛选。`}</p>
            <label className='kb-form-field'>
              <span>来源关键词</span>
              <input
                onChange={(event) => set_source_keyword(event.target.value)}
                placeholder='按名称、摘要、类型或导入方式搜索'
                type='search'
                value={source_keyword}
              />
            </label>
          </div>

          <div className='kb-source-list'>
            {filtered_sources.map((source) => (
              <button
                className={`kb-source-card ${selected_source_browser_id === source.id ? 'is-active' : ''}`}
                key={source.id}
                onClick={() => set_selected_source_browser_id(source.id)}
                type='button'
              >
                <strong>{source.name}</strong>
                <span>{source_summary(source)}</span>
                <div className='kb-meta-strip'>
                  <span className='kb-meta-pill'>{get_input_mode_label(source.input_mode)}</span>
                  <span className='kb-meta-pill'>{get_status_label(source.status)}</span>
                  <span className='kb-meta-pill'>{get_strategy_label(source.strategy)}</span>
                </div>
              </button>
            ))}
            {!filtered_sources.length ? <div className='kb-empty-card'>没有匹配的来源。</div> : null}
          </div>
        </aside>

        <div className='kb-detail-panel kb-source-detail'>
          <div className='kb-detail-card kb-source-profile'>
            <h3>来源概览</h3>
            {source_detail ? (
              <>
                <strong>{source_detail.source.name}</strong>
                <div className='kb-meta-strip'>
                  <span className='kb-meta-pill'>{`段落 ${source_detail.paragraph_count}`}</span>
                  <span className='kb-meta-pill'>{`实体 ${source_detail.entity_count}`}</span>
                  <span className='kb-meta-pill'>{`关系 ${source_detail.relation_count}`}</span>
                  <span className='kb-meta-pill'>{get_strategy_label(source_detail.source.strategy)}</span>
                </div>
                <p>{source_detail.source.summary || '该来源暂时没有摘要。'}</p>
                <pre>{JSON.stringify(source_detail.source.metadata, null, 2)}</pre>
              </>
            ) : (
              <span>选择一个来源以查看元数据和段落统计。</span>
            )}
          </div>

          <div className='kb-detail-card'>
            <div className='kb-section-header'>
              <div>
                <h3>段落阅读</h3>
                <p>在当前来源内搜索段落，并回到图谱上下文继续查看。</p>
              </div>
            </div>

            <label className='kb-form-field'>
              <span>段落关键词</span>
              <input
                onChange={(event) => set_paragraph_keyword(event.target.value)}
                placeholder='在当前来源中筛选段落内容'
                type='search'
                value={paragraph_keyword}
              />
            </label>

            <div className='kb-paragraph-list'>
              {filtered_paragraphs.map((paragraph) => (
                <div className='kb-inline-card' key={paragraph.id}>
                  <strong>{`#${paragraph.position + 1}`}</strong>
                  <span>{paragraph.content}</span>
                  <div className='kb-meta-strip'>
                    <span className='kb-meta-pill'>{get_knowledge_type_label(paragraph.knowledge_type)}</span>
                    <span className='kb-meta-pill'>{`词元 ${paragraph.token_count}`}</span>
                    <span className='kb-meta-pill'>{get_vector_state_label(paragraph.vector_state)}</span>
                  </div>
                  <button className='kb-secondary-button' onClick={() => focus_paragraph(paragraph.id)} type='button'>
                    在图谱中定位
                  </button>
                </div>
              ))}
              {!filtered_paragraphs.length ? <span>当前来源下没有匹配段落。</span> : null}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
