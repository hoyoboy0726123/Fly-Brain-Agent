/** Typed mirrors of the backend API models (`app.models.health`, `app.api.escape`). */

export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
  environment: string
  phase: string
}

export function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return (
    record['status'] === 'ok' &&
    typeof record['service'] === 'string' &&
    typeof record['version'] === 'string' &&
    typeof record['environment'] === 'string' &&
    typeof record['phase'] === 'string'
  )
}

// ---------------------------------------------------------------------------- escape demo

export type Direction = 'left' | 'center' | 'right'
export const DIRECTIONS: readonly Direction[] = ['left', 'center', 'right']

/** The only actions the P4 decoder exposes (no left/right escape is decoded). */
export type ActionValue = 'NO_ACTION' | 'ESCAPE'
export const ACTION_VALUES: readonly ActionValue[] = ['NO_ACTION', 'ESCAPE']

/** Which giant fiber(s) fired — metadata only, never an action. */
export type GfActivity = 'None' | 'Left' | 'Right' | 'Both'

export type GroupRole = 'sensory' | 'output' | 'other'

export interface ActivityGroup {
  key: string
  cell_type: string
  side: string
  role: GroupRole
  neuron_count: number
  stimulable_count: number
}

export interface GroupEdge {
  pre_key: string
  post_key: string
  edge_count: number
  synapse_total: number
  dataset: string
  dataset_version: string
}

export interface GroupActivity {
  label: string
  groups: ActivityGroup[]
  /** group key -> per-step SIMULATED spike counts (index 0 = step 1) */
  fired_counts: Record<string, number[]>
}

export type TimelineTag =
  | 't0_stimulus'
  | 't1_sensory_activation'
  | 't2_intermediate_activity'
  | 't3_output_activation'
  | 't4_decoded_action'

export interface TimelineEvent {
  tag: TimelineTag
  step: number | null
  label: string
  description: string
  neuron_ids: string[]
  count: number
}

export interface LoomingStimulus {
  stimulus: 'looming'
  direction: Direction
  intensity: number
}

export interface EscapeRunRequest {
  stimulus: 'looming'
  direction: Direction
  intensity: number
  steps?: number
}

export interface LayerDescription {
  layer: string
  kind: 'BIOLOGICAL STRUCTURE' | 'COMPUTATIONAL DYNAMICS' | 'APPLICATION DECODING'
  modules: string[]
  description: string
}

export interface Citation {
  key: string
  authors: string
  year: number
  title: string
  venue: string
  doi: string | null
  url: string | null
  claim: string
  verification: string
  confidence: 'high' | 'medium' | 'low'
}

export interface SimulationConfigSummary {
  label: string
  dt: number
  threshold: number
  leak: number
  refractory_steps: number
  weight_transform: string
  weight_scale: number
  stimulus_gain: number
  noise_std: number
  random_seed: number
  sign_mode: string
  [key: string]: unknown
}

export interface EscapeConfig {
  disclaimer: string
  scientific_labels: string[]
  config_version: string
  circuit_id: string
  circuit_hash: string
  expected_circuit_hash: string | null
  circuit_verified: boolean
  biological_status: string
  research_document: string
  dataset: string
  dataset_version: string
  canonical_selection_rule: string
  circuit_neurons: number
  circuit_edges: number
  sensory_cell_types: string[]
  output_cell_types: string[]
  sensory_population_counts: Record<string, number>
  stimulated_sensory_counts: Record<string, number>
  excluded_sensory_counts: Record<string, number>
  exclusion_reason: string
  output_groups: Record<string, string[]>
  groups: ActivityGroup[]
  group_edges: GroupEdge[]
  actions: string[]
  decoder_rule: string
  mapping_rule: string
  mapping_label: string
  mapping_gain: number
  stimulus_duration_steps: number
  simulation_steps: number
  max_steps: number
  simulation_config: SimulationConfigSummary
  activity_label: string
  layers: LayerDescription[]
  mapping_confidence: Record<string, string>
  limitations: string[]
  citations: Citation[]
}

export interface CircuitReference {
  circuit_id: string
  circuit_hash: string
  dataset: string
  dataset_version: string
  canonical_selection_rule: string
  neurons: number
  edges: number
  biological_status: string
  research_document: string
}

export interface SensoryActivity {
  label: string
  stimulated_neuron_ids: string[]
  stimulated_count: number
  stimulated_sides: string[]
  injected_current: number
  duration_steps: number
  mapping_rule: string
  mapping_label: string
  first_fire_step: number | null
  fired_count_at_first_step: number
  fired_counts_per_step: number[]
}

export interface OutputActivity {
  neuron_id: string
  side: string
  spike_count: number
  fire_steps: number[]
  label: string
}

export interface MotorDecision {
  action: ActionValue
  rule: string
  output_spike_count: number
  first_output_fire_step: number | null
  fired_output_neuron_ids: string[]
  fired_output_sides: string[]
  label: string
}

