import { BrainPanel } from '../brain/BrainPanel.tsx'
import { ActionPanel } from '../dashboard/ActionPanel.tsx'
import { HowItWorks } from '../dashboard/HowItWorks.tsx'
import { EnvironmentPanel } from '../environment/EnvironmentPanel.tsx'
import { StoryStrip } from './StoryStrip.tsx'
import type { EscapeDemo } from './useEscapeDemo.ts'

/** The P5 three-column demo (Environment / Fly Brain / Action) with the P6.1 story strip. */
export function DemoView({ demo }: { demo: EscapeDemo }) {
  const { state, view } = demo
  const groups = state.result?.group_activity.groups ?? state.config?.groups ?? []
  const edges = state.config?.group_edges ?? []
  return (
    <>
      <StoryStrip phase={state.phase} view={view} />
      <main className="grid" id="demo-panels">
        <EnvironmentPanel
          direction={state.direction}
          intensity={state.intensity}
          intensityValid={demo.intensityValid}
          phase={state.phase}
          view={view}
          onDirectionChange={demo.setDirection}
          onIntensityChange={demo.setIntensity}
          onPreset={(preset) => {
            demo.setDirection(preset.direction)
            demo.setIntensity(preset.intensity)
          }}
          onTrigger={demo.trigger}
          onReset={demo.reset}
        />
        <BrainPanel groups={groups} edges={edges} circuitId={state.config?.circuit_id ?? state.result?.circuit_id ?? null} phase={state.phase} view={view} />
        <ActionPanel
          phase={state.phase}
          view={view}
          result={state.result}
          error={state.error}
          transport={state.transport}
          streamedEvents={state.streamedEvents}
        />
      </main>
      <HowItWorks config={state.config} configError={state.configError} />
    </>
  )
}
