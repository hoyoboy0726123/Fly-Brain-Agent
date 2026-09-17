import type { ThreatLab } from './useThreatLab.ts'

/** Safe application-level parameters (world geometry, loop length, seed). No neural parameter. */
export function ParamsForm({ lab }: { lab: ThreatLab }) {
  const { params } = lab.state
  const running = lab.state.phase === 'running'
  const limit = (key: string) => lab.limits[key] ?? {}
  const number = (key: keyof typeof params, testId: string, limitKey: string, step: number, unit?: string) => {
    const l = limit(limitKey)
    return (
      <label className="lab-param">
        <span className="control__label">
          {testId.replace('lab-', '').replace(/-/g, ' ')}
          {unit ? ` (${unit})` : ''}
        </span>
        <input
          type="number"
          className="mono"
          value={params[key]}
          min={l.min}
          max={l.max}
          step={step}
          disabled={running}
          onChange={(event) => lab.setParams({ [key]: Number(event.target.value) } as Partial<typeof params>)}
          data-testid={testId}
        />
      </label>
    )
  }
  return (
    <form
      className="lab-params"
      data-testid="lab-params"
      onSubmit={(event) => {
        event.preventDefault()
        lab.run()
      }}
    >
      <fieldset className="control">
        <legend className="control__label">Object azimuth</legend>
        <div className="segmented segmented--small" role="group" aria-label="Object azimuth preset">
          {[
            { id: 'left', label: 'LEFT (+60°)', value: 60 },
            { id: 'center', label: 'CENTER (0°)', value: 0 },
            { id: 'right', label: 'RIGHT (−60°)', value: -60 },
          ].map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`segmented__option ${params.azimuthDeg === preset.value ? 'segmented__option--selected' : ''}`}
              disabled={running}
              onClick={() => lab.setParams({ azimuthDeg: preset.value })}
              data-testid={`lab-azimuth-${preset.id}`}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="lab-params__grid">
        {number('startDistance', 'lab-start-distance', 'world.start_distance', 0.5, 'units')}
        {number('approachSpeed', 'lab-approach-speed', 'world.approach_speed', 0.5, 'units/s')}
        {number('azimuthDeg', 'lab-azimuth', 'world.azimuth_deg', 5, 'deg')}
        {number('maxSteps', 'lab-steps', 'max_steps', 1, 'loop steps')}
        {number('seed', 'lab-seed', 'seed', 1)}
      </div>
      {!lab.paramsValid && (
        <p className="lab-params__error" role="alert" data-testid="lab-params-error">
          A parameter is outside the backend limits (see <code>run_request_limits</code>).
        </p>
      )}
      <p className="muted panel__note">
        Only world geometry, loop length and the seed can be changed. Neural parameters of escape_v1 are fixed and not exposed.
      </p>
    </form>
  )
}
