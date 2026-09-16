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

/** Compact backend liveness indicator (GET /health) shown in the header. */
export function BackendBadge() {
  const { state, refresh } = useBackendHealth()

  return (
    <section className={`backend backend--${state.kind}`} data-testid="backend-health" aria-live="polite">
      <span className="backend__dot" aria-hidden="true" />
      <span className="backend__title">Backend</span>
      <span className={`badge badge--${state.kind}`} data-testid="backend-health-status">
        {statusLabel(state.kind)}
      </span>
      {state.kind === 'ok' && (
        <span className="backend__meta">
          <span data-testid="backend-health-service">{state.health.service}</span>
          <span aria-hidden="true">·</span>
          <span>
            v<span data-testid="backend-health-version">{state.health.version}</span>
          </span>
          <span aria-hidden="true">·</span>
          <span data-testid="backend-health-environment">{state.health.environment}</span>
          <span aria-hidden="true">·</span>
          <span data-testid="backend-health-phase">{state.health.phase}</span>
        </span>
      )}
      {state.kind === 'error' && (
        <span className="backend__error" role="alert" data-testid="backend-health-error">
          Could not reach the backend: {state.message}
        </span>
      )}
      <button type="button" className="btn btn--ghost btn--small" onClick={refresh} disabled={state.kind === 'loading'}>
        Re-check
      </button>
    </section>
  )
}
