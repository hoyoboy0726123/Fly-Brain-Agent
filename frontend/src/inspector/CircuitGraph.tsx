import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { select } from 'd3-selection'
import { zoom, zoomIdentity, type ZoomBehavior } from 'd3-zoom'

import type { CircuitEdgeRecord, CircuitNodeRecord } from '../api/types.ts'
import { cellTypeColor } from './cellTypeStyle.ts'
import { LAYOUT_HEIGHT, LAYOUT_WIDTH, type NodePosition } from './layout.ts'
import { edgeKey } from './useCircuitData.ts'
import type { NeuronSimState } from './useReplay.ts'

export interface GraphHighlight {
  mode: 'upstream' | 'downstream' | null
  nodeIds: Set<string>
  edgeKeys: Set<string>
}

export interface EdgeSelection {
  pre: string
  post: string
}

export interface CircuitGraphProps {
  nodes: CircuitNodeRecord[]
  edges: CircuitEdgeRecord[]
  positions: Map<string, NodePosition>
  cellTypes: string[]
  selectedNeuronId: string | null
  selectedEdge: EdgeSelection | null
  highlight: GraphHighlight
  matches: Set<string>
  stateOf: (neuronId: string) => NeuronSimState | null
  replayActive: boolean
  focusRequest: { neuronId: string; nonce: number } | null
  onSelectNeuron: (neuronId: string) => void
  onSelectEdge: (pre: string, post: string) => void
}

interface Tooltip {
  x: number
  y: number
  lines: string[]
}

const NODE_RADIUS = 6
const TARGET_RADIUS = 11

export function nodeRadius(node: CircuitNodeRecord): number {
  return node.is_target ? TARGET_RADIUS : NODE_RADIUS
}

