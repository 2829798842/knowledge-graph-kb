import { useMemo, useState } from 'react';

import { ParagraphEvidencePreview } from '../../shared/components/paragraph_evidence_preview';
import type { AnswerCitationRecord } from '../../shared/types/knowledge_base_types';

interface ChatSourcesSectionProps {
  citations: AnswerCitationRecord[];
  on_view_in_graph: (
    source_id: string,
    paragraph_id: string,
    options?: {
      preferred_anchor_node_id?: string | null;
      anchor_node_ids?: string[];
    },
  ) => void;
  on_focus_paragraph: (paragraph_id: string) => void;
}

const PAGE_SIZE = 3;

function pagination_label(page: number, page_count: number): string {
  return `第 ${page} / ${page_count} 页`;
}

export function ChatSourcesSection(props: ChatSourcesSectionProps) {
  const { citations, on_view_in_graph, on_focus_paragraph } = props;
  const [open, set_open] = useState(false);
  const [page, set_page] = useState(1);

  const page_count = Math.max(1, Math.ceil(citations.length / PAGE_SIZE));
  const visible_citations = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return citations.slice(start, start + PAGE_SIZE);
  }, [citations, page]);

  if (!citations.length) {
    return null;
  }

  return (
    <section className='kb-chat-sources'>
      <button className='kb-chat-sources-toggle' onClick={() => set_open((current) => !current)} type='button'>
        <strong>{open ? '隐藏来源' : '显示来源'}</strong>
        <span>{`${citations.length} 条命中`}</span>
      </button>

      {open ? (
        <div className='kb-chat-sources-body'>
          <div className='kb-chat-sources-scroll'>
            {visible_citations.map((citation) => (
              <article className='kb-chat-source-card' key={`${citation.source_id}-${citation.paragraph_id}`}>
                <div className='kb-chat-source-head'>
                  <strong>{citation.source_name}</strong>
                  <span>{`匹配度 ${citation.score.toFixed(2)}`}</span>
                </div>

                <p className='kb-chat-source-reason'>
                  {citation.match_reason ?? '当前回答命中了这条来源证据。'}
                </p>

                <ParagraphEvidencePreview
                  render_kind={citation.render_kind}
                  rendered_html={citation.rendered_html}
                  text_content={citation.excerpt}
                />

                <div className='kb-chat-source-meta'>
                  {citation.source_kind ? <span>{`类型：${citation.source_kind}`}</span> : null}
                  {citation.worksheet_name ? <span>{`工作表：${citation.worksheet_name}`}</span> : null}
                  {citation.page_number !== null && citation.page_number !== undefined ? (
                    <span>{`页码：${citation.page_number}`}</span>
                  ) : null}
                  {citation.paragraph_position !== null && citation.paragraph_position !== undefined ? (
                    <span>{`段落：${citation.paragraph_position + 1}`}</span>
                  ) : null}
                </div>

                <div className='kb-button-row'>
                  <button
                    className='kb-secondary-button'
                    onClick={() =>
                      on_view_in_graph(citation.source_id, citation.paragraph_id, {
                        preferred_anchor_node_id: citation.preferred_anchor_node_id ?? null,
                        anchor_node_ids: citation.anchor_node_ids ?? [],
                      })
                    }
                    type='button'
                  >
                    在图谱中查看
                  </button>
                  <button
                    className='kb-secondary-button'
                    onClick={() => on_focus_paragraph(citation.paragraph_id)}
                    type='button'
                  >
                    定位段落
                  </button>
                </div>
              </article>
            ))}
          </div>

          {page_count > 1 ? (
            <div className='kb-chat-sources-pagination'>
              <button
                className='kb-secondary-button'
                disabled={page <= 1}
                onClick={() => set_page((current) => Math.max(1, current - 1))}
                type='button'
              >
                上一页
              </button>
              <span>{pagination_label(page, page_count)}</span>
              <button
                className='kb-secondary-button'
                disabled={page >= page_count}
                onClick={() => set_page((current) => Math.min(page_count, current + 1))}
                type='button'
              >
                下一页
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
