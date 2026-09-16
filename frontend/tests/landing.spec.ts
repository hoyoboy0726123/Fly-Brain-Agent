import { expect, test, type Page } from '@playwright/test'

/** P6.1 landing experience, demo story and presets (live backend). */

async function ready(page: Page, query = 'pace=5'): Promise<void> {
  await page.goto(`/?${query}`)
  await expect(page.getByTestId('backend-health-status')).toHaveText('ok')
  await expect(page.getByTestId('brain-node-LC4_L')).toBeVisible()
}

test.describe('P6.1 landing', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('above the fold: title, three-line tagline, two CTAs, qualifier and disclaimer', async ({ page }) => {
    await ready(page)
    const hero = page.getByTestId('hero')
    await expect(hero.getByRole('heading', { level: 1, name: 'FlyBrain Agent' })).toBeInViewport()
    await expect(page.getByTestId('hero-tagline')).toHaveText('Real fruit-fly connectome.Simulated neural activity.Observable behavior.')
    await expect(page.getByTestId('hero-tagline')).toBeInViewport()
    await expect(page.getByTestId('cta-run-demo')).toHaveText('RUN LOOMING DEMO')
    await expect(page.getByTestId('cta-run-demo')).toBeInViewport()
    await expect(page.getByTestId('cta-explore')).toHaveText('EXPLORE THE BRAIN')
    await expect(page.getByTestId('subtitle')).toHaveText('Connectome-grounded simulation using MaleCNS v1.0')
    await expect(page.getByTestId('subtitle')).toBeInViewport()
    await expect(page.getByTestId('scientific-labels')).toBeInViewport()
    await expect(page.getByTestId('story-strip')).toBeInViewport()
    await expect(page.getByTestId('disclaimer')).toContainText('NEURAL ACTIVITY IS SIMULATED')
  })

  test('RUN LOOMING DEMO runs the current preset (MEDIUM by default) and tells the story', async ({ page }) => {
    await ready(page)
    await expect(page.getByTestId('preset-medium')).toHaveAttribute('aria-pressed', 'true')
    for (let i = 1; i <= 4; i += 1) {
      await expect(page.getByTestId(`story-stage-${i}`)).toHaveAttribute('data-state', 'idle')
    }
    await page.getByTestId('cta-run-demo').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 20_000 })
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
    await expect(page.getByTestId('story-stage-1')).toHaveAttribute('data-state', 'done')
    await expect(page.getByTestId('story-stage-2')).toHaveAttribute('data-state', 'done')
    await expect(page.getByTestId('story-stage-3')).toHaveAttribute('data-state', 'done')
    await expect(page.getByTestId('story-stage-4')).toHaveAttribute('data-state', 'done')
    await expect(page.getByTestId('story-strip')).toContainText('OBJECT APPROACHES')
    await expect(page.getByTestId('story-strip')).toContainText('LC4 / LPLC2 ACTIVATE')
    await expect(page.getByTestId('story-strip')).toContainText('SIGNAL REACHES GIANT FIBER')
    await expect(page.getByTestId('story-strip')).toContainText('ESCAPE')
  })

  test('story strip follows the backend steps while replaying', async ({ page }) => {
    await ready(page, 'pace=3000')
    await page.getByTestId('preset-high').click()
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('brain-step')).toHaveText('step 1 / 30', { timeout: 15_000 })
    await expect(page.getByTestId('story-stage-1')).toHaveAttribute('data-state', 'active')
    await expect(page.getByTestId('story-stage-2')).toHaveAttribute('data-state', 'active')
    await expect(page.getByTestId('story-stage-4')).toHaveAttribute('data-state', 'idle')
    await expect(page.getByTestId('brain-step')).toHaveText('step 2 / 30')
    await expect(page.getByTestId('story-stage-3')).toHaveAttribute('data-state', 'active')
  })

  test('EXPLORE THE BRAIN opens the inspector', async ({ page }) => {
    await ready(page)
    await page.getByTestId('cta-explore').click()
    await expect(page.getByTestId('inspector-view')).toBeVisible()
    await expect(page).toHaveURL(/#inspector$/)
    await expect(page.getByTestId('hero')).toHaveCount(0)
    await page.getByTestId('tab-demo').click()
    await expect(page.getByTestId('hero')).toBeVisible()
  })

  test('presets set direction and intensity and state the expected current model result', async ({ page }) => {
    await ready(page)
    const low = page.getByTestId('preset-low')
    await expect(low).toContainText('CENTER / 0.2')
    await expect(low).toContainText('Expected current model result: NO ACTION')
    await expect(page.getByTestId('preset-medium')).toContainText('Expected current model result: ESCAPE')
    await expect(page.getByTestId('preset-high')).toContainText('CENTER / 1.0')
    await expect(page.getByTestId('environment-panel')).toContainText('not a biological threshold')

    await low.click()
    await expect(page.getByTestId('intensity-value')).toHaveText('0.20')
    await expect(page.getByTestId('direction-center')).toHaveAttribute('aria-pressed', 'true')
    await expect(low).toHaveAttribute('aria-pressed', 'true')
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 20_000 })
    await expect(page.getByTestId('action-value')).toHaveText('NO ACTION')
    await expect(page.getByTestId('story-stage-2')).toHaveAttribute('data-state', 'skipped')
    await expect(page.getByTestId('story-stage-4')).toHaveAttribute('data-state', 'no-action')

    await page.getByTestId('preset-high').click()
    await expect(page.getByTestId('intensity-value')).toHaveText('1.00')
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 20_000 })
    await expect(page.getByTestId('action-value')).toHaveText('ESCAPE')
  })

  test('manual control still works after a preset', async ({ page }) => {
    await ready(page)
    await page.getByTestId('preset-high').click()
    await page.getByTestId('direction-left').click()
    await page.getByTestId('intensity-input').fill('0.7')
    await expect(page.getByTestId('intensity-value')).toHaveText('0.70')
    await expect(page.getByTestId('preset-high')).toHaveAttribute('aria-pressed', 'false')
    await page.getByTestId('trigger-looming').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 20_000 })
    await expect(page.getByTestId('gf-activity')).toHaveText('Left')
  })

  test('reset returns the story to idle', async ({ page }) => {
    await ready(page)
    await page.getByTestId('cta-run-demo').click()
    await expect(page.getByTestId('demo-status')).toHaveText('finished', { timeout: 20_000 })
    await page.getByTestId('reset').click()
    await expect(page.getByTestId('demo-status')).toHaveText('idle')
    for (let i = 1; i <= 4; i += 1) {
      await expect(page.getByTestId(`story-stage-${i}`)).toHaveAttribute('data-state', 'idle')
    }
  })
})
