import { expect, test, type Page } from '@playwright/test'

import { RELEASE_VIEWPORT, shoot } from './helpers/screenshots'

/** P7.2 screenshots (live backend, no mocking). */

async function openLab(page: Page): Promise<void> {
  await page.goto('/?pace=30#intervention')
  await expect(page.getByTestId('ilab-resolved')).not.toHaveText('resolving targets…')
}

async function runPaused(page: Page, selector: string): Promise<number> {
  await page.getByTestId('ilab-selector').selectOption(selector)
  const responsePromise = page.waitForResponse((r) => r.url().includes('/embodiment/intervention/compare'))
  await page.getByTestId('ilab-run').click()
  const result = (await (await responsePromise).json()) as { control: { experiment: { outcome: { first_escape_step: number | null } } } }
  await expect(page.getByTestId('intervention-lab')).toHaveAttribute('data-phase', 'ready')
  await page.getByTestId('ilab-pause').click({ force: true })
  await expect(page.getByTestId('ilab-status')).toHaveText('paused')
  return result.control.experiment.outcome.first_escape_step ?? 0
}

test.describe('Neural Intervention Lab screenshots', () => {
  test.use({ viewport: RELEASE_VIEWPORT })

  test('A. initial state', async ({ page }) => {
    await openLab(page)
    await shoot(page, 'intervention-A-initial')
  })

  test('B. SILENCE LPLC2 at the control ESCAPE step', async ({ page }) => {
    await openLab(page)
    const first = await runPaused(page, 'SILENCE_LPLC2')
    await page.getByTestId('ilab-slider').fill(String(first))
    await expect(page.getByTestId('ilab-step')).toHaveAttribute('data-step', String(first))
    await page.evaluate(() => document.getElementById('ilab-panels')?.scrollIntoView({ block: 'start' }))
    await shoot(page, 'intervention-B-silence-lplc2', { scroll: 'keep' })
  })

  test('C. SILENCE LC4 + LPLC2 comparison panel', async ({ page }) => {
    await openLab(page)
    await runPaused(page, 'SILENCE_LC4_LPLC2')
    await page.getByTestId('comparison-panel').scrollIntoViewIfNeeded()
    await page.evaluate(() => {
      const panel = document.querySelector('[data-testid="comparison-panel"]')
      if (panel) window.scrollTo({ top: panel.getBoundingClientRect().top + window.scrollY - 16 })
    })
    await shoot(page, 'intervention-C-comparison', { scroll: 'keep' })
  })
})
