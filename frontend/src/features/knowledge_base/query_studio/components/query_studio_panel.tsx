import { useMemo, useRef, useState, type FormEvent } from 'react';

import { ModelConfigModal } from '../../model_config/components/model_config_modal';
import { selected_source_summary } from '../../graph_browser/components/graph_browser_utils';
import { QUERY_MODE_OPTIONS } from '../../shared/config/ui_constants';
import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';
import { use_query_studio } from '../hooks/use_query_studio';
import { ChatDiagnosticsSection } from './chat_diagnostics_section';
import { ChatSourcesSection } from './chat_sources_section';
import { SourceLibraryDrawer } from './source_library_drawer';
import '../styles/query_studio_panel.css';

export function QueryStudioPanel() {
  const query = use_query_studio();
  const workspace = use_knowledge_base_workspace_context();
  const upload_input_ref = useRef<HTMLInputElement | null>(null);
  const [query_text, set_query_text] = useState('');

  const source_scope_text = useMemo(
    () => selected_source_summary(workspace.selected_source_ids, workspace.sources),
    [workspace.selected_source_ids, workspace.sources],
  );
  const current_mode_label =
    QUERY_MODE_OPTIONS.find((option) => option.id === query.query_mode)?.label ?? '问答';

  async function handle_submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const normalized = query_text.trim();
    if (!normalized) {
      return;
    }
    await query.execute_query(normalized);
    set_query_text('');
  }

  async function handle_upload_files(files: FileList | null): Promise<void> {
    if (!files?.length) {
      return;
    }
    await workspace.upload_files(Array.from(files), 'summary');
  }

  return (
    <section className='kb-panel kb-chat-page'>
      <header className='kb-chat-topbar'>
        <div className='kb-chat-session-rail'>
          {query.answer_sessions.map((session) => (
            <button
              className={`kb-chat-session-pill ${session.id === query.active_answer_session_id ? 'is-active' : ''}`}
              key={session.id}
              onClick={() => void query.select_answer_session(session.id)}
              type='button'
            >
              <strong>{session.title}</strong>
              <span>{session.last_message_at ? '最近更新' : '新会话'}</span>
            </button>
          ))}
          {!query.answer_sessions.length ? <div className='kb-chat-session-status'>暂无会话</div> : null}
        </div>

        <div className='kb-chat-topbar-actions'>
          <button className='kb-secondary-button' onClick={() => void query.create_answer_session()} type='button'>
            新建对话
          </button>
          <button
            className='kb-secondary-button'
            onClick={() => workspace.set_is_source_library_open(true)}
            type='button'
          >
            来源范围
          </button>
          <button
            className='kb-secondary-button'
            onClick={() => upload_input_ref.current?.click()}
            type='button'
          >
            导入文件
          </button>
          <button
            className='kb-secondary-button'
            onClick={() => workspace.set_is_settings_open(true)}
            type='button'
          >
            设置
          </button>
          <input
            hidden
            multiple
            onChange={(event) => void handle_upload_files(event.target.files)}
            ref={upload_input_ref}
            type='file'
          />
        </div>
      </header>

      <div className='kb-chat-composer-meta'>
        <span>{source_scope_text}</span>
        <span>{`当前模式：${current_mode_label}`}</span>
      </div>

      <div className='kb-mode-tabs'>
        {QUERY_MODE_OPTIONS.map((option) => (
          <button
            className={`kb-pill-button ${query.query_mode === option.id ? 'is-active' : ''}`}
            key={option.id}
            onClick={() => query.set_query_mode(option.id)}
            type='button'
          >
            {option.label}
          </button>
        ))}
      </div>

      <section className='kb-chat-thread-shell'>
        <div className='kb-chat-thread'>
          {!query.answer_messages.length ? (
            <section className='kb-chat-empty'>
              <span className='kb-context-label'>就绪</span>
              <h3>开始提问</h3>
              <p>先提出问题，回答会显示在这里，并附带命中来源和检索诊断。</p>
            </section>
          ) : null}

          {query.answer_messages.map((message) => (
            <article
              className={`kb-chat-bubble ${message.role === 'user' ? 'is-user' : 'is-assistant'}`}
              key={message.id}
            >
              <div className='kb-chat-bubble-head'>
                <strong>{message.role === 'user' ? '用户' : '助手'}</strong>
                <span>{message.created_at}</span>
              </div>
              <div className='kb-chat-bubble-body'>{message.content}</div>
              {message.role === 'assistant' ? (
                <>
                  <ChatSourcesSection
                    citations={message.citations}
                    on_focus_paragraph={workspace.focus_paragraph}
                    on_view_in_graph={workspace.focus_citation}
                  />
                  <ChatDiagnosticsSection execution={message.execution} retrieval_trace={message.retrieval_trace} />
                </>
              ) : null}
            </article>
          ))}

          {query.is_querying ? (
            <article className='kb-chat-bubble is-assistant is-pending'>
              <div className='kb-chat-bubble-head'>
                <strong>助手</strong>
                <span>正在生成</span>
              </div>
              <div className='kb-chat-bubble-body'>正在检索知识图谱与来源证据，请稍候…</div>
            </article>
          ) : null}
        </div>
      </section>

      <section className='kb-chat-composer-card'>
        <form className='kb-chat-composer-main' onSubmit={(event) => void handle_submit(event)}>
          <label className='kb-form-field kb-chat-composer-input'>
            <span>输入问题</span>
            <textarea
              onChange={(event) => set_query_text(event.target.value)}
              placeholder='输入你的问题，按 Enter 发送，Shift + Enter 换行。'
              value={query_text}
            />
          </label>

          <div className='kb-chat-composer-actions'>
            <div className='kb-chat-composer-meta'>
              <span>{source_scope_text}</span>
              <span>{query.is_loading_answer_sessions ? '正在同步会话…' : '会话已同步'}</span>
            </div>
            <button className='kb-primary-button' disabled={query.is_querying || !query_text.trim()} type='submit'>
              {query.is_querying ? '发送中…' : '发送'}
            </button>
          </div>
        </form>
      </section>

      <SourceLibraryDrawer
        delete_source={workspace.delete_source}
        is_deleting_source={workspace.is_deleting_source}
        is_updating_source={workspace.is_updating_source}
        on_close={() => workspace.set_is_source_library_open(false)}
        on_focus_paragraph={workspace.focus_paragraph}
        open={workspace.is_source_library_open}
        selected_source_browser_id={workspace.selected_source_browser_id}
        selected_source_ids={workspace.selected_source_ids}
        set_selected_source_browser_id={workspace.set_selected_source_browser_id}
        set_selected_source_ids={workspace.set_selected_source_ids}
        source_detail={workspace.source_detail}
        source_paragraphs={workspace.source_paragraphs}
        sources={workspace.sources}
        update_source={workspace.update_source}
      />

      <ModelConfigModal on_close={() => workspace.set_is_settings_open(false)} open={workspace.is_settings_open} />
    </section>
  );
}
