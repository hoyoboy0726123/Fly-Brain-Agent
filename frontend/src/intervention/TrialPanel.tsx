import type { ThreatLabRunResult, ThreatLabStep, TrialView } from '../api/types.ts'
import { Arena } from '../threatlab/Arena.tsx'
import { ThreatLabBrain } from '../threatlab/ThreatLabBrain.tsx'
import type { LabPhase } from '../threatlab/useThreatLab.ts'
import type { TrialCursor } from './useInterventionLab.ts'

export interface TrialPanelProps {
  role: 'control' | 'intervention'
  phase: LabPhase
  trial: TrialView | null
  cursor: TrialCursor
  suppressedCellTypes: readonly string[]
  step: number
}

function num(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

/** One trial column: arena + brain (SUPPRESSED groups marked) + action, all from the backend record. */
export function TrialPanel({ role, phase, trial, cursor, suppressedCellTypes, step }: TrialPanelProps) {
  const experiment: ThreatLabRunResult | null = trial?.experiment ?? null
  const current: ThreatLabStep | null = cursor.step
  const ended = cursor.ended
  const suppressed = role === 'intervention' ? suppressedCellTypes : []
  const action = current ? current.brain.action : ended ? 'TRIAL ENDED' : phase === 'error' ? 'NO RESULT' : phase === 'running' ? 'RUNNING' : 'WAITING FOR EXPERIMENT'
  const groups = experiment?.groups ?? []
  return (
    <section className={`panel trial trial--${role}`} data-testid={`trial-${role}`} data-step={current?.step_index ?? -1} data-ended={ended} aria-labelledby={`trial-${role}-title`}>
      <header className="panel__header">
        <div>
          <p className="panel__kicker">{role === 'control' ? 'Trial A' : 'Trial B'}</p>
          <h2 id={`trial-${role}-title`} className="panel__title trial__title">
            {role === 'control' ? 'CONTROL' : 'INTERVENTION'}
          </h2>
        </div>
        <span className={`tag ${role === 'control' ? 'tag--bio' : 'tag--suppressed'}`} data-testid={`trial-${role}-label`}>
          {role === 'control' ? 'NO INTERVENTION' : trial ? trial.resolved_targets.label : 'COMPUTATIONAL FIRING SUPPRESSION'}
        </span>
      </header>
      {role === 'intervention' && trial && trial.intervention_config.intervention_type === 'SUPPRESS_FIRING' && (
        <p className="trial__targets mono" data-testid="trial-intervention-targets">
          {trial.resolved_targets.neuron_count} neurons resolved from the circuit ({trial.resolved_targets.cell_types.join(' + ')}) · suppressed threshold crossings{' '}
          {trial.suppressed_events}
        </p>
      )}
      <div className="trial__arena">
        <Arena phase={phase} result={experiment} step={current} />
        {ended && (
          <div className="trial__ended" data-testid={`trial-${role}-ended`}>
            TRIAL ENDED
          </div>
        )}
      </div>
      <dl className="lab-metrics lab-metrics--trial">
        <div className="lab-metric">
          <dt>DISTANCE</dt>
          <dd className="mono" data-testid={`trial-${role}-distance`}>
            {current ? `${num(current.sensor.distance)} units` : '—'}
          </dd>
        </div>
        <div className="lab-metric">
          <dt>LOOMING INPUT</dt>
          <dd className="mono" data-testid={`trial-${role}-looming`}>
            {current ? num(current.sensor.intensity, 3) : '—'}
          </dd>
        </div>
        <div className="lab-metric">
          <dt>BODY</dt>
          <dd className="mono" data-testid={`trial-${role}-body`} data-x={current?.body.position.x ?? ''} data-z={current?.body.position.z ?? ''}>
            {current ? `(${num(current.body.position.x)}, ${num(current.body.position.z)})${current.body.grounded ? '' : ' airborne'}` : '—'}
          </dd>
        </div>
        <div className={`lab-metric lab-metric--action ${action === 'ESCAPE' ? 'lab-metric--escape' : ''}`}>
          <dt>ACTION</dt>
          <dd className="mono" data-testid={`trial-${role}-action`} data-value={action}>
            {action}
          </dd>
        </div>
      </dl>
      <ThreatLabBrain
        groups={groups}
        edges={[]}
        circuitId={experiment?.provenance.circuit_id ?? null}
        phase={phase}
        brain={current?.brain ?? null}
        loopStep={current?.step_index ?? null}
        suppressedCellTypes={suppressed}
        compact
        title={role === 'control' ? 'LC4 / LPLC2 → DNp01' : `LC4 / LPLC2 → DNp01${suppressed.length ? ` · ${suppressed.join(' + ')} suppressed` : ''}`}
      />
      <p className="muted panel__note">
        {ended
          ? `This trial recorded ${cursor.steps} steps; step ${step} is beyond its timeline, so nothing is shown (its last state is not reused).`
          : 'Everything shown is the backend-recorded state at the shared cursor.'}
      </p>
    </section>
  )
}
