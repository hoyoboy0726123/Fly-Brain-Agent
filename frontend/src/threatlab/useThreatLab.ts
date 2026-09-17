import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { ApiError, fetchThreatLabConfig, runThreatLab, toApiError, withTimeout } from '../api/client.ts'
import type { ThreatLabConfig, ThreatLabRangeLimit, ThreatLabRunRequest, ThreatLabRunResult, ThreatLabStep } from '../api/types.ts'
import { DEFAULT_PACE_MS, RUN_TIMEOUT_MS } from '../content.ts'

/**
 * Virtual Threat Lab state (P7.1).
 *
 * The hook only (1) asks the backend for one closed-loop experiment and (2) keeps a replay
 * cursor into the returned timeline. Nothing here simulates, decodes or moves anything:
 * every panel reads `current` (= `result.timeline[step]`) and renders the recorded state.
 */
export type LabPhase = 'idle' | 'running' | 'ready' | 'error'

export interface LabParams {
  startDistance: number
  approachSpeed: number
  azimuthDeg: number
  maxSteps: number
  seed: number
}

export const DEFAULT_PARAMS: LabParams = { startDistance: 20, approachSpeed: 10, azimuthDeg: 0, maxSteps: 30, seed: 0 }

/** Fallback limits (the backend's `run_request_limits` win when the config is loaded). */
export const FALLBACK_LIMITS: Record<string, ThreatLabRangeLimit> = {
  'world.start_distance': { min: 1, max: 100, default: 20 },
  'world.approach_speed': { min: 0, max: 50, default: 10 },
  'world.azimuth_deg': { min: -180, max: 180, default: 0 },
  max_steps: { min: 1, max: 200, default: 30 },
  seed: { min: 0 },
}

export interface LabState {
  config: ThreatLabConfig | null
  configError: ApiError | null
  phase: LabPhase
  result: ThreatLabRunResult | null
  error: ApiError | null
  params: LabParams
  /** replay cursor: index into `result.timeline` (0-based, = `step_index`) */
  step: number
  playing: boolean
}

export interface LabOptions {
  paceMs?: number
}

export interface ThreatLab {
  state: LabState
  current: ThreatLabStep | null
  steps: number
  limits: Record<string, ThreatLabRangeLimit>
  paramsValid: boolean
  paceMs: number
  run: () => void
  play: () => void
  pause: () => void
  stepForward: () => void
  stepBack: () => void
  seek: (step: number) => void
  reset: () => void
  setParams: (patch: Partial<LabParams>) => void
  reloadConfig: () => void
}

function limitsOf(config: ThreatLabConfig | null): Record<string, ThreatLabRangeLimit> {
  const limits: Record<string, ThreatLabRangeLimit> = { ...FALLBACK_LIMITS }
  if (!config) return limits
  for (const [key, value] of Object.entries(config.run_request_limits)) {
    if (typeof value === 'object' && value !== null) limits[key] = value
  }
  return limits
}

function within(value: number, limit: ThreatLabRangeLimit | undefined): boolean {
  if (!Number.isFinite(value)) return false
  if (limit?.min !== undefined && value < limit.min) return false
  if (limit?.max !== undefined && value > limit.max) return false
  return true
}

export function validateParams(params: LabParams, limits: Record<string, ThreatLabRangeLimit>): boolean {
  return (
    within(params.startDistance, limits['world.start_distance']) &&
    within(params.approachSpeed, limits['world.approach_speed']) &&
    within(params.azimuthDeg, limits['world.azimuth_deg']) &&
    within(params.maxSteps, limits['max_steps']) &&
    Number.isInteger(params.maxSteps) &&
    within(params.seed, limits['seed']) &&
    Number.isInteger(params.seed)
  )
}

