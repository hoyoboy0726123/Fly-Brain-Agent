import type { ThreatLabConfig, ThreatLabRunResult } from '../api/types.ts'

export const EMBODIMENT_DISCLAIMER =
  'Structural connectivity is biological data. Neural activity is simulated. ' +
  'Virtual sensing, motor mapping, body dynamics, and world physics are computational interpretations.'

const FALLBACK_LABELS: Record<string, string> = {
  world_physics: 'COMPUTATIONAL',
  virtual_sensing: 'COMPUTATIONAL SENSOR INPUT',
  neural_activity: 'SIMULATED',
  structural_connectivity: 'BIOLOGICAL DATA',
  body: 'SIMPLIFIED COMPUTATIONAL BODY',
}

export function LabLabels({ config }: { config: ThreatLabConfig | null }) {
  const labels = config?.labels ?? FALLBACK_LABELS
  const order = ['structural_connectivity', 'neural_activity', 'virtual_sensing', 'world_physics', 'body', 'motor_mapping']
  return (
    <ul className="lab-labels" data-testid="lab-labels" aria-label="Scientific labels">
      {order
        .filter((key) => labels[key] !== undefined)
        .map((key) => (
          <li key={key} className={`lab-labels__item lab-labels__item--${key}`} data-testid={`lab-label-${key}`}>
            <span className="lab-labels__key">{key.replace(/_/g, ' ')}</span>
            <span className="lab-labels__value">{labels[key]}</span>
          </li>
        ))}
    </ul>
  )
}

/** Scientific boundaries, provenance and the P7 disclaimer (served by the backend). */
export function Boundaries({ config, result }: { config: ThreatLabConfig | null; result: ThreatLabRunResult | null }) {
  const boundaries = config?.scientific_boundaries ?? []
  const prov = result?.provenance ?? null
  return (
    <section className="panel panel--lab-boundaries" data-testid="lab-boundaries" aria-labelledby="lab-boundaries-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Scientific boundaries</p>
          <h2 id="lab-boundaries-title" className="panel__title">
            What is biological data, what is simulated, what is computational
          </h2>
        </div>
      </header>
      {boundaries.length > 0 ? (
        <ul className="lab-boundaries__list">
          {boundaries.map((b) => (
            <li key={b.label} className="lab-boundaries__item">
              <span className={`tag ${b.label === 'BIOLOGICAL DATA' ? 'tag--bio' : b.label === 'SIMULATED' ? 'tag--simulated' : 'tag--input'}`}>{b.label}</span>
              <span>{b.scope}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="panel__empty">Boundaries are served by <code>GET /embodiment/config</code>.</p>
      )}
      <dl className="lab-state__list mono lab-prov" data-testid="lab-provenance">
        <dt>circuit</dt>
        <dd>
          {(prov?.circuit_id ?? config?.circuit.circuit_id ?? '—') + ' · '}
          <span data-testid="lab-circuit-hash">{(prov?.circuit_hash ?? config?.circuit.circuit_hash ?? '').slice(0, 16)}…</span>
          {config ? ` · ${config.circuit.neurons} neurons / ${config.circuit.edges} edges` : ''}
        </dd>
        <dt>dataset</dt>
        <dd>{config ? `${config.dataset} ${config.dataset_version} (structure) · BIOLOGICAL CIRCUIT STATUS: ${config.circuit.biological_status}` : '—'}</dd>
        <dt>timing</dt>
        <dd>{config ? `loop dt ${config.timing.loop_dt} s · ${config.timing.neural_steps_per_loop_step} neural steps (dt ${config.timing.neural_dt}) per loop step` : '—'}</dd>
        <dt>adapters</dt>
        <dd>{prov ? `${prov.world_adapter} → ${prov.sensor_adapter} → escape_v1 (${prov.escape_config_version}) → ${prov.motor_adapter} → ${prov.body_adapter} · seed ${prov.random_seed}` : 'recorded per run'}</dd>
        {result && (
          <>
            <dt>experiment</dt>
            <dd data-testid="lab-experiment-id">{result.experiment_id}</dd>
          </>
        )}
      </dl>
      <p className="disclaimer lab-disclaimer" data-testid="lab-disclaimer">
        {config?.disclaimer ?? result?.disclaimer ?? EMBODIMENT_DISCLAIMER}
      </p>
      <p className="muted panel__note">
        Not part of this lab: neural intervention (silencing, stimulation, lesions), food or odour, 3D biomechanics, robotics. The
        frontend renders backend-recorded states and never generates behaviour.
      </p>
    </section>
  )
}
