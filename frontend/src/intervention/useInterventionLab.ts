import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { ApiError, compareIntervention, fetchInterventionLabConfig, toApiError, withTimeout } from '../api/client.ts'
import type { InterventionCompareRequest, InterventionCompareResult, InterventionLabConfig, InterventionSelector, ThreatLabStep } from '../api/types.ts'
import { DEFAULT_PACE_MS, RUN_TIMEOUT_MS } from '../content.ts'
import { DEFAULT_PARAMS, FALLBACK_LIMITS, validateParams, type LabParams } from '../threatlab/useThreatLab.ts'

/**
 * Neural Intervention Lab state (P7.2). One backend call returns two recorded trials
 * (CONTROL and one COMPUTATIONAL FIRING SUPPRESSION) under matched conditions; one replay
 * cursor indexes both timelines. Nothing is simulated, suppressed or decoded here.
 */
export type InterventionPhase = 'idle' | 'running' | 'ready' | 'error'

export interface InterventionState {
  config: InterventionLabConfig | null
  configError: ApiError | null
  phase: InterventionPhase
  result: InterventionCompareResult | null
  error: ApiError | null
  selector: InterventionSelector
  params: LabParams
  step: number
  playing: boolean
}

export interface TrialCursor {
  /** step of this trial at the shared cursor, or null when the trial has ended */
  step: ThreatLabStep | null
  ended: boolean
  steps: number
}

export interface InterventionLab {
  state: InterventionState
  control: TrialCursor
  intervention: TrialCursor
  /** cell types suppressed in the intervention trial (from the backend's resolved targets) */
  suppressedCellTypes: string[]
  cursorMax: number
  paramsValid: boolean
  paceMs: number
  run: () => void
  play: () => void
  pause: () => void
  stepForward: () => void
  stepBack: () => void
  seek: (step: number) => void
  reset: () => void
  setSelector: (selector: InterventionSelector) => void
  setParams: (patch: Partial<LabParams>) => void
  reloadConfig: () => void
}

export function toCompareRequest(selector: InterventionSelector, params: LabParams): InterventionCompareRequest {
  return {
    intervention: selector,
    seed: params.seed,
    max_steps: params.maxSteps,
    world: { start_distance: params.startDistance, approach_speed: params.approachSpeed, azimuth_deg: params.azimuthDeg },
  }
}

function cursorOf(timeline: ThreatLabStep[] | undefined, step: number): TrialCursor {
  const steps = timeline?.length ?? 0
  const current = timeline?.[step] ?? null
  return { step: current, ended: steps > 0 && step >= steps, steps }
}

export function useInterventionLab(options: { paceMs?: number } = {}): InterventionLab {
  const paceMs = options.paceMs ?? DEFAULT_PACE_MS
  const [config, setConfig] = useState<InterventionLabConfig | null>(null)
  const [configError, setConfigError] = useState<ApiError | null>(null)
  const [configNonce, setConfigNonce] = useState(0)
  const [phase, setPhase] = useState<InterventionPhase>('idle')
  const [result, setResult] = useState<InterventionCompareResult | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [selector, setSelector] = useState<InterventionSelector>('SILENCE_LPLC2')
  const [params, setParamsState] = useState<LabParams>(DEFAULT_PARAMS)
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setConfigError(null)
    fetchInterventionLabConfig(controller.signal)
      .then(setConfig)
      .catch((cause: unknown) => {
        const apiError = toApiError(cause)
        if (apiError.code !== 'aborted') setConfigError(apiError)
      })
    return () => controller.abort()
  }, [configNonce])

  useEffect(() => () => abortRef.current?.abort(), [])

  const cursorMax = result ? result.comparison.synchronization.cursor_max : -1
  const total = cursorMax + 1

  useEffect(() => {
    if (!playing || total === 0) return
    const timer = window.setInterval(() => {
      setStep((current) => {
        if (current + 1 >= total) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, Math.max(0, paceMs))
    return () => window.clearInterval(timer)
  }, [playing, total, paceMs])

  const paramsValid = validateParams(params, FALLBACK_LIMITS)

  const run = useCallback(() => {
    if (!paramsValid) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const timeout = withTimeout(RUN_TIMEOUT_MS * 2, controller.signal)
    setPhase('running')
    setPlaying(false)
    setError(null)
    setResult(null)
    setStep(0)
    compareIntervention(toCompareRequest(selector, params), timeout.signal)
      .then((loaded) => {
        if (controller.signal.aborted) return
        setResult(loaded)
        setStep(0)
        setPhase('ready')
        setPlaying(loaded.comparison.synchronization.cursor_max > 0)
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
  }, [params, paramsValid, selector])

  const clamp = useCallback((value: number) => Math.min(Math.max(0, Math.trunc(value)), Math.max(0, total - 1)), [total])
  const play = useCallback(() => {
    if (total === 0) return
    setStep((current) => (current + 1 >= total ? 0 : current))
    setPlaying(true)
  }, [total])
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

  const control = useMemo(() => cursorOf(result?.control.experiment.timeline, step), [result, step])
  const intervention = useMemo(() => cursorOf(result?.intervention.experiment.timeline, step), [result, step])
  const suppressedCellTypes = useMemo(() => result?.intervention.resolved_targets.cell_types ?? [], [result])

  return {
    state: { config, configError, phase, result, error, selector, params, step, playing },
    control,
    intervention,
    suppressedCellTypes,
    cursorMax,
    paramsValid,
    paceMs,
    run,
    play,
    pause,
    stepForward,
    stepBack,
    seek,
    reset,
    setSelector,
    setParams,
    reloadConfig,
  }
}
