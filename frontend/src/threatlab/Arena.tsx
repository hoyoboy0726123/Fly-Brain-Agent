import type { ThreatLabRunResult, ThreatLabStep } from '../api/types.ts'
import type { LabPhase } from './useThreatLab.ts'

const WIDTH = 560
const HEIGHT = 380
const PAD = 34
const EYE_R = 44

export interface ArenaProps {
  phase: LabPhase
  result: ThreatLabRunResult | null
  step: ThreatLabStep | null
}

/** World extent (units) that keeps every recorded object and body position on screen. */
export function arenaExtent(result: ThreatLabRunResult): number {
  let extent = 5
  for (const s of result.timeline) {
    extent = Math.max(extent, Math.abs(s.body.position.x), Math.abs(s.body.position.y))
    for (const o of s.world.objects) extent = Math.max(extent, Math.abs(o.position.x) + o.size, Math.abs(o.position.y) + o.size)
  }
  return extent * 1.08
}

function fmt(value: number, digits = 2): string {
  return value.toFixed(digits)
}

/**
 * Top-down 2D arena (SVG, no 3D engine). Everything drawn comes from the replayed
 * backend record: the object from `WorldState`, the fly from `BodyState`, the fly's-eye
 * inset from the sensor's recorded angular size. The short CSS transition between two
 * recorded states is presentation only (no intermediate state is computed here).
 */
