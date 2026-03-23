/**
 * 模块名称：features/knowledge_base/components/status_banner/status_banner
 * 主要功能：渲染页面顶部状态横幅与主题切换控件。
 */

import type { ThemeMode } from '../../../../theme/theme_types';

/**
 * 状态横幅属性。
 */
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

/**
 * 渲染顶部状态横幅。
 *
 * @param props - 组件属性。
 * @returns 顶部状态横幅组件。
 */
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
        <p className='eyebrow'>Knowledge Graph KB</p>
        <h1>导入文档、查看连接，并直接向图谱提问。</h1>
        <p className='hero-copy'>
          这个工作区会把 OpenAI 嵌入、力导向图和个性化 PageRank 结合起来，把个人文档整理成可以检索、可追溯的知识地图。
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
              明色
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
          <span className='status-label'>状态</span>
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