export function toRequest(params: LabParams): ThreatLabRunRequest {
  return {
    experiment: 'virtual_threat_lab_v1',
    seed: params.seed,
    max_steps: params.maxSteps,
    world: { start_distance: params.startDistance, approach_speed: params.approachSpeed, azimuth_deg: params.azimuthDeg },
  }
}

export function useThreatLab(options: LabOptions = {}): ThreatLab {
  const paceMs = options.paceMs ?? DEFAULT_PACE_MS
  const [config, setConfig] = useState<ThreatLabConfig | null>(null)
  const [configError, setConfigError] = useState<ApiError | null>(null)
  const [configNonce, setConfigNonce] = useState(0)
  const [phase, setPhase] = useState<LabPhase>('idle')
  const [result, setResult] = useState<ThreatLabRunResult | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [params, setParamsState] = useState<LabParams>(DEFAULT_PARAMS)
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setConfigError(null)
    fetchThreatLabConfig(controller.signal)
      .then((loaded) => {
        setConfig(loaded)
      })
      .catch((cause: unknown) => {
        const apiError = toApiError(cause)
        if (apiError.code !== 'aborted') setConfigError(apiError)
      })
    return () => controller.abort()
  }, [configNonce])

  useEffect(() => () => abortRef.current?.abort(), [])

  const steps = result?.timeline.length ?? 0

  // Replay clock: advances the cursor through the recorded timeline; stops at the last step.
  useEffect(() => {
    if (!playing || steps === 0) return
    const timer = window.setInterval(() => {
      setStep((current) => {
        if (current + 1 >= steps) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, Math.max(0, paceMs))
    return () => window.clearInterval(timer)
  }, [playing, steps, paceMs])

  const limits = useMemo(() => limitsOf(config), [config])
  const paramsValid = validateParams(params, limits)

  const run = useCallback(() => {
    if (!paramsValid) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const timeout = withTimeout(RUN_TIMEOUT_MS, controller.signal)
    setPhase('running')
    setPlaying(false)
    setError(null)
    setResult(null)
    setStep(0)
    runThreatLab(toRequest(params), timeout.signal)
      .then((loaded) => {
        if (controller.signal.aborted) return
        setResult(loaded)
        setStep(0)
        setPhase('ready')
        setPlaying(loaded.timeline.length > 1)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted && !(cause instanceof Error && cause.name === 'TimeoutError')) return
        const apiError = toApiError(cause)
        if (apiError.code === 'aborted') return
        setResult(null)
        setError(apiError)
        setPhase('error')
      })
      .finally(() => timeout.clear())
  }, [params, paramsValid])

  const clamp = useCallback((value: number) => Math.min(Math.max(0, Math.trunc(value)), Math.max(0, steps - 1)), [steps])

  const play = useCallback(() => {
    if (steps === 0) return
    setStep((current) => (current + 1 >= steps ? 0 : current))
    setPlaying(true)
  }, [steps])
  const pause = useCallback(() => setPlaying(false), [])
  const stepForward = useCallback(() => {
    setPlaying(false)
    setStep((current) => clamp(current + 1))
  }, [clamp])
  const stepBack = useCallback(() => {
    setPlaying(false)
    setStep((current) => clamp(current - 1))
  }, [clamp])
  const seek = useCallback(
    (target: number) => {
      setPlaying(false)
      setStep(clamp(target))
    },
    [clamp],
  )
  const reset = useCallback(() => {
    setPlaying(false)
    setStep(0)
  }, [])
  const setParams = useCallback((patch: Partial<LabParams>) => setParamsState((current) => ({ ...current, ...patch })), [])
  const reloadConfig = useCallback(() => setConfigNonce((n) => n + 1), [])

  const current = result?.timeline[step] ?? null

  return {
    state: { config, configError, phase, result, error, params, step, playing },
    current,
    steps,
    limits,
    paramsValid,
    paceMs,
    run,
    play,
    pause,
    stepForward,
    stepBack,
    seek,
    reset,
    setParams,
    reloadConfig,
  }
}
