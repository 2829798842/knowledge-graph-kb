interface MetadataRowsProps {
  rows: [string, string][];
}

interface JsonDetailsProps {
  title: string;
  value: Record<string, unknown>;
}

export function MetadataRows(props: MetadataRowsProps) {
  const { rows } = props;

  if (!rows.length) {
    return null;
  }

  return (
    <div className='kb-graph-metadata-list'>
      {rows.map(([label, value]) => (
        <div className='kb-graph-metadata-row' key={`${label}-${value}`}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

export function JsonDetails(props: JsonDetailsProps) {
  const { title, value } = props;

  if (!Object.keys(value).length) {
    return null;
  }

  return (
    <details className='kb-graph-json-block'>
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
