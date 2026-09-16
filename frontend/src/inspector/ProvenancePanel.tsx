import type { CircuitProvenance } from '../api/types.ts'

const fmt = (n: number | null | undefined): string => (n === null || n === undefined ? 'Not available' : n.toLocaleString('en-US'))

export function ProvenancePanel({ provenance }: { provenance: CircuitProvenance }) {
  const source = provenance.source_dataset
  return (
    <details className="prov" data-testid="provenance-panel" open>
      <summary className="prov__summary">
        Provenance <span className="tag tag--bio">WHERE THIS COMES FROM</span>
      </summary>
      <div className="prov__body">
        <dl className="kv kv--tight">
          <dt>Dataset</dt>
          <dd data-testid="prov-dataset">
            {source ? `${source.name} ${source.version}` : `${provenance.dataset} ${provenance.dataset_version}`}
          </dd>
          <dt>Source dataset count</dt>
          <dd data-testid="prov-source-count">≈{fmt(source?.official_neuron_count)} neurons</dd>
          <dt>Canonical graph</dt>
          <dd>
            <code>{provenance.canonical_graph.selection_rule}</code>
            <br />
            <span data-testid="prov-canonical-neurons">{fmt(provenance.canonical_graph.neuron_count)}</span> neurons ·{' '}
            <span data-testid="prov-canonical-connections">{fmt(provenance.canonical_graph.connection_count)}</span> directed
            connections
          </dd>
          <dt>Loaded circuit</dt>
          <dd data-testid="prov-loaded">
            <code>{provenance.circuit_id}</code> · {fmt(provenance.loaded_circuit['neurons'])} neurons ·{' '}
            {fmt(provenance.loaded_circuit['edges'])} edges
          </dd>
          <dt>Circuit hash</dt>
          <dd className="mono" data-testid="prov-hash" style={{ overflowWrap: 'anywhere' }}>
            {provenance.circuit_hash}
            <br />
            <span className="muted">{provenance.circuit_verified ? 'verified against the configured expected hash' : 'NOT verified'}</span>
          </dd>
          <dt>Biological status</dt>
          <dd data-testid="prov-status">
            <strong>{provenance.biological_status ?? 'Not available'}</strong>
            {provenance.research_document ? (
              <>
                {' '}
                · <code>{provenance.research_document}</code>
              </>
            ) : null}
          </dd>
          <dt>License</dt>
          <dd>{provenance.license ?? 'Not available'}</dd>
          <dt>Official source</dt>
          <dd style={{ overflowWrap: 'anywhere' }}>
            {provenance.source_page ? (
              <a href={provenance.source_page} target="_blank" rel="noreferrer">
                {provenance.source_page}
              </a>
            ) : (
              'Not available'
            )}
            {provenance.download_url ? (
              <>
                <br />
                <code>{provenance.download_url}</code>
              </>
            ) : null}
          </dd>
          <dt>Raw files (sha256)</dt>
          <dd>
            {provenance.raw_files.length === 0
              ? 'Not available'
              : provenance.raw_files.map((file) => (
                  <div key={file.role} className="mono" title={file.path}>
                    {file.role}: {file.sha256 ? `${file.sha256.slice(0, 16)}…` : 'Not available'}
                  </div>
                ))}
          </dd>
          <dt>Extracted</dt>
          <dd className="mono">
            {provenance.extracted_at} · extractor {provenance.extractor_version}
          </dd>
        </dl>
        <p className="prov__note muted" data-testid="prov-note">
          {provenance.canonical_graph_note}
        </p>
        {provenance.citations.length > 0 && (
          <>
            <p className="legend__title">Citations (escape_v1 research record)</p>
            <ul className="how__list how__list--citations" data-testid="prov-citations">
              {provenance.citations.map((c) => (
                <li key={c.key}>
                  {c.authors} ({c.year}). <em>{c.title}</em>. {c.venue}.{' '}
                  {c.url ? (
                    <a href={c.url} target="_blank" rel="noreferrer">
                      {c.doi ? `doi:${c.doi}` : 'link'}
                    </a>
                  ) : c.doi ? (
                    <code>doi:{c.doi}</code>
                  ) : null}{' '}
                  <span className="muted">— {c.claim} [{c.confidence}]</span>
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="disclaimer">{provenance.disclaimer}</p>
      </div>
    </details>
  )
}
