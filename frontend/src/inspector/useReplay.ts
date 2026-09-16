import { useCallback, useEffect, useMemo, useState } from 'react'

import type { NeuronActivity } from '../api/types.ts'

export type SimState = 'inactive' | 'active' | 'fired' | 'refractory'

export interface NeuronSimState {
  state: SimState
  membranePotential: number
  fired: boolean
  refractoryRemaining: number
}

export interface Replay {
  /** 0 = initial state (before step 1); N = after the last step */
  step: number
  steps: number
  playing: boolean
  play: () => void
  pause: () => void
  stepForward: () => void
  stepBack: () => void
  reset: () => void
  seek: (step: number) => void
  firedIds: Set<string>
  stateOf: (neuronId: string) => NeuronSimState | null
  firedCount: number
}

/** Steps through the per-neuron SIMULATED state history of one backend run. */
export function useReplay(activity: NeuronActivity | null, paceMs: number): Replay {
  const steps = activity ? activity.fired_ids_per_step.length : 0
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    setStep(0)
    setPlaying(false)
  }, [activity])

  useEffect(() => {
    if (!playing) return
    const interval = window.setInterval(() => {
      setStep((current) => {
        if (current >= steps) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, Math.max(paceMs, 1))
    return () => window.clearInterval(interval)
  }, [playing, steps, paceMs])

  const indexOf = useMemo(() => new Map((activity?.neuron_ids ?? []).map((id, i) => [id, i])), [activity])
  const firedIds = useMemo(
    () => new Set(step > 0 && activity ? (activity.fired_ids_per_step[step - 1] ?? []) : []),
    [activity, step],
  )

  const stateOf = useCallback(
    (neuronId: string): NeuronSimState | null => {
      if (!activity) return null
      const index = indexOf.get(neuronId)
      if (index === undefined) return null
      if (step === 0) {
        return { state: 'inactive', membranePotential: activity.resting_potential, fired: false, refractoryRemaining: 0 }
      }
      const potential = activity.membrane_potential_per_step[step - 1]?.[index] ?? activity.resting_potential
      const refractory = activity.refractory_per_step[step - 1]?.[index] ?? 0
      const fired = firedIds.has(neuronId)
      const state: SimState = fired
        ? 'fired'
        : refractory > 0
          ? 'refractory'
          : Math.abs(potential - activity.resting_potential) > 1e-9
            ? 'active'
            : 'inactive'
      return { state, membranePotential: potential, fired, refractoryRemaining: refractory }
    },
    [activity, indexOf, step, firedIds],
  )

  const play = useCallback(() => {
    if (steps === 0) return
    setStep((current) => (current >= steps ? 0 : current))
    setPlaying(true)
  }, [steps])
  const pause = useCallback(() => setPlaying(false), [])
  const stepForward = useCallback(() => {
    setPlaying(false)
    setStep((current) => Math.min(current + 1, steps))
  }, [steps])
  const stepBack = useCallback(() => {
    setPlaying(false)
    setStep((current) => Math.max(current - 1, 0))
  }, [])
  const reset = useCallback(() => {
    setPlaying(false)
    setStep(0)
  }, [])
  const seek = useCallback(
    (target: number) => {
      setPlaying(false)
      setStep(Math.min(Math.max(Math.round(target), 0), steps))
    },
    [steps],
  )

  return { step, steps, playing, play, pause, stepForward, stepBack, reset, seek, firedIds, stateOf, firedCount: firedIds.size }
}
