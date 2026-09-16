import { useMemo } from 'react'

import { BackendBadge } from './components/BackendBadge.tsx'
import { BrainPanel } from './brain/BrainPanel.tsx'
import { APP_SUBTITLE, APP_TITLE, DISCLAIMER, SCIENTIFIC_LABELS } from './content.ts'
import { ActionPanel } from './dashboard/ActionPanel.tsx'
import { HowItWorks } from './dashboard/HowItWorks.tsx'
import { useEscapeDemo, type DemoOptions } from './demo/useEscapeDemo.ts'
import { EnvironmentPanel } from './environment/EnvironmentPanel.tsx'

/** `?pace=<ms>` speeds replay up for tests; `?transport=rest` forces the REST path. */
function optionsFromLocation(): DemoOptions {
  const params = new URLSearchParams(window.location.search)
  const options: DemoOptions = {}
  const pace = params.get('pace')
  if (pace !== null && Number.isFinite(Number(pace)) && Number(pace) >= 0) options.paceMs = Number(pace)
  if (params.get('transport') === 'rest') options.transport = 'rest'
  return options
}

export function App() {
  const options = useMemo(optionsFromLocation, [])
  const demo = useEscapeDemo(options)
  const { state, view } = demo
  const groups = state.result?.group_activity.groups ?? state.config?.groups ?? []
  const edges = state.config?.group_edges ?? []
  const labels = state.config?.scientific_labels ?? SCIENTIFIC_LABELS

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <h1>{APP_TITLE}</h1>
          <p className="subtitle" data-testid="subtitle">
            {APP_SUBTITLE}
          </p>
          <ul className="labels" data-testid="scientific-labels" aria-label="Scientific labelling">
            {labels.map((label) => (
              <li key={label} className="labels__item">
                {label}
              </li>
            ))}
          </ul>
        </div>
        <BackendBadge />
      </header>

      {state.configError && (
        <div className="banner banner--error" role="alert" data-testid="config-error">
          <strong>Backend unavailable</strong> — the escape configuration could not be loaded ({state.configError.code}):{' '}
          {state.configError.message}{' '}
          <button type="button" className="btn btn--ghost btn--small" onClick={demo.reloadConfig}>
            Retry
          </button>
        </div>
      )}

      <main className="grid">
        <EnvironmentPanel
          direction={state.direction}
          intensity={state.intensity}
          intensityValid={demo.intensityValid}
          phase={state.phase}
          view={view}
          onDirectionChange={demo.setDirection}
          onIntensityChange={demo.setIntensity}
          onTrigger={demo.trigger}
          onReset={demo.reset}
        />
        <BrainPanel groups={groups} edges={edges} circuitId={state.config?.circuit_id ?? state.result?.circuit_id ?? null} phase={state.phase} view={view} />
        <ActionPanel
          phase={state.phase}
          view={view}
          result={state.result}
          error={state.error}
          transport={state.transport}
          streamedEvents={state.streamedEvents}
        />
      </main>

      <HowItWorks config={state.config} configError={state.configError} />

      <footer className="app__footer">
        <p className="disclaimer" data-testid="disclaimer">
          {state.config?.disclaimer ?? DISCLAIMER}
        </p>
        <p className="muted">
          Neural activity shown here is simulated (simplified neural dynamics). Structural connectivity from a biological
          dataset (MaleCNS v1.0, CC-BY 4.0). No camera or physical device is used.
        </p>
      </footer>
    </div>
  )
}
