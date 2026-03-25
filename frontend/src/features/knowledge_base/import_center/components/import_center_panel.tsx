/**
 * 导入中心面板。
 */

import { useState } from 'react';

import {
  EXCEL_IMPORT_HINT,
  get_input_mode_label,
  get_status_label,
  get_step_label,
  get_strategy_label,
  IMPORT_MODES,
  STRATEGY_OPTIONS,
  SUPPORTED_UPLOAD_ACCEPT,
  SUPPORTED_UPLOAD_HINT,
  TASK_STATUS_ORDER,
} from '../../shared/config/ui_constants';
import type { ImportMode, ImportTaskRecord } from '../../shared/types/knowledge_base_types';
import { use_import_center } from '../hooks/use_import_center';
import '../styles/import_center_panel.css';

function resolve_task_mode_label(task: ImportTaskRecord): string {
  const task_source: string = task.source.split(':', 1)[0] || '';
  const file_source_kind: string = task.files[0]?.source_kind ?? '';
  const mode_key: string = file_source_kind || task_source || task.input_mode;
  return get_input_mode_label(mode_key || task.input_mode);
}

function count_partial_files(task: ImportTaskRecord): number {
  return task.files.filter((file) => file.status === 'partial').length;
}

function count_failed_files(task: ImportTaskRecord): number {
  return task.files.filter((file) => ['failed', 'cancelled', 'aborted'].includes(file.status)).length;
}

function count_problem_files(task: ImportTaskRecord): number {
  return task.files.filter((file) => ['partial', 'failed', 'cancelled', 'aborted'].includes(file.status)).length;
}

function count_processed_files(task: ImportTaskRecord): number {
  return task.files.filter((file) => ['completed', 'partial'].includes(file.status)).length;
}

