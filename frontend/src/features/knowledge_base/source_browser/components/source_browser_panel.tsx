/**
 * Source-browser panel.
 */

import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

import { ParagraphEvidencePreview } from '../../shared/components/paragraph_evidence_preview';
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
  const deferred_source_keyword = useDeferredValue(source_keyword.trim().toLowerCase());
  const deferred_paragraph_keyword = useDeferredValue(paragraph_keyword.trim().toLowerCase());
  const paragraph_scroll_ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!selected_source_browser_id && sources.length) {
      set_selected_source_browser_id(sources[0].id);
    }
  }, [selected_source_browser_id, set_selected_source_browser_id, sources]);

  const filtered_sources: SourceRecord[] = sources.filter((source) => {
    if (!deferred_source_keyword) {
      return true;
    }
    const haystack = `${source.name} ${source.summary ?? ''} ${source.source_kind} ${source.input_mode}`.toLowerCase();
    return haystack.includes(deferred_source_keyword);
  });

  const filtered_paragraphs: ParagraphRecord[] = source_paragraphs.filter((paragraph) => {
    if (!deferred_paragraph_keyword) {
      return true;
    }
    return paragraph.content.toLowerCase().includes(deferred_paragraph_keyword);
  });

  const paragraph_virtualizer = useVirtualizer({
    count: filtered_paragraphs.length,
    getScrollElement: () => paragraph_scroll_ref.current,
    estimateSize: () => 260,
    overscan: 6,
    measureElement: (element) => element?.getBoundingClientRect().height ?? 0,
  });

  const active_source = source_detail?.source ?? sources.find((source) => source.id === selected_source_browser_id) ?? null;
  const active_source_summary = active_source ? source_summary(active_source) : '选择一个来源后，这里会显示摘要和元数据。';
  const metadata_text =
    source_detail && Object.keys(source_detail.source.metadata).length
      ? JSON.stringify(source_detail.source.metadata, null, 2)
      : null;

  return (
    <section className='kb-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>来源浏览</h2>
          <p>把来源目录和阅读区拆开，左侧负责选来源，右侧只负责看内容和回到图谱。</p>
        </div>
      </header>

      <div className='kb-source-shell'>
        <aside className='kb-source-rail'>
          <div className='kb-detail-card'>
            <span className='kb-context-label'>Catalog</span>
            <h3>来源目录</h3>
            <label className='kb-form-field'>
              <span>来源关键词</span>
              <input
                onChange={(event) => set_source_keyword(event.target.value)}
                placeholder='按名称、摘要、类型或导入方式搜索'
                type='search'
                value={source_keyword}
              />
            </label>

            <div className='kb-meta-strip'>
              <span className='kb-meta-pill'>{`总数 ${sources.length}`}</span>
              <span className='kb-meta-pill'>{`匹配 ${filtered_sources.length}`}</span>
            </div>
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

        <div className='kb-source-main'>
          <div className='kb-detail-card kb-source-stage'>
            <div className='kb-source-hero'>
              <span className='kb-context-label'>Selected Source</span>
              <h3>{active_source?.name ?? '选择一个来源'}</h3>
              <p>{active_source_summary}</p>
              {source_detail ? (
                <div className='kb-meta-strip'>
                  <span className='kb-meta-pill'>{`段落 ${source_detail.paragraph_count}`}</span>
                  <span className='kb-meta-pill'>{`实体 ${source_detail.entity_count}`}</span>
                  <span className='kb-meta-pill'>{`关系 ${source_detail.relation_count}`}</span>
                  <span className='kb-meta-pill'>{get_strategy_label(source_detail.source.strategy)}</span>
                  <span className='kb-meta-pill'>{get_status_label(source_detail.source.status)}</span>
                </div>
              ) : null}
            </div>

            {metadata_text ? <pre>{metadata_text}</pre> : <span className='kb-helper-text'>当前来源没有额外元数据可展示。</span>}
          </div>

          <div className='kb-detail-card kb-source-reading'>
            <div className='kb-section-header'>
              <div>
                <span className='kb-context-label'>Reading</span>
                <h3>段落阅读</h3>
                <p>只在当前来源内检索段落，命中后可以一键回到图谱中的对应位置。</p>
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

            <div className='kb-meta-strip'>
              <span className='kb-meta-pill'>{`命中段落 ${filtered_paragraphs.length}`}</span>
              <span className='kb-meta-pill'>{`当前来源 ${active_source?.name ?? '--'}`}</span>
            </div>

            <div className='kb-paragraph-list' ref={paragraph_scroll_ref}>
              {filtered_paragraphs.length ? (
                <div
                  className='kb-virtual-list-spacer'
                  style={{ height: `${paragraph_virtualizer.getTotalSize()}px`, position: 'relative' }}
                >
                  {paragraph_virtualizer.getVirtualItems().map((virtual_item) => {
                    const paragraph = filtered_paragraphs[virtual_item.index];
                    return (
                      <div
                        className='kb-virtual-list-item'
                        data-index={virtual_item.index}
                        key={paragraph.id}
                        ref={paragraph_virtualizer.measureElement}
                        style={{
                          left: 0,
                          position: 'absolute',
                          top: 0,
                          transform: `translateY(${virtual_item.start}px)`,
                          width: '100%',
                        }}
                      >
                        <div className='kb-inline-card'>
                          <strong>{`#${paragraph.position + 1}`}</strong>
                          <ParagraphEvidencePreview
                            render_kind={paragraph.render_kind}
                            rendered_html={paragraph.rendered_html}
                            text_content={paragraph.content}
                          />
                          <div className='kb-meta-strip'>
                            <span className='kb-meta-pill'>{get_knowledge_type_label(paragraph.knowledge_type)}</span>
                            <span className='kb-meta-pill'>{`词元 ${paragraph.token_count}`}</span>
                            <span className='kb-meta-pill'>{get_vector_state_label(paragraph.vector_state)}</span>
                          </div>
                          <button className='kb-secondary-button' onClick={() => focus_paragraph(paragraph.id)} type='button'>
                            在图谱中定位
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className='kb-empty-card'>当前来源下没有匹配的段落。</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
