import { useBackendHealth } from '../api/useBackendHealth.ts'

function statusLabel(kind: 'loading' | 'ok' | 'error'): string {
  switch (kind) {
    case 'loading':
      return 'checking'
    case 'ok':
      return 'ok'
    case 'error':
      return 'unreachable'
  }
}

export function HealthStatus() {
  const { state, refresh } = useBackendHealth()

  return (
    <section className="card" data-testid="backend-health" aria-live="polite">
      <header className="card__header">
        <h2>Backend health</h2>
        <span className={`badge badge--${state.kind}`} data-testid="backend-health-status">
          {statusLabel(state.kind)}
        </span>
      </header>

      {state.kind === 'loading' && <p className="muted">Contacting backend…</p>}

      {state.kind === 'ok' && (
        <dl className="kv">
          <dt>Service</dt>
          <dd data-testid="backend-health-service">{state.health.service}</dd>
          <dt>Version</dt>
          <dd data-testid="backend-health-version">{state.health.version}</dd>
          <dt>Environment</dt>
          <dd data-testid="backend-health-environment">{state.health.environment}</dd>
          <dt>Phase</dt>
          <dd data-testid="backend-health-phase">{state.health.phase}</dd>
          <dt>Checked</dt>
          <dd>{state.checkedAt.toLocaleTimeString()}</dd>
        </dl>
      )}

      {state.kind === 'error' && (
        <p className="error" role="alert" data-testid="backend-health-error">
          Could not reach the backend: {state.message}
        </p>
      )}

      <button type="button" onClick={refresh} disabled={state.kind === 'loading'}>
        Re-check
      </button>
    </section>
  )
}
