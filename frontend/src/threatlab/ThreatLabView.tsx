import { describeErrorCode } from '../api/client.ts'
import { Arena } from './Arena.tsx'
import { Boundaries, LabLabels } from './Boundaries.tsx'
import { LoopStory } from './LoopStory.tsx'
import { Metrics, WorldBodyPanel } from './Panels.tsx'
import { ParamsForm } from './ParamsForm.tsx'
import { ReplayControls } from './ReplayControls.tsx'
import { ThreatLabBrain } from './ThreatLabBrain.tsx'
import type { ThreatLab } from './useThreatLab.ts'

/** VIRTUAL THREAT LAB (P7.1): replay of one backend-computed closed-loop experiment. */
export function ThreatLabView({ lab }: { lab: ThreatLab }) {
  const { state, current } = lab
  const groups = state.result?.groups ?? state.config?.groups ?? []
  const edges = state.config?.group_edges ?? []
  return (
    <div className="lab" data-testid="threat-lab" data-phase={state.phase}>
      <header className="lab__header">
        <div>
          <p className="panel__kicker">Embodiment · P7.1</p>
          <h2 className="lab__title" data-testid="lab-title">
            VIRTUAL THREAT LAB
          </h2>
          <p className="lab__tagline">
            One closed loop, computed by the backend and replayed here: a virtual object approaches, the virtual sensor turns its
            angular size into a looming stimulus, the escape circuit is simulated on MaleCNS structure, the decoded action becomes a
            body command, the body moves in the world.
          </p>
        </div>
        <LabLabels config={state.config} />
      </header>

      {state.configError && (
        <div className="banner banner--error" role="alert" data-testid="lab-config-error">
          <strong>{describeErrorCode(state.configError.code)}</strong> — the Threat Lab configuration could not be loaded ({state.configError.code}):{' '}
          {state.configError.message}{' '}
          <button type="button" className="btn btn--ghost btn--small" onClick={lab.reloadConfig}>
            Retry
          </button>
        </div>
      )}
      {state.error && (
        <div className="banner banner--error" role="alert" data-testid="lab-error">
          <strong>NO RESULT</strong> — {describeErrorCode(state.error.code)} ({state.error.code}): {state.error.message}. No timeline was
          returned, so nothing is replayed.
        </div>
      )}

      <LoopStory step={current} />

      <main className="lab__grid" id="lab-panels">
        <section className="panel panel--lab-arena" aria-labelledby="lab-arena-title">
          <header className="panel__header">
            <div>
              <p className="panel__kicker">Arena · top-down</p>
              <h2 id="lab-arena-title" className="panel__title">
                Virtual world
              </h2>
            </div>
            <span className="tag tag--input">COMPUTATIONAL</span>
          </header>
          <Arena phase={state.phase} result={state.result} step={current} />
          <Metrics phase={state.phase} step={current} />
          <ReplayControls lab={lab} />
        </section>

        <ThreatLabBrain
          groups={groups}
          edges={edges}
          circuitId={state.config?.circuit.circuit_id ?? state.result?.provenance.circuit_id ?? null}
          phase={state.phase}
          brain={current?.brain ?? null}
          loopStep={current?.step_index ?? null}
        />

        <div className="lab__side">
          <section className="panel panel--lab-params" aria-labelledby="lab-params-title">
            <header className="panel__header">
              <div>
                <p className="panel__kicker">Experiment</p>
                <h2 id="lab-params-title" className="panel__title">
                  World parameters
                </h2>
              </div>
            </header>
            <ParamsForm lab={lab} />
          </section>
          <WorldBodyPanel step={current} result={state.result} />
        </div>
      </main>

      <Boundaries config={state.config} result={state.result} />
    </div>
  )
}
