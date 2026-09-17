import type { InterventionCompareResult } from '../api/types.ts'

function yesNo(value: boolean): string {
  return value ? 'yes' : 'NO'
}

/** Matched conditions (verified by the backend) and descriptive differences. */
export function ComparisonPanel({ result }: { result: InterventionCompareResult }) {
  const { matched_conditions: matched, differences: diff, synchronization: sync, structural_integrity: integrity } = result.comparison
  const conditions = Object.entries(matched).filter(([key]) => key.startsWith('same_')) as [string, boolean][]
  return (
    <section className="panel panel--comparison" data-testid="comparison-panel" aria-labelledby="comparison-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Comparison</p>
          <h2 id="comparison-title" className="panel__title">
            {diff.label}
          </h2>
        </div>
        <span className={`tag ${matched.all_matched ? 'tag--decoding' : 'tag--error'}`} data-testid="matched-badge" data-all-matched={matched.all_matched}>
          {matched.all_matched ? 'SAME WORLD • SAME SEED • SAME MODEL' : 'CONDITIONS NOT MATCHED'}
        </span>
      </header>
      <div className="comparison__grid">
        <div>
          <h3 className="lab-state__title">Matched conditions (verified)</h3>
          <ul className="comparison__conditions mono" data-testid="matched-conditions">
            {conditions.map(([key, value]) => (
              <li key={key} data-testid={`matched-${key}`} data-value={value}>
                {key.replace('same_', '').replace(/_/g, ' ')}: {yesNo(value)}
              </li>
            ))}
            <li>only difference: {matched.only_difference}</li>
            <li data-testid="structure-unchanged" data-value={integrity.unchanged}>
              structure unchanged: {yesNo(integrity.unchanged)} ({integrity.after.node_count} neurons / {integrity.after.edge_count} edges /{' '}
              {integrity.after.synapse_total} synapses, hash {integrity.after.circuit_hash.slice(0, 12)}…)
            </li>
          </ul>
        </div>
        <div>
          <h3 className="lab-state__title">Differences (descriptive)</h3>
          <table className="comparison__table mono" data-testid="differences-table">
            <thead>
              <tr>
                <th />
                <th>CONTROL</th>
                <th>INTERVENTION</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>first ESCAPE step</td>
                <td data-testid="diff-control-first-escape">{diff.control_first_escape_step ?? 'NONE'}</td>
                <td data-testid="diff-intervention-first-escape">{diff.intervention_first_escape_step ?? 'NONE'}</td>
              </tr>
              <tr>
                <td>ESCAPE occurred</td>
                <td>{yesNo(diff.control_escape_occurred)}</td>
                <td data-testid="diff-intervention-escape-occurred">{yesNo(diff.intervention_escape_occurred)}</td>
              </tr>
              {Object.entries(diff.simulated_firing_totals).map(([cellType, values]) => (
                <tr key={cellType} data-testid={`diff-firing-${cellType}`}>
                  <td>{cellType === 'DNp01' ? 'GF (DNp01)' : cellType} simulated spikes</td>
                  <td data-testid={`diff-firing-${cellType}-control`}>{values.control}</td>
                  <td data-testid={`diff-firing-${cellType}-intervention`}>
                    {values.intervention} ({values.delta >= 0 ? '+' : ''}
                    {values.delta})
                  </td>
                </tr>
              ))}
              <tr>
                <td>final displacement</td>
                <td>{diff.control_final_displacement.toFixed(2)}</td>
                <td data-testid="diff-intervention-displacement">{diff.intervention_final_displacement.toFixed(2)}</td>
              </tr>
              <tr>
                <td>first divergent step</td>
                <td colSpan={2} data-testid="diff-first-divergent">
                  {diff.first_divergent_step ?? 'none (identical trials)'}
                </td>
              </tr>
              <tr>
                <td>timeline</td>
                <td>{sync.control_steps} steps</td>
                <td>{sync.intervention_steps} steps</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <ul className="comparison__summary" data-testid="comparison-summary">
        {diff.summary.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <p className="muted panel__note mono">
        runtime: control {result.runtime['control_seconds']?.toFixed(3)} s · intervention {result.runtime['intervention_seconds']?.toFixed(3)} s · combined{' '}
        {result.runtime['combined_seconds']?.toFixed(3)} s · comparison {result.comparison_id}
      </p>
    </section>
  )
}
