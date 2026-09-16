import type { ActionValue, Direction } from '../api/types.ts'

/**
 * Demo presets. "Expected current model result" is what the current escape_v1 configuration
 * and P3 simulation defaults produce (recorded in PROGRESS.md / data/simulations) — it is
 * NOT a biological threshold and changes if the model parameters change.
 */
export interface DemoPreset {
  id: 'low' | 'medium' | 'high'
  label: 'LOW' | 'MEDIUM' | 'HIGH'
  direction: Direction
  intensity: number
  expected: ActionValue
}

export const EXPECTED_RESULT_LABEL = 'Expected current model result'

export const DEMO_PRESETS: readonly DemoPreset[] = [
  { id: 'low', label: 'LOW', direction: 'center', intensity: 0.2, expected: 'NO_ACTION' },
  { id: 'medium', label: 'MEDIUM', direction: 'center', intensity: 0.5, expected: 'ESCAPE' },
  { id: 'high', label: 'HIGH', direction: 'center', intensity: 1.0, expected: 'ESCAPE' },
]

export function actionLabel(action: ActionValue): 'NO ACTION' | 'ESCAPE' {
  return action === 'ESCAPE' ? 'ESCAPE' : 'NO ACTION'
}

export function presetFor(direction: Direction, intensity: number): DemoPreset | null {
  return DEMO_PRESETS.find((p) => p.direction === direction && Math.abs(p.intensity - intensity) < 1e-9) ?? null
}
