import { expect, test, type Page } from '@playwright/test'

/**
 * P7.2 Neural Intervention Lab (live backend, no mocking on the happy paths).
 * Every rendered value is compared with the payload captured from the same
 * `POST /embodiment/intervention/compare` request. No test asserts whether an
 * intervention prevents ESCAPE — only that the UI shows what the backend recorded.
 */

interface Step {
  step_index: number
  body: { position: { x: number; y: number; z: number }; grounded: boolean }
  brain: { action: string; firing_events: number; group_peak_fired: Record<string, number> }
  motor: { command: string }
}
interface Trial {
  experiment: { timeline: Step[]; outcome: { first_escape_step: number | null; displacement: number } }
  resolved_targets: { cell_types: string[]; neuron_count: number; neuron_ids: string[] }
  simulated_firing_totals: Record<string, number>
  suppressed_events: number
}
interface CompareResult {
  control: Trial
  intervention: Trial
  comparison: {
    matched_conditions: Record<string, boolean | string>
    differences: { summary: string[]; intervention_first_escape_step: number | null }
    synchronization: { cursor_max: number; shared_steps: number }
    structural_integrity: { unchanged: boolean }
  }
}

async function openLab(page: Page, query = 'pace=30'): Promise<void> {
  await page.goto(`/?${query}#intervention`)
  await expect(page.getByTestId('intervention-lab')).toBeVisible()
  await expect(page.getByTestId('ilab-resolved')).not.toHaveText('resolving targets…')
}

async function runCompare(page: Page, selector?: string): Promise<CompareResult> {
  if (selector) await page.getByTestId('ilab-selector').selectOption(selector)
  const responsePromise = page.waitForResponse((r) => r.url().includes('/embodiment/intervention/compare') && r.request().method() === 'POST')
  await page.getByTestId('ilab-run').click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const result = (await response.json()) as CompareResult
  await expect(page.getByTestId('intervention-lab')).toHaveAttribute('data-phase', 'ready')
  return result
}

async function pause(page: Page): Promise<void> {
  await page.getByTestId('ilab-pause').click({ force: true })
  await expect(page.getByTestId('ilab-status')).toHaveText('paused')
}

async function seek(page: Page, step: number): Promise<void> {
  await pause(page)
  await page.getByTestId('ilab-slider').fill(String(step))
  await expect(page.getByTestId('ilab-step')).toHaveAttribute('data-step', String(step))
}

function expectTrialStep(page: Page, role: 'control' | 'intervention', step: Step) {
  const panel = page.getByTestId(`trial-${role}`)
  return Promise.all([
    expect(panel).toHaveAttribute('data-step', String(step.step_index)),
    expect(page.getByTestId(`trial-${role}-action`)).toHaveText(step.brain.action),
    expect(page.getByTestId(`trial-${role}-body`)).toHaveAttribute('data-x', String(step.body.position.x)),
    expect(panel.getByTestId('lab-brain-fired')).toHaveText(String(step.brain.firing_events)),
    expect(panel.getByTestId('lab-node-DNp01_L')).toHaveAttribute('data-fired', String(step.brain.group_peak_fired['DNp01_L'])),
    expect(panel.getByTestId('lab-node-LC4_L')).toHaveAttribute('data-fired', String(step.brain.group_peak_fired['LC4_L'])),
    expect(panel.getByTestId('lab-node-LPLC2_L')).toHaveAttribute('data-fired', String(step.brain.group_peak_fired['LPLC2_L'])),
  ])
}

