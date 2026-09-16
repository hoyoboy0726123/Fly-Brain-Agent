import { API_BASE_URL, ApiError } from './client.ts'
import { isEscapeSocketEvent, type EscapeRunRequest, type EscapeRunResult, type EscapeSocketEvent } from './types.ts'

/** `ws(s)://…/ws/escape` next to the REST base (proxied by Vite in development). */
export function escapeSocketUrl(): string {
  if (/^https?:\/\//.test(API_BASE_URL)) {
    return API_BASE_URL.replace(/^http/, 'ws') + '/ws/escape'
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${API_BASE_URL}/ws/escape`
}

export interface SocketRunOptions {
  timeoutMs: number
  signal?: AbortSignal
  onEvent?: (event: EscapeSocketEvent) => void
}

/**
 * Run one experiment over `WS /ws/escape`: send the request, forward every streamed event
 * to `onEvent`, resolve with the final result. Rejects with an ApiError whose `code` follows
 * the backend contract (`backend_unavailable` when the socket cannot be opened).
 */
export function runEscapeOverSocket(request: EscapeRunRequest, options: SocketRunOptions): Promise<EscapeRunResult> {
  return new Promise<EscapeRunResult>((resolve, reject) => {
    let socket: WebSocket
    try {
      socket = new WebSocket(escapeSocketUrl())
    } catch (error) {
      reject(new ApiError(`WebSocket could not be created: ${String(error)}`, { code: 'backend_unavailable' }))
      return
    }
    let settled = false
    let opened = false
    let received = false

    const finish = (fn: () => void) => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      options.signal?.removeEventListener('abort', onAbort)
      fn()
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000, 'done')
      }
    }
    const fail = (error: ApiError) => finish(() => reject(error))
    const onAbort = () => fail(new ApiError('Run cancelled', { code: 'aborted' }))
    const timer = window.setTimeout(
      () => fail(new ApiError(`No answer from the backend within ${options.timeoutMs} ms`, { code: 'timeout' })),
      options.timeoutMs,
    )
    options.signal?.addEventListener('abort', onAbort, { once: true })

    socket.addEventListener('open', () => {
      opened = true
      socket.send(JSON.stringify(request))
    })
    socket.addEventListener('message', (message: MessageEvent<unknown>) => {
      let payload: unknown
      try {
        payload = JSON.parse(String(message.data))
      } catch {
        fail(new ApiError('Backend sent a non-JSON WebSocket message', { code: 'unexpected_response' }))
        return
      }
      if (!isEscapeSocketEvent(payload)) {
        fail(new ApiError('Backend sent an unexpected WebSocket event', { code: 'unexpected_response' }))
        return
      }
      received = true
      if (payload.event === 'error') {
        fail(new ApiError(payload.message, { code: payload.error }))
        return
      }
      options.onEvent?.(payload)
      if (payload.event === 'experiment_finished') {
        finish(() => resolve(payload.result))
      }
    })
    socket.addEventListener('error', () => {
      if (!opened) fail(new ApiError('WebSocket connection failed', { code: 'backend_unavailable' }))
    })
    socket.addEventListener('close', (event) => {
      if (settled) return
      // Closed without ever answering: the socket endpoint is unavailable (the caller may
      // fall back to REST). Closed mid-stream: the run is incomplete and must not be shown.
      const code = opened && received ? 'unexpected_response' : 'backend_unavailable'
      fail(new ApiError(`WebSocket closed before the experiment finished (code ${event.code})`, { code }))
    })
  })
}
