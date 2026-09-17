import { describeErrorCode } from '../api/client.ts'
import { INTERVENTION_SELECTORS, type InterventionSelector } from '../api/types.ts'
import { BiologicalContext } from './BiologicalContext.tsx'
import { ComparisonPanel } from './ComparisonPanel.tsx'
import { TrialPanel } from './TrialPanel.tsx'
import type { InterventionLab } from './useInterventionLab.ts'

const SELECTOR_LABELS: Record<InterventionSelector, string> = {
  CONTROL: 'CONTROL',
  SILENCE_LC4: 'SILENCE LC4',
  SILENCE_LPLC2: 'SILENCE LPLC2',
  SILENCE_LC4_LPLC2: 'SILENCE LC4 + LPLC2',
}

/** NEURAL INTERVENTION LAB (P7.2): CONTROL vs COMPUTATIONAL FIRING SUPPRESSION, one shared cursor. */
export function InterventionLabView({ lab }: { lab: InterventionLab }) {
  const { state, control, intervention, cursorMax } = lab
  const hasRun = cursorMax >= 0
  const running = state.phase === 'running'
  const atEnd = hasRun && state.step >= cursorMax
  const selectorInfo = state.config?.selectors.find((s) => s.selector === state.selector) ?? null
  const summary = state.result?.comparison.differences.summary ?? null
  return (
    <div className="lab ilab" data-testid="intervention-lab" data-phase={state.phase}>
      <header className="lab__header">
        <div>
          <p className="panel__kicker">Embodiment · P7.2</p>
          <h2 className="lab__title" data-testid="ilab-title">
            NEURAL INTERVENTION LAB
          </h2>
          <p className="lab__tagline">
            Run the same virtual threat twice — CONTROL and one computational intervention — and compare what the simulated escape
            circuit does. The intervention suppresses simulated firing of selected neurons inside the simulation engine; their biological
            structure (ids, edges, synapse counts) is untouched. The simulation decides the outcome; nothing is pre-filled.
          </p>
        </div>
        <span className="tag tag--suppressed ilab__tag">COMPUTATIONAL FIRING SUPPRESSION · layer: COMPUTATIONAL DYNAMICS</span>
      </header>

      {state.configError && (
        <div className="banner banner--error" role="alert" data-testid="ilab-config-error">
          <strong>{describeErrorCode(state.configError.code)}</strong> — the intervention configuration could not be loaded ({state.configError.code}):{' '}
          {state.configError.message}{' '}
          <button type="button" className="btn btn--ghost btn--small" onClick={lab.reloadConfig}>
            Retry
          </button>
        </div>
      )}
      {state.error && (
        <div className="banner banner--error" role="alert" data-testid="ilab-error">
          <strong>NO RESULT</strong> — {describeErrorCode(state.error.code)} ({state.error.code}): {state.error.message}. No comparison was
          returned, so nothing is replayed.
        </div>
      )}

      <section className="panel ilab__setup" data-testid="ilab-setup">
        <div className="ilab__controls">
          <label className="control ilab__selector">
            <span className="control__label">Intervention</span>
            <select value={state.selector} onChange={(event) => lab.setSelector(event.target.value as InterventionSelector)} disabled={running} data-testid="ilab-selector">
              {INTERVENTION_SELECTORS.map((selector) => (
                <option key={selector} value={selector}>
                  {SELECTOR_LABELS[selector]}
                </option>
              ))}
            </select>
          </label>
          <div className="ilab__resolved mono" data-testid="ilab-resolved">
            {selectorInfo
              ? selectorInfo.resolved.neuron_count > 0
                ? `${selectorInfo.resolved.neuron_count} neurons resolved from the circuit (${Object.entries(selectorInfo.resolved.per_cell_type_counts)
                    .map(([ct, n]) => `${ct} ${n}`)
                    .join(', ')})`
                : 'no intervention (A/A check)'
              : 'resolving targets…'}
          </div>
          <div className="lab-params__grid ilab__params">
            <label className="lab-param">
              <span className="control__label">seed</span>
              <input type="number" className="mono" value={state.params.seed} min={0} step={1} disabled={running} onChange={(e) => lab.setParams({ seed: Number(e.target.value) })} data-testid="ilab-seed" />
            </label>
            <label className="lab-param">
              <span className="control__label">loop steps</span>
              <input type="number" className="mono" value={state.params.maxSteps} min={1} max={200} step={1} disabled={running} onChange={(e) => lab.setParams({ maxSteps: Number(e.target.value) })} data-testid="ilab-steps" />
            </label>
            <label className="lab-param">
              <span className="control__label">start distance (units)</span>
              <input type="number" className="mono" value={state.params.startDistance} min={1} max={100} step={0.5} disabled={running} onChange={(e) => lab.setParams({ startDistance: Number(e.target.value) })} data-testid="ilab-start-distance" />
            </label>
            <label className="lab-param">
              <span className="control__label">approach speed (units/s)</span>
              <input type="number" className="mono" value={state.params.approachSpeed} min={0} max={50} step={0.5} disabled={running} onChange={(e) => lab.setParams({ approachSpeed: Number(e.target.value) })} data-testid="ilab-approach-speed" />
            </label>
          </div>
          <button type="button" className="btn btn--primary btn--large" onClick={lab.run} disabled={running || !lab.paramsValid} data-testid="ilab-run">
            {running ? 'RUNNING…' : 'RUN CONTROL + INTERVENTION'}
          </button>
        </div>
        <p className="ilab__matched mono" data-testid="ilab-matched">
          {state.result
            ? state.result.comparison.matched_conditions.all_matched
              ? 'SAME WORLD • SAME SEED • SAME MODEL — verified by the backend'
              : 'CONDITIONS NOT MATCHED'
            : 'SAME WORLD • SAME SEED • SAME MODEL — the only difference will be the intervention'}
        </p>
      </section>

      <main className="ilab__grid" id="ilab-panels">
        <TrialPanel role="control" phase={state.phase} trial={state.result?.control ?? null} cursor={control} suppressedCellTypes={[]} step={state.step} />
        <TrialPanel role="intervention" phase={state.phase} trial={state.result?.intervention ?? null} cursor={intervention} suppressedCellTypes={lab.suppressedCellTypes} step={state.step} />
      </main>

      <div className="replay lab-replay ilab__replay" data-testid="ilab-replay">
        <div className="replay__run">
          <span className="control__label">SAME STEP</span>
          <button type="button" className="btn" onClick={lab.stepBack} disabled={!hasRun || state.step === 0} data-testid="ilab-step-back">
            ◀ STEP
          </button>
          <button type="button" className="btn" onClick={lab.play} disabled={!hasRun || state.playing} data-testid="ilab-play">
            PLAY
          </button>
          <button type="button" className="btn" onClick={lab.pause} disabled={!hasRun || !state.playing} data-testid="ilab-pause">
            PAUSE
          </button>
          <button type="button" className="btn" onClick={lab.stepForward} disabled={!hasRun || atEnd} data-testid="ilab-step-forward">
            STEP ▶
          </button>
          <button type="button" className="btn btn--ghost" onClick={lab.reset} disabled={!hasRun} data-testid="ilab-reset">
            RESET
          </button>
          <span className="mono lab-replay__status" data-testid="ilab-status" data-playing={state.playing}>
            {state.phase === 'idle' ? 'WAITING FOR EXPERIMENT' : state.phase === 'running' ? 'running' : state.phase === 'error' ? 'NO RESULT' : state.playing ? 'playing' : 'paused'}
          </span>
        </div>
        <div className="lab-replay__timeline">
          <div className="lab-replay__track">
            <input
              type="range"
              min={0}
              max={Math.max(0, cursorMax)}
              step={1}
              value={hasRun ? state.step : 0}
              disabled={!hasRun}
              onChange={(event) => lab.seek(Number(event.target.value))}
              aria-label="Shared replay step for both trials"
              data-testid="ilab-slider"
            />
            <div className="lab-replay__markers">
              {state.result?.control.experiment.outcome.first_escape_step !== null && state.result?.control.experiment.outcome.first_escape_step !== undefined && (
                <button
                  type="button"
                  className="lab-replay__marker lab-replay__marker--first_escape"
                  style={{ left: `${cursorMax > 0 ? (state.result.control.experiment.outcome.first_escape_step / cursorMax) * 100 : 0}%` }}
                  onClick={() => lab.seek(state.result?.control.experiment.outcome.first_escape_step ?? 0)}
                  title={`CONTROL first ESCAPE (step ${state.result.control.experiment.outcome.first_escape_step})`}
                  data-testid="ilab-marker-control-escape"
                >
                  ⚡A
                </button>
              )}
              {state.result?.intervention.experiment.outcome.first_escape_step !== null && state.result?.intervention.experiment.outcome.first_escape_step !== undefined && (
                <button
                  type="button"
                  className="lab-replay__marker lab-replay__marker--escape lab-replay__marker--b"
                  style={{ left: `${cursorMax > 0 ? (state.result.intervention.experiment.outcome.first_escape_step / cursorMax) * 100 : 0}%` }}
                  onClick={() => lab.seek(state.result?.intervention.experiment.outcome.first_escape_step ?? 0)}
                  title={`INTERVENTION first ESCAPE (step ${state.result.intervention.experiment.outcome.first_escape_step})`}
                  data-testid="ilab-marker-intervention-escape"
                >
                  ⚡B
                </button>
              )}
            </div>
          </div>
          <span className="mono" data-testid="ilab-step" data-step={hasRun ? state.step : -1}>
            {hasRun ? `step ${state.step} / ${cursorMax}` : 'step — / —'}
          </span>
        </div>
        <p className="replay__note muted">One cursor drives both trials: at step N the CONTROL column shows CONTROL step N and the INTERVENTION column shows INTERVENTION step N.</p>
      </div>

      {state.result && <ComparisonPanel result={state.result} />}
      <BiologicalContext config={state.config} summary={summary} />
    </div>
  )
}