test.describe('Neural Intervention Lab', () => {
  test('1. loads with selector, two trial panels, shared replay, context and disclaimers', async ({ page }) => {
    await openLab(page)
    await expect(page.getByTestId('ilab-title')).toHaveText('NEURAL INTERVENTION LAB')
    await expect(page.getByTestId('ilab-selector')).toBeVisible()
    await expect(page.getByTestId('trial-control')).toBeVisible()
    await expect(page.getByTestId('trial-intervention')).toBeVisible()
    await expect(page.getByTestId('ilab-replay')).toBeVisible()
    await expect(page.getByTestId('biological-context')).toBeVisible()
    await expect(page.getByTestId('ilab-status')).toHaveText('WAITING FOR EXPERIMENT')
    await expect(page.getByTestId('trial-control-action')).toHaveText('WAITING FOR EXPERIMENT')
    await expect(page.getByTestId('trial-intervention-action')).toHaveText('WAITING FOR EXPERIMENT')
    await expect(page.getByTestId('ilab-slider')).toBeDisabled()
    await expect(page.getByTestId('tab-intervention')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('ilab-resolved')).toContainText('neurons resolved from the circuit')
  })

  test('2-4. select SILENCE LC4, run the comparison, both panels receive results', async ({ page }) => {
    await openLab(page)
    await page.getByTestId('ilab-selector').selectOption('SILENCE_LC4')
    await expect(page.getByTestId('ilab-resolved')).toContainText('LC4')
    const result = await runCompare(page)
    expect(result.intervention.resolved_targets.cell_types).toEqual(['LC4'])
    expect(result.intervention.resolved_targets.neuron_count).toBeGreaterThan(0)
    await expect(page.getByTestId('trial-control').getByTestId('lab-fly')).toBeVisible()
    await expect(page.getByTestId('trial-intervention').getByTestId('lab-fly')).toBeVisible()
    await expect(page.getByTestId('trial-intervention-label')).toHaveText('SILENCE LC4')
    await expect(page.getByTestId('trial-intervention-targets')).toContainText(`${result.intervention.resolved_targets.neuron_count} neurons resolved`)
    await expect(page.getByTestId('comparison-panel')).toBeVisible()
    await expect(page.getByTestId('matched-badge')).toHaveAttribute('data-all-matched', 'true')
    await expect(page.getByTestId('structure-unchanged')).toHaveAttribute('data-value', 'true')
    await expect(page.getByTestId('ilab-step')).toHaveAttribute('data-step', String(result.comparison.synchronization.cursor_max), { timeout: 20_000 })
  })

  test('5. one slider controls both panels', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LC4')
    for (const step of [0, 8, 16, 22]) {
      await seek(page, step)
      const c = result.control.experiment.timeline[step]
      const i = result.intervention.experiment.timeline[step]
      if (!c || !i) throw new Error(`no step ${step}`)
      await expectTrialStep(page, 'control', c)
      await expectTrialStep(page, 'intervention', i)
    }
  })

  test('6-8. CONTROL LC4 renders normally; INTERVENTION LC4 shows SUPPRESSED yet structurally present', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LC4')
    const first = result.control.experiment.outcome.first_escape_step ?? 16
    await seek(page, first)
    const control = page.getByTestId('trial-control')
    const treated = page.getByTestId('trial-intervention')
    const controlStep = result.control.experiment.timeline[first]
    if (!controlStep) throw new Error('no control step')
    // control: LC4 activity from the backend record, not marked
    await expect(control.getByTestId('lab-node-LC4_L')).toHaveAttribute('data-suppressed', 'false')
    await expect(control.getByTestId('lab-node-LC4_L')).toHaveAttribute('data-fired', String(controlStep.brain.group_peak_fired['LC4_L']))
    expect(result.control.simulated_firing_totals['LC4']).toBeGreaterThan(0)
    await expect(control.getByTestId('lab-suppressed-note')).toHaveCount(0)
    // intervention: same LC4 nodes exist (structure), marked SUPPRESSED, never fired
    await expect(treated.getByTestId('lab-brain-panel')).toHaveAttribute('data-suppressed', 'LC4')
    for (const key of ['LC4_L', 'LC4_R']) {
      const node = treated.getByTestId(`lab-node-${key}`)
      await expect(node).toHaveAttribute('data-suppressed', 'true')
      await expect(node).toHaveAttribute('data-fired', '0')
      await expect(node).toHaveAttribute('data-active', 'false')
      await expect(node).toHaveAttribute('data-neuron-count', await control.getByTestId(`lab-node-${key}`).getAttribute('data-neuron-count') ?? '')
      await expect(node.locator('.node__count')).toContainText('SUPPRESSED')
      await expect(treated.getByTestId(`lab-raster-${key}`)).toHaveAttribute('data-suppressed', 'true')
      await expect(treated.getByTestId(`lab-raster-${key}`)).toHaveAttribute('data-total', '0')
    }
    await expect(treated.getByTestId('lab-suppressed-note')).toContainText('STRUCTURE PRESENT')
    await expect(treated.getByTestId('lab-suppressed-note')).toContainText('SIMULATED FIRING SUPPRESSED')
    // LPLC2 is not targeted: not marked, rendered from the record
    const treatedStep = result.intervention.experiment.timeline[first]
    if (!treatedStep) throw new Error('no intervention step')
    await expect(treated.getByTestId('lab-node-LPLC2_L')).toHaveAttribute('data-suppressed', 'false')
    await expect(treated.getByTestId('lab-node-LPLC2_L')).toHaveAttribute('data-fired', String(treatedStep.brain.group_peak_fired['LPLC2_L']))
    expect(result.intervention.simulated_firing_totals['LC4']).toBe(0)
  })

  test('9-10. select SILENCE LPLC2: LPLC2 displays SUPPRESSED', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LPLC2')
    expect(result.intervention.resolved_targets.cell_types).toEqual(['LPLC2'])
    await pause(page)
    const treated = page.getByTestId('trial-intervention')
    await expect(treated.getByTestId('lab-brain-panel')).toHaveAttribute('data-suppressed', 'LPLC2')
    await expect(treated.getByTestId('lab-node-LPLC2_L')).toHaveAttribute('data-suppressed', 'true')
    await expect(treated.getByTestId('lab-node-LPLC2_R')).toHaveAttribute('data-suppressed', 'true')
    await expect(treated.getByTestId('lab-node-LC4_L')).toHaveAttribute('data-suppressed', 'false')
    await expect(treated.getByTestId('lab-node-LPLC2_L').locator('.node__count')).toContainText('SUPPRESSED')
    await expect(page.getByTestId('trial-intervention-label')).toHaveText('SILENCE LPLC2')
    expect(result.intervention.simulated_firing_totals['LPLC2']).toBe(0)
    await expect(page.getByTestId('diff-firing-LPLC2-intervention')).toContainText('0')
  })

  test('11-12. select LC4 + LPLC2: both groups display SUPPRESSED', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LC4_LPLC2')
    expect(result.intervention.resolved_targets.cell_types).toEqual(['LC4', 'LPLC2'])
    await pause(page)
    const treated = page.getByTestId('trial-intervention')
    await expect(treated.getByTestId('lab-brain-panel')).toHaveAttribute('data-suppressed', 'LC4,LPLC2')
    for (const key of ['LC4_L', 'LC4_R', 'LPLC2_L', 'LPLC2_R']) {
      await expect(treated.getByTestId(`lab-node-${key}`)).toHaveAttribute('data-suppressed', 'true')
      await expect(treated.getByTestId(`lab-node-${key}`)).toBeVisible()
    }
    await expect(treated.getByTestId('lab-node-DNp01_L')).toHaveAttribute('data-suppressed', 'false')
    await expect(page.getByTestId('trial-intervention-label')).toHaveText('SILENCE LC4 + LPLC2')
  })

  test('13. GF activity is backend-derived in both panels', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LC4_LPLC2')
    const first = result.control.experiment.outcome.first_escape_step ?? 16
    await seek(page, first)
    const c = result.control.experiment.timeline[first]
    const i = result.intervention.experiment.timeline[first]
    if (!c || !i) throw new Error('missing step')
    for (const key of ['DNp01_L', 'DNp01_R']) {
      await expect(page.getByTestId('trial-control').getByTestId(`lab-node-${key}`)).toHaveAttribute('data-fired', String(c.brain.group_peak_fired[key]))
      await expect(page.getByTestId('trial-intervention').getByTestId(`lab-node-${key}`)).toHaveAttribute('data-fired', String(i.brain.group_peak_fired[key]))
    }
    await expect(page.getByTestId('diff-firing-DNp01-control')).toHaveText(String(result.control.simulated_firing_totals['DNp01']))
    await expect(page.getByTestId('diff-firing-DNp01-intervention')).toContainText(String(result.intervention.simulated_firing_totals['DNp01']))
  })

  test('14. actions are backend-derived (never pre-filled)', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LPLC2')
    for (const step of [0, 10, result.control.experiment.outcome.first_escape_step ?? 16, result.comparison.synchronization.cursor_max]) {
      await seek(page, step)
      const c = result.control.experiment.timeline[step]
      const i = result.intervention.experiment.timeline[step]
      if (!c || !i) throw new Error('missing step')
      await expect(page.getByTestId('trial-control-action')).toHaveText(c.brain.action)
      await expect(page.getByTestId('trial-intervention-action')).toHaveText(i.brain.action)
    }
    const shown = await page.getByTestId('diff-intervention-first-escape').textContent()
    const expected = result.comparison.differences.intervention_first_escape_step
    expect(shown).toBe(expected === null ? 'NONE' : String(expected))
  })

  test('15. body movement is backend-derived in both trials', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LC4_LPLC2')
    const last = result.comparison.synchronization.cursor_max
    for (const step of [0, last]) {
      await seek(page, step)
      const c = result.control.experiment.timeline[step]
      const i = result.intervention.experiment.timeline[step]
      if (!c || !i) throw new Error('missing step')
      await expect(page.getByTestId('trial-control').getByTestId('lab-fly')).toHaveAttribute('data-x', String(c.body.position.x))
      await expect(page.getByTestId('trial-intervention').getByTestId('lab-fly')).toHaveAttribute('data-x', String(i.body.position.x))
      await expect(page.getByTestId('trial-control-body')).toHaveAttribute('data-x', String(c.body.position.x))
      await expect(page.getByTestId('trial-intervention-body')).toHaveAttribute('data-x', String(i.body.position.x))
    }
    await expect(page.getByTestId('diff-intervention-displacement')).toHaveText(result.intervention.experiment.outcome.displacement.toFixed(2))
  })

  test('16. replay step backward / forward moves both trials together', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LC4')
    await seek(page, 5)
    await page.getByTestId('ilab-step-forward').click()
    await expect(page.getByTestId('ilab-step')).toHaveAttribute('data-step', '6')
    await expect(page.getByTestId('trial-control')).toHaveAttribute('data-step', '6')
    await expect(page.getByTestId('trial-intervention')).toHaveAttribute('data-step', '6')
    await page.getByTestId('ilab-step-back').click()
    await page.getByTestId('ilab-step-back').click()
    await expect(page.getByTestId('ilab-step')).toHaveAttribute('data-step', '4')
    const c = result.control.experiment.timeline[4]
    const i = result.intervention.experiment.timeline[4]
    if (!c || !i) throw new Error('missing step')
    await expectTrialStep(page, 'control', c)
    await expectTrialStep(page, 'intervention', i)
  })

  test('17. reset rewinds both trials to step 0', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LPLC2')
    await seek(page, 18)
    await page.getByTestId('ilab-reset').click()
    await expect(page.getByTestId('ilab-step')).toHaveAttribute('data-step', '0')
    await expect(page.getByTestId('trial-control')).toHaveAttribute('data-step', '0')
    await expect(page.getByTestId('trial-intervention')).toHaveAttribute('data-step', '0')
    const c = result.control.experiment.timeline[0]
    if (!c) throw new Error('missing step')
    await expectTrialStep(page, 'control', c)
    await expect(page.getByTestId('ilab-status')).toHaveText('paused')
  })

  test('18. scientific disclaimers are visible', async ({ page }) => {
    await openLab(page)
    await expect(page.getByTestId('intervention-disclaimer')).toHaveText(
      'Neural interventions in this lab are computational manipulations of simulated neural dynamics. They do not reproduce a specific biological silencing, optogenetic, genetic, pharmacological, or lesion technique. Biological structural connectivity remains unchanged.',
    )
    await expect(page.getByTestId('intervention-embodiment-disclaimer')).toHaveText(
      'Structural connectivity is biological data. Neural activity is simulated. Virtual sensing, motor mapping, body dynamics, and world physics are computational interpretations.',
    )
  })

  test('19. biological context is separated from the computational result', async ({ page }) => {
    await openLab(page)
    const bio = page.getByTestId('context-biological')
    const comp = page.getByTestId('context-computational')
    await expect(bio).toContainText('BIOLOGICAL EVIDENCE')
    await expect(bio).toContainText('Ache')
    await expect(bio).toContainText('10.1016/j.cub.2019.01.079')
    await expect(bio).toContainText('LPLC2')
    await expect(comp).toContainText('CURRENT COMPUTATIONAL RESULT')
    await expect(comp).toContainText('No comparison yet')
    await runCompare(page, 'SILENCE_LPLC2')
    await expect(comp).toContainText('In the current computational model')
    await expect(comp).toContainText('not a biological interpretation')
    await expect(bio).not.toContainText('In the current computational model')
    await expect(page.getByTestId('comparison-summary')).not.toContainText('real flies')
  })

  test('20. the Virtual Threat Lab remains functional', async ({ page }) => {
    await page.goto('/?pace=30#threat-lab')
    await expect(page.getByTestId('lab-title')).toHaveText('VIRTUAL THREAT LAB')
    await expect(page.getByTestId('lab-node-LC4_L')).toHaveAttribute('data-suppressed', 'false')
    await expect(page.getByTestId('lab-suppressed-note')).toHaveCount(0)
    const responsePromise = page.waitForResponse((r) => r.url().includes('/embodiment/run'))
    await page.getByTestId('lab-run').click()
    expect((await responsePromise).status()).toBe(200)
    await expect(page.getByTestId('threat-lab')).toHaveAttribute('data-phase', 'ready')
    await expect(page.getByTestId('lab-fly')).toBeVisible()
    await page.getByTestId('tab-intervention').click()
    await expect(page.getByTestId('ilab-title')).toHaveText('NEURAL INTERVENTION LAB')
  })

  test('21. the Brain Inspector remains functional and shows the intervention state', async ({ page }) => {
    await openLab(page)
    const result = await runCompare(page, 'SILENCE_LPLC2')
    const target = result.intervention.resolved_targets.neuron_ids[0]
    if (!target) throw new Error('no target')
    await page.getByTestId('tab-inspector').click()
    await expect(page.getByTestId('circuit-graph')).toHaveAttribute('data-node-count', '286')
    await page.getByTestId('inspector-search').fill(target)
    await page.getByTestId('inspector-search-submit').click()
    await expect(page.getByTestId('neuron-inspector')).toHaveAttribute('data-neuron-id', target)
    await expect(page.getByTestId('intervention-state')).toContainText('COMPUTATIONAL FIRING SUPPRESSION')
    await expect(page.getByTestId('intervention-structure')).toHaveText('present')
    await expect(page.getByTestId('intervention-fired')).toHaveText('false')
    await page.getByTestId('inspector-search').fill('10010')
    await page.getByTestId('inspector-search-submit').click()
    await expect(page.getByTestId('neuron-inspector')).toHaveAttribute('data-neuron-id', '10010')
    await expect(page.getByTestId('intervention-state')).toContainText('none')
  })
})
