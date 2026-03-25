/**
 * Knowledge-base workspace shell.
 */

import type { ResolvedTheme, ThemeMode } from '../../theme';
import { WorkspaceBody } from './shared/components/workspace_body';
import { WorkspaceHeader } from './shared/components/workspace_header';
import { KnowledgeBaseWorkspaceProvider } from './shared/context/knowledge_base_workspace_context';
import './shared/styles/knowledge_base_workspace.css';

interface KnowledgeBaseWorkspaceProps {
  theme_mode: ThemeMode;
  resolved_theme: ResolvedTheme;
  set_theme_mode: (theme_mode: ThemeMode) => void;
}

function KnowledgeBaseWorkspaceShell(props: KnowledgeBaseWorkspaceProps) {
  const { resolved_theme } = props;

  return (
    <main className='kb-shell'>
      <WorkspaceHeader />

      <section className='kb-workspace-body'>
        <WorkspaceBody resolved_theme={resolved_theme} />
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
