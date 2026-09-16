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

/** Per-neuron, per-step SIMULATED state (index 0 = step 1); never a measured recording. */
export interface NeuronActivity {
  label: string
  neuron_ids: string[]
  fired_ids_per_step: string[][]
  membrane_potential_per_step: number[][]
  refractory_per_step: number[][]
  resting_potential: number
  reset_potential: number
  threshold: number
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
  neuron_activity: NeuronActivity | null
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

// ---------------------------------------------------------------------------- circuit inspector (P6)

export interface CircuitNodeRecord {
  neuron_id: string
  cell_type: string | null
  cell_class: string | null
  neurotransmitter_prediction: string | null
  dataset: string
  dataset_version: string
  minimum_hop_from_seed: number
  is_seed: boolean
  is_target: boolean
  side: string | null
  role: string | null
  in_degree: number
  out_degree: number
  in_synapses: number
  out_synapses: number
}

export interface CircuitNodesPage {
  circuit_id: string
  circuit_hash: string
  label: string
  total: number
  offset: number
  limit: number
  items: CircuitNodeRecord[]
}

export interface SimulationWeightInfo {
  label: string
  value: number
  weight_transform: string
  weight_scale: number
  parameter_label: string
}

export interface CircuitEdgeRecord {
  label: string
  pre_neuron_id: string
  post_neuron_id: string
  synapse_count: number
  synapse_count_label: string
  dataset: string
  dataset_version: string
  simulation_weight: SimulationWeightInfo | null
}

export interface CircuitEdgesPage {
  circuit_id: string
  circuit_hash: string
  label: string
  total: number
  offset: number
  limit: number
  items: CircuitEdgeRecord[]
}

export interface BiologicalMetadata {
  label: string
  neuron_id: string
  cell_type: string | null
  cell_class: string | null
  neurotransmitter_prediction: string | null
  dataset: string
  dataset_version: string
}

export interface CircuitMetadata {
  label: string
  minimum_hop_from_seed: number
  is_seed: boolean
  is_target: boolean
  side: string | null
  role: string | null
  stimulated_by_config: boolean | null
}

export interface ConnectivitySummary {
  label: string
  in_degree: number
  out_degree: number
  in_synapses: number
  out_synapses: number
}

export interface NeuronDetail {
  circuit_id: string
  circuit_hash: string
  biological: BiologicalMetadata
  circuit: CircuitMetadata
  connectivity: ConnectivitySummary
  not_available_marker: string
}

export interface NeighborRecord {
  neuron_id: string
  cell_type: string | null
  synapse_count: number
  pre_neuron_id: string
  post_neuron_id: string
  dataset: string
  dataset_version: string
}

export interface NeighborList {
  total: number
  offset: number
  limit: number
  items: NeighborRecord[]
}

export interface NeighborsResponse {
  label: string
  circuit_id: string
  circuit_hash: string
  neuron_id: string
  direction: 'upstream' | 'downstream' | 'both'
  upstream: NeighborList | null
  downstream: NeighborList | null
}

export interface EdgeDetail {
  label: 'BIOLOGICAL STRUCTURAL CONNECTION'
  pre: BiologicalMetadata
  post: BiologicalMetadata
  synapse_count: number
  synapse_count_label: string
  dataset: string
  dataset_version: string
  circuit_id: string
  circuit_hash: string
  simulation_weight: SimulationWeightInfo | null
}

export interface TargetReport {
  neuron_id: string
  reachable: boolean
  minimum_path_length: number | null
}

export interface CircuitSummary {
  circuit_id: string
  dataset: string
  dataset_version: string
  circuit_hash: string
  canonical_graph: { selection_rule: string; neuron_count: number; connection_count: number; fingerprint: string }
  extractor_config: Record<string, unknown>
  seed_neurons: number
  target_neurons: TargetReport[]
  neurons: number
  edges: number
  synapses_total: number
  cell_type_counts: Record<string, number>
  extracted_at: string
  extractor_version: string
  biological_interpretation: string
  biological_status: string | null
  research_document: string | null
  config_version: string | null
  disclaimer: string
}

export interface CircuitProvenance {
  disclaimer: string
  circuit_id: string
  circuit_hash: string
  expected_circuit_hash: string | null
  circuit_verified: boolean
  biological_status: string | null
  research_document: string | null
  dataset: string
  dataset_version: string
  license: string | null
  source_page: string | null
  download_url: string | null
  source_dataset: {
    name: string
    version: string
    official_neuron_count: number | null
    official_neuron_count_source: string | null
    description: string | null
  } | null
  canonical_graph: { selection_rule: string; neuron_count: number; connection_count: number; description: string | null }
  canonical_graph_note: string
  loaded_circuit: Record<string, number>
  raw_files: { role: string; path: string; sha256: string | null }[]
  graph_fingerprint: string
  extracted_at: string
  extractor_version: string
  citations: Citation[]
  mapping_confidence: Record<string, string>
  limitations: string[]
}

function hasPage(value: unknown): value is Record<string, unknown> & { total: number; items: unknown[] } {
  return isRecord(value) && typeof value['total'] === 'number' && Array.isArray(value['items'])
}

export function isCircuitNodesPage(value: unknown): value is CircuitNodesPage {
  return hasPage(value) && typeof value['circuit_hash'] === 'string'
}

export function isCircuitEdgesPage(value: unknown): value is CircuitEdgesPage {
  return hasPage(value) && typeof value['circuit_hash'] === 'string'
}

export function isNeuronDetail(value: unknown): value is NeuronDetail {
  return isRecord(value) && isRecord(value['biological']) && isRecord(value['circuit']) && isRecord(value['connectivity'])
}

export function isNeighborsResponse(value: unknown): value is NeighborsResponse {
  return isRecord(value) && typeof value['neuron_id'] === 'string' && 'upstream' in value && 'downstream' in value
}

export function isEdgeDetail(value: unknown): value is EdgeDetail {
  return isRecord(value) && value['label'] === 'BIOLOGICAL STRUCTURAL CONNECTION' && isRecord(value['pre']) && isRecord(value['post'])
}

export function isCircuitSummary(value: unknown): value is CircuitSummary {
  return isRecord(value) && typeof value['circuit_id'] === 'string' && typeof value['neurons'] === 'number' && isRecord(value['canonical_graph'])
}

export function isCircuitProvenance(value: unknown): value is CircuitProvenance {
  return isRecord(value) && typeof value['circuit_hash'] === 'string' && isRecord(value['canonical_graph']) && isRecord(value['loaded_circuit'])
}
