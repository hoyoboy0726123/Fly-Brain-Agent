import { APP_SUBTITLE, APP_TITLE } from '../content.ts'

export interface HeroProps {
  running: boolean
  canRun: boolean
  onRunDemo: () => void
  onExplore: () => void
  onThreatLab: () => void
}

/** Above-the-fold summary: what this is, in one glance, with the two entry points. */
export function Hero({ running, canRun, onRunDemo, onExplore, onThreatLab }: HeroProps) {
  return (
    <section className="hero" data-testid="hero" aria-labelledby="hero-title">
      <h1 id="hero-title" className="hero__title">
        {APP_TITLE}
      </h1>
      <p className="hero__tagline" data-testid="hero-tagline">
        <span>Real fruit-fly connectome.</span>
        <span>Simulated neural activity.</span>
        <span>Observable behavior.</span>
      </p>
      <div className="hero__cta">
        <button type="button" className="btn btn--primary btn--large" onClick={onRunDemo} disabled={running || !canRun} data-testid="cta-run-demo">
          {running ? 'RUNNING…' : 'RUN LOOMING DEMO'}
        </button>
        <button type="button" className="btn btn--large" onClick={onExplore} data-testid="cta-explore">
          EXPLORE THE BRAIN
        </button>
        <button type="button" className="btn btn--large" onClick={onThreatLab} data-testid="cta-threat-lab">
          VIRTUAL THREAT LAB
        </button>
      </div>
      <p className="hero__qualifier subtitle" data-testid="subtitle">
        {APP_SUBTITLE}
      </p>
    </section>
  )
}
