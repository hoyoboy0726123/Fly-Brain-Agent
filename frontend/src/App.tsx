import { HealthStatus } from './components/HealthStatus.tsx'

export function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1>FlyBrain Agent</h1>
        <p className="tagline">Connectome-grounded simulation · P0 bootstrap skeleton</p>
      </header>

      <main className="app__main">
        <HealthStatus />
      </main>

      <footer className="app__footer muted">
        <p>
          Structural connectivity will be loaded from a biological dataset in a later phase
          (P1). Any neural activity this application will display is simulated, not measured.
          No dataset is loaded or required in P0.
        </p>
      </footer>
    </div>
  )
}