export function Arena({ phase, result, step }: ArenaProps) {
  const extent = result ? arenaExtent(result) : 5
  const scale = Math.min(WIDTH / 2 - PAD, HEIGHT / 2 - PAD) / extent
  const cx = WIDTH / 2
  const cy = HEIGHT / 2
  const toScreen = (x: number, y: number) => ({ sx: cx + x * scale, sy: cy - y * scale })
  const fly = step?.body ?? null
  const flyScreen = fly ? toScreen(fly.position.x, fly.position.y) : null
  const lift = fly ? fly.position.z * scale : 0
  const headingDeg = fly ? (-fly.heading * 180) / Math.PI : 0
  const angular = step?.sensor.angular_size_rad ?? 0
  const eyeFraction = Math.min(1, angular / Math.PI)
  const bearing = step?.sensor.bearing_rad ?? 0
  const gridLines = [-1, -0.5, 0.5, 1].map((f) => f * extent)
  const waiting = phase === 'idle' || phase === 'running'
  const overlay = phase === 'error' ? 'NO RESULT' : waiting ? (phase === 'running' ? 'RUNNING EXPERIMENT…' : 'WAITING FOR EXPERIMENT') : null

  return (
    <div className="lab-arena" data-testid="lab-arena" data-phase={phase} data-step={step?.step_index ?? -1}>
      <svg className="lab-arena__svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Top-down view of the virtual world: the fly at the origin and the approaching object">
        <defs>
          <radialGradient id="labObjectFill" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffd9a3" />
            <stop offset="100%" stopColor="#f2b134" />
          </radialGradient>
        </defs>
        <rect className="lab-arena__floor" x="0" y="0" width={WIDTH} height={HEIGHT} />
        {gridLines.map((g) => (
          <g key={g} className="lab-arena__grid">
            <line x1={cx + g * scale} y1={PAD / 2} x2={cx + g * scale} y2={HEIGHT - PAD / 2} />
            <line x1={PAD / 2} y1={cy - g * scale} x2={WIDTH - PAD / 2} y2={cy - g * scale} />
            <text x={cx + g * scale} y={HEIGHT - 8} textAnchor="middle">
              {fmt(g, 0)}
            </text>
          </g>
        ))}
        <line className="lab-arena__axis" x1={PAD / 2} y1={cy} x2={WIDTH - PAD / 2} y2={cy} />
        <line className="lab-arena__axis" x1={cx} y1={PAD / 2} x2={cx} y2={HEIGHT - PAD / 2} />
        <text className="lab-arena__axis-label" x={WIDTH - PAD / 2} y={cy - 6} textAnchor="end">
          x (units)
        </text>
        <text className="lab-arena__axis-label" x={cx + 6} y={PAD / 2 + 12}>
          y (units) · fly’s left
        </text>

        {step &&
          step.world.objects.map((o) => {
            const { sx, sy } = toScreen(o.position.x, o.position.y)
            return (
              <g
                key={o.object_id}
                className="lab-arena__object"
                data-testid={`lab-object-${o.object_id}`}
                data-x={o.position.x}
                data-y={o.position.y}
                data-z={o.position.z}
                data-size={o.size}
                style={{ transform: `translate(${fmt(sx, 1)}px, ${fmt(sy, 1)}px)` }}
              >
                <circle className="lab-arena__object-halo" r={Math.max(4, o.size * scale) + 6} />
                <circle className="lab-arena__object-disc" r={Math.max(4, o.size * scale)} />
                <text className="lab-arena__object-label" y={-Math.max(4, o.size * scale) - 6} textAnchor="middle">
                  {o.object_type.replace(/_/g, ' ')}
                </text>
              </g>
            )
          })}

        {fly && flyScreen && (
          <g
            className={`lab-arena__fly ${fly.grounded ? '' : 'lab-arena__fly--airborne'}`}
            data-testid="lab-fly"
            data-x={fly.position.x}
            data-y={fly.position.y}
            data-z={fly.position.z}
            data-heading={fly.heading}
            data-grounded={fly.grounded}
            style={{ transform: `translate(${fmt(flyScreen.sx, 1)}px, ${fmt(flyScreen.sy, 1)}px)` }}
          >
            <ellipse className="lab-arena__shadow" rx={9 + lift * 0.4} ry={5 + lift * 0.2} />
            <g style={{ transform: `translate(0px, ${fmt(-lift, 1)}px) rotate(${fmt(headingDeg, 1)}deg)` }}>
              <ellipse className="lab-arena__fly-body" rx="12" ry="6" />
              <polygon className="lab-arena__fly-head" points="10,-4 18,0 10,4" />
              <ellipse className="lab-arena__fly-wing" cx="-3" cy="-7" rx="8" ry="3" />
              <ellipse className="lab-arena__fly-wing" cx="-3" cy="7" rx="8" ry="3" />
            </g>
            <text className="lab-arena__fly-label" y="24" textAnchor="middle">
              fly (point body)
            </text>
          </g>
        )}

        <g className="lab-arena__eye" data-testid="lab-eye" data-angular-size={angular} data-fraction={eyeFraction.toFixed(4)} style={{ transform: `translate(${WIDTH - EYE_R - 34}px, ${EYE_R + 14}px)` }}>
          <circle className="lab-arena__eye-ring" r={EYE_R} />
          {step && step.sensor.visible && angular > 0 && (
            <circle className="lab-arena__eye-disc" cx={fmt(-Math.sin(bearing) * EYE_R * 0.45, 1)} cy="0" r={fmt(Math.max(1.5, eyeFraction * EYE_R), 1)} />
          )}
          <text className="lab-arena__eye-label" y={EYE_R + 14} textAnchor="middle">
            fly’s eye · angular size
          </text>
        </g>

        {overlay && (
          <g className="lab-arena__overlay" data-testid="lab-overlay">
            <rect x={cx - 150} y={cy - 26} width="300" height="52" rx="10" />
            <text x={cx} y={cy + 6} textAnchor="middle" data-testid="lab-overlay-text">
              {overlay}
            </text>
          </g>
        )}
      </svg>
      <p className="lab-arena__caption muted">
        Top-down view in dimensionless world units. Object = <code>WorldState</code>, fly = <code>BodyState</code>, eye inset = recorded
        angular size. Motion between two recorded steps is a presentation-only transition.
      </p>
    </div>
  )
}
