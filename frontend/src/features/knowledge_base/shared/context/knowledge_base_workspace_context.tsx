/**
 * Workspace provider and typed context accessors.
 */

import { createContext, type ReactNode, useContext } from 'react';

import {
  type KnowledgeBaseWorkspaceStore,
  use_knowledge_base_workspace_store,
} from '../hooks/use_knowledge_base_workspace';

const KnowledgeBaseWorkspaceContext = createContext<KnowledgeBaseWorkspaceStore | null>(null);

interface KnowledgeBaseWorkspaceProviderProps {
  children: ReactNode;
}

export function KnowledgeBaseWorkspaceProvider(props: KnowledgeBaseWorkspaceProviderProps) {
  const { children } = props;
  const workspace = use_knowledge_base_workspace_store();

  return (
    <KnowledgeBaseWorkspaceContext.Provider value={workspace}>
      {children}
    </KnowledgeBaseWorkspaceContext.Provider>
  );
}

export function use_knowledge_base_workspace_context(): KnowledgeBaseWorkspaceStore {
  const context = useContext(KnowledgeBaseWorkspaceContext);
  if (context === null) {
    throw new Error('use_knowledge_base_workspace_context must be used within KnowledgeBaseWorkspaceProvider');
  }
  return context;
}
