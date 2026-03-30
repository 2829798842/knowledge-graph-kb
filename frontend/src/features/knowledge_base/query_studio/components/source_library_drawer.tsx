import { useDeferredValue, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

import { ParagraphEvidencePreview } from '../../shared/components/paragraph_evidence_preview';
import { get_input_mode_label, get_status_label, get_strategy_label, get_vector_state_label } from '../../shared/config/ui_constants';
import type { ParagraphRecord, SourceDetailRecord, SourceRecord } from '../../shared/types/knowledge_base_types';

function source_summary(source: SourceRecord): string {
  return source.summary || get_input_mode_label(source.source_kind) || '暂无摘要';
}

function is_source_in_scope(source_id: string, selected_source_ids: string[]): boolean {
  return !selected_source_ids.length || selected_source_ids.includes(source_id);
}

interface SourceLibraryDrawerProps {
  open: boolean;
  sources: SourceRecord[];
  selected_source_ids: string[];
  set_selected_source_ids: Dispatch<SetStateAction<string[]>>;
  selected_source_browser_id: string | null;
  set_selected_source_browser_id: Dispatch<SetStateAction<string | null>>;
  source_detail: SourceDetailRecord | null;
  source_paragraphs: ParagraphRecord[];
  is_updating_source: boolean;
  is_deleting_source: boolean;
  update_source: (source_id: string, payload: { name?: string; summary?: string; metadata?: Record<string, unknown> }) => Promise<void>;
  delete_source: (source_id: string) => Promise<void>;
  on_close: () => void;
  on_focus_paragraph: (paragraph_id: string) => void;
}

export function SourceLibraryDrawer(props: SourceLibraryDrawerProps) {
  const {
    open,
    sources,
    selected_source_ids,
    set_selected_source_ids,
    selected_source_browser_id,
    set_selected_source_browser_id,
    source_detail,
    source_paragraphs,
    is_updating_source,
    is_deleting_source,
    update_source,
    delete_source,
    on_close,
    on_focus_paragraph,
  } = props;

  const [source_keyword, set_source_keyword] = useState('');
  const [paragraph_keyword, set_paragraph_keyword] = useState('');
  const [name_draft, set_name_draft] = useState('');
  const [summary_draft, set_summary_draft] = useState('');
  const deferred_source_keyword = useDeferredValue(source_keyword.trim().toLowerCase());
  const deferred_paragraph_keyword = useDeferredValue(paragraph_keyword.trim().toLowerCase());
  const paragraph_scroll_ref = useRef<HTMLDivElement | null>(null);

  const filtered_sources = useMemo(
    () =>
      sources.filter((source) => {
        if (!deferred_source_keyword) {
          return true;
        }
        const haystack = `${source.name} ${source.summary ?? ''} ${source.source_kind} ${source.input_mode}`.toLowerCase();
        return haystack.includes(deferred_source_keyword);
      }),
    [deferred_source_keyword, sources],
  );

  const filtered_paragraphs = useMemo(
    () =>
      source_paragraphs.filter((paragraph) => {
        if (!deferred_paragraph_keyword) {
          return true;
        }
        return paragraph.content.toLowerCase().includes(deferred_paragraph_keyword);
      }),
    [deferred_paragraph_keyword, source_paragraphs],
  );

  const paragraph_virtualizer = useVirtualizer({
    count: filtered_paragraphs.length,
    getScrollElement: () => paragraph_scroll_ref.current,
    estimateSize: () => 200,
    overscan: 4,
    measureElement: (element) => element?.getBoundingClientRect().height ?? 0,
  });

  const active_source = source_detail?.source ?? sources.find((source) => source.id === selected_source_browser_id) ?? null;

  useEffect(() => {
    set_name_draft(active_source?.name ?? '');
    set_summary_draft(active_source?.summary ?? '');
  }, [active_source]);

  if (!open) {
    return null;
  }

  return (
    <div className='kb-modal-backdrop' onClick={on_close} role='presentation'>
      <aside aria-modal='true' className='kb-side-drawer' onClick={(event) => event.stopPropagation()} role='dialog'>
        <div className='kb-side-drawer-header'>
          <div>
            <span className='kb-context-label'>Sources</span>
            <h3>来源库</h3>
            <p>在这里切换来源范围、查看单个来源详情，并完成重命名与删除。</p>
          </div>
          <button className='kb-secondary-button' onClick={on_close} type='button'>
            关闭
          </button>
        </div>

        <div className='kb-side-drawer-actions'>
          <button className='kb-secondary-button' onClick={() => set_selected_source_ids([])} type='button'>
            全部来源
          </button>
          {active_source ? (
            <button className='kb-secondary-button' onClick={() => set_selected_source_ids([active_source.id])} type='button'>
              仅当前来源
            </button>
          ) : null}
        </div>

        <div className='kb-source-library-layout'>
          <section className='kb-source-library-list'>
            <label className='kb-form-field'>
              <span>筛选来源</span>
              <input onChange={(event) => set_source_keyword(event.target.value)} placeholder='按名称、摘要或类型搜索' type='search' value={source_keyword} />
            </label>

            <div className='kb-source-library-results'>
              {filtered_sources.map((source) => {
                const in_scope = is_source_in_scope(source.id, selected_source_ids);
                return (
                  <article className={`kb-source-library-card ${selected_source_browser_id === source.id ? 'is-active' : ''}`} key={source.id}>
                    <button className='kb-source-library-hit' onClick={() => set_selected_source_browser_id(source.id)} type='button'>
                      <strong>{source.name}</strong>
                      <span>{source_summary(source)}</span>
                    </button>

                    <div className='kb-meta-strip'>
                      <span className='kb-meta-pill'>{get_input_mode_label(source.input_mode)}</span>
                      <span className='kb-meta-pill'>{get_status_label(source.status)}</span>
                      <span className='kb-meta-pill'>{get_strategy_label(source.strategy)}</span>
                    </div>

                    <button
                      className='kb-secondary-button'
                      onClick={() => {
                        if (!selected_source_ids.length) {
                          set_selected_source_ids([source.id]);
                          return;
                        }
                        if (selected_source_ids.includes(source.id)) {
                          set_selected_source_ids(selected_source_ids.filter((item) => item !== source.id));
                          return;
                        }
                        set_selected_source_ids([...selected_source_ids, source.id]);
                      }}
                      type='button'
                    >
                      {selected_source_ids.length ? (in_scope ? '移出范围' : '加入范围') : '仅此来源'}
                    </button>
                  </article>
                );
              })}
              {!filtered_sources.length ? <div className='kb-empty-card'>没有匹配的来源。</div> : null}
            </div>
          </section>

          <section className='kb-source-library-preview'>
            <div className='kb-detail-card'>
              <span className='kb-context-label'>Preview</span>
              <h3>{active_source?.name ?? '选择一个来源'}</h3>
              <p>{active_source ? source_summary(active_source) : '选中来源后，这里会显示摘要、统计和段落内容。'}</p>
              {source_detail ? (
                <div className='kb-meta-strip'>
                  <span className='kb-meta-pill'>{`段落 ${source_detail.paragraph_count}`}</span>
                  <span className='kb-meta-pill'>{`实体 ${source_detail.entity_count}`}</span>
                  <span className='kb-meta-pill'>{`关系 ${source_detail.relation_count}`}</span>
                </div>
              ) : null}

              {active_source ? (
                <>
                  <label className='kb-form-field'>
                    <span>来源名称</span>
                    <input onChange={(event) => set_name_draft(event.target.value)} type='text' value={name_draft} />
                  </label>

                  <label className='kb-form-field'>
                    <span>摘要</span>
                    <textarea onChange={(event) => set_summary_draft(event.target.value)} rows={3} value={summary_draft} />
                  </label>

                  <div className='kb-button-row'>
                    <button
                      className='kb-primary-button'
                      disabled={is_updating_source || !name_draft.trim()}
                      onClick={() => void update_source(active_source.id, { name: name_draft.trim(), summary: summary_draft.trim() || undefined })}
                      type='button'
                    >
                      {is_updating_source ? '保存中...' : '保存来源'}
                    </button>
                    <button className='kb-secondary-button' disabled={is_deleting_source} onClick={() => void delete_source(active_source.id)} type='button'>
                      {is_deleting_source ? '删除中...' : '删除来源'}
                    </button>
                  </div>
                </>
              ) : null}
            </div>

            <label className='kb-form-field'>
              <span>筛选段落</span>
              <input onChange={(event) => set_paragraph_keyword(event.target.value)} placeholder='按段落内容搜索' type='search' value={paragraph_keyword} />
            </label>

            <div className='kb-source-library-paragraphs' ref={paragraph_scroll_ref}>
              {filtered_paragraphs.length ? (
                <div className='kb-virtual-list-spacer' style={{ height: `${paragraph_virtualizer.getTotalSize()}px`, position: 'relative' }}>
                  {paragraph_virtualizer.getVirtualItems().map((virtual_item) => {
                    const paragraph = filtered_paragraphs[virtual_item.index];
                    return (
                      <div
                        className='kb-virtual-list-item'
                        data-index={virtual_item.index}
                        key={paragraph.id}
                        ref={paragraph_virtualizer.measureElement}
                        style={{ left: 0, position: 'absolute', top: 0, transform: `translateY(${virtual_item.start}px)`, width: '100%' }}
                      >
                        <article className='kb-chat-source-card'>
                          <strong>{`#${paragraph.position + 1}`}</strong>
                          <ParagraphEvidencePreview render_kind={paragraph.render_kind} rendered_html={paragraph.rendered_html} text_content={paragraph.content} />
                          <div className='kb-meta-strip'>
                            <span className='kb-meta-pill'>{get_vector_state_label(paragraph.vector_state)}</span>
                            <span className='kb-meta-pill'>{`Token ${paragraph.token_count}`}</span>
                          </div>
                          <div className='kb-button-row'>
                            <button className='kb-secondary-button' onClick={() => on_focus_paragraph(paragraph.id)} type='button'>
                              在图谱中定位
                            </button>
                          </div>
                        </article>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className='kb-empty-card'>当前来源下没有匹配的段落。</div>
              )}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}
