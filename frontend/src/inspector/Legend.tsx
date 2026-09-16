import { cellTypeColor } from './cellTypeStyle.ts'

export function Legend({ cellTypes, counts }: { cellTypes: string[]; counts: Record<string, number> }) {
  return (
    <section className="legend" data-testid="inspector-legend" aria-label="Legend">
      <div className="legend__group">
        <p className="legend__title">
          Neuron identity <span className="tag tag--bio">BIOLOGICAL DATA</span>
        </p>
        <ul className="legend__list">
          {cellTypes.map((type) => (
            <li key={type} className="legend__item">
              <span className="legend__swatch" style={{ background: cellTypeColor(type, cellTypes) }} aria-hidden="true" />
              <span className="mono">{type}</span>
              <span className="muted">{counts[type] ?? 0} neurons</span>
            </li>
          ))}
          <li className="legend__item">
            <span className="legend__swatch legend__swatch--target" aria-hidden="true" />
            <span>large node = extraction target (DNp01 / giant fiber)</span>
          </li>
        </ul>
      </div>
      <div className="legend__group">
        <p className="legend__title">
          Activity state <span className="tag tag--simulated">SIMULATED</span>
        </p>
        <ul className="legend__list">
          <li className="legend__item">
            <span className="legend__ring" aria-hidden="true" />
            <span>inactive (at resting potential)</span>
          </li>
          <li className="legend__item">
            <span className="legend__ring legend__ring--active" aria-hidden="true" />
            <span>simulated active (membrane potential above rest)</span>
          </li>
          <li className="legend__item">
            <span className="legend__ring legend__ring--fired" aria-hidden="true" />
            <span>simulated fired (spike at this step)</span>
          </li>
          <li className="legend__item">
            <span className="legend__ring legend__ring--refractory" aria-hidden="true" />
            <span>simulated refractory</span>
          </li>
        </ul>
      </div>
      <div className="legend__group">
        <p className="legend__title">
          Edges <span className="tag tag--bio">STRUCTURAL CONNECTION — BIOLOGICAL DATA</span>
        </p>
        <p className="muted legend__note">
          Arrow = pre → post; width ∝ synapse count from the dataset. Every edge is read from the P2 circuit
          artifact; none is derived by the UI.
        </p>
      </div>
    </section>
  )
}
