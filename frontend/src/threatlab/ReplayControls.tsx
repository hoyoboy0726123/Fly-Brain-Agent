import type { ThreatLabEvent } from '../api/types.ts'
import type { ThreatLab } from './useThreatLab.ts'

/** RUN / PLAY / PAUSE / RESET / STEP and the slider with ESCAPE markers (click = jump). */
export function ReplayControls({ lab }: { lab: ThreatLab }) {
  const { state, steps, current } = lab
  const hasRun = steps > 0
  const running = state.phase === 'running'
  const events = state.result?.outcome.events ?? []
  const markers = events.filter((e): e is ThreatLabEvent => e.kind === 'first_escape' || e.kind === 'escape')
  const landed = events.find((e) => e.kind === 'landed')
  const atEnd = hasRun && state.step >= steps - 1

  return (
    <div className="replay lab-replay" data-testid="lab-replay">
      <div className="replay__run">
        <button type="button" className="btn btn--primary" onClick={lab.run} disabled={running || !lab.paramsValid} data-testid="lab-run">
          {running ? 'RUNNING…' : 'RUN EXPERIMENT'}
        </button>
        <button type="button" className="btn" onClick={lab.play} disabled={!hasRun || state.playing} data-testid="lab-play">
          PLAY
        </button>
        <button type="button" className="btn" onClick={lab.pause} disabled={!hasRun || !state.playing} data-testid="lab-pause">
          PAUSE
        </button>
        <button type="button" className="btn" onClick={lab.stepBack} disabled={!hasRun || state.step === 0} data-testid="lab-step-back">
          ◀ STEP
        </button>
        <button type="button" className="btn" onClick={lab.stepForward} disabled={!hasRun || atEnd} data-testid="lab-step-forward">
          STEP ▶
        </button>
        <button type="button" className="btn btn--ghost" onClick={lab.reset} disabled={!hasRun} data-testid="lab-reset">
          RESET
        </button>
        <span className="mono lab-replay__status" data-testid="lab-status" data-phase={state.phase} data-playing={state.playing}>
          {state.phase === 'idle' ? 'WAITING FOR EXPERIMENT' : state.phase === 'running' ? 'running' : state.phase === 'error' ? 'NO RESULT' : state.playing ? 'playing' : 'paused'}
        </span>
      </div>

      <div className="lab-replay__timeline" data-testid="lab-timeline">
        <div className="lab-replay__track">
          <input
            type="range"
            min={0}
            max={Math.max(0, steps - 1)}
            step={1}
            value={hasRun ? state.step : 0}
            disabled={!hasRun}
            onChange={(event) => lab.seek(Number(event.target.value))}
            aria-label="Replay step"
            data-testid="lab-slider"
          />
          <div className="lab-replay__markers" aria-hidden={markers.length === 0}>
            {markers.map((event) => (
              <button
                key={`${event.kind}-${event.step_index}`}
                type="button"
                className={`lab-replay__marker lab-replay__marker--${event.kind} ${state.step === event.step_index ? 'lab-replay__marker--here' : ''}`}
                style={{ left: `${steps > 1 ? (event.step_index / (steps - 1)) * 100 : 0}%` }}
                title={`${event.description} (step ${event.step_index})`}
                onClick={() => lab.seek(event.step_index)}
                data-testid={`lab-marker-${event.kind}-${event.step_index}`}
              >
                ⚡{event.kind === 'first_escape' ? ' ESCAPE' : ''}
              </button>
            ))}
            {landed && (
              <button
                type="button"
                className="lab-replay__marker lab-replay__marker--landed"
                style={{ left: `${steps > 1 ? (landed.step_index / (steps - 1)) * 100 : 0}%` }}
                title={`${landed.description} (step ${landed.step_index})`}
                onClick={() => lab.seek(landed.step_index)}
                data-testid={`lab-marker-landed-${landed.step_index}`}
              >
                ▼
              </button>
            )}
          </div>
        </div>
        <span className="mono" data-testid="lab-step" data-step={hasRun ? state.step : -1}>
          {hasRun && current ? `step ${state.step} / ${steps - 1} · t = ${current.simulation_time.toFixed(2)} s` : 'step — / —'}
        </span>
      </div>
      <p className="replay__note muted">
        Replay of the backend-recorded timeline: selecting a step shows the world, sensor, simulated brain activity, motor command and body
        recorded at that step. ⚡ marks steps where the decoded action was ESCAPE.
      </p>
    </div>
  )
}
