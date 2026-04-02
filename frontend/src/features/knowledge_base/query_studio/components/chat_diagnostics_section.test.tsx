import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ChatDiagnosticsSection } from './chat_diagnostics_section';

describe('ChatDiagnosticsSection', () => {
  it('renders localized diagnostics copy', async () => {
    const user = userEvent.setup();

    render(
      <ChatDiagnosticsSection
        execution={{
          status: 'ready',
          retrieval_mode: 'hybrid',
          model_invoked: true,
          matched_paragraph_count: 3,
          message: '结构化检索与向量检索均已执行。',
        }}
        retrieval_trace={{
          structured: {
            executed: true,
            skipped_reason: null,
            hit_count: 1,
            latency_ms: 12,
            top_paragraph_ids: ['p1'],
          },
          vector: {
            executed: true,
            skipped_reason: null,
            hit_count: 2,
            latency_ms: 18,
            top_paragraph_ids: ['p2'],
          },
          fusion: {
            executed: true,
            skipped_reason: null,
            hit_count: 2,
            latency_ms: 6,
            top_paragraph_ids: ['p1'],
          },
          ppr: {
            executed: false,
            skipped_reason: 'no_graph_hits',
            hit_count: 0,
            latency_ms: 0,
            top_paragraph_ids: [],
          },
          total_ms: 40,
        }}
      />,
    );

    await user.click(screen.getByRole('button', { name: /显示执行信息/ }));

    expect(screen.getByText('检索路径')).toBeInTheDocument();
    expect(screen.getByText('结构化检索')).toBeInTheDocument();
    expect(screen.getByText('向量检索')).toBeInTheDocument();
    expect(screen.getByText('融合排序')).toBeInTheDocument();
    expect(screen.getByText('图谱扩散')).toBeInTheDocument();
    expect(screen.getAllByText(/命中段落：p1/).length).toBeGreaterThan(0);
  });
});
