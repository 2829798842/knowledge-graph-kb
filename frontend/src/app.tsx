/**
 * 模块名称：app
 * 主要功能：提供前端应用根入口，并挂载全局主题状态。
 */

import { KnowledgeBaseWorkspace } from './features/knowledge_base';
import { use_theme_mode } from './theme';

/**
 * 渲染应用首页。
 *
 * @returns 应用首页组件。
 */
export default function App() {
  const { theme_mode, resolved_theme, set_theme_mode } = use_theme_mode();

  return (
    <KnowledgeBaseWorkspace
      theme_mode={theme_mode}
      resolved_theme={resolved_theme}
      set_theme_mode={set_theme_mode}
    />
  );
}
