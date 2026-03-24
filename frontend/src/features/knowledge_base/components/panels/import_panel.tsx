/**
 * 模块名称：features/knowledge_base/components/panels/import_panel
 * 主要功能：渲染文件上传、手动开始抽取、文档列表与任务进度面板。
 */

import { useMemo, useState, type ChangeEvent, type DragEvent } from 'react';

import type { KnowledgeBaseDocument, KnowledgeBaseJob } from '../../types/knowledge_base';
import { get_latest_job_for_document } from '../../utils/job_utils';
import {
  get_document_status_label,
  get_file_type_label,
  get_job_stage_label,
  get_job_status_label,
} from '../../utils/label_utils';

interface ImportPanelProps {
  documents: KnowledgeBaseDocument[];
  jobs: KnowledgeBaseJob[];
  selected_document_id: string | null;
  include_chunks: boolean;
  is_uploading: boolean;
  is_starting_extraction: boolean;
  starting_document_id: string | null;
  set_selected_document_id: (document_id: string | null) => void;
  set_include_chunks: (value: boolean) => void;
  upload_file: (file: File) => Promise<void>;
  start_document_extraction: (document_id?: string | null) => Promise<void>;
}

export function ImportPanel(props: ImportPanelProps) {
  const {
    documents,
    jobs,
    selected_document_id,
    include_chunks,
    is_uploading,
    is_starting_extraction,
    starting_document_id,
    set_selected_document_id,
    set_include_chunks,
    upload_file,
    start_document_extraction,
  } = props;
  const [is_drag_active, set_is_drag_active] = useState<boolean>(false);

  const selected_document: KnowledgeBaseDocument | null = useMemo(
    () => documents.find((document) => document.id === selected_document_id) ?? null,
    [documents, selected_document_id],
  );
  const selected_job: KnowledgeBaseJob | null = useMemo(
    () => (selected_document ? get_latest_job_for_document(jobs, selected_document.id) : null),
    [jobs, selected_document],
  );
  const can_start_extraction: boolean = Boolean(
    selected_document_id &&
      !is_starting_extraction &&
      selected_job?.status !== 'processing' &&
      selected_job?.status !== 'pending',
  );

  function handle_file_change(event: ChangeEvent<HTMLInputElement>): void {
    const file: File | undefined = event.target.files?.[0];
    if (file) {
      void upload_file(file);
    }
    event.currentTarget.value = '';
  }

  function handle_drag_over(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    set_is_drag_active(true);
  }

  function handle_drag_leave(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    set_is_drag_active(false);
  }

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
        <h2>导入与抽取</h2>
        <p>先上传文档，再手动开始 LLM 抽取。处理过程中会展示阶段、进度和结果统计。</p>
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
        <small>支持 `.txt`、`.pdf`、`.docx`。上传后不会自动调用模型，便于你先确认文档和配置。</small>
      </label>

      <div className='toggle-row'>
        <label className='toggle-option'>
          <input
            type='checkbox'
            checked={include_chunks}
            onChange={(event) => set_include_chunks(event.target.checked)}
          />
          <span>显示片段节点</span>
        </label>
      </div>

      <div className='panel-section'>
        <div className='section-title-row'>
          <div>
            <h3>当前文档</h3>
            <p className='muted-text'>选中文档后可手动开始抽取，也能查看最新进度。</p>
          </div>
          <button
            className='primary-button'
            disabled={!can_start_extraction}
            type='button'
            onClick={() => void start_document_extraction(selected_document_id)}
          >
            {is_starting_extraction && starting_document_id === selected_document_id ? '正在启动...' : '开始 LLM 抽取'}
          </button>
        </div>

        {selected_document ? (
          <article className='detail-card'>
            <strong>{selected_document.original_name}</strong>
            <span>
              {get_file_type_label(selected_document.file_type)} · {get_document_status_label(selected_document.status)}
            </span>
            <p className='muted-text'>
              {selected_document.summary ?? '尚未完成抽取，当前还没有切块和实体统计。'}
            </p>
            <div className='document-meta-grid'>
              <span>片段 {read_numeric_metadata(selected_document.metadata, 'chunk_count')}</span>
              <span>实体 {read_numeric_metadata(selected_document.metadata, 'entity_count')}</span>
              <span>关系 {read_numeric_metadata(selected_document.metadata, 'relation_count')}</span>
            </div>
            {selected_job ? (
              <div className='job-progress-block'>
                <div className='job-progress-header'>
                  <strong>{get_job_status_label(selected_job.status)}</strong>
                  <span>{selected_job.progress_percent}%</span>
                </div>
                <div className='job-progress-track'>
                  <div className='job-progress-fill' style={{ width: `${selected_job.progress_percent}%` }} />
                </div>
                <small>{selected_job.status_message ?? get_job_stage_label(selected_job.stage)}</small>
              </div>
            ) : (
              <small>上传完成后，点击“开始 LLM 抽取”即可进入切块、向量化和实体关系抽取。</small>
            )}
          </article>
        ) : (
          <div className='empty-state-card'>
            <strong>还没有选中文档</strong>
            <span>先上传一个文件，或在下方文档列表里选择一个已上传文档。</span>
          </div>
        )}
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
            documents.map((document) => {
              const latest_job: KnowledgeBaseJob | null = get_latest_job_for_document(jobs, document.id);
              return (
                <li
                  className={document.id === selected_document_id ? 'document-card active' : 'document-card'}
                  key={document.id}
                >
                  <button type='button' onClick={() => set_selected_document_id(document.id)}>
                    <strong>{document.original_name}</strong>
                    <span>{document.summary ?? get_file_type_label(document.file_type)}</span>
                    <em>{get_document_status_label(document.status)}</em>
                    {latest_job ? (
                      <small>
                        {latest_job.progress_percent}% · {latest_job.status_message ?? get_job_stage_label(latest_job.stage)}
                      </small>
                    ) : null}
                  </button>
                </li>
              );
            })
          ) : (
            <li className='empty-state-card'>
              <strong>还没有导入文档</strong>
              <span>先上传一个文件，图谱和问答结果会在抽取完成后出现在这里。</span>
            </li>
          )}
        </ul>
      </div>

      <div className='panel-section'>
        <h3>任务进度</h3>
        <ul className='job-list'>
          {jobs.length ? (
            jobs.map((job) => {
              const document_name: string =
                documents.find((document) => document.id === job.document_id)?.original_name ?? job.document_id;
              return (
                <li className='job-progress-card' key={job.id}>
                  <div className='job-progress-header'>
                    <div>
                      <strong>{document_name}</strong>
                      <small>{job.status_message ?? get_job_stage_label(job.stage)}</small>
                    </div>
                    <strong className={`job-pill ${job.status}`}>{get_job_status_label(job.status)}</strong>
                  </div>
                  <div className='job-progress-track'>
                    <div className='job-progress-fill' style={{ width: `${job.progress_percent}%` }} />
                  </div>
                  <div className='job-progress-footer'>
                    <span>{job.progress_percent}%</span>
                    {job.error_message ? <small>{job.error_message}</small> : null}
                  </div>
                </li>
              );
            })
          ) : (
            <li className='muted-text'>当前还没有抽取任务，上传文档后可以手动开始。</li>
          )}
        </ul>
      </div>
    </aside>
  );
}

function read_numeric_metadata(metadata: Record<string, unknown>, key: string): number {
  const raw_value: unknown = metadata[key];
  return typeof raw_value === 'number' ? raw_value : 0;
}
