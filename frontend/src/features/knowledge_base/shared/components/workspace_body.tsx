/**
 * Route workspace body.
 */

import { Suspense, lazy, useEffect, useMemo, useState } from 'react';

import type { ResolvedTheme } from '../../../../theme';
import { WORKSPACE_TABS } from '../config/ui_constants';
import { use_workspace_shell } from '../hooks/use_workspace_shell';
import type { WorkspaceTab } from '../types/knowledge_base_types';
import { WorkspaceLoadingState } from './workspace_loading_state';

interface WorkspaceBodyProps {
  resolved_theme: ResolvedTheme;
}

const ImportCenterPanel = lazy(async () => ({
  default: (await import('../../import_center/components/import_center_panel')).ImportCenterPanel,
}));

const ModelConfigPanel = lazy(async () => ({
  default: (await import('../../model_config/components/model_config_panel')).ModelConfigPanel,
}));

const GraphBrowserPanel = lazy(async () => ({
  default: (await import('../../graph_browser/components/graph_browser_panel')).GraphBrowserPanel,
}));

const QueryStudioPanel = lazy(async () => ({
  default: (await import('../../query_studio/components/query_studio_panel')).QueryStudioPanel,
}));

const SourceBrowserPanel = lazy(async () => ({
  default: (await import('../../source_browser/components/source_browser_panel')).SourceBrowserPanel,
}));

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
            <Suspense
              fallback={<WorkspaceLoadingState description={tab.description} title={tab.label} />}
            >
              {panels[tab.id]}
            </Suspense>
          </section>
        );
      })}
    </div>
  );
}
