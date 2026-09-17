import { useCallback, useMemo, useState } from 'react'

import type { EscapeDemo } from '../demo/useEscapeDemo.ts'
import { CircuitGraph, type EdgeSelection, type GraphHighlight } from './CircuitGraph.tsx'
import { EdgeInspector } from './EdgeInspector.tsx'
import { Legend } from './Legend.tsx'
import { NeuronInspector, type InterventionInfo } from './NeuronInspector.tsx'
import { ProvenancePanel } from './ProvenancePanel.tsx'
import { ReplayControls } from './ReplayControls.tsx'
import { SearchBar } from './SearchBar.tsx'
import { edgeKey, useCircuitData } from './useCircuitData.ts'
import { useReplay } from './useReplay.ts'

export const DEFAULT_CIRCUIT_ID = 'escape_v1'

type Selection = { kind: 'neuron'; id: string } | { kind: 'edge'; pre: string; post: string } | null

const EMPTY_HIGHLIGHT: GraphHighlight = { mode: null, nodeIds: new Set(), edgeKeys: new Set() }

export interface InspectorViewProps {
  demo: EscapeDemo
  paceMs: number
  /** P7.2: the last Neural Intervention Lab comparison (targets are shown per neuron; graph unchanged). */
  intervention?: InterventionInfo | null
}

