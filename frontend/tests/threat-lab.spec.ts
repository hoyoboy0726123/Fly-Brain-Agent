import { expect, test, type Page } from '@playwright/test'

/**
 * P7.1 Virtual Threat Lab (live backend, no mocking on the happy paths).
 * The UI replays what `POST /embodiment/run` recorded; every assertion below compares
 * the rendered state with the backend payload captured from the same request.
 */

interface Step {
  step_index: number
  simulation_time: number
  world: { objects: { position: { x: number; y: number; z: number }; size: number }[] }
  body: { position: { x: number; y: number; z: number }; grounded: boolean }
  sensor: { distance: number | null; intensity: number; direction: string; angular_size_rad: number | null }
  brain: { action: string; firing_events: number; group_peak_fired: Record<string, number>; group_fired_counts: Record<string, number[]> }
  motor: { command: string }
}

interface RunResult {
  timeline: Step[]
  outcome: { first_escape_step: number | null; escape_steps: number[]; events: { kind: string; step_index: number }[] }
}

async function openLab(page: Page, query = 'pace=30'): Promise<void> {
  await page.goto(`/?${query}#threat-lab`)
  await expect(page.getByTestId('threat-lab')).toBeVisible()
  await expect(page.getByTestId('lab-node-LC4_L')).toBeVisible()
}

/** Click RUN and capture the backend payload the UI is about to replay. */
async function runAndCapture(page: Page): Promise<RunResult> {
  const responsePromise = page.waitForResponse((r) => r.url().includes('/embodiment/run') && r.request().method() === 'POST')
  await page.getByTestId('lab-run').click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const result = (await response.json()) as RunResult
  await expect(page.getByTestId('threat-lab')).toHaveAttribute('data-phase', 'ready')
  return result
}

/** PAUSE is a no-op once the replay has reached its last step (the button is then disabled). */
async function pause(page: Page): Promise<void> {
  await page.getByTestId('lab-pause').click({ force: true })
  await expect(page.getByTestId('lab-status')).toHaveText('paused')
}

async function pauseAndSeek(page: Page, step: number): Promise<void> {
  await pause(page)
  await page.getByTestId('lab-slider').fill(String(step))
  await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', String(step))
}

function expectStepRendered(page: Page, step: Step) {
  return Promise.all([
    expect(page.getByTestId('lab-fly')).toHaveAttribute('data-x', String(step.body.position.x)),
    expect(page.getByTestId('lab-fly')).toHaveAttribute('data-z', String(step.body.position.z)),
    expect(page.getByTestId('lab-fly')).toHaveAttribute('data-grounded', String(step.body.grounded)),
    expect(page.locator('[data-testid^="lab-object-"]').first()).toHaveAttribute('data-x', String(step.world.objects[0]?.position.x)),
    expect(page.getByTestId('lab-distance')).toHaveAttribute('data-value', String(step.sensor.distance)),
    expect(page.getByTestId('lab-looming')).toHaveAttribute('data-value', String(step.sensor.intensity)),
    expect(page.getByTestId('lab-action')).toHaveText(step.brain.action),
    expect(page.getByTestId('lab-motor-command')).toContainText(step.motor.command),
    expect(page.getByTestId('lab-brain-fired')).toHaveText(String(step.brain.firing_events)),
    expect(page.getByTestId('lab-node-DNp01_L')).toHaveAttribute('data-fired', String(step.brain.group_peak_fired['DNp01_L'])),
    expect(page.getByTestId('lab-node-LC4_L')).toHaveAttribute('data-fired', String(step.brain.group_peak_fired['LC4_L'])),
    expect(page.getByTestId('lab-brain-step')).toContainText(`loop step ${step.step_index}`),
  ])
}

