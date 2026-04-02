import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SourceLibraryDrawer } from './source_library_drawer';

describe('SourceLibraryDrawer', () => {
  it('renders localized source drawer labels', () => {
    render(
      <SourceLibraryDrawer
        delete_source={vi.fn(async () => {})}
        is_deleting_source={false}
        is_updating_source={false}
        on_close={vi.fn()}
        on_focus_paragraph={vi.fn()}
        open
        selected_source_browser_id='source-1'
        selected_source_ids={[]}
        set_selected_source_browser_id={vi.fn()}
        set_selected_source_ids={vi.fn()}
        source_detail={{
          source: {
            id: 'source-1',
            name: '孙子兵法.txt',
            source_kind: 'file',
            input_mode: 'upload',
            file_type: 'txt',
            storage_path: null,
            strategy: 'factual',
            status: 'ready',
            summary: '兵法原文',
            metadata: {},
            created_at: '',
            updated_at: '',
          },
          paragraph_count: 12,
          entity_count: 8,
          relation_count: 6,
        }}
        source_paragraphs={[]}
        sources={[
          {
            id: 'source-1',
            name: '孙子兵法.txt',
            source_kind: 'file',
            input_mode: 'upload',
            file_type: 'txt',
            storage_path: null,
            strategy: 'factual',
            status: 'ready',
            summary: '兵法原文',
            metadata: {},
            created_at: '',
            updated_at: '',
          },
        ]}
        update_source={vi.fn(async () => {})}
      />,
    );

    expect(screen.getByText('来源')).toBeInTheDocument();
    expect(screen.getByText('来源库')).toBeInTheDocument();
    expect(screen.getByText('来源预览')).toBeInTheDocument();
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    expect(screen.queryByText('Preview')).not.toBeInTheDocument();
  });
});
