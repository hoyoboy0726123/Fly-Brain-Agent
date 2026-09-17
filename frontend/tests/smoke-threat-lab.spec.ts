import { expect, test, type Page } from '@playwright/test'

import { RELEASE_VIEWPORT, shoot } from './helpers/screenshots'

/** P7.1 screenshots A–E (live backend, no mocking) + a frontend memory/payload note. */

interface Outcome {
  first_escape_step: number | null
}

async function openLab(page: Page, query = 'pace=30'): Promise<void> {
  await page.goto(`/?${query}#threat-lab`)
  await expect(page.getByTestId('lab-node-LC4_L')).toBeVisible()
}

async function runPaused(page: Page): Promise<{ first: number; bytes: number }> {
  const responsePromise = page.waitForResponse((r) => r.url().includes('/embodiment/run'))
  await page.getByTestId('lab-run').click()
  const response = await responsePromise
  const body = await response.body()
  const outcome = ((await response.json()) as { outcome: Outcome }).outcome
  await expect(page.getByTestId('threat-lab')).toHaveAttribute('data-phase', 'ready')
  await page.getByTestId('lab-pause').click({ force: true })
  await expect(page.getByTestId('lab-status')).toHaveText('paused')
  return { first: outcome.first_escape_step ?? 0, bytes: body.length }
}

async function seek(page: Page, step: number): Promise<void> {
  await page.getByTestId('lab-slider').fill(String(step))
  await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', String(step))
}

test.describe('Threat Lab screenshots', () => {
  test.use({ viewport: RELEASE_VIEWPORT })

  test('A. initial state (WAITING FOR EXPERIMENT)', async ({ page }) => {
    await openLab(page)
    await expect(page.getByTestId('lab-overlay-text')).toHaveText('WAITING FOR EXPERIMENT')
    await shoot(page, 'threatlab-A-initial')
  })

  test('B. object approaching', async ({ page }) => {
    await openLab(page)
    const { first } = await runPaused(page)
    await seek(page, Math.max(1, first - 4))
    await expect(page.getByTestId('lab-action')).toHaveText('NO_ACTION')
    await shoot(page, 'threatlab-B-approaching')
  })

  test('C. ESCAPE event', async ({ page }) => {
    await openLab(page)
    const { first } = await runPaused(page)
    await seek(page, first)
    await expect(page.getByTestId('lab-action')).toHaveText('ESCAPE')
    await shoot(page, 'threatlab-C-escape-event')
  })

  test('D. post-escape body movement', async ({ page }) => {
    await openLab(page)
    const { first } = await runPaused(page)
    await seek(page, first + 1)
    await expect(page.getByTestId('lab-fly')).toHaveAttribute('data-grounded', 'false')
    await shoot(page, 'threatlab-D-post-escape-body')
  })

  test('E. replay at the ESCAPE step via the timeline marker', async ({ page }) => {
    await openLab(page)
    const { first, bytes } = await runPaused(page)
    await seek(page, 29)
    await page.getByTestId(`lab-marker-first_escape-${first}`).click()
    await expect(page.getByTestId('lab-step')).toHaveAttribute('data-step', String(first))
    await page.evaluate(() => document.getElementById('lab-panels')?.scrollIntoView({ block: 'start' }))
    await shoot(page, 'threatlab-E-replay-escape-step', { scroll: 'keep' })
    const heap = await page.evaluate(() => {
      const memory = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory
      return memory ? memory.usedJSHeapSize : null
    })
    // Recorded in PROGRESS.md; not asserted (browser-dependent).
    console.log(`[threat-lab] run payload ${(bytes / 1024).toFixed(1)} KiB; JS heap after replay ${heap === null ? 'n/a' : `${(heap / 1048576).toFixed(1)} MiB`}`)
  })
})
