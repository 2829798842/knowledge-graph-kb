/**
 * 通用证据预览
 */

import './paragraph_evidence_preview.css';
import type { ParagraphRenderKind } from '../types/knowledge_base_types';

interface ParagraphEvidencePreviewProps {
  render_kind: ParagraphRenderKind;
  rendered_html: string | null;
  text_content: string;
}

export function ParagraphEvidencePreview(props: ParagraphEvidencePreviewProps) {
  const { render_kind, rendered_html, text_content } = props;
  const normalized_render_kind = render_kind || 'text';
  const normalized_text_content = text_content.trim();
  const has_html = Boolean(rendered_html);

  return (
    <div className={`kb-rendered-evidence kb-rendered-evidence--${normalized_render_kind}`}>
      {has_html ? (
        <div
          className='kb-rendered-evidence-html'
          dangerouslySetInnerHTML={{ __html: rendered_html ?? '' }}
        />
      ) : null}
      {normalized_text_content ? (
        <p className={`kb-rendered-evidence-text ${has_html ? 'is-secondary' : ''}`}>{normalized_text_content}</p>
      ) : null}
    </div>
  );
}
