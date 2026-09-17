import type { ActivityGroup, GroupEdge, ThreatLabBrain as BrainRecord } from '../api/types.ts'
import type { LabPhase } from './useThreatLab.ts'

const WIDTH = 360
const HEIGHT = 250
const COLUMN_X: Record<string, number> = { L: 96, R: 264 }
const NODE_R = 22

interface NodeLayout {
  group: ActivityGroup
  x: number
  y: number
}

function layout(groups: ActivityGroup[]): NodeLayout[] {
  const sensoryTypes = [...new Set(groups.filter((g) => g.role === 'sensory').map((g) => g.cell_type))].sort()
  const otherTypes = [...new Set(groups.filter((g) => g.role === 'other').map((g) => g.cell_type))].sort()
  const rows = sensoryTypes.length + otherTypes.length
  const rowGap = rows > 0 ? Math.min(62, 130 / Math.max(rows, 1)) : 62
  return groups.map((group) => {
    let y: number
    if (group.role === 'output') y = HEIGHT - 46
    else {
      const index = group.role === 'sensory' ? sensoryTypes.indexOf(group.cell_type) : sensoryTypes.length + otherTypes.indexOf(group.cell_type)
      y = 52 + index * rowGap
    }
    return { group, x: COLUMN_X[group.side] ?? WIDTH / 2, y }
  })
}

export interface ThreatLabBrainProps {
  groups: ActivityGroup[]
  edges: GroupEdge[]
  circuitId: string | null
  phase: LabPhase
  brain: BrainRecord | null
  loopStep: number | null
}

/**
 * Brain panel of the lab. Node identity (cell type, side, neuron count) and edges are
 * biological structure from the circuit artifact; the glow and the per-neural-step bars
 * are the SIMULATED activity the backend recorded for the replayed loop step.
 */
