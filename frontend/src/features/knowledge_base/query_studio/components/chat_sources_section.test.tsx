import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ChatSourcesSection } from './chat_sources_section';

describe('ChatSourcesSection', () => {
  it('renders localized source actions', async () => {
    const user = userEvent.setup();
    const focus_paragraph = vi.fn();
    const view_in_graph = vi.fn();

    render(
      <ChatSourcesSection
        citations={[
          {
            paragraph_id: 'paragraph-1',
            source_id: 'source-1',
            source_name: '孙子兵法.txt',
            excerpt: '火猫相关段落',
            score: 0.82,
            match_reason: '实体名称直接命中',
            matched_fields: [],
            source_kind: 'text',
            worksheet_name: null,
            page_number: 3,
            paragraph_position: 4,
            winning_lane: 'fusion',
            anchor_node_ids: ['entity:fire-cat'],
            preferred_anchor_node_id: 'entity:fire-cat',
            render_kind: 'text',
            rendered_html: null,
            render_metadata: {},
          },
        ]}
        on_focus_paragraph={focus_paragraph}
        on_view_in_graph={view_in_graph}
      />,
    );

    await user.click(screen.getByRole('button', { name: /显示来源/ }));

    expect(screen.getByText('匹配度 0.82')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '在图谱中查看' }));
    expect(view_in_graph).toHaveBeenCalledWith('source-1', 'paragraph-1', {
      preferred_anchor_node_id: 'entity:fire-cat',
      anchor_node_ids: ['entity:fire-cat'],
    });

    await user.click(screen.getByRole('button', { name: '定位段落' }));
    expect(focus_paragraph).toHaveBeenCalledWith('paragraph-1');
  });
});
