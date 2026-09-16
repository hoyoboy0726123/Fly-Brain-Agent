import { useCallback, useEffect, useMemo, useState } from 'react'

import { fetchAllCircuitEdges, fetchAllCircuitNodes, fetchCircuitProvenance, fetchCircuitSummary, toApiError } from '../api/client.ts'
import type { CircuitEdgeRecord, CircuitNodeRecord, CircuitProvenance, CircuitSummary } from '../api/types.ts'
import { computeLayout, type NodePosition } from './layout.ts'

export type CircuitDataState =
  | { status: 'loading' }
  | { status: 'error'; code: string; message: string }
  | {
      status: 'ready'
      summary: CircuitSummary
      provenance: CircuitProvenance
      nodes: CircuitNodeRecord[]
      edges: CircuitEdgeRecord[]
    }

export const edgeKey = (pre: string, post: string): string => `${pre}->${post}`

export interface CircuitIndex {
  nodeById: Map<string, CircuitNodeRecord>
  edgeByKey: Map<string, CircuitEdgeRecord>
  outEdges: Map<string, CircuitEdgeRecord[]>
  inEdges: Map<string, CircuitEdgeRecord[]>
  positions: Map<string, NodePosition>
  cellTypes: string[]
}

const EMPTY_INDEX: CircuitIndex = {
  nodeById: new Map(),
  edgeByKey: new Map(),
  outEdges: new Map(),
  inEdges: new Map(),
  positions: new Map(),
  cellTypes: [],
}

/** Loads the whole (small) circuit once: summary, provenance, nodes, edges, and a layout. */
export function useCircuitData(circuitId: string): { state: CircuitDataState; index: CircuitIndex; reload: () => void } {
  const [state, setState] = useState<CircuitDataState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    Promise.all([
      fetchCircuitSummary(circuitId, controller.signal),
      fetchCircuitProvenance(circuitId, controller.signal),
      fetchAllCircuitNodes(circuitId, controller.signal),
      fetchAllCircuitEdges(circuitId, controller.signal),
    ])
      .then(([summary, provenance, nodes, edges]) => setState({ status: 'ready', summary, provenance, nodes, edges }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const apiError = toApiError(error)
        setState({ status: 'error', code: apiError.code, message: apiError.message })
      })
    return () => controller.abort()
  }, [circuitId, attempt])

  const index = useMemo<CircuitIndex>(() => {
    if (state.status !== 'ready') return EMPTY_INDEX
    const nodeById = new Map(state.nodes.map((n) => [n.neuron_id, n]))
    const edgeByKey = new Map<string, CircuitEdgeRecord>()
    const outEdges = new Map<string, CircuitEdgeRecord[]>()
    const inEdges = new Map<string, CircuitEdgeRecord[]>()
    for (const edge of state.edges) {
      edgeByKey.set(edgeKey(edge.pre_neuron_id, edge.post_neuron_id), edge)
      const outs = outEdges.get(edge.pre_neuron_id) ?? []
      outs.push(edge)
      outEdges.set(edge.pre_neuron_id, outs)
      const ins = inEdges.get(edge.post_neuron_id) ?? []
      ins.push(edge)
      inEdges.set(edge.post_neuron_id, ins)
    }
    const cellTypes = [...new Set(state.nodes.map((n) => n.cell_type ?? 'unknown'))].sort()
    return { nodeById, edgeByKey, outEdges, inEdges, positions: computeLayout(state.nodes, state.edges), cellTypes }
  }, [state])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  return { state, index, reload }
}
