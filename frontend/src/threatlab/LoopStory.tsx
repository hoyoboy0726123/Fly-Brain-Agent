import type { ThreatLabStep } from '../api/types.ts'

export type LoopStageId = 'world' | 'sensor' | 'brain' | 'motor' | 'body'
type StageState = 'idle' | 'quiet' | 'active'

export interface LoopStage {
  id: LoopStageId
  title: string
  label: string
  plain: string
  state: StageState
  caption: string
}

const ORDER: LoopStageId[] = ['world', 'sensor', 'brain', 'motor', 'body']

function fmt(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

/**
 * The closed loop WORLD → SENSOR → BRAIN → MOTOR → BODY → WORLD at the replayed step.
 * Stage states are read off the backend record only: a stage is "active" when its recorded
 * value carries signal at this step (looming input > 0, simulated spikes > 0, ESCAPE
 * command, body moving). The highlighted stage is the deepest active one.
 */
export function deriveLoopStages(step: ThreatLabStep | null): { stages: LoopStage[]; current: LoopStageId | null } {
  const object = step?.world.objects[0]
  const moving = step ? !step.body.grounded || Math.hypot(step.body.velocity.x, step.body.velocity.y, step.body.velocity.z) > 0 : false
  const states: Record<LoopStageId, StageState> = {
    world: step ? 'active' : 'idle',
    sensor: step ? (step.sensor.intensity > 0 ? 'active' : 'quiet') : 'idle',
    brain: step ? (step.brain.firing_events > 0 ? 'active' : 'quiet') : 'idle',
    motor: step ? (step.motor.command === 'ESCAPE' ? 'active' : 'quiet') : 'idle',
    body: step ? (moving ? 'active' : 'quiet') : 'idle',
  }
  const captions: Record<LoopStageId, string> = {
    world: step ? (object ? `object at ${fmt(step.sensor.distance)} units` : 'no object') : 'waiting for experiment',
    sensor: step ? (step.sensor.intensity > 0 ? `looming ${fmt(step.sensor.intensity, 3)} · ${step.sensor.direction}` : 'no looming input') : '',
    brain: step ? (step.brain.firing_events > 0 ? `${step.brain.firing_events} simulated spikes · ${step.brain.action}` : 'no simulated spikes · NO_ACTION') : '',
    motor: step ? (step.motor.command === 'ESCAPE' ? 'ESCAPE command' : 'IDLE') : '',
    body: step ? (moving ? (step.body.grounded ? 'moving' : 'airborne') : 'at rest') : '',
  }
  const stages: LoopStage[] = [
    { id: 'world', title: 'WORLD', label: 'COMPUTATIONAL', plain: 'A virtual object approaches the fly (world physics).' },
    { id: 'sensor', title: 'SENSOR', label: 'COMPUTATIONAL SENSOR INPUT', plain: 'Angular size and bearing become a looming stimulus.' },
    { id: 'brain', title: 'BRAIN', label: 'SIMULATED', plain: 'LC4 / LPLC2 → DNp01 activity on MaleCNS structure.' },
    { id: 'motor', title: 'MOTOR', label: 'COMPUTATIONAL MOTOR MAPPING', plain: 'Decoded action becomes a body command.' },
    { id: 'body', title: 'BODY', label: 'SIMPLIFIED COMPUTATIONAL BODY', plain: 'A point body moves; the world sees the new position.' },
  ].map((stage) => ({ ...stage, state: states[stage.id as LoopStageId], caption: captions[stage.id as LoopStageId] }) as LoopStage)
  const current = step ? ([...ORDER].reverse().find((id) => states[id] === 'active') ?? 'world') : null
  return { stages, current }
}

export function LoopStory({ step }: { step: ThreatLabStep | null }) {
  const { stages, current } = deriveLoopStages(step)
  return (
    <ol className="loop" data-testid="loop-story" data-current={current ?? 'none'} aria-label="Closed loop: world, sensor, brain, motor, body, world">
      {stages.map((stage, index) => (
        <li
          key={stage.id}
          className={`loop__stage loop__stage--${stage.state} loop__stage--${stage.id} ${current === stage.id ? 'loop__stage--current' : ''}`}
          data-testid={`loop-stage-${stage.id}`}
          data-state={stage.state}
          data-current={current === stage.id}
        >
          <span className="loop__title">{stage.title}</span>
          <span className="loop__label">{stage.label}</span>
          <span className="loop__plain">{stage.plain}</span>
          <span className="loop__caption mono" data-testid={`loop-caption-${stage.id}`}>
            {stage.caption}
          </span>
          <span className="loop__arrow" aria-hidden="true">
            {index < stages.length - 1 ? '↓' : '↺ WORLD'}
          </span>
        </li>
      ))}
    </ol>
  )
}
