import { useEffect, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

import { ParagraphEvidencePreview } from '../../shared/components/paragraph_evidence_preview';
import type { AnswerCitationRecord } from '../../shared/types/knowledge_base_types';

const SOURCE_PAGE_SIZE = 5;

function read_metadata_text(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function resolve_source_meta(citation: AnswerCitationRecord): string[] {
  const metadata = citation.render_metadata ?? {};
  const file_name = read_metadata_text(metadata.filename) ?? read_metadata_text(metadata.file_name) ?? read_metadata_text(metadata.title);
  const page_number = read_metadata_text(metadata.page_number) ?? read_metadata_text(metadata.page);
  const sheet_name = read_metadata_text(metadata.worksheet_name) ?? read_metadata_text(metadata.sheet_name);

  return [
    file_name ? `文件：${file_name}` : null,
    page_number ? `页码：${page_number}` : null,
    sheet_name ? `工作表：${sheet_name}` : null,
  ].filter((item): item is string => Boolean(item));
}

interface ChatSourcesSectionProps {
  citations: AnswerCitationRecord[];
  on_focus_paragraph: (paragraph_id: string) => void;
  on_open_source: (source_id: string) => void;
}

export function ChatSourcesSection(props: ChatSourcesSectionProps) {
  const { citations, on_focus_paragraph, on_open_source } = props;
  const [is_open, set_is_open] = useState(false);
  const [page, set_page] = useState(1);
  const scroll_ref = useRef<HTMLDivElement | null>(null);
  const total_pages = Math.max(1, Math.ceil(citations.length / SOURCE_PAGE_SIZE));
  const page_items = useMemo(() => citations.slice((page - 1) * SOURCE_PAGE_SIZE, page * SOURCE_PAGE_SIZE), [citations, page]);

  useEffect(() => {
    if (page > total_pages) {
      set_page(total_pages);
    }
  }, [page, total_pages]);

  useEffect(() => {
    if (is_open) {
      scroll_ref.current?.scrollTo({ top: 0 });
    }
  }, [is_open, page]);

  const virtualizer = useVirtualizer({
    count: page_items.length,
    getScrollElement: () => scroll_ref.current,
    estimateSize: () => 180,
    overscan: 3,
    measureElement: (element) => element?.getBoundingClientRect().height ?? 0,
  });

  return (
    <div className='kb-chat-sources'>
      <button className='kb-chat-sources-toggle' onClick={() => set_is_open((value) => !value)} type='button'>
        <strong>{is_open ? '隐藏来源' : '显示来源'}</strong>
        <span>{`${citations.length} 条匹配`}</span>
      </button>

      {is_open ? (
        <div className='kb-chat-sources-body'>
          {page_items.length ? (
            <div className='kb-chat-sources-scroll' ref={scroll_ref}>
              <div className='kb-virtual-list-spacer' style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
                {virtualizer.getVirtualItems().map((virtual_item) => {
                  const citation = page_items[virtual_item.index];
                  const meta_lines = resolve_source_meta(citation);

                  return (
                    <div
                      className='kb-virtual-list-item'
                      data-index={virtual_item.index}
                      key={`${citation.paragraph_id}-${citation.source_id}-${virtual_item.index}`}
                      ref={virtualizer.measureElement}
                      style={{ left: 0, position: 'absolute', top: 0, transform: `translateY(${virtual_item.start}px)`, width: '100%' }}
                    >
                      <article className='kb-chat-source-card'>
                        <div className='kb-chat-source-head'>
                          <button className='kb-link-button' onClick={() => on_open_source(citation.source_id)} type='button'>
                            {citation.source_name}
                          </button>
                          <span>{`相关度 ${citation.score.toFixed(2)}`}</span>
                        </div>

                        <ParagraphEvidencePreview render_kind={citation.render_kind} rendered_html={citation.rendered_html} text_content={citation.excerpt} />

                        {meta_lines.length ? <div className='kb-chat-source-meta'>{meta_lines.map((line) => <span key={line}>{line}</span>)}</div> : null}

                        <div className='kb-button-row'>
                          <button className='kb-secondary-button' onClick={() => on_focus_paragraph(citation.paragraph_id)} type='button'>
                            定位段落
                          </button>
                        </div>
                      </article>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className='kb-empty-card'>当前回答没有可展开的来源。</div>
          )}

          {total_pages > 1 ? (
            <div className='kb-chat-sources-pagination'>
              <button className='kb-secondary-button' disabled={page <= 1} onClick={() => set_page((value) => value - 1)} type='button'>
                上一页
              </button>
              <span>{`第 ${page} / ${total_pages} 页`}</span>
              <button className='kb-secondary-button' disabled={page >= total_pages} onClick={() => set_page((value) => value + 1)} type='button'>
                下一页
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
