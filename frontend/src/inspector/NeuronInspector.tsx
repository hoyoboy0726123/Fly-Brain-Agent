import { useEffect, useState } from 'react'

import { fetchNeighbors, fetchNeuron, toApiError } from '../api/client.ts'
import type { NeighborRecord, NeighborsResponse, NeuronDetail } from '../api/types.ts'
import { cellTypeDescription } from './cellTypeStyle.ts'
import type { NeuronSimState } from './useReplay.ts'

export interface NeuronInspectorProps {
  circuitId: string
  neuronId: string
  simState: NeuronSimState | null
  replayStep: number
  replayAvailable: boolean
  highlightMode: 'upstream' | 'downstream' | null
  onHighlight: (mode: 'upstream' | 'downstream' | null) => void
  onSelectNeuron: (neuronId: string) => void
  onSelectEdge: (pre: string, post: string) => void
}

type Loaded = { detail: NeuronDetail; neighbors: NeighborsResponse }
type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; data: Loaded }

const NA = 'Not available'
const LIST_LIMIT = 40

function value(text: string | null | undefined): string {
  return text === null || text === undefined || text === '' ? NA : text
}

function NeighborTable({
  title,
  list,
  side,
  onSelectNeuron,
  onSelectEdge,
}: {
  title: string
  list: { total: number; items: NeighborRecord[] } | null
  side: 'upstream' | 'downstream'
  onSelectNeuron: (id: string) => void
  onSelectEdge: (pre: string, post: string) => void
}) {
  const [showAll, setShowAll] = useState(false)
  const items = list?.items ?? []
  const shown = showAll ? items : items.slice(0, LIST_LIMIT)
  return (
    <div className="neighbors" data-testid={`neighbors-${side}`} data-total={list?.total ?? 0}>
      <p className="neighbors__title">
        {title} <span className="mono muted">({list?.total ?? 0})</span>
      </p>
      {items.length === 0 ? (
        <p className="muted">none within the loaded circuit</p>
      ) : (
        <table className="neighbors__table">
          <thead>
            <tr>
              <th>neuron_id</th>
              <th>cell_type</th>
              <th>synapses</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={row.neuron_id} data-testid={`neighbor-${side}-${row.neuron_id}`}>
                <td>
                  <button type="button" className="linklike mono" onClick={() => onSelectNeuron(row.neuron_id)}>
                    {row.neuron_id}
                  </button>
                </td>
                <td>{value(row.cell_type)}</td>
                <td className="mono">{row.synapse_count}</td>
                <td>
                  <button
                    type="button"
                    className="linklike"
                    onClick={() => onSelectEdge(row.pre_neuron_id, row.post_neuron_id)}
                    data-testid={`neighbor-edge-${row.pre_neuron_id}-${row.post_neuron_id}`}
                  >
                    edge
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {items.length > LIST_LIMIT && (
        <button type="button" className="linklike" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'show fewer' : `show all ${items.length}`}
        </button>
      )}
    </div>
  )
}

export function NeuronInspector(props: NeuronInspectorProps) {
  const { circuitId, neuronId, simState, replayStep, replayAvailable, highlightMode } = props
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: 'loading' })
    Promise.all([fetchNeuron(circuitId, neuronId, controller.signal), fetchNeighbors(circuitId, neuronId, controller.signal)])
      .then(([detail, neighbors]) => setState({ kind: 'ready', data: { detail, neighbors } }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({ kind: 'error', message: toApiError(error).message })
      })
    return () => controller.abort()
  }, [circuitId, neuronId])

  if (state.kind === 'loading') {
    return (
      <p className="muted" data-testid="neuron-inspector-loading">
        Loading neuron {neuronId}…
      </p>
    )
  }
  if (state.kind === 'error') {
    return (
      <p className="alert" role="alert" data-testid="neuron-inspector-error">
        {state.message}
      </p>
    )
  }
  const { detail, neighbors } = state.data
  const bio = detail.biological
  const circuit = detail.circuit

  return (
    <div className="inspector-neuron" data-testid="neuron-inspector" data-neuron-id={neuronId}>
      <header className="inspector-neuron__head">
        <p className="panel__kicker">Neuron</p>
        <h3 className="mono">{bio.neuron_id}</h3>
        <p className="muted">{cellTypeDescription(bio.cell_type)}</p>
      </header>

      <section className="meta meta--bio" data-testid="biological-metadata">
        <p className="meta__label">
          <span className="tag tag--bio">BIOLOGICAL METADATA</span>
          <span className="muted"> {bio.label}</span>
        </p>
        <dl className="kv kv--tight">
          <dt>neuron_id</dt>
          <dd className="mono">{bio.neuron_id}</dd>
          <dt>cell_type</dt>
          <dd data-testid="bio-cell-type">{value(bio.cell_type)}</dd>
          <dt>cell_class</dt>
          <dd data-testid="bio-cell-class">{value(bio.cell_class)}</dd>
          <dt>neurotransmitter_prediction</dt>
          <dd data-testid="bio-nt">{value(bio.neurotransmitter_prediction)}</dd>
          <dt>dataset</dt>
          <dd>{bio.dataset}</dd>
          <dt>dataset_version</dt>
          <dd>{bio.dataset_version}</dd>
        </dl>
      </section>

      <section className="meta meta--circuit" data-testid="circuit-metadata">
        <p className="meta__label">
          <span className="tag tag--decoding">CIRCUIT / SIMULATION METADATA</span>
          <span className="muted"> {circuit.label}</span>
        </p>
        <dl className="kv kv--tight">
          <dt>minimum_hop_from_seed</dt>
          <dd className="mono">{circuit.minimum_hop_from_seed}</dd>
          <dt>is_seed</dt>
          <dd className="mono">{String(circuit.is_seed)}</dd>
          <dt>is_target</dt>
          <dd className="mono">{String(circuit.is_target)}</dd>
          <dt>side (escape config)</dt>
          <dd>{value(circuit.side)}</dd>
          <dt>role (escape config)</dt>
          <dd>{value(circuit.role)}</dd>
          <dt>stimulated by config</dt>
          <dd>{circuit.stimulated_by_config === null ? NA : String(circuit.stimulated_by_config)}</dd>
          <dt>circuit / hash</dt>
          <dd className="mono" title={detail.circuit_hash}>
            {detail.circuit_id} · {detail.circuit_hash.slice(0, 12)}…
          </dd>
        </dl>
      </section>

      <section className="meta meta--sim" data-testid="simulated-state">
        <p className="meta__label">
          <span className="tag tag--simulated">SIMULATED STATE</span>
          <span className="muted"> not a measured neural recording</span>
        </p>
        {simState && replayAvailable ? (
          <dl className="kv kv--tight">
            <dt>replay step</dt>
            <dd className="mono">{replayStep}</dd>
            <dt>simulated membrane potential</dt>
            <dd className="mono" data-testid="sim-potential">
              {simState.membranePotential.toFixed(4)}
            </dd>
            <dt>simulated fired</dt>
            <dd className="mono" data-testid="sim-fired">
              {String(simState.fired)}
            </dd>
            <dt>simulated refractory</dt>
            <dd className="mono" data-testid="sim-refractory">
              {simState.refractoryRemaining > 0 ? `yes (${simState.refractoryRemaining} step(s) left)` : 'no'}
            </dd>
            <dt>state</dt>
            <dd data-testid="sim-state">{simState.state}</dd>
          </dl>
        ) : (
          <p className="muted" data-testid="sim-state-empty">
            Run looming (replay controls) to see this neuron's simulated state per step.
          </p>
        )}
      </section>

      <section className="meta meta--conn" data-testid="connectivity-inspector">
        <p className="meta__label">
          <span className="tag tag--bio">CONNECTIONS WITHIN LOADED CIRCUIT</span>
          <span className="muted"> {neighbors.label}</span>
        </p>
        <p className="muted">
          in-degree {detail.connectivity.in_degree} ({detail.connectivity.in_synapses} synapses) · out-degree{' '}
          {detail.connectivity.out_degree} ({detail.connectivity.out_synapses} synapses)
        </p>
        <div className="actions actions--wrap">
          <button
            type="button"
            className={`btn btn--small ${highlightMode === 'upstream' ? 'btn--active' : ''}`}
            onClick={() => props.onHighlight('upstream')}
            data-testid="highlight-upstream"
          >
            Highlight upstream
          </button>
          <button
            type="button"
            className={`btn btn--small ${highlightMode === 'downstream' ? 'btn--active' : ''}`}
            onClick={() => props.onHighlight('downstream')}
            data-testid="highlight-downstream"
          >
            Highlight downstream
          </button>
          <button type="button" className="btn btn--ghost btn--small" onClick={() => props.onHighlight(null)} data-testid="clear-highlight">
            Clear highlight
          </button>
        </div>
        <NeighborTable title="Upstream (pre → this neuron)" list={neighbors.upstream} side="upstream" onSelectNeuron={props.onSelectNeuron} onSelectEdge={props.onSelectEdge} />
        <NeighborTable title="Downstream (this neuron → post)" list={neighbors.downstream} side="downstream" onSelectNeuron={props.onSelectNeuron} onSelectEdge={props.onSelectEdge} />
      </section>
    </div>
  )
}
