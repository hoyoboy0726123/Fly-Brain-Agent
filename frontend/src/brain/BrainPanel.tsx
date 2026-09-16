import type { ActivityGroup, GroupEdge } from '../api/types.ts'
import { SIMULATED_ACTIVITY_LABEL } from '../content.ts'
import type { DemoPhase, DemoView } from '../demo/useEscapeDemo.ts'

export interface BrainPanelProps {
  groups: ActivityGroup[]
  edges: GroupEdge[]
  circuitId: string | null
  phase: DemoPhase
  view: DemoView
}

interface NodeLayout {
  group: ActivityGroup
  x: number
  y: number
}

const WIDTH = 360
const HEIGHT = 280
const COLUMN_X: Record<string, number> = { L: 96, R: 264 }
const NODE_R = 24

function columnFor(side: string): number {
  return COLUMN_X[side] ?? WIDTH / 2
}

/** Sensory groups in rows by cell type (top), output groups at the bottom, L/R columns. */
function layout(groups: ActivityGroup[]): NodeLayout[] {
  const sensoryTypes = [...new Set(groups.filter((g) => g.role === 'sensory').map((g) => g.cell_type))].sort()
  const otherTypes = [...new Set(groups.filter((g) => g.role === 'other').map((g) => g.cell_type))].sort()
  const rows = sensoryTypes.length + otherTypes.length
  const rowGap = rows > 0 ? Math.min(66, 150 / Math.max(rows, 1)) : 66
  return groups.map((group) => {
    let y: number
    if (group.role === 'output') {
      y = HEIGHT - 52
    } else {
      const index = group.role === 'sensory' ? sensoryTypes.indexOf(group.cell_type) : sensoryTypes.length + otherTypes.indexOf(group.cell_type)
      y = 58 + index * rowGap
    }
    return { group, x: columnFor(group.side), y }
  })
}

function sideName(side: string): string {
  return side === 'L' ? 'left' : side === 'R' ? 'right' : side
}

export function BrainPanel({ groups, edges, circuitId, phase, view }: BrainPanelProps) {
  const nodes = layout(groups)
  const position = new Map(nodes.map((n) => [n.group.key, n]))
  const drawnEdges = edges.filter((e) => e.pre_key !== e.post_key && position.has(e.pre_key) && position.has(e.post_key))
  const selfEdges = edges.filter((e) => e.pre_key === e.post_key)
  const maxSynapses = Math.max(1, ...drawnEdges.map((e) => e.synapse_total))
  const replaying = phase === 'replaying' || phase === 'finished'

  return (
    <section className="panel panel--brain" data-testid="brain-panel" aria-labelledby="brain-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Fly brain</p>
          <h2 id="brain-title" className="panel__title">
            Escape circuit {circuitId ? <span className="muted mono">({circuitId})</span> : null}
          </h2>
        </div>
        <span className="tag tag--simulated" data-testid="simulated-activity-label">
          {SIMULATED_ACTIVITY_LABEL}
        </span>
      </header>

      <div className="brain__status">
        <span className="mono" data-testid="brain-step">
          {view.steps > 0 ? `step ${view.step} / ${view.steps}` : 'no run yet'}
        </span>
        <span className="muted">
          {view.steps > 0 ? (
            <>
              {view.stimulusActive ? 'stimulus current injected' : view.step > 0 ? 'stimulus ended' : 'replaying backend timeline'} ·{' '}
              <span data-testid="brain-fired-total">{view.firedTotal}</span> simulated spikes this step
            </>
          ) : (
            'node glow = fraction of the group firing at the replayed step'
          )}
        </span>
      </div>

      {nodes.length === 0 ? (
        <p className="panel__empty" data-testid="brain-empty">
          Circuit groups are loaded from the backend (<code>GET /escape/config</code>). No structural data is shown
          until the connection succeeds.
        </p>
      ) : (
        <svg className="brain" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Schematic of the escape circuit groups with simulated activity">
          <defs>
            <filter id="nodeGlow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <text className="brain__hemi" x={COLUMN_X['L']} y="22" textAnchor="middle">
            LEFT
          </text>
          <text className="brain__hemi" x={COLUMN_X['R']} y="22" textAnchor="middle">
            RIGHT
          </text>
          <line className="brain__midline" x1={WIDTH / 2} y1="30" x2={WIDTH / 2} y2={HEIGHT - 20} />

          {drawnEdges.map((edge) => {
            const from = position.get(edge.pre_key)
            const to = position.get(edge.post_key)
            if (!from || !to) return null
            const active = replaying && (view.firedByGroup[edge.pre_key] ?? 0) > 0
            const width = 1.2 + 3.5 * Math.sqrt(edge.synapse_total / maxSynapses)
            return (
              <line
                key={`${edge.pre_key}->${edge.post_key}`}
                className={`brain__edge ${active ? 'brain__edge--active' : ''}`}
                x1={from.x}
                y1={from.y + NODE_R}
                x2={to.x}
                y2={to.y - NODE_R}
                strokeWidth={width}
                data-testid={`brain-edge-${edge.pre_key}-${edge.post_key}`}
                data-active={active}
              >
                <title>{`${edge.pre_key} → ${edge.post_key}: ${edge.edge_count} edges, ${edge.synapse_total} synapses (${edge.dataset} ${edge.dataset_version})`}</title>
              </line>
            )
          })}

          {nodes.map(({ group, x, y }) => {
            const fired = replaying ? (view.firedByGroup[group.key] ?? 0) : 0
            const fraction = group.neuron_count > 0 ? fired / group.neuron_count : 0
            const active = fired > 0
            return (
              <g
                key={group.key}
                className={`node node--${group.role} ${active ? 'node--active' : ''}`}
                data-testid={`brain-node-${group.key}`}
                data-active={active}
                data-fired={fired}
                style={{ ['--fraction' as string]: fraction }}
              >
                <circle className="node__ring" cx={x} cy={y} r={NODE_R + 4} />
                <circle className="node__glow" cx={x} cy={y} r={NODE_R} filter="url(#nodeGlow)" />
                <circle className="node__core" cx={x} cy={y} r={NODE_R} />
                <text className="node__label" x={x} y={y - 3} textAnchor="middle">
                  {group.cell_type}
                </text>
                <text className="node__sub" x={x} y={y + 10} textAnchor="middle">
                  {sideName(group.side)}
                </text>
                <text className="node__count" x={x} y={y + NODE_R + 14} textAnchor="middle">
                  {replaying ? `${fired} / ${group.neuron_count}` : `${group.neuron_count} neurons`}
                </text>
              </g>
            )
          })}
        </svg>
      )}

      <footer className="brain__legend">
        <p>
          Nodes = groups of circuit neurons by MaleCNS <code>cell_type</code> and side (structure). Edges = aggregated
          synaptic connections from the circuit artifact; width ∝ synapse count. Glow = fraction of the group with a
          simulated spike at the replayed step.
        </p>
        {selfEdges.length > 0 && (
          <p className="muted">
            Not drawn (within-group edges): {selfEdges.map((e) => `${e.pre_key} ${e.edge_count}`).join(' · ')}
          </p>
        )}
      </footer>
    </section>
  )
}
