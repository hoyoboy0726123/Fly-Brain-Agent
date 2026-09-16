import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'

import { fetchEscapeConfig, runEscape, toApiError, withTimeout } from '../api/client.ts'
import { runEscapeOverSocket } from '../api/escapeSocket.ts'
import type {
  ActionValue,
  Direction,
  EscapeConfig,
  EscapeRunRequest,
  EscapeRunResult,
  GfActivity,
  TimelineEvent,
} from '../api/types.ts'
import { DEFAULT_PACE_MS, RUN_TIMEOUT_MS } from '../content.ts'

export type DemoPhase = 'idle' | 'requesting' | 'replaying' | 'finished' | 'error'
export type Transport = 'websocket' | 'rest'

export interface DemoError {
  code: string
  message: string
}

export interface DemoState {
  phase: DemoPhase
  direction: Direction
  intensity: number
  config: EscapeConfig | null
  configError: DemoError | null
  result: EscapeRunResult | null
  /** number of simulation steps replayed so far (0 = nothing shown yet) */
  step: number
  transport: Transport | null
  streamedEvents: number
  error: DemoError | null
  runId: number
}

type DemoAction =
  | { type: 'config_loaded'; config: EscapeConfig }
  | { type: 'config_failed'; error: DemoError }
  | { type: 'set_direction'; direction: Direction }
  | { type: 'set_intensity'; intensity: number }
  | { type: 'run_started'; runId: number }
  | { type: 'socket_event'; runId: number }
  | { type: 'run_succeeded'; runId: number; result: EscapeRunResult; transport: Transport }
  | { type: 'run_failed'; runId: number; error: DemoError }
  | { type: 'advance' }
  | { type: 'reset' }

const initialState: DemoState = {
  phase: 'idle',
  direction: 'center',
  intensity: 0.5,
  config: null,
  configError: null,
  result: null,
  step: 0,
  transport: null,
  streamedEvents: 0,
  error: null,
  runId: 0,
}

function reducer(state: DemoState, action: DemoAction): DemoState {
  switch (action.type) {
    case 'config_loaded':
      return { ...state, config: action.config, configError: null }
    case 'config_failed':
      return { ...state, configError: action.error }
    case 'set_direction':
      return { ...state, direction: action.direction }
    case 'set_intensity':
      return { ...state, intensity: action.intensity }
    case 'run_started':
      return {
        ...state,
        phase: 'requesting',
        result: null,
        step: 0,
        transport: null,
        streamedEvents: 0,
        error: null,
        runId: action.runId,
      }
    case 'socket_event':
      if (action.runId !== state.runId) return state
      return { ...state, streamedEvents: state.streamedEvents + 1 }
    case 'run_succeeded':
      if (action.runId !== state.runId) return state
      return { ...state, phase: 'replaying', result: action.result, step: 0, transport: action.transport }
    case 'run_failed':
      if (action.runId !== state.runId) return state
      return { ...state, phase: 'error', result: null, step: 0, error: action.error }
    case 'advance': {
      if (state.phase !== 'replaying' || !state.result) return state
      const step = Math.min(state.step + 1, state.result.steps)
      return { ...state, step, phase: step >= state.result.steps ? 'finished' : 'replaying' }
    }
    case 'reset':
      return {
        ...state,
        phase: 'idle',
        result: null,
        step: 0,
        transport: null,
        streamedEvents: 0,
        error: null,
        runId: state.runId + 1,
      }
  }
}

/** Everything the panels render for the current replay step, derived from the backend result. */
export interface DemoView {
  step: number
  steps: number
  stimulusDuration: number
  stimulusActive: boolean
  /** 0..1 fraction of the stimulus window elapsed (stays 1 after it ends) */
  stimulusProgress: number
  firedByGroup: Record<string, number>
  firedTotal: number
  sensoryFired: boolean
  outputFired: boolean
  outputSidesFired: string[]
  reachedEvents: TimelineEvent[]
  /** decoded action, only once the whole backend timeline has been replayed */
  action: ActionValue | null
  gfActivity: GfActivity | null
  escaped: boolean
}

const EMPTY_VIEW: DemoView = {
  step: 0,
  steps: 0,
  stimulusDuration: 0,
  stimulusActive: false,
  stimulusProgress: 0,
  firedByGroup: {},
  firedTotal: 0,
  sensoryFired: false,
  outputFired: false,
  outputSidesFired: [],
  reachedEvents: [],
  action: null,
  gfActivity: null,
  escaped: false,
}

