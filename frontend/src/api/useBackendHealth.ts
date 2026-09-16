import { useCallback, useEffect, useState } from 'react'

import { fetchHealth } from './client.ts'
import type { HealthResponse } from './types.ts'

export type BackendHealthState =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse; checkedAt: Date }
  | { kind: 'error'; message: string; checkedAt: Date }

export interface UseBackendHealth {
  state: BackendHealthState
  refresh: () => void
}

/** Fetches `GET /health` once on mount; `refresh()` re-checks on demand. */
export function useBackendHealth(): UseBackendHealth {
  const [state, setState] = useState<BackendHealthState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: 'loading' })

    fetchHealth(controller.signal)
      .then((health) => setState({ kind: 'ok', health, checkedAt: new Date() }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof Error ? error.message : 'Unknown error'
        setState({ kind: 'error', message, checkedAt: new Date() })
      })

    return () => controller.abort()
  }, [attempt])

  const refresh = useCallback(() => setAttempt((n) => n + 1), [])

  return { state, refresh }
}
