import { useEffect, useMemo, useState } from 'react'

import { BackendBadge } from './components/BackendBadge.tsx'
import { APP_SUBTITLE, APP_TITLE, DEFAULT_PACE_MS, DISCLAIMER, SCIENTIFIC_LABELS } from './content.ts'
import { DemoView } from './demo/DemoView.tsx'
import { useEscapeDemo, type DemoOptions } from './demo/useEscapeDemo.ts'
import { InspectorView } from './inspector/InspectorView.tsx'
import { Hero } from './landing/Hero.tsx'

type View = 'demo' | 'inspector'

/** `?pace=<ms>` speeds replay up for tests; `?transport=rest` forces the REST path. */
function optionsFromLocation(): DemoOptions {
  const params = new URLSearchParams(window.location.search)
  const options: DemoOptions = {}
  const pace = params.get('pace')
  if (pace !== null && Number.isFinite(Number(pace)) && Number(pace) >= 0) options.paceMs = Number(pace)
  if (params.get('transport') === 'rest') options.transport = 'rest'
  return options
}

function viewFromHash(): View {
  return window.location.hash === '#inspector' ? 'inspector' : 'demo'
}

export function App() {
  const options = useMemo(optionsFromLocation, [])
  const demo = useEscapeDemo(options)
  const { state } = demo
  const [view, setView] = useState<View>(viewFromHash)
  const labels = state.config?.scientific_labels ?? SCIENTIFIC_LABELS

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const switchView = (next: View) => {
    setView(next)
    const hash = next === 'inspector' ? '#inspector' : ''
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${hash}`)
    window.scrollTo({ top: 0 })
  }

  const runDemo = () => {
    demo.trigger()
    window.setTimeout(() => document.getElementById('demo-panels')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  return (
    <div className="app">
      <header className={`app__header ${view === 'demo' ? 'app__header--landing' : ''}`}>
        <div className="app__brand">
          {view === 'demo' ? (
            <Hero running={state.phase === 'requesting'} canRun={demo.intensityValid} onRunDemo={runDemo} onExplore={() => switchView('inspector')} />
          ) : (
            <>
              <h1>{APP_TITLE}</h1>
              <p className="subtitle" data-testid="subtitle">
                {APP_SUBTITLE}
              </p>
            </>
          )}
          <ul className="labels" data-testid="scientific-labels" aria-label="Scientific labelling">
            {labels.map((label) => (
              <li key={label} className="labels__item">
                {label}
              </li>
            ))}
          </ul>
        </div>
        <div className="app__tools">
          <BackendBadge />
          <nav className="tabs" aria-label="Views">
            <button type="button" className={`tabs__tab ${view === 'demo' ? 'tabs__tab--active' : ''}`} aria-pressed={view === 'demo'} onClick={() => switchView('demo')} data-testid="tab-demo">
              Demo
            </button>
            <button
              type="button"
              className={`tabs__tab ${view === 'inspector' ? 'tabs__tab--active' : ''}`}
              aria-pressed={view === 'inspector'}
              onClick={() => switchView('inspector')}
              data-testid="tab-inspector"
            >
              Brain Inspector
            </button>
          </nav>
        </div>
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

      {view === 'demo' ? <DemoView demo={demo} /> : <InspectorView demo={demo} paceMs={options.paceMs ?? DEFAULT_PACE_MS} />}

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
