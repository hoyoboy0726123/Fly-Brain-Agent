import type { InterventionLabConfig } from '../api/types.ts'

export const INTERVENTION_DISCLAIMER =
  'Neural interventions in this lab are computational manipulations of simulated neural dynamics. ' +
  'They do not reproduce a specific biological silencing, optogenetic, genetic, pharmacological, or lesion technique. ' +
  'Biological structural connectivity remains unchanged.'

export const EMBODIMENT_DISCLAIMER =
  'Structural connectivity is biological data. Neural activity is simulated. ' +
  'Virtual sensing, motor mapping, body dynamics, and world physics are computational interpretations.'

/** Literature (BIOLOGICAL EVIDENCE) kept visually and semantically apart from the computational result. */
export function BiologicalContext({ config, summary }: { config: InterventionLabConfig | null; summary: string[] | null }) {
  const context = config?.biological_context ?? null
  return (
    <section className="panel panel--context" data-testid="biological-context" aria-labelledby="context-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Biological context</p>
          <h2 id="context-title" className="panel__title">
            Biological evidence vs current computational result
          </h2>
        </div>
      </header>
      <div className="context__grid">
        <div className="context__col context__col--bio" data-testid="context-biological">
          <h3 className="lab-state__title">
            <span className="tag tag--bio">BIOLOGICAL EVIDENCE</span> literature — motivates target selection only
          </h3>
          {context ? (
            <>
              <p>
                <strong>LC4.</strong> {context.LC4}
              </p>
              <p>
                <strong>LPLC2.</strong> {context.LPLC2}
              </p>
              <p className="muted">
                {context.citation.authors} ({context.citation.year}). {context.citation.title}. {context.citation.journal}. DOI{' '}
                <span className="mono">{context.citation.doi}</span>
              </p>
              <p className="muted">{context.scope}</p>
            </>
          ) : (
            <p className="muted">Served by GET /embodiment/intervention/config.</p>
          )}
        </div>
        <div className="context__col context__col--comp" data-testid="context-computational">
          <h3 className="lab-state__title">
            <span className="tag tag--simulated">CURRENT COMPUTATIONAL RESULT</span> this simulation only
          </h3>
          {summary ? (
            <ul className="comparison__summary">
              {summary.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">No comparison yet. Run CONTROL + INTERVENTION to see what the current model does.</p>
          )}
          <p className="muted">Never a validation of the biological study: the model is a simplified LIF-like simulation on MaleCNS structure.</p>
        </div>
      </div>
      <p className="disclaimer lab-disclaimer" data-testid="intervention-disclaimer">
        {config?.intervention_disclaimer ?? INTERVENTION_DISCLAIMER}
      </p>
      <p className="disclaimer lab-disclaimer" data-testid="intervention-embodiment-disclaimer">
        {config?.disclaimer ?? EMBODIMENT_DISCLAIMER}
      </p>
    </section>
  )
}
