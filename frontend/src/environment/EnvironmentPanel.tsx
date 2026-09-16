import type { ChangeEvent } from 'react'

import { DIRECTIONS, type Direction } from '../api/types.ts'
import type { DemoPhase, DemoView } from '../demo/useEscapeDemo.ts'

export interface EnvironmentPanelProps {
  direction: Direction
  intensity: number
  intensityValid: boolean
  phase: DemoPhase
  view: DemoView
  onDirectionChange: (direction: Direction) => void
  onIntensityChange: (intensity: number) => void
  onTrigger: () => void
  onReset: () => void
}

const LOOM_X: Record<Direction, number> = { left: 64, center: 160, right: 256 }
const LOOM_Y = 62
const FLY_X = 160
const FLY_Y = 172

/** Radius of the looming disc for the current replay step (visual mapping of backend steps). */
function loomRadius(view: DemoView, intensity: number): number {
  if (view.steps === 0 || view.step === 0) return 0
  return 6 + view.stimulusProgress * (16 + 44 * intensity)
}

export function EnvironmentPanel(props: EnvironmentPanelProps) {
  const { direction, intensity, intensityValid, phase, view } = props
  const busy = phase === 'requesting'
  const radius = loomRadius(view, intensity)
  const loomVisible = radius > 0
  const loomState = view.stimulusActive ? 'active' : loomVisible ? 'held' : 'idle'
  const loomX = LOOM_X[direction]

  const onSlider = (event: ChangeEvent<HTMLInputElement>) => props.onIntensityChange(Number(event.target.value))
  const onNumber = (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value.trim()
    props.onIntensityChange(value === '' ? Number.NaN : Number(value))
  }

  return (
    <section className="panel panel--environment" data-testid="environment-panel" aria-labelledby="env-title">
      <header className="panel__header">
        <div>
          <p className="panel__kicker">Environment</p>
          <h2 id="env-title" className="panel__title">
            Virtual arena
          </h2>
        </div>
        <span className="tag tag--input">APPLICATION INPUT</span>
      </header>

      <div className={`arena arena--${loomState}`} data-testid="arena" data-loom-state={loomState}>
        <svg viewBox="0 0 320 220" role="img" aria-label="Virtual fly with a looming object approaching from the selected direction">
          <defs>
            <radialGradient id="loomGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ff9f6e" stopOpacity="0.95" />
              <stop offset="70%" stopColor="#ff6a3d" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#ff6a3d" stopOpacity="0.05" />
            </radialGradient>
            <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0d141c" />
              <stop offset="100%" stopColor="#141d28" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="320" height="220" fill="url(#ground)" />
          <g className="arena__grid" aria-hidden="true">
            {[40, 80, 120, 160, 200, 240, 280].map((x) => (
              <line key={`v${x}`} x1={x} y1="0" x2={x} y2="220" />
            ))}
            {[40, 80, 120, 160, 200].map((y) => (
              <line key={`h${y}`} x1="0" y1={y} x2="320" y2={y} />
            ))}
          </g>
          <line className="arena__horizon" x1="0" y1="190" x2="320" y2="190" />

          {/* looming object: expands with the replayed backend steps of the stimulus window */}
          <g className={`loom loom--${loomState}`} data-testid="looming-object" data-radius={radius.toFixed(1)}>
            <circle className="loom__origin" cx={loomX} cy={LOOM_Y} r="6" />
            {loomVisible && (
              <>
                <line className="loom__path" x1={loomX} y1={LOOM_Y} x2={FLY_X} y2={FLY_Y - 14} />
                <circle className="loom__halo" cx={loomX} cy={LOOM_Y} r={radius * 1.35} />
                <circle className="loom__disc" cx={loomX} cy={LOOM_Y} r={radius} fill="url(#loomGlow)" />
              </>
            )}
          </g>

          {/* virtual fly: takes off on ESCAPE (visual only; no direction is decoded) */}
          <g className={`fly ${view.escaped ? 'fly--escape' : ''}`} data-testid="virtual-fly" data-escaped={view.escaped}>
            <ellipse className="fly__shadow" cx={FLY_X} cy={FLY_Y + 14} rx="14" ry="3" />
            <ellipse className="fly__wing" cx={FLY_X - 9} cy={FLY_Y - 6} rx="11" ry="4" transform={`rotate(-25 ${FLY_X - 9} ${FLY_Y - 6})`} />
            <ellipse className="fly__wing" cx={FLY_X + 9} cy={FLY_Y - 6} rx="11" ry="4" transform={`rotate(25 ${FLY_X + 9} ${FLY_Y - 6})`} />
            <ellipse className="fly__body" cx={FLY_X} cy={FLY_Y} rx="8" ry="12" />
            <circle className="fly__head" cx={FLY_X} cy={FLY_Y - 14} r="5" />
            <circle className="fly__eye" cx={FLY_X - 3} cy={FLY_Y - 15} r="1.6" />
            <circle className="fly__eye" cx={FLY_X + 3} cy={FLY_Y - 15} r="1.6" />
          </g>

          <text className="arena__label" x="10" y="16">
            VIRTUAL ENVIRONMENT · synthetic stimulus · no camera
          </text>
          <text className="arena__label arena__label--right" x="310" y="212" textAnchor="end">
            {view.steps > 0 ? `step ${view.step} / ${view.steps}` : 'awaiting stimulus'}
          </text>
        </svg>
        {view.escaped && (
          <div className="arena__banner" data-testid="arena-escape-banner">
            takeoff animation · decoded ESCAPE · direction not decoded
          </div>
        )}
      </div>

      <div className="controls">
        <fieldset className="control" disabled={busy}>
          <legend className="control__label">Looming direction</legend>
          <div className="segmented" role="group" aria-label="Looming direction">
            {DIRECTIONS.map((option) => (
              <button
                key={option}
                type="button"
                className={`segmented__option ${option === direction ? 'segmented__option--selected' : ''}`}
                aria-pressed={option === direction}
                data-testid={`direction-${option}`}
                onClick={() => props.onDirectionChange(option)}
              >
                {option.toUpperCase()}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="control">
          <label className="control__label" htmlFor="intensity-slider">
            Intensity <span className="muted">(application input, 0–1; not a measured quantity)</span>
          </label>
          <div className="intensity">
            <input
              id="intensity-slider"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={intensityValid ? intensity : 0}
              onChange={onSlider}
              disabled={busy}
              data-testid="intensity-slider"
              aria-label="Looming intensity"
            />
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={Number.isNaN(intensity) ? '' : intensity}
              onChange={onNumber}
              disabled={busy}
              data-testid="intensity-input"
              aria-label="Looming intensity value"
              aria-invalid={!intensityValid}
              className={intensityValid ? '' : 'invalid'}
            />
            <output className="intensity__value" data-testid="intensity-value" htmlFor="intensity-slider">
              {Number.isNaN(intensity) ? '—' : intensity.toFixed(2)}
            </output>
          </div>
          {!intensityValid && (
            <p className="field-error" role="alert" data-testid="intensity-error">
              Invalid intensity: enter a number between 0 and 1.
            </p>
          )}
        </div>

        <div className="actions">
          <button
            type="button"
            className="btn btn--primary"
            onClick={props.onTrigger}
            disabled={busy || !intensityValid}
            data-testid="trigger-looming"
          >
            {busy ? 'RUNNING…' : 'TRIGGER LOOMING'}
          </button>
          <button type="button" className="btn btn--ghost" onClick={props.onReset} data-testid="reset">
            RESET
          </button>
        </div>
      </div>
    </section>
  )
}