export function ImportCenterPanel() {
  const {
    tasks,
    is_submitting_import,
    upload_files,
    import_paste_text,
    import_scan_path,
    import_structured_payload,
    cancel_task,
    retry_task,
  } = use_import_center();

  const [import_mode, set_import_mode] = useState<ImportMode>('upload');
  const [strategy, set_strategy] = useState<string>('auto');
  const [upload_files_value, set_upload_files_value] = useState<File[]>([]);
  const [paste_title, set_paste_title] = useState<string>('新粘贴来源');
  const [paste_content, set_paste_content] = useState<string>('');
  const [scan_root_path, set_scan_root_path] = useState<string>('');
  const [scan_glob_pattern, set_scan_glob_pattern] = useState<string>('**/*.*');
  const [structured_title, set_structured_title] = useState<string>('结构化数据');
  const [structured_payload_text, set_structured_payload_text] = useState<string>(
    '{\n  "paragraphs": [],\n  "entities": [],\n  "relations": []\n}',
  );

  const ordered_tasks = [...tasks].sort((left_task, right_task) => {
    const left_rank: number = TASK_STATUS_ORDER[left_task.status] ?? 99;
    const right_rank: number = TASK_STATUS_ORDER[right_task.status] ?? 99;
    return left_rank - right_rank;
  });
  const active_task_count: number = tasks.filter((task) => ['queued', 'running'].includes(task.status)).length;
  const partial_task_count: number = tasks.filter((task) => count_partial_files(task) > 0 || task.status === 'partial').length;
  const failed_task_count: number = tasks.filter((task) => count_failed_files(task) > 0 || task.status === 'failed').length;
  const current_mode = IMPORT_MODES.find((mode) => mode.id === import_mode) ?? IMPORT_MODES[0];

  return (
    <section className='kb-panel kb-import-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>导入中心</h2>
          <p>上传文件、粘贴文本、扫描目录，或者导入结构化结果。</p>
        </div>
      </header>

      <div className='kb-detail-card kb-panel-selector'>
        <label className='kb-form-field'>
          <span>导入方式</span>
          <select
            aria-label='选择导入方式'
            onChange={(event) => set_import_mode(event.target.value as ImportMode)}
            value={import_mode}
          >
            {IMPORT_MODES.map((mode) => (
              <option key={mode.id} value={mode.id}>
                {mode.label}
              </option>
            ))}
          </select>
        </label>

        <p className='kb-helper-text'>{current_mode.description}</p>
      </div>

      <div className='kb-import-grid'>
        <div className='kb-result-stack kb-import-config'>
          <div className='kb-detail-card'>
            <h3>{current_mode.label}</h3>
            <p>{current_mode.description}</p>
            <div className='kb-meta-strip'>
              <span className='kb-meta-pill'>{`进行中 ${active_task_count}`}</span>
              <span className='kb-meta-pill'>{`部分完成 ${partial_task_count}`}</span>
              <span className='kb-meta-pill'>{`失败 ${failed_task_count}`}</span>
              <span className='kb-meta-pill'>{`总任务 ${tasks.length}`}</span>
            </div>
          </div>

          <div className='kb-detail-card'>
            <h3>导入参数</h3>
            <div className='kb-form-grid'>
              <label className='kb-form-field'>
                <span>导入策略</span>
                <select onChange={(event) => set_strategy(event.target.value)} value={strategy}>
                  {STRATEGY_OPTIONS.map((item) => (
                    <option key={item} value={item}>
                      {get_strategy_label(item)}
                    </option>
                  ))}
                </select>
              </label>

              {import_mode === 'upload' ? (
                <label className='kb-form-field kb-form-field-wide'>
                  <span>选择文件</span>
                  <input
                    accept={SUPPORTED_UPLOAD_ACCEPT}
                    multiple
                    onChange={(event) => set_upload_files_value(Array.from(event.target.files ?? []))}
                    type='file'
                  />
                  <span className='kb-helper-text'>{SUPPORTED_UPLOAD_HINT}</span>
                  <span className='kb-helper-text'>{EXCEL_IMPORT_HINT}</span>
                </label>
              ) : null}

              {import_mode === 'paste' ? (
                <>
                  <label className='kb-form-field'>
                    <span>标题</span>
                    <input onChange={(event) => set_paste_title(event.target.value)} type='text' value={paste_title} />
                  </label>
                  <label className='kb-form-field kb-form-field-wide'>
                    <span>内容</span>
                    <textarea onChange={(event) => set_paste_content(event.target.value)} value={paste_content} />
                  </label>
                </>
              ) : null}

              {import_mode === 'scan' ? (
                <>
                  <label className='kb-form-field'>
                    <span>根目录</span>
                    <input
                      onChange={(event) => set_scan_root_path(event.target.value)}
                      type='text'
                      value={scan_root_path}
                    />
                  </label>
                  <label className='kb-form-field'>
                    <span>匹配模式</span>
                    <input
                      onChange={(event) => set_scan_glob_pattern(event.target.value)}
                      type='text'
                      value={scan_glob_pattern}
                    />
                  </label>
                  <span className='kb-helper-text'>{`会扫描这些类型：${SUPPORTED_UPLOAD_HINT}`}</span>
                  <span className='kb-helper-text'>{EXCEL_IMPORT_HINT}</span>
                </>
              ) : null}

              {import_mode === 'openie' || import_mode === 'convert' ? (
                <>
                  <label className='kb-form-field'>
                    <span>标题</span>
                    <input
                      onChange={(event) => set_structured_title(event.target.value)}
                      type='text'
                      value={structured_title}
                    />
                  </label>
                  <label className='kb-form-field kb-form-field-wide'>
                    <span>结构化 JSON</span>
                    <textarea
                      onChange={(event) => set_structured_payload_text(event.target.value)}
                      value={structured_payload_text}
                    />
                  </label>
                </>
              ) : null}
            </div>

            <div className='kb-button-row'>
              {import_mode === 'upload' ? (
                <button
                  className='kb-primary-button'
                  disabled={is_submitting_import || upload_files_value.length === 0}
                  onClick={() => void upload_files(upload_files_value, strategy)}
                  type='button'
                >
                  {is_submitting_import ? '提交中...' : '提交上传任务'}
                </button>
              ) : null}

              {import_mode === 'paste' ? (
                <button
                  className='kb-primary-button'
                  disabled={is_submitting_import || !paste_content.trim()}
                  onClick={() => void import_paste_text(paste_title, paste_content, strategy)}
                  type='button'
                >
                  {is_submitting_import ? '提交中...' : '提交粘贴任务'}
                </button>
              ) : null}

              {import_mode === 'scan' ? (
                <button
                  className='kb-primary-button'
                  disabled={is_submitting_import || !scan_root_path.trim()}
                  onClick={() => void import_scan_path(scan_root_path, scan_glob_pattern, strategy)}
                  type='button'
                >
                  {is_submitting_import ? '提交中...' : '提交扫描任务'}
                </button>
              ) : null}

              {import_mode === 'openie' ? (
                <button
                  className='kb-primary-button'
                  disabled={is_submitting_import || !structured_payload_text.trim()}
                  onClick={() =>
                    void import_structured_payload('openie', structured_title, structured_payload_text, strategy)
                  }
                  type='button'
                >
                  {is_submitting_import ? '提交中...' : '提交 OpenIE 数据'}
                </button>
              ) : null}

              {import_mode === 'convert' ? (
                <button
                  className='kb-primary-button'
                  disabled={is_submitting_import || !structured_payload_text.trim()}
                  onClick={() =>
                    void import_structured_payload('convert', structured_title, structured_payload_text, strategy)
                  }
                  type='button'
                >
                  {is_submitting_import ? '提交中...' : '提交转换结果'}
                </button>
              ) : null}
            </div>
          </div>
        </div>

        <div className='kb-result-stack kb-import-jobs'>
          <div className='kb-detail-card'>
            <h3>任务看板</h3>
            <p>运行中的任务会自动刷新状态。</p>
          </div>

          <div className='kb-task-list'>
            {ordered_tasks.map((task) => {
              const processed_file_count: number = count_processed_files(task);
              const problem_file_count: number = count_problem_files(task);

              return (
                <article className='kb-task-card' key={task.id}>
                  <div className='kb-task-header'>
                    <div>
                      <strong>{`${resolve_task_mode_label(task)}任务`}</strong>
                      <span>{`当前阶段：${get_step_label(task.current_step)}`}</span>
                    </div>
                    <span className='kb-task-status'>{get_status_label(task.status)}</span>
                  </div>

                  <div className='kb-progress-track'>
                    <div className='kb-progress-fill' style={{ width: `${task.progress}%` }} />
                  </div>

                  <div className='kb-task-meta'>
                    <span>{`已处理 ${processed_file_count}/${task.total_files}`}</span>
                    <span>{`分块 ${task.completed_chunks}/${task.total_chunks}`}</span>
                    <span>{`异常文件 ${problem_file_count}`}</span>
                    <span>{`策略 ${get_strategy_label(task.strategy)}`}</span>
                  </div>

                  {task.error ? <span className='kb-helper-text'>{`说明：${task.error}`}</span> : null}

                  <div className='kb-task-actions'>
                    {['running', 'queued'].includes(task.status) ? (
                      <button className='kb-secondary-button' onClick={() => void cancel_task(task.id)} type='button'>
                        取消任务
                      </button>
                    ) : null}
                    {problem_file_count > 0 ? (
                      <button className='kb-secondary-button' onClick={() => void retry_task(task.id)} type='button'>
                        重试异常文件
                      </button>
                    ) : null}
                  </div>

                  <div className='kb-task-files'>
                    {task.files.slice(0, 3).map((file) => (
                      <div className='kb-task-file' key={file.id}>
                        <div className='kb-task-file-header'>
                          <strong>{file.name}</strong>
                          <span>{get_status_label(file.status)}</span>
                        </div>
                        <span>{`阶段：${get_step_label(file.current_step)}`}</span>
                        <div className='kb-progress-track is-compact'>
                          <div className='kb-progress-fill' style={{ width: `${file.progress}%` }} />
                        </div>
                        <span>{`分块 ${file.completed_chunks}/${file.total_chunks}，失败 ${file.failed_chunks}`}</span>
                        {file.error ? <span className='kb-helper-text'>{`说明：${file.error}`}</span> : null}
                      </div>
                    ))}
                    {task.files.length > 3 ? (
                      <span className='kb-helper-text'>{`还有 ${task.files.length - 3} 个文件`}</span>
                    ) : null}
                  </div>
                </article>
              );
            })}

            {!ordered_tasks.length ? <div className='kb-empty-card'>暂时还没有导入任务。</div> : null}
          </div>
        </div>
      </div>
    </section>
  );
}
