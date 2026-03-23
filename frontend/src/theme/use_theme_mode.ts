/**
 * 模块名称：theme/use_theme_mode
 * 主要功能：管理主题模式、跟随系统主题并同步到文档根节点。
 */

import { useEffect, useState } from 'react';

import type { ResolvedTheme, ThemeMode } from './theme_types';

const THEME_STORAGE_KEY: string = 'knowledge_graph_kb:theme_mode';

/**
 * 读取持久化的主题模式。
 *
 * @returns 当前保存的主题模式。
 */
function read_theme_mode(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'system';
  }

  const stored_theme_mode: string | null = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (stored_theme_mode === 'light' || stored_theme_mode === 'dark' || stored_theme_mode === 'system') {
    return stored_theme_mode;
  }
  return 'system';
}

/**
 * 获取系统主题。
 *
 * @returns 解析后的系统主题。
 */
function get_system_theme(): ResolvedTheme {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'light';
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * 解析当前应生效的主题。
 *
 * @param theme_mode - 当前主题模式。
 * @returns 实际生效的主题。
 */
function resolve_theme(theme_mode: ThemeMode): ResolvedTheme {
  if (theme_mode === 'system') {
    return get_system_theme();
  }
  return theme_mode;
}

/**
 * 管理主题模式与系统主题跟随。
 *
 * @returns 主题模式、解析后的主题以及更新函数。
 */
export function use_theme_mode(): {
  theme_mode: ThemeMode;
  resolved_theme: ResolvedTheme;
  set_theme_mode: (theme_mode: ThemeMode) => void;
} {
  const [theme_mode, set_theme_mode_state] = useState<ThemeMode>(() => read_theme_mode());
  const [resolved_theme, set_resolved_theme] = useState<ResolvedTheme>(() => resolve_theme(read_theme_mode()));

  useEffect(() => {
    const next_resolved_theme: ResolvedTheme = resolve_theme(theme_mode);
    set_resolved_theme(next_resolved_theme);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme_mode);
    }
  }, [theme_mode]);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = resolved_theme;
      document.documentElement.style.colorScheme = resolved_theme;
    }
  }, [resolved_theme]);

  useEffect(() => {
    if (theme_mode !== 'system' || typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }

    const media_query: MediaQueryList = window.matchMedia('(prefers-color-scheme: dark)');

    /**
     * 在系统主题变化时同步解析后的主题。
     */
    function handle_change(): void {
      set_resolved_theme(media_query.matches ? 'dark' : 'light');
    }

    handle_change();
    if (typeof media_query.addEventListener === 'function') {
      media_query.addEventListener('change', handle_change);
    } else {
      media_query.addListener(handle_change);
    }
    return () => {
      if (typeof media_query.removeEventListener === 'function') {
        media_query.removeEventListener('change', handle_change);
      } else {
        media_query.removeListener(handle_change);
      }
    };
  }, [theme_mode]);

  /**
   * 更新当前主题模式。
   *
   * @param next_theme_mode - 新的主题模式。
   */
  function set_theme_mode(next_theme_mode: ThemeMode): void {
    set_theme_mode_state(next_theme_mode);
  }

  return {
    theme_mode,
    resolved_theme,
    set_theme_mode,
  };
}
