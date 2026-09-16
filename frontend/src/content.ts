/**
 * Fixed scientific wording (NEUROSCIENCE.md §3, PRD). The backend serves the same strings
 * (`GET /escape/config`); these copies keep the labels visible even when it is unreachable.
 */
export const APP_TITLE = 'FlyBrain Agent'
export const APP_SUBTITLE = 'Connectome-grounded simulation using MaleCNS v1.0'

export const SCIENTIFIC_LABELS: readonly string[] = [
  'Structural connectivity: biological data',
  'Neural activity: simulated',
  'Behavior decoding: computational interpretation',
]

export const DISCLAIMER =
  'STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED. ' +
  'STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS.'

export const SIMULATED_ACTIVITY_LABEL = 'SIMULATED ACTIVITY'

/** Replay pace (ms per simulation step) when `?pace=` is not given. */
export const DEFAULT_PACE_MS = 140

/** Client-side wall-clock budget for one experiment (WebSocket or REST). */
export const RUN_TIMEOUT_MS = 15_000
