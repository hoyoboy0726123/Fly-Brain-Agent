import type { EscapeConfig } from '../api/types.ts'
import type { DemoError } from '../demo/useEscapeDemo.ts'

export interface HowItWorksProps {
  config: EscapeConfig | null
  configError: DemoError | null
}

const FALLBACK_LAYERS = [
  {
    kind: 'BIOLOGICAL STRUCTURE',
    layer: 'Structural connectivity',
    description:
      'Neurons and synaptic connections come from the MaleCNS v1.0 connectome (canonical simulation graph). The escape circuit is a hash-sealed structural subgraph.',
  },
  {
    kind: 'COMPUTATIONAL DYNAMICS',
    layer: 'Neural activity',
    description:
      'Activity is produced by a simplified discrete-time LIF-like model with computational parameters. Every spike shown here is simulated, not recorded.',
  },
  {
    kind: 'APPLICATION DECODING',
    layer: 'Behavior decoding',
    description:
      'The looming stimulus is mapped to injected current and giant-fiber output is decoded into NO_ACTION or ESCAPE by a rule. These are computational interpretations.',
  },
]

export function HowItWorks({ config, configError }: HowItWorksProps) {
  const layers = config?.layers ?? FALLBACK_LAYERS
  const status = config?.biological_status ?? 'unknown (backend configuration not loaded)'

  return (
    <details className="how" data-testid="how-it-works">
      <summary className="how__summary">How this works</summary>
      <div className="how__body">
        <p className="how__status" data-testid="biological-status" data-status={config?.biological_status ?? ''}>
          BIOLOGICAL CIRCUIT STATUS: <strong>{status}</strong>
        </p>
        {configError && (
          <p className="alert" role="status">
            Configuration could not be loaded from the backend ({configError.code}); the layer description below is the
            static fallback text.
          </p>
        )}

        <div className="layers">
          {layers.map((layer) => (
            <article key={layer.kind} className={`layer layer--${layer.kind.split(' ')[0]?.toLowerCase() ?? 'x'}`}>
              <p className="layer__kind">{layer.kind}</p>
              <h3 className="layer__title">{layer.layer}</h3>
              <p className="layer__text">{layer.description}</p>
            </article>
          ))}
        </div>

        {config && (
          <div className="how__facts">
            <dl className="kv">
              <dt>Dataset</dt>
              <dd>
                {config.dataset} {config.dataset_version} · canonical graph: <code>{config.canonical_selection_rule}</code>
              </dd>
              <dt>Circuit</dt>
              <dd>
                <code>{config.circuit_id}</code> · {config.circuit_neurons} neurons / {config.circuit_edges} edges · hash{' '}
                <code title={config.circuit_hash}>{config.circuit_hash.slice(0, 16)}…</code>{' '}
                {config.circuit_verified ? '(verified against the configured hash)' : '(NOT verified)'}
              </dd>
              <dt>Sensory population</dt>
              <dd>
                {config.sensory_cell_types.join(' + ')}: L {config.sensory_population_counts['L'] ?? 0} / R{' '}
                {config.sensory_population_counts['R'] ?? 0}; stimulated in circuit L{' '}
                {config.stimulated_sensory_counts['L'] ?? 0} / R {config.stimulated_sensory_counts['R'] ?? 0}; excluded L{' '}
                {config.excluded_sensory_counts['L'] ?? 0} / R {config.excluded_sensory_counts['R'] ?? 0}
                {config.exclusion_reason ? ` (${config.exclusion_reason})` : ''}
              </dd>
              <dt>Output</dt>
              <dd>
                {config.output_cell_types.join(', ')} (giant fiber): L {config.output_groups['L']?.join(', ') ?? '—'} · R{' '}
                {config.output_groups['R']?.join(', ') ?? '—'}
              </dd>
              <dt>Stimulus mapping</dt>
              <dd>{config.mapping_rule}</dd>
              <dt>Decoder</dt>
              <dd>{config.decoder_rule}</dd>
              <dt>Simulation</dt>
              <dd>
                {config.simulation_steps} steps, stimulus for {config.stimulus_duration_steps} steps; threshold{' '}
                {config.simulation_config.threshold}, leak {config.simulation_config.leak}, refractory{' '}
                {config.simulation_config.refractory_steps}, weights {config.simulation_config.weight_transform} ×{' '}
                {config.simulation_config.weight_scale}, seed {config.simulation_config.random_seed} —{' '}
                <em>{config.simulation_config.label}</em>
              </dd>
              <dt>Research record</dt>
              <dd>
                <code>{config.research_document}</code>
              </dd>
            </dl>

            <h3>Known limitations</h3>
            <ul className="how__list">
              {config.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>

            <h3>Citations ({config.citations.length})</h3>
            <ul className="how__list how__list--citations">
              {config.citations.map((c) => (
                <li key={c.key}>
                  {c.authors} ({c.year}). <em>{c.title}</em>. {c.venue}.{' '}
                  {c.doi ? <code>doi:{c.doi}</code> : c.url ? <code>{c.url}</code> : null}{' '}
                  <span className="muted">— {c.claim} [{c.confidence}; {c.verification}]</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  )
}
