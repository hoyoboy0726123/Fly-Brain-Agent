import { describeErrorCode } from '../api/client.ts'
import type { EscapeRunResult, TimelineEvent } from '../api/types.ts'
import type { DemoError, DemoPhase, DemoView, Transport } from '../demo/useEscapeDemo.ts'

export interface ActionPanelProps {
  phase: DemoPhase
  view: DemoView
  result: EscapeRunResult | null
  error: DemoError | null
  transport: Transport | null
  streamedEvents: number
}

/** Display text for the decoded action. Only NO ACTION / ESCAPE exist; anything else is a bug. */
function actionText(phase: DemoPhase, view: DemoView): { text: string; kind: string } {
  if (phase === 'requesting') return { text: 'RUNNING…', kind: 'pending' }
  if (phase === 'replaying') return { text: 'DECODING…', kind: 'pending' }
  if (phase === 'error') return { text: 'NO RESULT', kind: 'error' }
  if (phase === 'finished' && view.action === 'ESCAPE') return { text: 'ESCAPE', kind: 'escape' }
  if (phase === 'finished' && view.action === 'NO_ACTION') return { text: 'NO ACTION', kind: 'no-action' }
  return { text: '—', kind: 'idle' }
}

const TIMELINE_ORDER: TimelineEvent['tag'][] = [
  't0_stimulus',
  't1_sensory_activation',
  't2_intermediate_activity',
  't3_output_activation',
  't4_decoded_action',
]

function short(hash: string): string {
  return hash.length > 14 ? `${hash.slice(0, 12)}…` : hash
}

export function ActionPanel({ phase, view, result, error, transport, streamedEvents }: ActionPanelProps) {
  const action = actionText(phase, view)
  const finished = phase === 'finished' && result !== null
  const reached = new Set(view.reachedEvents.map((e) => e.tag))
  if (finished) reached.add('t4_decoded_action')

  return (
    <section className="panel panel--action" data-testid="action-panel" aria-labelledby="action-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Action</p>
          <h2 id="action-title" className="panel__title">
            Decoded behaviour
          </h2>
        </div>
        <span className="tag tag--decoding">APPLICATION DECODING</span>
      </header>

      <div className={`action action--${action.kind}`} data-testid="action-display" aria-live="polite">
        <span className="action__value" data-testid="action-value" data-action={view.action ?? ''}>
          {action.text}
        </span>
        <span className="action__caption">
          {phase === 'idle' && 'awaiting stimulus'}
          {phase === 'requesting' && 'running the simulation on the backend'}
          {phase === 'replaying' && `replaying backend timeline · step ${view.step} / ${view.steps}`}
          {finished && 'decoded from simulated giant-fiber activity'}
          {phase === 'error' && 'no action is shown when the backend run fails'}
        </span>
        <span className="status-pill" data-testid="demo-status" data-phase={phase}>
          {phase}
        </span>
      </div>

      {error && (
        <div className="alert" role="alert" data-testid="demo-error" data-error-code={error.code}>
          <strong>{describeErrorCode(error.code)}</strong>
          <span className="mono muted"> [{error.code}]</span>
          <p>{error.message}</p>
        </div>
      )}

      <dl className="kv" data-testid="action-metadata">
        <dt>GF activity</dt>
        <dd data-testid="gf-activity">{finished && view.gfActivity ? view.gfActivity : '—'}</dd>
        <dt>GF spikes</dt>
        <dd>{result ? result.decision.output_spike_count : '—'}</dd>
        <dt>First GF spike</dt>
        <dd>{result ? (result.decision.first_output_fire_step ?? 'none') : '—'}</dd>
        <dt>First sensory spike</dt>
        <dd>{result ? (result.sensory_activity.first_fire_step ?? 'none') : '—'}</dd>
        <dt>Stimulated neurons</dt>
        <dd>
          {result ? `${result.sensory_activity.stimulated_count} (${result.sensory_activity.stimulated_sides.join('+')})` : '—'}
        </dd>
        <dt>Transport</dt>
        <dd data-testid="transport">
          {transport ?? '—'}
          {transport === 'websocket' && streamedEvents > 0 ? ` · ${streamedEvents} events` : ''}
        </dd>
        <dt>Experiment</dt>
        <dd className="mono" data-testid="experiment-id">
          {result ? result.experiment_id.slice(0, 8) : '—'}
        </dd>
        <dt>Circuit hash</dt>
        <dd className="mono" data-testid="result-circuit-hash" title={result?.circuit_hash ?? ''}>
          {result ? short(result.circuit_hash) : '—'}
        </dd>
        <dt>Runtime</dt>
        <dd>{result ? `${(result.runtime_seconds * 1000).toFixed(1)} ms` : '—'}</dd>
      </dl>

      <ol className="timeline" data-testid="timeline">
        {TIMELINE_ORDER.map((tag) => {
          const event = result?.timeline.find((e) => e.tag === tag)
          const done = result !== null && reached.has(tag)
          return (
            <li key={tag} className={`timeline__item ${done ? 'timeline__item--reached' : ''}`} data-tag={tag} data-reached={done}>
              <span className="timeline__tag mono">{tag.slice(0, 2)}</span>
              <span className="timeline__body">
                <span className="timeline__label">{event?.label ?? tag.slice(3).replaceAll('_', ' ')}</span>
                <span className="timeline__desc muted">
                  {event ? (event.step === null ? event.description : `step ${event.step} · ${event.description}`) : '—'}
                </span>
              </span>
            </li>
          )
        })}
      </ol>

      <p className="panel__note muted">
        Only <strong>NO ACTION</strong> and <strong>ESCAPE</strong> are decoded: the giant fiber responds invariantly to
        stimulus azimuth, so left/right is never decoded. The firing GF side is metadata.
      </p>
    </section>
  )
}