export function deriveView(state: DemoState): DemoView {
  const { result, step, phase } = state
  if (!result || (phase !== 'replaying' && phase !== 'finished')) return EMPTY_VIEW
  const duration = result.stimulus_duration_steps
  const firedByGroup: Record<string, number> = {}
  for (const [key, counts] of Object.entries(result.group_activity.fired_counts)) {
    firedByGroup[key] = step > 0 ? (counts[step - 1] ?? 0) : 0
  }
  const sensoryStep = result.sensory_activity.first_fire_step
  const outputStep = result.decision.first_output_fire_step
  const finished = phase === 'finished'
  return {
    step,
    steps: result.steps,
    stimulusDuration: duration,
    stimulusActive: step >= 1 && step <= duration,
    stimulusProgress: duration > 0 ? Math.min(step, duration) / duration : 0,
    firedByGroup,
    firedTotal: step > 0 ? (result.per_step_fired_counts[step - 1] ?? 0) : 0,
    sensoryFired: sensoryStep !== null && step >= sensoryStep,
    outputFired: outputStep !== null && step >= outputStep,
    outputSidesFired: result.output_activity
      .filter((o) => o.fire_steps.some((s) => s <= step))
      .map((o) => o.side)
      .sort(),
    reachedEvents: result.timeline.filter(
      (e) => e.tag === 't0_stimulus' || (e.step !== null && e.step <= step && e.tag !== 't4_decoded_action'),
    ),
    action: finished ? result.action : null,
    gfActivity: finished ? result.gf_activity : null,
    escaped: finished && result.action === 'ESCAPE',
  }
}

export interface DemoOptions {
  /** ms per replayed simulation step (0 = as fast as the browser allows) */
  paceMs?: number
  timeoutMs?: number
  /** 'auto' = WebSocket first, REST fallback when the socket cannot be opened */
  transport?: 'auto' | 'rest'
}

export interface EscapeDemo {
  state: DemoState
  view: DemoView
  intensityValid: boolean
  setDirection: (direction: Direction) => void
  setIntensity: (intensity: number) => void
  trigger: () => void
  reset: () => void
  reloadConfig: () => void
}

export function useEscapeDemo(options: DemoOptions = {}): EscapeDemo {
  const paceMs = options.paceMs ?? DEFAULT_PACE_MS
  const timeoutMs = options.timeoutMs ?? RUN_TIMEOUT_MS
  const transportMode = options.transport ?? 'auto'
  const [state, dispatch] = useReducer(reducer, initialState)
  const [configAttempt, setConfigAttempt] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const runIdRef = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchEscapeConfig(controller.signal)
      .then((config) => dispatch({ type: 'config_loaded', config }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const apiError = toApiError(error)
        dispatch({ type: 'config_failed', error: { code: apiError.code, message: apiError.message } })
      })
    return () => controller.abort()
  }, [configAttempt])

  useEffect(() => {
    if (state.phase !== 'replaying') return
    const interval = window.setInterval(() => dispatch({ type: 'advance' }), Math.max(paceMs, 1))
    return () => window.clearInterval(interval)
  }, [state.phase, state.runId, paceMs])

  useEffect(() => () => abortRef.current?.abort(), [])

  const intensityValid = Number.isFinite(state.intensity) && state.intensity >= 0 && state.intensity <= 1

  const trigger = useCallback(() => {
    if (state.phase === 'requesting' || !intensityValid) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const runId = ++runIdRef.current
    dispatch({ type: 'run_started', runId })
    const request: EscapeRunRequest = {
      stimulus: 'looming',
      direction: state.direction,
      intensity: state.intensity,
    }

    const execute = async (): Promise<void> => {
      let transport: Transport = 'websocket'
      let result: EscapeRunResult
      if (transportMode === 'rest') {
        transport = 'rest'
        const guard = withTimeout(timeoutMs, controller.signal)
        try {
          result = await runEscape(request, guard.signal)
        } finally {
          guard.clear()
        }
      } else {
        try {
          result = await runEscapeOverSocket(request, {
            timeoutMs,
            signal: controller.signal,
            onEvent: () => dispatch({ type: 'socket_event', runId }),
          })
        } catch (error) {
          const apiError = toApiError(error)
          // Only a socket that could not be opened falls back to REST; an error the
          // backend reported (validation, circuit, simulation, timeout) is final.
          if (apiError.code !== 'backend_unavailable') throw apiError
          transport = 'rest'
          const guard = withTimeout(timeoutMs, controller.signal)
          try {
            result = await runEscape(request, guard.signal)
          } finally {
            guard.clear()
          }
        }
      }
      if (controller.signal.aborted) return
      dispatch({ type: 'run_succeeded', runId, result, transport })
    }

    execute().catch((error: unknown) => {
      if (controller.signal.aborted) return
      const apiError = toApiError(error)
      dispatch({ type: 'run_failed', runId, error: { code: apiError.code, message: apiError.message } })
    })
  }, [state.phase, state.direction, state.intensity, intensityValid, timeoutMs, transportMode])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    runIdRef.current += 1
    dispatch({ type: 'reset' })
  }, [])

  const setDirection = useCallback((direction: Direction) => dispatch({ type: 'set_direction', direction }), [])
  const setIntensity = useCallback((intensity: number) => dispatch({ type: 'set_intensity', intensity }), [])
  const reloadConfig = useCallback(() => setConfigAttempt((n) => n + 1), [])

  const view = useMemo(() => deriveView(state), [state])

  return { state, view, intensityValid, setDirection, setIntensity, trigger, reset, reloadConfig }
}