export function CircuitGraph(props: CircuitGraphProps) {
  const { nodes, edges, positions, cellTypes, selectedNeuronId, selectedEdge, highlight, matches, stateOf, replayActive } = props
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const zoomGroupRef = useRef<SVGGElement>(null)
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [size, setSize] = useState({ width: 900, height: 620 })
  const [tooltip, setTooltip] = useState<Tooltip | null>(null)
  const [zoomLevel, setZoomLevel] = useState(1)

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const update = () => setSize({ width: Math.max(element.clientWidth, 320), height: Math.max(element.clientHeight, 320) })
    update()
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const scale = Math.min(size.width / LAYOUT_WIDTH, size.height / LAYOUT_HEIGHT)

  useEffect(() => {
    const svgElement = svgRef.current
    const group = zoomGroupRef.current
    if (!svgElement || !group) return
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 12])
      .on('zoom', (event) => {
        select(group).attr('transform', event.transform.toString())
        setZoomLevel(event.transform.k)
      })
    select(svgElement).call(behavior)
    zoomRef.current = behavior
    return () => {
      select(svgElement).on('.zoom', null)
    }
  }, [])

  // centre on a neuron when asked (search / select from a list)
  const focus = props.focusRequest
  useEffect(() => {
    if (!focus || !svgRef.current || !zoomRef.current) return
    const position = positions.get(focus.neuronId)
    if (!position) return
    const k = 2.6
    const transform = zoomIdentity
      .translate(size.width / 2 - position.x * scale * k, size.height / 2 - position.y * scale * k)
      .scale(k)
    select(svgRef.current).call(zoomRef.current.transform, transform)
  }, [focus, positions, scale, size.height, size.width])

  const zoomBy = (factor: number) => {
    if (svgRef.current && zoomRef.current) select(svgRef.current).call(zoomRef.current.scaleBy, factor)
  }
  const resetView = () => {
    if (svgRef.current && zoomRef.current) select(svgRef.current).call(zoomRef.current.transform, zoomIdentity)
  }

  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.neuron_id, n])), [nodes])
  const maxSynapses = useMemo(() => Math.max(1, ...edges.map((e) => e.synapse_count)), [edges])
  const dimming = highlight.mode !== null || matches.size > 0

  const showTooltip = (event: ReactMouseEvent, lines: string[]) => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    setTooltip({ x: event.clientX - rect.left + 14, y: event.clientY - rect.top + 14, lines })
  }

  return (
    <div className="graph" ref={containerRef} data-testid="circuit-graph" data-node-count={nodes.length} data-edge-count={edges.length}>
      <svg ref={svgRef} width={size.width} height={size.height} role="img" aria-label="Escape circuit graph: neurons (biological identity) and structural edges from the circuit artifact">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" className="graph__arrow" />
          </marker>
          <marker id="arrow-hl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" className="graph__arrow graph__arrow--hl" />
          </marker>
        </defs>
        <g ref={zoomGroupRef}>
          <g transform={`scale(${scale})`}>
            <g className="graph__edges">
              {edges.map((edge) => {
                const from = positions.get(edge.pre_neuron_id)
                const to = positions.get(edge.post_neuron_id)
                const target = nodeById.get(edge.post_neuron_id)
                if (!from || !to || !target) return null
                const key = edgeKey(edge.pre_neuron_id, edge.post_neuron_id)
                const dx = to.x - from.x
                const dy = to.y - from.y
                const length = Math.max(Math.hypot(dx, dy), 1)
                const shrink = nodeRadius(target) + 2
                const x2 = to.x - (dx / length) * shrink
                const y2 = to.y - (dy / length) * shrink
                const selected = selectedEdge !== null && selectedEdge.pre === edge.pre_neuron_id && selectedEdge.post === edge.post_neuron_id
                const highlighted = highlight.edgeKeys.has(key)
                const dimmed = dimming && !highlighted && !selected
                const width = 0.6 + 4.5 * Math.sqrt(edge.synapse_count / maxSynapses)
                const cls = `graph__edge ${selected ? 'graph__edge--selected' : ''} ${highlighted ? 'graph__edge--hl' : ''} ${dimmed ? 'graph__edge--dim' : ''}`
                const lines = [
                  `${edge.pre_neuron_id} → ${edge.post_neuron_id}`,
                  `${edge.synapse_count} synapses · ${edge.dataset} ${edge.dataset_version}`,
                  'Structural connection — biological data',
                ]
                return (
                  <g key={key}>
                    <line className={cls} x1={from.x} y1={from.y} x2={x2} y2={y2} strokeWidth={width} markerEnd={selected || highlighted ? 'url(#arrow-hl)' : 'url(#arrow)'} />
                    <line
                      className="graph__edge-hit"
                      x1={from.x}
                      y1={from.y}
                      x2={x2}
                      y2={y2}
                      data-testid={`edge-hit-${edge.pre_neuron_id}-${edge.post_neuron_id}`}
                      data-selected={selected}
                      data-highlighted={highlighted}
                      onClick={(event) => {
                        event.stopPropagation()
                        props.onSelectEdge(edge.pre_neuron_id, edge.post_neuron_id)
                      }}
                      onMouseEnter={(event) => showTooltip(event, lines)}
                      onMouseMove={(event) => showTooltip(event, lines)}
                      onMouseLeave={() => setTooltip(null)}
                    />
                  </g>
                )
              })}
            </g>
            <g className="graph__nodes">
              {nodes.map((node) => {
                const position = positions.get(node.neuron_id)
                if (!position) return null
                const sim = replayActive ? stateOf(node.neuron_id) : null
                const simState = sim?.state ?? 'inactive'
                const selected = node.neuron_id === selectedNeuronId
                const highlighted = highlight.nodeIds.has(node.neuron_id) || matches.has(node.neuron_id)
                const dimmed = dimming && !highlighted && !selected
                const radius = nodeRadius(node)
                const lines = [
                  `neuron ${node.neuron_id} · ${node.cell_type ?? 'cell type not available'}${node.side ? ` · ${node.side}` : ''}`,
                  `${node.dataset} ${node.dataset_version} (biological identity)`,
                ]
                if (sim) lines.push(`SIMULATED: ${simState} · V=${sim.membranePotential.toFixed(3)}`)
                return (
                  <g
                    key={node.neuron_id}
                    className={`graph__node sim-${simState} ${selected ? 'graph__node--selected' : ''} ${highlighted ? 'graph__node--hl' : ''} ${dimmed ? 'graph__node--dim' : ''}`}
                    transform={`translate(${position.x} ${position.y})`}
                    data-testid={`node-${node.neuron_id}`}
                    data-cell-type={node.cell_type ?? ''}
                    data-sim-state={simState}
                    data-selected={selected}
                    data-highlighted={highlighted}
                    onClick={(event) => {
                      event.stopPropagation()
                      props.onSelectNeuron(node.neuron_id)
                    }}
                    onMouseEnter={(event) => showTooltip(event, lines)}
                    onMouseMove={(event) => showTooltip(event, lines)}
                    onMouseLeave={() => setTooltip(null)}
                  >
                    <circle className="graph__node-glow" r={radius + 6} />
                    <circle className="graph__node-ring" r={radius + 3} />
                    <circle className="graph__node-core" r={radius} fill={cellTypeColor(node.cell_type, cellTypes)} />
                    {(node.is_target || selected) && (
                      <text className="graph__node-label" y={radius + 11} textAnchor="middle">
                        {node.cell_type ?? node.neuron_id} {node.neuron_id}
                      </text>
                    )}
                  </g>
                )
              })}
            </g>
          </g>
        </g>
      </svg>
      {tooltip && (
        <div className="graph__tooltip" style={{ left: tooltip.x, top: tooltip.y }} role="tooltip" data-testid="graph-tooltip">
          {tooltip.lines.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      )}
      <div className="graph__controls">
        <button type="button" className="btn btn--ghost btn--small" onClick={() => zoomBy(1.4)} aria-label="Zoom in" data-testid="zoom-in">
          +
        </button>
        <button type="button" className="btn btn--ghost btn--small" onClick={() => zoomBy(1 / 1.4)} aria-label="Zoom out" data-testid="zoom-out">
          −
        </button>
        <button type="button" className="btn btn--ghost btn--small" onClick={resetView} data-testid="zoom-reset">
          fit
        </button>
        <span className="mono muted" data-testid="zoom-level">
          ×{zoomLevel.toFixed(2)}
        </span>
      </div>
      <div className="graph__caption">
        <span className="tag tag--bio">BIOLOGICAL STRUCTURE</span>
        <span className="muted">
          {nodes.length} neurons · {edges.length} structural edges from the circuit artifact · drag to pan, wheel to zoom
        </span>
      </div>
    </div>
  )
}
