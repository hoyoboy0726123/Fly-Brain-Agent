import { isHealthResponse, type HealthResponse } from './types.ts'

/** Base URL for the backend API. `/api` is proxied to FastAPI by the Vite dev server. */
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const init: RequestInit = { headers: { Accept: 'application/json' } }
  if (signal) init.signal = signal
  const response = await fetch(`${API_BASE_URL}/health`, init)
  if (!response.ok) {
    throw new ApiError(`Backend responded with HTTP ${response.status}`, response.status)
  }
  const payload: unknown = await response.json()
  if (!isHealthResponse(payload)) {
    throw new ApiError('Backend returned an unexpected /health payload')
  }
  return payload
}
