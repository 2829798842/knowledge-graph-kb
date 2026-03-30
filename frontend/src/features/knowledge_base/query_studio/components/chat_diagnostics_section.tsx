import { useMemo, useState } from 'react';

import type { AnswerExecutionRecord, RetrievalTraceRecord } from '../../shared/types/knowledge_base_types';

interface ChatDiagnosticsSectionProps {
  execution: AnswerExecutionRecord | null;
  retrieval_trace: RetrievalTraceRecord | null;
}

function format_latency(value: number): string {
  if (!Number.isFinite(value)) {
    return '-';
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ms`;
}

export function ChatDiagnosticsSection(props: ChatDiagnosticsSectionProps) {
  const { execution, retrieval_trace } = props;
  const [is_open, set_is_open] = useState(false);

  const trace_rows = useMemo(() => {
    if (!retrieval_trace) {
      return [];
    }
    return [
      ['Structured', retrieval_trace.structured],
      ['Vector', retrieval_trace.vector],
      ['Fusion', retrieval_trace.fusion],
      ['PPR', retrieval_trace.ppr],
    ] as const;
  }, [retrieval_trace]);

  if (!execution && !retrieval_trace) {
    return null;
  }

  return (
    <div className='kb-chat-diagnostics'>
      <button className='kb-chat-sources-toggle' onClick={() => set_is_open((value) => !value)} type='button'>
        <strong>{is_open ? '隐藏执行信息' : '显示执行信息'}</strong>
        <span>{execution ? execution.status : 'trace'}</span>
      </button>

      {is_open ? (
        <div className='kb-chat-diagnostics-body'>
          {execution ? (
            <article className='kb-chat-source-card'>
              <div className='kb-chat-source-head'>
                <strong>执行摘要</strong>
                <span>{execution.retrieval_mode}</span>
              </div>
              <div className='kb-chat-source-meta'>
                <span>{`状态：${execution.status}`}</span>
                <span>{`命中文段：${execution.matched_paragraph_count}`}</span>
                <span>{execution.model_invoked ? '已调用模型生成回答' : '未调用模型'}</span>
              </div>
              <div className='kb-chat-bubble-body'>{execution.message}</div>
            </article>
          ) : null}

          {retrieval_trace ? (
            <article className='kb-chat-source-card'>
              <div className='kb-chat-source-head'>
                <strong>Retrieval Trace</strong>
                <span>{`总耗时 ${format_latency(retrieval_trace.total_ms)}`}</span>
              </div>
              <div className='kb-chat-diagnostics-trace'>
                {trace_rows.map(([label, lane]) => (
                  <div className='kb-chat-diagnostics-trace-row' key={label}>
                    <strong>{label}</strong>
                    <span>{lane.executed ? '已执行' : `已跳过${lane.skipped_reason ? `：${lane.skipped_reason}` : ''}`}</span>
                    <span>{`命中 ${lane.hit_count}`}</span>
                    <span>{`耗时 ${format_latency(lane.latency_ms)}`}</span>
                    <span>{lane.top_paragraph_ids.length ? `Top IDs: ${lane.top_paragraph_ids.join(', ')}` : '无段落 ID'}</span>
                  </div>
                ))}
              </div>
            </article>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