export function ThreatLabBrain({ groups, edges, circuitId, phase, brain, loopStep }: ThreatLabBrainProps) {
  const nodes = layout(groups)
  const position = new Map(nodes.map((n) => [n.group.key, n]))
  const drawnEdges = edges.filter((e) => e.pre_key !== e.post_key && position.has(e.pre_key) && position.has(e.post_key))
  const maxSynapses = Math.max(1, ...drawnEdges.map((e) => e.synapse_total))
  const firedTotal = brain ? Object.values(brain.group_peak_fired).reduce((a, b) => a + b, 0) : 0
  const neuralSteps = brain?.neural_steps ?? 0

  return (
    <section className="panel panel--lab-brain" data-testid="lab-brain-panel" aria-labelledby="lab-brain-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Brain · escape circuit {circuitId ? <span className="mono">({circuitId})</span> : null}</p>
          <h2 id="lab-brain-title" className="panel__title">
            LC4 / LPLC2 → DNp01
          </h2>
        </div>
        <span className="tag tag--simulated" data-testid="lab-brain-label">
          SIMULATED NEURAL ACTIVITY
        </span>
      </header>

      <div className="brain__status">
        <span className="mono" data-testid="lab-brain-step">
          {brain && loopStep !== null ? `loop step ${loopStep} · ${brain.neural_steps} neural steps` : phase === 'error' ? 'NO RESULT' : 'no experiment yet'}
        </span>
        <span className="muted">
          {brain ? (
            <>
              stimulus {brain.stimulus.direction} {brain.stimulus.intensity.toFixed(3)} · <span data-testid="lab-brain-fired">{brain.firing_events}</span> simulated spikes ·
              decoded <span className="mono" data-testid="lab-brain-action">{brain.action}</span>
            </>
          ) : (
            'node identity = biological structure · glow = simulated activity (none before a run)'
          )}
        </span>
      </div>

      {nodes.length === 0 ? (
        <p className="panel__empty" data-testid="lab-brain-empty">
          Circuit groups are loaded from the backend (<code>GET /embodiment/config</code>).
        </p>
      ) : (
        <svg className="brain brain--lab" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Escape circuit groups with simulated activity at the replayed loop step">
          <defs>
            <filter id="labNodeGlow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <text className="brain__hemi" x={COLUMN_X['L']} y="20" textAnchor="middle">
            LEFT
          </text>
          <text className="brain__hemi" x={COLUMN_X['R']} y="20" textAnchor="middle">
            RIGHT
          </text>
          <line className="brain__midline" x1={WIDTH / 2} y1="28" x2={WIDTH / 2} y2={HEIGHT - 16} />
          {drawnEdges.map((edge) => {
            const from = position.get(edge.pre_key)
            const to = position.get(edge.post_key)
            if (!from || !to) return null
            const active = (brain?.group_peak_fired[edge.pre_key] ?? 0) > 0
            return (
              <line
                key={`${edge.pre_key}->${edge.post_key}`}
                className={`brain__edge ${active ? 'brain__edge--active' : ''}`}
                x1={from.x}
                y1={from.y + NODE_R}
                x2={to.x}
                y2={to.y - NODE_R}
                strokeWidth={1.2 + 3.5 * Math.sqrt(edge.synapse_total / maxSynapses)}
                data-testid={`lab-edge-${edge.pre_key}-${edge.post_key}`}
                data-active={active}
              >
                <title>{`${edge.pre_key} → ${edge.post_key}: ${edge.edge_count} edges, ${edge.synapse_total} synapses (${edge.dataset} ${edge.dataset_version}) — biological structure`}</title>
              </line>
            )
          })}
          {nodes.map(({ group, x, y }) => {
            const fired = brain?.group_peak_fired[group.key] ?? 0
            const fraction = group.neuron_count > 0 ? fired / group.neuron_count : 0
            const active = fired > 0
            return (
              <g
                key={group.key}
                className={`node node--${group.role} ${active ? 'node--active' : ''}`}
                data-testid={`lab-node-${group.key}`}
                data-active={active}
                data-fired={fired}
                style={{ ['--fraction' as string]: fraction }}
              >
                <circle className="node__ring" cx={x} cy={y} r={NODE_R + 4} />
                <circle className="node__glow" cx={x} cy={y} r={NODE_R} filter="url(#labNodeGlow)" />
                <circle className="node__core" cx={x} cy={y} r={NODE_R} />
                <text className="node__label" x={x} y={y - 3} textAnchor="middle">
                  {group.cell_type}
                </text>
                <text className="node__sub" x={x} y={y + 10} textAnchor="middle">
                  {group.side === 'L' ? 'left' : group.side === 'R' ? 'right' : group.side}
                </text>
                <text className="node__count" x={x} y={y + NODE_R + 13} textAnchor="middle">
                  {brain ? `peak ${fired} / ${group.neuron_count}` : `${group.neuron_count} neurons`}
                </text>
              </g>
            )
          })}
        </svg>
      )}

      <div className="lab-raster" data-testid="lab-raster" data-neural-steps={neuralSteps} aria-label="Simulated spike counts per neural step for each group">
        {groups.map((group) => {
          const counts = brain?.group_fired_counts[group.key] ?? []
          const max = Math.max(1, group.neuron_count)
          return (
            <div key={group.key} className="lab-raster__row" data-testid={`lab-raster-${group.key}`} data-total={counts.reduce((a, b) => a + b, 0)}>
              <span className="lab-raster__key mono">{group.key}</span>
              <span className="lab-raster__bars" aria-hidden="true">
                {(counts.length > 0 ? counts : Array.from({ length: Math.max(neuralSteps, 1) }, () => 0)).map((count, i) => (
                  <span key={i} className={`lab-raster__bar ${count > 0 ? 'lab-raster__bar--on' : ''}`} style={{ height: `${Math.max(count > 0 ? 18 : 6, Math.round((count / max) * 100))}%` }} />
                ))}
              </span>
            </div>
          )
        })}
      </div>
      <footer className="brain__legend">
        <p>
          Node identity, neuron counts and edges = <strong>biological structure</strong> (MaleCNS circuit artifact). Glow = fraction of the group
          with a simulated spike at its peak neural step; bars = simulated spike counts per neural step of this loop step. {firedTotal === 0 && brain ? 'No simulated activity at this step.' : ''}
        </p>
      </footer>
    </section>
  )
}
