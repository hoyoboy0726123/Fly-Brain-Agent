import {
  isApiErrorDetail,
  isEscapeConfig,
  isEscapeRunResult,
  isHealthResponse,
  type EscapeConfig,
  type EscapeRunRequest,
  type EscapeRunResult,
  type HealthResponse,
} from './types.ts'

/** Base URL for the backend API. `/api` is proxied to FastAPI by the Vite dev server. */
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/+$/, '')

/** Error codes shared with the backend (`app.api.escape`), plus client-side ones. */
export type ErrorCode =
  | 'invalid_request'
  | 'config_unavailable'
  | 'circuit_unavailable'
  | 'circuit_mismatch'
  | 'simulation_error'
  | 'timeout'
  | 'backend_unavailable'
  | 'unexpected_response'
  | 'aborted'
  | string

export class ApiError extends Error {
  readonly status: number | undefined
  readonly code: ErrorCode

  constructor(message: string, options: { status?: number; code?: ErrorCode } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.code = options.code ?? (options.status === undefined ? 'backend_unavailable' : 'http_error')
  }
}

/** Human-readable title for an error code (the UI shows code + message). */
export function describeErrorCode(code: ErrorCode): string {
  switch (code) {
    case 'backend_unavailable':
      return 'Backend unavailable'
    case 'invalid_request':
      return 'Invalid request'
    case 'config_unavailable':
      return 'Behaviour configuration unavailable'
    case 'circuit_unavailable':
      return 'Circuit artifact unavailable'
    case 'circuit_mismatch':
      return 'Circuit mismatch (hash / id differs from the configured expectation)'
    case 'simulation_error':
      return 'Simulation error'
    case 'timeout':
      return 'Timeout'
    case 'unexpected_response':
      return 'Unexpected backend response'
    case 'aborted':
      return 'Cancelled'
    default:
      return 'Request failed'
  }
}

/** Convert any thrown value into an ApiError (network failures become backend_unavailable). */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (error instanceof DOMException && error.name === 'AbortError') {
    return new ApiError('Request cancelled', { code: 'aborted' })
  }
  if (error instanceof Error && error.name === 'TimeoutError') {
    return new ApiError('The backend did not answer in time', { code: 'timeout' })
  }
  const message = error instanceof Error ? error.message : 'Unknown error'
  return new ApiError(`Could not reach the backend: ${message}`, { code: 'backend_unavailable' })
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  let payload: unknown = null
  try {
    payload = await response.json()
  } catch {
    // non-JSON error body; fall through to the generic message
  }
  const detail = typeof payload === 'object' && payload !== null ? (payload as Record<string, unknown>)['detail'] : undefined
  if (isApiErrorDetail(detail)) {
    return new ApiError(detail.message, { status: response.status, code: detail.error })
  }
  if (response.status === 422) {
    const first = Array.isArray(detail) ? (detail[0] as Record<string, unknown> | undefined) : undefined
    const msg = first && typeof first['msg'] === 'string' ? first['msg'] : 'request validation failed'
    const loc = first && Array.isArray(first['loc']) ? first['loc'].slice(1).join('.') : ''
    return new ApiError(loc ? `${loc}: ${msg}` : msg, { status: 422, code: 'invalid_request' })
  }
  if (response.status >= 502 && response.status <= 504) {
    return new ApiError(`Backend responded with HTTP ${response.status}`, {
      status: response.status,
      code: response.status === 504 ? 'timeout' : 'backend_unavailable',
    })
  }
  return new ApiError(`Backend responded with HTTP ${response.status}`, { status: response.status })
}

async function requestJson(path: string, init: RequestInit): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init.headers ?? {}) },
    })
  } catch (error) {
    throw toApiError(error)
  }
  if (!response.ok) throw await errorFromResponse(response)
  try {
    return await response.json()
  } catch {
    throw new ApiError('Backend returned a non-JSON payload', {
      status: response.status,
      code: 'unexpected_response',
    })
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const init: RequestInit = {}
  if (signal) init.signal = signal
  const payload = await requestJson('/health', init)
  if (!isHealthResponse(payload)) {
    throw new ApiError('Backend returned an unexpected /health payload', { code: 'unexpected_response' })
  }
  return payload
}

export async function fetchEscapeConfig(signal?: AbortSignal): Promise<EscapeConfig> {
  const init: RequestInit = {}
  if (signal) init.signal = signal
  const payload = await requestJson('/escape/config', init)
  if (!isEscapeConfig(payload)) {
    throw new ApiError('Backend returned an unexpected /escape/config payload', {
      code: 'unexpected_response',
    })
  }
  return payload
}

/** `POST /escape/run` — REST fallback when the WebSocket is not available. */
export async function runEscape(request: EscapeRunRequest, signal?: AbortSignal): Promise<EscapeRunResult> {
  const init: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  }
  if (signal) init.signal = signal
  const payload = await requestJson('/escape/run', init)
  if (!isEscapeRunResult(payload)) {
    throw new ApiError('Backend returned an unexpected /escape/run payload', {
      code: 'unexpected_response',
    })
  }
  return payload
}

/** An AbortSignal that fires on `signal` or after `timeoutMs`, whichever comes first. */
export function withTimeout(timeoutMs: number, signal?: AbortSignal): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController()
  const timer = window.setTimeout(
    () => controller.abort(new DOMException('The backend did not answer in time', 'TimeoutError')),
    timeoutMs,
  )
  const forward = () => controller.abort(signal?.reason)
  signal?.addEventListener('abort', forward, { once: true })
  return {
    signal: controller.signal,
    clear: () => {
      window.clearTimeout(timer)
      signal?.removeEventListener('abort', forward)
    },
  }
}
