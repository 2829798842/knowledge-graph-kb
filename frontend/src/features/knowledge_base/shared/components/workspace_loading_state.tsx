interface WorkspaceLoadingStateProps {
  title: string;
  description: string;
}

export function WorkspaceLoadingState(props: WorkspaceLoadingStateProps) {
  const { title, description } = props;

  return (
    <div className='kb-loading-state'>
      <div className='kb-loading-copy'>
        <span className='kb-context-label'>正在加载工作区</span>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>

      <div className='kb-loading-surface'>
        <div className='kb-loading-bar is-wide' />
        <div className='kb-loading-bar' />
        <div className='kb-loading-grid'>
          <div className='kb-loading-card' />
          <div className='kb-loading-card' />
          <div className='kb-loading-card' />
        </div>
      </div>
    </div>
  );
}
