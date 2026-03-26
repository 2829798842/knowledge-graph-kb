/**
 * Import-center panel.
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
} from '../../shared/config/ui_constants';
import type { ImportFileRecord, ImportMode, ImportTaskRecord } from '../../shared/types/knowledge_base_types';
import { use_import_center } from '../hooks/use_import_center';
import {
  format_import_task_short_id,
  format_import_task_timestamp,
  sort_import_tasks,
} from '../utils/import_task_order';
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

function resolve_progress_debug(metadata: Record<string, unknown>): string | null {
  const progress_message = metadata.progress_message;
  if (typeof progress_message !== 'string') {
    return null;
  }
  const normalized = progress_message.trim();
  return normalized ? normalized : null;
}

function format_progress(progress: number): string {
  const normalized = Math.max(0, Math.min(progress, 100));
  const rounded = Math.round(normalized * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded.toFixed(0)}%` : `${rounded.toFixed(1)}%`;
}

function resolve_progress_detail(
  metadata: Record<string, unknown>,
): { label: string; current: number | null; total: number | null } | null {
  const label = typeof metadata.progress_detail_label === 'string' ? metadata.progress_detail_label.trim() : '';
  const current = typeof metadata.progress_detail_current === 'number' ? metadata.progress_detail_current : null;
  const total = typeof metadata.progress_detail_total === 'number' ? metadata.progress_detail_total : null;
  if (!label) {
    return null;
  }
  return { label, current, total };
}

function render_strategy_summary(task: ImportTaskRecord): string {
  const requested_label = get_strategy_label(task.strategy);
  const detected_strategies = [
    ...new Set(
      task.files
        .map((file) => file.strategy)
        .filter((value) => value),
    ),
  ];
  if (!detected_strategies.length) {
    return `策略 ${requested_label}`;
  }
  if (detected_strategies.length === 1) {
    const detected_label = get_strategy_label(detected_strategies[0]);
    if (detected_strategies[0] === task.strategy) {
      return `策略 ${detected_label}`;
    }
    return `策略 请求 ${requested_label} / 实际 ${detected_label}`;
  }
  return `策略 请求 ${requested_label} / 实际 多种`;
}

function render_file_strategy_summary(file: ImportFileRecord): string {
  const actual_label = get_strategy_label(file.strategy);
  const retry_payload =
    typeof file.metadata.retry_payload === 'object' && file.metadata.retry_payload !== null
      ? (file.metadata.retry_payload as { strategy?: unknown })
      : null;
  const requested = typeof retry_payload?.strategy === 'string' ? retry_payload.strategy.trim() : '';
  if (!requested || requested === file.strategy) {
    return `策略 ${actual_label}`;
  }
  return `策略 请求 ${get_strategy_label(requested)} / 实际 ${actual_label}`;
}

function render_file_progress_summary(file: ImportFileRecord): string {
  const progress_detail = resolve_progress_detail(file.metadata);
  if (
    file.current_step === 'extracting' &&
    progress_detail?.label === '抽取窗口' &&
    progress_detail.current !== null &&
    progress_detail.total !== null
  ) {
    return `${progress_detail.label} ${progress_detail.current}/${progress_detail.total}，已抽取段落 ${file.completed_chunks}/${file.total_chunks}，失败 ${file.failed_chunks}`;
  }
  if (
    progress_detail?.label === '段落分块' &&
    progress_detail.current !== null &&
    progress_detail.total !== null &&
    progress_detail.total > 0 &&
    file.current_step === 'completed'
  ) {
    return `${progress_detail.label} ${progress_detail.current}/${progress_detail.total}，失败 ${file.failed_chunks}`;
  }
  return `进度 ${format_progress(file.progress)}，分块 ${file.completed_chunks}/${file.total_chunks}，失败 ${file.failed_chunks}`;
}

function render_task_chunk_summary(task: ImportTaskRecord): string {
  const extracting_file = task.files.find((file) => {
    const progress_detail = resolve_progress_detail(file.metadata);
    return (
      file.current_step === 'extracting' &&
      progress_detail?.label === '抽取窗口' &&
      progress_detail.current !== null &&
      progress_detail.total !== null
    );
  });
  if (extracting_file) {
    const progress_detail = resolve_progress_detail(extracting_file.metadata);
    if (progress_detail && progress_detail.current !== null && progress_detail.total !== null) {
      return `${progress_detail.label} ${progress_detail.current}/${progress_detail.total}，已抽取段落 ${task.completed_chunks}/${task.total_chunks}`;
    }
  }
  return `段落分块 ${task.completed_chunks}/${task.total_chunks}`;
}

function get_import_mode_hints(import_mode: ImportMode, upload_file_count: number): string[] {
  if (import_mode === 'upload') {
    return [
      upload_file_count ? `已选择 ${upload_file_count} 个文件。` : '选择一个或多个本地文件后即可提交。',
      SUPPORTED_UPLOAD_HINT,
      EXCEL_IMPORT_HINT,
    ];
  }
  if (import_mode === 'paste') {
    return ['适合快速录入说明、纪要或临时文本。', '标题会作为来源名保存到知识库中。'];
  }
  if (import_mode === 'scan') {
    return ['适合对目录做批量导入。', SUPPORTED_UPLOAD_HINT, EXCEL_IMPORT_HINT];
  }
  if (import_mode === 'openie') {
    return ['适合直接导入 OpenIE 抽取结果。', '请确保 JSON 中的段落、实体和关系结构完整。'];
  }
  return ['适合导入外部转换后的结构化结果。', '请保持 JSON 结构稳定，方便后续检索和图谱使用。'];
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

  const ordered_tasks = sort_import_tasks(tasks);
  const active_task_count: number = tasks.filter((task) => ['queued', 'running'].includes(task.status)).length;
  const partial_task_count: number = tasks.filter((task) => count_partial_files(task) > 0 || task.status === 'partial').length;
  const failed_task_count: number = tasks.filter((task) => count_failed_files(task) > 0 || task.status === 'failed').length;
  const current_mode = IMPORT_MODES.find((mode) => mode.id === import_mode) ?? IMPORT_MODES[0];
  const import_hints = get_import_mode_hints(import_mode, upload_files_value.length);

  async function submit_current_import(): Promise<void> {
    if (import_mode === 'upload') {
      await upload_files(upload_files_value, strategy);
      return;
    }
    if (import_mode === 'paste') {
      await import_paste_text(paste_title, paste_content, strategy);
      return;
    }
    if (import_mode === 'scan') {
      await import_scan_path(scan_root_path, scan_glob_pattern, strategy);
      return;
    }
    if (import_mode === 'openie') {
      await import_structured_payload('openie', structured_title, structured_payload_text, strategy);
      return;
    }
    await import_structured_payload('convert', structured_title, structured_payload_text, strategy);
  }

  const can_submit =
    (import_mode === 'upload' && upload_files_value.length > 0) ||
    (import_mode === 'paste' && paste_content.trim().length > 0) ||
    (import_mode === 'scan' && scan_root_path.trim().length > 0) ||
    ((import_mode === 'openie' || import_mode === 'convert') && structured_payload_text.trim().length > 0);

  const submit_label =
    import_mode === 'upload'
      ? '提交上传任务'
      : import_mode === 'paste'
        ? '提交粘贴任务'
        : import_mode === 'scan'
          ? '提交扫描任务'
          : import_mode === 'openie'
            ? '提交 OpenIE 数据'
            : '提交转换结果';

  return (
    <section className='kb-panel kb-import-panel'>
      <header className='kb-section-header'>
        <div>
          <h2>导入中心</h2>
          <p>把新内容送进知识库的入口只保留两件事：创建任务，以及跟进任务状态。</p>
        </div>
      </header>

      <div className='kb-import-shell'>
        <div className='kb-import-main'>
          <div className='kb-detail-card kb-import-stage'>
            <div className='kb-import-hero'>
              <span className='kb-context-label'>New Import</span>
              <h3>{current_mode.label}</h3>
              <p>{current_mode.description}</p>
              <div className='kb-meta-strip'>
                <span className='kb-meta-pill'>{`进行中 ${active_task_count}`}</span>
                <span className='kb-meta-pill'>{`部分完成 ${partial_task_count}`}</span>
                <span className='kb-meta-pill'>{`失败 ${failed_task_count}`}</span>
                <span className='kb-meta-pill'>{`总任务 ${tasks.length}`}</span>
              </div>
            </div>

            <div className='kb-tab-bar'>
              {IMPORT_MODES.map((mode) => (
                <button
                  className={`kb-tab-button ${mode.id === import_mode ? 'is-active' : ''}`}
                  key={mode.id}
                  onClick={() => set_import_mode(mode.id)}
                  type='button'
                >
                  <strong>{mode.label}</strong>
                  <span>{mode.description}</span>
                </button>
              ))}
            </div>

            <div className='kb-detail-card kb-import-composer'>
              <div className='kb-import-form-head'>
                <div>
                  <span className='kb-context-label'>Compose</span>
                  <h3>导入内容</h3>
                  <p>根据当前模式填写最少必要信息即可，更多细节会在后台任务里继续展开。</p>
                </div>

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
              </div>

              <div className='kb-form-grid'>
                {import_mode === 'upload' ? (
                  <label className='kb-form-field kb-form-field-wide'>
                    <span>选择文件</span>
                    <input
                      accept={SUPPORTED_UPLOAD_ACCEPT}
                      multiple
                      onChange={(event) => set_upload_files_value(Array.from(event.target.files ?? []))}
                      type='file'
                    />
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
                        placeholder='例如 D:\\docs'
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

              <div className='kb-import-hints'>
                {import_hints.map((hint) => (
                  <div className='kb-import-hint' key={hint}>
                    {hint}
                  </div>
                ))}
              </div>

              <div className='kb-import-submit-row'>
                <span className='kb-helper-text'>
                  {can_submit ? '信息已足够，可以直接提交任务。' : '先补充当前模式所需的最小输入。'}
                </span>

                <button
                  className='kb-primary-button'
                  disabled={is_submitting_import || !can_submit}
                  onClick={() => void submit_current_import()}
                  type='button'
                >
                  {is_submitting_import ? '提交中...' : submit_label}
                </button>
              </div>
            </div>
          </div>
        </div>

        <aside className='kb-import-rail'>
          <div className='kb-detail-card'>
            <span className='kb-context-label'>Task Stream</span>
            <h3>任务流</h3>
            <p>优先展示运行中的任务；旧任务保留在下面，方便继续追踪或重试。</p>
          </div>

          <div className='kb-task-list'>
            {ordered_tasks.map((task) => {
              const processed_file_count: number = count_processed_files(task);
              const problem_file_count: number = count_problem_files(task);
              const task_note = task.error ?? task.message ?? null;

              return (
                <article className='kb-task-card' key={task.id}>
                  <div className='kb-task-header'>
                    <div className='kb-task-title'>
                      <strong>{`${resolve_task_mode_label(task)}任务`}</strong>
                      <span>{`阶段：${get_step_label(task.current_step)}`}</span>
                      <span className='kb-helper-text'>{`任务 ${format_import_task_short_id(task.id)} · 创建于 ${format_import_task_timestamp(task.created_at)}`}</span>
                    </div>
                    <span className='kb-task-status'>{get_status_label(task.status)}</span>
                  </div>

                  <div className='kb-progress-track'>
                    <div className='kb-progress-fill' style={{ width: `${task.progress}%` }} />
                  </div>

                  {task_note ? <div className='kb-progress-debug'>{task_note}</div> : null}

                  <div className='kb-meta-strip'>
                    <span className='kb-meta-pill'>{`进度 ${format_progress(task.progress)}`}</span>
                    <span className='kb-meta-pill'>{`已处理 ${processed_file_count}/${task.total_files}`}</span>
                    <span className='kb-meta-pill'>{render_task_chunk_summary(task)}</span>
                    <span className='kb-meta-pill'>{`异常文件 ${problem_file_count}`}</span>
                  </div>

                  <span className='kb-helper-text'>{render_strategy_summary(task)}</span>

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
                    {task.files.slice(0, 2).map((file) => (
                      <div className='kb-task-file' key={file.id}>
                        <div className='kb-task-file-header'>
                          <strong>{file.name}</strong>
                          <span>{get_status_label(file.status)}</span>
                        </div>
                        <span>{`阶段：${get_step_label(file.current_step)}`}</span>
                        <div className='kb-progress-track is-compact'>
                          <div className='kb-progress-fill' style={{ width: `${file.progress}%` }} />
                        </div>
                        {resolve_progress_debug(file.metadata) ? (
                          <div className='kb-progress-debug is-compact'>{resolve_progress_debug(file.metadata)}</div>
                        ) : null}
                        <span>{render_file_progress_summary(file)}</span>
                        <span>{render_file_strategy_summary(file)}</span>
                        {file.error ? <span className='kb-helper-text'>{`说明：${file.error}`}</span> : null}
                      </div>
                    ))}
                    {task.files.length > 2 ? <span className='kb-helper-text'>{`还有 ${task.files.length - 2} 个文件`}</span> : null}
                  </div>
                </article>
              );
            })}

            {!ordered_tasks.length ? <div className='kb-empty-card'>暂时还没有导入任务。</div> : null}
          </div>
        </aside>
      </div>
    </section>
  );
}
