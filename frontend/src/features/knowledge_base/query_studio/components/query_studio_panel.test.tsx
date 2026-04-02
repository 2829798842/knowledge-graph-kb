import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { QueryStudioPanel } from './query_studio_panel';

const query_state = vi.hoisted(() => ({
  current: {
    query_mode: 'answer',
    answer_sessions: [],
    active_answer_session_id: null,
    answer_messages: [],
    active_answer_message: null,
    record_results: [],
    entity_results: [],
    relation_results: [],
    source_results: [],
    is_querying: false,
    is_loading_answer_sessions: false,
    set_query_mode: vi.fn(),
    execute_query: vi.fn(async () => {}),
    select_answer_session: vi.fn(async () => {}),
    create_answer_session: vi.fn(async () => {}),
    focus_entity: vi.fn(),
    focus_relation: vi.fn(),
    focus_source: vi.fn(),
    focus_paragraph: vi.fn(),
    focus_citation: vi.fn(),
  },
}));

const workspace_state = vi.hoisted(() => ({
  current: {
    selected_source_ids: [],
    sources: [],
    upload_files: vi.fn(async () => {}),
    set_is_source_library_open: vi.fn(),
    set_is_settings_open: vi.fn(),
    is_source_library_open: false,
    is_settings_open: false,
    delete_source: vi.fn(async () => {}),
    is_deleting_source: false,
    is_updating_source: false,
    focus_paragraph: vi.fn(),
    focus_citation: vi.fn(),
    selected_source_browser_id: null,
    set_selected_source_browser_id: vi.fn(),
    set_selected_source_ids: vi.fn(),
    source_detail: null,
    source_paragraphs: [],
    update_source: vi.fn(async () => {}),
  },
}));

vi.mock('../hooks/use_query_studio', () => ({
  use_query_studio: () => query_state.current,
}));

vi.mock('../../shared/context/knowledge_base_workspace_context', () => ({
  use_knowledge_base_workspace_context: () => workspace_state.current,
}));

vi.mock('./source_library_drawer', () => ({
  SourceLibraryDrawer: () => null,
}));

vi.mock('../../model_config/components/model_config_modal', () => ({
  ModelConfigModal: () => null,
}));

describe('QueryStudioPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    query_state.current.answer_messages = [];
    query_state.current.answer_sessions = [];
    workspace_state.current.selected_source_ids = [];
    workspace_state.current.sources = [];
  });

  it('renders localized query toolbar copy', () => {
    render(<QueryStudioPanel />);

    expect(screen.getByRole('button', { name: '来源范围' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '导入文件' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '设置' })).toBeInTheDocument();
    expect(screen.getByText('开始提问')).toBeInTheDocument();
    expect(screen.getAllByText('当前范围：全部来源').length).toBeGreaterThan(0);
  });

  it('submits a query from the composer', async () => {
    const user = userEvent.setup();
    render(<QueryStudioPanel />);

    await user.type(screen.getByPlaceholderText('输入你的问题，按 Enter 发送，Shift + Enter 换行。'), '火猫是谁？');
    await user.click(screen.getByRole('button', { name: '发送' }));

    expect(query_state.current.execute_query).toHaveBeenCalledWith('火猫是谁？');
  });
});
