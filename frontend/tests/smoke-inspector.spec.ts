import { expect, test, type Page } from '@playwright/test'

import { RELEASE_VIEWPORT, shoot } from './helpers/screenshots'

/** MVP v0.1 screenshots A–E (live backend, no mocking). */

async function openInspector(page: Page, query = 'pace=30'): Promise<void> {
  await page.goto(`/?${query}#inspector`)
  await expect(page.getByTestId('circuit-graph')).toHaveAttribute('data-node-count', '286')
}

test.describe('MVP v0.1 screenshots', () => {
  test.use({ viewport: RELEASE_VIEWPORT })

  test('A. P5 main demo', async ({ page }) => {
    await page.goto('/?pace=30')
    await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
    await page.getByTestId('intensity-input').fill('0.5')
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 30_000 })
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await shoot(page, 'mvp-A-p5-main-demo')
  })

  test('B. Brain Inspector full graph', async ({ page }) => {
    await openInspector(page)
    await expect(page.locator('[data-testid^="node-"]')).toHaveCount(286)
    await shoot(page, 'mvp-B-inspector-full-graph')
  })

  test('C. Selected DNp01 neuron', async ({ page }) => {
    await openInspector(page)
    await page.getByTestId('inspector-search').fill('10010')
    await page.getByTestId('inspector-search-submit').click()
    await expect(page.getByTestId('neuron-inspector')).toHaveAttribute('data-neuron-id', '10010')
    await page.getByTestId('highlight-upstream').click()
    await expect(page.locator('[data-testid^="edge-hit-"][data-highlighted="true"]')).toHaveCount(155)
    await shoot(page, 'mvp-C-neuron-DNp01')
  })

  test('D. Selected LC4 → DNp01 edge', async ({ page }) => {
    await openInspector(page)
    await page.getByTestId('inspector-search').fill('10010')
    await page.getByTestId('inspector-search-submit').click()
    await page.getByTestId('edge-hit-12032-10010').dispatchEvent('click')
    await expect(page.getByTestId('edge-inspector')).toHaveAttribute('data-pre', '12032')
    await expect(page.getByTestId('edge-simulation-weight')).toBeVisible()
    await shoot(page, 'mvp-D-edge-LC4-DNp01')
  })

  test('E. Simulation activity replay', async ({ page }) => {
    await openInspector(page)
    await page.getByTestId('inspector-direction-center').click()
    await page.getByTestId('inspector-intensity').fill('1')
    await page.getByTestId('inspector-run-looming').click()
    await expect(page.getByTestId('replay-step-label')).toHaveText('step 0 / 30', { timeout: 30_000 })
    await page.getByTestId('inspector-search').fill('10010')
    await page.getByTestId('inspector-search-submit').click()
    await page.getByTestId('zoom-reset').click()
    await page.getByTestId('replay-step').click()
    await page.getByTestId('replay-step').click()
    await expect(page.getByTestId('replay-step-label')).toHaveText('step 2 / 30')
    await expect(page.getByTestId('node-10010')).toHaveAttribute('data-sim-state', 'fired')
    await shoot(page, 'mvp-E-activity-replay')
  })
})
