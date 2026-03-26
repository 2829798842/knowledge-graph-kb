/**
 * Workspace shell for the knowledge-base frontend.
 */

import type { ResolvedTheme, ThemeMode } from '../../theme';
import { WorkspaceBody } from './shared/components/workspace_body';
import { WorkspaceHeader } from './shared/components/workspace_header';
import { WorkspaceOverview } from './shared/components/workspace_overview';
import { KnowledgeBaseWorkspaceProvider } from './shared/context/knowledge_base_workspace_context';
import './shared/styles/knowledge_base_workspace.css';

interface KnowledgeBaseWorkspaceProps {
  theme_mode: ThemeMode;
  resolved_theme: ResolvedTheme;
  set_theme_mode: (theme_mode: ThemeMode) => void;
}

function KnowledgeBaseWorkspaceShell(props: KnowledgeBaseWorkspaceProps) {
  const { theme_mode, resolved_theme, set_theme_mode } = props;

  return (
    <main className='kb-shell'>
      <WorkspaceOverview set_theme_mode={set_theme_mode} theme_mode={theme_mode} />

      <section className='kb-shell-main'>
        <WorkspaceHeader />

        <section className='kb-workspace-body'>
          <WorkspaceBody resolved_theme={resolved_theme} />
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