export function InspectorView({ demo, paceMs, intervention = null }: InspectorViewProps) {
  const circuitId = demo.state.config?.circuit_id ?? DEFAULT_CIRCUIT_ID
  const { state, index, reload } = useCircuitData(circuitId)
  const replay = useReplay(demo.state.result?.neuron_activity ?? null, paceMs)
  const [selection, setSelection] = useState<Selection>(null)
  const [highlightMode, setHighlightMode] = useState<'upstream' | 'downstream' | null>(null)
  const [cellTypeFilter, setCellTypeFilter] = useState('')
  const [searchMessage, setSearchMessage] = useState<string | null>(null)
  const [focusRequest, setFocusRequest] = useState<{ neuronId: string; nonce: number } | null>(null)

  const selectNeuron = useCallback((neuronId: string, focus = false) => {
    setSelection({ kind: 'neuron', id: neuronId })
    setHighlightMode(null)
    if (focus) setFocusRequest({ neuronId, nonce: Date.now() })
  }, [])
  const selectEdge = useCallback((pre: string, post: string) => {
    setSelection({ kind: 'edge', pre, post })
    setHighlightMode(null)
  }, [])

  const nodes = state.status === 'ready' ? state.nodes : []
  const edges = state.status === 'ready' ? state.edges : []
  const selectedNeuronId = selection?.kind === 'neuron' ? selection.id : null
  const selectedEdge: EdgeSelection | null = selection?.kind === 'edge' ? { pre: selection.pre, post: selection.post } : null

  const highlight = useMemo<GraphHighlight>(() => {
    if (!selectedNeuronId || !highlightMode) return EMPTY_HIGHLIGHT
    const list = (highlightMode === 'upstream' ? index.inEdges.get(selectedNeuronId) : index.outEdges.get(selectedNeuronId)) ?? []
    const nodeIds = new Set<string>([selectedNeuronId])
    const edgeKeys = new Set<string>()
    for (const edge of list) {
      nodeIds.add(highlightMode === 'upstream' ? edge.pre_neuron_id : edge.post_neuron_id)
      edgeKeys.add(edgeKey(edge.pre_neuron_id, edge.post_neuron_id))
    }
    return { mode: highlightMode, nodeIds, edgeKeys }
  }, [selectedNeuronId, highlightMode, index])

  const matches = useMemo(() => {
    if (!cellTypeFilter) return new Set<string>()
    return new Set(nodes.filter((n) => (n.cell_type ?? 'unknown') === cellTypeFilter).map((n) => n.neuron_id))
  }, [cellTypeFilter, nodes])

  const onSearchId = (neuronId: string) => {
    if (!neuronId) {
      setSearchMessage('Enter a neuron id.')
      return
    }
    const node = index.nodeById.get(neuronId)
    if (!node) {
      setSearchMessage(`No neuron with id "${neuronId}" in the loaded circuit ${circuitId}.`)
      return
    }
    selectNeuron(neuronId, true)
    setSearchMessage(`Neuron ${neuronId} (${node.cell_type ?? 'cell type not available'}) selected.`)
  }
  const onCellTypeFilter = (type: string) => {
    setCellTypeFilter(type)
    if (!type) {
      setSearchMessage(null)
      return
    }
    const count = nodes.filter((n) => (n.cell_type ?? 'unknown') === type).length
    setSearchMessage(`${count} ${type} neuron(s) in the loaded circuit are highlighted.`)
  }

  const counts = state.status === 'ready' ? state.summary.cell_type_counts : {}
  const replayActive = replay.steps > 0
  const simState = selectedNeuronId && replayActive ? replay.stateOf(selectedNeuronId) : null

  return (
    <section className="inspector" data-testid="inspector-view" aria-labelledby="inspector-title">
      <header className="inspector__header">
        <div>
          <p className="panel__kicker">Brain inspector</p>
          <h2 id="inspector-title" className="panel__title">
            Circuit <code>{circuitId}</code>
            {state.status === 'ready' && (
              <span className="muted">
                {' '}
                · {state.summary.neurons} neurons · {state.summary.edges} edges · {state.summary.dataset}{' '}
                {state.summary.dataset_version}
              </span>
            )}
          </h2>
        </div>
        <div className="inspector__tags">
          <span className="tag tag--bio">BIOLOGICAL STRUCTURE = neuron identity + structural edges</span>
          <span className="tag tag--simulated">SIMULATED ACTIVITY = firing / membrane potential</span>
          <span className="tag tag--decoding">COMPUTATIONAL INTERPRETATION = looming mapping + decoder</span>
        </div>
      </header>

      {state.status === 'error' && (
        <div className="banner banner--error" role="alert" data-testid="inspector-error">
          <strong>Circuit unavailable</strong> ({state.code}): {state.message}{' '}
          <button type="button" className="btn btn--ghost btn--small" onClick={reload}>
            Retry
          </button>
        </div>
      )}

      <div className="inspector__grid">
        <aside className="inspector__side">
          <SearchBar cellTypes={index.cellTypes} cellTypeFilter={cellTypeFilter} message={searchMessage} onSearchId={onSearchId} onCellTypeFilter={onCellTypeFilter} />
          <Legend cellTypes={index.cellTypes} counts={counts} />
        </aside>

        <div className="inspector__center">
          {state.status === 'loading' ? (
            <p className="panel__empty" data-testid="inspector-loading">
              Loading circuit {circuitId} from the backend (nodes, edges, provenance)…
            </p>
          ) : (
            <CircuitGraph
              nodes={nodes}
              edges={edges}
              positions={index.positions}
              cellTypes={index.cellTypes}
              selectedNeuronId={selectedNeuronId}
              selectedEdge={selectedEdge}
              highlight={highlight}
              matches={matches}
              stateOf={replay.stateOf}
              replayActive={replayActive}
              focusRequest={focusRequest}
              onSelectNeuron={(id) => selectNeuron(id)}
              onSelectEdge={selectEdge}
            />
          )}
        </div>

        <aside className="inspector__side inspector__side--right">
          <ReplayControls demo={demo} replay={replay} />
          <section className="panel panel--inspector" data-testid="selection-panel">
            {selection === null && (
              <p className="muted" data-testid="selection-empty">
                Click a neuron or an edge in the graph, or search a neuron id. Neuron identity and edges are biological
                data; activity colours are simulated.
              </p>
            )}
            {selection?.kind === 'neuron' && (
              <NeuronInspector
                circuitId={circuitId}
                neuronId={selection.id}
                simState={simState}
                replayStep={replay.step}
                replayAvailable={replayActive}
                intervention={intervention}
                highlightMode={highlightMode}
                onHighlight={setHighlightMode}
                onSelectNeuron={(id) => selectNeuron(id, true)}
                onSelectEdge={selectEdge}
              />
            )}
            {selection?.kind === 'edge' && (
              <EdgeInspector circuitId={circuitId} pre={selection.pre} post={selection.post} onSelectNeuron={(id) => selectNeuron(id, true)} />
            )}
          </section>
        </aside>
      </div>

      {state.status === 'ready' && <ProvenancePanel provenance={state.provenance} />}
    </section>
  )
}
