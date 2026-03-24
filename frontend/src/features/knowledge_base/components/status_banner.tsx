/**
 * 模块名称：features/knowledge_base/components/status_banner
 * 主要功能：渲染知识库工作台顶部状态横幅。
 */

import type { ThemeMode } from '../../../theme';

interface StatusBannerProps {
  message: string;
  error: string | null;
  document_count: number;
  active_job_count: number;
  node_count: number;
  edge_count: number;
  highlighted_node_count: number;
  theme_mode: ThemeMode;
  set_theme_mode: (theme_mode: ThemeMode) => void;
}

export function StatusBanner(props: StatusBannerProps) {
  const {
    message,
    error,
    document_count,
    active_job_count,
    node_count,
    edge_count,
    highlighted_node_count,
    theme_mode,
    set_theme_mode,
  } = props;

  return (
    <section className='hero'>
      <div>
        <p className='eyebrow'>本地知识库工作台</p>
        <h1>上传文档，手动开始抽取，然后直接向知识图谱提问。</h1>
        <p className='hero-copy'>
          这个工作区把自然分段、向量检索、实体关系抽取和图谱排序串起来，让文档从“文件”变成可浏览、可追溯、可问答的知识结构。
        </p>
      </div>
      <div className='hero-status'>
        <div className='theme-switcher'>
          <span className='status-label'>主题</span>
          <div className='theme-toggle-group'>
            <button
              className={theme_mode === 'system' ? 'theme-toggle active' : 'theme-toggle'}
              type='button'
              onClick={() => set_theme_mode('system')}
            >
              跟随系统
            </button>
            <button
              className={theme_mode === 'light' ? 'theme-toggle active' : 'theme-toggle'}
              type='button'
              onClick={() => set_theme_mode('light')}
            >
              明亮
            </button>
            <button
              className={theme_mode === 'dark' ? 'theme-toggle active' : 'theme-toggle'}
              type='button'
              onClick={() => set_theme_mode('dark')}
            >
              暗色
            </button>
          </div>
        </div>

        <div>
          <span className='status-label'>当前状态</span>
          <strong>{message}</strong>
          {error ? <p className='error-message'>{error}</p> : null}
        </div>

        <div className='hero-metrics'>
          <article>
            <span>文档数</span>
            <strong>{document_count}</strong>
          </article>
          <article>
            <span>活动任务</span>
            <strong>{active_job_count}</strong>
          </article>
          <article>
            <span>图谱规模</span>
            <strong>
              {node_count} / {edge_count}
            </strong>
          </article>
          <article>
            <span>高亮节点</span>
            <strong>{highlighted_node_count}</strong>
          </article>
        </div>
      </div>
    </section>
  );
}
