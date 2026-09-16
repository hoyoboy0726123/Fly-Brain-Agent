import { mkdirSync } from 'node:fs'
import path from 'node:path'

import { expect, test, type Page } from '@playwright/test'

/**
 * P5 smoke demo: the three documented scenarios end to end (live backend, no mocking),
 * with screenshots saved under docs/screenshots/.
 */

const SCREENSHOT_DIR = path.resolve(import.meta.dirname, '..', '..', 'docs', 'screenshots')
mkdirSync(SCREENSHOT_DIR, { recursive: true })

const SCENARIOS = [
  { name: 'center-0.2-no-action', direction: 'center', intensity: 0.2, action: 'NO ACTION', gf: 'None' },
  { name: 'center-0.5-escape', direction: 'center', intensity: 0.5, action: 'ESCAPE', gf: 'Both' },
  { name: 'left-1.0-escape', direction: 'left', intensity: 1, action: 'ESCAPE', gf: 'Left' },
] as const

async function shoot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${name}.png`), fullPage: false })
}

test.describe('P5 smoke demo', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('idle dashboard', async ({ page }) => {
    await page.goto('/?pace=30')
    await expect(page.getByTestId('backend-health-status')).toHaveText('ok')
    await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
    await shoot(page, 'p5-idle-dashboard')
  })

  for (const scenario of SCENARIOS) {
    test(`${scenario.direction.toUpperCase()} ${scenario.intensity} -> ${scenario.action}`, async ({ page }) => {
      await page.goto('/?pace=30')
      await expect(page.getByTestId('backend-health-status')).toHaveText('ok')
      await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
      await page.getByTestId(`direction-${scenario.direction}`).click()
      await page.getByTestId('intensity-input').fill(String(scenario.intensity))
      await page.getByTestId('trigger-looming').click()
      await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 30_000 })
      await expect(page.getByTestId('action-value')).toHaveText(scenario.action)
      await expect(page.getByTestId('gf-activity')).toHaveText(scenario.gf)
      await expect(page.getByTestId('disclaimer')).toContainText('NEURAL ACTIVITY IS SIMULATED')
      await shoot(page, `p5-${scenario.name}`)
      await page.getByTestId('how-it-works').locator('summary').click()
      await expect(page.getByTestId('biological-status')).toContainText('PARTIALLY SUPPORTED')
    })
  }

  test('mid-replay activity (CENTER 1.0): sensory groups at step 1, giant fibers at step 2', async ({ page }) => {
    await page.goto('/?pace=3000')
    await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
    await page.getByTestId('intensity-input').fill('1')
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('brain-step')).toHaveText('step 1 / 30', { timeout: 15_000 })
    await expect(page.getByTestId('brain-node-LPLC2_L')).toHaveAttribute('data-active', 'true')
    await shoot(page, 'p5-replay-step1-sensory')
    await expect(page.getByTestId('brain-step')).toHaveText('step 2 / 30')
    await expect(page.getByTestId('brain-node-DNp01_R')).toHaveAttribute('data-active', 'true')
    await shoot(page, 'p5-replay-step2-giant-fiber')
  })

  test('how it works section', async ({ page }) => {
    await page.goto('/?pace=30')
    await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
    const how = page.getByTestId('how-it-works')
    await how.locator('summary').click()
    await expect(page.getByTestId('biological-status')).toContainText('PARTIALLY SUPPORTED')
    await how.scrollIntoViewIfNeeded()
    await shoot(page, 'p5-how-it-works')
  })

  test('tablet layout stays usable', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.goto('/?pace=30')
    await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
    await expect(page.getByTestId('trigger-looming')).toBeVisible()
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 30_000 })
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await shoot(page, 'p5-tablet-1024x768')
  })
})
