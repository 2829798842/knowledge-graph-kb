import { useEffect, useMemo, useRef, type CSSProperties, type PointerEvent as ReactPointerEvent } from 'react';

import type { ResolvedTheme, ThemeMode } from '../../theme';
import { WorkspaceBody } from './shared/components/workspace_body';
import { WorkspaceHeader } from './shared/components/workspace_header';
import { WorkspaceOverview } from './shared/components/workspace_overview';
import { KnowledgeBaseWorkspaceProvider } from './shared/context/knowledge_base_workspace_context';
import { use_workspace_shell } from './shared/hooks/use_workspace_shell';
import './shared/styles/knowledge_base_workspace.css';

interface KnowledgeBaseWorkspaceProps {
  theme_mode: ThemeMode;
  resolved_theme: ResolvedTheme;
  set_theme_mode: (theme_mode: ThemeMode) => void;
}

const MIN_SIDEBAR_WIDTH = 220;
const MAX_SIDEBAR_WIDTH = 272;

function clamp_sidebar_width(value: number): number {
  return Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, value));
}

function KnowledgeBaseWorkspaceShell(props: KnowledgeBaseWorkspaceProps) {
  const { resolved_theme } = props;
  const { sidebar_collapsed, set_sidebar_collapsed, sidebar_width, set_sidebar_width } = use_workspace_shell();
  const shell_ref = useRef<HTMLElement | null>(null);
  const drag_state_ref = useRef<{ offset_left: number } | null>(null);

  useEffect(() => {
    function handle_pointer_move(event: PointerEvent): void {
      if (!drag_state_ref.current) {
        return;
      }

      set_sidebar_width(clamp_sidebar_width(event.clientX - drag_state_ref.current.offset_left));
    }

    function handle_pointer_up(): void {
      drag_state_ref.current = null;
      document.body.classList.remove('kb-is-resizing');
    }

    window.addEventListener('pointermove', handle_pointer_move);
    window.addEventListener('pointerup', handle_pointer_up);

    return () => {
      window.removeEventListener('pointermove', handle_pointer_move);
      window.removeEventListener('pointerup', handle_pointer_up);
      document.body.classList.remove('kb-is-resizing');
    };
  }, [set_sidebar_width]);

  const shell_style = useMemo(
    () =>
      ({
        '--kb-sidebar-width': `${clamp_sidebar_width(sidebar_width)}px`,
      }) as CSSProperties,
    [sidebar_width],
  );

  function handle_toggle_sidebar(): void {
    set_sidebar_collapsed((current_value) => !current_value);
  }

  function handle_start_resize(event: ReactPointerEvent<HTMLButtonElement>): void {
    if (sidebar_collapsed) {
      return;
    }

    const shell_bounds = shell_ref.current?.getBoundingClientRect();
    if (!shell_bounds) {
      return;
    }

    drag_state_ref.current = { offset_left: shell_bounds.left };
    document.body.classList.add('kb-is-resizing');
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  return (
    <main className='kb-shell-frame'>
      <div aria-hidden='true' className='kb-shell-ambient kb-shell-ambient-a' />
      <div aria-hidden='true' className='kb-shell-ambient kb-shell-ambient-b' />
      <div aria-hidden='true' className='kb-shell-ambient kb-shell-ambient-c' />

      <section
        className={`kb-shell ${sidebar_collapsed ? 'is-sidebar-collapsed' : ''}`}
        ref={shell_ref}
        style={shell_style}
      >
        {!sidebar_collapsed ? (
          <div className='kb-sidebar-shell'>
            <WorkspaceOverview collapsed={false} />
            <button
              aria-label='调整侧栏宽度'
              className='kb-sidebar-resizer'
              onPointerDown={handle_start_resize}
              type='button'
            />
          </div>
        ) : null}

        <section className='kb-shell-main'>
          <WorkspaceHeader on_toggle_sidebar={handle_toggle_sidebar} sidebar_collapsed={sidebar_collapsed} />
          <section className='kb-workspace-body'>
            <WorkspaceBody resolved_theme={resolved_theme} />
          </section>
        </section>
      </section>
    </main>
  );
}

export function KnowledgeBaseWorkspace(props: KnowledgeBaseWorkspaceProps) {
  return (
    <KnowledgeBaseWorkspaceProvider>
      <KnowledgeBaseWorkspaceShell {...props} />
    </KnowledgeBaseWorkspaceProvider>
  );
}
