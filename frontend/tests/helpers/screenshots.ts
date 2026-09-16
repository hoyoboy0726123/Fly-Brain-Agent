import { mkdirSync } from 'node:fs'
import path from 'node:path'

import type { Page } from '@playwright/test'

/**
 * Screenshots go to frontend/test-results/screenshots (git-ignored) unless
 * FLYBRAIN_SCREENSHOT_DIR points somewhere else (`make screenshots` uses docs/screenshots).
 */
const fromEnv = process.env['FLYBRAIN_SCREENSHOT_DIR']
export const SCREENSHOT_DIR = fromEnv
  ? path.resolve(process.cwd(), fromEnv)
  : path.resolve(import.meta.dirname, '..', '..', 'test-results', 'screenshots')
mkdirSync(SCREENSHOT_DIR, { recursive: true })

export const RELEASE_VIEWPORT = { width: 1440, height: 900 }

export async function shoot(page: Page, name: string, options: { scroll?: 'top' | 'keep' } = {}): Promise<void> {
  if ((options.scroll ?? 'top') === 'top') await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${name}.png`), fullPage: false })
}
