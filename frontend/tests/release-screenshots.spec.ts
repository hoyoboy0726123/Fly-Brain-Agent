import { expect, test, type Page } from '@playwright/test'

import { RELEASE_VIEWPORT, shoot } from './helpers/screenshots'

/** Release screenshots (P6.1): consistent 1440×900 viewport, live backend, no mocking. */

async function ready(page: Page, query = 'pace=30'): Promise<void> {
  await page.goto(`/?${query}`)
  await expect(page.getByTestId('backend-health-status')).toHaveText('ok')
  await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
}

test.describe('release screenshots', () => {
  test.use({ viewport: RELEASE_VIEWPORT })

  test('release-main: landing', async ({ page }) => {
    await ready(page)
    await shoot(page, 'release-main')
  })

  test('release-looming: object approaching, sensory neurons active', async ({ page }) => {
    await ready(page, 'pace=3000')
    await page.getByTestId('preset-medium').click()
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('brain-step')).toHaveText('step 3 / 30', { timeout: 20_000 })
    await expect(page.getByTestId('brain-node-LC4_L')).toHaveAttribute('data-active', 'true')
    await page.evaluate(() => document.getElementById('demo-panels')?.scrollIntoView({ block: 'start' }))
    await shoot(page, 'release-looming', { scroll: 'keep' })
  })

  test('release-escape: decoded ESCAPE', async ({ page }) => {
    await ready(page)
    await page.getByTestId('cta-run-demo').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 30_000 })
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await page.evaluate(() => document.getElementById('demo-panels')?.scrollIntoView({ block: 'start' }))
    await shoot(page, 'release-escape', { scroll: 'keep' })
  })

  test('release-inspector: DNp01 selected with upstream highlighted', async ({ page }) => {
    await page.goto('/?pace=30#inspector')
    await expect(page.getByTestId('circuit-graph')).toHaveAttribute('data-node-count', '286')
    await page.getByTestId('inspector-search').fill('10010')
    await page.getByTestId('inspector-search-submit').click()
    await expect(page.getByTestId('neuron-inspector')).toHaveAttribute('data-neuron-id', '10010')
    await page.getByTestId('highlight-upstream').click()
    await expect(page.locator('[data-testid^="edge-hit-"][data-highlighted="true"]')).toHaveCount(155)
    await shoot(page, 'release-inspector')
  })

  test('release-provenance: provenance panel', async ({ page }) => {
    await page.goto('/?pace=30#inspector')
    await expect(page.getByTestId('circuit-graph')).toHaveAttribute('data-node-count', '286')
    await expect(page.getByTestId('prov-status')).toContainText('PARTIALLY SUPPORTED')
    await page.getByTestId('provenance-panel').scrollIntoViewIfNeeded()
    await page.evaluate(() => {
      const panel = document.querySelector('[data-testid="provenance-panel"]')
      if (panel) window.scrollTo({ top: panel.getBoundingClientRect().top + window.scrollY - 16 })
    })
    await shoot(page, 'release-provenance', { scroll: 'keep' })
  })
})
