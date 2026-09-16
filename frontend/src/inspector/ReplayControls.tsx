import { DIRECTIONS } from '../api/types.ts'
import type { EscapeDemo } from '../demo/useEscapeDemo.ts'
import type { Replay } from './useReplay.ts'

export interface ReplayControlsProps {
  demo: EscapeDemo
  replay: Replay
}

export function ReplayControls({ demo, replay }: ReplayControlsProps) {
  const { state } = demo
  const result = state.result
  const busy = state.phase === 'requesting'
  const hasActivity = result?.neuron_activity != null && replay.steps > 0

  return (
    <section className="replay" data-testid="replay-controls" aria-label="Simulated activity replay">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Activity replay</p>
          <h3 className="panel__title">Simulated activity</h3>
        </div>
        <span className="tag tag--simulated">SIMULATED STATE</span>
      </header>

      <div className="replay__run">
        <div className="segmented segmented--small" role="group" aria-label="Looming direction">
          {DIRECTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`segmented__option ${option === state.direction ? 'segmented__option--selected' : ''}`}
              aria-pressed={option === state.direction}
              onClick={() => demo.setDirection(option)}
              disabled={busy}
              data-testid={`inspector-direction-${option}`}
            >
              {option.toUpperCase()}
            </button>
          ))}
        </div>
        <label className="replay__intensity">
          <span className="muted">intensity</span>
          <input
            type="number"
            min="0"
            max="1"
            step="0.05"
            value={Number.isNaN(state.intensity) ? '' : state.intensity}
            onChange={(event) => demo.setIntensity(event.target.value === '' ? Number.NaN : Number(event.target.value))}
            disabled={busy}
            data-testid="inspector-intensity"
            aria-label="Looming intensity"
          />
        </label>
        <button
          type="button"
          className="btn btn--primary btn--small"
          onClick={demo.trigger}
          disabled={busy || !demo.intensityValid}
          data-testid="inspector-run-looming"
        >
          {busy ? 'RUNNING…' : result ? 'RUN LOOMING AGAIN' : 'RUN LOOMING'}
        </button>
      </div>

      {state.error && (
        <p className="alert" role="alert" data-testid="inspector-run-error">
          {state.error.code}: {state.error.message}
        </p>
      )}

      {hasActivity && result ? (
        <>
          <p className="muted replay__meta" data-testid="replay-run-meta">
            experiment <span className="mono">{result.experiment_id.slice(0, 8)}</span> · {result.stimulus.direction} ·
            intensity {result.stimulus.intensity} · action <strong>{result.action === 'ESCAPE' ? 'ESCAPE' : 'NO ACTION'}</strong>{' '}
            · GF activity {result.gf_activity}
          </p>
          <div className="replay__transport">
            <button type="button" className="btn btn--small" onClick={replay.play} disabled={replay.playing} data-testid="replay-play">
              PLAY
            </button>
            <button type="button" className="btn btn--small" onClick={replay.pause} disabled={!replay.playing} data-testid="replay-pause">
              PAUSE
            </button>
            <button type="button" className="btn btn--small" onClick={replay.stepBack} disabled={replay.step === 0} data-testid="replay-step-back">
              ◀ STEP
            </button>
            <button type="button" className="btn btn--small" onClick={replay.stepForward} disabled={replay.step >= replay.steps} data-testid="replay-step">
              STEP ▶
            </button>
            <button type="button" className="btn btn--ghost btn--small" onClick={replay.reset} data-testid="replay-reset">
              RESET
            </button>
          </div>
          <div className="replay__timeline">
            <input
              type="range"
              min="0"
              max={replay.steps}
              step="1"
              value={replay.step}
              onChange={(event) => replay.seek(Number(event.target.value))}
              data-testid="replay-slider"
              aria-label="Replay step"
            />
            <span className="mono" data-testid="replay-step-label">
              step {replay.step} / {replay.steps}
            </span>
            <span className="muted" data-testid="replay-fired-count">
              {replay.firedCount} simulated spikes
            </span>
          </div>
          <p className="muted replay__note">
            Step 0 is the initial state; each step shows the model state after that backend step. Values are simulated,
            never measured recordings.
          </p>
        </>
      ) : (
        <p className="muted" data-testid="replay-empty">
          {busy ? 'Running the simulation on the backend…' : 'No run yet — trigger looming to replay simulated activity on the graph.'}
        </p>
      )}
    </section>
  )
}
