/**
 * 模块名称：features/knowledge_base/components/panels/import_panel
 * 主要功能：渲染文件导入、文档列表和任务状态面板，并提供拖拽上传体验。
 */

import { useState, type ChangeEvent, type DragEvent } from 'react';

import type { KnowledgeBaseDocument, KnowledgeBaseJob } from '../../types/knowledge_base';
import {
  get_document_status_label,
  get_file_type_label,
  get_job_status_label,
} from '../../utils/label_utils';

/**
 * 导入面板属性。
 */
interface ImportPanelProps {
  documents: KnowledgeBaseDocument[];
  jobs: KnowledgeBaseJob[];
  selected_document_id: string | null;
  include_chunks: boolean;
  is_uploading: boolean;
  set_selected_document_id: (document_id: string | null) => void;
  set_include_chunks: (value: boolean) => void;
  upload_file: (file: File) => Promise<void>;
}

/**
 * 渲染导入面板。
 *
 * @param props - 组件属性。
 * @returns 导入面板组件。
 */
export function ImportPanel(props: ImportPanelProps) {
  const {
    documents,
    jobs,
    selected_document_id,
    include_chunks,
    is_uploading,
    set_selected_document_id,
    set_include_chunks,
    upload_file,
  } = props;
  const [is_drag_active, set_is_drag_active] = useState<boolean>(false);

  /**
   * 处理文件选择事件。
   *
   * @param event - 文件输入事件。
   */
  function handle_file_change(event: ChangeEvent<HTMLInputElement>): void {
    const file: File | undefined = event.target.files?.[0];
    if (file) {
      void upload_file(file);
    }
    event.currentTarget.value = '';
  }

  /**
   * 处理拖拽进入上传区事件。
   *
   * @param event - 拖拽事件对象。
   */
  function handle_drag_over(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    set_is_drag_active(true);
  }

  /**
   * 处理拖拽离开上传区事件。
   *
   * @param event - 拖拽事件对象。
   */
  function handle_drag_leave(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    set_is_drag_active(false);
  }

  /**
   * 处理文件拖放上传事件。
   *
   * @param event - 拖拽事件对象。
   */
  function handle_drop(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    set_is_drag_active(false);
    const file: File | undefined = event.dataTransfer.files?.[0];
    if (file) {
      void upload_file(file);
    }
  }

  return (
    <aside className='panel'>
      <header className='panel-header'>
        <h2>导入文档</h2>
        <p>支持导入 `.txt`、`.pdf` 和 `.docx` 文件，系统会在后台完成索引与建图。</p>
      </header>

      <label
        className={is_drag_active ? 'upload-box upload-box-active' : 'upload-box'}
        onDragOver={handle_drag_over}
        onDragLeave={handle_drag_leave}
        onDrop={handle_drop}
      >
        <input
          aria-label='上传文档'
          type='file'
          accept='.txt,.pdf,.docx'
          disabled={is_uploading}
          onChange={handle_file_change}
        />
        <span>{is_uploading ? '正在上传文档...' : '拖拽文件到这里，或点击选择文档'}</span>
        <small>文件会先本地保存，再在后台进行切块、嵌入和实体关系抽取。</small>
      </label>

      <div className='toggle-row'>
        <label className='toggle-option'>
          <input
            type='checkbox'
            checked={include_chunks}
            onChange={(event) => set_include_chunks(event.target.checked)}
          />
          <span>显示切块节点</span>
        </label>
      </div>

      <div className='panel-section'>
        <div className='section-title-row'>
          <h3>文档列表</h3>
          <select
            value={selected_document_id ?? ''}
            onChange={(event) => set_selected_document_id(event.target.value || null)}
          >
            <option value=''>全部文档</option>
            {documents.map((document) => (
              <option key={document.id} value={document.id}>
                {document.original_name}
              </option>
            ))}
          </select>
        </div>
        <ul className='document-list'>
          {documents.length ? (
            documents.map((document) => (
              <li
                className={document.id === selected_document_id ? 'document-card active' : 'document-card'}
                key={document.id}
              >
                <button type='button' onClick={() => set_selected_document_id(document.id)}>
                  <strong>{document.original_name}</strong>
                  <span>{document.summary ?? get_file_type_label(document.file_type)}</span>
                  <em>{get_document_status_label(document.status)}</em>
                </button>
              </li>
            ))
          ) : (
            <li className='empty-state-card'>
              <strong>还没有导入文档</strong>
              <span>先导入一个文件，图谱和问答结果会在索引完成后出现在这里。</span>
            </li>
          )}
        </ul>
      </div>

      <div className='panel-section'>
        <h3>任务状态</h3>
        <ul className='job-list'>
          {jobs.length ? (
            jobs.map((job) => (
              <li className='job-card' key={job.id}>
                <div>
                  <span>{job.document_id.slice(0, 8)}</span>
                  {job.error_message ? <small>{job.error_message}</small> : null}
                </div>
                <strong className={`job-pill ${job.status}`}>{get_job_status_label(job.status)}</strong>
              </li>
            ))
          ) : (
            <li className='muted-text'>当前没有进行中的导入任务。</li>
          )}
        </ul>
      </div>
    </aside>
  );
}
