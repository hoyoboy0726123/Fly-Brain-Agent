import { expect, test, type Page } from '@playwright/test'

/**
 * P5 interactive demo. Happy paths run against the live backend (no mocking); only the
 * error states intercept requests. `?pace=` shortens the per-step replay for speed.
 */

const DISCLAIMER =
  'STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED. ' +
  'STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS.'

async function open(page: Page, query = 'pace=5'): Promise<void> {
  await page.goto(`/?${query}`)
  await expect(page.getByTestId('backend-health-status')).toHaveText('ok')
  await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
}

async function setIntensity(page: Page, value: number): Promise<void> {
  await page.getByTestId('intensity-input').fill(String(value))
  await expect(page.getByTestId('intensity-value')).toHaveText(value.toFixed(2))
}

async function runAndWait(page: Page): Promise<void> {
  await page.getByTestId('trigger-looming').click()
  await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 20_000 })
}

test.describe('P5 escape demo', () => {
  test('page loads with title, subtitle and the three scientific labels', async ({ page }) => {
    await page.goto('/?pace=5')
    await expect(page).toHaveTitle(/FlyBrain Agent/)
    await expect(page.getByRole('heading', { level: 1, name: 'FlyBrain Agent' })).toBeVisible()
    await expect(page.getByTestId('subtitle')).toHaveText('Connectome-grounded simulation using MaleCNS v1.0')
    const labels = page.getByTestId('scientific-labels').getByRole('listitem')
    await expect(labels).toHaveText([
      'Structural connectivity: biological data',
      'Neural activity: simulated',
      'Behavior decoding: computational interpretation',
    ])
    await expect(page.getByTestId('environment-panel')).toBeVisible()
    await expect(page.getByTestId('brain-panel')).toBeVisible()
    await expect(page.getByTestId('action-panel')).toBeVisible()
  })

  test('backend is connected and the circuit configuration is loaded', async ({ page }) => {
    await open(page)
    await expect(page.getByTestId('backend-health-phase')).toHaveText('P5')
    for (const key of ['LC4_L', 'LC4_R', 'LPLC2_L', 'LPLC2_R', 'DNp01_L', 'DNp01_R']) {
      await expect(page.getByTestId(`brain-node-${key}`)).toBeVisible()
    }
    await expect(page.getByTestId('brain-node-LC4_L')).toContainText('71 neurons')
    await expect(page.getByTestId('brain-edge-LC4_L-DNp01_L')).toBeAttached()
    await expect(page.getByTestId('brain-edge-LPLC2_R-DNp01_R')).toBeAttached()
    await expect(page.getByTestId('config-error')).toHaveCount(0)
  })

  test('user can change the looming direction', async ({ page }) => {
    await open(page)
    await expect(page.getByTestId('direction-center')).toHaveAttribute('aria-pressed', 'true')
    await page.getByTestId('direction-left').click()
    await expect(page.getByTestId('direction-left')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('direction-center')).toHaveAttribute('aria-pressed', 'false')
    await page.getByTestId('direction-right').click()
    await expect(page.getByTestId('direction-right')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('direction-left')).toHaveAttribute('aria-pressed', 'false')
  })

  test('user can change the intensity with the slider and the number field', async ({ page }) => {
    await open(page)
    await expect(page.getByTestId('intensity-value')).toHaveText('0.50')
    await page.getByTestId('intensity-slider').fill('0.2')
    await expect(page.getByTestId('intensity-value')).toHaveText('0.20')
    await setIntensity(page, 1)
    await expect(page.getByTestId('intensity-slider')).toHaveValue('1')
  })

  test('invalid intensity is rejected before any request is sent', async ({ page }) => {
    await open(page)
    await page.getByTestId('intensity-input').fill('1.5')
    await expect(page.getByTestId('intensity-error')).toBeVisible()
    await expect(page.getByTestId('trigger-looming')).toBeDisabled()
    await page.getByTestId('intensity-input').fill('0.5')
    await expect(page.getByTestId('intensity-error')).toHaveCount(0)
    await expect(page.getByTestId('trigger-looming')).toBeEnabled()
  })

  test('triggering looming runs the backend experiment and replays its timeline', async ({ page }) => {
    await open(page)
    await runAndWait(page)
    await expect(page.getByTestId('brain-step')).toHaveText('step 30 / 30')
    await expect(page.getByTestId('transport')).toContainText('websocket')
    await expect(page.getByTestId('experiment-id')).not.toHaveText('—')
    await expect(page.getByTestId('result-circuit-hash')).toHaveText(/^db7c46e6a165…$/)
    await expect(page.getByTestId('action-value')).toHaveText(/^(NO ACTION|ESCAPE)$/)
    await expect(page.getByTestId('timeline').locator('[data-tag="t0_stimulus"]')).toHaveAttribute('data-reached', 'true')
  })

  test('CENTER 0.2 decodes NO_ACTION and the fly stays', async ({ page }) => {
    await open(page)
    await page.getByTestId('direction-center').click()
    await setIntensity(page, 0.2)
    await runAndWait(page)
    await expect(page.getByTestId('action-value')).toHaveText('NO ACTION')
    await expect(page.getByTestId('action-value')).toHaveAttribute('data-action', 'NO_ACTION')
    await expect(page.getByTestId('gf-activity')).toHaveText('None')
    await expect(page.getByTestId('virtual-fly')).toHaveAttribute('data-escaped', 'false')
    await expect(page.getByTestId('timeline').locator('[data-tag="t3_output_activation"]')).toHaveAttribute('data-reached', 'false')
  })

  test('CENTER 0.5 decodes ESCAPE with both giant fibers and the fly jumps away', async ({ page }) => {
    await open(page)
    await page.getByTestId('direction-center').click()
    await setIntensity(page, 0.5)
    await runAndWait(page)
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await expect(page.getByTestId('action-value')).toHaveAttribute('data-action', 'ESCAPE')
    await expect(page.getByTestId('gf-activity')).toHaveText('Both')
    await expect(page.getByTestId('virtual-fly')).toHaveAttribute('data-escaped', 'true')
    await expect(page.getByTestId('arena-escape-banner')).toBeVisible()
    const t3 = page.getByTestId('timeline').locator('[data-tag="t3_output_activation"]')
    await expect(t3).toHaveAttribute('data-reached', 'true')
    await expect(t3).toContainText('step 4')
  })

  test('LEFT 1.0 decodes ESCAPE; GF side is metadata only and ESCAPE_LEFT never appears', async ({ page }) => {
    await open(page)
    await page.getByTestId('direction-left').click()
    await setIntensity(page, 1)
    await runAndWait(page)
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await expect(page.getByTestId('gf-activity')).toHaveText('Left')
    const text = await page.locator('body').innerText()
    expect(text).not.toMatch(/ESCAPE_LEFT|ESCAPE_RIGHT|ESCAPE LEFT|ESCAPE RIGHT/)
  })

  test('brain animation follows the backend steps (sensory first, then giant fiber)', async ({ page }) => {
    // A slow replay (3 s per step) so each step is observed by the polling assertions.
    await open(page, 'pace=3000')
    await page.getByTestId('direction-center').click()
    await setIntensity(page, 1)
    await page.getByTestId('trigger-looming').click()
    // backend timeline for center/1.0: sensory groups fire at step 1, DNp01 at step 2
    await expect(page.getByTestId('brain-step')).toHaveText('step 1 / 30', { timeout: 15_000 })
    await expect(page.getByTestId('brain-node-LC4_L')).toHaveAttribute('data-active', 'true')
    await expect(page.getByTestId('brain-node-LPLC2_R')).toHaveAttribute('data-active', 'true')
    await expect(page.getByTestId('brain-node-DNp01_L')).toHaveAttribute('data-active', 'false')
    await expect(page.getByTestId('arena')).toHaveAttribute('data-loom-state', 'active')
    await expect(page.getByTestId('action-value')).not.toHaveText('ESCAPE')
    await expect(page.getByTestId('brain-step')).toHaveText('step 2 / 30')
    await expect(page.getByTestId('brain-node-DNp01_L')).toHaveAttribute('data-active', 'true')
    await expect(page.getByTestId('brain-node-DNp01_R')).toHaveAttribute('data-active', 'true')
  })

  test('reset clears the result and animation', async ({ page }) => {
    await open(page)
    await runAndWait(page)
    await page.getByTestId('reset').click()
    await expect(page.getByTestId('demo-status')).toHaveText('idle')
    await expect(page.getByTestId('action-value')).toHaveText('—')
    await expect(page.getByTestId('gf-activity')).toHaveText('—')
    await expect(page.getByTestId('brain-step')).toHaveText('no run yet')
    await expect(page.getByTestId('virtual-fly')).toHaveAttribute('data-escaped', 'false')
    await expect(page.getByTestId('arena')).toHaveAttribute('data-loom-state', 'idle')
  })

  test('backend unavailable: error is shown and no ESCAPE is displayed', async ({ page }) => {
    // WebSocket routes must be installed before navigation (Playwright requirement).
    await page.routeWebSocket('**/api/ws/escape', (ws) => ws.close({ code: 1011, reason: 'test: backend down' }))
    await page.route('**/api/escape/run', (route) => route.abort('connectionrefused'))
    await open(page)
    await page.getByTestId('trigger-looming').click()
    const error = page.getByTestId('demo-error')
    await expect(error).toBeVisible({ timeout: 20_000 })
    await expect(error).toHaveAttribute('data-error-code', 'backend_unavailable')
    await expect(error).toContainText('Backend unavailable')
    await expect(page.getByTestId('demo-status')).toHaveText('error')
    await expect(page.getByTestId('action-value')).toHaveText('NO RESULT')
    await expect(page.getByTestId('virtual-fly')).toHaveAttribute('data-escaped', 'false')
  })

  test('backend error contract is surfaced: simulation error and circuit mismatch', async ({ page }) => {
    await page.routeWebSocket('**/api/ws/escape', (ws) => ws.close({ code: 1011, reason: 'test' }))
    let detail = { error: 'simulation_error', message: 'membrane potential became NaN at step 3' }
    let status = 500
    await page.route('**/api/escape/run', (route) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify({ detail }) }),
    )
    await open(page)
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-error')).toHaveAttribute('data-error-code', 'simulation_error', { timeout: 20_000 })
    await expect(page.getByTestId('demo-error')).toContainText('NaN')
    await expect(page.getByTestId('action-value')).toHaveText('NO RESULT')

    detail = { error: 'circuit_mismatch', message: 'circuit hash 0000… differs from the configured expected_circuit_hash' }
    status = 503
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-error')).toHaveAttribute('data-error-code', 'circuit_mismatch', { timeout: 20_000 })
    await expect(page.getByTestId('demo-error')).toContainText('Circuit mismatch')
  })

  test('backend unavailable at load: config banner, empty circuit, labels still visible', async ({ page }) => {
    await page.route('**/api/escape/config', (route) => route.abort('connectionrefused'))
    await page.goto('/?pace=5')
    await expect(page.getByTestId('config-error')).toBeVisible()
    await expect(page.getByTestId('brain-empty')).toBeVisible()
    await expect(page.getByTestId('disclaimer')).toHaveText(DISCLAIMER)
    await expect(page.getByTestId('simulated-activity-label')).toHaveText('SIMULATED ACTIVITY')
    await page.getByTestId('how-it-works').locator('summary').click()
    await expect(page.getByTestId('biological-status')).toContainText('unknown')
  })

  test('REST fallback transport produces the same decoded action', async ({ page }) => {
    await open(page, 'pace=5&transport=rest')
    await setIntensity(page, 0.5)
    await runAndWait(page)
    await expect(page.getByTestId('transport')).toHaveText('rest')
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await expect(page.getByTestId('gf-activity')).toHaveText('Both')
  })

  test('scientific disclaimer, simulated-activity label and circuit status are visible', async ({ page }) => {
    await open(page)
    await expect(page.getByTestId('disclaimer')).toHaveText(DISCLAIMER)
    await expect(page.getByTestId('simulated-activity-label')).toHaveText('SIMULATED ACTIVITY')
    const how = page.getByTestId('how-it-works')
    await how.locator('summary').click()
    await expect(page.getByTestId('biological-status')).toHaveText(/BIOLOGICAL CIRCUIT STATUS:\s*PARTIALLY SUPPORTED/)
    await expect(how).toContainText('BIOLOGICAL STRUCTURE')
    await expect(how).toContainText('COMPUTATIONAL DYNAMICS')
    await expect(how).toContainText('APPLICATION DECODING')
    await expect(how).toContainText('docs/circuits/escape_v1.md')
  })
})
