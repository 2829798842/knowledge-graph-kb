/**
 * Route workspace body.
 */

import { useEffect, useMemo, useState } from 'react';

import type { ResolvedTheme } from '../../../../theme';
import { GraphBrowserPanel } from '../../graph_browser/components/graph_browser_panel';
import { ImportCenterPanel } from '../../import_center/components/import_center_panel';
import { ModelConfigPanel } from '../../model_config/components/model_config_panel';
import { QueryStudioPanel } from '../../query_studio/components/query_studio_panel';
import { SourceBrowserPanel } from '../../source_browser/components/source_browser_panel';
import { WORKSPACE_TABS } from '../config/ui_constants';
import { use_workspace_shell } from '../hooks/use_workspace_shell';
import type { WorkspaceTab } from '../types/knowledge_base_types';

interface WorkspaceBodyProps {
  resolved_theme: ResolvedTheme;
}

export function WorkspaceBody(props: WorkspaceBodyProps) {
  const { resolved_theme } = props;
  const { active_workspace } = use_workspace_shell();
  const [mounted_workspaces, set_mounted_workspaces] = useState<WorkspaceTab[]>(['import']);

  useEffect(() => {
    set_mounted_workspaces((current_tabs) =>
      current_tabs.includes(active_workspace) ? current_tabs : [...current_tabs, active_workspace],
    );
  }, [active_workspace]);

  const panels: Record<WorkspaceTab, JSX.Element> = useMemo(
    () => ({
      import: <ImportCenterPanel />,
      config: <ModelConfigPanel />,
      graph: <GraphBrowserPanel resolved_theme={resolved_theme} />,
      query: <QueryStudioPanel />,
      source: <SourceBrowserPanel />,
    }),
    [resolved_theme],
  );

  return (
    <div className='kb-workspace-stack'>
      {WORKSPACE_TABS.map((tab) => {
        if (!mounted_workspaces.includes(tab.id)) {
          return null;
        }

        const is_active: boolean = active_workspace === tab.id;
        return (
          <section
            aria-hidden={!is_active}
            className='kb-workspace-view'
            hidden={!is_active}
            key={tab.id}
          >
            {panels[tab.id]}
          </section>
        );
      })}
    </div>
  );
}
