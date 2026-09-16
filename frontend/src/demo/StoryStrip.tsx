import type { DemoPhase, DemoView } from './useEscapeDemo.ts'

type StageState = 'idle' | 'active' | 'done' | 'skipped' | 'no-action'

interface Stage {
  id: string
  title: string
  plain: string
  tag: string
  state: StageState
}

/** Four-step story of one run, derived only from the backend result being replayed. */
export function deriveStages(phase: DemoPhase, view: DemoView): Stage[] {
  const running = phase === 'replaying' || phase === 'finished'
  const finished = phase === 'finished'
  const objectState: StageState = !running ? 'idle' : view.stimulusActive ? 'active' : view.step > 0 ? 'done' : 'idle'
  const sensoryState: StageState = !running
    ? 'idle'
    : view.sensoryFired
      ? view.outputFired || finished
        ? 'done'
        : 'active'
      : finished
        ? 'skipped'
        : 'idle'
  const gfState: StageState = !running ? 'idle' : view.outputFired ? (finished ? 'done' : 'active') : finished ? 'skipped' : 'idle'
  const actionState: StageState = !finished ? 'idle' : view.action === 'ESCAPE' ? 'done' : 'no-action'
  return [
    {
      id: 'object',
      title: 'OBJECT APPROACHES',
      plain: 'A dark disc grows in the fly’s view (the looming stimulus).',
      tag: 'input',
      state: objectState,
    },
    {
      id: 'sensory',
      title: 'LC4 / LPLC2 ACTIVATE',
      plain: 'Looming-detecting visual neurons fire — simulated on real MaleCNS neurons.',
      tag: 'simulated',
      state: sensoryState,
    },
    {
      id: 'gf',
      title: 'SIGNAL REACHES GIANT FIBER',
      plain: 'Their synapses drive DNp01, the escape command neuron (simulated).',
      tag: 'simulated',
      state: gfState,
    },
    {
      id: 'action',
      title: 'ESCAPE',
      plain: 'Giant-fiber activity is decoded as ESCAPE or NO ACTION.',
      tag: 'decoding',
      state: actionState,
    },
  ]
}

function stateCaption(state: StageState): string {
  switch (state) {
    case 'active':
      return 'happening now'
    case 'done':
      return 'done'
    case 'skipped':
      return 'did not happen'
    case 'no-action':
      return 'NO ACTION'
    default:
      return ''
  }
}

export function StoryStrip({ phase, view }: { phase: DemoPhase; view: DemoView }) {
  const stages = deriveStages(phase, view)
  return (
    <ol className="story" data-testid="story-strip" aria-label="What happens during a run">
      {stages.map((stage, index) => (
        <li key={stage.id} className={`story__stage story__stage--${stage.state} story__stage--${stage.tag}`} data-testid={`story-stage-${index + 1}`} data-state={stage.state}>
          <span className="story__index" aria-hidden="true">
            {index + 1}
          </span>
          <span className="story__body">
            <span className="story__title">{stage.title}</span>
            <span className="story__plain">{stage.plain}</span>
            <span className="story__caption">{stateCaption(stage.state)}</span>
          </span>
          {index < stages.length - 1 && (
            <span className="story__arrow" aria-hidden="true">
              →
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}
