import { useEffect, useState } from 'react'

import { fetchEdge, toApiError } from '../api/client.ts'
import type { EdgeDetail } from '../api/types.ts'

export interface EdgeInspectorProps {
  circuitId: string
  pre: string
  post: string
  onSelectNeuron: (neuronId: string) => void
}

type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; edge: EdgeDetail }

export function EdgeInspector({ circuitId, pre, post, onSelectNeuron }: EdgeInspectorProps) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: 'loading' })
    fetchEdge(circuitId, pre, post, controller.signal)
      .then((edge) => setState({ kind: 'ready', edge }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({ kind: 'error', message: toApiError(error).message })
      })
    return () => controller.abort()
  }, [circuitId, pre, post])

  if (state.kind === 'loading') return <p className="muted">Loading edge…</p>
  if (state.kind === 'error') {
    return (
      <p className="alert" role="alert" data-testid="edge-inspector-error">
        {state.message}
      </p>
    )
  }
  const edge = state.edge
  const weight = edge.simulation_weight
  return (
    <div className="inspector-edge" data-testid="edge-inspector" data-pre={pre} data-post={post}>
      <header className="inspector-neuron__head">
        <p className="panel__kicker">Edge</p>
        <h3 className="mono">
          {edge.pre.neuron_id} → {edge.post.neuron_id}
        </h3>
        <p>
          <span className="tag tag--bio" data-testid="edge-label">
            {edge.label}
          </span>
        </p>
      </header>
      <dl className="kv kv--tight">
        <dt>FROM</dt>
        <dd>
          <button type="button" className="linklike mono" onClick={() => onSelectNeuron(edge.pre.neuron_id)}>
            {edge.pre.neuron_id}
          </button>{' '}
          <span className="muted">{edge.pre.cell_type ?? 'cell type not available'}</span>
        </dd>
        <dt>TO</dt>
        <dd>
          <button type="button" className="linklike mono" onClick={() => onSelectNeuron(edge.post.neuron_id)}>
            {edge.post.neuron_id}
          </button>{' '}
          <span className="muted">{edge.post.cell_type ?? 'cell type not available'}</span>
        </dd>
        <dt>synapse_count</dt>
        <dd>
          <span className="mono" data-testid="edge-synapse-count">
            {edge.synapse_count}
          </span>
          <br />
          <span className="muted">{edge.synapse_count_label}</span>
        </dd>
        <dt>dataset</dt>
        <dd>
          {edge.dataset} {edge.dataset_version}
        </dd>
        <dt>circuit_id</dt>
        <dd className="mono">{edge.circuit_id}</dd>
        <dt>circuit_hash</dt>
        <dd className="mono" data-testid="edge-circuit-hash" style={{ overflowWrap: 'anywhere' }}>
          {edge.circuit_hash}
        </dd>
      </dl>
      {weight && (
        <section className="meta meta--sim" data-testid="edge-simulation-weight">
          <p className="meta__label">
            <span className="tag tag--simulated">COMPUTATIONAL SIMULATION WEIGHT</span>
          </p>
          <dl className="kv kv--tight">
            <dt>simulation weight</dt>
            <dd className="mono">{weight.value.toFixed(4)}</dd>
            <dt>transformation</dt>
            <dd className="mono">
              {weight.weight_transform}(synapse_count) × {weight.weight_scale}
            </dd>
          </dl>
          <p className="muted">
            synapse_count: <strong>Biological structural observation</strong> · simulation weight:{' '}
            <strong>Computational transformation</strong> — {weight.parameter_label}
          </p>
        </section>
      )}
    </div>
  )
}
