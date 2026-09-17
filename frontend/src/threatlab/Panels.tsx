import type { ThreatLabRunResult, ThreatLabStep } from '../api/types.ts'
import type { LabPhase } from './useThreatLab.ts'

function num(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

function vec(v: { x: number; y: number; z: number } | undefined): string {
  return v ? `(${num(v.x)}, ${num(v.y)}, ${num(v.z)})` : '—'
}

/** The four headline numbers of the replayed step (all from the backend record). */
export function Metrics({ phase, step }: { phase: LabPhase; step: ThreatLabStep | null }) {
  const action = step ? step.brain.action : phase === 'error' ? 'NO RESULT' : phase === 'running' ? 'RUNNING' : 'WAITING FOR EXPERIMENT'
  return (
    <dl className="lab-metrics" data-testid="lab-metrics">
      <div className="lab-metric">
        <dt>DISTANCE</dt>
        <dd className="mono" data-testid="lab-distance" data-value={step?.sensor.distance ?? ''}>
          {step ? `${num(step.sensor.distance)} units` : '—'}
        </dd>
      </div>
      <div className="lab-metric">
        <dt>LOOMING INPUT</dt>
        <dd className="mono" data-testid="lab-looming" data-value={step?.sensor.intensity ?? ''} data-direction={step?.sensor.direction ?? ''}>
          {step ? `${num(step.sensor.intensity, 3)} · ${step.sensor.direction}` : '—'}
        </dd>
      </div>
      <div className="lab-metric">
        <dt>BODY POSITION</dt>
        <dd className="mono" data-testid="lab-body-position" data-x={step?.body.position.x ?? ''} data-y={step?.body.position.y ?? ''} data-z={step?.body.position.z ?? ''}>
          {step ? vec(step.body.position) : '—'}
        </dd>
      </div>
      <div className={`lab-metric lab-metric--action ${action === 'ESCAPE' ? 'lab-metric--escape' : ''}`}>
        <dt>ACTION</dt>
        <dd className="mono" data-testid="lab-action" data-value={action}>
          {action}
        </dd>
      </div>
    </dl>
  )
}

/** WORLD (computational physics) and BODY (simplified computational body) at the replayed step. */
export function WorldBodyPanel({ step, result }: { step: ThreatLabStep | null; result: ThreatLabRunResult | null }) {
  const object = step?.world.objects[0]
  return (
    <section className="panel panel--lab-world" data-testid="lab-world-body-panel" aria-labelledby="lab-world-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">World · Body</p>
          <h2 id="lab-world-title" className="panel__title">
            Recorded state
          </h2>
        </div>
        <span className="tag tag--input">COMPUTATIONAL</span>
      </header>
      <div className="lab-state" data-testid="lab-world-panel">
        <h3 className="lab-state__title">
          WORLD <span className="tag tag--input">COMPUTATIONAL</span>
        </h3>
        <dl className="lab-state__list mono">
          <dt>time</dt>
          <dd data-testid="lab-world-time">{step ? `${num(step.world.simulation_time)} s (loop dt ${num(step.dt, 1)} s)` : '—'}</dd>
          <dt>object</dt>
          <dd data-testid="lab-world-object">{object ? object.object_type : '—'}</dd>
          <dt>position</dt>
          <dd data-testid="lab-world-position">{vec(object?.position)}</dd>
          <dt>velocity</dt>
          <dd data-testid="lab-world-velocity">{vec(object?.velocity)}</dd>
          <dt>size</dt>
          <dd data-testid="lab-world-size">{object ? `${num(object.size)} units` : '—'}</dd>
        </dl>
      </div>
      <div className="lab-state" data-testid="lab-body-panel">
        <h3 className="lab-state__title">
          BODY <span className="tag tag--decoding">SIMPLIFIED COMPUTATIONAL BODY</span>
        </h3>
        <dl className="lab-state__list mono">
          <dt>position</dt>
          <dd data-testid="lab-body-pos">{step ? vec(step.body.position) : '—'}</dd>
          <dt>velocity</dt>
          <dd data-testid="lab-body-velocity">{step ? vec(step.body.velocity) : '—'}</dd>
          <dt>heading</dt>
          <dd data-testid="lab-body-heading">{step ? `${num(step.body.heading)} rad` : '—'}</dd>
          <dt>grounded</dt>
          <dd data-testid="lab-body-grounded">{step ? String(step.body.grounded) : '—'}</dd>
        </dl>
      </div>
      <div className="lab-state" data-testid="lab-sensor-panel">
        <h3 className="lab-state__title">
          SENSOR <span className="tag tag--input">COMPUTATIONAL SENSOR INPUT</span>
        </h3>
        <dl className="lab-state__list mono">
          <dt>angular size</dt>
          <dd data-testid="lab-sensor-angular">{step ? `${num(step.sensor.angular_size_rad, 3)} rad` : '—'}</dd>
          <dt>bearing</dt>
          <dd data-testid="lab-sensor-bearing">{step ? `${num(step.sensor.bearing_rad, 3)} rad → ${step.sensor.direction}` : '—'}</dd>
          <dt>intensity</dt>
          <dd data-testid="lab-sensor-intensity">{step ? num(step.sensor.intensity, 3) : '—'}</dd>
          <dt>motor</dt>
          <dd data-testid="lab-motor-command">{step ? `${step.motor.command} (from ${step.motor.source_action}; no direction decoded)` : '—'}</dd>
        </dl>
      </div>
      {result && (
        <p className="panel__note muted" data-testid="lab-outcome">
          Outcome: first ESCAPE at {result.outcome.first_escape_step === null ? 'no step (NO_ACTION throughout)' : `step ${result.outcome.first_escape_step}`} ·
          displacement {num(result.outcome.displacement)} units · backend runtime {result.runtime_seconds.toFixed(3)} s · {result.units_note}
        </p>
      )}
    </section>
  )
}
