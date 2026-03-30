import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';

import { use_import_center } from '../../import_center/hooks/use_import_center';
import { ModelConfigModal } from '../../model_config/components/model_config_modal';
import { SUPPORTED_UPLOAD_ACCEPT } from '../../shared/config/ui_constants';
import { use_knowledge_base_workspace_context } from '../../shared/context/knowledge_base_workspace_context';
import type { ChatMessageRecord, ChatSessionRecord, SourceRecord } from '../../shared/types/knowledge_base_types';
import { use_query_studio } from '../hooks/use_query_studio';
import '../styles/query_studio_panel.css';
import { ChatDiagnosticsSection } from './chat_diagnostics_section';
import { ChatSourcesSection } from './chat_sources_section';
import { SourceLibraryDrawer } from './source_library_drawer';

function format_session_time(session: ChatSessionRecord): string {
  const value = session.last_message_at ?? session.updated_at ?? session.created_at;
  try {
    return new Date(value).toLocaleString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function format_message_time(message: ChatMessageRecord): string {
  try {
    return new Date(message.created_at).toLocaleString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return message.created_at;
  }
}

function source_scope_text(selected_source_ids: string[], sources: SourceRecord[]): string {
  if (!selected_source_ids.length) {
    return '当前范围：全部来源';
  }
  const names = sources.filter((source) => selected_source_ids.includes(source.id)).map((source) => source.name);
  if (!names.length) {
    return '当前范围：已选来源';
  }
  if (names.length <= 2) {
    return `当前范围：${names.join('、')}`;
  }
  return `当前范围：${names.slice(0, 2).join('、')} 等 ${names.length} 个来源`;
}

function latest_import_text(task_count: number, is_submitting_import: boolean): string {
  if (is_submitting_import) {
    return '文件正在提交到导入队列...';
  }
  if (!task_count) {
    return '暂时没有导入任务。';
  }
  return `导入中心内共有 ${task_count} 个任务。`;
}

export function QueryStudioPanel() {
  const workspace = use_knowledge_base_workspace_context();
  const {
    answer_sessions,
    active_answer_session_id,
    answer_messages,
    is_querying,
    is_loading_answer_sessions,
    execute_query,
    select_answer_session,
    create_answer_session,
    focus_paragraph,
  } = use_query_studio();
  const { upload_files, is_submitting_import, tasks } = use_import_center();
  const [query_text, set_query_text] = useState('');
  const file_input_ref = useRef<HTMLInputElement | null>(null);
  const thread_ref = useRef<HTMLDivElement | null>(null);

  const source_scope_label = useMemo(
    () => source_scope_text(workspace.selected_source_ids, workspace.sources),
    [workspace.selected_source_ids, workspace.sources],
  );
  const import_label = useMemo(
    () => latest_import_text(tasks.length, is_submitting_import),
    [is_submitting_import, tasks.length],
  );
  const recent_sessions = answer_sessions.slice(0, 6);

  useEffect(() => {
    if (!thread_ref.current) {
      return;
    }
    thread_ref.current.scrollTo({
      top: thread_ref.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [answer_messages.length, is_querying]);

  async function handle_submit(): Promise<void> {
    const normalized_query = query_text.trim();
    if (!normalized_query || is_querying) {
      return;
    }
    await execute_query(normalized_query);
    set_query_text('');
  }

  async function handle_upload_change(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) {
      return;
    }
    await upload_files(files, 'auto');
    event.target.value = '';
  }

  async function handle_delete_source(source_id: string): Promise<void> {
    const source = workspace.sources.find((item) => item.id === source_id);
    if (!source) {
      return;
    }
    if (!window.confirm(`确认删除来源“${source.name}”吗？这会同步清理段落、关系和向量索引。`)) {
      return;
    }
    await workspace.delete_source(source_id);
    workspace.set_selected_source_ids((current) => current.filter((item) => item !== source_id));
  }

  return (
    <section className='kb-panel kb-chat-page'>
      <input accept={SUPPORTED_UPLOAD_ACCEPT} hidden multiple onChange={(event) => void handle_upload_change(event)} ref={file_input_ref} type='file' />

      <div className='kb-chat-topbar'>
        <div className='kb-chat-session-rail'>
          <button className='kb-primary-button' onClick={() => void create_answer_session()} type='button'>
            新建对话
          </button>

          {is_loading_answer_sessions ? <span className='kb-chat-session-status'>正在加载历史会话...</span> : null}

          {recent_sessions.map((session) => (
            <button
              className={`kb-chat-session-pill ${active_answer_session_id === session.id ? 'is-active' : ''}`}
              key={session.id}
              onClick={() => void select_answer_session(session.id)}
              type='button'
            >
              <strong>{session.title}</strong>
              <span>{format_session_time(session)}</span>
            </button>
          ))}
        </div>

        <div className='kb-chat-topbar-actions'>
          <button className='kb-secondary-button' onClick={() => workspace.set_is_source_library_open(true)} type='button'>
            来源范围
          </button>
          <button className='kb-secondary-button' onClick={() => file_input_ref.current?.click()} type='button'>
            导入文件
          </button>
          <button className='kb-secondary-button' onClick={() => workspace.set_is_settings_open(true)} type='button'>
            设置
          </button>
        </div>
      </div>

      <div className='kb-chat-thread-shell'>
        <div className='kb-chat-thread' ref={thread_ref}>
          {!answer_messages.length ? (
            <div className='kb-chat-empty'>
              <span className='kb-context-label'>Ready</span>
              <h3>开始提问</h3>
              <p>直接输入问题，或者先导入文件，再让系统基于知识图谱和来源证据回答。</p>
              <div className='kb-meta-strip'>
                <span className='kb-meta-pill'>{source_scope_label}</span>
                <span className='kb-meta-pill'>{import_label}</span>
              </div>
            </div>
          ) : null}

          {answer_messages.map((message) => (
            <article className={`kb-chat-bubble ${message.role === 'user' ? 'is-user' : 'is-assistant'}`} key={message.id}>
              <div className='kb-chat-bubble-head'>
                <strong>{message.role === 'user' ? '你' : '助手'}</strong>
                <span>{format_message_time(message)}</span>
              </div>

              <div className='kb-chat-bubble-body'>{message.content}</div>

              {message.role === 'assistant' ? (
                <>
                  <ChatSourcesSection citations={message.citations} on_focus_paragraph={focus_paragraph} on_open_source={workspace.focus_source} />
                  <ChatDiagnosticsSection execution={message.execution} retrieval_trace={message.retrieval_trace} />
                </>
              ) : null}
            </article>
          ))}

          {is_querying ? (
            <article className='kb-chat-bubble is-assistant is-pending'>
              <div className='kb-chat-bubble-head'>
                <strong>助手</strong>
                <span>正在生成</span>
              </div>
              <div className='kb-chat-bubble-body'>正在检索知识图谱与来源证据，请稍候...</div>
            </article>
          ) : null}
        </div>
      </div>

      <div className='kb-chat-composer-card'>
        <div className='kb-chat-composer-meta'>
          <span>{source_scope_label}</span>
          <span>{import_label}</span>
        </div>

        <div className='kb-chat-composer-main'>
          <label className='kb-form-field kb-chat-composer-input'>
            <span className='sr-only'>输入问题</span>
            <textarea
              onChange={(event) => set_query_text(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  void handle_submit();
                }
              }}
              placeholder='输入你的问题，按 Enter 发送，Shift + Enter 换行。'
              value={query_text}
            />
          </label>

          <div className='kb-chat-composer-actions'>
            <div className='kb-button-row'>
              <button className='kb-secondary-button' onClick={() => workspace.set_is_source_library_open(true)} type='button'>
                选择来源
              </button>
              <button className='kb-secondary-button' onClick={() => file_input_ref.current?.click()} type='button'>
                上传文件
              </button>
              <button className='kb-secondary-button' onClick={() => workspace.set_is_settings_open(true)} type='button'>
                模型设置
              </button>
            </div>

            <button className='kb-primary-button' disabled={is_querying || !query_text.trim()} onClick={() => void handle_submit()} type='button'>
              {is_querying ? '发送中...' : '发送'}
            </button>
          </div>
        </div>
      </div>

      <SourceLibraryDrawer
        delete_source={handle_delete_source}
        is_deleting_source={workspace.is_deleting_source}
        is_updating_source={workspace.is_updating_source}
        on_close={() => workspace.set_is_source_library_open(false)}
        on_focus_paragraph={focus_paragraph}
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

      <ModelConfigModal open={workspace.is_settings_open} on_close={() => workspace.set_is_settings_open(false)} />
    </section>
  );
}
