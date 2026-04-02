import { useMemo, useState } from 'react';

import type {
  AnswerExecutionRecord,
  RetrievalTraceLaneRecord,
  RetrievalTraceRecord,
} from '../../shared/types/knowledge_base_types';

interface ChatDiagnosticsSectionProps {
  execution: AnswerExecutionRecord | null;
  retrieval_trace: RetrievalTraceRecord | null;
}

const TRACE_LABELS: Record<keyof Omit<RetrievalTraceRecord, 'total_ms'>, string> = {
  structured: '结构化检索',
  vector: '向量检索',
  fusion: '融合排序',
  ppr: '图谱扩散',
};

const SKIPPED_REASON_LABELS: Record<string, string> = {
  no_graph_hits: '没有图谱命中',
  no_sources_selected: '未选择来源',
  no_vector_hits: '没有向量命中',
  no_structured_hits: '没有结构化命中',
  not_executed: '未执行',
};

function lane_status(lane: RetrievalTraceLaneRecord): string {
  if (lane.executed) {
    return '已执行';
  }
  if (!lane.skipped_reason) {
    return '已跳过';
  }
  return `已跳过：${SKIPPED_REASON_LABELS[lane.skipped_reason] ?? lane.skipped_reason}`;
}

function lane_summary(lane: RetrievalTraceLaneRecord): string {
  const paragraph_text = lane.top_paragraph_ids.length
    ? `命中段落：${lane.top_paragraph_ids.join('、')}`
    : '没有命中段落';
  return `命中 ${lane.hit_count} 条，耗时 ${lane.latency_ms} ms，${paragraph_text}`;
}

export function ChatDiagnosticsSection(props: ChatDiagnosticsSectionProps) {
  const { execution, retrieval_trace } = props;
  const [open, set_open] = useState(false);

  const trace_rows = useMemo(
    () =>
      retrieval_trace
        ? (Object.entries(TRACE_LABELS).map(([key, label]) => ({
            key,
            label,
            lane: retrieval_trace[key as keyof typeof TRACE_LABELS],
          })) as Array<{ key: string; label: string; lane: RetrievalTraceLaneRecord }>)
        : [],
    [retrieval_trace],
  );

  if (!execution && !retrieval_trace) {
    return null;
  }

  return (
    <section className='kb-chat-diagnostics'>
      <button className='kb-chat-sources-toggle' onClick={() => set_open((current) => !current)} type='button'>
        <strong>{open ? '隐藏执行信息' : '显示执行信息'}</strong>
        <span>诊断</span>
      </button>

      {open ? (
        <div className='kb-chat-diagnostics-body'>
          {execution ? (
            <article className='kb-chat-diagnostics-trace-row'>
              <strong>执行摘要</strong>
              <span>{`状态：${execution.status}`}</span>
              <span>{`命中段落：${execution.matched_paragraph_count}`}</span>
              <span>{execution.model_invoked ? '已调用模型生成回答' : '未调用模型'}</span>
              <span>{execution.message}</span>
            </article>
          ) : null}

          {trace_rows.length ? (
            <section className='kb-chat-diagnostics-trace'>
              <strong>检索路径</strong>
              {trace_rows.map(({ key, label, lane }) => (
                <article className='kb-chat-diagnostics-trace-row' key={key}>
                  <strong>{label}</strong>
                  <span>{lane_status(lane)}</span>
                  <span>{lane_summary(lane)}</span>
                </article>
              ))}
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
