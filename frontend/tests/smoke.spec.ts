import { expect, test } from '@playwright/test'

test.describe('backend health smoke (P0, phase updated per delivered phase)', () => {
  test('frontend loads', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/FlyBrain Agent/)
    await expect(page.getByRole('heading', { level: 1, name: 'FlyBrain Agent' })).toBeVisible()
  })

  test('frontend displays backend health from the live API', async ({ page }) => {
    await page.goto('/')
    const card = page.getByTestId('backend-health')
    await expect(card.getByTestId('backend-health-status')).toHaveText('ok')
    await expect(card.getByTestId('backend-health-service')).toHaveText('flybrain-agent-backend')
    await expect(card.getByTestId('backend-health-phase')).toHaveText('P6.1')
    await expect(card.getByTestId('backend-health-version')).not.toBeEmpty()
  })

  test('frontend shows an unreachable state when the backend is down', async ({ page }) => {
    await page.route('**/api/health', (route) => route.abort('connectionrefused'))
    await page.goto('/')
    await expect(page.getByTestId('backend-health-status')).toHaveText('unreachable')
    await expect(page.getByTestId('backend-health-error')).toBeVisible()
  })

  test('re-check button recovers once the backend is back', async ({ page }) => {
    // Keep the backend "down" for every request until we flip the flag; this stays
    // correct even though React StrictMode double-invokes the mount effect in dev.
    let backendDown = true
    await page.route('**/api/health', (route) =>
      backendDown ? route.abort('connectionrefused') : route.continue(),
    )
    await page.goto('/')
    const status = page.getByTestId('backend-health-status')
    await expect(status).toHaveText('unreachable')

    backendDown = false
    await page.getByRole('button', { name: 'Re-check' }).click()
    await expect(status).toHaveText('ok')
    await expect(page.getByTestId('backend-health-phase')).toHaveText('P6.1')
  })
})