test.describe('Virtual Threat Lab', () => {
  test('1. loads with the loop story, arena, brain, world/body panels and boundaries', async ({ page }) => {
    await openLab(page)
    await expect(page.getByTestId('lab-title')).toHaveText('VIRTUAL THREAT LAB')
    await expect(page.getByTestId('loop-story')).toBeVisible()
    for (const stage of ['world', 'sensor', 'brain', 'motor', 'body']) {
      await expect(page.getByTestId(`loop-stage-${stage}`)).toBeVisible()
    }
    await expect(page.getByTestId('lab-arena')).toBeVisible()
    await expect(page.getByTestId('lab-brain-panel')).toBeVisible()
    await expect(page.getByTestId('lab-world-body-panel')).toBeVisible()
    await expect(page.getByTestId('lab-boundaries')).toBeVisible()
    await expect(page.getByTestId('lab-brain-label')).toHaveText('SIMULATED NEURAL ACTIVITY')
    await expect(page.getByTestId('lab-label-structural_connectivity')).toContainText('BIOLOGICAL DATA')
    await expect(page.getByTestId('lab-label-neural_activity')).toContainText('SIMULATED')
    await expect(page.getByTestId('lab-label-virtual_sensing')).toContainText('COMPUTATIONAL SENSOR INPUT')
    await expect(page.getByTestId('lab-label-world_physics')).toContainText('COMPUTATIONAL')
    await expect(page.getByTestId('lab-label-body')).toContainText('SIMPLIFIED COMPUTATIONAL BODY')
    await expect(page.getByTestId('lab-disclaimer')).toHaveText(
      'Structural connectivity is biological data. Neural activity is simulated. Virtual sensing, motor mapping, body dynamics, and world physics are computational interpretations.',
    )
    await expect(page.getByTestId('lab-circuit-hash')).toContainText('db7c46e6a1653')
    await expect(page.getByTestId('tab-threat-lab')).toHaveAttribute('aria-pressed', 'true')
  })

  test('2. before a run: WAITING FOR EXPERIMENT, no fake activity, no fly, no object', async ({ page }) => {
    await openLab(page)
    await expect(page.getByTestId('lab-overlay-text')).toHaveText('WAITING FOR EXPERIMENT')
    await expect(page.getByTestId('lab-status')).toHaveText('WAITING FOR EXPERIMENT')
    await expect(page.getByTestId('lab-action')).toHaveText('WAITING FOR EXPERIMENT')
    await expect(page.getByTestId('lab-fly')).toHaveCount(0)
    await expect(page.locator('[data-testid^="lab-object-"]')).toHaveCount(0)
    await expect(page.locator('[data-testid^="lab-node-"][data-active="true"]')).toHaveCount(0)
    await expect(page.locator('.lab-raster__bar--on')).toHaveCount(0)
    await expect(page.getByTestId('lab-node-LC4_L')).toHaveAttribute('data-fired', '0')
    await expect(page.getByTestId('loop-story')).toHaveAttribute('data-current', 'none')
    await expect(page.getByTestId('lab-slider')).toBeDisabled()
    await expect(page.getByTestId('lab-play')).toBeDisabled()
    await expect(page.getByTestId('lab-step')).toHaveText('step — / —')
  })

  test('3. RUN asks the backend and replays its timeline', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    expect(result.timeline.length).toBe(30)
    await expect(page.getByTestId('lab-overlay')).toHaveCount(0)
    await expect(page.getByTestId('lab-fly')).toBeVisible()
    await expect(page.getByTestId('lab-experiment-id')).not.toHaveText('')
    await expect(page.getByTestId('lab-slider')).toHaveAttribute('max', '29')
    await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', '29', { timeout: 20_000 })
    await expect(page.getByTestId('lab-status')).toHaveText('paused')
    const last = result.timeline[29]
    if (!last) throw new Error('timeline too short')
    await expectStepRendered(page, last)
  })

  test('4. the object approaches: recorded distance shrinks step by step', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    const first = result.outcome.first_escape_step ?? 10
    await pauseAndSeek(page, 0)
    const object = page.locator('[data-testid^="lab-object-"]').first()
    await expect(object).toHaveAttribute('data-x', '20')
    await expect(page.getByTestId('lab-distance')).toHaveText('20.00 units')
    for (const step of [3, Math.floor(first / 2), first]) {
      await pauseAndSeek(page, step)
      const record = result.timeline[step]
      if (!record) throw new Error(`no step ${step}`)
      await expect(object).toHaveAttribute('data-x', String(record.world.objects[0]?.position.x))
      await expect(page.getByTestId('lab-distance')).toHaveAttribute('data-value', String(record.sensor.distance))
    }
    const distances = result.timeline.slice(0, first + 1).map((s) => s.sensor.distance ?? Infinity)
    for (let i = 1; i < distances.length; i += 1) expect(distances[i]).toBeLessThan(distances[i - 1] ?? Infinity)
  })

  test('5. looming input, eye inset and brain activity follow the backend record', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    const first = result.outcome.first_escape_step
    expect(first).not.toBeNull()
    const quiet = result.timeline[0]
    const loud = result.timeline[first ?? 0]
    if (!quiet || !loud) throw new Error('missing steps')
    await pauseAndSeek(page, 0)
    await expect(page.getByTestId('lab-looming')).toHaveAttribute('data-value', String(quiet.sensor.intensity))
    await expect(page.getByTestId('lab-eye')).toHaveAttribute('data-angular-size', String(quiet.sensor.angular_size_rad))
    await expect(page.getByTestId('lab-brain-fired')).toHaveText('0')
    await expect(page.locator('[data-testid^="lab-node-"][data-active="true"]')).toHaveCount(0)
    await expect(page.getByTestId('loop-stage-brain')).toHaveAttribute('data-state', 'quiet')
    await pauseAndSeek(page, first ?? 0)
    await expect(page.getByTestId('lab-looming')).toHaveAttribute('data-value', String(loud.sensor.intensity))
    expect(loud.sensor.intensity).toBeGreaterThan(quiet.sensor.intensity)
    await expect(page.getByTestId('lab-eye')).toHaveAttribute('data-angular-size', String(loud.sensor.angular_size_rad))
    await expect(page.getByTestId('lab-brain-fired')).toHaveText(String(loud.brain.firing_events))
    for (const key of Object.keys(loud.brain.group_peak_fired)) {
      await expect(page.getByTestId(`lab-node-${key}`)).toHaveAttribute('data-fired', String(loud.brain.group_peak_fired[key]))
      await expect(page.getByTestId(`lab-raster-${key}`)).toHaveAttribute('data-total', String((loud.brain.group_fired_counts[key] ?? []).reduce((a, b) => a + b, 0)))
    }
    await expect(page.getByTestId('lab-node-DNp01_L')).toHaveAttribute('data-active', 'true')
    await expect(page.getByTestId('loop-stage-brain')).toHaveAttribute('data-state', 'active')
  })

  test('6. ESCAPE event: marker on the timeline, action, motor and story highlight', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    const first = result.outcome.first_escape_step
    expect(first).not.toBeNull()
    await pause(page)
    const marker = page.getByTestId(`lab-marker-first_escape-${first}`)
    await expect(marker).toBeVisible()
    await expect(marker).toContainText('ESCAPE')
    await expect(page.locator('[data-testid^="lab-marker-"]')).toHaveCount(result.outcome.events.length)
    await marker.click()
    await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', String(first))
    await expect(page.getByTestId('lab-action')).toHaveText('ESCAPE')
    await expect(page.getByTestId('lab-motor-command')).toContainText('ESCAPE')
    await expect(page.getByTestId('loop-stage-motor')).toHaveAttribute('data-state', 'active')
    await expect(page.getByTestId('loop-story')).toHaveAttribute('data-current', 'motor')
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-x', '0')
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-grounded', 'true')
  })

  test('7. the fly moves only as the recorded BodyState moves (after ESCAPE)', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    const first = result.outcome.first_escape_step ?? 0
    for (const step of [0, Math.max(0, first - 1), first]) {
      await pauseAndSeek(page, step)
      await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-x', '0')
      await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-z', '0')
      await expect(page.getByTestId('loop-stage-body')).toHaveAttribute('data-state', 'quiet')
    }
    const after = result.timeline[first + 1]
    if (!after) throw new Error('no post-escape step')
    expect(after.body.position.x).toBeGreaterThan(0)
    await pauseAndSeek(page, first + 1)
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-x', String(after.body.position.x))
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-z', String(after.body.position.z))
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-grounded', 'false')
    await expect(page.getByTestId('lab-body-position')).toHaveAttribute('data-x', String(after.body.position.x))
    await expect(page.getByTestId('loop-stage-body')).toHaveAttribute('data-state', 'active')
    await expect(page.getByTestId('loop-story')).toHaveAttribute('data-current', 'body')
    const last = result.timeline[result.timeline.length - 1]
    if (!last) throw new Error('empty timeline')
    await pauseAndSeek(page, result.timeline.length - 1)
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-x', String(last.body.position.x))
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-grounded', String(last.body.grounded))
  })

  test('8. PAUSE freezes the replay and PLAY resumes it', async ({ page }) => {
    await openLab(page, 'pace=200')
    await runAndCapture(page)
    await expect(page.getByTestId('lab-status')).toHaveText('playing')
    await page.getByTestId('lab-pause').click()
    await expect(page.getByTestId('lab-status')).toHaveText('paused')
    const frozen = await page.getByTestId('lab-step').getAttribute('data-step')
    await page.waitForTimeout(700)
    await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', frozen ?? '')
    await page.getByTestId('lab-play').click()
    await expect(page.getByTestId('lab-status')).toHaveText('playing')
    await expect(page.getByTestId('lab-step')).not.toHaveAttribute('data-step', frozen ?? '')
  })

  test('9. STEP FORWARD / STEP BACK move exactly one recorded step', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    await pauseAndSeek(page, 5)
    await page.getByTestId('lab-step-forward').click()
    await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', '6')
    const six = result.timeline[6]
    if (!six) throw new Error('no step 6')
    await expectStepRendered(page, six)
    await page.getByTestId('lab-step-back').click()
    await page.getByTestId('lab-step-back').click()
    await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', '4')
    const four = result.timeline[4]
    if (!four) throw new Error('no step 4')
    await expectStepRendered(page, four)
    await pauseAndSeek(page, 0)
    await expect(page.getByTestId('lab-step-back')).toBeDisabled()
    await pauseAndSeek(page, 29)
    await expect(page.getByTestId('lab-step-forward')).toBeDisabled()
  })

  test('10. slider selects a step and every panel shows that step', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    for (const step of [2, 17, 25]) {
      await pauseAndSeek(page, step)
      const record = result.timeline[step]
      if (!record) throw new Error(`no step ${step}`)
      await expectStepRendered(page, record)
      await expect(page.getByTestId('lab-world-time')).toContainText(record.simulation_time.toFixed(2))
      await expect(page.getByTestId('lab-body-grounded')).toHaveText(String(record.body.grounded))
      await expect(page.getByTestId('lab-sensor-intensity')).toHaveText(record.sensor.intensity.toFixed(3))
    }
  })

  test('11. RESET rewinds to step 0 and pauses', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    await pauseAndSeek(page, 20)
    await page.getByTestId('lab-reset').click()
    await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', '0')
    await expect(page.getByTestId('lab-status')).toHaveText('paused')
    const zero = result.timeline[0]
    if (!zero) throw new Error('no step 0')
    await expectStepRendered(page, zero)
    await expect(page.getByTestId('lab-experiment-id')).not.toHaveText('')
  })

  test('12. a failed run shows NO RESULT and never synthesises a timeline', async ({ page }) => {
    await page.route('**/api/embodiment/run', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: { error: 'simulation_error', message: 'injected failure' } }) }),
    )
    await openLab(page)
    await page.getByTestId('lab-run').click()
    await expect(page.getByTestId('threat-lab')).toHaveAttribute('data-phase', 'error')
    await expect(page.getByTestId('lab-error')).toContainText('NO RESULT')
    await expect(page.getByTestId('lab-error')).toContainText('simulation_error')
    await expect(page.getByTestId('lab-overlay-text')).toHaveText('NO RESULT')
    await expect(page.getByTestId('lab-action')).toHaveText('NO RESULT')
    await expect(page.getByTestId('lab-status')).toHaveText('NO RESULT')
    await expect(page.getByTestId('lab-fly')).toHaveCount(0)
    await expect(page.locator('[data-testid^="lab-marker-"]')).toHaveCount(0)
    await expect(page.getByTestId('lab-slider')).toBeDisabled()
    await expect(page.locator('[data-testid^="lab-node-"][data-active="true"]')).toHaveCount(0)
    await expect(page.getByTestId('lab-step')).toHaveText('step — / —')
  })

  test('13. azimuth preset changes the recorded direction, not the brain', async ({ page }) => {
    await openLab(page)
    await page.getByTestId('lab-azimuth-left').click()
    await expect(page.getByTestId('lab-azimuth')).toHaveValue('60')
    await page.getByTestId('lab-start-distance').fill('8')
    await page.getByTestId('lab-steps').fill('6')
    const result = await runAndCapture(page)
    expect(result.timeline.length).toBe(6)
    await pauseAndSeek(page, 2)
    await expect(page.getByTestId('lab-looming')).toHaveAttribute('data-direction', 'left')
    await expect(page.locator('[data-testid^="lab-object-"]').first()).toHaveAttribute('data-y', String(result.timeline[2]?.world.objects[0]?.position.y))
  })

  test('14. out-of-range parameters are rejected client-side and by the backend', async ({ page }) => {
    await openLab(page)
    await page.getByTestId('lab-steps').fill('999')
    await expect(page.getByTestId('lab-params-error')).toBeVisible()
    await expect(page.getByTestId('lab-run')).toBeDisabled()
    const response = await page.request.post('/api/embodiment/run', { data: { max_steps: 999 } })
    expect(response.status()).toBe(422)
    const tuning = await page.request.post('/api/embodiment/run', { data: { neural_gain: 2 } })
    expect(tuning.status()).toBe(422)
  })

  test('15. the same seed and world replay identically', async ({ page }) => {
    await openLab(page)
    const a = await runAndCapture(page)
    await pause(page)
    const b = await runAndCapture(page)
    expect(b.timeline).toEqual(a.timeline)
  })

  test('16. hero button and tab open the lab; hash routing works', async ({ page }) => {
    await page.goto('/?pace=30')
    await page.getByTestId('cta-threat-lab').click()
    await expect(page.getByTestId('threat-lab')).toBeVisible()
    expect(page.url()).toContain('#threat-lab')
    await page.getByTestId('tab-demo').click()
    await expect(page.getByTestId('hero')).toBeVisible()
    await page.getByTestId('tab-threat-lab').click()
    await expect(page.getByTestId('lab-title')).toHaveText('VIRTUAL THREAT LAB')
  })

  test('17. the escape demo (P5) still works next to the lab', async ({ page }) => {
    await page.goto('/?pace=30')
    await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
    await page.getByTestId('preset-medium').click()
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 30_000 })
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await page.getByTestId('tab-threat-lab').click()
    await expect(page.getByTestId('lab-overlay-text')).toHaveText('WAITING FOR EXPERIMENT')
  })

  test('18. the brain inspector (P6) still works next to the lab', async ({ page }) => {
    await page.goto('/?pace=30#inspector')
    await expect(page.getByTestId('circuit-graph')).toHaveAttribute('data-node-count', '286')
    await page.getByTestId('tab-threat-lab').click()
    await expect(page.getByTestId('lab-title')).toHaveText('VIRTUAL THREAT LAB')
    await page.getByTestId('tab-inspector').click()
    await expect(page.getByTestId('circuit-graph')).toHaveAttribute('data-node-count', '286')
    await expect(page.getByTestId('provenance-panel')).toBeVisible()
  })

  test('19. brain nodes keep their biological identity while activity is labelled simulated', async ({ page }) => {
    await openLab(page)
    const result = await runAndCapture(page)
    const first = result.outcome.first_escape_step ?? 0
    for (const key of ['LC4_L', 'LC4_R', 'LPLC2_L', 'LPLC2_R', 'DNp01_L', 'DNp01_R']) {
      await expect(page.getByTestId(`lab-node-${key}`)).toBeVisible()
    }
    await expect(page.getByTestId('lab-edge-LC4_L-DNp01_L')).toHaveCount(1)
    await expect(page.getByTestId('lab-edge-LC4_L-DNp01_L')).toHaveAttribute('data-active', 'false')
    await expect(page.getByTestId('lab-brain-label')).toHaveText('SIMULATED NEURAL ACTIVITY')
    await pauseAndSeek(page, first)
    await expect(page.getByTestId('lab-edge-LC4_L-DNp01_L')).toHaveAttribute('data-active', 'true')
    await expect(page.getByTestId('lab-brain-action')).toHaveText('ESCAPE')
    await expect(page.getByTestId('lab-raster')).toHaveAttribute('data-neural-steps', '30')
  })
})