export interface EscapeRunResult {
  experiment_id: string
  created_at: string
  disclaimer: string
  activity_label: string
  config_version: string
  stimulus: LoomingStimulus
  circuit_id: string
  circuit_hash: string
  circuit: CircuitReference
  biological_status: string
  steps: number
  stimulus_duration_steps: number
  timeline: TimelineEvent[]
  sensory_activity: SensoryActivity
  group_activity: GroupActivity
  per_step_fired_counts: number[]
  firing_events: number
  neurons_activated: number
  output_activity: OutputActivity[]
  gf_activity: GfActivity
  action: ActionValue
  decision: MotorDecision
  simulation_config: SimulationConfigSummary
  random_seed: number
  runtime_seconds: number
}

/** Shape of `detail` for backend error responses (`app.api.escape` error contract). */
export interface ApiErrorDetail {
  error: string
  message: string
}

// ---------------------------------------------------------------------------- WebSocket

export interface SocketEventBase {
  experiment_id: string
  activity_label: string
}

export interface StimulusStartedEvent extends SocketEventBase {
  event: 'stimulus_started'
  stimulus: LoomingStimulus
  steps: number
  stimulus_duration_steps: number
  stimulated_count: number
  stimulated_sides: string[]
  injected_current: number
  groups: ActivityGroup[]
  disclaimer: string
}

export interface NeuralActivityEvent extends SocketEventBase {
  event: 'neural_activity'
  step: number
  stimulus_active: boolean
  fired_total: number
  fired_by_group: Record<string, number>
}

export interface SensoryActivationEvent extends SocketEventBase {
  event: 'sensory_activation'
  step: number
  count: number
  sides: string[]
  description: string
}

export interface OutputActivationEvent extends SocketEventBase {
  event: 'output_activation'
  step: number
  neuron_ids: string[]
  sides: string[]
  description: string
}

export interface ActionDecodedEvent extends SocketEventBase {
  event: 'action_decoded'
  action: ActionValue
  gf_activity: GfActivity
  rule: string
  output_spike_count: number
  first_output_fire_step: number | null
  label: string
}

export interface ExperimentFinishedEvent extends SocketEventBase {
  event: 'experiment_finished'
  result: EscapeRunResult
}

export interface SocketErrorEvent {
  event: 'error'
  error: string
  message: string
}

export type EscapeSocketEvent =
  | StimulusStartedEvent
  | NeuralActivityEvent
  | SensoryActivationEvent
  | OutputActivationEvent
  | ActionDecodedEvent
  | ExperimentFinishedEvent
  | SocketErrorEvent

// ---------------------------------------------------------------------------- guards

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function isActionValue(value: unknown): value is ActionValue {
  return typeof value === 'string' && (ACTION_VALUES as readonly string[]).includes(value)
}

export function isEscapeConfig(value: unknown): value is EscapeConfig {
  if (!isRecord(value)) return false
  return (
    typeof value['disclaimer'] === 'string' &&
    typeof value['circuit_id'] === 'string' &&
    typeof value['circuit_hash'] === 'string' &&
    typeof value['biological_status'] === 'string' &&
    Array.isArray(value['groups']) &&
    Array.isArray(value['group_edges']) &&
    Array.isArray(value['layers']) &&
    typeof value['simulation_steps'] === 'number' &&
    typeof value['stimulus_duration_steps'] === 'number'
  )
}

export function isEscapeRunResult(value: unknown): value is EscapeRunResult {
  if (!isRecord(value)) return false
  const group = value['group_activity']
  return (
    typeof value['experiment_id'] === 'string' &&
    typeof value['disclaimer'] === 'string' &&
    typeof value['circuit_id'] === 'string' &&
    typeof value['circuit_hash'] === 'string' &&
    typeof value['steps'] === 'number' &&
    typeof value['stimulus_duration_steps'] === 'number' &&
    Array.isArray(value['timeline']) &&
    Array.isArray(value['output_activity']) &&
    Array.isArray(value['per_step_fired_counts']) &&
    isRecord(value['sensory_activity']) &&
    isRecord(value['decision']) &&
    isRecord(group) &&
    Array.isArray(group['groups']) &&
    isRecord(group['fired_counts']) &&
    isActionValue(value['action']) &&
    typeof value['gf_activity'] === 'string'
  )
}

export function isEscapeSocketEvent(value: unknown): value is EscapeSocketEvent {
  if (!isRecord(value)) return false
  const kind = value['event']
  switch (kind) {
    case 'stimulus_started':
      return typeof value['steps'] === 'number' && Array.isArray(value['groups'])
    case 'neural_activity':
      return typeof value['step'] === 'number' && isRecord(value['fired_by_group'])
    case 'sensory_activation':
    case 'output_activation':
      return typeof value['step'] === 'number'
    case 'action_decoded':
      return isActionValue(value['action']) && typeof value['gf_activity'] === 'string'
    case 'experiment_finished':
      return isEscapeRunResult(value['result'])
    case 'error':
      return typeof value['error'] === 'string' && typeof value['message'] === 'string'
    default:
      return false
  }
}

export function isApiErrorDetail(value: unknown): value is ApiErrorDetail {
  return isRecord(value) && typeof value['error'] === 'string' && typeof value['message'] === 'string'
}
